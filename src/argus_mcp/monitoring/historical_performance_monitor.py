"""
历史数据性能监控系统

扩展现有性能优化器，专门监控历史数据API的性能指标
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging
import threading
from functools import wraps

from src.argus_mcp.exceptions.historical_data_exceptions import HistoricalDataException, ErrorCategory

logger = logging.getLogger(__name__)


@dataclass
class HistoricalPerformanceMetrics:
    """历史数据性能指标"""
    
    # API响应时间
    api_response_time: float = 0.0
    api_min_response_time: float = float('inf')
    api_max_response_time: float = 0.0
    api_avg_response_time: float = 0.0
    
    # 数据获取时间
    data_fetch_time: float = 0.0
    processing_time: float = 0.0
    cache_check_time: float = 0.0
    
    # 成功率统计
    success_count: int = 0
    error_count: int = 0
    total_requests: int = 0
    
    # 缓存性能
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    
    # 数据质量指标
    data_quality_score: float = 0.0
    validation_failures: int = 0
    
    # 按股票代码统计
    symbol_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # 按周期统计
    period_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # 错误分类统计
    error_categories: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class HistoricalPerformanceMonitor:
    """历史数据性能监控器"""
    
    def __init__(
        self,
        window_size: int = 1000,
        alert_thresholds: Optional[Dict[str, float]] = None,
        enable_auto_alerts: bool = True
    ):
        self.window_size = window_size
        self.enable_auto_alerts = enable_auto_alerts
        
        # 性能数据存储
        self.metrics_history = deque(maxlen=window_size)
        self.response_times = deque(maxlen=window_size)
        self.error_history = deque(maxlen=100)
        
        # 当前指标
        self.current_metrics = HistoricalPerformanceMetrics()
        
        # 告警阈值
        self.alert_thresholds = alert_thresholds or {
            'max_response_time': 5.0,
            'min_success_rate': 0.95,
            'min_cache_hit_rate': 0.7,
            'max_error_rate': 0.05
        }
        
        # 告警回调
        self.alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # 监控状态
        self.is_monitoring = False
        self._lock = threading.Lock()
        
        # 统计周期
        self.last_reset_time = datetime.now()
        
        logger.info("Historical performance monitor initialized")
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """添加告警回调"""
        self.alert_callbacks.append(callback)
    
    def start_monitoring(self) -> None:
        """开始监控"""
        self.is_monitoring = True
        logger.info("Historical performance monitoring started")
    
    def stop_monitoring(self) -> None:
        """停止监控"""
        self.is_monitoring = False
        logger.info("Historical performance monitoring stopped")
    
    def reset_metrics(self) -> None:
        """重置指标"""
        with self._lock:
            self.current_metrics = HistoricalPerformanceMetrics()
            self.last_reset_time = datetime.now()
        logger.info("Performance metrics reset")
    
    def record_api_call(
        self,
        symbol: str,
        period: str,
        response_time: float,
        success: bool,
        cache_hit: bool = False,
        error_category: Optional[str] = None,
        data_quality_score: float = 1.0
    ) -> None:
        """记录API调用"""
        with self._lock:
            self.current_metrics.total_requests += 1
            
            if success:
                self.current_metrics.success_count += 1
            else:
                self.current_metrics.error_count += 1
            
            # 更新响应时间
            self.current_metrics.api_response_time = response_time
            self.current_metrics.api_min_response_time = min(
                self.current_metrics.api_min_response_time, response_time
            )
            self.current_metrics.api_max_response_time = max(
                self.current_metrics.api_max_response_time, response_time
            )
            
            # 计算平均响应时间
            total_time = (
                self.current_metrics.api_avg_response_time * 
                (self.current_metrics.total_requests - 1) + response_time
            )
            self.current_metrics.api_avg_response_time = total_time / self.current_metrics.total_requests
            
            # 缓存统计
            if cache_hit:
                self.current_metrics.cache_hits += 1
            else:
                self.current_metrics.cache_misses += 1
            
            # 计算缓存命中率
            total_cache_ops = self.current_metrics.cache_hits + self.current_metrics.cache_misses
            if total_cache_ops > 0:
                self.current_metrics.cache_hit_rate = (
                    self.current_metrics.cache_hits / total_cache_ops
                )
            
            # 数据质量
            self.current_metrics.data_quality_score = data_quality_score
            
            # 按股票代码统计
            if symbol not in self.current_metrics.symbol_stats:
                self.current_metrics.symbol_stats[symbol] = {
                    'requests': 0, 'errors': 0, 'cache_hits': 0
                }
            
            symbol_stats = self.current_metrics.symbol_stats[symbol]
            symbol_stats['requests'] += 1
            if not success:
                symbol_stats['errors'] += 1
            if cache_hit:
                symbol_stats['cache_hits'] += 1
            
            # 按周期统计
            if period not in self.current_metrics.period_stats:
                self.current_metrics.period_stats[period] = {
                    'requests': 0, 'errors': 0, 'cache_hits': 0
                }
            
            period_stats = self.current_metrics.period_stats[period]
            period_stats['requests'] += 1
            if not success:
                period_stats['errors'] += 1
            if cache_hit:
                period_stats['cache_hits'] += 1
            
            # 错误分类
            if error_category:
                self.current_metrics.error_categories[error_category] += 1
                self.error_history.append({
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'period': period,
                    'error_category': error_category,
                    'response_time': response_time
                })
            
            # 检查告警
            self._check_alerts()
    
    def record_processing_time(self, processing_time: float) -> None:
        """记录处理时间"""
        with self._lock:
            self.current_metrics.processing_time = processing_time
    
    def record_data_fetch_time(self, fetch_time: float) -> None:
        """记录数据获取时间"""
        with self._lock:
            self.current_metrics.data_fetch_time = fetch_time
    
    def record_cache_check_time(self, check_time: float) -> None:
        """记录缓存检查时间"""
        with self._lock:
            self.current_metrics.cache_check_time = check_time
    
    def record_validation_failure(self) -> None:
        """记录验证失败"""
        with self._lock:
            self.current_metrics.validation_failures += 1
    
    def _check_alerts(self) -> None:
        """检查告警条件"""
        if not self.enable_auto_alerts:
            return
        
        alerts = []
        
        # 响应时间告警
        if self.current_metrics.api_avg_response_time > self.alert_thresholds['max_response_time']:
            alerts.append({
                'type': 'high_response_time',
                'value': self.current_metrics.api_avg_response_time,
                'threshold': self.alert_thresholds['max_response_time'],
                'severity': 'warning'
            })
        
        # 成功率告警
        success_rate = self.get_success_rate()
        if success_rate < self.alert_thresholds['min_success_rate']:
            alerts.append({
                'type': 'low_success_rate',
                'value': success_rate,
                'threshold': self.alert_thresholds['min_success_rate'],
                'severity': 'critical'
            })
        
        # 缓存命中率告警
        if self.current_metrics.cache_hit_rate < self.alert_thresholds['min_cache_hit_rate']:
            alerts.append({
                'type': 'low_cache_hit_rate',
                'value': self.current_metrics.cache_hit_rate,
                'threshold': self.alert_thresholds['min_cache_hit_rate'],
                'severity': 'warning'
            })
        
        # 错误率告警
        error_rate = self.get_error_rate()
        if error_rate > self.alert_thresholds['max_error_rate']:
            alerts.append({
                'type': 'high_error_rate',
                'value': error_rate,
                'threshold': self.alert_thresholds['max_error_rate'],
                'severity': 'critical'
            })
        
        # 触发告警回调
        for alert in alerts:
            self._trigger_alert(alert['type'], alert)
    
    def _trigger_alert(self, alert_type: str, alert_data: Dict[str, Any]) -> None:
        """触发告警"""
        for callback in self.alert_callbacks:
            try:
                callback(alert_type, alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.current_metrics.total_requests == 0:
            return 1.0
        return self.current_metrics.success_count / self.current_metrics.total_requests
    
    def get_error_rate(self) -> float:
        """获取错误率"""
        if self.current_metrics.total_requests == 0:
            return 0.0
        return self.current_metrics.error_count / self.current_metrics.total_requests
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        with self._lock:
            return {
                'timestamp': datetime.now().isoformat(),
                'uptime': (datetime.now() - self.last_reset_time).total_seconds(),
                'total_requests': self.current_metrics.total_requests,
                'success_rate': self.get_success_rate(),
                'error_rate': self.get_error_rate(),
                'response_time': {
                    'avg': self.current_metrics.api_avg_response_time,
                    'min': self.current_metrics.api_min_response_time,
                    'max': self.current_metrics.api_max_response_time
                },
                'cache_performance': {
                    'hit_rate': self.current_metrics.cache_hit_rate,
                    'hits': self.current_metrics.cache_hits,
                    'misses': self.current_metrics.cache_misses
                },
                'data_quality': {
                    'score': self.current_metrics.data_quality_score,
                    'validation_failures': self.current_metrics.validation_failures
                },
                'top_symbols': dict(list(self.current_metrics.symbol_stats.items())[:10]),
                'top_periods': dict(list(self.current_metrics.period_stats.items())[:10]),
                'error_breakdown': dict(self.current_metrics.error_categories),
                'alerts': {
                    'thresholds': self.alert_thresholds,
                    'current_status': self._get_alert_status()
                }
            }
    
    def _get_alert_status(self) -> Dict[str, bool]:
        """获取告警状态"""
        return {
            'high_response_time': self.current_metrics.api_avg_response_time > self.alert_thresholds['max_response_time'],
            'low_success_rate': self.get_success_rate() < self.alert_thresholds['min_success_rate'],
            'low_cache_hit_rate': self.current_metrics.cache_hit_rate < self.alert_thresholds['min_cache_hit_rate'],
            'high_error_rate': self.get_error_rate() > self.alert_thresholds['max_error_rate']
        }
    
    def get_detailed_metrics(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """获取详细指标"""
        with self._lock:
            if symbol:
                return self.current_metrics.symbol_stats.get(symbol, {})
            else:
                return {
                    'symbol_stats': self.current_metrics.symbol_stats,
                    'period_stats': self.current_metrics.period_stats,
                    'error_history': list(self.error_history)[-50:],
                    'performance_trend': self._calculate_performance_trend()
                }
    
    def _calculate_performance_trend(self) -> Dict[str, List[float]]:
        """计算性能趋势"""
        if len(self.response_times) < 10:
            return {'response_times': [], 'success_rates': []}
        
        # 简单的滑动平均计算
        recent_times = list(self.response_times)[-20:]
        return {
            'response_times': recent_times,
            'success_rates': [self.get_success_rate()] * len(recent_times)
        }


# 全局监控器实例
_global_monitor: Optional[HistoricalPerformanceMonitor] = None

def get_historical_performance_monitor() -> HistoricalPerformanceMonitor:
    """获取全局历史数据性能监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = HistoricalPerformanceMonitor()
    return _global_monitor


def monitor_performance(
    symbol_param: str = 'symbol',
    period_param: str = 'period'
):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor = get_historical_performance_monitor()
            
            if not monitor.is_monitoring:
                monitor.start_monitoring()
            
            start_time = time.time()
            symbol = kwargs.get(symbol_param, args[0] if args else 'unknown')
            period = kwargs.get(period_param, 'unknown')
            
            try:
                result = await func(*args, **kwargs)
                
                end_time = time.time()
                response_time = end_time - start_time
                
                # 检查是否来自缓存
                cache_hit = getattr(result, '_from_cache', False) if result else False
                
                monitor.record_api_call(
                    symbol=symbol,
                    period=period,
                    response_time=response_time,
                    success=True,
                    cache_hit=cache_hit
                )
                
                return result
                
            except HistoricalDataException as e:
                end_time = time.time()
                response_time = end_time - start_time
                
                monitor.record_api_call(
                    symbol=symbol,
                    period=period,
                    response_time=response_time,
                    success=False,
                    error_category=e.category.value
                )
                raise
                
            except Exception as e:
                end_time = time.time()
                response_time = end_time - start_time
                
                monitor.record_api_call(
                    symbol=symbol,
                    period=period,
                    response_time=response_time,
                    success=False,
                    error_category=ErrorCategory.UNKNOWN_ERROR.value
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            monitor = get_historical_performance_monitor()
            
            if not monitor.is_monitoring:
                monitor.start_monitoring()
            
            start_time = time.time()
            symbol = kwargs.get(symbol_param, args[0] if args else 'unknown')
            period = kwargs.get(period_param, 'unknown')
            
            try:
                result = func(*args, **kwargs)
                
                end_time = time.time()
                response_time = end_time - start_time
                
                cache_hit = getattr(result, '_from_cache', False) if result else False
                
                monitor.record_api_call(
                    symbol=symbol,
                    period=period,
                    response_time=response_time,
                    success=True,
                    cache_hit=cache_hit
                )
                
                return result
                
            except HistoricalDataException as e:
                end_time = time.time()
                response_time = end_time - start_time
                
                monitor.record_api_call(
                    symbol=symbol,
                    period=period,
                    response_time=response_time,
                    success=False,
                    error_category=e.category.value
                )
                raise
                
            except Exception as e:
                end_time = time.time()
                response_time = end_time - start_time
                
                monitor.record_api_call(
                    symbol=symbol,
                    period=period,
                    response_time=response_time,
                    success=False,
                    error_category=ErrorCategory.UNKNOWN_ERROR.value
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator