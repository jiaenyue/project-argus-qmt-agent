"""Enhanced Cache Dashboard Core Implementation.

This module contains the main EnhancedCacheDashboard class with all its functionality.
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import asdict

from .dashboard_types import ChartDataPoint, TrendAnalysis, PerformanceComparison

logger = logging.getLogger(__name__)


class EnhancedCacheDashboard:
    """Enhanced cache dashboard with real-time charts and analytics."""
    
    def __init__(self, cache_manager, cache_monitor):
        """Initialize the enhanced cache dashboard.
        
        Args:
            cache_manager: Cache manager instance
            cache_monitor: Cache performance monitor instance
        """
        self.cache_manager = cache_manager
        self.cache_monitor = cache_monitor
        
        # Chart data storage
        self._chart_data: Dict[str, List[ChartDataPoint]] = {
            'hit_rate': [],
            'memory_usage': [],
            'entry_count': [],
            'evictions': [],
            'response_time': []
        }
        
        # Trend analysis cache
        self._trend_cache: Dict[str, TrendAnalysis] = {}
        self._trend_cache_time = 0
        self._trend_cache_ttl = 300  # 5 minutes
        
        # Performance comparison cache
        self._comparison_cache: Dict[str, PerformanceComparison] = {}
        self._comparison_cache_time = 0
        self._comparison_cache_ttl = 300  # 5 minutes
        
        # Dashboard configuration
        self._max_data_points = 1000
        self._update_interval = 30  # seconds
        self._real_time_enabled = False
        self._update_task = None
        self._update_active = False
    
    async def start_real_time_updates(self):
        """Start real-time dashboard updates."""
        if self._real_time_enabled:
            return
        
        self._real_time_enabled = True
        self._update_active = True
        self._update_task = asyncio.create_task(self._update_chart_data_loop())
        logger.info("Real-time dashboard updates started")
    
    async def _update_chart_data_loop(self):
        """Main loop for updating chart data."""
        while self._update_active:
            try:
                await self._update_chart_data()
                await asyncio.sleep(self._update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in chart data update loop: {e}")
                await asyncio.sleep(self._update_interval)
    
    async def _update_chart_data(self):
        """Update chart data with current metrics."""
        try:
            current_time = time.time()
            cache_stats = self.cache_manager.get_stats()
            
            # Update chart data points
            metrics = {
                'hit_rate': getattr(cache_stats, 'hit_rate', 0) * 100,
                'memory_usage': getattr(cache_stats, 'memory_usage', 0) / (1024 * 1024),  # MB
                'entry_count': getattr(cache_stats, 'entry_count', 0),
                'evictions': getattr(cache_stats, 'evictions', 0),
                'response_time': getattr(cache_stats, 'avg_response_time', 0) * 1000  # ms
            }
            
            for metric_name, value in metrics.items():
                data_point = ChartDataPoint(
                    timestamp=current_time,
                    value=value,
                    label=self._get_metric_title(metric_name)
                )
                
                self._chart_data[metric_name].append(data_point)
                
                # Limit data points
                if len(self._chart_data[metric_name]) > self._max_data_points:
                    self._chart_data[metric_name] = self._chart_data[metric_name][-self._max_data_points:]
            
            # Clear caches to force refresh
            self._trend_cache_time = 0
            self._comparison_cache_time = 0
            
        except Exception as e:
            logger.error(f"Error updating chart data: {e}")
    
    def get_real_time_charts(self, metrics: List[str] = None) -> Dict[str, Any]:
        """Get real-time chart data for specified metrics.
        
        Args:
            metrics: List of metric names to include
            
        Returns:
            Dictionary with chart data for each metric
        """
        if metrics is None:
            metrics = list(self._chart_data.keys())
        
        charts = {}
        for metric_name in metrics:
            if metric_name in self._chart_data:
                data_points = self._chart_data[metric_name][-100:]  # Last 100 points
                
                charts[metric_name] = {
                    'title': self._get_metric_title(metric_name),
                    'unit': self._get_metric_unit(metric_name),
                    'color': self._get_metric_color(metric_name),
                    'data': [
                        {
                            'x': point.timestamp,
                            'y': point.value,
                            'label': point.label
                        }
                        for point in data_points
                    ],
                    'trend': self._calculate_simple_trend(data_points),
                    'latest_value': data_points[-1].value if data_points else 0
                }
        
        return {
            'charts': charts,
            'last_updated': time.time(),
            'update_interval': self._update_interval
        }
    
    def get_historical_trends(self, metrics: List[str] = None, 
                            analysis_window: int = 3600) -> Dict[str, TrendAnalysis]:
        """Get historical trend analysis for metrics.
        
        Args:
            metrics: List of metric names to analyze
            analysis_window: Time window for analysis in seconds
            
        Returns:
            Dictionary mapping metric names to trend analysis
        """
        # Check cache
        if (time.time() - self._trend_cache_time) < self._trend_cache_ttl and self._trend_cache:
            return self._trend_cache
        
        if metrics is None:
            metrics = list(self._chart_data.keys())
        
        trends = {}
        current_time = time.time()
        
        for metric_name in metrics:
            # Get data points within analysis window
            data_points = [
                point for point in self._chart_data.get(metric_name, [])
                if current_time - point.timestamp <= analysis_window
            ]
            
            if len(data_points) < 2:
                # Generate sample data for demonstration
                data_points = [
                    ChartDataPoint(current_time - 3600 + i * 300, 50 + i * 2, metric_name)
                    for i in range(12)
                ]
            
            trends[metric_name] = self._analyze_trend(metric_name, data_points)
        
        # Cache results
        self._trend_cache = trends
        self._trend_cache_time = current_time
        
        return trends
    
    def get_performance_comparison(self, current_period: int = 3600, 
                                 previous_period: int = 3600) -> Dict[str, Any]:
        """Get performance comparison between current and previous periods.
        
        Args:
            current_period: Current period duration in seconds
            previous_period: Previous period duration in seconds
            
        Returns:
            Performance comparison data
        """
        # Check cache
        if (time.time() - self._comparison_cache_time) < self._comparison_cache_ttl and self._comparison_cache:
            return {
                'comparisons': self._comparison_cache,
                'current_period_hours': current_period / 3600,
                'previous_period_hours': previous_period / 3600,
                'generated_at': self._comparison_cache_time
            }
        
        current_time = time.time()
        comparisons = {}
        
        for metric_name in self._chart_data.keys():
            # Get current period data
            current_data = [
                point.value for point in self._chart_data[metric_name]
                if current_time - point.timestamp <= current_period
            ]
            
            # Get previous period data
            previous_start = current_time - current_period - previous_period
            previous_end = current_time - current_period
            previous_data = [
                point.value for point in self._chart_data[metric_name]
                if previous_start <= current_time - point.timestamp <= previous_end
            ]
            
            # Generate sample data if no real data available
            if not current_data:
                current_data = [50 + i for i in range(10)]
            if not previous_data:
                previous_data = [45 + i for i in range(10)]
            
            comparisons[metric_name] = self._compare_periods(
                metric_name, current_data, previous_data
            )
        
        # Cache results
        self._comparison_cache = comparisons
        self._comparison_cache_time = current_time
        
        return {
            'comparisons': comparisons,
            'current_period_hours': current_period / 3600,
            'previous_period_hours': previous_period / 3600,
            'generated_at': current_time
        }
    
    def get_comprehensive_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data including all components.
        
        Returns:
            Complete dashboard data
        """
        return {
            'real_time_charts': self.get_real_time_charts(),
            'historical_trends': self.get_historical_trends(),
            'performance_comparison': self.get_performance_comparison(),
            'cache_health': self._get_cache_health_summary(),
            'system_status': self._get_system_status(),
            'smart_recommendations': self._get_smart_recommendations(),
            'generated_at': time.time()
        }
    
    def _analyze_trend(self, metric_name: str, data_points: List[ChartDataPoint]) -> TrendAnalysis:
        """Analyze trend for a specific metric.
        
        Args:
            metric_name: Name of the metric
            data_points: List of data points
            
        Returns:
            Trend analysis result
        """
        if len(data_points) < 2:
            return TrendAnalysis(
                metric_name=metric_name,
                trend_direction='stable',
                trend_strength=0,
                change_percentage=0,
                prediction=0,
                confidence=0
            )
        
        values = [point.value for point in data_points]
        timestamps = [point.timestamp for point in data_points]
        
        # Calculate linear regression
        n = len(values)
        sum_x = sum(timestamps)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(timestamps, values))
        sum_x2 = sum(x * x for x in timestamps)
        
        # Slope calculation
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            slope = 0
        else:
            slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Determine trend direction and strength
        first_value = values[0] if values[0] != 0 else 1
        last_value = values[-1]
        change_percentage = ((last_value - first_value) / abs(first_value)) * 100
        
        # Trend strength based on R-squared
        mean_y = sum_y / n
        ss_tot = sum((y - mean_y) ** 2 for y in values)
        if ss_tot == 0:
            r_squared = 1.0
        else:
            ss_res = sum((values[i] - (slope * timestamps[i] + (sum_y - slope * sum_x) / n)) ** 2 
                        for i in range(n))
            r_squared = 1 - (ss_res / ss_tot)
        
        # Determine trend direction
        if abs(change_percentage) < 5:
            direction = 'stable'
        elif change_percentage > 0:
            direction = 'improving' if self._is_improvement_metric(metric_name) else 'declining'
        else:
            direction = 'declining' if self._is_improvement_metric(metric_name) else 'improving'
        
        return TrendAnalysis(
            metric_name=metric_name,
            trend_direction=direction,
            trend_strength=max(0, min(1, r_squared)),
            change_percentage=change_percentage,
            prediction=self._predict_next_value(timestamps, values, slope),
            confidence=r_squared
        )
    
    def _compare_periods(self, metric_name: str, current_data: List[float], 
                        previous_data: List[float]) -> PerformanceComparison:
        """Compare performance between two periods.
        
        Args:
            metric_name: Name of the metric
            current_data: Current period data
            previous_data: Previous period data
            
        Returns:
            Performance comparison result
        """
        current_avg = sum(current_data) / len(current_data)
        previous_avg = sum(previous_data) / len(previous_data)
        
        if previous_avg == 0:
            improvement_percentage = 0
        else:
            improvement_percentage = ((current_avg - previous_avg) / abs(previous_avg)) * 100
        
        # Determine status
        if abs(improvement_percentage) < 2:
            status = 'stable'
        elif improvement_percentage > 0:
            status = 'improved' if self._is_improvement_metric(metric_name) else 'degraded'
        else:
            status = 'degraded' if self._is_improvement_metric(metric_name) else 'improved'
        
        return PerformanceComparison(
            metric_name=metric_name,
            current_period={
                'average': current_avg,
                'min': min(current_data),
                'max': max(current_data),
                'count': len(current_data)
            },
            previous_period={
                'average': previous_avg,
                'min': min(previous_data),
                'max': max(previous_data),
                'count': len(previous_data)
            },
            improvement_percentage=improvement_percentage,
            status=status
        )
    
    def _get_cache_health_summary(self) -> Dict[str, Any]:
        """Get cache health summary."""
        try:
            performance_summary = self.cache_monitor.get_performance_summary(1)
            recent_alerts = self.cache_monitor._get_recent_alerts(10)
            
            # Calculate health score
            hit_rate = performance_summary.get('overall_hit_rate', 0)
            alert_count = len(recent_alerts)
            
            health_score = max(0, min(100, 
                hit_rate * 100 - alert_count * 10
            ))
            
            return {
                'health_score': health_score,
                'status': self._get_health_status(health_score),
                'hit_rate': hit_rate,
                'alert_count': alert_count,
                'uptime_hours': performance_summary.get('uptime_hours', 0)
            }
        except Exception as e:
            logger.error(f"Error getting cache health summary: {e}")
            return {
                'health_score': 0,
                'status': 'unknown',
                'hit_rate': 0,
                'alert_count': 0,
                'uptime_hours': 0
            }
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get system status information."""
        return {
            'monitoring_active': getattr(self.cache_monitor, '_monitoring_active', False),
            'dashboard_active': True,
            'last_update': time.time(),
            'chart_data_points': sum(len(data) for data in self._chart_data.values()),
            'trend_cache_valid': (time.time() - self._trend_cache_time) < self._trend_cache_ttl
        }
    
    def _get_smart_recommendations(self) -> List[Dict[str, Any]]:
        """Get smart recommendations based on current performance."""
        recommendations = []
        
        try:
            trends = self.get_historical_trends()
            comparisons = self.get_performance_comparison()
            
            # Analyze trends for recommendations
            for metric_name, trend in trends.items():
                if trend.trend_direction == 'declining' and trend.trend_strength > 0.7:
                    recommendations.append({
                        'type': 'performance_warning',
                        'metric': metric_name,
                        'message': f"{metric_name} is declining with {trend.change_percentage:.1f}% change",
                        'priority': 'high' if abs(trend.change_percentage) > 20 else 'medium',
                        'action': self._get_metric_recommendation(metric_name, 'declining')
                    })
            
            # Analyze comparisons for recommendations
            comparison_data = comparisons.get('comparisons', {})
            for metric_name, comparison in comparison_data.items():
                if comparison.status == 'degraded' and abs(comparison.improvement_percentage) > 10:
                    recommendations.append({
                        'type': 'performance_degradation',
                        'metric': metric_name,
                        'message': f"{metric_name} degraded by {abs(comparison.improvement_percentage):.1f}%",
                        'priority': 'high',
                        'action': self._get_metric_recommendation(metric_name, 'degraded')
                    })
        
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    # Helper methods
    def _get_metric_title(self, metric_name: str) -> str:
        """Get display title for metric."""
        titles = {
            'hit_rate': 'Cache Hit Rate (%)',
            'memory_usage': 'Memory Usage (MB)',
            'entry_count': 'Cache Entries',
            'evictions': 'Cache Evictions',
            'response_time': 'Response Time (ms)'
        }
        return titles.get(metric_name, metric_name.replace('_', ' ').title())
    
    def _get_metric_unit(self, metric_name: str) -> str:
        """Get unit for metric."""
        units = {
            'hit_rate': '%',
            'memory_usage': 'MB',
            'entry_count': 'count',
            'evictions': 'count',
            'response_time': 'ms'
        }
        return units.get(metric_name, '')
    
    def _get_metric_color(self, metric_name: str) -> str:
        """Get color for metric chart."""
        colors = {
            'hit_rate': '#4CAF50',
            'memory_usage': '#FF9800',
            'entry_count': '#2196F3',
            'evictions': '#F44336',
            'response_time': '#9C27B0'
        }
        return colors.get(metric_name, '#607D8B')
    
    def _calculate_simple_trend(self, data_points: List[ChartDataPoint]) -> str:
        """Calculate simple trend direction."""
        if len(data_points) < 2:
            return 'stable'
        
        first_half = data_points[:len(data_points)//2]
        second_half = data_points[len(data_points)//2:]
        
        first_avg = sum(p.value for p in first_half) / len(first_half)
        second_avg = sum(p.value for p in second_half) / len(second_half)
        
        if abs(second_avg - first_avg) < 0.1:
            return 'stable'
        elif second_avg > first_avg:
            return 'up'
        else:
            return 'down'
    
    def _is_improvement_metric(self, metric_name: str) -> bool:
        """Check if higher values mean improvement for this metric."""
        improvement_metrics = {'hit_rate'}
        return metric_name in improvement_metrics
    
    def _predict_next_value(self, timestamps: List[float], values: List[float], slope: float) -> float:
        """Predict next value based on trend."""
        if not timestamps or not values:
            return 0
        
        last_timestamp = timestamps[-1]
        next_timestamp = last_timestamp + 300  # 5 minutes ahead
        
        # Simple linear prediction
        intercept = sum(values) / len(values) - slope * sum(timestamps) / len(timestamps)
        prediction = slope * next_timestamp + intercept
        
        return max(0, prediction)  # Ensure non-negative
    
    def _get_health_status(self, health_score: float) -> str:
        """Get health status based on score."""
        if health_score >= 80:
            return 'excellent'
        elif health_score >= 60:
            return 'good'
        elif health_score >= 40:
            return 'fair'
        elif health_score >= 20:
            return 'poor'
        else:
            return 'critical'
    
    def _get_metric_recommendation(self, metric_name: str, issue_type: str) -> str:
        """Get recommendation for metric issue."""
        recommendations = {
            'hit_rate': {
                'declining': 'Consider adjusting TTL settings or preloading strategies',
                'degraded': 'Review cache size limits and eviction policies'
            },
            'memory_usage': {
                'declining': 'Monitor for memory leaks or inefficient caching',
                'degraded': 'Consider increasing cache size or optimizing data structures'
            },
            'response_time': {
                'declining': 'Check for network issues or database performance',
                'degraded': 'Optimize cache lookup algorithms or increase cache levels'
            }
        }
        
        return recommendations.get(metric_name, {}).get(issue_type, 'Monitor and investigate further')
    
    def get_chart_data(self, metric_type: str = None, time_range: int = 3600, metric: str = None, time_window: int = None, metrics: List[str] = None) -> Dict[str, Any]:
        """Get chart data for specified metrics.
        
        Args:
            metric_type: 指标类型 (如 'hit_rate', 'memory_usage', 'response_time')
            time_range: 时间范围（秒）
            metric: 指标名称（向后兼容）
            time_window: 时间窗口（向后兼容）
            metrics: List of metric names to retrieve
            
        Returns:
            Dictionary mapping metric names to chart data points or chart data
        """
        try:
            # 参数兼容性处理
            if metrics:
                # Original behavior for multiple metrics
                chart_data = {}
                time_span = time_window or 3600
                
                for metric_name in metrics:
                    if metric_name in self._chart_data:
                        # Filter data points within time window
                        current_time = time.time()
                        filtered_data = [
                            point for point in self._chart_data[metric_name]
                            if current_time - point.timestamp <= time_span
                        ]
                        chart_data[metric_name] = filtered_data
                    else:
                        chart_data[metric_name] = []
                
                return chart_data
            else:
                # Single metric behavior
                metric_name = metric_type or metric or 'hit_rate'
                time_span = time_range or time_window or 3600
                
                # Get cache statistics
                cache_stats = self.cache_manager.get_stats()
                
                # 根据指标类型返回相应数据
                current_time = time.time()
                if metric_name == 'hit_rate':
                    return {
                        'labels': ['Current'],
                        'values': [getattr(cache_stats, 'hit_rate', 0)],
                        'timestamps': [current_time],
                        'type': 'line'
                    }
                elif metric_name == 'memory_usage':
                    return {
                        'labels': ['Current'],
                        'values': [getattr(cache_stats, 'memory_usage', 0)],
                        'timestamps': [current_time],
                        'type': 'bar'
                    }
                elif metric_name == 'response_time':
                    return {
                        'labels': ['Current'],
                        'values': [getattr(cache_stats, 'avg_response_time', 0)],
                        'timestamps': [current_time],
                        'type': 'line'
                    }
                else:
                    return {
                        'labels': [],
                        'values': [],
                        'timestamps': [],
                        'type': 'line'
                    }
                    
        except Exception as e:
            logger.error(f"Error getting chart data: {e}")
            return {
                'labels': [],
                'values': [],
                'type': 'line'
            }
    
    async def stop_real_time_updates(self):
        """Stop real-time dashboard updates."""
        try:
            # 停止实时更新任务
            if hasattr(self, '_update_task') and self._update_task:
                self._update_task.cancel()
                self._update_task = None
            
            # 重置更新标志
            if hasattr(self, '_real_time_enabled'):
                self._real_time_enabled = False
            
            if hasattr(self, '_update_active'):
                self._update_active = False
            
            logger.info("Real-time dashboard updates stopped")
            
        except Exception as e:
            logger.error(f"Error stopping real-time updates: {e}")
    
    def export_dashboard_data(self, filename: Optional[str] = None, format_type: str = 'json') -> str:
        """Export comprehensive dashboard data to file.
        
        Args:
            filename: Optional filename, auto-generated if not provided
            format_type: Export format ('json' or 'csv')
            
        Returns:
            Path to exported file or exported data as string
        """
        if filename is None:
            timestamp = int(time.time())
            extension = 'json' if format_type == 'json' else 'csv'
            filename = f"enhanced_dashboard_{timestamp}.{extension}"
        
        dashboard_data = self.get_comprehensive_dashboard()
        
        if format_type == 'json':
            # Convert dataclasses to dictionaries for JSON serialization
            def convert_dataclass(obj):
                if hasattr(obj, '__dataclass_fields__'):
                    return asdict(obj)
                elif isinstance(obj, dict):
                    return {k: convert_dataclass(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_dataclass(item) for item in obj]
                else:
                    return obj
            
            serializable_data = convert_dataclass(dashboard_data)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        elif format_type == 'csv':
            # Export as CSV format
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Metric', 'Value', 'Timestamp'])
                
                # Write basic metrics
                for key, value in dashboard_data.get('metrics', {}).items():
                    writer.writerow([key, value, time.time()])
        
        logger.info(f"Enhanced dashboard data exported to {filename}")
        return filename