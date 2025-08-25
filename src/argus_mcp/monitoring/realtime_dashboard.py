"""
实时监控仪表板

提供实时的性能监控和数据质量监控API
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import logging
import json
from collections import deque

from src.argus_mcp.monitoring.historical_performance_monitor import get_historical_performance_monitor
from src.argus_mcp.cache.intelligent_cache_strategy import get_intelligent_cache_strategy
from src.argus_mcp.optimization.batch_data_optimizer import get_batch_data_optimizer

logger = logging.getLogger(__name__)


@dataclass
class DashboardMetrics:
    """仪表板指标"""
    timestamp: str
    
    # API性能指标
    api_response_time: float
    api_success_rate: float
    api_error_rate: float
    requests_per_second: float
    
    # 缓存性能指标
    cache_hit_rate: float
    cache_size: int
    cache_memory_usage_mb: float
    
    # 数据质量指标
    data_quality_score: float
    validation_failures: int
    
    # 系统资源指标
    memory_usage_mb: float
    cpu_usage_percent: float
    
    # 热点数据指标
    hot_data_patterns_count: int
    top_symbols: List[str]
    top_periods: List[str]
    
    # 批量处理指标
    batch_queue_size: int
    batch_processing_active: bool
    batch_success_rate: float


class RealtimeDashboard:
    """实时监控仪表板"""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.metrics_history = deque(maxlen=history_size)
        
        # 监控组件
        self.performance_monitor = get_historical_performance_monitor()
        self.cache_strategy = get_intelligent_cache_strategy()
        self.batch_optimizer = get_batch_data_optimizer()
        
        # 实时数据收集
        self.is_collecting = False
        self.collection_interval = 5.0  # 5秒收集一次
        
        # 告警状态
        self.active_alerts = []
        self.alert_history = deque(maxlen=100)
        
        logger.info("Realtime dashboard initialized")
    
    async def start_monitoring(self) -> None:
        """开始实时监控"""
        if self.is_collecting:
            logger.warning("Monitoring already started")
            return
        
        self.is_collecting = True
        logger.info("Starting realtime monitoring")
        
        # 启动数据收集任务
        asyncio.create_task(self._collect_metrics_loop())
        asyncio.create_task(self._alert_monitoring_loop())
    
    async def stop_monitoring(self) -> None:
        """停止实时监控"""
        self.is_collecting = False
        logger.info("Stopped realtime monitoring")
    
    async def _collect_metrics_loop(self) -> None:
        """指标收集循环"""
        while self.is_collecting:
            try:
                metrics = await self._collect_current_metrics()
                self.metrics_history.append(metrics)
                
                # 检查告警条件
                await self._check_alerts(metrics)
                
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _alert_monitoring_loop(self) -> None:
        """告警监控循环"""
        while self.is_collecting:
            try:
                # 清理过期告警
                self._cleanup_expired_alerts()
                
                # 每30秒检查一次
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in alert monitoring: {e}")
                await asyncio.sleep(30)
    
    async def _collect_current_metrics(self) -> DashboardMetrics:
        """收集当前指标"""
        timestamp = datetime.now().isoformat()
        
        # 获取性能监控数据
        performance_summary = self.performance_monitor.get_performance_summary()
        
        # 获取缓存策略数据
        cache_stats = self.cache_strategy.get_cache_strategy_stats()
        
        # 获取批量处理数据
        batch_status = await self.batch_optimizer.get_queue_status()
        
        # 获取热点数据推荐
        hot_data = self.cache_strategy.get_hot_data_recommendations(5)
        
        return DashboardMetrics(
            timestamp=timestamp,
            
            # API性能指标
            api_response_time=performance_summary.get('response_time', {}).get('avg', 0),
            api_success_rate=performance_summary.get('success_rate', 0),
            api_error_rate=performance_summary.get('error_rate', 0),
            requests_per_second=self._calculate_rps(performance_summary),
            
            # 缓存性能指标
            cache_hit_rate=performance_summary.get('cache_performance', {}).get('hit_rate', 0),
            cache_size=0,  # 需要从缓存系统获取
            cache_memory_usage_mb=0,  # 需要从缓存系统获取
            
            # 数据质量指标
            data_quality_score=performance_summary.get('data_quality', {}).get('score', 0),
            validation_failures=performance_summary.get('data_quality', {}).get('validation_failures', 0),
            
            # 系统资源指标
            memory_usage_mb=self._get_memory_usage(),
            cpu_usage_percent=self._get_cpu_usage(),
            
            # 热点数据指标
            hot_data_patterns_count=cache_stats.get('hot_data_patterns_count', 0),
            top_symbols=[item['symbol'] for item in hot_data[:5]],
            top_periods=[item['period'] for item in hot_data[:5]],
            
            # 批量处理指标
            batch_queue_size=batch_status.get('queue_size', 0),
            batch_processing_active=batch_status.get('is_processing', False),
            batch_success_rate=batch_status.get('success_rate', 0)
        )
    
    def _calculate_rps(self, performance_summary: Dict[str, Any]) -> float:
        """计算每秒请求数"""
        total_requests = performance_summary.get('total_requests', 0)
        uptime = performance_summary.get('uptime', 1)
        
        if uptime > 0:
            return total_requests / uptime
        return 0.0
    
    def _get_memory_usage(self) -> float:
        """获取内存使用量"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            import psutil
            return psutil.cpu_percent(interval=None)
        except ImportError:
            return 0.0
    
    async def _check_alerts(self, metrics: DashboardMetrics) -> None:
        """检查告警条件"""
        alerts = []
        
        # 响应时间告警
        if metrics.api_response_time > 5.0:
            alerts.append({
                'type': 'high_response_time',
                'severity': 'warning',
                'message': f'API响应时间过高: {metrics.api_response_time:.2f}s',
                'value': metrics.api_response_time,
                'threshold': 5.0,
                'timestamp': metrics.timestamp
            })
        
        # 成功率告警
        if metrics.api_success_rate < 0.95:
            alerts.append({
                'type': 'low_success_rate',
                'severity': 'critical',
                'message': f'API成功率过低: {metrics.api_success_rate:.2%}',
                'value': metrics.api_success_rate,
                'threshold': 0.95,
                'timestamp': metrics.timestamp
            })
        
        # 缓存命中率告警
        if metrics.cache_hit_rate < 0.7:
            alerts.append({
                'type': 'low_cache_hit_rate',
                'severity': 'warning',
                'message': f'缓存命中率过低: {metrics.cache_hit_rate:.2%}',
                'value': metrics.cache_hit_rate,
                'threshold': 0.7,
                'timestamp': metrics.timestamp
            })
        
        # 内存使用告警
        if metrics.memory_usage_mb > 1000:  # 1GB
            alerts.append({
                'type': 'high_memory_usage',
                'severity': 'warning',
                'message': f'内存使用过高: {metrics.memory_usage_mb:.1f}MB',
                'value': metrics.memory_usage_mb,
                'threshold': 1000,
                'timestamp': metrics.timestamp
            })
        
        # 批量队列积压告警
        if metrics.batch_queue_size > 100:
            alerts.append({
                'type': 'high_queue_size',
                'severity': 'warning',
                'message': f'批量处理队列积压: {metrics.batch_queue_size}',
                'value': metrics.batch_queue_size,
                'threshold': 100,
                'timestamp': metrics.timestamp
            })
        
        # 更新活跃告警
        for alert in alerts:
            if not self._is_duplicate_alert(alert):
                self.active_alerts.append(alert)
                self.alert_history.append(alert)
                logger.warning(f"Alert triggered: {alert['message']}")
    
    def _is_duplicate_alert(self, new_alert: Dict[str, Any]) -> bool:
        """检查是否为重复告警"""
        for active_alert in self.active_alerts:
            if (active_alert['type'] == new_alert['type'] and
                active_alert['severity'] == new_alert['severity']):
                # 如果是同类型告警且在5分钟内，认为是重复
                alert_time = datetime.fromisoformat(active_alert['timestamp'])
                if datetime.now() - alert_time < timedelta(minutes=5):
                    return True
        return False
    
    def _cleanup_expired_alerts(self) -> None:
        """清理过期告警"""
        current_time = datetime.now()
        self.active_alerts = [
            alert for alert in self.active_alerts
            if current_time - datetime.fromisoformat(alert['timestamp']) < timedelta(minutes=30)
        ]
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        if not self.metrics_history:
            return {'error': 'No metrics data available'}
        
        latest_metrics = self.metrics_history[-1]
        return asdict(latest_metrics)
    
    async def get_metrics_history(
        self,
        minutes: int = 60,
        interval: int = 1
    ) -> List[Dict[str, Any]]:
        """获取历史指标"""
        if not self.metrics_history:
            return []
        
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=minutes)
        
        # 过滤时间范围内的数据
        filtered_metrics = []
        for metrics in self.metrics_history:
            metrics_time = datetime.fromisoformat(metrics.timestamp)
            if start_time <= metrics_time <= end_time:
                filtered_metrics.append(asdict(metrics))
        
        # 按间隔采样
        if interval > 1 and len(filtered_metrics) > interval:
            sampled_metrics = filtered_metrics[::interval]
            return sampled_metrics
        
        return filtered_metrics
    
    async def get_performance_trends(self) -> Dict[str, Any]:
        """获取性能趋势"""
        if len(self.metrics_history) < 10:
            return {'error': 'Insufficient data for trend analysis'}
        
        recent_metrics = list(self.metrics_history)[-60:]  # 最近60个数据点
        
        # 计算趋势
        response_times = [m.api_response_time for m in recent_metrics]
        success_rates = [m.api_success_rate for m in recent_metrics]
        cache_hit_rates = [m.cache_hit_rate for m in recent_metrics]
        
        return {
            'response_time_trend': self._calculate_trend(response_times),
            'success_rate_trend': self._calculate_trend(success_rates),
            'cache_hit_rate_trend': self._calculate_trend(cache_hit_rates),
            'data_points': len(recent_metrics),
            'time_range_minutes': len(recent_metrics) * (self.collection_interval / 60)
        }
    
    def _calculate_trend(self, values: List[float]) -> Dict[str, Any]:
        """计算趋势"""
        if len(values) < 2:
            return {'direction': 'stable', 'change_percent': 0.0}
        
        # 简单的线性趋势计算
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if first_avg == 0:
            change_percent = 0.0
        else:
            change_percent = ((second_avg - first_avg) / first_avg) * 100
        
        if abs(change_percent) < 5:
            direction = 'stable'
        elif change_percent > 0:
            direction = 'increasing'
        else:
            direction = 'decreasing'
        
        return {
            'direction': direction,
            'change_percent': change_percent,
            'first_half_avg': first_avg,
            'second_half_avg': second_avg
        }
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        return self.active_alerts.copy()
    
    async def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取告警历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert['timestamp']) >= cutoff_time
        ]
    
    async def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        if not self.metrics_history:
            return {'status': 'unknown', 'message': 'No metrics data available'}
        
        latest_metrics = self.metrics_history[-1]
        
        # 健康检查规则
        health_checks = {
            'api_performance': latest_metrics.api_response_time < 3.0 and latest_metrics.api_success_rate > 0.95,
            'cache_performance': latest_metrics.cache_hit_rate > 0.6,
            'system_resources': latest_metrics.memory_usage_mb < 2000 and latest_metrics.cpu_usage_percent < 80,
            'data_quality': latest_metrics.data_quality_score > 0.8,
            'batch_processing': latest_metrics.batch_queue_size < 200
        }
        
        # 计算整体健康状态
        healthy_checks = sum(health_checks.values())
        total_checks = len(health_checks)
        health_score = healthy_checks / total_checks
        
        if health_score >= 0.8:
            status = 'healthy'
            message = '系统运行正常'
        elif health_score >= 0.6:
            status = 'warning'
            message = '系统存在一些问题，需要关注'
        else:
            status = 'critical'
            message = '系统存在严重问题，需要立即处理'
        
        return {
            'status': status,
            'message': message,
            'health_score': health_score,
            'checks': health_checks,
            'active_alerts_count': len(self.active_alerts),
            'timestamp': latest_metrics.timestamp
        }
    
    async def generate_dashboard_report(self) -> Dict[str, Any]:
        """生成仪表板报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'current_metrics': await self.get_current_metrics(),
            'performance_trends': await self.get_performance_trends(),
            'system_health': await self.get_system_health(),
            'active_alerts': await self.get_active_alerts(),
            'monitoring_status': {
                'is_collecting': self.is_collecting,
                'collection_interval': self.collection_interval,
                'metrics_history_size': len(self.metrics_history),
                'alert_history_size': len(self.alert_history)
            }
        }


# 全局仪表板实例
_global_dashboard: Optional[RealtimeDashboard] = None

def get_realtime_dashboard() -> RealtimeDashboard:
    """获取全局实时仪表板"""
    global _global_dashboard
    if _global_dashboard is None:
        _global_dashboard = RealtimeDashboard()
    return _global_dashboard


# 便捷函数
async def start_dashboard_monitoring() -> None:
    """启动仪表板监控"""
    dashboard = get_realtime_dashboard()
    await dashboard.start_monitoring()


async def get_dashboard_data() -> Dict[str, Any]:
    """获取仪表板数据"""
    dashboard = get_realtime_dashboard()
    return await dashboard.generate_dashboard_report()


async def get_system_health_status() -> Dict[str, Any]:
    """获取系统健康状态"""
    dashboard = get_realtime_dashboard()
    return await dashboard.get_system_health()