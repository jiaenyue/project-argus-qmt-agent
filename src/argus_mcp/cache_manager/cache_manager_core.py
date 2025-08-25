"""Cache Manager Core Module.

This module contains the main CacheManager class implementation.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Set, Union

from .cache_entry import CacheEntry
from .cache_policy import CachePolicy
from .cache_stats import CacheStats

logger = logging.getLogger(__name__)


class CacheManager:
    """Advanced cache manager with multiple eviction policies and performance monitoring."""
    
    def __init__(
        self,
        max_size: int = 10000,
        max_memory: int = 100 * 1024 * 1024,  # 100MB
        default_ttl: Optional[int] = 3600,
        policy: CachePolicy = CachePolicy.LRU,
        enable_performance_monitoring: bool = True
    ):
        """Initialize cache manager."""
        self.max_size = max_size
        self.max_memory = max_memory
        self.default_ttl = default_ttl
        self.policy = policy
        
        self._cache: Dict[str, CacheEntry] = {}
        self._level_caches: Dict[str, Dict[str, CacheEntry]] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "expired": 0,
            "evictions": 0,
            "memory_usage": 0,
            "total_size": 0
        }
        
        # Performance monitoring
        self.enable_performance_monitoring = enable_performance_monitoring
        self.performance_manager = None
        self.adaptive_strategy = None
        self._preloader = None
        
        # Start cleanup task
        self._cleanup_task = None
        
        logger.info(f"CacheManager initialized with policy={policy.value}, max_size={max_size}")
    
    async def start(self):
        """Start cache manager background tasks."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if self.enable_performance_monitoring and self.performance_manager:
            await self.performance_manager.start_performance_monitoring()
        
        logger.info("CacheManager started")
    
    async def stop(self):
        """Stop cache manager background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        if self.performance_manager:
            await self.performance_manager.stop_performance_monitoring()
        
        logger.info("CacheManager stopped")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return default
            
            if entry.is_expired():
                await self._remove_entry(key, entry)
                self._stats["misses"] += 1
                self._stats["expired"] += 1
                return default
            
            # Update access metadata
            entry.touch()
            self._stats["hits"] += 1
            
            # Check for pre-refresh
            if self._should_prerefresh(entry):
                self._mark_for_refresh(key, "prerefresh")
            
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        priority: int = 5
    ) -> bool:
        """Set value in cache."""
        async with self._lock:
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.default_ttl
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl,
                priority=priority
            )
            
            # Check capacity before adding
            await self._ensure_capacity(entry.size)
            
            # Add to cache
            self._cache[key] = entry
            self._update_memory_stats()
            
            logger.debug(f"Cached key={key}, size={entry.size}, ttl={ttl}")
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                await self._remove_entry(key, entry)
                self._update_memory_stats()
                logger.debug(f"Deleted key={key}")
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            for level_cache in self._level_caches.values():
                level_cache.clear()
            self._stats = {
                "hits": 0,
                "misses": 0,
                "expired": 0,
                "evictions": 0,
                "memory_usage": 0,
                "total_size": 0
            }
            logger.info("Cache cleared successfully")
    
    async def _ensure_capacity(self, new_entry_size: int):
        """Ensure cache has capacity for new entry."""
        # Check size limit
        while len(self._cache) >= self.max_size:
            await self._evict_entry()
        
        # Check memory limit
        current_memory = sum(entry.size for entry in self._cache.values())
        while current_memory + new_entry_size > self.max_memory:
            await self._evict_entry()
            current_memory = sum(entry.size for entry in self._cache.values())
    
    async def _evict_entry(self):
        """Evict an entry based on the cache policy."""
        if not self._cache:
            return
        
        if self.policy == CachePolicy.LRU:
            # Evict least recently used
            oldest_key = min(self._cache.keys(), 
                           key=lambda k: self._cache[k].last_accessed)
        elif self.policy == CachePolicy.LFU:
            # Evict least frequently used
            oldest_key = min(self._cache.keys(),
                           key=lambda k: self._cache[k].access_count)
        else:  # TTL
            # Evict entry with shortest remaining TTL
            oldest_key = min(self._cache.keys(),
                           key=lambda k: self._cache[k].created_at + (self._cache[k].ttl or 0))
        
        entry = self._cache[oldest_key]
        await self._remove_entry(oldest_key, entry)
        self._stats["evictions"] += 1
        
        logger.debug(f"Evicted key={oldest_key} using policy={self.policy.value}")
    
    async def _cleanup_expired(self):
        """Clean up expired cache entries."""
        expired_keys = []
        
        for key, entry in list(self._cache.items()):
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            entry = self._cache[key]
            await self._remove_entry(key, entry)
            self._stats["expired"] += 1
        
        if expired_keys:
            self._stats["total_size"] = len(self._cache)
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def _cleanup_loop(self):
        """Background task for periodic cleanup."""
        cleanup_interval = 60  # seconds
        while True:
            try:
                await asyncio.sleep(cleanup_interval)
                async with self._lock:
                    await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
    
    def _update_memory_stats(self):
        """Update memory usage statistics."""
        self._stats["memory_usage"] = sum(entry.size for entry in self._cache.values())
        self._stats["total_size"] = len(self._cache)
    
    def _should_prerefresh(self, entry: CacheEntry) -> bool:
        """Check if entry should be pre-refreshed."""
        if entry.ttl is None:
            return False
        
        time_remaining = entry.ttl - (time.time() - entry.created_at)
        refresh_threshold = entry.ttl * 0.1  # Refresh when 10% TTL remaining
        
        return time_remaining <= refresh_threshold
    
    def _mark_for_refresh(self, key: str, data_type: str):
        """Mark entry for background refresh."""
        logger.debug(f"Marked {key} for refresh (type: {data_type})")
    
    async def _remove_entry(self, key: str, entry: CacheEntry):
        """Remove entry from cache and level caches."""
        if key in self._cache:
            del self._cache[key]
        await self._remove_from_level_cache(key, entry)
    
    async def _remove_from_level_cache(self, key: str, entry: CacheEntry):
        """Remove entry from level caches."""
        for level_cache in self._level_caches.values():
            if key in level_cache:
                del level_cache[key]
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests) if total_requests > 0 else 0.0
        
        return CacheStats(
            hits=self._stats["hits"],
            misses=self._stats["misses"],
            expired=self._stats.get("expired", 0),
            evictions=self._stats.get("evictions", 0),
            memory_usage=self._stats["memory_usage"],
            entry_count=len(self._cache),
            hit_rate=hit_rate
        )
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information."""
        entries_info = []
        
        for key, entry in list(self._cache.items()):
            entries_info.append({
                "key": key,
                "size": entry.size,
                "created_at": entry.created_at,
                "last_accessed": entry.last_accessed,
                "access_count": entry.access_count,
                "ttl": entry.ttl,
                "expired": entry.is_expired()
            })
        
        return {
            "policy": self.policy.value,
            "max_size": self.max_size,
            "max_memory": self.max_memory,
            "default_ttl": self.default_ttl,
            "entries": entries_info
        }
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return True
            elif entry and entry.is_expired():
                del self._cache[key]
                self._update_memory_stats()
            return False
    
    async def keys(self) -> Set[str]:
        """Get all cache keys."""
        async with self._lock:
            return set(self._cache.keys())
    
    async def size(self) -> int:
        """Get number of cache entries."""
        return len(self._cache)
    
    def create_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments."""
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items()) if kwargs else {}
        }
        
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    # Performance and optimization methods
    def set_preloader(self, preloader):
        """Set cache preloader instance."""
        self._preloader = preloader
        logger.info("Cache preloader has been set")
    
    def get_performance_manager(self):
        """Get cache performance manager."""
        return self.performance_manager
    
    async def start_performance_monitoring(self):
        """Start comprehensive performance monitoring."""
        if self.performance_manager:
            await self.performance_manager.start_performance_monitoring()
    
    async def stop_performance_monitoring(self):
        """Stop performance monitoring."""
        if self.performance_manager:
            await self.performance_manager.stop_performance_monitoring()
    
    async def generate_performance_report(self):
        """Generate comprehensive performance report."""
        if self.performance_manager:
            return await self.performance_manager.generate_comprehensive_report()
        return {}
    
    async def optimize_cache_performance(self):
        """Perform cache optimization."""
        if self.performance_manager:
            return await self.performance_manager.optimize_cache_performance()
        return {}
    
    def get_performance_status(self):
        """Get current performance status."""
        if self.performance_manager:
            return self.performance_manager.get_current_status()
        return {}
    
    # Adaptive strategy methods
    async def start_adaptive_optimization(self):
        """启动自适应优化"""
        if self.adaptive_strategy:
            await self.adaptive_strategy.start_monitoring(self)
            logger.info("Started adaptive cache optimization")
    
    async def stop_adaptive_optimization(self):
        """停止自适应优化"""
        if self.adaptive_strategy:
            await self.adaptive_strategy.stop_monitoring()
            logger.info("Stopped adaptive cache optimization")
    
    def get_adaptive_status(self) -> Dict[str, Any]:
        """获取自适应优化状态"""
        if self.adaptive_strategy:
            return self.adaptive_strategy.get_adaptation_status()
        return {}
    
    def optimize_structure(self):
        """优化缓存结构（供自适应策略调用）"""
        try:
            # 重新组织缓存数据结构
            if hasattr(self, '_reorganize_cache'):
                self._reorganize_cache()
            
            # 清理过期数据
            asyncio.create_task(self._cleanup_expired())
            
            # 优化内存使用
            if hasattr(self, '_optimize_memory'):
                self._optimize_memory()
                
            logger.info("Cache structure optimization completed")
            
        except Exception as e:
            logger.error(f"Error optimizing cache structure: {e}")


class CacheDecorator:
    """Decorator for caching function results."""
    
    def __init__(self, cache_manager: CacheManager, ttl: Optional[int] = None):
        """Initialize cache decorator."""
        self.cache_manager = cache_manager
        self.ttl = ttl
    
    def __call__(self, func):
        """Decorate function with caching."""
        async def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = f"{func.__name__}_{self.cache_manager.create_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await self.cache_manager.set(cache_key, result, self.ttl)
            
            return result
        
        return wrapper