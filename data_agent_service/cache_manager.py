"""Windows兼容缓存管理模块

提供统一的缓存接口，支持市场数据缓存、配置缓存等功能。
使用内存缓存实现，完全兼容Windows环境。"""

import json
import asyncio
import logging
import time
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from cachetools import TTLCache, LRUCache
import hashlib
import threading
from collections import defaultdict

# 配置日志
logger = logging.getLogger(__name__)

class CacheConfig:
    """缓存配置类"""
    
    def __init__(self):
        # 缓存策略配置
        self.default_ttl = 300  # 5分钟默认过期时间
        self.market_data_ttl = 60  # 市场数据1分钟过期
        self.instrument_detail_ttl = 3600  # 合约详情1小时过期
        self.kline_data_ttl = 300  # K线数据5分钟过期
        
        # 内存缓存配置
        self.cache_size = 10000  # 缓存条目数量
        self.max_memory_mb = 512  # 最大内存使用量(MB)
        
        # 性能配置
        self.enable_stats = True  # 启用统计信息
        self.cleanup_interval = 60  # 清理间隔(秒)
        self.batch_size = 100  # 批量操作大小
        
        # Windows性能计数器配置
        self.enable_perf_counters = True

class CacheStats:
    """缓存统计信息"""
    
    def __init__(self):
        self.hits = defaultdict(int)
        self.misses = defaultdict(int)
        self.operations = defaultdict(list)
        self.start_time = time.time()
        self._lock = threading.Lock()
    
    def record_hit(self, cache_type: str):
        with self._lock:
            self.hits[cache_type] += 1
    
    def record_miss(self, cache_type: str):
        with self._lock:
            self.misses[cache_type] += 1
    
    def record_operation(self, operation: str, cache_type: str, duration: float):
        with self._lock:
            self.operations[f"{operation}_{cache_type}"].append(duration)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_hits = sum(self.hits.values())
            total_misses = sum(self.misses.values())
            hit_rate = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0
            
            return {
                "uptime_seconds": time.time() - self.start_time,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "hit_rate": hit_rate,
                "hits_by_type": dict(self.hits),
                "misses_by_type": dict(self.misses),
                "avg_operation_times": {
                    op: sum(times) / len(times) if times else 0
                    for op, times in self.operations.items()
                }
            }

class CacheManager:
    """Windows兼容缓存管理器
    
    提供统一的缓存接口，使用内存缓存实现。
    支持TTL过期、统计信息、批量操作等功能。
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        
        # 创建多个缓存实例用于不同类型的数据
        self.caches = {
            "default": TTLCache(maxsize=self.config.cache_size, ttl=self.config.default_ttl),
            "market_data": TTLCache(maxsize=self.config.cache_size, ttl=self.config.market_data_ttl),
            "instrument": TTLCache(maxsize=self.config.cache_size, ttl=self.config.instrument_detail_ttl),
            "kline": TTLCache(maxsize=self.config.cache_size, ttl=self.config.kline_data_ttl)
        }
        
        # 统计信息
        self.stats = CacheStats() if self.config.enable_stats else None
        
        # 线程锁
        self._locks = {cache_type: threading.RLock() for cache_type in self.caches.keys()}
        
        # 启动清理任务
        self._cleanup_task = None
        self._running = False
        
    async def start(self):
        """启动缓存管理器"""
        self._running = True
        if self.config.cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("缓存管理器已启动")
    
    async def stop(self):
        """停止缓存管理器"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("缓存管理器已停止")
    
    async def _cleanup_loop(self):
        """定期清理过期缓存"""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"缓存清理任务错误: {str(e)}")
    
    def _cleanup_expired(self):
        """清理过期缓存项"""
        for cache_type, cache in self.caches.items():
            with self._locks[cache_type]:
                # TTLCache会自动清理过期项，这里只是触发清理
                cache.expire()
                logger.debug(f"清理缓存类型 {cache_type}，当前大小: {len(cache)}")
    
    def _generate_key(self, prefix: str, identifier: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [prefix, identifier]
        
        # 添加额外参数到键中
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_suffix = "_".join([f"{k}:{v}" for k, v in sorted_kwargs])
            key_parts.append(key_suffix)
        
        key = ":".join(key_parts)
        
        # 如果键太长，使用哈希
        if len(key) > 200:
            hash_obj = hashlib.md5(key.encode())
            key = f"{prefix}:hash:{hash_obj.hexdigest()}"
        
        return key
    
    def _serialize_data(self, data: Any) -> str:
        """序列化数据"""
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"数据序列化失败: {str(e)}")
            raise
    
    def _deserialize_data(self, data: str) -> Any:
        """反序列化数据"""
        try:
            return json.loads(data)
        except Exception as e:
            logger.error(f"数据反序列化失败: {str(e)}")
            raise
    
    async def get(self, key: str, cache_type: str = "default") -> Optional[Any]:
        """获取缓存数据"""
        start_time = time.time()
        
        try:
            cache = self.caches.get(cache_type, self.caches["default"])
            
            with self._locks[cache_type if cache_type in self._locks else "default"]:
                if key in cache:
                    if self.stats:
                        self.stats.record_hit(cache_type)
                    logger.debug(f"缓存命中: {key} (类型: {cache_type})")
                    return cache[key]
                
                if self.stats:
                    self.stats.record_miss(cache_type)
                logger.debug(f"缓存未命中: {key} (类型: {cache_type})")
                return None
        
        finally:
            if self.stats:
                duration = time.time() - start_time
                self.stats.record_operation("get", cache_type, duration)
    
    async def set(self, key: str, value: Any, ttl: int = None, cache_type: str = "default") -> bool:
        """设置缓存数据"""
        start_time = time.time()
        
        try:
            cache = self.caches.get(cache_type, self.caches["default"])
            
            with self._locks[cache_type if cache_type in self._locks else "default"]:
                # 如果指定了TTL，创建临时TTLCache
                if ttl and ttl != cache.ttl:
                    # 对于不同TTL的情况，直接存储到默认缓存中
                    # 这是一个简化实现，实际项目中可能需要更复杂的TTL管理
                    cache[key] = value
                else:
                    cache[key] = value
                
                logger.debug(f"缓存设置成功: {key} (类型: {cache_type})")
                return True
                
        except Exception as e:
            logger.error(f"缓存设置失败: {key}, 错误: {str(e)}")
            return False
        
        finally:
            if self.stats:
                duration = time.time() - start_time
                self.stats.record_operation("set", cache_type, duration)
    
    async def delete(self, key: str, cache_type: str = "default") -> bool:
        """删除缓存数据"""
        start_time = time.time()
        
        try:
            cache = self.caches.get(cache_type, self.caches["default"])
            
            with self._locks[cache_type if cache_type in self._locks else "default"]:
                if key in cache:
                    del cache[key]
                    logger.debug(f"缓存删除成功: {key} (类型: {cache_type})")
                    return True
                else:
                    logger.debug(f"缓存键不存在: {key} (类型: {cache_type})")
                    return False
                
        except Exception as e:
            logger.error(f"缓存删除失败: {key}, 错误: {str(e)}")
            return False
        
        finally:
            if self.stats:
                duration = time.time() - start_time
                self.stats.record_operation("delete", cache_type, duration)
    
    async def exists(self, key: str, cache_type: str = "default") -> bool:
        """检查缓存是否存在"""
        try:
            cache = self.caches.get(cache_type, self.caches["default"])
            
            with self._locks[cache_type if cache_type in self._locks else "default"]:
                return key in cache
                
        except Exception as e:
            logger.error(f"检查缓存存在性失败: {key}, 错误: {str(e)}")
            return False
    
    async def clear_pattern(self, pattern: str, cache_type: str = "default") -> int:
        """清除匹配模式的缓存"""
        try:
            cache = self.caches.get(cache_type, self.caches["default"])
            deleted_count = 0
            
            with self._locks[cache_type if cache_type in self._locks else "default"]:
                # 简单的模式匹配实现
                keys_to_delete = []
                for key in list(cache.keys()):
                    if self._match_pattern(key, pattern):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    if key in cache:
                        del cache[key]
                        deleted_count += 1
                
                logger.info(f"清除缓存模式 {pattern}: {deleted_count} 个键 (类型: {cache_type})")
                return deleted_count
            
        except Exception as e:
            logger.error(f"清除缓存模式失败: {pattern}, 错误: {str(e)}")
            return 0
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """简单的模式匹配实现"""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
    
    async def clear_all(self, cache_type: str = None) -> int:
        """清除所有缓存或指定类型的缓存"""
        total_deleted = 0
        
        try:
            if cache_type:
                cache = self.caches.get(cache_type)
                if cache:
                    with self._locks[cache_type]:
                        count = len(cache)
                        cache.clear()
                        total_deleted = count
                        logger.info(f"清除所有缓存 (类型: {cache_type}): {count} 个键")
            else:
                for ct, cache in self.caches.items():
                    with self._locks[ct]:
                        count = len(cache)
                        cache.clear()
                        total_deleted += count
                        logger.info(f"清除所有缓存 (类型: {ct}): {count} 个键")
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"清除缓存失败, 错误: {str(e)}")
            return 0
    
    def get_cache_info(self, cache_type: str = None) -> Dict[str, Any]:
        """获取缓存信息"""
        try:
            if cache_type:
                cache = self.caches.get(cache_type)
                if cache:
                    with self._locks[cache_type]:
                        return {
                            "type": cache_type,
                            "size": len(cache),
                            "maxsize": cache.maxsize,
                            "ttl": cache.ttl,
                            "currsize": cache.currsize if hasattr(cache, 'currsize') else len(cache)
                        }
                return {}
            else:
                info = {}
                for ct, cache in self.caches.items():
                    with self._locks[ct]:
                        info[ct] = {
                            "size": len(cache),
                            "maxsize": cache.maxsize,
                            "ttl": cache.ttl,
                            "currsize": cache.currsize if hasattr(cache, 'currsize') else len(cache)
                        }
                
                # 添加统计信息
                if self.stats:
                    info["stats"] = self.stats.get_stats()
                
                return info
                
        except Exception as e:
            logger.error(f"获取缓存信息失败, 错误: {str(e)}")
            return {}
    
    # 市场数据专用缓存方法
    async def cache_market_data(self, symbol: str, data_type: str, data: Any, **kwargs) -> bool:
        """缓存市场数据"""
        key = self._generate_key("market", f"{symbol}:{data_type}", **kwargs)
        return await self.set(key, data, ttl=self.config.market_data_ttl, cache_type="market_data")
    
    async def get_market_data(self, symbol: str, data_type: str, **kwargs) -> Optional[Any]:
        """获取市场数据缓存"""
        key = self._generate_key("market", f"{symbol}:{data_type}", **kwargs)
        return await self.get(key, cache_type="market_data")
    
    async def cache_instrument_detail(self, symbol: str, detail: Dict) -> bool:
        """缓存合约详情"""
        key = self._generate_key("instrument", symbol)
        return await self.set(key, detail, ttl=self.config.instrument_detail_ttl, cache_type="instrument")
    
    async def get_instrument_detail(self, symbol: str) -> Optional[Dict]:
        """获取合约详情缓存"""
        key = self._generate_key("instrument", symbol)
        return await self.get(key, cache_type="instrument")
    
    async def cache_kline_data(self, symbol: str, period: str, data: List[Dict], **kwargs) -> bool:
        """缓存K线数据"""
        key = self._generate_key("kline", f"{symbol}:{period}", **kwargs)
        return await self.set(key, data, ttl=self.config.kline_data_ttl, cache_type="kline")
    
    async def get_kline_data(self, symbol: str, period: str, **kwargs) -> Optional[List[Dict]]:
        """获取K线数据缓存"""
        key = self._generate_key("kline", f"{symbol}:{period}", **kwargs)
        return await self.get(key, cache_type="kline")
    
    async def cache_tick_data(self, symbol: str, tick_data: Dict) -> bool:
        """缓存Tick数据"""
        key = self._generate_key("tick", symbol)
        return await self.set(key, tick_data, ttl=5, cache_type="market_data")  # Tick数据5秒过期
    
    async def get_tick_data(self, symbol: str) -> Optional[Dict]:
        """获取Tick数据缓存"""
        key = self._generate_key("tick", symbol)
        return await self.get(key, cache_type="market_data")
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if self.stats:
            return self.stats.get_stats()
        return {}
    
    async def clear_by_pattern(self, pattern: str) -> int:
        """按模式清理缓存"""
        total_cleared = 0
        for cache_type in self.caches.keys():
            cleared = await self.clear_pattern(pattern, cache_type)
            total_cleared += cleared
        return total_cleared
    
    async def optimize(self) -> Dict[str, Any]:
        """优化缓存"""
        try:
            # 清理过期项
            self._cleanup_expired()
            
            # 收集优化信息
            optimization_info = {
                'cleaned_expired': True,
                'cache_info': self.get_cache_info(),
                'timestamp': datetime.now().isoformat()
            }
            
            return optimization_info
        except Exception as e:
            logger.error(f"缓存优化失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    async def get_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return {
            'default_ttl': self.config.default_ttl,
            'market_data_ttl': self.config.market_data_ttl,
            'instrument_detail_ttl': self.config.instrument_detail_ttl,
            'kline_data_ttl': self.config.kline_data_ttl,
            'cache_size': self.config.cache_size,
            'max_memory_mb': self.config.max_memory_mb,
            'enable_stats': self.config.enable_stats,
            'cleanup_interval': self.config.cleanup_interval
        }
    
    async def update_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """更新缓存配置"""
        try:
            for key, value in config_dict.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            return await self.get_config()
        except Exception as e:
            logger.error(f"更新缓存配置失败: {e}")
            return {'error': str(e)}
    
    async def get_keys(self, pattern: str = None, limit: int = 100) -> List[str]:
        """获取缓存键列表"""
        keys = []
        for cache_type, cache in self.caches.items():
            with self._locks[cache_type]:
                cache_keys = list(cache.keys())
                if pattern:
                    cache_keys = [k for k in cache_keys if self._match_pattern(k, pattern)]
                keys.extend(cache_keys[:limit//len(self.caches)])
        
        return keys[:limit]


# 全局缓存管理器实例
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

async def init_cache_manager(config: CacheConfig = None) -> CacheManager:
    """初始化缓存管理器"""
    global _cache_manager
    _cache_manager = CacheManager(config)
    await _cache_manager.start()
    return _cache_manager

async def shutdown_cache_manager():
    """关闭缓存管理器"""
    global _cache_manager
    if _cache_manager:
        await _cache_manager.stop()
        _cache_manager = None