"""Enhanced Cache Dashboard Instance Management.

This module provides global dashboard instance management.
"""

from typing import Optional
from .dashboard_core import EnhancedCacheDashboard

# Global dashboard instance
enhanced_cache_dashboard: Optional[EnhancedCacheDashboard] = None


def initialize_dashboard(cache_monitor, cache_manager) -> EnhancedCacheDashboard:
    """Initialize the global enhanced cache dashboard instance.
    
    Args:
        cache_monitor: Cache performance monitor instance
        cache_manager: Cache manager instance
        
    Returns:
        Initialized dashboard instance
    """
    global enhanced_cache_dashboard
    
    enhanced_cache_dashboard = EnhancedCacheDashboard(
        cache_monitor=cache_monitor,
        cache_manager=cache_manager
    )
    
    return enhanced_cache_dashboard


def get_dashboard() -> Optional[EnhancedCacheDashboard]:
    """Get the global enhanced cache dashboard instance.
    
    Returns:
        Dashboard instance if initialized, None otherwise
    """
    return enhanced_cache_dashboard