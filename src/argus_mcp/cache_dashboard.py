"""Argus MCP Server - Cache Performance Dashboard.

This module provides a real-time cache performance monitoring dashboard.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import asdict

from .cache_monitor import cache_monitor, CacheMetrics, CacheAlert
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


class CacheDashboard:
    """Real-time cache performance dashboard."""
    
    def __init__(self, cache_manager: CacheManager, update_interval: int = 5):
        """Initialize cache dashboard.
        
        Args:
            cache_manager: Cache manager instance
            update_interval: Dashboard update interval in seconds
        """
        self.cache_manager = cache_manager
        self.update_interval = update_interval
        self._is_running = False
        self._dashboard_task: Optional[asyncio.Task] = None
        
        # Dashboard state
        self._current_dashboard_data = {}
        self._alert_history = []
        self._performance_history = []
        
    async def start_dashboard(self):
        """Start the real-time dashboard."""
        if self._is_running:
            logger.warning("Cache dashboard is already running")
            return
        
        self._is_running = True
        self._dashboard_task = asyncio.create_task(self._dashboard_loop())
        logger.info(f"Started cache performance dashboard (update interval: {self.update_interval}s)")
    
    async def stop_dashboard(self):
        """Stop the dashboard."""
        if not self._is_running:
            return
        
        self._is_running = False
        if self._dashboard_task:
            self._dashboard_task.cancel()
            try:
                await self._dashboard_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped cache performance dashboard")
    
    async def _dashboard_loop(self):
        """Main dashboard update loop."""
        while self._is_running:
            try:
                await self._update_dashboard_data()
                await self._check_performance_alerts()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in dashboard loop: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def _update_dashboard_data(self):
        """Update dashboard data with current metrics."""
        try:
            # Get current cache stats
            cache_stats = self.cache_manager.get_stats()
            
            # Get performance summary
            performance_summary = cache_monitor.get_performance_summary(3600)  # Last hour
            
            # Get performance report
            performance_report = cache_monitor.get_performance_report()
            
            # Calculate real-time metrics
            current_time = time.time()
            real_time_metrics = {
                'timestamp': current_time,
                'cache_stats': {
                    'hits': getattr(cache_stats, 'hits', 0),
                    'misses': getattr(cache_stats, 'misses', 0),
                    'hit_rate': getattr(cache_stats, 'hit_rate', 0.0),
                    'memory_usage_mb': getattr(cache_stats, 'memory_usage', 0) / (1024 * 1024),
                    'entry_count': getattr(cache_stats, 'entry_count', 0),
                    'evictions': getattr(cache_stats, 'evictions', 0)
                },
                'performance_metrics': performance_summary,
                'health_score': performance_report.get('health_score', 0),
                'alerts_count': len([a for a in cache_monitor._alerts_history 
                                   if current_time - a.timestamp < 3600]),
                'trends': performance_report.get('trends', {}),
                'recommendations': performance_report.get('recommendations', [])
            }
            
            self._current_dashboard_data = real_time_metrics
            self._performance_history.append(real_time_metrics)
            
            # Keep only last 100 entries
            if len(self._performance_history) > 100:
                self._performance_history = self._performance_history[-100:]
            
            # Log dashboard update
            logger.debug(f"Dashboard updated - Hit Rate: {cache_stats.hit_rate:.1%}, "
                        f"Health Score: {real_time_metrics['health_score']:.1f}")
            
        except Exception as e:
            logger.error(f"Error updating dashboard data: {e}")
    
    async def _check_performance_alerts(self):
        """Check for performance alerts and update alert history."""
        try:
            current_time = time.time()
            
            # Get recent alerts from monitor
            recent_alerts = [
                alert for alert in cache_monitor._alerts_history
                if current_time - alert.timestamp < 300  # Last 5 minutes
            ]
            
            # Add new alerts to dashboard history
            for alert in recent_alerts:
                alert_dict = asdict(alert)
                alert_dict['dashboard_timestamp'] = current_time
                
                # Check if alert is already in history
                existing = any(
                    existing_alert.get('timestamp') == alert.timestamp and
                    existing_alert.get('metric_name') == alert.metric_name
                    for existing_alert in self._alert_history
                )
                
                if not existing:
                    self._alert_history.append(alert_dict)
            
            # Keep only last 50 alerts
            if len(self._alert_history) > 50:
                self._alert_history = self._alert_history[-50:]
            
        except Exception as e:
            logger.error(f"Error checking performance alerts: {e}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get current dashboard data."""
        return {
            'current_metrics': self._current_dashboard_data,
            'performance_history': self._performance_history[-20:],  # Last 20 entries
            'recent_alerts': self._alert_history[-10:],  # Last 10 alerts
            'dashboard_status': {
                'is_running': self._is_running,
                'update_interval': self.update_interval,
                'last_update': self._current_dashboard_data.get('timestamp', 0)
            }
        }
    
    def get_performance_trends(self, time_window: int = 3600) -> Dict[str, Any]:
        """Get performance trends for the specified time window.
        
        Args:
            time_window: Time window in seconds
            
        Returns:
            Performance trends data
        """
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        # Filter performance history
        recent_history = [
            entry for entry in self._performance_history
            if entry.get('timestamp', 0) >= cutoff_time
        ]
        
        if len(recent_history) < 2:
            return {'error': 'Insufficient data for trend analysis'}
        
        # Calculate trends
        hit_rates = [entry['cache_stats']['hit_rate'] for entry in recent_history]
        memory_usage = [entry['cache_stats']['memory_usage_mb'] for entry in recent_history]
        health_scores = [entry.get('health_score', 0) for entry in recent_history]
        
        return {
            'time_window_hours': time_window / 3600,
            'data_points': len(recent_history),
            'hit_rate_trend': {
                'current': hit_rates[-1] if hit_rates else 0,
                'average': sum(hit_rates) / len(hit_rates),
                'min': min(hit_rates),
                'max': max(hit_rates),
                'trend_direction': self._calculate_trend_direction(hit_rates)
            },
            'memory_trend': {
                'current_mb': memory_usage[-1] if memory_usage else 0,
                'average_mb': sum(memory_usage) / len(memory_usage),
                'min_mb': min(memory_usage),
                'max_mb': max(memory_usage),
                'trend_direction': self._calculate_trend_direction(memory_usage)
            },
            'health_trend': {
                'current': health_scores[-1] if health_scores else 0,
                'average': sum(health_scores) / len(health_scores),
                'min': min(health_scores),
                'max': max(health_scores),
                'trend_direction': self._calculate_trend_direction(health_scores)
            }
        }
    
    def _calculate_trend_direction(self, values: List[float]) -> str:
        """Calculate trend direction for a series of values."""
        if len(values) < 2:
            return 'stable'
        
        # Compare first half with second half
        mid_point = len(values) // 2
        first_half_avg = sum(values[:mid_point]) / mid_point
        second_half_avg = sum(values[mid_point:]) / (len(values) - mid_point)
        
        if first_half_avg == 0:
            diff_percentage = 0 if second_half_avg == 0 else 100
        else:
            diff_percentage = (second_half_avg - first_half_avg) / first_half_avg * 100
        
        if diff_percentage > 5:
            return 'increasing'
        elif diff_percentage < -5:
            return 'decreasing'
        else:
            return 'stable'
    
    def export_dashboard_report(self, filepath: str):
        """Export comprehensive dashboard report to JSON file.
        
        Args:
            filepath: Output file path
        """
        try:
            report_data = {
                'export_timestamp': time.time(),
                'export_date': datetime.now().isoformat(),
                'dashboard_data': self.get_dashboard_data(),
                'performance_trends': self.get_performance_trends(86400),  # 24 hours
                'cache_configuration': {
                    'update_interval': self.update_interval,
                    'monitoring_active': self._is_running
                },
                'summary': {
                    'total_performance_samples': len(self._performance_history),
                    'total_alerts': len(self._alert_history),
                    'current_health_score': self._current_dashboard_data.get('health_score', 0)
                }
            }
            
            with open(filepath, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            logger.info(f"Dashboard report exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting dashboard report: {e}")
            raise
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of recent alerts."""
        current_time = time.time()
        
        # Categorize alerts by level and time
        alert_summary = {
            'total_alerts': len(self._alert_history),
            'alerts_last_hour': len([
                alert for alert in self._alert_history
                if current_time - alert.get('timestamp', 0) < 3600
            ]),
            'alerts_by_level': {},
            'alerts_by_metric': {},
            'most_recent_alert': None
        }
        
        # Count by level
        for alert in self._alert_history:
            level = alert.get('level', 'UNKNOWN')
            alert_summary['alerts_by_level'][level] = alert_summary['alerts_by_level'].get(level, 0) + 1
        
        # Count by metric
        for alert in self._alert_history:
            metric = alert.get('metric_name', 'unknown')
            alert_summary['alerts_by_metric'][metric] = alert_summary['alerts_by_metric'].get(metric, 0) + 1
        
        # Get most recent alert
        if self._alert_history:
            alert_summary['most_recent_alert'] = self._alert_history[-1]
        
        return alert_summary


# Global dashboard instance
cache_dashboard = None


def get_cache_dashboard(cache_manager: CacheManager) -> CacheDashboard:
    """Get or create global cache dashboard instance."""
    global cache_dashboard
    if cache_dashboard is None:
        cache_dashboard = CacheDashboard(cache_manager)
    return cache_dashboard