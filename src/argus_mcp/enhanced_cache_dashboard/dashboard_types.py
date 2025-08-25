"""Enhanced Cache Dashboard Data Types.

This module contains all data classes and types used by the enhanced cache dashboard.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class ChartDataPoint:
    """Data point for charts."""
    timestamp: float
    value: float
    label: Optional[str] = None
    category: Optional[str] = None


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    metric_name: str
    trend_direction: str  # 'improving', 'declining', 'stable'
    trend_strength: float  # 0-1
    change_percentage: float
    prediction: Optional[float] = None
    confidence: Optional[float] = None


@dataclass
class PerformanceComparison:
    """Performance comparison between time periods."""
    metric_name: str
    current_period: Dict[str, Any]
    previous_period: Dict[str, Any]
    improvement_percentage: float
    status: str  # 'improved', 'degraded', 'stable'