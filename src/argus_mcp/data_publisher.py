"""
WebSocket 实时数据系统 - 数据推送服务
根据 tasks.md 任务4要求实现的数据推送服务
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from .websocket_models import (
    WebSocketMessage, MessageType, DataType, TickData, 
    QuoteData, KLineData, TradeData, DepthData, OrderBookData,
    ErrorMessage, SubscriptionStatus
)
from .subscription_manager import SubscriptionManager
from .websocket_connection_manager import WebSocketConnectionManager

logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """数据源配置"""
    source_type: str  # "mock", "qmt", "tdx", "yahoo"
    update_interval: float = 1.0  # 秒
    batch_size: int = 100
    retry_attempts: int = 3
    retry_delay: float = 1.0


class DataPublisher:
    """数据推送服务 - 负责从数据源获取数据并推送给订阅者"""
    
    def __init__(
        self,
        subscription_manager: SubscriptionManager,
        connection_manager: WebSocketConnectionManager,
        config: DataSourceConfig = None
    ):
        self.subscription_manager = subscription_manager
        self.connection_manager = connection_manager
        self.config = config or DataSourceConfig()
        
        # 运行状态
        self.is_running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # 数据缓存
        self._data_cache: Dict[str, Dict[str, Any]] = {}  # symbol -> data_type -> latest_data
        self._last_update: Dict[str, Dict[str, datetime]] = {}  # symbol -> data_type -> last_update
        
        # 订阅跟踪
        self._active_symbols: Set[str] = set()
        self._symbol_subscribers: Dict[str, int] = {}  # symbol -> subscriber_count
        
    async def start(self):
        """启动数据推送服务"""
        if self.is_running:
            logger.warning("DataPublisher already running")
            return
            
        self.is_running = True
        logger.info("Starting DataPublisher...")
        
        # 启动数据更新任务
        update_task = asyncio.create_task(self._data_update_loop())
        self._tasks.append(update_task)
        
        # 启动订阅监控任务
        monitor_task = asyncio.create_task(self._subscription_monitor_loop())
        self._tasks.append(monitor_task)
        
        logger.info("DataPublisher started successfully")
    
    async def stop(self):
        """停止数据推送服务"""
        if not self.is_running:
            return
            
        self.is_running = False
        logger.info("Stopping DataPublisher...")
        
        # 取消所有任务
        for task in self._tasks:
            task.cancel()
        
        # 等待所有任务完成
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        logger.info("DataPublisher stopped")
    
    async def _data_update_loop(self):
        """数据更新主循环"""
        logger.info("Starting data update loop...")
        
        while self.is_running:
            try:
                # 获取当前活跃的股票列表
                active_symbols = await self._get_active_symbols()
                
                if active_symbols:
                    # 更新数据
                    await self._update_symbol_data(active_symbols)
                    
                    # 推送数据给订阅者
                    await self._push_data_to_subscribers(active_symbols)
                
                # 等待下一次更新
                await asyncio.sleep(self.config.update_interval)
                
            except asyncio.CancelledError:
                logger.info("Data update loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in data update loop: {e}")
                await asyncio.sleep(self.config.retry_delay)
    
    async def _subscription_monitor_loop(self):
        """订阅监控循环"""
        logger.info("Starting subscription monitor loop...")
        
        while self.is_running:
            try:
                # 检查订阅状态变化
                await self._check_subscription_changes()
                
                # 清理无效数据
                await self._cleanup_inactive_data()
                
                # 每5秒检查一次
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                logger.info("Subscription monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in subscription monitor loop: {e}")
                await asyncio.sleep(1)
    
    async def _get_active_symbols(self) -> Set[str]:
        """获取当前有订阅的股票列表"""
        try:
            stats = await self.subscription_manager.get_subscription_stats()
            subscribed_symbols = stats.get("subscriptions_per_symbol", {})
            return set(subscribed_symbols.keys())
        except Exception as e:
            logger.error(f"Error getting active symbols: {e}")
            return set()
    
    async def _update_symbol_data(self, symbols: Set[str]):
        """更新股票数据"""
        try:
            for symbol in symbols:
                # 获取该股票的所有订阅数据类型
                data_types = await self._get_symbol_data_types(symbol)
                
                for data_type in data_types:
                    # 获取最新数据
                    data = await self._fetch_data(symbol, data_type)
                    if data:
                        # 更新缓存
                        await self._update_cache(symbol, data_type, data)
                        
                        # 记录更新时间
                        if symbol not in self._last_update:
                            self._last_update[symbol] = {}
                        self._last_update[symbol][data_type.value] = datetime.now()
                        
        except Exception as e:
            logger.error(f"Error updating symbol data: {e}")
    
    async def _get_symbol_data_types(self, symbol: str) -> List[DataType]:
        """获取股票的所有订阅数据类型"""
        try:
            # 获取该股票的所有订阅
            stats = await self.subscription_manager.get_subscription_stats()
            subscriptions = await self.subscription_manager.subscriptions.values()
            
            data_types = set()
            for subscription in subscriptions:
                if subscription.symbol.upper() == symbol.upper():
                    data_types.add(subscription.data_type)
            
            return list(data_types)
        except Exception as e:
            logger.error(f"Error getting symbol data types: {e}")
            return []
    
    async def _fetch_data(self, symbol: str, data_type: DataType) -> Optional[Dict[str, Any]]:
        """从数据源获取数据"""
        try:
            if self.config.source_type == "mock":
                return await self._generate_mock_data(symbol, data_type)
            elif self.config.source_type == "qmt":
                return await self._fetch_from_qmt(symbol, data_type)
            elif self.config.source_type == "tdx":
                return await self._fetch_from_tdx(symbol, data_type)
            else:
                logger.warning(f"Unknown data source: {self.config.source_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching data for {symbol} {data_type}: {e}")
            return None
    
    async def _generate_mock_data(self, symbol: str, data_type: DataType) -> Optional[Dict[str, Any]]:
        """生成模拟数据"""
        import random
        import time
        
        timestamp = int(time.time() * 1000)
        
        if data_type == DataType.TICK:
            return {
                "symbol": symbol,
                "timestamp": timestamp,
                "price": round(random.uniform(10.0, 100.0), 2),
                "volume": random.randint(100, 10000),
                "turnover": round(random.uniform(1000.0, 100000.0), 2),
                "change": round(random.uniform(-5.0, 5.0), 2),
                "change_percent": round(random.uniform(-10.0, 10.0), 2)
            }
        
        elif data_type == DataType.QUOTE:
            return {
                "symbol": symbol,
                "timestamp": timestamp,
                "open": round(random.uniform(10.0, 100.0), 2),
                "high": round(random.uniform(10.0, 100.0), 2),
                "low": round(random.uniform(10.0, 100.0), 2),
                "close": round(random.uniform(10.0, 100.0), 2),
                "volume": random.randint(100000, 10000000),
                "turnover": round(random.uniform(1000000.0, 100000000.0), 2)
            }
        
        elif data_type == DataType.KLINE:
            return {
                "symbol": symbol,
                "timestamp": timestamp,
                "open": round(random.uniform(10.0, 100.0), 2),
                "high": round(random.uniform(10.0, 100.0), 2),
                "low": round(random.uniform(10.0, 100.0), 2),
                "close": round(random.uniform(10.0, 100.0), 2),
                "volume": random.randint(100000, 10000000),
                "turnover": round(random.uniform(1000000.0, 100000000.0), 2),
                "frequency": "1m"
            }
        
        elif data_type == DataType.TRADE:
            return {
                "symbol": symbol,
                "timestamp": timestamp,
                "price": round(random.uniform(10.0, 100.0), 2),
                "volume": random.randint(100, 10000),
                "amount": round(random.uniform(1000.0, 100000.0), 2),
                "direction": random.choice(["buy", "sell"]),
                "trade_type": random.choice(["normal", "block"])
            }
        
        elif data_type == DataType.ORDERBOOK:
            bids = [[round(random.uniform(10.0, 100.0), 2), random.randint(100, 10000)] 
                   for _ in range(5)]
            asks = [[round(random.uniform(10.0, 100.0), 2), random.randint(100, 10000)] 
                   for _ in range(5)]
            
            return {
                "symbol": symbol,
                "timestamp": timestamp,
                "bids": bids,
                "asks": asks,
                "total_bid_volume": sum([bid[1] for bid in bids]),
                "total_ask_volume": sum([ask[1] for ask in asks])
            }
        
        return None
    
    async def _fetch_from_qmt(self, symbol: str, data_type: DataType) -> Optional[Dict[str, Any]]:
        """从QMT获取数据"""
        # TODO: 实现QMT数据获取
        logger.info(f"Fetching {data_type} data for {symbol} from QMT")
        return await self._generate_mock_data(symbol, data_type)
    
    async def _fetch_from_tdx(self, symbol: str, data_type: DataType) -> Optional[Dict[str, Any]]:
        """从TDX获取数据"""
        # TODO: 实现TDX数据获取
        logger.info(f"Fetching {data_type} data for {symbol} from TDX")
        return await self._generate_mock_data(symbol, data_type)
    
    async def _update_cache(self, symbol: str, data_type: DataType, data: Dict[str, Any]):
        """更新数据缓存"""
        if symbol not in self._data_cache:
            self._data_cache[symbol] = {}
        self._data_cache[symbol][data_type.value] = data
    
    async def _push_data_to_subscribers(self, symbols: Set[str]):
        """将数据推送给订阅者"""
        try:
            for symbol in symbols:
                # 获取该股票的订阅者
                data_types = await self._get_symbol_data_types(symbol)
                
                for data_type in data_types:
                    # 获取数据
                    data = self._data_cache.get(symbol, {}).get(data_type.value)
                    if not data:
                        continue
                    
                    # 获取订阅者
                    subscribers = await self.subscription_manager.get_subscribers(symbol, data_type)
                    
                    if subscribers:
                        # 创建WebSocket消息
                        message = WebSocketMessage(
                            type=MessageType.DATA,
                            data={
                                "symbol": symbol,
                                "data_type": data_type.value,
                                "data": data,
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        
                        # 推送数据
                        await self._broadcast_to_subscribers(subscribers, message)
                        
        except Exception as e:
            logger.error(f"Error pushing data to subscribers: {e}")
    
    async def _broadcast_to_subscribers(self, subscribers: List[str], message: WebSocketMessage):
        """向订阅者广播消息"""
        try:
            for client_id in subscribers:
                await self.connection_manager.send_message(client_id, message)
        except Exception as e:
            logger.error(f"Error broadcasting to subscribers: {e}")
    
    async def _check_subscription_changes(self):
        """检查订阅状态变化"""
        try:
            current_symbols = await self._get_active_symbols()
            
            # 检查新增加的股票
            new_symbols = current_symbols - self._active_symbols
            if new_symbols:
                logger.info(f"New symbols added: {new_symbols}")
                self._active_symbols.update(new_symbols)
            
            # 检查移除的股票
            removed_symbols = self._active_symbols - current_symbols
            if removed_symbols:
                logger.info(f"Symbols removed: {removed_symbols}")
                self._active_symbols.difference_update(removed_symbols)
                
                # 清理相关缓存
                for symbol in removed_symbols:
                    if symbol in self._data_cache:
                        del self._data_cache[symbol]
                    if symbol in self._last_update:
                        del self._last_update[symbol]
                        
        except Exception as e:
            logger.error(f"Error checking subscription changes: {e}")
    
    async def _cleanup_inactive_data(self):
        """清理无效数据"""
        try:
            current_time = datetime.now()
            
            # 清理过期缓存数据（超过10分钟未更新）
            for symbol in list(self._data_cache.keys()):
                if symbol not in self._active_symbols:
                    del self._data_cache[symbol]
                    continue
                
                # 清理过期数据
                for data_type in list(self._data_cache[symbol].keys()):
                    last_update = self._last_update.get(symbol, {}).get(data_type)
                    if last_update and (current_time - last_update) > timedelta(minutes=10):
                        del self._data_cache[symbol][data_type]
                        if symbol in self._last_update:
                            del self._last_update[symbol][data_type]
                        
                        if not self._data_cache[symbol]:
                            del self._data_cache[symbol]
                        
        except Exception as e:
            logger.error(f"Error cleaning up inactive data: {e}")
    
    async def get_publisher_stats(self) -> Dict[str, Any]:
        """获取推送服务统计信息"""
        return {
            "is_running": self.is_running,
            "active_symbols": list(self._active_symbols),
            "cached_symbols": list(self._data_cache.keys()),
            "data_source": self.config.source_type,
            "update_interval": self.config.update_interval,
            "cache_size": len(self._data_cache),
            "last_update_times": {
                symbol: {
                    data_type: last_update.isoformat() if isinstance(last_update, datetime) else str(last_update)
                    for data_type, last_update in self._last_update.get(symbol, {}).items()
                }
                for symbol in self._last_update
            }
        }