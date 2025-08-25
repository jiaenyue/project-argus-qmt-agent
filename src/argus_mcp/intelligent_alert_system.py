"""Intelligent Alert System Module.

This module provides backward compatibility by importing from the new modular structure.
"""

# Import all components from the new modular structure
from .intelligent_alert_system.alert_types import (
    AlertPriority,
    AlertStatus,
    AlertCategory,
    IntelligentAlert,
    AlertRule,
    AlertSummary
)

from .intelligent_alert_system.alert_system import IntelligentAlertSystem

from .intelligent_alert_system.alert_instance import (
    intelligent_alert_system,
    initialize_alert_system,
    get_alert_system
)

# Re-export everything for backward compatibility
__all__ = [
    'AlertPriority',
    'AlertStatus', 
    'AlertCategory',
    'IntelligentAlert',
    'AlertRule',
    'AlertSummary',
    'IntelligentAlertSystem',
    'intelligent_alert_system',
    'initialize_alert_system',
    'get_alert_system'
]