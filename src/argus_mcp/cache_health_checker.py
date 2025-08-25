"""Argus MCP Server - Cache Health Checker.

This module provides comprehensive cache health monitoring and diagnostic capabilities.
"""

import logging

# Import from new modular structure
from .health_checker import (
    HealthStatus, CheckSeverity, HealthCheckResult, SystemHealthReport,
    CacheHealthChecker
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    'HealthStatus',
    'CheckSeverity', 
    'HealthCheckResult',
    'SystemHealthReport',
    'CacheHealthChecker'
]