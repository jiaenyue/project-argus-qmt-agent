"""Enhanced Cache Dashboard Module.

This module provides an enhanced dashboard with real-time charts,
historical trend analysis, and performance comparison features.
"""

from .dashboard_types import (
    ChartDataPoint,
    TrendAnalysis,
    PerformanceComparison
)

from .dashboard_core import EnhancedCacheDashboard

from .dashboard_instance import (
    enhanced_cache_dashboard,
    initialize_dashboard,
    get_dashboard
)

# Re-export everything for easy access
__all__ = [
    'ChartDataPoint',
    'TrendAnalysis',
    'PerformanceComparison',
    'EnhancedCacheDashboard',
    'enhanced_cache_dashboard',
    'initialize_dashboard',
    'get_dashboard'
]