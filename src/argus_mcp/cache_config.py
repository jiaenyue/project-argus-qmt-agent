"""Argus MCP Server - Advanced Cache Configuration.

This module provides advanced caching configuration with optimized TTL settings,
multi-level caching, and intelligent cache management.
"""

import time
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache level enumeration."""
    L1 = "l1"  # Hot data cache
    L2 = "l2"  # Warm data cache
    L3 = "l3"  # Cold data cache


class DataType(Enum):
    """Data type enumeration for cache optimization."""
    TRADING_DATES = "trading_dates"
    STOCK_LIST = "stock_list"
    INSTRUMENT_DETAIL = "instrument_detail"
    LATEST_DATA = "latest_data"
    HISTORICAL_DATA = "historical_data"
    FULL_DATA = "full_data"
    MARKET_STATUS = "market_status"
    SECTOR_DATA = "sector_data"


@dataclass
class CacheRule:
    """Cache rule configuration."""
    ttl: int  # Time to live in seconds
    max_size: int  # Maximum number of entries
    level: CacheLevel  # Cache level
    priority: int  # Priority (1-10, higher is more important)
    preload: bool = False  # Whether to preload this data
    refresh_ahead: bool = False  # Whether to refresh before expiry
    refresh_threshold: float = 0.8  # Refresh when TTL reaches this ratio


class OptimizedCacheConfig:
    """Optimized cache configuration with intelligent TTL and multi-level caching."""
    
    def __init__(self):
        """Initialize optimized cache configuration."""
        self._cache_rules = self._initialize_cache_rules()
        self._dynamic_adjustments = {}
        self._performance_stats = {}
    
    def _initialize_cache_rules(self) -> Dict[str, CacheRule]:
        """Initialize optimized cache rules for different data types."""
        return {
            DataType.TRADING_DATES.value: CacheRule(
                ttl=86400,  # 24 hours - static data, rarely changes
                max_size=100,
                level=CacheLevel.L1,
                priority=9,
                preload=True,
                refresh_ahead=True,
                refresh_threshold=0.95  # Refresh very close to expiry
            ),
            DataType.STOCK_LIST.value: CacheRule(
                ttl=7200,  # 2 hours - semi-static, changes during trading hours
                max_size=500,
                level=CacheLevel.L1,
                priority=8,
                preload=True,
                refresh_ahead=True,
                refresh_threshold=0.85
            ),
            DataType.INSTRUMENT_DETAIL.value: CacheRule(
                ttl=3600,  # 1 hour - relatively stable instrument info
                max_size=1000,
                level=CacheLevel.L2,
                priority=7,
                preload=False,
                refresh_ahead=True,
                refresh_threshold=0.75
            ),
            DataType.LATEST_DATA.value: CacheRule(
                ttl=15,  # 15 seconds - very dynamic real-time data
                max_size=2000,
                level=CacheLevel.L1,
                priority=10,
                preload=False,
                refresh_ahead=True,
                refresh_threshold=0.3  # Refresh early for real-time data
            ),
            DataType.HISTORICAL_DATA.value: CacheRule(
                ttl=14400,  # 4 hours - historical data is stable
                max_size=500,
                level=CacheLevel.L3,
                priority=6,
                preload=False,
                refresh_ahead=False,
                refresh_threshold=0.9
            ),
            DataType.MARKET_STATUS.value: CacheRule(
                ttl=5,  # 5 seconds - extremely dynamic market data
                max_size=1000,
                level=CacheLevel.L1,
                priority=9,
                preload=False,
                refresh_ahead=True,
                refresh_threshold=0.2  # Very aggressive refresh
            ),
            DataType.SECTOR_DATA.value: CacheRule(
                ttl=3600,  # 1 hour - analysis results are computationally expensive
                max_size=200,
                level=CacheLevel.L2,
                priority=5,
                preload=False,
                refresh_ahead=True,
                refresh_threshold=0.8
            ),
            DataType.FULL_DATA.value: CacheRule(
                ttl=7200,  # 2 hours - user config changes infrequently
                max_size=100,
                level=CacheLevel.L2,
                priority=4,
                preload=True,
                refresh_ahead=False,
                refresh_threshold=0.95
            )
        }
    
    def get_cache_rule(self, data_type: Union[str, DataType]) -> CacheRule:
        """Get cache rule for a specific data type."""
        if isinstance(data_type, str):
            try:
                data_type = DataType(data_type)
            except ValueError:
                logger.warning(f"Unknown data type: {data_type}, using default rule")
                return self._get_default_rule()
        
        rule = self._cache_rules.get(data_type)
        if rule is None:
            logger.warning(f"No cache rule for data type: {data_type}, using default")
            return self._get_default_rule()
        
        # Apply dynamic adjustments if any
        return self._apply_dynamic_adjustments(data_type, rule)
    
    def _get_default_rule(self) -> CacheRule:
        """Get default cache rule."""
        return CacheRule(
            ttl=300,  # 5 minutes
            max_size=1000,
            level=CacheLevel.L2,
            priority=5,
            preload=False,
            refresh_ahead=False
        )
    
    def _apply_dynamic_adjustments(self, data_type: DataType, rule: CacheRule) -> CacheRule:
        """Apply dynamic adjustments based on performance stats."""
        adjustments = self._dynamic_adjustments.get(data_type, {})
        
        if not adjustments:
            return rule
        
        # Create a copy of the rule with adjustments
        adjusted_rule = CacheRule(
            ttl=int(rule.ttl * adjustments.get('ttl_multiplier', 1.0)),
            max_size=int(rule.max_size * adjustments.get('size_multiplier', 1.0)),
            level=rule.level,
            priority=rule.priority,
            preload=rule.preload,
            refresh_ahead=rule.refresh_ahead,
            refresh_threshold=rule.refresh_threshold
        )
        
        return adjusted_rule
    
    def calculate_ttl(self, data_type: Union[str, DataType], 
                     data_size: int = 0, 
                     access_frequency: float = 1.0) -> int:
        """Calculate optimized TTL based on data type, size, and access patterns."""
        rule = self.get_cache_rule(data_type)
        base_ttl = rule.ttl
        
        # Adjust based on data size
        size_factor = 1.0
        if data_size > 10000:  # Very large datasets
            size_factor = 1.5
        elif data_size > 1000:  # Large datasets
            size_factor = 1.2
        elif data_size < 10:  # Very small datasets
            size_factor = 0.5
        
        # Adjust based on access frequency
        frequency_factor = 1.0
        if access_frequency > 10:  # Very frequently accessed
            frequency_factor = 0.5
        elif access_frequency > 5:  # Frequently accessed
            frequency_factor = 0.8
        elif access_frequency < 0.1:  # Rarely accessed
            frequency_factor = 2.0
        
        # Calculate final TTL
        final_ttl = int(base_ttl * size_factor * frequency_factor)
        
        # Ensure minimum and maximum bounds
        min_ttl = 30 if rule.level == CacheLevel.L1 else 60
        max_ttl = 86400  # 24 hours
        
        return max(min_ttl, min(final_ttl, max_ttl))
    
    def should_preload(self, data_type: Union[str, DataType]) -> bool:
        """Check if data type should be preloaded."""
        rule = self.get_cache_rule(data_type)
        return rule.preload
    
    def should_refresh_ahead(self, data_type: Union[str, DataType], 
                           time_since_creation: float, ttl: int) -> bool:
        """Check if data should be refreshed ahead of expiry."""
        rule = self.get_cache_rule(data_type)
        
        if not rule.refresh_ahead:
            return False
        
        time_ratio = time_since_creation / ttl
        return time_ratio >= rule.refresh_threshold
    
    def get_cache_priority(self, data_type: Union[str, DataType]) -> int:
        """Get cache priority for eviction decisions."""
        rule = self.get_cache_rule(data_type)
        return rule.priority
    
    def get_cache_level(self, data_type: Union[str, DataType]) -> CacheLevel:
        """Get cache level for data type."""
        rule = self.get_cache_rule(data_type)
        return rule.level
    
    def update_performance_stats(self, data_type: Union[str, DataType], 
                               hit_rate: float, avg_access_time: float):
        """Update performance statistics for dynamic optimization."""
        if isinstance(data_type, str):
            try:
                data_type = DataType(data_type)
            except ValueError:
                return
        
        self._performance_stats[data_type] = {
            'hit_rate': hit_rate,
            'avg_access_time': avg_access_time,
            'last_updated': time.time()
        }
        
        # Trigger dynamic adjustment if needed
        self._adjust_cache_rules(data_type)
    
    def _adjust_cache_rules(self, data_type: DataType):
        """Dynamically adjust cache rules based on performance."""
        stats = self._performance_stats.get(data_type)
        if not stats:
            return
        
        hit_rate = stats['hit_rate']
        avg_access_time = stats['avg_access_time']
        
        adjustments = {}
        
        # Adjust TTL based on hit rate
        if hit_rate < 0.5:  # Low hit rate
            adjustments['ttl_multiplier'] = 1.5  # Increase TTL
        elif hit_rate > 0.9:  # Very high hit rate
            adjustments['ttl_multiplier'] = 0.8  # Decrease TTL for fresher data
        
        # Adjust cache size based on access time
        if avg_access_time > 1.0:  # Slow access
            adjustments['size_multiplier'] = 1.2  # Increase cache size
        
        if adjustments:
            self._dynamic_adjustments[data_type] = adjustments
            logger.info(f"Applied dynamic adjustments for {data_type.value}: {adjustments}")
    
    def get_cache_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current cache configuration."""
        summary = {
            'cache_rules': {},
            'dynamic_adjustments': self._dynamic_adjustments,
            'performance_stats': self._performance_stats
        }
        
        for data_type, rule in self._cache_rules.items():
            summary['cache_rules'][data_type.value] = {
                'ttl': rule.ttl,
                'max_size': rule.max_size,
                'level': rule.level.value,
                'priority': rule.priority,
                'preload': rule.preload,
                'refresh_ahead': rule.refresh_ahead
            }
        
        return summary
    
    def reset_dynamic_adjustments(self):
        """Reset all dynamic adjustments."""
        self._dynamic_adjustments.clear()
        logger.info("Reset all dynamic cache adjustments")


# Global cache configuration instance
cache_config = OptimizedCacheConfig()


def get_optimized_ttl(data_type: str, data_size: int = 0, 
                     access_frequency: float = 1.0) -> int:
    """Get optimized TTL for backward compatibility."""
    return cache_config.calculate_ttl(data_type, data_size, access_frequency)


def should_preload_data(data_type: str) -> bool:
    """Check if data should be preloaded."""
    return cache_config.should_preload(data_type)


def should_refresh_ahead_of_expiry(data_type: str, time_since_creation: float, ttl: int) -> bool:
    """Check if data should be refreshed ahead of expiry."""
    return cache_config.should_refresh_ahead(data_type, time_since_creation, ttl)