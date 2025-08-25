"""Cache Metrics Module.

This module defines data structures for cache performance metrics and alerts.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    timestamp: float
    hit_rate: float
    miss_rate: float
    eviction_rate: float
    memory_usage: int
    entry_count: int
    avg_access_time: float
    cache_level: str
    data_type: Optional[str] = None


@dataclass
class CacheAlert:
    """Cache performance alert."""
    timestamp: float
    level: str  # INFO, WARNING, ERROR
    message: str
    metric_name: str
    current_value: float
    threshold: float
    cache_level: Optional[str] = None