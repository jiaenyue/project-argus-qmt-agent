"""Health check data models."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .health_status import HealthStatus, CheckSeverity


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_name: str
    status: HealthStatus
    severity: CheckSeverity
    message: str
    details: Dict[str, Any]
    timestamp: float
    recommendations: List[str]
    metrics: Optional[Dict[str, float]] = None


@dataclass
class SystemHealthReport:
    """Comprehensive system health report."""
    overall_status: HealthStatus
    health_score: float
    timestamp: float
    uptime_hours: float
    checks: List[HealthCheckResult]
    summary: Dict[str, Any]
    recommendations: List[str]
    next_check_time: float