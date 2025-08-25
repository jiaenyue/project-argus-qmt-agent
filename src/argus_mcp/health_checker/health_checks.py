"""Health check implementations."""

import time
import logging
from typing import Dict, List, Any

from .health_status import HealthStatus, CheckSeverity
from .health_models import HealthCheckResult

logger = logging.getLogger(__name__)


class HealthChecks:
    """Individual health check implementations."""
    
    def __init__(self, cache_monitor, cache_manager, config: Dict[str, Any]):
        """Initialize health checks.
        
        Args:
            cache_monitor: Cache performance monitor instance
            cache_manager: Cache manager instance
            config: Health check configuration
        """
        self.cache_monitor = cache_monitor
        self.cache_manager = cache_manager
        self.config = config
    
    async def check_cache_hit_rate(self) -> HealthCheckResult:
        """Check cache hit rate."""
        try:
            cache_stats = self.cache_manager.get_stats()
            hit_rate = getattr(cache_stats, 'hit_rate', 0.0)
            
            if hit_rate < self.config['critical_thresholds']['hit_rate_min']:
                status = HealthStatus.CRITICAL
                severity = CheckSeverity.CRITICAL
                message = f"Critical: Cache hit rate is {hit_rate:.1%}, below {self.config['critical_thresholds']['hit_rate_min']:.1%}"
            elif hit_rate < self.config['warning_thresholds']['hit_rate_min']:
                status = HealthStatus.WARNING
                severity = CheckSeverity.WARNING
                message = f"Warning: Cache hit rate is {hit_rate:.1%}, below optimal {self.config['warning_thresholds']['hit_rate_min']:.1%}"
            else:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = f"Cache hit rate is healthy at {hit_rate:.1%}"
            
            recommendations = []
            if hit_rate < 0.8:
                recommendations.extend([
                    "Review cache TTL settings",
                    "Analyze cache key patterns",
                    "Consider implementing cache warming strategies"
                ])
            
            return HealthCheckResult(
                check_name="cache_hit_rate",
                status=status,
                severity=severity,
                message=message,
                details={
                    'current_hit_rate': hit_rate,
                    'critical_threshold': self.config['critical_thresholds']['hit_rate_min'],
                    'warning_threshold': self.config['warning_thresholds']['hit_rate_min'],
                    'total_requests': getattr(cache_stats, 'hits', 0) + getattr(cache_stats, 'misses', 0)
                },
                timestamp=time.time(),
                recommendations=recommendations,
                metrics={'hit_rate': hit_rate}
            )
        
        except Exception as e:
            logger.error(f"Error checking cache hit rate: {e}")
            return HealthCheckResult(
                check_name="cache_hit_rate",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check cache hit rate: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check cache manager connectivity"]
            )
    
    async def check_memory_usage(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            cache_stats = self.cache_manager.get_stats()
            memory_usage = getattr(cache_stats, 'memory_usage', 0)
            max_memory = getattr(cache_stats, 'max_memory', 1)
            
            usage_ratio = memory_usage / max_memory if max_memory > 0 else 0
            
            if usage_ratio > self.config['critical_thresholds']['memory_usage_max']:
                status = HealthStatus.CRITICAL
                severity = CheckSeverity.CRITICAL
                message = f"Critical: Memory usage is {usage_ratio:.1%}, exceeding {self.config['critical_thresholds']['memory_usage_max']:.1%}"
            elif usage_ratio > self.config['warning_thresholds']['memory_usage_max']:
                status = HealthStatus.WARNING
                severity = CheckSeverity.WARNING
                message = f"Warning: Memory usage is {usage_ratio:.1%}, approaching limit"
            else:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = f"Memory usage is healthy at {usage_ratio:.1%}"
            
            recommendations = []
            if usage_ratio > 0.8:
                recommendations.extend([
                    "Consider increasing cache memory limit",
                    "Review cache eviction policies",
                    "Analyze large cache entries"
                ])
            
            return HealthCheckResult(
                check_name="memory_usage",
                status=status,
                severity=severity,
                message=message,
                details={
                    'current_usage_bytes': memory_usage,
                    'max_memory_bytes': max_memory,
                    'usage_ratio': usage_ratio,
                    'entry_count': getattr(cache_stats, 'entry_count', 0)
                },
                timestamp=time.time(),
                recommendations=recommendations,
                metrics={'memory_usage_ratio': usage_ratio}
            )
        
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
            return HealthCheckResult(
                check_name="memory_usage",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check memory usage: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check cache manager connectivity"]
            )
    
    async def check_response_time(self) -> HealthCheckResult:
        """Check cache response time."""
        try:
            cache_stats = self.cache_manager.get_stats()
            avg_response_time = getattr(cache_stats, 'avg_response_time', 0)
            
            if avg_response_time > self.config['critical_thresholds']['response_time_max']:
                status = HealthStatus.CRITICAL
                severity = CheckSeverity.CRITICAL
                message = f"Critical: Average response time is {avg_response_time:.3f}s, exceeding {self.config['critical_thresholds']['response_time_max']}s"
            elif avg_response_time > self.config['warning_thresholds']['response_time_max']:
                status = HealthStatus.WARNING
                severity = CheckSeverity.WARNING
                message = f"Warning: Average response time is {avg_response_time:.3f}s, above optimal threshold"
            else:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = f"Response time is healthy at {avg_response_time:.3f}s"
            
            recommendations = []
            if avg_response_time > 1.0:
                recommendations.extend([
                    "Optimize cache lookup algorithms",
                    "Check for network latency issues",
                    "Consider cache partitioning"
                ])
            
            return HealthCheckResult(
                check_name="response_time",
                status=status,
                severity=severity,
                message=message,
                details={
                    'avg_response_time': avg_response_time,
                    'critical_threshold': self.config['critical_thresholds']['response_time_max'],
                    'warning_threshold': self.config['warning_thresholds']['response_time_max']
                },
                timestamp=time.time(),
                recommendations=recommendations,
                metrics={'avg_response_time': avg_response_time}
            )
        
        except Exception as e:
            logger.error(f"Error checking response time: {e}")
            return HealthCheckResult(
                check_name="response_time",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check response time: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check cache manager connectivity"]
            )
    
    async def check_error_rate(self) -> HealthCheckResult:
        """Check cache error rate."""
        try:
            # Get error statistics from monitor
            performance_summary = self.cache_monitor.get_performance_summary(1)
            total_operations = performance_summary.get('total_operations', 1)
            error_count = performance_summary.get('error_count', 0)
            
            error_rate = error_count / total_operations if total_operations > 0 else 0
            
            if error_rate > self.config['critical_thresholds']['error_rate_max']:
                status = HealthStatus.CRITICAL
                severity = CheckSeverity.CRITICAL
                message = f"Critical: Error rate is {error_rate:.1%}, exceeding {self.config['critical_thresholds']['error_rate_max']:.1%}"
            elif error_rate > self.config['warning_thresholds']['error_rate_max']:
                status = HealthStatus.WARNING
                severity = CheckSeverity.WARNING
                message = f"Warning: Error rate is {error_rate:.1%}, above acceptable threshold"
            else:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = f"Error rate is healthy at {error_rate:.1%}"
            
            recommendations = []
            if error_rate > 0.02:
                recommendations.extend([
                    "Investigate error patterns",
                    "Check cache backend connectivity",
                    "Review error handling logic"
                ])
            
            return HealthCheckResult(
                check_name="error_rate",
                status=status,
                severity=severity,
                message=message,
                details={
                    'error_rate': error_rate,
                    'error_count': error_count,
                    'total_operations': total_operations,
                    'critical_threshold': self.config['critical_thresholds']['error_rate_max']
                },
                timestamp=time.time(),
                recommendations=recommendations,
                metrics={'error_rate': error_rate}
            )
        
        except Exception as e:
            logger.error(f"Error checking error rate: {e}")
            return HealthCheckResult(
                check_name="error_rate",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check error rate: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check cache manager connectivity"]
            )