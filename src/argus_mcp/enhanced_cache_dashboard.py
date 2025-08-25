"""Enhanced Cache Dashboard - Import Interface.

This module provides backward compatibility by importing and re-exporting
all components from the modularized enhanced_cache_dashboard package.
"""

# Import all components from the modularized structure
from .enhanced_cache_dashboard import (
    ChartDataPoint,
    TrendAnalysis,
    PerformanceComparison,
    EnhancedCacheDashboard,
    enhanced_cache_dashboard,
    initialize_dashboard,
    get_dashboard
)

# Re-export everything for backward compatibility
__all__ = [
    'ChartDataPoint',
    'TrendAnalysis', 
    'PerformanceComparison',
    'EnhancedCacheDashboard',
    'enhanced_cache_dashboard',
    'initialize_dashboard',
    'get_dashboard'
]