#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控和指标收集模块

提供实时性能监控、指标收集、告警和报告功能
"""

import asyncio
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"  # 计数器
    GAUGE = "gauge"      # 仪表盘
    HISTOGRAM = "histogram"  # 直方图
    TIMER = "timer"      # 计时器

class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE

@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric_name: str
    condition: str  # 条件表达式，如 "> 80", "< 10"
    threshold: float
    level: AlertLevel
    duration: int = 60  # 持续时间（秒）
    enabled: bool = True
    callback: Optional[Callable] = None

@dataclass
class Alert:
    """告警信息"""
    alert_id: str
    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    level: AlertLevel
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    resolved: bool = False

class SystemMetricsCollector:
    """系统指标收集器"""
    
    def __init__(self):
        self.process = psutil.Process()
    
    def collect_cpu_metrics(self) -> Dict[str, float]:
        """收集CPU指标"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "cpu_count": psutil.cpu_count(),
                "process_cpu_percent": self.process.cpu_percent(),
                "load_avg_1m": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
                "load_avg_5m": psutil.getloadavg()[1] if hasattr(psutil, 'getloadavg') else 0,
                "load_avg_15m": psutil.getloadavg()[2] if hasattr(psutil, 'getloadavg') else 0
            }
        except Exception as e:
            logger.error(f"收集CPU指标失败: {e}")
            return {}
    
    def collect_memory_metrics(self) -> Dict[str, float]:
        """收集内存指标"""
        try:
            memory = psutil.virtual_memory()
            process_memory = self.process.memory_info()
            
            return {
                "memory_total": memory.total,
                "memory_available": memory.available,
                "memory_used": memory.used,
                "memory_percent": memory.percent,
                "process_memory_rss": process_memory.rss,
                "process_memory_vms": process_memory.vms,
                "process_memory_percent": self.process.memory_percent()
            }
        except Exception as e:
            logger.error(f"收集内存指标失败: {e}")
            return {}
    
    def collect_disk_metrics(self) -> Dict[str, float]:
        """收集磁盘指标"""
        try:
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            metrics = {
                "disk_total": disk_usage.total,
                "disk_used": disk_usage.used,
                "disk_free": disk_usage.free,
                "disk_percent": disk_usage.used / disk_usage.total * 100
            }
            
            if disk_io:
                metrics.update({
                    "disk_read_bytes": disk_io.read_bytes,
                    "disk_write_bytes": disk_io.write_bytes,
                    "disk_read_count": disk_io.read_count,
                    "disk_write_count": disk_io.write_count
                })
            
            return metrics
        except Exception as e:
            logger.error(f"收集磁盘指标失败: {e}")
            return {}
    
    def collect_network_metrics(self) -> Dict[str, float]:
        """收集网络指标"""
        try:
            net_io = psutil.net_io_counters()
            connections = psutil.net_connections()
            
            metrics = {
                "network_bytes_sent": net_io.bytes_sent,
                "network_bytes_recv": net_io.bytes_recv,
                "network_packets_sent": net_io.packets_sent,
                "network_packets_recv": net_io.packets_recv,
                "network_connections_total": len(connections),
                "network_connections_established": len([c for c in connections if c.status == 'ESTABLISHED'])
            }
            
            return metrics
        except Exception as e:
            logger.error(f"收集网络指标失败: {e}")
            return {}

class ApplicationMetricsCollector:
    """应用指标收集器"""
    
    def __init__(self):
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.lock = threading.Lock()
    
    def increment_counter(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """增加计数器"""
        with self.lock:
            key = self._make_key(name, tags)
            self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """设置仪表盘值"""
        with self.lock:
            key = self._make_key(name, tags)
            self.gauges[key] = value
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """记录直方图值"""
        with self.lock:
            key = self._make_key(name, tags)
            self.histograms[key].append(value)
            # 保持最近1000个值
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
    
    def record_timer(self, name: str, duration: float, tags: Dict[str, str] = None):
        """记录计时器值"""
        with self.lock:
            key = self._make_key(name, tags)
            self.timers[key].append({
                'duration': duration,
                'timestamp': time.time()
            })
    
    def _make_key(self, name: str, tags: Dict[str, str] = None) -> str:
        """生成指标键"""
        if not tags:
            return name
        tag_str = ','.join([f"{k}={v}" for k, v in sorted(tags.items())])
        return f"{name}[{tag_str}]"
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取所有应用指标"""
        with self.lock:
            metrics = {
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histograms': {},
                'timers': {}
            }
            
            # 计算直方图统计
            for key, values in self.histograms.items():
                if values:
                    metrics['histograms'][key] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'mean': sum(values) / len(values),
                        'p50': self._percentile(values, 50),
                        'p95': self._percentile(values, 95),
                        'p99': self._percentile(values, 99)
                    }
            
            # 计算计时器统计
            current_time = time.time()
            for key, timer_data in self.timers.items():
                # 只统计最近5分钟的数据
                recent_data = [d for d in timer_data if current_time - d['timestamp'] <= 300]
                if recent_data:
                    durations = [d['duration'] for d in recent_data]
                    metrics['timers'][key] = {
                        'count': len(durations),
                        'min': min(durations),
                        'max': max(durations),
                        'mean': sum(durations) / len(durations),
                        'p50': self._percentile(durations, 50),
                        'p95': self._percentile(durations, 95),
                        'p99': self._percentile(durations, 99)
                    }
            
            return metrics
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.lock = threading.Lock()
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        with self.lock:
            self.rules[rule.name] = rule
    
    def remove_rule(self, rule_name: str):
        """移除告警规则"""
        with self.lock:
            if rule_name in self.rules:
                del self.rules[rule_name]
    
    def check_alerts(self, metrics: Dict[str, Any]):
        """检查告警"""
        with self.lock:
            current_time = datetime.now()
            
            for rule_name, rule in self.rules.items():
                if not rule.enabled:
                    continue
                
                # 查找对应的指标值
                metric_value = self._find_metric_value(metrics, rule.metric_name)
                if metric_value is None:
                    continue
                
                # 检查条件
                if self._check_condition(metric_value, rule.condition, rule.threshold):
                    # 触发告警
                    alert_id = f"{rule_name}_{int(current_time.timestamp())}"
                    
                    if alert_id not in self.active_alerts:
                        alert = Alert(
                            alert_id=alert_id,
                            rule_name=rule_name,
                            metric_name=rule.metric_name,
                            current_value=metric_value,
                            threshold=rule.threshold,
                            level=rule.level,
                            message=f"{rule.metric_name} {rule.condition} {rule.threshold}, 当前值: {metric_value}",
                            triggered_at=current_time
                        )
                        
                        self.active_alerts[alert_id] = alert
                        self.alert_history.append(alert)
                        
                        # 执行回调
                        if rule.callback:
                            try:
                                rule.callback(alert)
                            except Exception as e:
                                logger.error(f"执行告警回调失败: {e}")
                        
                        logger.warning(f"触发告警: {alert.message}")
                else:
                    # 检查是否需要解决告警
                    alerts_to_resolve = []
                    for alert_id, alert in self.active_alerts.items():
                        if alert.rule_name == rule_name and not alert.resolved:
                            alerts_to_resolve.append(alert_id)
                    
                    for alert_id in alerts_to_resolve:
                        self.resolve_alert(alert_id)
    
    def _find_metric_value(self, metrics: Dict[str, Any], metric_name: str) -> Optional[float]:
        """查找指标值"""
        # 在不同类型的指标中查找
        for metric_type in ['gauges', 'counters']:
            if metric_type in metrics and metric_name in metrics[metric_type]:
                return float(metrics[metric_type][metric_name])
        
        # 在直方图和计时器中查找平均值
        for metric_type in ['histograms', 'timers']:
            if metric_type in metrics and metric_name in metrics[metric_type]:
                return float(metrics[metric_type][metric_name].get('mean', 0))
        
        return None
    
    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """检查条件"""
        try:
            if condition.startswith('>'):
                return value > threshold
            elif condition.startswith('<'):
                return value < threshold
            elif condition.startswith('>='):
                return value >= threshold
            elif condition.startswith('<='):
                return value <= threshold
            elif condition.startswith('=='):
                return value == threshold
            elif condition.startswith('!='):
                return value != threshold
            else:
                return False
        except Exception:
            return False
    
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now()
            del self.active_alerts[alert_id]
            logger.info(f"告警已解决: {alert.message}")
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        with self.lock:
            return self.alert_history[-limit:]

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, collection_interval: int = 30):
        self.collection_interval = collection_interval
        self.system_collector = SystemMetricsCollector()
        self.app_collector = ApplicationMetricsCollector()
        self.alert_manager = AlertManager()
        
        self.metrics_history: deque = deque(maxlen=1000)  # 保存最近1000个采集点
        self.running = False
        self.collection_thread: Optional[threading.Thread] = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # 添加默认告警规则
        self._setup_default_alerts()
    
    def _setup_default_alerts(self):
        """设置默认告警规则"""
        default_rules = [
            AlertRule(
                name="high_cpu_usage",
                metric_name="cpu_percent",
                condition=">",
                threshold=80.0,
                level=AlertLevel.WARNING,
                duration=60
            ),
            AlertRule(
                name="high_memory_usage",
                metric_name="memory_percent",
                condition=">",
                threshold=85.0,
                level=AlertLevel.WARNING,
                duration=60
            ),
            AlertRule(
                name="low_disk_space",
                metric_name="disk_percent",
                condition=">",
                threshold=90.0,
                level=AlertLevel.ERROR,
                duration=300
            ),
            AlertRule(
                name="high_response_time",
                metric_name="api_response_time",
                condition=">",
                threshold=5.0,
                level=AlertLevel.WARNING,
                duration=120
            )
        ]
        
        for rule in default_rules:
            self.alert_manager.add_rule(rule)
    
    def start(self):
        """启动监控"""
        if self.running:
            return
        
        self.running = True
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        logger.info("性能监控器已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
        logger.info("性能监控器已停止")
    
    def _collection_loop(self):
        """指标收集循环"""
        while self.running:
            try:
                start_time = time.time()
                
                # 并行收集系统指标
                system_future = self.executor.submit(self._collect_system_metrics)
                app_future = self.executor.submit(self._collect_app_metrics)
                
                system_metrics = system_future.result(timeout=10)
                app_metrics = app_future.result(timeout=10)
                
                # 合并指标
                all_metrics = {
                    'timestamp': datetime.now().isoformat(),
                    'system': system_metrics,
                    'application': app_metrics
                }
                
                # 保存到历史记录
                self.metrics_history.append(all_metrics)
                
                # 检查告警
                combined_metrics = {**system_metrics, **app_metrics}
                self.alert_manager.check_alerts(combined_metrics)
                
                # 记录收集耗时
                collection_time = time.time() - start_time
                self.app_collector.record_timer('metrics_collection_time', collection_time)
                
                # 等待下次收集
                time.sleep(max(0, self.collection_interval - collection_time))
                
            except Exception as e:
                logger.error(f"指标收集失败: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_system_metrics(self) -> Dict[str, float]:
        """收集系统指标"""
        metrics = {}
        
        try:
            metrics.update(self.system_collector.collect_cpu_metrics())
            metrics.update(self.system_collector.collect_memory_metrics())
            metrics.update(self.system_collector.collect_disk_metrics())
            metrics.update(self.system_collector.collect_network_metrics())
        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
        
        return metrics
    
    def _collect_app_metrics(self) -> Dict[str, Any]:
        """收集应用指标"""
        try:
            return self.app_collector.get_metrics()
        except Exception as e:
            logger.error(f"收集应用指标失败: {e}")
            return {}
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        if self.metrics_history:
            return self.metrics_history[-1]
        return {}
    
    def get_metrics_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指标历史"""
        return list(self.metrics_history)[-limit:]
    
    def get_performance_summary(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """获取性能摘要"""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        
        # 过滤指定时间范围内的数据
        recent_metrics = []
        for metric in self.metrics_history:
            try:
                metric_time = datetime.fromisoformat(metric['timestamp'])
                if metric_time >= cutoff_time:
                    recent_metrics.append(metric)
            except Exception:
                continue
        
        if not recent_metrics:
            return {}
        
        # 计算摘要统计
        summary = {
            'period_minutes': duration_minutes,
            'data_points': len(recent_metrics),
            'cpu': self._calculate_metric_summary(recent_metrics, 'system.cpu_percent'),
            'memory': self._calculate_metric_summary(recent_metrics, 'system.memory_percent'),
            'disk': self._calculate_metric_summary(recent_metrics, 'system.disk_percent'),
            'active_alerts': len(self.alert_manager.get_active_alerts()),
            'total_alerts': len(self.alert_manager.get_alert_history())
        }
        
        return summary
    
    def _calculate_metric_summary(self, metrics: List[Dict], metric_path: str) -> Dict[str, float]:
        """计算指标摘要"""
        values = []
        
        for metric in metrics:
            try:
                # 解析嵌套路径
                value = metric
                for key in metric_path.split('.'):
                    value = value[key]
                values.append(float(value))
            except (KeyError, TypeError, ValueError):
                continue
        
        if not values:
            return {'min': 0, 'max': 0, 'avg': 0, 'current': 0}
        
        return {
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'current': values[-1] if values else 0
        }
    
    # 应用指标记录方法
    def increment_counter(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """增加计数器"""
        self.app_collector.increment_counter(name, value, tags)
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """设置仪表盘值"""
        self.app_collector.set_gauge(name, value, tags)
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """记录直方图值"""
        self.app_collector.record_histogram(name, value, tags)
    
    def record_timer(self, name: str, duration: float, tags: Dict[str, str] = None):
        """记录计时器值"""
        self.app_collector.record_timer(name, duration, tags)
    
    # 告警管理方法
    def add_alert_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.alert_manager.add_rule(rule)
    
    def remove_alert_rule(self, rule_name: str):
        """移除告警规则"""
        self.alert_manager.remove_rule(rule_name)
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return self.alert_manager.get_active_alerts()
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        return self.alert_manager.get_alert_history(limit)
    
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        self.alert_manager.resolve_alert(alert_id)

# 全局性能监控器实例
_global_performance_monitor: Optional[PerformanceMonitor] = None
_monitor_lock = threading.Lock()

def get_global_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _global_performance_monitor
    
    with _monitor_lock:
        if _global_performance_monitor is None:
            _global_performance_monitor = PerformanceMonitor()
        return _global_performance_monitor

def shutdown_global_performance_monitor():
    """关闭全局性能监控器"""
    global _global_performance_monitor
    
    with _monitor_lock:
        if _global_performance_monitor is not None:
            _global_performance_monitor.stop()
            _global_performance_monitor = None