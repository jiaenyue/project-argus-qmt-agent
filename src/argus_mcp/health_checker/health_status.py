"""Health status enums and constants."""

from enum import Enum


class HealthStatus(Enum):
    """Health status levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CheckSeverity(Enum):
    """Check severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"