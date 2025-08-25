"""Cache Monitor Instance Module.

This module provides a global cache monitor instance for the application.
"""

from .performance_monitor import CachePerformanceMonitor

# Global cache monitor instance
cache_monitor = CachePerformanceMonitor()