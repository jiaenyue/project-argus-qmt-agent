"""Intelligent Alert System Module.

This module provides an advanced alert system with intelligent deduplication,
tiered alerting, and automatic recovery detection.
"""

# Import from modular structure
from .alert_types import (
    AlertPriority, AlertStatus, AlertCategory,
    IntelligentAlert, AlertRule, AlertSummary
)
from .alert_system import IntelligentAlertSystem
from .alert_instance import intelligent_alert_system

# Re-export for backward compatibility
__all__ = [
    "AlertPriority",
    "AlertStatus", 
    "AlertCategory",
    "IntelligentAlert",
    "AlertRule",
    "AlertSummary",
    "IntelligentAlertSystem",
    "intelligent_alert_system"
]