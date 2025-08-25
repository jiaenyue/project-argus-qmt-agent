"""Health analysis and trend calculation utilities."""

import time
import logging
from typing import Dict, List, Any, Tuple

from .health_status import HealthStatus, CheckSeverity
from .health_models import HealthCheckResult, SystemHealthReport

logger = logging.getLogger(__name__)


class HealthAnalyzer:
    """Health analysis and trend calculation utilities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize health analyzer.
        
        Args:
            config: Health check configuration
        """
        self.config = config
    
    def calculate_overall_health(self, checks: List[HealthCheckResult]) -> Tuple[HealthStatus, float]:
        """Calculate overall health status and score.
        
        Args:
            checks: List of health check results
            
        Returns:
            Tuple of (overall_status, health_score)
        """
        if not checks:
            return HealthStatus.UNKNOWN, 0.0
        
        # Weight different check types
        weights = {
            'cache_hit_rate': 0.25,
            'memory_usage': 0.20,
            'response_time': 0.20,
            'error_rate': 0.15,
            'eviction_rate': 0.10,
            'cache_connectivity': 0.05,
            'monitoring_status': 0.05
        }
        
        total_score = 0.0
        total_weight = 0.0
        critical_count = 0
        warning_count = 0
        
        for check in checks:
            weight = weights.get(check.check_name, 0.05)
            total_weight += weight
            
            # Convert status to score
            if check.status == HealthStatus.EXCELLENT:
                score = 100
            elif check.status == HealthStatus.GOOD:
                score = 85
            elif check.status == HealthStatus.WARNING:
                score = 60
                warning_count += 1
            elif check.status == HealthStatus.CRITICAL:
                score = 20
                critical_count += 1
            else:  # UNKNOWN
                score = 50
            
            total_score += score * weight
        
        # Calculate weighted average
        health_score = total_score / total_weight if total_weight > 0 else 0
        
        # Determine overall status
        if critical_count > 0:
            overall_status = HealthStatus.CRITICAL
        elif warning_count >= 3:
            overall_status = HealthStatus.WARNING
        elif warning_count > 0:
            overall_status = HealthStatus.WARNING
        elif health_score >= 90:
            overall_status = HealthStatus.EXCELLENT
        elif health_score >= 75:
            overall_status = HealthStatus.GOOD
        else:
            overall_status = HealthStatus.WARNING
        
        return overall_status, health_score
    
    def generate_health_recommendations(self, checks: List[HealthCheckResult]) -> List[str]:
        """Generate health recommendations based on check results.
        
        Args:
            checks: List of health check results
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Collect all recommendations from checks
        for check in checks:
            recommendations.extend(check.recommendations)
        
        # Remove duplicates while preserving order
        unique_recommendations = []
        seen = set()
        for rec in recommendations:
            if rec not in seen:
                unique_recommendations.append(rec)
                seen.add(rec)
        
        # Add general recommendations based on patterns
        critical_checks = [c for c in checks if c.status == HealthStatus.CRITICAL]
        warning_checks = [c for c in checks if c.status == HealthStatus.WARNING]
        
        if len(critical_checks) > 1:
            unique_recommendations.insert(0, "Multiple critical issues detected - prioritize immediate action")
        
        if len(warning_checks) >= 3:
            unique_recommendations.append("Multiple warnings detected - schedule maintenance window")
        
        return unique_recommendations[:10]  # Limit to top 10 recommendations
    
    def create_health_summary(self, checks: List[HealthCheckResult]) -> Dict[str, Any]:
        """Create health summary from check results.
        
        Args:
            checks: List of health check results
            
        Returns:
            Health summary dictionary
        """
        summary = {
            'total_checks': len(checks),
            'status_counts': {
                'excellent': 0,
                'good': 0,
                'warning': 0,
                'critical': 0,
                'unknown': 0
            },
            'severity_counts': {
                'info': 0,
                'warning': 0,
                'error': 0,
                'critical': 0
            },
            'key_metrics': {},
            'issues': []
        }
        
        for check in checks:
            # Count statuses
            summary['status_counts'][check.status.value] += 1
            summary['severity_counts'][check.severity.value] += 1
            
            # Collect key metrics
            if check.metrics:
                summary['key_metrics'].update(check.metrics)
            
            # Collect issues
            if check.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                summary['issues'].append({
                    'check': check.check_name,
                    'status': check.status.value,
                    'message': check.message
                })
        
        return summary
    
    def calculate_trend(self, values: List[float]) -> float:
        """Calculate trend direction from a series of values.
        
        Args:
            values: List of numeric values
            
        Returns:
            Trend direction (positive = increasing, negative = decreasing)
        """
        if len(values) < 2:
            return 0.0
        
        # Simple linear regression slope
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        denominator = n * x2_sum - x_sum * x_sum
        if denominator == 0:
            return 0.0
        
        slope = (n * xy_sum - x_sum * y_sum) / denominator
        return slope
    
    def get_uptime_hours(self, start_time: float) -> float:
        """Calculate uptime in hours.
        
        Args:
            start_time: Start timestamp
            
        Returns:
            Uptime in hours
        """
        return (time.time() - start_time) / 3600