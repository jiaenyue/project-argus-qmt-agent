"""Cache Monitor Module.

This module provides comprehensive cache performance monitoring and analytics.
Refactored into a modular structure for better maintainability.
"""

# Import from modular structure
from .cache_monitor.cache_metrics import CacheMetrics, CacheAlert
from .cache_monitor.performance_monitor import CachePerformanceMonitor
from .cache_monitor.monitor_instance import cache_monitor

# Re-export for backward compatibility
__all__ = [
    "CacheMetrics",
    "CacheAlert", 
    "CachePerformanceMonitor",
    "cache_monitor"
]