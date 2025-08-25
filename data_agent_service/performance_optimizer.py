#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能优化模块
实现数据缓存、批量处理、响应时间优化等功能
"""

import asyncio
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"  # 最近最少使用
    LFU = "lfu"  # 最少使用频率
    TTL = "ttl"  # 时间过期
    FIFO = "fifo"  # 先进先出

class OptimizationLevel(Enum):
    """优化级别"""
    CONSERVATIVE = "conservative"  # 保守优化
    BALANCED = "balanced"  # 平衡优化
    AGGRESSIVE = "aggressive"  # 激进优化

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl_seconds is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds
    
    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed = datetime.now()
        self.access_count += 1

@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    batch_operations: int = 0
    concurrent_operations: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    def update_response_time(self, response_time: float):
        """更新响应时间统计"""
        self.min_response_time = min(self.min_response_time, response_time)
        self.max_response_time = max(self.max_response_time, response_time)
        
        # 计算移动平均
        if self.total_requests == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                (self.avg_response_time * self.total_requests + response_time) / 
                (self.total_requests + 1)
            )
        
        self.total_requests += 1

class SmartCache:
    """智能缓存系统"""
    
    def __init__(
        self,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.LRU,
        default_ttl: Optional[int] = None
    ):
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order = deque()  # For LRU
        self._lock = threading.RLock()
        
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired():
                self._remove(key)
                return None
            
            entry.touch()
            
            # 更新访问顺序（LRU）
            if self.strategy == CacheStrategy.LRU:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
            
            return entry.value
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """存储缓存值"""
        with self._lock:
            # 检查是否需要清理空间
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict()
            
            ttl = ttl or self.default_ttl
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                ttl_seconds=ttl
            )
            
            self._cache[key] = entry
            
            # 更新访问顺序
            if self.strategy == CacheStrategy.LRU:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
    
    def _evict(self) -> None:
        """根据策略驱逐缓存项"""
        if not self._cache:
            return
        
        if self.strategy == CacheStrategy.LRU:
            # 移除最近最少使用的项
            if self._access_order:
                key_to_remove = self._access_order.popleft()
                self._remove(key_to_remove)
        
        elif self.strategy == CacheStrategy.LFU:
            # 移除使用频率最低的项
            min_access_key = min(self._cache.keys(), 
                               key=lambda k: self._cache[k].access_count)
            self._remove(min_access_key)
        
        elif self.strategy == CacheStrategy.FIFO:
            # 移除最早创建的项
            oldest_key = min(self._cache.keys(), 
                           key=lambda k: self._cache[k].created_at)
            self._remove(oldest_key)
    
    def _remove(self, key: str) -> None:
        """移除缓存项"""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            self._access_order.remove(key)
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                self._remove(key)
            
            return len(expired_keys)

class BatchProcessor:
    """批量处理器"""
    
    def __init__(
        self,
        batch_size: int = 10,
        max_wait_time: float = 0.1,
        max_workers: int = 4
    ):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.max_workers = max_workers
        self._pending_requests: List[Tuple[Callable, tuple, dict]] = []
        self._batch_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def process_batch(
        self,
        func: Callable,
        requests: List[Tuple[tuple, dict]]
    ) -> List[Any]:
        """批量处理请求"""
        if not requests:
            return []
        
        # 如果只有一个请求，直接处理
        if len(requests) == 1:
            args, kwargs = requests[0]
            return [await self._execute_single(func, args, kwargs)]
        
        # 并发处理多个请求
        tasks = []
        for args, kwargs in requests:
            task = asyncio.create_task(
                self._execute_single(func, args, kwargs)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def _execute_single(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """执行单个请求"""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # 在线程池中执行同步函数
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self._executor, lambda: func(*args, **kwargs)
                )
        except Exception as e:
            logger.error(f"Error executing function {func.__name__}: {str(e)}")
            raise

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(
        self,
        optimization_level: OptimizationLevel = OptimizationLevel.BALANCED,
        cache_size: int = 1000,
        cache_ttl: int = 300,  # 5分钟
        batch_size: int = 10,
        enable_compression: bool = True
    ):
        self.optimization_level = optimization_level
        self.enable_compression = enable_compression
        
        # 初始化缓存
        self.cache = SmartCache(
            max_size=cache_size,
            strategy=CacheStrategy.LRU,
            default_ttl=cache_ttl
        )
        
        # 初始化批量处理器
        self.batch_processor = BatchProcessor(batch_size=batch_size)
        
        # 性能指标
        self.metrics = PerformanceMetrics()
        
        # 响应时间历史（用于计算趋势）
        self._response_times = deque(maxlen=1000)
        
        # 定期清理任务
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动定期清理任务"""
        def cleanup_worker():
            while True:
                try:
                    # 清理过期缓存
                    expired_count = self.cache.cleanup_expired()
                    if expired_count > 0:
                        logger.debug(f"Cleaned up {expired_count} expired cache entries")
                    
                    time.sleep(60)  # 每分钟清理一次
                except Exception as e:
                    logger.error(f"Error in cleanup task: {str(e)}")
                    time.sleep(60)
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def cached(self, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
        """缓存装饰器"""
        def decorator(func: Callable) -> Callable:
            from functools import wraps
            
            @wraps(func)  # 保留原始函数的签名和元数据
            async def async_wrapper(*args, **kwargs):
                # 生成缓存键
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self.cache._generate_key(func.__name__, args, kwargs)
                
                # 尝试从缓存获取
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self.metrics.cache_hits += 1
                    return cached_result
                
                self.metrics.cache_misses += 1
                
                # 执行函数并缓存结果
                start_time = time.time()
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    # 缓存结果
                    self.cache.put(cache_key, result, ttl)
                    
                    # 更新性能指标
                    response_time = time.time() - start_time
                    self.metrics.update_response_time(response_time)
                    self._response_times.append(response_time)
                    
                    return result
                    
                except Exception as e:
                    # 即使出错也要更新响应时间
                    response_time = time.time() - start_time
                    self.metrics.update_response_time(response_time)
                    raise
            
            @wraps(func)  # 保留原始函数的签名和元数据
            def sync_wrapper(*args, **kwargs):
                # 对于同步函数的简化版本
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self.cache._generate_key(func.__name__, args, kwargs)
                
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self.metrics.cache_hits += 1
                    return cached_result
                
                self.metrics.cache_misses += 1
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    self.cache.put(cache_key, result, ttl)
                    
                    response_time = time.time() - start_time
                    self.metrics.update_response_time(response_time)
                    self._response_times.append(response_time)
                    
                    return result
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    self.metrics.update_response_time(response_time)
                    raise
            
            # 根据函数类型返回相应的包装器
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "cache": {
                "size": self.cache.size(),
                "max_size": self.cache.max_size,
                "hit_rate": self.metrics.cache_hit_rate,
                "hits": self.metrics.cache_hits,
                "misses": self.metrics.cache_misses
            },
            "response_times": {
                "avg": self.metrics.avg_response_time,
                "min": self.metrics.min_response_time if self.metrics.min_response_time != float('inf') else 0,
                "max": self.metrics.max_response_time,
                "total_requests": self.metrics.total_requests
            },
            "optimization": {
                "level": self.optimization_level.value,
                "compression_enabled": self.enable_compression,
                "batch_operations": self.metrics.batch_operations,
                "concurrent_operations": self.metrics.concurrent_operations
            }
        }
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self.cache.clear()
        logger.info("Performance optimizer cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            "size": self.cache.size(),
            "max_size": self.cache.max_size,
            "strategy": self.cache.strategy.value,
            "default_ttl": self.cache.default_ttl
        }

# 全局性能优化器实例
_global_optimizer: Optional[PerformanceOptimizer] = None

def get_global_optimizer() -> PerformanceOptimizer:
    """获取全局性能优化器实例"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = PerformanceOptimizer()
    return _global_optimizer

def optimize_performance(
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None
):
    """性能优化装饰器"""
    optimizer = get_global_optimizer()
    return optimizer.cached(ttl=ttl, key_func=key_func)

def clear_performance_cache():
    """清空性能缓存"""
    optimizer = get_global_optimizer()
    optimizer.clear_cache()

def get_performance_stats() -> Dict[str, Any]:
    """获取性能统计"""
    optimizer = get_global_optimizer()
    return optimizer.get_performance_stats()