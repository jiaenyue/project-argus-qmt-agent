"""Cache Manager Module.

This module provides cache management functionality with multiple eviction policies,
performance monitoring, and adaptive optimization.
"""

from .cache_stats import CacheStats
from .cache_policy import CachePolicy
from .cache_entry import CacheEntry
from .cache_manager_core import CacheManager, CacheDecorator

__all__ = [
    "CacheStats",
    "CachePolicy", 
    "CacheEntry",
    "CacheManager",
    "CacheDecorator"
]