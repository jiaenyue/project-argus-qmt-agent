"""Global Intelligent Alert System Instance.

This module provides a global instance of the intelligent alert system.
"""

from .alert_system import IntelligentAlertSystem

# Global intelligent alert system instance
# Will be initialized when cache_monitor, cache_manager, and health_checker are available
intelligent_alert_system = None


def initialize_alert_system(cache_monitor, cache_manager, health_checker):
    """Initialize the global alert system instance.
    
    Args:
        cache_monitor: Cache performance monitor
        cache_manager: Cache manager
        health_checker: Cache health checker
    """
    global intelligent_alert_system
    intelligent_alert_system = IntelligentAlertSystem(
        cache_monitor=cache_monitor,
        cache_manager=cache_manager,
        health_checker=health_checker
    )
    return intelligent_alert_system


def get_alert_system():
    """Get the global alert system instance.
    
    Returns:
        IntelligentAlertSystem: The global alert system instance
        
    Raises:
        RuntimeError: If the alert system has not been initialized
    """
    if intelligent_alert_system is None:
        raise RuntimeError("Alert system not initialized. Call initialize_alert_system() first.")
    return intelligent_alert_system