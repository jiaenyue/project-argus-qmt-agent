"""
WebSocket 实时数据系统 - 数据集成服务
根据 tasks.md 任务6要求实现的数据集成服务，与现有 data_agent_service 系统集成
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import threading

# 导入现有系统组件
try:
    from data_agent_service.cache_manager import get_cache_manager, CacheManager
    from data_agent_service.optimized_data_service import get_global_data_service, OptimizedDataService, DataRequest
    from data_agent_service.auth_middleware import get_current_user
    from data_agent_service.security_config import security_config
except ImportError as e:
    logging.warning(f"无法导入data_agent_service组件: {e}")
    # 提供模拟实现以便测试
    get_cache_manager = None
    get_global_data_service = None
    get_current_user = None
    security_config = None

# 导入WebSocket模型
from .websocket_models import (
    QuoteData, KLineData, TradeData, DepthData, TickData,
    DataType, WebSocketMessage, MessageType, StatusMessage,
    PerformanceMetrics, ValidationResult
)

logger = logging.getLogger(__name__)

@dataclass
class DataIntegrationConfig:
    """数据集成配置"""
    cache_ttl_seconds: int = 60
    batch_size: int = 100
    max_concurrent_requests: int = 10
    data_consistency_check: bool = True
    enable_data_validation: bool = True
    enable_performance_monitoring: bool = True
    websocket_buffer_size: int = 1000
    rest_api_timeout: float = 30.0

@dataclass
class DataConsistencyResult:
    """数据一致性检查结果"""
    is_consistent: bool
    websocket_data: Any
    rest_api_data: Any
    differences: List[str]
    timestamp: datetime

class DataIntegrationService:
    """数据集成服务
    
    负责WebSocket服务与现有data_agent_service系统的集成，
    确保数据一致性、缓存共享和统一的认证日志系统。
    """
    
    def __init__(self, config: DataIntegrationConfig = None):
        self.config = config or DataIntegrationConfig()
        
        # 现有系统组件
        self.cache_manager: Optional[CacheManager] = None
        self.data_service: Optional[OptimizedDataService] = None
        
        # 数据订阅回调
        self._data_callbacks: Dict[str, List[Callable]] = {}
        self._callback_lock = threading.Lock()
        
        # 性能监控
        self._performance_metrics = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'data_consistency_checks': 0,
            'consistency_failures': 0,
            'average_response_time': 0.0,
            'last_update': datetime.now()
        }
        
        # 线程池
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_requests,
            thread_name_prefix="data_integration"
        )
        
        # 运行状态
        self._running = False
        self._background_tasks: List[asyncio.Task] = []
        
        logger.info("DataIntegrationService initialized")
    
    async def start(self):
        """启动数据集成服务"""
        if self._running:
            return
        
        try:
            # 初始化现有系统组件
            await self._initialize_components()
            
            # 启动后台任务
            self._running = True
            await self._start_background_tasks()
            
            logger.info("DataIntegrationService started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start DataIntegrationService: {e}")
            raise
    
    async def stop(self):
        """停止数据集成服务"""
        self._running = False
        
        # 取消后台任务
        for task in self._background_tasks:
            task.cancel()
        
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # 关闭线程池
        self._executor.shutdown(wait=True)
        
        logger.info("DataIntegrationService stopped")
    
    async def _initialize_components(self):
        """初始化现有系统组件"""
        try:
            # 初始化缓存管理器
            if get_cache_manager:
                self.cache_manager = get_cache_manager()
                if hasattr(self.cache_manager, 'start'):
                    await self.cache_manager.start()
                logger.info("Cache manager initialized")
            else:
                logger.warning("Cache manager not available")
            
            # 初始化数据服务
            if get_global_data_service:
                self.data_service = get_global_data_service()
                if hasattr(self.data_service, 'start'):
                    await self.data_service.start()
                logger.info("Data service initialized")
            else:
                logger.warning("Data service not available")
                
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    async def _start_background_tasks(self):
        """启动后台任务"""
        if self.config.enable_performance_monitoring:
            task = asyncio.create_task(self._performance_monitoring_loop())
            self._background_tasks.append(task)
        
        # 可以添加更多后台任务
        logger.info(f"Started {len(self._background_tasks)} background tasks")
    
    async def _performance_monitoring_loop(self):
        """性能监控循环"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟更新一次
                await self._update_performance_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
    
    async def _update_performance_metrics(self):
        """更新性能指标"""
        try:
            self._performance_metrics['last_update'] = datetime.now()
            
            # 计算缓存命中率
            total_cache_ops = self._performance_metrics['cache_hits'] + self._performance_metrics['cache_misses']
            if total_cache_ops > 0:
                hit_rate = self._performance_metrics['cache_hits'] / total_cache_ops
                logger.debug(f"Cache hit rate: {hit_rate:.2%}")
            
            # 计算数据一致性率
            consistency_checks = self._performance_metrics['data_consistency_checks']
            if consistency_checks > 0:
                consistency_rate = 1 - (self._performance_metrics['consistency_failures'] / consistency_checks)
                logger.debug(f"Data consistency rate: {consistency_rate:.2%}")
                
        except Exception as e:
            logger.error(f"Failed to update performance metrics: {e}")
    
    async def get_real_time_quote(self, symbol: str) -> Optional[QuoteData]:
        """获取实时行情数据"""
        start_time = time.time()
        self._performance_metrics['total_requests'] += 1
        
        try:
            # 首先检查缓存
            cached_data = await self._get_cached_quote(symbol)
            if cached_data:
                self._performance_metrics['cache_hits'] += 1
                return cached_data
            
            self._performance_metrics['cache_misses'] += 1
            
            # 从数据服务获取数据
            if not self.data_service:
                logger.warning("Data service not available")
                return None
            
            # 创建数据请求
            request = DataRequest(
                request_id=str(uuid.uuid4()),
                request_type='market_data',
                symbols=[symbol],
                fields=['lastPrice', 'change', 'changePercent', 'volume', 'amount', 
                       'bid1', 'ask1', 'bidVol1', 'askVol1', 'open', 'high', 'low', 'close', 'preClose'],
                params={},
                timestamp=datetime.now()
            )
            
            # 请求数据
            result = await self.data_service.request_data(request)
            
            if result.success and result.data:
                # 转换为QuoteData格式
                symbol_data = result.data.get(symbol, {})
                quote_data = await self._convert_to_quote_data(symbol, symbol_data)
                
                # 缓存数据
                if quote_data:
                    await self._cache_quote_data(symbol, quote_data)
                
                return quote_data
            else:
                logger.error(f"Failed to get quote data for {symbol}: {result.error}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting real-time quote for {symbol}: {e}")
            return None
        finally:
            # 更新响应时间
            response_time = time.time() - start_time
            self._update_average_response_time(response_time)
    
    async def get_latest_kline(self, symbol: str, period: str, count: int = 1) -> Optional[List[KLineData]]:
        """获取最新K线数据"""
        start_time = time.time()
        self._performance_metrics['total_requests'] += 1
        
        try:
            # 检查缓存
            cache_key = f"kline:{symbol}:{period}:{count}"
            cached_data = await self._get_cached_kline(cache_key)
            if cached_data:
                self._performance_metrics['cache_hits'] += 1
                return cached_data
            
            self._performance_metrics['cache_misses'] += 1
            
            # 从数据服务获取数据
            if not self.data_service:
                logger.warning("Data service not available")
                return None
            
            # 创建K线数据请求
            request = DataRequest(
                request_id=str(uuid.uuid4()),
                request_type='kline',
                symbols=[symbol],
                fields=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
                params={
                    'period': period,
                    'count': count,
                    'end_time': datetime.now().strftime('%Y%m%d')
                },
                timestamp=datetime.now()
            )
            
            # 请求数据
            result = await self.data_service.request_data(request)
            
            if result.success and result.data:
                # 转换为KLineData格式
                symbol_data = result.data.get(symbol, [])
                kline_data = await self._convert_to_kline_data(symbol, symbol_data, period)
                
                # 缓存数据
                if kline_data:
                    await self._cache_kline_data(cache_key, kline_data)
                
                return kline_data
            else:
                logger.error(f"Failed to get kline data for {symbol}: {result.error}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting kline data for {symbol}: {e}")
            return None
        finally:
            response_time = time.time() - start_time
            self._update_average_response_time(response_time)
    
    async def subscribe_to_data_updates(self, symbols: List[str], data_types: List[DataType], 
                                      callback: Callable[[str, DataType, Any], None]) -> str:
        """订阅数据更新"""
        subscription_id = str(uuid.uuid4())
        
        try:
            with self._callback_lock:
                for symbol in symbols:
                    for data_type in data_types:
                        key = f"{symbol}:{data_type.value}"
                        if key not in self._data_callbacks:
                            self._data_callbacks[key] = []
                        self._data_callbacks[key].append({
                            'subscription_id': subscription_id,
                            'callback': callback
                        })
            
            logger.info(f"Created subscription {subscription_id} for {len(symbols)} symbols and {len(data_types)} data types")
            return subscription_id
            
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            raise
    
    async def unsubscribe_from_data_updates(self, subscription_id: str) -> bool:
        """取消数据更新订阅"""
        try:
            removed_count = 0
            with self._callback_lock:
                for key in list(self._data_callbacks.keys()):
                    callbacks = self._data_callbacks[key]
                    self._data_callbacks[key] = [
                        cb for cb in callbacks 
                        if cb['subscription_id'] != subscription_id
                    ]
                    removed_count += len(callbacks) - len(self._data_callbacks[key])
                    
                    # 清理空的回调列表
                    if not self._data_callbacks[key]:
                        del self._data_callbacks[key]
            
            logger.info(f"Removed subscription {subscription_id}, cleaned {removed_count} callbacks")
            return removed_count > 0
            
        except Exception as e:
            logger.error(f"Error removing subscription {subscription_id}: {e}")
            return False
    
    async def publish_data_update(self, symbol: str, data_type: DataType, data: Any):
        """发布数据更新给订阅者"""
        try:
            key = f"{symbol}:{data_type.value}"
            
            with self._callback_lock:
                callbacks = self._data_callbacks.get(key, [])
            
            if callbacks:
                # 异步调用所有回调
                tasks = []
                for callback_info in callbacks:
                    callback = callback_info['callback']
                    task = asyncio.create_task(self._safe_callback(callback, symbol, data_type, data))
                    tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    logger.debug(f"Published {data_type.value} update for {symbol} to {len(callbacks)} subscribers")
            
        except Exception as e:
            logger.error(f"Error publishing data update for {symbol}: {e}")
    
    async def _safe_callback(self, callback: Callable, symbol: str, data_type: DataType, data: Any):
        """安全调用回调函数"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(symbol, data_type, data)
            else:
                callback(symbol, data_type, data)
        except Exception as e:
            logger.error(f"Error in data callback: {e}")
    
    async def check_data_consistency(self, symbol: str, data_type: DataType) -> DataConsistencyResult:
        """检查WebSocket数据与REST API数据的一致性"""
        self._performance_metrics['data_consistency_checks'] += 1
        
        try:
            # 获取WebSocket数据（从缓存）
            websocket_data = None
            if data_type == DataType.QUOTE:
                websocket_data = await self._get_cached_quote(symbol)
            elif data_type == DataType.KLINE:
                websocket_data = await self._get_cached_kline(f"kline:{symbol}:1d:1")
            
            # 获取REST API数据
            rest_api_data = None
            if data_type == DataType.QUOTE:
                rest_api_data = await self.get_real_time_quote(symbol)
            elif data_type == DataType.KLINE:
                rest_api_data = await self.get_latest_kline(symbol, "1d", 1)
            
            # 比较数据
            differences = []
            is_consistent = True
            
            if websocket_data and rest_api_data:
                differences = await self._compare_data(websocket_data, rest_api_data, data_type)
                is_consistent = len(differences) == 0
            elif websocket_data is None and rest_api_data is None:
                is_consistent = True
            else:
                is_consistent = False
                differences.append("One data source is None while the other is not")
            
            if not is_consistent:
                self._performance_metrics['consistency_failures'] += 1
                logger.warning(f"Data inconsistency detected for {symbol} {data_type.value}: {differences}")
            
            return DataConsistencyResult(
                is_consistent=is_consistent,
                websocket_data=websocket_data,
                rest_api_data=rest_api_data,
                differences=differences,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error checking data consistency for {symbol}: {e}")
            self._performance_metrics['consistency_failures'] += 1
            return DataConsistencyResult(
                is_consistent=False,
                websocket_data=None,
                rest_api_data=None,
                differences=[f"Error: {str(e)}"],
                timestamp=datetime.now()
            )
    
    async def get_market_status(self) -> Dict[str, Any]:
        """获取市场状态"""
        try:
            # 从数据服务获取市场状态
            if self.data_service:
                stats = self.data_service.get_stats()
                connection_status = stats.get('connection_status', {})
                
                return {
                    'is_market_open': connection_status.get('is_healthy', False),
                    'connection_status': connection_status.get('status_message', 'Unknown'),
                    'last_update': datetime.now(),
                    'data_service_stats': stats
                }
            else:
                return {
                    'is_market_open': False,
                    'connection_status': 'Data service not available',
                    'last_update': datetime.now()
                }
                
        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            return {
                'is_market_open': False,
                'connection_status': f'Error: {str(e)}',
                'last_update': datetime.now()
            }
    
    async def validate_auth_token(self, token: str) -> Dict[str, Any]:
        """验证认证令牌"""
        try:
            if security_config:
                is_valid = security_config.is_api_key_valid(token)
                if is_valid:
                    key_info = security_config.get_api_key_info(token)
                    return {
                        'valid': True,
                        'key_info': key_info
                    }
                else:
                    return {
                        'valid': False,
                        'error': 'Invalid API key'
                    }
            else:
                # 如果没有安全配置，允许所有请求（开发模式）
                return {
                    'valid': True,
                    'key_info': {
                        'name': 'Development Mode',
                        'permissions': ['read', 'write']
                    }
                }
                
        except Exception as e:
            logger.error(f"Error validating auth token: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    async def log_websocket_activity(self, client_id: str, action: str, details: Dict[str, Any]):
        """记录WebSocket活动日志"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'client_id': client_id,
                'action': action,
                'details': details,
                'service': 'websocket_integration'
            }
            
            # 使用现有的日志系统
            logger.info(f"WebSocket activity: {action}", extra=log_entry)
            
        except Exception as e:
            logger.error(f"Error logging WebSocket activity: {e}")
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """获取性能指标"""
        try:
            return PerformanceMetrics(
                connections_count=0,  # 这个需要从WebSocket管理器获取
                active_subscriptions=sum(len(callbacks) for callbacks in self._data_callbacks.values()),
                messages_per_second=0,  # 需要实现消息计数
                average_latency_ms=self._performance_metrics['average_response_time'] * 1000,
                memory_usage_mb=0,  # 需要实现内存监控
                cpu_usage_percent=0,  # 需要实现CPU监控
                network_io_mbps=0,  # 需要实现网络监控
                error_rate_percent=0,  # 需要实现错误率计算
                buffer_utilization_percent=0,  # 需要从缓冲区获取
                uptime_seconds=(datetime.now() - self._performance_metrics['last_update']).total_seconds()
            )
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return PerformanceMetrics(
                connections_count=0,
                active_subscriptions=0,
                messages_per_second=0,
                average_latency_ms=0,
                memory_usage_mb=0,
                cpu_usage_percent=0,
                network_io_mbps=0,
                error_rate_percent=0,
                buffer_utilization_percent=0,
                uptime_seconds=0
            )
    
    # 私有辅助方法
    
    async def _get_cached_quote(self, symbol: str) -> Optional[QuoteData]:
        """从缓存获取行情数据"""
        if not self.cache_manager:
            return None
        
        try:
            cached_data = await self.cache_manager.get_market_data(symbol, "quote")
            if cached_data:
                return QuoteData(**cached_data)
            return None
        except Exception as e:
            logger.error(f"Error getting cached quote for {symbol}: {e}")
            return None
    
    async def _cache_quote_data(self, symbol: str, quote_data: QuoteData):
        """缓存行情数据"""
        if not self.cache_manager:
            return
        
        try:
            await self.cache_manager.cache_market_data(
                symbol, "quote", quote_data.dict(), 
                ttl=self.config.cache_ttl_seconds
            )
        except Exception as e:
            logger.error(f"Error caching quote data for {symbol}: {e}")
    
    async def _get_cached_kline(self, cache_key: str) -> Optional[List[KLineData]]:
        """从缓存获取K线数据"""
        if not self.cache_manager:
            return None
        
        try:
            cached_data = await self.cache_manager.get(cache_key, cache_type="kline")
            if cached_data:
                return [KLineData(**item) for item in cached_data]
            return None
        except Exception as e:
            logger.error(f"Error getting cached kline data: {e}")
            return None
    
    async def _cache_kline_data(self, cache_key: str, kline_data: List[KLineData]):
        """缓存K线数据"""
        if not self.cache_manager:
            return
        
        try:
            data_dict = [item.dict() for item in kline_data]
            await self.cache_manager.set(
                cache_key, data_dict, 
                ttl=self.config.cache_ttl_seconds, 
                cache_type="kline"
            )
        except Exception as e:
            logger.error(f"Error caching kline data: {e}")
    
    async def _convert_to_quote_data(self, symbol: str, data: Dict[str, Any]) -> Optional[QuoteData]:
        """转换原始数据为QuoteData格式"""
        try:
            return QuoteData(
                symbol=symbol,
                timestamp=datetime.now(),
                last_price=Decimal(str(data.get('lastPrice', 0))),
                change=Decimal(str(data.get('change', 0))),
                change_percent=Decimal(str(data.get('changePercent', 0))),
                volume=int(data.get('volume', 0)),
                amount=Decimal(str(data.get('amount', 0))),
                bid_price=Decimal(str(data.get('bid1', 0))),
                ask_price=Decimal(str(data.get('ask1', 0))),
                bid_volume=int(data.get('bidVol1', 0)),
                ask_volume=int(data.get('askVol1', 0)),
                open=Decimal(str(data.get('open', 0))),
                high=Decimal(str(data.get('high', 0))),
                low=Decimal(str(data.get('low', 0))),
                close=Decimal(str(data.get('close', 0))),
                prev_close=Decimal(str(data.get('preClose', 0)))
            )
        except Exception as e:
            logger.error(f"Error converting to QuoteData: {e}")
            return None
    
    async def _convert_to_kline_data(self, symbol: str, data: List[Dict[str, Any]], period: str) -> List[KLineData]:
        """转换原始数据为KLineData格式"""
        try:
            kline_list = []
            for item in data:
                kline = KLineData(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(item.get('time', 0)),
                    period=period,
                    open=Decimal(str(item.get('open', 0))),
                    high=Decimal(str(item.get('high', 0))),
                    low=Decimal(str(item.get('low', 0))),
                    close=Decimal(str(item.get('close', 0))),
                    volume=int(item.get('volume', 0)),
                    amount=Decimal(str(item.get('amount', 0)))
                )
                kline_list.append(kline)
            return kline_list
        except Exception as e:
            logger.error(f"Error converting to KLineData: {e}")
            return []
    
    async def _compare_data(self, data1: Any, data2: Any, data_type: DataType) -> List[str]:
        """比较两个数据对象的差异"""
        differences = []
        
        try:
            if data_type == DataType.QUOTE:
                if isinstance(data1, QuoteData) and isinstance(data2, QuoteData):
                    # 比较关键字段
                    if abs(data1.last_price - data2.last_price) > Decimal('0.01'):
                        differences.append(f"last_price: {data1.last_price} vs {data2.last_price}")
                    if abs(data1.volume - data2.volume) > 100:
                        differences.append(f"volume: {data1.volume} vs {data2.volume}")
                    # 可以添加更多字段比较
            
            elif data_type == DataType.KLINE:
                if isinstance(data1, list) and isinstance(data2, list):
                    if len(data1) != len(data2):
                        differences.append(f"length: {len(data1)} vs {len(data2)}")
                    else:
                        # 比较最新的K线数据
                        if data1 and data2:
                            k1, k2 = data1[-1], data2[-1]
                            if abs(k1.close - k2.close) > Decimal('0.01'):
                                differences.append(f"close: {k1.close} vs {k2.close}")
            
        except Exception as e:
            differences.append(f"Comparison error: {str(e)}")
        
        return differences
    
    def _update_average_response_time(self, response_time: float):
        """更新平均响应时间"""
        current_avg = self._performance_metrics['average_response_time']
        total_requests = self._performance_metrics['total_requests']
        
        # 计算新的平均值
        new_avg = ((current_avg * (total_requests - 1)) + response_time) / total_requests
        self._performance_metrics['average_response_time'] = new_avg


# 全局数据集成服务实例
_global_integration_service: Optional[DataIntegrationService] = None

def get_data_integration_service() -> DataIntegrationService:
    """获取全局数据集成服务实例"""
    global _global_integration_service
    if _global_integration_service is None:
        _global_integration_service = DataIntegrationService()
    return _global_integration_service

async def init_data_integration_service(config: DataIntegrationConfig = None) -> DataIntegrationService:
    """初始化数据集成服务"""
    global _global_integration_service
    _global_integration_service = DataIntegrationService(config)
    await _global_integration_service.start()
    return _global_integration_service

async def shutdown_data_integration_service():
    """关闭数据集成服务"""
    global _global_integration_service
    if _global_integration_service:
        await _global_integration_service.stop()
        _global_integration_service = None