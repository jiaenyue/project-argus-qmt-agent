"""Main cache health checker implementation."""

import time
import asyncio
import logging
from typing import Dict, List, Any, Optional

from .health_status import HealthStatus, CheckSeverity
from .health_models import HealthCheckResult, SystemHealthReport
from .health_checks import HealthChecks
from .health_analyzer import HealthAnalyzer

logger = logging.getLogger(__name__)


class CacheHealthChecker:
    """Comprehensive cache health monitoring and diagnostic system."""
    
    def __init__(self, cache_monitor, cache_manager):
        """Initialize health checker.
        
        Args:
            cache_monitor: Cache performance monitor instance
            cache_manager: Cache manager instance
        """
        self.cache_monitor = cache_monitor
        self.cache_manager = cache_manager
        
        # Health check configuration
        self.config = {
            'check_interval': 300,  # 5 minutes
            'critical_thresholds': {
                'hit_rate_min': 0.5,  # 50%
                'memory_usage_max': 0.9,  # 90%
                'response_time_max': 5.0,  # 5 seconds
                'error_rate_max': 0.1,  # 10%
                'eviction_rate_max': 0.2  # 20%
            },
            'warning_thresholds': {
                'hit_rate_min': 0.7,  # 70%
                'memory_usage_max': 0.8,  # 80%
                'response_time_max': 2.0,  # 2 seconds
                'error_rate_max': 0.05,  # 5%
                'eviction_rate_max': 0.1  # 10%
            },
            'trend_analysis_window': 3600,  # 1 hour
            'baseline_period': 86400  # 24 hours
        }
        
        # Initialize components
        self.health_checks = HealthChecks(cache_monitor, cache_manager, self.config)
        self.health_analyzer = HealthAnalyzer(self.config)
        
        # Health check history
        self._health_history: List[SystemHealthReport] = []
        self._last_check_time = 0
        self._baseline_metrics: Optional[Dict[str, float]] = None
        self._is_monitoring = False
        self._start_time = time.time()
    
    async def start_health_monitoring(self):
        """Start continuous health monitoring."""
        if self._is_monitoring:
            logger.warning("Health monitoring is already running")
            return
        
        self._is_monitoring = True
        asyncio.create_task(self._health_monitoring_loop())
        logger.info("Started cache health monitoring")
    
    async def stop_health_monitoring(self):
        """Stop health monitoring."""
        self._is_monitoring = False
        logger.info("Stopped cache health monitoring")
    
    async def _health_monitoring_loop(self):
        """Main health monitoring loop."""
        while self._is_monitoring:
            try:
                await self.perform_health_check()
                await asyncio.sleep(self.config['check_interval'])
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.config['check_interval'])
    
    async def perform_health_check(self) -> SystemHealthReport:
        """Perform comprehensive health check.
        
        Returns:
            System health report
        """
        start_time = time.time()
        logger.info("Starting comprehensive health check")
        
        # Perform individual health checks
        checks = []
        
        # Core performance checks
        checks.append(await self.health_checks.check_cache_hit_rate())
        checks.append(await self.health_checks.check_memory_usage())
        checks.append(await self.health_checks.check_response_time())
        checks.append(await self.health_checks.check_error_rate())
        
        # System health checks
        checks.append(await self._check_cache_connectivity())
        checks.append(await self._check_monitoring_status())
        checks.append(await self._check_data_consistency())
        
        # Trend analysis checks
        checks.append(await self._check_performance_trends())
        checks.append(await self._check_capacity_planning())
        
        # Calculate overall health
        overall_status, health_score = self.health_analyzer.calculate_overall_health(checks)
        
        # Generate recommendations
        recommendations = self.health_analyzer.generate_health_recommendations(checks)
        
        # Create health report
        report = SystemHealthReport(
            overall_status=overall_status,
            health_score=health_score,
            timestamp=start_time,
            uptime_hours=self.health_analyzer.get_uptime_hours(self._start_time),
            checks=checks,
            summary=self.health_analyzer.create_health_summary(checks),
            recommendations=recommendations,
            next_check_time=start_time + self.config['check_interval']
        )
        
        # Store in history
        self._health_history.append(report)
        if len(self._health_history) > 100:  # Keep last 100 reports
            self._health_history.pop(0)
        
        self._last_check_time = start_time
        
        logger.info(f"Health check completed in {time.time() - start_time:.2f}s, "
                   f"status: {overall_status.value}, score: {health_score:.1f}")
        
        return report
    
    async def _check_cache_connectivity(self) -> HealthCheckResult:
        """Check cache connectivity."""
        try:
            # Test basic cache operations
            test_key = f"health_check_{int(time.time())}"
            test_value = "connectivity_test"
            
            # Test set operation
            await self.cache_manager.set(test_key, test_value, ttl=60)
            
            # Test get operation
            retrieved_value = await self.cache_manager.get(test_key)
            
            # Test delete operation
            await self.cache_manager.delete(test_key)
            
            if retrieved_value == test_value:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = "Cache connectivity is healthy"
                recommendations = []
            else:
                status = HealthStatus.WARNING
                severity = CheckSeverity.WARNING
                message = "Cache connectivity test failed - data mismatch"
                recommendations = ["Check cache backend connectivity"]
            
            return HealthCheckResult(
                check_name="cache_connectivity",
                status=status,
                severity=severity,
                message=message,
                details={
                    'test_successful': retrieved_value == test_value,
                    'test_key': test_key
                },
                timestamp=time.time(),
                recommendations=recommendations
            )
        
        except Exception as e:
            logger.error(f"Error checking cache connectivity: {e}")
            return HealthCheckResult(
                check_name="cache_connectivity",
                status=HealthStatus.CRITICAL,
                severity=CheckSeverity.CRITICAL,
                message=f"Cache connectivity failed: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check cache backend status", "Verify network connectivity"]
            )
    
    async def _check_monitoring_status(self) -> HealthCheckResult:
        """Check monitoring system status."""
        try:
            # Check if monitor is collecting data
            recent_metrics = self.cache_monitor.get_performance_summary(1)
            
            if recent_metrics and recent_metrics.get('total_operations', 0) > 0:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = "Monitoring system is active"
                recommendations = []
            else:
                status = HealthStatus.WARNING
                severity = CheckSeverity.WARNING
                message = "Monitoring system appears inactive"
                recommendations = ["Check monitoring configuration"]
            
            return HealthCheckResult(
                check_name="monitoring_status",
                status=status,
                severity=severity,
                message=message,
                details={
                    'recent_operations': recent_metrics.get('total_operations', 0) if recent_metrics else 0,
                    'monitoring_active': bool(recent_metrics)
                },
                timestamp=time.time(),
                recommendations=recommendations
            )
        
        except Exception as e:
            logger.error(f"Error checking monitoring status: {e}")
            return HealthCheckResult(
                check_name="monitoring_status",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check monitoring status: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check monitoring system"]
            )
    
    async def _check_data_consistency(self) -> HealthCheckResult:
        """Check cache data consistency."""
        try:
            cache_stats = self.cache_manager.get_stats()
            entry_count = getattr(cache_stats, 'entry_count', 0)
            
            # Basic consistency checks
            inconsistencies = []
            
            # Check if stats are reasonable
            hits = getattr(cache_stats, 'hits', 0)
            misses = getattr(cache_stats, 'misses', 0)
            
            if hits < 0 or misses < 0:
                inconsistencies.append("Negative hit/miss counts detected")
            
            if entry_count < 0:
                inconsistencies.append("Negative entry count detected")
            
            if inconsistencies:
                status = HealthStatus.WARNING
                severity = CheckSeverity.WARNING
                message = f"Data consistency issues detected: {', '.join(inconsistencies)}"
                recommendations = ["Check cache statistics calculation", "Consider cache reset"]
            else:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = "Cache data consistency is healthy"
                recommendations = []
            
            return HealthCheckResult(
                check_name="data_consistency",
                status=status,
                severity=severity,
                message=message,
                details={
                    'inconsistencies': inconsistencies,
                    'entry_count': entry_count,
                    'stats_valid': len(inconsistencies) == 0
                },
                timestamp=time.time(),
                recommendations=recommendations
            )
        
        except Exception as e:
            logger.error(f"Error checking data consistency: {e}")
            return HealthCheckResult(
                check_name="data_consistency",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check data consistency: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check cache manager status"]
            )
    
    async def _check_performance_trends(self) -> HealthCheckResult:
        """Check performance trends."""
        try:
            if len(self._health_history) < 2:
                return HealthCheckResult(
                    check_name="performance_trends",
                    status=HealthStatus.GOOD,
                    severity=CheckSeverity.INFO,
                    message="Insufficient data for trend analysis",
                    details={'history_count': len(self._health_history)},
                    timestamp=time.time(),
                    recommendations=["Continue monitoring to build trend data"]
                )
            
            # Analyze trends from recent health reports
            recent_reports = self._health_history[-10:]  # Last 10 reports
            
            # Extract hit rate trends
            hit_rates = []
            for report in recent_reports:
                for check in report.checks:
                    if check.check_name == "cache_hit_rate" and check.metrics:
                        hit_rates.append(check.metrics.get('hit_rate', 0))
            
            if len(hit_rates) >= 3:
                trend_direction = self.health_analyzer.calculate_trend(hit_rates)
                
                if trend_direction < -0.1:  # Declining trend
                    status = HealthStatus.WARNING
                    severity = CheckSeverity.WARNING
                    message = "Performance is declining - hit rate trending down"
                    recommendations = [
                        "Investigate cache configuration",
                        "Review access patterns"
                    ]
                elif trend_direction > 0.1:  # Improving trend
                    status = HealthStatus.GOOD
                    severity = CheckSeverity.INFO
                    message = "Performance is improving - hit rate trending up"
                    recommendations = []
                else:  # Stable trend
                    status = HealthStatus.GOOD
                    severity = CheckSeverity.INFO
                    message = "Performance is stable"
                    recommendations = []
            else:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = "Insufficient trend data"
                recommendations = []
                trend_direction = 0
            
            return HealthCheckResult(
                check_name="performance_trends",
                status=status,
                severity=severity,
                message=message,
                details={
                    'trend_direction': trend_direction if len(hit_rates) >= 3 else None,
                    'data_points': len(hit_rates),
                    'recent_hit_rates': hit_rates[-5:] if hit_rates else []
                },
                timestamp=time.time(),
                recommendations=recommendations
            )
        
        except Exception as e:
            logger.error(f"Error checking performance trends: {e}")
            return HealthCheckResult(
                check_name="performance_trends",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check performance trends: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check health history data"]
            )
    
    async def _check_capacity_planning(self) -> HealthCheckResult:
        """Check capacity planning metrics."""
        try:
            cache_stats = self.cache_manager.get_stats()
            memory_usage = getattr(cache_stats, 'memory_usage', 0)
            max_memory = getattr(cache_stats, 'max_memory', 1)
            entry_count = getattr(cache_stats, 'entry_count', 0)
            
            usage_ratio = memory_usage / max_memory if max_memory > 0 else 0
            
            # Predict when capacity will be reached
            if len(self._health_history) >= 5:
                recent_usage = []
                for report in self._health_history[-5:]:
                    for check in report.checks:
                        if check.check_name == "memory_usage" and check.metrics:
                            recent_usage.append(check.metrics.get('memory_usage_ratio', 0))
                
                if len(recent_usage) >= 3:
                    growth_rate = self.health_analyzer.calculate_trend(recent_usage)
                    
                    if growth_rate > 0.01:  # Growing at 1% per check
                        time_to_capacity = (1.0 - usage_ratio) / growth_rate
                        hours_to_capacity = time_to_capacity * self.config['check_interval'] / 3600
                        
                        if hours_to_capacity < 24:
                            status = HealthStatus.CRITICAL
                            severity = CheckSeverity.CRITICAL
                            message = f"Capacity will be reached in {hours_to_capacity:.1f} hours"
                        elif hours_to_capacity < 72:
                            status = HealthStatus.WARNING
                            severity = CheckSeverity.WARNING
                            message = f"Capacity will be reached in {hours_to_capacity:.1f} hours"
                        else:
                            status = HealthStatus.GOOD
                            severity = CheckSeverity.INFO
                            message = "Capacity planning looks healthy"
                    else:
                        status = HealthStatus.GOOD
                        severity = CheckSeverity.INFO
                        message = "Memory usage is stable or declining"
                        hours_to_capacity = None
                else:
                    status = HealthStatus.GOOD
                    severity = CheckSeverity.INFO
                    message = "Insufficient data for capacity prediction"
                    hours_to_capacity = None
            else:
                status = HealthStatus.GOOD
                severity = CheckSeverity.INFO
                message = "Building capacity planning data"
                hours_to_capacity = None
            
            recommendations = []
            if hours_to_capacity and hours_to_capacity < 72:
                recommendations.extend([
                    "Plan for cache capacity expansion",
                    "Review cache eviction policies",
                    "Consider data archiving strategies"
                ])
            
            return HealthCheckResult(
                check_name="capacity_planning",
                status=status,
                severity=severity,
                message=message,
                details={
                    'current_usage_ratio': usage_ratio,
                    'entry_count': entry_count,
                    'hours_to_capacity': hours_to_capacity,
                    'memory_usage_mb': memory_usage / (1024 * 1024)
                },
                timestamp=time.time(),
                recommendations=recommendations
            )
        
        except Exception as e:
            logger.error(f"Error checking capacity planning: {e}")
            return HealthCheckResult(
                check_name="capacity_planning",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.ERROR,
                message=f"Failed to check capacity planning: {e}",
                details={'error': str(e)},
                timestamp=time.time(),
                recommendations=["Check cache statistics availability"]
            )
    
    def get_health_history(self, limit: int = 10) -> List[SystemHealthReport]:
        """Get health check history.
        
        Args:
            limit: Maximum number of reports to return
            
        Returns:
            List of health reports
        """
        return self._health_history[-limit:] if self._health_history else []
    
    def get_latest_health_report(self) -> Optional[SystemHealthReport]:
        """Get the latest health report.
        
        Returns:
            Latest health report or None
        """
        return self._health_history[-1] if self._health_history else None