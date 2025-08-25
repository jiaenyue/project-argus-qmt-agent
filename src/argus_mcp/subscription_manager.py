"""
WebSocket 实时数据系统 - 订阅管理器
根据 tasks.md 任务3要求实现的订阅管理系统
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from .websocket_models import (
    Subscription, SubscriptionRequest, SubscriptionResponse, 
    SubscriptionStatus, DataType, ErrorMessage, WebSocketMessage,
    MessageType
)

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """订阅管理器 - 管理客户端的数据订阅和推送配置"""
    
    def __init__(self, max_subscriptions_per_client: int = 100):
        self.max_subscriptions_per_client = max_subscriptions_per_client
        
        # 存储结构
        self.subscriptions: Dict[str, Subscription] = {}  # subscription_id -> Subscription
        self.client_subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of subscription_ids
        self.symbol_subscribers: Dict[str, Dict[DataType, Set[str]]] = {}  # symbol -> data_type -> set of subscription_ids
        self.symbol_data_types: Dict[str, Set[DataType]] = {}  # symbol -> set of data_types
        
        # 限制和验证
        self.subscription_limits: Dict[str, int] = {}  # client_id -> current subscription count
        self._lock = asyncio.Lock()
        
    async def subscribe(
        self,
        client_id: str,
        subscription_request: SubscriptionRequest
    ) -> SubscriptionResponse:
        """
        添加新的订阅
        
        Args:
            client_id: 客户端唯一标识
            subscription_request: 订阅请求
            
        Returns:
            SubscriptionResponse: 订阅响应
        """
        try:
            # 验证客户端订阅数量限制
            current_count = self.subscription_limits.get(client_id, 0)
            if current_count >= self.max_subscriptions_per_client:
                return SubscriptionResponse(
                    subscription_id="",
                    status=SubscriptionStatus.ERROR,
                    message=f"订阅数量已达上限: {self.max_subscriptions_per_client}",
                    symbol=subscription_request.symbol,
                    data_type=subscription_request.data_type,
                    client_id=client_id
                )
            
            # 验证股票代码格式
            if not self._validate_symbol(subscription_request.symbol):
                return SubscriptionResponse(
                    subscription_id="",
                    status=SubscriptionStatus.ERROR,
                    message=f"无效的股票代码: {subscription_request.symbol}",
                    symbol=subscription_request.symbol,
                    data_type=subscription_request.data_type,
                    client_id=client_id
                )
            
            # 验证数据类型
            if subscription_request.data_type not in DataType:
                return SubscriptionResponse(
                    subscription_id="",
                    status=SubscriptionStatus.ERROR,
                    message=f"不支持的数据类型: {subscription_request.data_type}",
                    symbol=subscription_request.symbol,
                    data_type=subscription_request.data_type,
                    client_id=client_id
                )
            
            # 检查是否已经订阅
            existing_subscription = await self._find_existing_subscription(
                client_id, 
                subscription_request.symbol, 
                subscription_request.data_type,
                subscription_request.frequency
            )
            
            if existing_subscription:
                return SubscriptionResponse(
                    subscription_id=existing_subscription.subscription_id,
                    status=SubscriptionStatus.ACTIVE,
                    message="该订阅已存在",
                    symbol=subscription_request.symbol,
                    data_type=subscription_request.data_type,
                    client_id=client_id
                )
            
            # 创建新的订阅
            subscription = Subscription(
                subscription_id=self._generate_subscription_id(),
                client_id=client_id,
                symbol=subscription_request.symbol.upper(),
                data_type=subscription_request.data_type,
                frequency=subscription_request.frequency,
                filters=subscription_request.filters,
                status=SubscriptionStatus.ACTIVE
            )
            
            async with self._lock:
                # 添加到各种存储结构
                self.subscriptions[subscription.subscription_id] = subscription
                
                if client_id not in self.client_subscriptions:
                    self.client_subscriptions[client_id] = set()
                self.client_subscriptions[client_id].add(subscription.subscription_id)
                
                symbol = subscription.symbol
                if symbol not in self.symbol_subscribers:
                    self.symbol_subscribers[symbol] = {}
                    self.symbol_data_types[symbol] = set()
                
                if subscription.data_type not in self.symbol_subscribers[symbol]:
                    self.symbol_subscribers[symbol][subscription.data_type] = set()
                
                self.symbol_subscribers[symbol][subscription.data_type].add(subscription.subscription_id)
                self.symbol_data_types[symbol].add(subscription.data_type)
                
                # 更新客户端订阅计数
                self.subscription_limits[client_id] = current_count + 1
            
            logger.info(f"Client {client_id} subscribed to {subscription.symbol} {subscription.data_type}")
            
            return SubscriptionResponse(
                subscription_id=subscription.subscription_id,
                status=SubscriptionStatus.ACTIVE,
                message="订阅成功",
                symbol=subscription.symbol,
                data_type=subscription.data_type,
                client_id=client_id
            )
            
        except Exception as e:
            logger.error(f"Error subscribing client {client_id}: {e}")
            return SubscriptionResponse(
                subscription_id="",
                status=SubscriptionStatus.ERROR,
                message=f"订阅失败: {str(e)}",
                symbol=subscription_request.symbol,
                data_type=subscription_request.data_type,
                client_id=client_id
            )
    
    async def unsubscribe(
        self,
        client_id: str,
        subscription_id: str
    ) -> bool:
        """
        取消订阅
        
        Args:
            client_id: 客户端唯一标识
            subscription_id: 订阅唯一标识
            
        Returns:
            bool: 是否成功取消订阅
        """
        try:
            async with self._lock:
                # 检查订阅是否存在
                if subscription_id not in self.subscriptions:
                    logger.warning(f"Subscription {subscription_id} not found")
                    return False
                
                subscription = self.subscriptions[subscription_id]
                
                # 验证客户端是否有权限取消这个订阅
                if subscription.client_id != client_id:
                    logger.warning(f"Client {client_id} tried to unsubscribe other client's subscription")
                    return False
                
                # 从各种存储结构中移除
                symbol = subscription.symbol
                data_type = subscription.data_type
                
                # 移除订阅
                del self.subscriptions[subscription_id]
                
                # 从客户端订阅中移除
                if client_id in self.client_subscriptions:
                    self.client_subscriptions[client_id].discard(subscription_id)
                    if not self.client_subscriptions[client_id]:
                        del self.client_subscriptions[client_id]
                
                # 从股票订阅者中移除
                if symbol in self.symbol_subscribers and data_type in self.symbol_subscribers[symbol]:
                    self.symbol_subscribers[symbol][data_type].discard(subscription_id)
                    
                    # 清理空的集合
                    if not self.symbol_subscribers[symbol][data_type]:
                        del self.symbol_subscribers[symbol][data_type]
                        
                    if not self.symbol_subscribers[symbol]:
                        del self.symbol_subscribers[symbol]
                        del self.symbol_data_types[symbol]
                
                # 更新客户端订阅计数
                if client_id in self.subscription_limits:
                    self.subscription_limits[client_id] = max(0, self.subscription_limits[client_id] - 1)
                    if self.subscription_limits[client_id] == 0:
                        del self.subscription_limits[client_id]
            
            logger.info(f"Client {client_id} unsubscribed from {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error unsubscribing client {client_id}: {e}")
            return False
    
    async def unsubscribe_all(self, client_id: str) -> int:
        """
        取消客户端的所有订阅
        
        Args:
            client_id: 客户端唯一标识
            
        Returns:
            int: 取消的订阅数量
        """
        try:
            subscriptions_to_remove = []
            
            async with self._lock:
                if client_id not in self.client_subscriptions:
                    return 0
                
                subscriptions_to_remove = list(self.client_subscriptions[client_id])
            
            # 逐个取消订阅
            removed_count = 0
            for subscription_id in subscriptions_to_remove:
                if await self.unsubscribe(client_id, subscription_id):
                    removed_count += 1
            
            logger.info(f"Client {client_id} unsubscribed all {removed_count} subscriptions")
            return removed_count
            
        except Exception as e:
            logger.error(f"Error unsubscribing all for client {client_id}: {e}")
            return 0
    
    async def get_subscribers(
        self,
        symbol: str,
        data_type: DataType
    ) -> List[str]:
        """
        获取指定股票和数据类型的订阅者列表
        
        Args:
            symbol: 股票代码
            data_type: 数据类型
            
        Returns:
            List[str]: 客户端ID列表
        """
        try:
            symbol = symbol.upper()
            
            async with self._lock:
                if symbol not in self.symbol_subscribers or data_type not in self.symbol_subscribers[symbol]:
                    return []
                
                subscription_ids = self.symbol_subscribers[symbol][data_type]
                client_ids = []
                
                for subscription_id in subscription_ids:
                    if subscription_id in self.subscriptions:
                        subscription = self.subscriptions[subscription_id]
                        if subscription.status == SubscriptionStatus.ACTIVE:
                            client_ids.append(subscription.client_id)
                
                return list(set(client_ids))  # 去重
                
        except Exception as e:
            logger.error(f"Error getting subscribers for {symbol} {data_type}: {e}")
            return []
    
    async def get_client_subscriptions(
        self,
        client_id: str
    ) -> List[Subscription]:
        """
        获取客户端的所有订阅
        
        Args:
            client_id: 客户端唯一标识
            
        Returns:
            List[Subscription]: 订阅列表
        """
        try:
            async with self._lock:
                if client_id not in self.client_subscriptions:
                    return []
                
                subscriptions = []
                for subscription_id in self.client_subscriptions[client_id]:
                    if subscription_id in self.subscriptions:
                        subscriptions.append(self.subscriptions[subscription_id])
                
                return subscriptions
                
        except Exception as e:
            logger.error(f"Error getting subscriptions for client {client_id}: {e}")
            return []
    
    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """
        获取指定订阅信息
        
        Args:
            subscription_id: 订阅唯一标识
            
        Returns:
            Optional[Subscription]: 订阅信息或None
        """
        return self.subscriptions.get(subscription_id)
    
    async def get_subscription_stats(self) -> Dict[str, Any]:
        """
        获取订阅统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            async with self._lock:
                stats = {
                    "total_subscriptions": len(self.subscriptions),
                    "active_clients": len(self.client_subscriptions),
                    "subscribed_symbols": len(self.symbol_subscribers),
                    "subscriptions_per_data_type": {},
                    "subscriptions_per_symbol": {},
                    "client_subscription_counts": {}
                }
                
                # 按数据类型统计
                for subscription in self.subscriptions.values():
                    data_type = subscription.data_type.value
                    stats["subscriptions_per_data_type"][data_type] = \
                        stats["subscriptions_per_data_type"].get(data_type, 0) + 1
                
                # 按股票代码统计
                for symbol, data_types in self.symbol_data_types.items():
                    total_subscriptions = 0
                    for data_type in data_types:
                        if symbol in self.symbol_subscribers and data_type in self.symbol_subscribers[symbol]:
                            total_subscriptions += len(self.symbol_subscribers[symbol][data_type])
                    stats["subscriptions_per_symbol"][symbol] = total_subscriptions
                
                # 客户端订阅数量
                for client_id, count in self.subscription_limits.items():
                    stats["client_subscription_counts"][client_id] = count
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting subscription stats: {e}")
            return {}
    
    async def validate_subscription_request(
        self,
        subscription_request: SubscriptionRequest
    ) -> Dict[str, Any]:
        """
        验证订阅请求
        
        Args:
            subscription_request: 订阅请求
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        errors = []
        warnings = []
        
        # 验证股票代码
        if not self._validate_symbol(subscription_request.symbol):
            errors.append(f"无效的股票代码: {subscription_request.symbol}")
        
        # 验证数据类型
        if subscription_request.data_type not in DataType:
            errors.append(f"不支持的数据类型: {subscription_request.data_type}")
        
        # 验证频率
        if subscription_request.data_type == DataType.KLINE and subscription_request.frequency:
            valid_frequencies = ["1m", "5m", "15m", "30m", "1h", "1d", "1w", "1M"]
            if subscription_request.frequency not in valid_frequencies:
                errors.append(f"无效的K线周期: {subscription_request.frequency}")
        
        # 检查警告
        if subscription_request.symbol.upper() not in await self._get_available_symbols():
            warnings.append(f"股票代码可能不存在: {subscription_request.symbol}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _generate_subscription_id(self) -> str:
        """生成唯一的订阅ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _validate_symbol(self, symbol: str) -> bool:
        """验证股票代码格式"""
        if not symbol:
            return False
        
        symbol = symbol.upper()
        
        # 基本的股票代码格式验证
        # 支持A股、港股、美股等格式
        import re
        
        # A股: 6位数字，以0、3、6开头
        a_share_pattern = r'^(0|3|6)\d{5}$'
        
        # 港股: 1-5位数字
        hk_pattern = r'^\d{1,5}$'
        
        # 美股: 1-5位字母
        us_pattern = r'^[A-Z]{1,5}$'
        
        return bool(re.match(a_share_pattern, symbol) or 
                   re.match(hk_pattern, symbol) or 
                   re.match(us_pattern, symbol))
    
    async def _find_existing_subscription(
        self,
        client_id: str,
        symbol: str,
        data_type: DataType,
        frequency: Optional[str]
    ) -> Optional[Subscription]:
        """查找已存在的订阅"""
        try:
            async with self._lock:
                if client_id not in self.client_subscriptions:
                    return None
                
                for subscription_id in self.client_subscriptions[client_id]:
                    if subscription_id in self.subscriptions:
                        subscription = self.subscriptions[subscription_id]
                        if (subscription.symbol.upper() == symbol.upper() and
                            subscription.data_type == data_type and
                            subscription.frequency == frequency and
                            subscription.status == SubscriptionStatus.ACTIVE):
                            return subscription
                
                return None
                
        except Exception as e:
            logger.error(f"Error finding existing subscription: {e}")
            return None
    
    async def _get_available_symbols(self) -> List[str]:
        """获取可用的股票代码列表"""
        # TODO: 从数据源获取实际的股票代码列表
        # 暂时返回一些示例股票代码
        return [
            "000001", "000002", "000333", "000651", "002415",
            "600000", "600519", "601318", "601888", "603288",
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
            "00700", "03690", "09988", "01810", "00981"
        ]