"""Cache Performance Monitor Module.

This module provides comprehensive cache performance monitoring and analytics.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import asdict
from threading import Lock
from typing import Any, Dict, List, Optional

from .cache_metrics import CacheMetrics, CacheAlert

logger = logging.getLogger(__name__)


class CachePerformanceMonitor:
    """Advanced cache performance monitor with comprehensive analytics."""
    
    def __init__(self, max_history: int = 1000):
        """Initialize the cache performance monitor.
        
        Args:
            max_history: Maximum number of metrics to keep in history
        """
        self._max_history = max_history
        self._metrics_history = deque(maxlen=max_history)
        self._alerts_history = deque(maxlen=max_history)
        self._data_type_metrics = defaultdict(list)
        self._lock = Lock()
        self._monitoring = False
        self._monitor_task = None
        
        # Performance thresholds
        self._thresholds = {
            'hit_rate_warning': 0.7,
            'hit_rate_critical': 0.5,
            'memory_warning': 1000000000,  # 1GB
            'memory_critical': 2000000000,  # 2GB
            'access_time_warning': 0.05,   # 50ms
            'access_time_critical': 0.1,   # 100ms
            'eviction_rate_warning': 0.1,
            'eviction_rate_critical': 0.2
        }
        
        # Current statistics
        self._current_stats = {
            'total_requests': 0,
            'total_hits': 0,
            'total_misses': 0,
            'total_evictions': 0,
            'start_time': time.time()
        }
        
        # Performance trends
        self._performance_trends = {
            'hit_rate': deque(maxlen=100),
            'memory_usage': deque(maxlen=100),
            'access_time': deque(maxlen=100)
        }
        
        # Alert deduplication
        self._last_alerts = {}
        self._alert_cooldown = 300  # 5 minutes
    
    async def start_monitoring(self, interval: int = 60):
        """Start the monitoring loop.
        
        Args:
            interval: Monitoring interval in seconds
        """
        if self._monitoring:
            logger.warning("Cache monitoring is already running")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop(interval))
        logger.info(f"Started cache performance monitoring with {interval}s interval")
    
    async def stop_monitoring(self):
        """Stop the monitoring loop."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped cache performance monitoring")
    
    async def _monitoring_loop(self, interval: int):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                await self._collect_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_metrics(self):
        """Collect current cache metrics."""
        # This would be implemented to collect actual metrics from cache
        # For now, we'll create a placeholder implementation
        current_time = time.time()
        
        # Placeholder metrics - in real implementation, these would come from actual cache
        metrics = CacheMetrics(
            timestamp=current_time,
            hit_rate=0.85,  # Would be calculated from actual cache stats
            miss_rate=0.15,
            eviction_rate=0.05,
            memory_usage=500000000,  # 500MB
            entry_count=10000,
            avg_access_time=0.02,  # 20ms
            cache_level="L1"
        )
        
        self.record_metrics(metrics)
    
    def record_cache_access(self, cache_level: str, hit: bool, access_time: float, 
                          data_type: Optional[str] = None):
        """Record a cache access event.
        
        Args:
            cache_level: Cache level (L1, L2, etc.)
            hit: Whether it was a cache hit
            access_time: Access time in seconds
            data_type: Type of data accessed
        """
        with self._lock:
            self._current_stats['total_requests'] += 1
            if hit:
                self._current_stats['total_hits'] += 1
            else:
                self._current_stats['total_misses'] += 1
    
    def record_eviction(self, cache_level: str, reason: str, data_type: Optional[str] = None):
        """Record a cache eviction event.
        
        Args:
            cache_level: Cache level
            reason: Eviction reason (capacity, ttl, manual)
            data_type: Type of data evicted
        """
        with self._lock:
            self._current_stats['total_evictions'] += 1
            
            # Check for high eviction rate alert
            current_time = time.time()
            recent_evictions = sum(1 for m in self._metrics_history 
                                 if current_time - m.timestamp < 300)  # Last 5 minutes
            
            if recent_evictions > 100:  # Threshold for high eviction rate
                alert = CacheAlert(
                    timestamp=current_time,
                    level="WARNING",
                    message=f"High eviction rate detected: {recent_evictions} evictions in 5 minutes",
                    metric_name="eviction_rate",
                    current_value=recent_evictions,
                    threshold=100,
                    cache_level=cache_level
                )
                self._add_alert(alert)
    
    def record_metrics(self, metrics: CacheMetrics):
        """Record cache metrics.
        
        Args:
            metrics: Cache metrics to record
        """
        with self._lock:
            self._metrics_history.append(metrics)
            
            # Update performance trends
            self._performance_trends['hit_rate'].append(metrics.hit_rate)
            self._performance_trends['memory_usage'].append(metrics.memory_usage)
            self._performance_trends['access_time'].append(metrics.avg_access_time)
            
            # Store data type specific metrics
            if metrics.data_type:
                self._data_type_metrics[metrics.data_type].append(metrics)
            
            # Check for alerts
            self._check_alerts(metrics)
    
    def _check_alerts(self, metrics: CacheMetrics):
        """Check metrics against thresholds and generate alerts."""
        current_time = time.time()
        
        # Hit rate alerts
        if metrics.hit_rate < self._thresholds['hit_rate_critical']:
            self._create_alert(current_time, "ERROR", 
                             f"Critical hit rate: {metrics.hit_rate:.1%}",
                             "hit_rate", metrics.hit_rate, 
                             self._thresholds['hit_rate_critical'],
                             metrics.cache_level)
        elif metrics.hit_rate < self._thresholds['hit_rate_warning']:
            self._create_alert(current_time, "WARNING",
                             f"Low hit rate: {metrics.hit_rate:.1%}",
                             "hit_rate", metrics.hit_rate,
                             self._thresholds['hit_rate_warning'],
                             metrics.cache_level)
        
        # Memory usage alerts
        if metrics.memory_usage > self._thresholds['memory_critical']:
            self._create_alert(current_time, "ERROR",
                             f"Critical memory usage: {metrics.memory_usage/1000000:.1f}MB",
                             "memory_usage", metrics.memory_usage,
                             self._thresholds['memory_critical'],
                             metrics.cache_level)
        elif metrics.memory_usage > self._thresholds['memory_warning']:
            self._create_alert(current_time, "WARNING",
                             f"High memory usage: {metrics.memory_usage/1000000:.1f}MB",
                             "memory_usage", metrics.memory_usage,
                             self._thresholds['memory_warning'],
                             metrics.cache_level)
        
        # Access time alerts
        if metrics.avg_access_time > self._thresholds['access_time_critical']:
            self._create_alert(current_time, "ERROR",
                             f"Critical access time: {metrics.avg_access_time*1000:.1f}ms",
                             "access_time", metrics.avg_access_time,
                             self._thresholds['access_time_critical'],
                             metrics.cache_level)
        elif metrics.avg_access_time > self._thresholds['access_time_warning']:
            self._create_alert(current_time, "WARNING",
                             f"Slow access time: {metrics.avg_access_time*1000:.1f}ms",
                             "access_time", metrics.avg_access_time,
                             self._thresholds['access_time_warning'],
                             metrics.cache_level)
        
        # Cache thrashing detection
        if len(self._performance_trends['hit_rate']) >= 10:
            recent_hit_rates = list(self._performance_trends['hit_rate'])[-10:]
            hit_rate_variance = self._calculate_variance(recent_hit_rates)
            
            if hit_rate_variance > 0.1:  # High variance indicates thrashing
                self._create_alert(current_time, "WARNING",
                                 f"Cache thrashing detected (hit rate variance: {hit_rate_variance:.3f})",
                                 "cache_thrashing", hit_rate_variance, 0.1,
                                 metrics.cache_level)
        
        # Performance degradation detection
        if len(self._performance_trends['access_time']) >= 20:
            recent_times = list(self._performance_trends['access_time'])[-10:]
            older_times = list(self._performance_trends['access_time'])[-20:-10]
            
            recent_avg = sum(recent_times) / len(recent_times)
            older_avg = sum(older_times) / len(older_times)
            
            if recent_avg > older_avg * 1.5:  # 50% increase
                self._create_alert(current_time, "WARNING",
                                 f"Performance degradation detected: {recent_avg*1000:.1f}ms vs {older_avg*1000:.1f}ms",
                                 "performance_degradation", recent_avg, older_avg,
                                 metrics.cache_level)
    
    def _create_alert(self, timestamp: float, level: str, message: str,
                     metric_name: str, current_value: float, threshold: float,
                     cache_level: Optional[str] = None):
        """Create and store an alert with deduplication."""
        alert_key = f"{metric_name}_{level}_{cache_level}"
        
        # Check if we've recently sent this alert
        if (alert_key in self._last_alerts and 
            timestamp - self._last_alerts[alert_key] < self._alert_cooldown):
            return
        
        alert = CacheAlert(
            timestamp=timestamp,
            level=level,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
            cache_level=cache_level
        )
        
        self._add_alert(alert)
        self._last_alerts[alert_key] = timestamp
    
    def _add_alert(self, alert: CacheAlert):
        """Add alert to history and log it."""
        self._alerts_history.append(alert)
        
        log_level = {
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }.get(alert.level, logging.INFO)
        
        logger.log(log_level, f"Cache Alert: {alert.message}")
    
    def _analyze_performance(self) -> Dict[str, Any]:
        """Analyze current performance and return insights."""
        if not self._metrics_history:
            return {'status': 'no_data'}
        
        latest = self._metrics_history[-1]
        trends = self._calculate_trend()
        
        return {
            'current_hit_rate': latest.hit_rate,
            'memory_usage_mb': latest.memory_usage / (1024 * 1024),
            'avg_access_time_ms': latest.avg_access_time * 1000,
            'trends': trends,
            'health_score': self._calculate_health_score(latest),
            'recommendations': self._get_recommendations(latest, trends)
        }
    
    def _calculate_trend(self) -> Dict[str, str]:
        """Calculate performance trends."""
        if len(self._metrics_history) < 10:
            return {'insufficient_data': True}
        
        recent = list(self._metrics_history)[-5:]
        older = list(self._metrics_history)[-10:-5]
        
        recent_hit_rate = sum(m.hit_rate for m in recent) / len(recent)
        older_hit_rate = sum(m.hit_rate for m in older) / len(older)
        
        recent_access_time = sum(m.avg_access_time for m in recent) / len(recent)
        older_access_time = sum(m.avg_access_time for m in older) / len(older)
        
        return {
            'hit_rate': 'improving' if recent_hit_rate > older_hit_rate else 'declining',
            'access_time': 'improving' if recent_access_time < older_access_time else 'declining'
        }
    
    def _calculate_health_score(self, metrics: CacheMetrics) -> float:
        """Calculate overall cache health score (0-100)."""
        hit_rate_score = metrics.hit_rate * 100
        memory_score = max(0, 100 - (metrics.memory_usage / 20000000))  # Assume 2GB max
        speed_score = max(0, 100 - (metrics.avg_access_time * 1000))  # 100ms baseline
        
        return (hit_rate_score * 0.5 + memory_score * 0.3 + speed_score * 0.2)
    
    def _get_recommendations(self, metrics: CacheMetrics, trends: Dict[str, str]) -> List[str]:
        """Get performance recommendations."""
        recommendations = []
        
        if metrics.hit_rate < 0.7:
            recommendations.append("Consider increasing cache size or optimizing TTL settings")
        
        if metrics.memory_usage > 1000000000:  # 1GB
            recommendations.append("High memory usage - consider more aggressive eviction")
        
        if metrics.avg_access_time > 0.05:  # 50ms
            recommendations.append("Slow cache access - optimize cache structure")
        
        if trends.get('hit_rate') == 'declining':
            recommendations.append("Hit rate declining - investigate cache invalidation patterns")
        
        return recommendations
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of values."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def get_performance_summary(self, time_window: int = 3600) -> Dict[str, Any]:
        """Get performance summary for the specified time window.
        
        Args:
            time_window: Time window in seconds
            
        Returns:
            Performance summary dictionary
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - time_window
            
            # Filter metrics within time window
            recent_metrics = [
                m for m in self._metrics_history 
                if m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {'error': 'No metrics available for the specified time window'}
            
            # Calculate summary statistics
            hit_rates = [m.hit_rate for m in recent_metrics]
            access_times = [m.avg_access_time for m in recent_metrics]
            memory_usage = [m.memory_usage for m in recent_metrics]
            
            summary = {
                'time_window_hours': time_window / 3600,
                'total_requests': self._current_stats['total_requests'],
                'total_hits': self._current_stats['total_hits'],
                'total_misses': self._current_stats['total_misses'],
                'total_evictions': self._current_stats['total_evictions'],
                'overall_hit_rate': (
                    self._current_stats['total_hits'] / 
                    max(self._current_stats['total_requests'], 1)
                ),
                'recent_performance': {
                    'avg_hit_rate': sum(hit_rates) / len(hit_rates),
                    'min_hit_rate': min(hit_rates),
                    'max_hit_rate': max(hit_rates),
                    'avg_access_time': sum(access_times) / len(access_times),
                    'max_access_time': max(access_times),
                    'avg_memory_usage': sum(memory_usage) / len(memory_usage),
                    'max_memory_usage': max(memory_usage)
                },
                'data_type_breakdown': self._get_data_type_breakdown(cutoff_time),
                'recent_alerts': self._get_recent_alerts(cutoff_time),
                'uptime_hours': (current_time - self._current_stats['start_time']) / 3600
            }
            
            return summary
    
    def _get_data_type_breakdown(self, cutoff_time: float) -> Dict[str, Dict[str, float]]:
        """Get performance breakdown by data type."""
        breakdown = {}
        
        for data_type, metrics_list in self._data_type_metrics.items():
            recent_metrics = [
                m for m in metrics_list 
                if m.timestamp >= cutoff_time
            ]
            
            if recent_metrics:
                hit_rates = [m.hit_rate for m in recent_metrics]
                access_times = [m.avg_access_time for m in recent_metrics]
                
                breakdown[data_type] = {
                    'request_count': len(recent_metrics),
                    'avg_hit_rate': sum(hit_rates) / len(hit_rates),
                    'avg_access_time': sum(access_times) / len(access_times)
                }
        
        return breakdown
    
    def _get_recent_alerts(self, cutoff_time: float) -> List[Dict[str, Any]]:
        """Get recent alerts within the time window."""
        recent_alerts = [
            alert for alert in self._alerts_history 
            if alert.timestamp >= cutoff_time
        ]
        
        return [asdict(alert) for alert in recent_alerts]
    
    def export_metrics(self, filepath: str, time_window: int = 86400):
        """Export metrics to JSON file.
        
        Args:
            filepath: Output file path
            time_window: Time window in seconds (default: 24 hours)
        """
        summary = self.get_performance_summary(time_window)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Exported cache metrics to {filepath}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report with detailed analytics."""
        if not self._metrics_history:
            return {"error": "No metrics data available"}
        
        metrics_list = list(self._metrics_history)
        latest = metrics_list[-1] if metrics_list else None
        if not latest:
            return {"error": "No metrics data available"}
        
        # Calculate comprehensive trends and statistics
        trends = self._calculate_performance_trends()
        statistics = self._calculate_performance_statistics()
        recommendations = self._generate_performance_recommendations()
        
        return {
            "timestamp": latest.timestamp,
            "current_metrics": {
                "hit_rate": latest.hit_rate,
                "memory_usage_mb": getattr(latest, 'memory_usage', 0) / (1024 * 1024),
                "total_requests": self._current_stats['total_requests'],
                "avg_access_time": latest.avg_access_time,
                "eviction_rate": latest.eviction_rate,
                "cache_efficiency": self._calculate_cache_efficiency(latest),
                "throughput_per_second": self._calculate_throughput()
            },
            "trends": trends,
            "statistics": statistics,
            "recommendations": recommendations,
            "alerts": [
                {
                    "timestamp": alert.timestamp,
                    "level": alert.level,
                    "message": alert.message,
                    "metric": alert.metric_name,
                    "severity_score": self._calculate_alert_severity(alert)
                }
                for alert in list(self._alerts_history)[-10:]  # Last 10 alerts
            ],
            "health_score": self._calculate_overall_health_score()
        }

    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends over time."""
        if len(self._metrics_history) < 2:
            return {"insufficient_data": True}
        
        # Get time windows for analysis
        metrics_list = list(self._metrics_history)
        recent_window = metrics_list[-5:]  # Last 5 samples
        older_window = metrics_list[-10:-5] if len(metrics_list) >= 10 else metrics_list[:-5]
        
        if not older_window:
            older_window = [metrics_list[0]] if metrics_list else []
        
        # Calculate averages
        recent_avg = {
            'hit_rate': sum(m.hit_rate for m in recent_window) / len(recent_window),
            'memory_usage': sum(m.memory_usage for m in recent_window) / len(recent_window),
            'access_time': sum(m.avg_access_time for m in recent_window) / len(recent_window),
            'eviction_rate': sum(m.eviction_rate for m in recent_window) / len(recent_window)
        }
        
        older_avg = {
            'hit_rate': sum(m.hit_rate for m in older_window) / len(older_window),
            'memory_usage': sum(m.memory_usage for m in older_window) / len(older_window),
            'access_time': sum(m.avg_access_time for m in older_window) / len(older_window),
            'eviction_rate': sum(m.eviction_rate for m in older_window) / len(older_window)
        }
        
        return {
            'hit_rate_trend': recent_avg['hit_rate'] - older_avg['hit_rate'],
            'memory_trend': recent_avg['memory_usage'] - older_avg['memory_usage'],
            'access_time_trend': recent_avg['access_time'] - older_avg['access_time'],
            'eviction_rate_trend': recent_avg['eviction_rate'] - older_avg['eviction_rate'],
            'trend_direction': self._determine_overall_trend(recent_avg, older_avg)
        }
    
    def _calculate_performance_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance statistics."""
        if not self._metrics_history:
            return {}
        
        hit_rates = [m.hit_rate for m in self._metrics_history]
        memory_usage = [m.memory_usage for m in self._metrics_history]
        access_times = [m.avg_access_time for m in self._metrics_history]
        
        return {
            'hit_rate_stats': {
                'min': min(hit_rates),
                'max': max(hit_rates),
                'avg': sum(hit_rates) / len(hit_rates),
                'std_dev': self._calculate_std_dev(hit_rates)
            },
            'memory_stats': {
                'min': min(memory_usage),
                'max': max(memory_usage),
                'avg': sum(memory_usage) / len(memory_usage),
                'std_dev': self._calculate_std_dev(memory_usage)
            },
            'access_time_stats': {
                'min': min(access_times),
                'max': max(access_times),
                'avg': sum(access_times) / len(access_times),
                'std_dev': self._calculate_std_dev(access_times)
            },
            'total_samples': len(self._metrics_history),
            'monitoring_duration_hours': (list(self._metrics_history)[-1].timestamp - list(self._metrics_history)[0].timestamp) / 3600 if len(self._metrics_history) > 1 else 0
        }
    
    def _generate_performance_recommendations(self) -> List[Dict[str, Any]]:
        """Generate intelligent performance recommendations."""
        if not self._metrics_history:
            return [{"type": "info", "message": "No performance data available for recommendations"}]
        
        recommendations = []
        metrics_list = list(self._metrics_history)
        latest = metrics_list[-1] if metrics_list else None
        if not latest:
            return [{"type": "info", "message": "No performance data available for recommendations"}]
        trends = self._calculate_performance_trends()
        
        # Hit rate analysis
        if latest.hit_rate < 0.7:
            severity = "high" if latest.hit_rate < 0.5 else "medium"
            recommendations.append({
                "type": "optimization",
                "severity": severity,
                "message": f"Low hit rate ({latest.hit_rate:.1%}). Consider increasing cache size or optimizing TTL settings.",
                "action": "increase_cache_size"
            })
        
        # Memory usage analysis
        if latest.memory_usage > 1000000000:  # 1GB
            recommendations.append({
                "type": "resource",
                "severity": "medium",
                "message": f"High memory usage ({latest.memory_usage/1000000:.1f}MB). Consider implementing more aggressive eviction policies.",
                "action": "optimize_eviction"
            })
        
        # Access time analysis
        if latest.avg_access_time > 0.05:  # 50ms threshold
            recommendations.append({
                "type": "performance",
                "severity": "medium",
                "message": f"Slow cache access ({latest.avg_access_time*1000:.1f}ms). Consider optimizing cache structure.",
                "action": "optimize_structure"
            })
        
        # Trend-based recommendations
        if not trends.get('insufficient_data'):
            if trends['hit_rate_trend'] < -0.1:
                recommendations.append({
                    "type": "trend",
                    "severity": "high",
                    "message": "Hit rate is declining. Investigate cache invalidation patterns.",
                    "action": "investigate_invalidation"
                })
        
        return recommendations if recommendations else [{"type": "info", "message": "Cache performance is optimal"}]
    
    def _calculate_cache_efficiency(self, metrics: CacheMetrics) -> float:
        """Calculate overall cache efficiency score (0-1)."""
        hit_rate_score = metrics.hit_rate
        memory_efficiency = max(0, 1 - (metrics.memory_usage / 2000000000))  # Assume 2GB max
        speed_score = max(0, 1 - (metrics.avg_access_time / 0.1))  # 100ms baseline
        
        return (hit_rate_score * 0.5 + memory_efficiency * 0.3 + speed_score * 0.2)
    
    def _calculate_throughput(self) -> float:
        """Calculate current throughput (requests per second)."""
        if len(self._metrics_history) < 2:
            return 0.0
        
        metrics_list = list(self._metrics_history)
        latest = metrics_list[-1]
        previous = metrics_list[-2]
        time_diff = latest.timestamp - previous.timestamp
        request_diff = self._current_stats['total_requests'] - (self._current_stats['total_requests'] - 1)
        
        return request_diff / time_diff if time_diff > 0 else 0.0
    
    def _calculate_alert_severity(self, alert: CacheAlert) -> int:
        """Calculate numeric severity score for alert (1-10)."""
        severity_map = {
            'INFO': 2,
            'WARNING': 5,
            'ERROR': 8,
            'CRITICAL': 10
        }
        return severity_map.get(alert.level, 1)
    
    def _calculate_overall_health_score(self) -> float:
        """Calculate overall cache health score (0-100)."""
        if not self._metrics_history:
            return 0.0
        
        latest = self._metrics_history[-1]
        efficiency = self._calculate_cache_efficiency(latest)
        
        # Penalty for recent alerts
        recent_alerts = [a for a in self._alerts_history if time.time() - a.timestamp < 3600]  # Last hour
        alert_penalty = min(0.3, len(recent_alerts) * 0.05)
        
        return max(0, (efficiency - alert_penalty)) * 100
    
    def _determine_overall_trend(self, recent: Dict, older: Dict) -> str:
        """Determine overall performance trend direction."""
        improvements = 0
        degradations = 0
        
        if recent['hit_rate'] > older['hit_rate']:
            improvements += 1
        elif recent['hit_rate'] < older['hit_rate']:
            degradations += 1
            
        if recent['access_time'] < older['access_time']:
            improvements += 1
        elif recent['access_time'] > older['access_time']:
            degradations += 1
        
        if improvements > degradations:
            return "improving"
        elif degradations > improvements:
            return "degrading"
        else:
            return "stable"
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation of values."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get cache optimization recommendations based on performance data."""
        recommendations = self._generate_performance_recommendations()
        return [rec['message'] for rec in recommendations]
    
    async def start(self, interval: int = 60):
        """Alias for start_monitoring for compatibility."""
        await self.start_monitoring(interval)
    
    async def stop(self):
        """Alias for stop_monitoring for compatibility."""
        await self.stop_monitoring()