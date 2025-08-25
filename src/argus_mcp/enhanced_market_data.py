"""
增强的市场数据服务
支持实时数据推送、大数据量处理和高性能数据流
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import websockets
from websockets.server import WebSocketServerProtocol
import aioredis
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

from .data_service_client import DataServiceClient
from .cache_config import OptimizedCacheConfig
from .performance_monitor import monitor_performance

logger = logging.getLogger(__name__)

@dataclass
class MarketDataSubscription:
    """市场数据订阅配置"""
    symbols: List[str]
    fields: List[str]
    frequency: int  # 推送频率（毫秒）
    client_id: str
    websocket: Optional[WebSocketServerProtocol] = None
    last_update: float = 0.0
    active: bool = True

@dataclass
class RealTimeMarketData:
    """实时市场数据结构"""
    symbol: str
    timestamp: float
    data: Dict[str, Any]
    sequence: int

class DataBuffer:
    """高性能数据缓冲区"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.index = {}  # symbol -> deque positions
        
    def add(self, data: RealTimeMarketData):
        """添加数据到缓冲区"""
        self.buffer.append(data)
        
        # 更新索引
        if data.symbol not in self.index:
            self.index[data.symbol] = deque(maxlen=1000)
        self.index[data.symbol].append(len(self.buffer) - 1)
    
    def get_latest(self, symbol: str, count: int = 1) -> List[RealTimeMarketData]:
        """获取指定股票的最新数据"""
        if symbol not in self.index:
            return []
        
        positions = list(self.index[symbol])[-count:]
        return [self.buffer[pos] for pos in positions if pos < len(self.buffer)]
    
    def get_range(self, symbol: str, start_time: float, end_time: float) -> List[RealTimeMarketData]:
        """获取指定时间范围的数据"""
        if symbol not in self.index:
            return []
        
        result = []
        for pos in self.index[symbol]:
            if pos < len(self.buffer):
                data = self.buffer[pos]
                if start_time <= data.timestamp <= end_time:
                    result.append(data)
        
        return sorted(result, key=lambda x: x.timestamp)

class EnhancedMarketDataService:
    """增强的市场数据服务"""
    
    def __init__(self):
        self.subscriptions: Dict[str, MarketDataSubscription] = {}
        self.data_buffer = DataBuffer()
        self.redis_client: Optional[aioredis.Redis] = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.sequence_counter = 0
        self.running = False
        
        # 性能统计
        self.stats = {
            'messages_sent': 0,
            'data_points_processed': 0,
            'active_subscriptions': 0,
            'buffer_size': 0,
            'last_update': time.time()
        }
    
    async def initialize(self):
        """初始化服务"""
        try:
            # 初始化Redis连接（用于分布式数据共享）
            self.redis_client = await aioredis.from_url(
                "redis://localhost:6379",
                decode_responses=True
            )
            logger.info("Enhanced market data service initialized")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, continuing without Redis")
    
    async def start_service(self):
        """启动服务"""
        self.running = True
        
        # 启动数据推送任务
        asyncio.create_task(self._data_push_loop())
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._stats_update_loop())
        
        logger.info("Enhanced market data service started")
    
    async def stop_service(self):
        """停止服务"""
        self.running = False
        
        # 关闭所有WebSocket连接
        for subscription in self.subscriptions.values():
            if subscription.websocket and not subscription.websocket.closed:
                await subscription.websocket.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        self.executor.shutdown(wait=True)
        logger.info("Enhanced market data service stopped")
    
    @monitor_performance()
    async def subscribe_real_time_data(
        self,
        client_id: str,
        symbols: List[str],
        fields: List[str] = None,
        frequency: int = 1000,  # 默认1秒推送一次
        websocket: Optional[WebSocketServerProtocol] = None
    ) -> bool:
        """订阅实时数据"""
        try:
            if fields is None:
                fields = ['open', 'high', 'low', 'close', 'volume', 'amount']
            
            subscription = MarketDataSubscription(
                symbols=symbols,
                fields=fields,
                frequency=frequency,
                client_id=client_id,
                websocket=websocket,
                last_update=time.time()
            )
            
            self.subscriptions[client_id] = subscription
            self.stats['active_subscriptions'] = len(self.subscriptions)
            
            logger.info(f"Client {client_id} subscribed to {len(symbols)} symbols")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe real-time data: {e}")
            return False
    
    async def unsubscribe_real_time_data(self, client_id: str) -> bool:
        """取消订阅实时数据"""
        try:
            if client_id in self.subscriptions:
                subscription = self.subscriptions[client_id]
                subscription.active = False
                
                if subscription.websocket and not subscription.websocket.closed:
                    await subscription.websocket.close()
                
                del self.subscriptions[client_id]
                self.stats['active_subscriptions'] = len(self.subscriptions)
                
                logger.info(f"Client {client_id} unsubscribed")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False
    
    @monitor_performance()
    async def get_batch_market_data(
        self,
        symbols: List[str],
        fields: List[str] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """批量获取市场数据（大数据量处理）"""
        try:
            if fields is None:
                fields = ['open', 'high', 'low', 'close', 'volume']
            
            results = {}
            
            # 分批处理大量股票代码
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i + batch_size]
                
                # 并行获取数据
                tasks = []
                async with DataServiceClient() as client:
                    for symbol in batch_symbols:
                        task = client.get_latest_market_data([symbol])
                        tasks.append(task)
                    
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # 处理结果
                    for j, result in enumerate(batch_results):
                        symbol = batch_symbols[j]
                        if not isinstance(result, Exception) and result:
                            results[symbol] = result
                        else:
                            logger.warning(f"Failed to get data for {symbol}: {result}")
            
            self.stats['data_points_processed'] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"Failed to get batch market data: {e}")
            return {}
    
    async def get_streaming_data(
        self,
        symbols: List[str],
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000
    ) -> List[RealTimeMarketData]:
        """获取流式数据"""
        try:
            if not start_time:
                start_time = time.time() - 3600  # 默认最近1小时
            if not end_time:
                end_time = time.time()
            
            all_data = []
            for symbol in symbols:
                symbol_data = self.data_buffer.get_range(symbol, start_time, end_time)
                all_data.extend(symbol_data)
            
            # 按时间排序并限制数量
            all_data.sort(key=lambda x: x.timestamp)
            return all_data[-limit:] if len(all_data) > limit else all_data
            
        except Exception as e:
            logger.error(f"Failed to get streaming data: {e}")
            return []
    
    async def _data_push_loop(self):
        """数据推送循环"""
        while self.running:
            try:
                current_time = time.time()
                
                for client_id, subscription in list(self.subscriptions.items()):
                    if not subscription.active:
                        continue
                    
                    # 检查是否需要推送
                    if current_time - subscription.last_update < subscription.frequency / 1000:
                        continue
                    
                    # 获取最新数据
                    try:
                        async with DataServiceClient() as client:
                            latest_data = await client.get_latest_market_data(subscription.symbols)
                            
                            if latest_data and subscription.websocket and not subscription.websocket.closed:
                                # 构造推送消息
                                message = {
                                    'type': 'market_data_update',
                                    'timestamp': current_time,
                                    'data': latest_data,
                                    'sequence': self.sequence_counter
                                }
                                
                                # 发送WebSocket消息
                                await subscription.websocket.send(json.dumps(message))
                                
                                # 添加到缓冲区
                                for symbol, data in latest_data.items():
                                    market_data = RealTimeMarketData(
                                        symbol=symbol,
                                        timestamp=current_time,
                                        data=data,
                                        sequence=self.sequence_counter
                                    )
                                    self.data_buffer.add(market_data)
                                
                                subscription.last_update = current_time
                                self.sequence_counter += 1
                                self.stats['messages_sent'] += 1
                                
                    except Exception as e:
                        logger.error(f"Failed to push data to client {client_id}: {e}")
                        # 标记订阅为非活跃
                        subscription.active = False
                
                await asyncio.sleep(0.1)  # 100ms检查间隔
                
            except Exception as e:
                logger.error(f"Error in data push loop: {e}")
                await asyncio.sleep(1)
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self.running:
            try:
                current_time = time.time()
                
                # 清理非活跃订阅
                inactive_clients = []
                for client_id, subscription in self.subscriptions.items():
                    if not subscription.active or (
                        subscription.websocket and subscription.websocket.closed
                    ):
                        inactive_clients.append(client_id)
                
                for client_id in inactive_clients:
                    await self.unsubscribe_real_time_data(client_id)
                
                # 更新统计信息
                self.stats['buffer_size'] = len(self.data_buffer.buffer)
                self.stats['active_subscriptions'] = len(self.subscriptions)
                
                await asyncio.sleep(30)  # 30秒清理一次
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(30)
    
    async def _stats_update_loop(self):
        """统计信息更新循环"""
        while self.running:
            try:
                self.stats['last_update'] = time.time()
                
                # 如果有Redis，保存统计信息
                if self.redis_client:
                    await self.redis_client.setex(
                        "market_data_stats",
                        300,  # 5分钟过期
                        json.dumps(self.stats)
                    )
                
                await asyncio.sleep(60)  # 1分钟更新一次
                
            except Exception as e:
                logger.error(f"Error in stats update loop: {e}")
                await asyncio.sleep(60)
    
    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        return {
            **self.stats,
            'uptime': time.time() - self.stats['last_update'],
            'subscriptions': {
                client_id: {
                    'symbols_count': len(sub.symbols),
                    'frequency': sub.frequency,
                    'active': sub.active,
                    'last_update': sub.last_update
                }
                for client_id, sub in self.subscriptions.items()
            }
        }

# 全局服务实例
enhanced_market_data_service = EnhancedMarketDataService()

async def initialize_enhanced_market_data():
    """初始化增强市场数据服务"""
    await enhanced_market_data_service.initialize()
    await enhanced_market_data_service.start_service()

async def cleanup_enhanced_market_data():
    """清理增强市场数据服务"""
    await enhanced_market_data_service.stop_service()