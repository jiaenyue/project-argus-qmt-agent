#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级缓存策略模块
实现多层缓存、预测性缓存和智能缓存失效机制
"""

import asyncio
import time
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import threading
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheLevel(Enum):
    """缓存级别"""
    L1_MEMORY = "l1_memory"  # 内存缓存
    L2_DISK = "l2_disk"      # 磁盘缓存
    L3_DISTRIBUTED = "l3_distributed"  # 分布式缓存

class CachePriority(Enum):
    """缓存优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class CacheItem:
    """缓存项"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: Optional[float] = None
    priority: CachePriority = CachePriority.MEDIUM
    size: int = 0
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def update_access(self):
        """更新访问信息"""
        self.last_accessed = time.time()
        self.access_count += 1

@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0
    
    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

class PredictiveCache:
    """预测性缓存"""
    
    def __init__(self, max_predictions: int = 100):
        self.max_predictions = max_predictions
        self.access_patterns: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.prediction_scores: Dict[str, float] = {}
        self.lock = threading.RLock()
    
    def record_access(self, key: str, timestamp: float = None):
        """记录访问模式"""
        if timestamp is None:
            timestamp = time.time()
        
        with self.lock:
            self.access_patterns[key].append(timestamp)
            self._update_prediction_score(key)
    
    def _update_prediction_score(self, key: str):
        """更新预测分数"""
        pattern = self.access_patterns[key]
        if len(pattern) < 2:
            return
        
        # 计算访问频率
        intervals = [pattern[i] - pattern[i-1] for i in range(1, len(pattern))]
        avg_interval = sum(intervals) / len(intervals)
        
        # 计算预测分数（访问频率越高，分数越高）
        score = 1.0 / (avg_interval + 1)
        self.prediction_scores[key] = score
    
    def get_predictions(self, limit: int = None) -> List[str]:
        """获取预测的热点数据"""
        if limit is None:
            limit = self.max_predictions
        
        with self.lock:
            sorted_keys = sorted(
                self.prediction_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return [key for key, score in sorted_keys[:limit]]

class SmartEvictionPolicy:
    """智能驱逐策略"""
    
    def __init__(self):
        self.weights = {
            'frequency': 0.3,
            'recency': 0.3,
            'priority': 0.2,
            'size': 0.2
        }
    
    def calculate_score(self, item: CacheItem) -> float:
        """计算驱逐分数（分数越低越容易被驱逐）"""
        now = time.time()
        
        # 频率分数（访问次数）
        frequency_score = min(item.access_count / 100.0, 1.0)
        
        # 新近度分数（最近访问时间）
        recency_score = max(0, 1.0 - (now - item.last_accessed) / 3600.0)
        
        # 优先级分数
        priority_score = item.priority.value / 4.0
        
        # 大小分数（大小越小分数越高）
        size_score = max(0, 1.0 - item.size / 1024.0 / 1024.0)  # 1MB为基准
        
        # 加权计算总分
        total_score = (
            frequency_score * self.weights['frequency'] +
            recency_score * self.weights['recency'] +
            priority_score * self.weights['priority'] +
            size_score * self.weights['size']
        )
        
        return total_score
    
    def select_victims(self, items: List[CacheItem], count: int) -> List[str]:
        """选择要驱逐的项目"""
        scored_items = [(item.key, self.calculate_score(item)) for item in items]
        scored_items.sort(key=lambda x: x[1])  # 分数从低到高排序
        return [key for key, score in scored_items[:count]]

class AdvancedCacheStrategy:
    """高级缓存策略"""
    
    def __init__(
        self,
        max_size: int = 10000,
        max_memory_mb: int = 512,
        default_ttl: float = 3600.0,
        enable_prediction: bool = True,
        enable_compression: bool = True
    ):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.enable_prediction = enable_prediction
        self.enable_compression = enable_compression
        
        # 多层缓存存储
        self.l1_cache: Dict[str, CacheItem] = {}  # 内存缓存
        self.l2_cache: Dict[str, str] = {}  # 磁盘缓存路径
        
        # 缓存管理组件
        self.predictive_cache = PredictiveCache() if enable_prediction else None
        self.eviction_policy = SmartEvictionPolicy()
        self.stats = CacheStats()
        
        # 线程安全
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cache")
        
        # 标签和依赖管理
        self.tag_index: Dict[str, List[str]] = defaultdict(list)
        self.dependency_graph: Dict[str, List[str]] = defaultdict(list)
        
        # 后台任务
        self._background_tasks_running = False
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """启动后台任务"""
        if self._background_tasks_running:
            return
        
        self._background_tasks_running = True
        
        # 定期清理过期项
        def cleanup_expired():
            while self._background_tasks_running:
                try:
                    self._cleanup_expired_items()
                    time.sleep(60)  # 每分钟清理一次
                except Exception as e:
                    logger.error(f"清理过期项时发生错误: {e}")
        
        # 预热缓存
        def warmup_cache():
            while self._background_tasks_running:
                try:
                    if self.predictive_cache:
                        self._warmup_predicted_items()
                    time.sleep(300)  # 每5分钟预热一次
                except Exception as e:
                    logger.error(f"预热缓存时发生错误: {e}")
        
        self.executor.submit(cleanup_expired)
        self.executor.submit(warmup_cache)
    
    def _cleanup_expired_items(self):
        """清理过期项"""
        with self.lock:
            expired_keys = [
                key for key, item in self.l1_cache.items()
                if item.is_expired()
            ]
            
            for key in expired_keys:
                self._remove_item(key)
                self.stats.evictions += 1
    
    def _warmup_predicted_items(self):
        """预热预测的热点数据"""
        if not self.predictive_cache:
            return
        
        predictions = self.predictive_cache.get_predictions(limit=50)
        # 这里可以实现预加载逻辑
        logger.debug(f"预测的热点数据: {predictions[:10]}")
    
    def _calculate_item_size(self, value: Any) -> int:
        """计算项目大小"""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (int, float)):
                return 8
            else:
                # 序列化后计算大小
                serialized = json.dumps(value, default=str)
                return len(serialized.encode('utf-8'))
        except Exception:
            return 1024  # 默认1KB
    
    def _remove_item(self, key: str):
        """移除缓存项"""
        if key in self.l1_cache:
            item = self.l1_cache[key]
            
            # 更新统计
            self.stats.size -= item.size
            
            # 清理标签索引
            for tag in item.tags:
                if key in self.tag_index[tag]:
                    self.tag_index[tag].remove(key)
            
            # 清理依赖关系
            for dep in item.dependencies:
                if key in self.dependency_graph[dep]:
                    self.dependency_graph[dep].remove(key)
            
            del self.l1_cache[key]
    
    def _ensure_capacity(self):
        """确保缓存容量"""
        # 检查数量限制
        if len(self.l1_cache) >= self.max_size:
            evict_count = max(1, int(self.max_size * 0.1))  # 驱逐10%
            items = list(self.l1_cache.values())
            victims = self.eviction_policy.select_victims(items, evict_count)
            
            for key in victims:
                self._remove_item(key)
                self.stats.evictions += 1
        
        # 检查内存限制
        if self.stats.size > self.max_memory_bytes:
            target_size = int(self.max_memory_bytes * 0.8)  # 减少到80%
            items = list(self.l1_cache.values())
            items.sort(key=lambda x: self.eviction_policy.calculate_score(x))
            
            current_size = self.stats.size
            for item in items:
                if current_size <= target_size:
                    break
                self._remove_item(item.key)
                current_size -= item.size
                self.stats.evictions += 1
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self.lock:
            # L1缓存查找
            if key in self.l1_cache:
                item = self.l1_cache[key]
                
                if item.is_expired():
                    self._remove_item(key)
                    self.stats.misses += 1
                    return None
                
                item.update_access()
                self.stats.hits += 1
                
                # 记录访问模式
                if self.predictive_cache:
                    self.predictive_cache.record_access(key)
                
                return item.value
            
            # L2缓存查找（磁盘缓存）
            # TODO: 实现磁盘缓存逻辑
            
            self.stats.misses += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        priority: CachePriority = CachePriority.MEDIUM,
        tags: List[str] = None,
        dependencies: List[str] = None
    ) -> bool:
        """设置缓存项"""
        if tags is None:
            tags = []
        if dependencies is None:
            dependencies = []
        
        with self.lock:
            # 确保容量
            self._ensure_capacity()
            
            # 计算大小
            size = self._calculate_item_size(value)
            
            # 创建缓存项
            now = time.time()
            item = CacheItem(
                key=key,
                value=value,
                created_at=now,
                last_accessed=now,
                ttl=ttl,
                priority=priority,
                size=size,
                tags=tags,
                dependencies=dependencies
            )
            
            # 如果已存在，先移除旧项
            if key in self.l1_cache:
                self._remove_item(key)
            
            # 添加新项
            self.l1_cache[key] = item
            self.stats.size += size
            
            # 更新标签索引
            for tag in tags:
                self.tag_index[tag].append(key)
            
            # 更新依赖关系
            for dep in dependencies:
                self.dependency_graph[dep].append(key)
            
            return True
    
    async def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.l1_cache:
                self._remove_item(key)
                return True
            return False
    
    async def clear_by_tag(self, tag: str) -> int:
        """按标签清除缓存"""
        with self.lock:
            keys_to_remove = self.tag_index.get(tag, [])
            count = 0
            
            for key in keys_to_remove[:]:
                if key in self.l1_cache:
                    self._remove_item(key)
                    count += 1
            
            return count
    
    async def invalidate_dependencies(self, dependency: str) -> int:
        """使依赖项失效"""
        with self.lock:
            keys_to_remove = self.dependency_graph.get(dependency, [])
            count = 0
            
            for key in keys_to_remove[:]:
                if key in self.l1_cache:
                    self._remove_item(key)
                    count += 1
            
            return count
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            return {
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'hit_rate': self.stats.hit_rate,
                'evictions': self.stats.evictions,
                'size_bytes': self.stats.size,
                'size_mb': self.stats.size / 1024 / 1024,
                'item_count': len(self.l1_cache),
                'max_size': self.max_size,
                'max_memory_mb': self.max_memory_bytes / 1024 / 1024,
                'memory_usage_percent': (self.stats.size / self.max_memory_bytes) * 100,
                'predictions_enabled': self.enable_prediction,
                'compression_enabled': self.enable_compression
            }
    
    async def clear_by_pattern(self, pattern: str) -> int:
        """按模式清理缓存"""
        import fnmatch
        with self.lock:
            keys_to_remove = []
            for key in self.l1_cache.keys():
                if fnmatch.fnmatch(key, pattern):
                    keys_to_remove.append(key)
            
            count = 0
            for key in keys_to_remove:
                if key in self.l1_cache:
                    self._remove_item(key)
                    count += 1
            
            return count
    
    async def clear_all(self) -> int:
        """清理所有缓存"""
        with self.lock:
            count = len(self.l1_cache)
            self.l1_cache.clear()
            self.tag_index.clear()
            self.dependency_graph.clear()
            self.stats.size = 0
            return count
    
    async def optimize(self) -> Dict[str, Any]:
        """优化缓存"""
        with self.lock:
            # 强制驱逐过期项
            expired_count = 0
            keys_to_remove = []
            
            for key, item in self.l1_cache.items():
                if item.is_expired():
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._remove_item(key)
                expired_count += 1
            
            # 运行驱逐策略
            self._ensure_capacity()
            
            return {
                'expired_removed': expired_count,
                'current_size': len(self.l1_cache),
                'memory_usage_mb': self.stats.size / 1024 / 1024,
                'timestamp': time.time()
            }
    
    async def get_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return {
            'max_size': self.max_size,
            'max_memory_bytes': self.max_memory_bytes,
            'default_ttl': self.default_ttl,
            'enable_prediction': self.enable_prediction,
            'enable_compression': self.enable_compression,
            'eviction_policy': type(self.eviction_policy).__name__
        }
    
    async def update_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """更新缓存配置"""
        with self.lock:
            if 'max_size' in config_dict:
                self.max_size = config_dict['max_size']
            if 'max_memory_bytes' in config_dict:
                self.max_memory_bytes = config_dict['max_memory_bytes']
            if 'default_ttl' in config_dict:
                self.default_ttl = config_dict['default_ttl']
            if 'enable_prediction' in config_dict:
                self.enable_prediction = config_dict['enable_prediction']
            if 'enable_compression' in config_dict:
                self.enable_compression = config_dict['enable_compression']
        
        return await self.get_config()
    
    async def get_keys(self, pattern: str = None, limit: int = 100) -> List[str]:
        """获取缓存键列表"""
        import fnmatch
        with self.lock:
            keys = list(self.l1_cache.keys())
            
            if pattern:
                keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
            
            return keys[:limit]
    
    def shutdown(self):
        """关闭缓存策略"""
        self._background_tasks_running = False
        self.executor.shutdown(wait=True)
        
        with self.lock:
            self.l1_cache.clear()
            self.tag_index.clear()
            self.dependency_graph.clear()

# 全局高级缓存策略实例
_advanced_cache_strategy: Optional[AdvancedCacheStrategy] = None

def get_advanced_cache_strategy() -> AdvancedCacheStrategy:
    """获取全局高级缓存策略实例"""
    global _advanced_cache_strategy
    if _advanced_cache_strategy is None:
        _advanced_cache_strategy = AdvancedCacheStrategy()
    return _advanced_cache_strategy

def shutdown_advanced_cache_strategy():
    """关闭全局高级缓存策略"""
    global _advanced_cache_strategy
    if _advanced_cache_strategy is not None:
        _advanced_cache_strategy.shutdown()
        _advanced_cache_strategy = None