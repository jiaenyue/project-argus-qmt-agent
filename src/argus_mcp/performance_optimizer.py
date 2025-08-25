"""
WebSocket 服务性能优化器
实现内存和 CPU 使用优化、连接池管理、消息批处理等性能优化功能
"""

import asyncio
import gc
import logging
import psutil
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import weakref
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class PerformanceConfig:
    """性能优化配置"""
    # 内存优化
    memory_threshold_mb: float = 400.0
    gc_threshold_mb: float = 300.0
    gc_interval: float = 60.0
    
    # CPU优化
    cpu_threshold_percent: float = 80.0
    thread_pool_size: int = 4
    
    # 连接优化
    connection_pool_size: int = 1000
    idle_timeout: float = 300.0
    
    # 消息优化
    batch_size: int = 100
    batch_timeout: float = 0.1
    compression_threshold: int = 1024
    
    # 监控间隔
    monitoring_interval: float = 10.0


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime
    memory_usage_mb: float
    cpu_usage_percent: float
    active_connections: int
    message_queue_size: int
    gc_collections: int
    thread_pool_active: int
    batch_efficiency: float


class ConnectionPool:
    """连接池管理器"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.active_connections: Dict[str, Any] = {}
        self.idle_connections: deque = deque()
        self.connection_stats: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def get_connection(self, connection_id: str) -> Optional[Any]:
        """获取连接"""
        async with self._lock:
            if connection_id in self.active_connections:
                return self.active_connections[connection_id]
            
            # 从空闲连接池获取
            if self.idle_connections:
                connection = self.idle_connections.popleft()
                self.active_connections[connection_id] = connection
                return connection
            
            return None
    
    async def return_connection(self, connection_id: str, connection: Any):
        """归还连接到池"""
        async with self._lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
            
            if len(self.idle_connections) < self.max_size:
                self.idle_connections.append(connection)
    
    async def cleanup_idle_connections(self, timeout: float = 300.0):
        """清理空闲连接"""
        cutoff_time = time.time() - timeout
        cleaned = 0
        
        async with self._lock:
            # 清理过期的空闲连接
            while self.idle_connections:
                connection = self.idle_connections[0]
                if hasattr(connection, 'last_used') and connection.last_used < cutoff_time:
                    self.idle_connections.popleft()
                    cleaned += 1
                else:
                    break
        
        return cleaned


class MessageBatcher:
    """消息批处理器"""
    
    def __init__(self, batch_size: int = 100, timeout: float = 0.1):
        self.batch_size = batch_size
        self.timeout = timeout
        self.message_queue: deque = deque()
        self.batch_callbacks: List[Callable] = []
        self._lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_messages": 0,
            "total_batches": 0,
            "average_batch_size": 0.0
        }
    
    async def start(self):
        """启动批处理"""
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._batch_processor())
    
    async def stop(self):
        """停止批处理"""
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
    
    async def add_message(self, message: Any):
        """添加消息到批处理队列"""
        async with self._lock:
            self.message_queue.append(message)
            self._stats["total_messages"] += 1
    
    def register_batch_callback(self, callback: Callable):
        """注册批处理回调"""
        self.batch_callbacks.append(callback)
    
    async def _batch_processor(self):
        """批处理处理器"""
        try:
            while True:
                batch = []
                start_time = time.time()
                
                # 收集消息直到达到批大小或超时
                while len(batch) < self.batch_size and (time.time() - start_time) < self.timeout:
                    async with self._lock:
                        if self.message_queue:
                            batch.append(self.message_queue.popleft())
                        else:
                            await asyncio.sleep(0.01)  # 短暂等待
                
                # 处理批次
                if batch:
                    await self._process_batch(batch)
                    self._stats["total_batches"] += 1
                    self._stats["average_batch_size"] = self._stats["total_messages"] / self._stats["total_batches"]
                
                await asyncio.sleep(0.001)  # 防止CPU占用过高
                
        except asyncio.CancelledError:
            # 处理剩余消息
            if self.message_queue:
                remaining_batch = list(self.message_queue)
                await self._process_batch(remaining_batch)
    
    async def _process_batch(self, batch: List[Any]):
        """处理批次消息"""
        for callback in self.batch_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(batch)
                else:
                    callback(batch)
            except Exception as e:
                logger.error(f"批处理回调错误: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批处理统计"""
        return self._stats.copy()


class MemoryOptimizer:
    """内存优化器"""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.gc_stats = {
            "collections": 0,
            "freed_objects": 0,
            "last_collection": None
        }
        self._gc_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动内存优化"""
        self._gc_task = asyncio.create_task(self._gc_monitor())
    
    async def stop(self):
        """停止内存优化"""
        if self._gc_task and not self._gc_task.done():
            self._gc_task.cancel()
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用量(MB)"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def force_gc(self) -> Dict[str, Any]:
        """强制垃圾回收"""
        before_objects = len(gc.get_objects())
        collected = gc.collect()
        after_objects = len(gc.get_objects())
        
        self.gc_stats["collections"] += 1
        self.gc_stats["freed_objects"] += (before_objects - after_objects)
        self.gc_stats["last_collection"] = datetime.now()
        
        return {
            "collected": collected,
            "freed_objects": before_objects - after_objects,
            "remaining_objects": after_objects
        }
    
    async def _gc_monitor(self):
        """垃圾回收监控"""
        try:
            while True:
                await asyncio.sleep(self.config.gc_interval)
                
                memory_usage = self.get_memory_usage()
                if memory_usage > self.config.gc_threshold_mb:
                    logger.info(f"内存使用量 {memory_usage:.2f}MB 超过阈值，执行垃圾回收")
                    gc_result = self.force_gc()
                    logger.info(f"垃圾回收完成: {gc_result}")
                
        except asyncio.CancelledError:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取内存优化统计"""
        return {
            "current_memory_mb": self.get_memory_usage(),
            "gc_stats": self.gc_stats.copy()
        }


class CPUOptimizer:
    """CPU优化器"""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.thread_pool = ThreadPoolExecutor(max_workers=config.thread_pool_size)
        self.cpu_stats = {
            "peak_usage": 0.0,
            "average_usage": 0.0,
            "samples": deque(maxlen=100)
        }
    
    def get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        usage = psutil.cpu_percent(interval=0.1)
        self.cpu_stats["samples"].append(usage)
        
        if usage > self.cpu_stats["peak_usage"]:
            self.cpu_stats["peak_usage"] = usage
        
        if self.cpu_stats["samples"]:
            self.cpu_stats["average_usage"] = sum(self.cpu_stats["samples"]) / len(self.cpu_stats["samples"])
        
        return usage
    
    async def run_in_thread(self, func: Callable, *args, **kwargs):
        """在线程池中运行CPU密集型任务"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)
    
    def shutdown(self):
        """关闭线程池"""
        self.thread_pool.shutdown(wait=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取CPU优化统计"""
        return {
            "current_cpu_percent": self.get_cpu_usage(),
            "thread_pool_active": len(self.thread_pool._threads),
            "cpu_stats": self.cpu_stats.copy()
        }


class PerformanceOptimizer:
    """WebSocket性能优化器主类"""
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()
        
        # 优化组件
        self.connection_pool = ConnectionPool(self.config.connection_pool_size)
        self.message_batcher = MessageBatcher(self.config.batch_size, self.config.batch_timeout)
        self.memory_optimizer = MemoryOptimizer(self.config)
        self.cpu_optimizer = CPUOptimizer(self.config)
        
        # 监控任务
        self._monitoring_task: Optional[asyncio.Task] = None
        self.metrics_history: deque = deque(maxlen=1000)
        
        # 性能回调
        self.performance_callbacks: List[Callable] = []
    
    async def start(self):
        """启动性能优化器"""
        logger.info("启动WebSocket性能优化器")
        
        await self.message_batcher.start()
        await self.memory_optimizer.start()
        
        self._monitoring_task = asyncio.create_task(self._performance_monitor())
    
    async def stop(self):
        """停止性能优化器"""
        logger.info("停止WebSocket性能优化器")
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
        
        await self.message_batcher.stop()
        await self.memory_optimizer.stop()
        self.cpu_optimizer.shutdown()
    
    async def optimize_connection(self, connection_id: str, connection: Any):
        """优化连接"""
        return await self.connection_pool.get_connection(connection_id)
    
    async def optimize_message_sending(self, messages: List[Any]):
        """优化消息发送"""
        for message in messages:
            await self.message_batcher.add_message(message)
    
    def register_performance_callback(self, callback: Callable):
        """注册性能回调"""
        self.performance_callbacks.append(callback)
    
    def register_batch_callback(self, callback: Callable):
        """注册批处理回调"""
        self.message_batcher.register_batch_callback(callback)
    
    async def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能指标"""
        memory_stats = self.memory_optimizer.get_stats()
        cpu_stats = self.cpu_optimizer.get_stats()
        batch_stats = self.message_batcher.get_stats()
        
        return PerformanceMetrics(
            timestamp=datetime.now(),
            memory_usage_mb=memory_stats["current_memory_mb"],
            cpu_usage_percent=cpu_stats["current_cpu_percent"],
            active_connections=len(self.connection_pool.active_connections),
            message_queue_size=len(self.message_batcher.message_queue),
            gc_collections=memory_stats["gc_stats"]["collections"],
            thread_pool_active=cpu_stats["thread_pool_active"],
            batch_efficiency=batch_stats.get("average_batch_size", 0.0)
        )
    
    async def _performance_monitor(self):
        """性能监控循环"""
        try:
            while True:
                await asyncio.sleep(self.config.monitoring_interval)
                
                # 收集性能指标
                metrics = await self.get_current_metrics()
                self.metrics_history.append(metrics)
                
                # 检查性能阈值
                await self._check_performance_thresholds(metrics)
                
                # 执行优化操作
                await self._perform_optimizations(metrics)
                
                # 调用性能回调
                for callback in self.performance_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(metrics)
                        else:
                            callback(metrics)
                    except Exception as e:
                        logger.error(f"性能回调错误: {e}")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"性能监控错误: {e}")
    
    async def _check_performance_thresholds(self, metrics: PerformanceMetrics):
        """检查性能阈值"""
        warnings = []
        
        if metrics.memory_usage_mb > self.config.memory_threshold_mb:
            warnings.append(f"内存使用量过高: {metrics.memory_usage_mb:.2f}MB")
        
        if metrics.cpu_usage_percent > self.config.cpu_threshold_percent:
            warnings.append(f"CPU使用率过高: {metrics.cpu_usage_percent:.2f}%")
        
        if warnings:
            logger.warning(f"性能告警: {'; '.join(warnings)}")
    
    async def _perform_optimizations(self, metrics: PerformanceMetrics):
        """执行优化操作"""
        # 内存优化
        if metrics.memory_usage_mb > self.config.memory_threshold_mb:
            self.memory_optimizer.force_gc()
        
        # 连接池清理
        await self.connection_pool.cleanup_idle_connections(self.config.idle_timeout)
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """获取优化摘要"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest = self.metrics_history[-1]
        
        # 计算趋势
        if len(self.metrics_history) >= 10:
            recent_memory = [m.memory_usage_mb for m in list(self.metrics_history)[-10:]]
            recent_cpu = [m.cpu_usage_percent for m in list(self.metrics_history)[-10:]]
            
            memory_trend = recent_memory[-1] - recent_memory[0]
            cpu_trend = recent_cpu[-1] - recent_cpu[0]
        else:
            memory_trend = 0.0
            cpu_trend = 0.0
        
        return {
            "current_metrics": {
                "memory_usage_mb": latest.memory_usage_mb,
                "cpu_usage_percent": latest.cpu_usage_percent,
                "active_connections": latest.active_connections,
                "message_queue_size": latest.message_queue_size,
                "batch_efficiency": latest.batch_efficiency
            },
            "trends": {
                "memory_trend_mb": memory_trend,
                "cpu_trend_percent": cpu_trend
            },
            "optimizations": {
                "gc_collections": latest.gc_collections,
                "thread_pool_active": latest.thread_pool_active,
                "connection_pool_size": len(self.connection_pool.active_connections)
            },
            "recommendations": self._get_optimization_recommendations(latest)
        }
    
    def _get_optimization_recommendations(self, metrics: PerformanceMetrics) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        if metrics.memory_usage_mb > self.config.memory_threshold_mb * 0.8:
            recommendations.append("考虑增加垃圾回收频率或减少内存缓存")
        
        if metrics.cpu_usage_percent > self.config.cpu_threshold_percent * 0.8:
            recommendations.append("考虑增加线程池大小或优化CPU密集型操作")
        
        if metrics.message_queue_size > self.config.batch_size * 2:
            recommendations.append("考虑增加批处理大小或减少批处理超时时间")
        
        if metrics.batch_efficiency < self.config.batch_size * 0.5:
            recommendations.append("考虑调整批处理参数以提高效率")
        
        return recommendations