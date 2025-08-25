"""Alert Types and Data Structures.

This module defines all the data types, enums, and structures used by the intelligent alert system.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertCategory(Enum):
    """Alert categories."""
    PERFORMANCE = "performance"
    CAPACITY = "capacity"
    CONNECTIVITY = "connectivity"
    HEALTH = "health"
    SYSTEM = "system"


@dataclass
class IntelligentAlert:
    """Enhanced alert with intelligent features."""
    id: str
    title: str
    message: str
    category: AlertCategory
    priority: AlertPriority
    status: AlertStatus
    metric_name: str
    current_value: float
    threshold_value: float
    timestamp: float
    first_occurrence: float
    last_occurrence: float
    occurrence_count: int
    fingerprint: str
    tags: Dict[str, str]
    context: Dict[str, Any]
    recovery_threshold: Optional[float] = None
    escalation_level: int = 0
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[float] = None
    resolved_at: Optional[float] = None
    suppressed_until: Optional[float] = None


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    metric_name: str
    category: AlertCategory
    condition: str  # 'gt', 'lt', 'eq', 'ne'
    threshold: float
    priority: AlertPriority
    recovery_threshold: Optional[float] = None
    min_duration: int = 60  # seconds
    max_frequency: int = 300  # seconds between alerts
    escalation_thresholds: List[Tuple[int, AlertPriority]] = None  # (time, priority)
    tags: Dict[str, str] = None
    enabled: bool = True


@dataclass
class AlertSummary:
    """Alert summary statistics."""
    total_alerts: int
    active_alerts: int
    critical_alerts: int
    high_priority_alerts: int
    alerts_by_category: Dict[str, int]
    alerts_by_priority: Dict[str, int]
    recent_alerts: List[IntelligentAlert]
    top_metrics: List[Tuple[str, int]]  # (metric_name, count)
    alert_rate: float  # alerts per hour
    resolution_rate: float  # percentage