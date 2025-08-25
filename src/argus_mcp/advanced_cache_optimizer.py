"""
高级缓存优化器
实现智能缓存策略、自适应TTL和缓存预热
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import redis
import hashlib
from enum import Enum

logger = logging.getLogger(__name__)

class CacheStrategy(Enum):
    """缓存策略枚举"""
    LRU = "lru"
    LFU = "lfu"
    ADAPTIVE = "adaptive"
    PREDICTIVE = "predictive"

class DataType(Enum):
    """数据类型枚举"""
    MARKET_DATA = "market_data"
    INSTRUMENT_DETAIL = "instrument_detail"
    TRADING_DATES = "trading_dates"
    HISTORICAL_DATA = "historical_data"

@dataclass
class CacheMetrics:
    """缓存指标"""
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    total_requests: int = 0
    avg_response_time: float = 0.0
    cache_size: int = 0
    memory_usage: int = 0
    
    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.hit_count / self.total_requests
    
    @property
    def miss_rate(self) -> float:
        """缓存未命中率"""
        return 1.0 - self.hit_rate

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl: int
    data_type: DataType
    size: int
    
    @property
    def age(self) -> float:
        """缓存条目年龄（秒）"""
        return time.time() - self.created_at
    
    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        return time.time() - self.created_at > self.ttl

class AdaptiveTTLCalculator:
    """自适应TTL计算器"""
    
    def __init__(self):
        self.access_patterns = defaultdict(list)
        self.volatility_scores = defaultdict(float)
        self.base_ttls = {
            DataType.MARKET_DATA: 30,  # 30秒
            DataType.INSTRUMENT_DETAIL: 3600,  # 1小时
            DataType.TRADING_DATES: 86400,  # 24小时
            DataType.HISTORICAL_DATA: 1800,  # 30分钟
        }
    
    def calculate_ttl(self, key: str, data_type: DataType, 
                     access_frequency: float = 0.0,
                     data_volatility: float = 0.0) -> int:
        """计算自适应TTL"""
        base_ttl = self.base_ttls[data_type]
        
        # 根据访问频率调整
        frequency_factor = min(2.0, 1.0 + access_frequency / 10.0)
        
        # 根据数据波动性调整
        volatility_factor = max(0.1, 1.0 - data_volatility)
        
        # 根据时间段调整（交易时间vs非交易时间）
        time_factor = self._get_time_factor()
        
        adaptive_ttl = int(base_ttl * frequency_factor * volatility_factor * time_factor)
        
        # 确保TTL在合理范围内
        min_ttl = base_ttl // 4
        max_ttl = base_ttl * 4
        
        return max(min_ttl, min(max_ttl, adaptive_ttl))
    
    def _get_time_factor(self) -> float:
        """获取时间因子"""
        now = datetime.now()
        hour = now.hour
        
        # 交易时间（9:30-15:00）缓存时间较短
        if 9 <= hour <= 15:
            return 0.5
        # 非交易时间缓存时间较长
        else:
            return 1.5

class PredictiveCacheManager:
    """预测性缓存管理器"""
    
    def __init__(self):
        self.access_history = defaultdict(deque)
        self.prediction_models = {}
        self.preload_queue = asyncio.Queue()
    
    def record_access(self, key: str, timestamp: float = None):
        """记录访问历史"""
        if timestamp is None:
            timestamp = time.time()
        
        self.access_history[key].append(timestamp)
        
        # 保持最近1000次访问记录
        if len(self.access_history[key]) > 1000:
            self.access_history[key].popleft()
    
    def predict_next_access(self, key: str) -> Optional[float]:
        """预测下次访问时间"""
        history = self.access_history[key]
        if len(history) < 3:
            return None
        
        # 简单的线性预测
        recent_accesses = list(history)[-10:]
        intervals = [recent_accesses[i] - recent_accesses[i-1] 
                    for i in range(1, len(recent_accesses))]
        
        if not intervals:
            return None
        
        avg_interval = sum(intervals) / len(intervals)
        return recent_accesses[-1] + avg_interval
    
    def get_preload_candidates(self) -> List[str]:
        """获取预加载候选项"""
        candidates = []
        current_time = time.time()
        
        for key, history in self.access_history.items():
            if len(history) < 3:
                continue
            
            predicted_time = self.predict_next_access(key)
            if predicted_time and predicted_time - current_time < 300:  # 5分钟内
                candidates.append(key)
        
        return candidates

class AdvancedCacheOptimizer:
    """高级缓存优化器"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.metrics = CacheMetrics()
        self.ttl_calculator = AdaptiveTTLCalculator()
        self.predictive_manager = PredictiveCacheManager()
        self.cache_entries = {}
        self.strategy = CacheStrategy.ADAPTIVE
        
        # 配置参数
        self.max_memory_usage = 512 * 1024 * 1024  # 512MB
        self.cleanup_interval = 300  # 5分钟
        self.preload_interval = 60  # 1分钟
        
        # 启动后台任务
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """启动后台任务"""
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._preload_loop())
        asyncio.create_task(self._metrics_update_loop())
    
    async def get(self, key: str, data_type: DataType = DataType.MARKET_DATA) -> Optional[Any]:
        """获取缓存数据"""
        start_time = time.time()
        
        try:
            # 记录访问
            self.predictive_manager.record_access(key)
            self.metrics.total_requests += 1
            
            # 从Redis获取
            cached_data = await self._redis_get(key)
            
            if cached_data is not None:
                self.metrics.hit_count += 1
                
                # 更新访问信息
                if key in self.cache_entries:
                    entry = self.cache_entries[key]
                    entry.last_accessed = time.time()
                    entry.access_count += 1
                
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(cached_data)
            else:
                self.metrics.miss_count += 1
                logger.debug(f"Cache miss for key: {key}")
                return None
                
        finally:
            # 更新响应时间
            response_time = time.time() - start_time
            self._update_avg_response_time(response_time)
    
    async def set(self, key: str, value: Any, data_type: DataType = DataType.MARKET_DATA,
                  custom_ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        try:
            # 计算TTL
            if custom_ttl is not None:
                ttl = custom_ttl
            else:
                access_freq = self._get_access_frequency(key)
                volatility = self._estimate_data_volatility(key, data_type)
                ttl = self.ttl_calculator.calculate_ttl(key, data_type, access_freq, volatility)
            
            # 序列化数据
            serialized_value = json.dumps(value, default=str)
            data_size = len(serialized_value.encode('utf-8'))
            
            # 检查内存使用
            if await self._check_memory_usage(data_size):
                await self._evict_entries()
            
            # 存储到Redis
            success = await self._redis_set(key, serialized_value, ttl)
            
            if success:
                # 更新缓存条目信息
                self.cache_entries[key] = CacheEntry(
                    key=key,
                    value=value,
                    created_at=time.time(),
                    last_accessed=time.time(),
                    access_count=1,
                    ttl=ttl,
                    data_type=data_type,
                    size=data_size
                )
                
                logger.debug(f"Cache set for key: {key}, TTL: {ttl}s")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error setting cache for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        try:
            success = await self._redis_delete(key)
            if success and key in self.cache_entries:
                del self.cache_entries[key]
            return success
        except Exception as e:
            logger.error(f"Error deleting cache for key {key}: {e}")
            return False
    
    async def clear_by_pattern(self, pattern: str) -> int:
        """按模式清除缓存"""
        try:
            keys = await self._redis_keys(pattern)
            if keys:
                deleted_count = await self._redis_delete_multiple(keys)
                
                # 更新本地缓存条目
                for key in keys:
                    if key in self.cache_entries:
                        del self.cache_entries[key]
                
                return deleted_count
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache by pattern {pattern}: {e}")
            return 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取缓存指标"""
        return {
            "metrics": asdict(self.metrics),
            "cache_entries_count": len(self.cache_entries),
            "strategy": self.strategy.value,
            "memory_usage_mb": self.metrics.memory_usage / (1024 * 1024),
            "top_accessed_keys": self._get_top_accessed_keys(10)
        }
    
    async def optimize_cache(self) -> Dict[str, Any]:
        """优化缓存"""
        optimization_results = {
            "cleaned_entries": 0,
            "preloaded_entries": 0,
            "memory_freed_mb": 0,
            "recommendations": []
        }
        
        # 清理过期条目
        cleaned = await self._cleanup_expired_entries()
        optimization_results["cleaned_entries"] = cleaned
        
        # 预加载热点数据
        preloaded = await self._preload_hot_data()
        optimization_results["preloaded_entries"] = preloaded
        
        # 内存优化
        freed_memory = await self._optimize_memory_usage()
        optimization_results["memory_freed_mb"] = freed_memory / (1024 * 1024)
        
        # 生成优化建议
        recommendations = self._generate_optimization_recommendations()
        optimization_results["recommendations"] = recommendations
        
        return optimization_results
    
    # 私有方法
    async def _redis_get(self, key: str) -> Optional[str]:
        """Redis GET操作"""
        try:
            return await asyncio.to_thread(self.redis_client.get, key)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    async def _redis_set(self, key: str, value: str, ttl: int) -> bool:
        """Redis SET操作"""
        try:
            return await asyncio.to_thread(self.redis_client.setex, key, ttl, value)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def _redis_delete(self, key: str) -> bool:
        """Redis DELETE操作"""
        try:
            result = await asyncio.to_thread(self.redis_client.delete, key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    async def _redis_keys(self, pattern: str) -> List[str]:
        """Redis KEYS操作"""
        try:
            keys = await asyncio.to_thread(self.redis_client.keys, pattern)
            return [key.decode('utf-8') if isinstance(key, bytes) else key for key in keys]
        except Exception as e:
            logger.error(f"Redis KEYS error for pattern {pattern}: {e}")
            return []
    
    async def _redis_delete_multiple(self, keys: List[str]) -> int:
        """Redis批量删除"""
        try:
            if keys:
                return await asyncio.to_thread(self.redis_client.delete, *keys)
            return 0
        except Exception as e:
            logger.error(f"Redis batch DELETE error: {e}")
            return 0
    
    def _get_access_frequency(self, key: str) -> float:
        """获取访问频率"""
        if key not in self.cache_entries:
            return 0.0
        
        entry = self.cache_entries[key]
        age_hours = entry.age / 3600
        
        if age_hours == 0:
            return 0.0
        
        return entry.access_count / age_hours
    
    def _estimate_data_volatility(self, key: str, data_type: DataType) -> float:
        """估算数据波动性"""
        # 简化的波动性估算
        volatility_map = {
            DataType.MARKET_DATA: 0.8,  # 高波动性
            DataType.INSTRUMENT_DETAIL: 0.1,  # 低波动性
            DataType.TRADING_DATES: 0.0,  # 无波动性
            DataType.HISTORICAL_DATA: 0.3,  # 中等波动性
        }
        
        return volatility_map.get(data_type, 0.5)
    
    async def _check_memory_usage(self, additional_size: int) -> bool:
        """检查内存使用情况"""
        current_usage = sum(entry.size for entry in self.cache_entries.values())
        return current_usage + additional_size > self.max_memory_usage
    
    async def _evict_entries(self):
        """驱逐缓存条目"""
        if self.strategy == CacheStrategy.LRU:
            await self._evict_lru()
        elif self.strategy == CacheStrategy.LFU:
            await self._evict_lfu()
        else:
            await self._evict_adaptive()
    
    async def _evict_lru(self):
        """LRU驱逐策略"""
        if not self.cache_entries:
            return
        
        # 按最后访问时间排序
        sorted_entries = sorted(
            self.cache_entries.values(),
            key=lambda x: x.last_accessed
        )
        
        # 驱逐最旧的条目
        for entry in sorted_entries[:len(sorted_entries)//4]:  # 驱逐25%
            await self.delete(entry.key)
            self.metrics.eviction_count += 1
    
    async def _evict_lfu(self):
        """LFU驱逐策略"""
        if not self.cache_entries:
            return
        
        # 按访问次数排序
        sorted_entries = sorted(
            self.cache_entries.values(),
            key=lambda x: x.access_count
        )
        
        # 驱逐访问次数最少的条目
        for entry in sorted_entries[:len(sorted_entries)//4]:  # 驱逐25%
            await self.delete(entry.key)
            self.metrics.eviction_count += 1
    
    async def _evict_adaptive(self):
        """自适应驱逐策略"""
        if not self.cache_entries:
            return
        
        # 综合考虑访问频率、年龄和大小
        scored_entries = []
        for entry in self.cache_entries.values():
            frequency_score = entry.access_count / max(1, entry.age / 3600)
            age_score = 1.0 / (1.0 + entry.age / 3600)
            size_score = 1.0 / (1.0 + entry.size / 1024)
            
            total_score = frequency_score * 0.5 + age_score * 0.3 + size_score * 0.2
            scored_entries.append((entry, total_score))
        
        # 按分数排序，驱逐分数最低的条目
        scored_entries.sort(key=lambda x: x[1])
        
        for entry, _ in scored_entries[:len(scored_entries)//4]:  # 驱逐25%
            await self.delete(entry.key)
            self.metrics.eviction_count += 1
    
    def _update_avg_response_time(self, response_time: float):
        """更新平均响应时间"""
        if self.metrics.total_requests == 1:
            self.metrics.avg_response_time = response_time
        else:
            # 指数移动平均
            alpha = 0.1
            self.metrics.avg_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.metrics.avg_response_time
            )
    
    def _get_top_accessed_keys(self, limit: int) -> List[Dict[str, Any]]:
        """获取访问次数最多的键"""
        sorted_entries = sorted(
            self.cache_entries.values(),
            key=lambda x: x.access_count,
            reverse=True
        )
        
        return [
            {
                "key": entry.key,
                "access_count": entry.access_count,
                "age_hours": entry.age / 3600,
                "size_kb": entry.size / 1024
            }
            for entry in sorted_entries[:limit]
        ]
    
    async def _cleanup_expired_entries(self) -> int:
        """清理过期条目"""
        expired_keys = [
            key for key, entry in self.cache_entries.items()
            if entry.is_expired
        ]
        
        for key in expired_keys:
            await self.delete(key)
        
        return len(expired_keys)
    
    async def _preload_hot_data(self) -> int:
        """预加载热点数据"""
        candidates = self.predictive_manager.get_preload_candidates()
        preloaded_count = 0
        
        for key in candidates[:10]:  # 限制预加载数量
            if key not in self.cache_entries:
                # 这里需要实际的数据获取逻辑
                # 暂时跳过
                pass
        
        return preloaded_count
    
    async def _optimize_memory_usage(self) -> int:
        """优化内存使用"""
        current_usage = sum(entry.size for entry in self.cache_entries.values())
        
        if current_usage > self.max_memory_usage * 0.8:  # 80%阈值
            await self._evict_entries()
            new_usage = sum(entry.size for entry in self.cache_entries.values())
            return current_usage - new_usage
        
        return 0
    
    def _generate_optimization_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 命中率建议
        if self.metrics.hit_rate < 0.7:
            recommendations.append("缓存命中率较低，建议增加缓存时间或预加载热点数据")
        
        # 内存使用建议
        memory_usage_ratio = self.metrics.memory_usage / self.max_memory_usage
        if memory_usage_ratio > 0.9:
            recommendations.append("内存使用率过高，建议增加内存限制或优化驱逐策略")
        
        # 响应时间建议
        if self.metrics.avg_response_time > 0.1:  # 100ms
            recommendations.append("缓存响应时间较慢，建议检查Redis连接或优化序列化")
        
        return recommendations
    
    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_entries()
                logger.debug("Cache cleanup completed")
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _preload_loop(self):
        """预加载循环"""
        while True:
            try:
                await asyncio.sleep(self.preload_interval)
                await self._preload_hot_data()
                logger.debug("Cache preload completed")
            except Exception as e:
                logger.error(f"Error in preload loop: {e}")
    
    async def _metrics_update_loop(self):
        """指标更新循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟更新一次
                
                # 更新缓存大小和内存使用
                self.metrics.cache_size = len(self.cache_entries)
                self.metrics.memory_usage = sum(
                    entry.size for entry in self.cache_entries.values()
                )
                
                logger.debug(f"Cache metrics updated: {self.get_metrics()}")
            except Exception as e:
                logger.error(f"Error in metrics update loop: {e}")

# 全局实例
_cache_optimizer: Optional[AdvancedCacheOptimizer] = None

def get_cache_optimizer() -> AdvancedCacheOptimizer:
    """获取缓存优化器实例"""
    global _cache_optimizer
    if _cache_optimizer is None:
        import redis
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        _cache_optimizer = AdvancedCacheOptimizer(redis_client)
    return _cache_optimizer

async def init_cache_optimizer(redis_client: redis.Redis = None) -> AdvancedCacheOptimizer:
    """初始化缓存优化器"""
    global _cache_optimizer
    if redis_client is None:
        import redis
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    _cache_optimizer = AdvancedCacheOptimizer(redis_client)
    return _cache_optimizer