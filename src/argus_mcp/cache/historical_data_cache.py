# -*- coding: utf-8 -*-
"""
历史数据专用缓存系统

针对历史K线数据特点设计的缓存系统，支持多周期数据、分层缓存、智能TTL策略。
"""

import asyncio
import json
import logging
import hashlib
import time
from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import threading
from cachetools import TTLCache, LRUCache

from src.argus_mcp.data_models.historical_data import (
    StandardKLineData, 
    DataQualityMetrics,
    SupportedPeriod
)

logger = logging.getLogger(__name__)


class HistoricalDataType(Enum):
    """历史数据类型"""
    KLINE_DATA = "kline_data"
    QUALITY_METRICS = "quality_metrics"
    AGGREGATED_DATA = "aggregated_data"
    NORMALIZED_DATA = "normalized_data"


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    data_type: HistoricalDataType
    period: SupportedPeriod
    symbol: str
    created_at: float
    last_accessed: float
    access_count: int
    ttl: int
    size: int
    
    @property
    def age(self) -> float:
        """缓存条目年龄（秒）"""
        return time.time() - self.created_at
    
    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        return time.time() - self.created_at > self.ttl


class HistoricalDataCache:
    """历史数据专用缓存系统"""
    
    def __init__(
        self,
        max_memory_mb: int = 512,
        default_ttl_hours: int = 24,
        market_hours_ttl: int = 3600,  # 交易时间内TTL（秒）
        after_hours_ttl: int = 86400,  # 非交易时间TTL（秒）
    ):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl = default_ttl_hours * 3600
        self.market_hours_ttl = market_hours_ttl
        self.after_hours_ttl = after_hours_ttl
        
        # 分层缓存
        self.l1_cache = TTLCache(maxsize=10000, ttl=3600)  # 内存缓存
        self.l2_cache = TTLCache(maxsize=50000, ttl=86400)  # 扩展缓存
        
        # 缓存统计
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0,
            'memory_usage': 0
        }
        
        # 缓存索引
        self.symbol_index: Dict[str, List[str]] = {}
        self.period_index: Dict[str, List[str]] = {}
        self.data_type_index: Dict[str, List[str]] = {}
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 启动后台清理任务
        self._cleanup_task = None
        self._start_cleanup_task()
    
    async def get_kline_data(
        self,
        symbol: str,
        period: SupportedPeriod,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[List[StandardKLineData]]:
        """获取K线数据缓存"""
        key = self._generate_kline_key(symbol, period, start_time, end_time)
        
        with self._lock:
            self.stats['total_requests'] += 1
            
            # L1缓存查找
            if key in self.l1_cache:
                self.stats['hits'] += 1
                data = self.l1_cache[key]
                await self._update_access_stats(key)
                return data
            
            # L2缓存查找
            if key in self.l2_cache:
                self.stats['hits'] += 1
                data = self.l2_cache[key]
                # 提升到L1缓存
                self.l1_cache[key] = data
                await self._update_access_stats(key)
                return data
            
            self.stats['misses'] += 1
            return None
    
    async def set_kline_data(
        self,
        symbol: str,
        period: SupportedPeriod,
        start_time: datetime,
        end_time: datetime,
        data: List[StandardKLineData],
        custom_ttl: Optional[int] = None
    ) -> bool:
        """设置K线数据缓存"""
        key = self._generate_kline_key(symbol, period, start_time, end_time)
        
        # 计算TTL
        ttl = custom_ttl or self._calculate_ttl_by_period(period)
        
        # 计算数据大小
        data_size = self._calculate_data_size(data)
        
        with self._lock:
            # 检查内存使用
            if await self._check_memory_usage(data_size):
                await self._evict_entries()
            
            # 存储到缓存
            self.l1_cache[key] = data
            self.l2_cache[key] = data
            
            # 更新索引
            await self._update_index(key, symbol, str(period.value), "kline_data")
            
            # 更新统计
            self.stats['memory_usage'] += data_size
            
            logger.debug(f"缓存K线数据: {symbol} {period.value} [{start_time} - {end_time}], TTL: {ttl}s")
            return True
    
    async def get_quality_metrics(
        self,
        symbol: str,
        period: SupportedPeriod
    ) -> Optional[DataQualityMetrics]:
        """获取数据质量指标缓存"""
        key = self._generate_quality_key(symbol, period)
        
        with self._lock:
            self.stats['total_requests'] += 1
            
            # 优先从L1缓存获取
            if key in self.l1_cache:
                self.stats['hits'] += 1
                data = self.l1_cache[key]
                await self._update_access_stats(key)
                return data
            
            self.stats['misses'] += 1
            return None
    
    async def set_quality_metrics(
        self,
        symbol: str,
        period: SupportedPeriod,
        metrics: DataQualityMetrics,
        custom_ttl: Optional[int] = None
    ) -> bool:
        """设置数据质量指标缓存"""
        key = self._generate_quality_key(symbol, period)
        ttl = custom_ttl or self._calculate_ttl_by_period(period)
        
        with self._lock:
            self.l1_cache[key] = metrics
            self.l2_cache[key] = metrics
            
            await self._update_index(key, symbol, str(period.value), "quality_metrics")
            
            logger.debug(f"缓存质量指标: {symbol} {period.value}")
            return True
    
    async def invalidate_symbol(self, symbol: str) -> None:
        """使特定股票的所有缓存失效"""
        with self._lock:
            if symbol in self.symbol_index:
                keys = self.symbol_index[symbol]
                for key in keys:
                    self.l1_cache.pop(key, None)
                    self.l2_cache.pop(key, None)
                
                del self.symbol_index[symbol]
                logger.info(f"使股票 {symbol} 的所有缓存失效")
    
    async def invalidate_period(self, period: SupportedPeriod) -> None:
        """使特定周期的所有缓存失效"""
        with self._lock:
            period_key = str(period.value)
            if period_key in self.period_index:
                keys = self.period_index[period_key]
                for key in keys:
                    self.l1_cache.pop(key, None)
                    self.l2_cache.pop(key, None)
                
                del self.period_index[period_key]
                logger.info(f"使周期 {period.value} 的所有缓存失效")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            hit_rate = 0.0
            if self.stats['total_requests'] > 0:
                hit_rate = self.stats['hits'] / self.stats['total_requests']
            
            return {
                'hit_rate': hit_rate,
                'total_requests': self.stats['total_requests'],
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'memory_usage_mb': self.stats['memory_usage'] / (1024 * 1024),
                'l1_cache_size': len(self.l1_cache),
                'l2_cache_size': len(self.l2_cache),
                'symbols_cached': len(self.symbol_index),
                'periods_cached': len(self.period_index)
            }
    
    async def cleanup_expired(self) -> None:
        """清理过期缓存"""
        with self._lock:
            expired_keys = []
            
            # 检查L1缓存
            for key in list(self.l1_cache.keys()):
                if key not in self.l1_cache:  # 可能已被清理
                    continue
                
                # TTLCache自动清理，这里只做额外检查
                if self._is_key_expired(key):
                    expired_keys.append(key)
            
            # 清理索引
            for key in expired_keys:
                await self._remove_from_index(key)
            
            if expired_keys:
                logger.info(f"清理 {len(expired_keys)} 个过期缓存条目")
    
    def _generate_kline_key(
        self,
        symbol: str,
        period: SupportedPeriod,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """生成K线数据缓存键"""
        start_str = start_time.strftime("%Y%m%d%H%M")
        end_str = end_time.strftime("%Y%m%d%H%M")
        return f"kline:{symbol}:{period.value}:{start_str}:{end_str}"
    
    def _generate_quality_key(self, symbol: str, period: SupportedPeriod) -> str:
        """生成质量指标缓存键"""
        return f"quality:{symbol}:{period.value}"
    
    def _calculate_ttl_by_period(self, period: SupportedPeriod) -> int:
        """根据周期计算TTL"""
        ttl_map = {
            "1m": 300,      # 5分钟
            "5m": 900,      # 15分钟
            "15m": 1800,    # 30分钟
            "30m": 3600,    # 1小时
            "1h": 7200,     # 2小时
            "4h": 14400,    # 4小时
            "1d": 86400,    # 24小时
            "1w": 604800,   # 7天
            "1M": 2592000   # 30天
        }
        return ttl_map.get(str(period.value), self.default_ttl)
    
    def _calculate_data_size(self, data: List[StandardKLineData]) -> int:
        """估算数据大小（字节）"""
        if not data:
            return 0
        
        # 粗略估算：每条记录约200字节
        return len(data) * 200
    
    async def _check_memory_usage(self, new_data_size: int) -> bool:
        """检查内存使用"""
        total_size = self.stats['memory_usage'] + new_data_size
        return total_size > self.max_memory_bytes
    
    async def _evict_entries(self) -> None:
        """驱逐缓存条目"""
        # TTLCache自动驱逐最旧的条目
        self.stats['evictions'] += 1
    
    async def _update_index(self, key: str, symbol: str, period: str, data_type: str) -> None:
        """更新索引"""
        # 更新符号索引
        if symbol not in self.symbol_index:
            self.symbol_index[symbol] = []
        if key not in self.symbol_index[symbol]:
            self.symbol_index[symbol].append(key)
        
        # 更新周期索引
        if period not in self.period_index:
            self.period_index[period] = []
        if key not in self.period_index[period]:
            self.period_index[period].append(key)
        
        # 更新数据类型索引
        if data_type not in self.data_type_index:
            self.data_type_index[data_type] = []
        if key not in self.data_type_index[data_type]:
            self.data_type_index[data_type].append(key)
    
    async def _remove_from_index(self, key: str) -> None:
        """从索引中移除"""
        # 从所有索引中移除
        for index in [self.symbol_index, self.period_index, self.data_type_index]:
            for key_list in index.values():
                if key in key_list:
                    key_list.remove(key)
    
    async def _update_access_stats(self, key: str) -> None:
        """更新访问统计"""
        # 这里可以添加更详细的访问统计
        pass
    
    def _is_key_expired(self, key: str) -> bool:
        """检查键是否过期"""
        # TTLCache自动处理过期，这里返回False
        return False
    
    def _start_cleanup_task(self) -> None:
        """启动后台清理任务"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(3600)  # 每小时清理一次
                    await self.cleanup_expired()
                except Exception as e:
                    logger.error(f"缓存清理任务错误: {e}")
        
        # 注意：这里需要外部事件循环来运行
        # cleanup_task = asyncio.create_task(cleanup_loop())
    
    def shutdown(self) -> None:
        """关闭缓存系统"""
        logger.info("关闭历史数据缓存系统")


# 全局缓存实例
_historical_cache: Optional[HistoricalDataCache] = None


def get_historical_cache() -> HistoricalDataCache:
    """获取历史数据缓存实例"""
    global _historical_cache
    if _historical_cache is None:
        _historical_cache = HistoricalDataCache()
    return _historical_cache


def shutdown_historical_cache():
    """关闭历史数据缓存"""
    global _historical_cache
    if _historical_cache is not None:
        _historical_cache.shutdown()
        _historical_cache = None