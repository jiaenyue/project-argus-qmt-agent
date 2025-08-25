#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连接状态监控模块
提供实时连接状态检查、健康度评估和告警功能
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Deque
from concurrent.futures import ThreadPoolExecutor

try:
    from xtquant import xtdata
except ImportError:
    raise ImportError(
        "无法导入xtdata模块。请确保miniQMT客户端已正确安装和配置。"
        "项目不再支持模拟模式，必须连接真实的miniQMT。"
    )


class HealthStatus(Enum):
    """健康状态枚举"""
    EXCELLENT = "excellent"      # 优秀 (95-100%)
    GOOD = "good"                # 良好 (85-94%)
    FAIR = "fair"                # 一般 (70-84%)
    POOR = "poor"                # 较差 (50-69%)
    CRITICAL = "critical"        # 严重 (<50%)
    UNKNOWN = "unknown"          # 未知


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthMetric:
    """健康指标"""
    timestamp: datetime
    response_time: float          # 响应时间(毫秒)
    success: bool                 # 是否成功
    error_message: Optional[str] = None
    connection_id: Optional[str] = None


@dataclass
class HealthSummary:
    """健康摘要"""
    status: HealthStatus
    success_rate: float           # 成功率 (0-1)
    avg_response_time: float      # 平均响应时间(毫秒)
    total_checks: int             # 总检查次数
    failed_checks: int            # 失败次数
    last_check_time: datetime
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    uptime_percentage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        data['last_check_time'] = self.last_check_time.isoformat()
        if self.last_success_time:
            data['last_success_time'] = self.last_success_time.isoformat()
        if self.last_failure_time:
            data['last_failure_time'] = self.last_failure_time.isoformat()
        return data


@dataclass
class Alert:
    """告警信息"""
    id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['level'] = self.level.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data


class HealthChecker:
    """健康检查器"""
    
    def __init__(self, check_interval: int = 30, history_size: int = 100):
        self.check_interval = check_interval
        self.history_size = history_size
        self.metrics_history: Deque[HealthMetric] = deque(maxlen=history_size)
        self.logger = logging.getLogger("health_checker")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[HealthMetric], None]] = []
    
    def add_callback(self, callback: Callable[[HealthMetric], None]):
        """添加健康检查回调"""
        self._callbacks.append(callback)
    
    def start(self):
        """启动健康检查"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        self.logger.info("健康检查器已启动")
    
    def stop(self):
        """停止健康检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.logger.info("健康检查器已停止")
    
    def _check_loop(self):
        """检查循环"""
        while self._running:
            try:
                metric = self._perform_health_check()
                self.metrics_history.append(metric)
                
                # 调用回调函数
                for callback in self._callbacks:
                    try:
                        callback(metric)
                    except Exception as e:
                        self.logger.error(f"健康检查回调异常: {e}")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"健康检查异常: {e}")
                time.sleep(self.check_interval)
    
    def _perform_health_check(self) -> HealthMetric:
        """执行健康检查"""
        start_time = time.time()
        
        try:
            # 实际健康检查 - 获取简单的市场数据
            result = xtdata.get_market_data(['000001.SZ'], period='1d', count=1)
            success = result is not None and len(result) > 0
            error_message = None if success else "获取市场数据失败"
            
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            return HealthMetric(
                timestamp=datetime.now(),
                response_time=response_time,
                success=success,
                error_message=error_message
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthMetric(
                timestamp=datetime.now(),
                response_time=response_time,
                success=False,
                error_message=str(e)
            )
    
    def get_health_summary(self, time_window_minutes: int = 60) -> HealthSummary:
        """获取健康摘要"""
        if not self.metrics_history:
            return HealthSummary(
                status=HealthStatus.UNKNOWN,
                success_rate=0.0,
                avg_response_time=0.0,
                total_checks=0,
                failed_checks=0,
                last_check_time=datetime.now()
            )
        
        # 过滤时间窗口内的指标
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            recent_metrics = list(self.metrics_history)[-10:]  # 至少取最近10个
        
        total_checks = len(recent_metrics)
        successful_checks = sum(1 for m in recent_metrics if m.success)
        failed_checks = total_checks - successful_checks
        success_rate = successful_checks / total_checks if total_checks > 0 else 0.0
        
        # 计算平均响应时间（只计算成功的请求）
        successful_metrics = [m for m in recent_metrics if m.success]
        avg_response_time = (
            sum(m.response_time for m in successful_metrics) / len(successful_metrics)
            if successful_metrics else 0.0
        )
        
        # 确定健康状态
        status = self._determine_health_status(success_rate, avg_response_time)
        
        # 获取最后的成功和失败时间
        last_success_time = None
        last_failure_time = None
        
        for metric in reversed(self.metrics_history):
            if metric.success and last_success_time is None:
                last_success_time = metric.timestamp
            elif not metric.success and last_failure_time is None:
                last_failure_time = metric.timestamp
            
            if last_success_time and last_failure_time:
                break
        
        return HealthSummary(
            status=status,
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            total_checks=total_checks,
            failed_checks=failed_checks,
            last_check_time=self.metrics_history[-1].timestamp,
            last_success_time=last_success_time,
            last_failure_time=last_failure_time,
            uptime_percentage=success_rate * 100
        )
    
    def _determine_health_status(self, success_rate: float, avg_response_time: float) -> HealthStatus:
        """确定健康状态"""
        # 基于成功率的基础状态
        if success_rate >= 0.95:
            base_status = HealthStatus.EXCELLENT
        elif success_rate >= 0.85:
            base_status = HealthStatus.GOOD
        elif success_rate >= 0.70:
            base_status = HealthStatus.FAIR
        elif success_rate >= 0.50:
            base_status = HealthStatus.POOR
        else:
            base_status = HealthStatus.CRITICAL
        
        # 根据响应时间调整状态
        if avg_response_time > 5000:  # 5秒以上
            if base_status in [HealthStatus.EXCELLENT, HealthStatus.GOOD]:
                base_status = HealthStatus.FAIR
            elif base_status == HealthStatus.FAIR:
                base_status = HealthStatus.POOR
        elif avg_response_time > 2000:  # 2秒以上
            if base_status == HealthStatus.EXCELLENT:
                base_status = HealthStatus.GOOD
        
        return base_status


class AlertManager:
    """告警管理器"""
    
    def __init__(self, max_alerts: int = 1000):
        self.max_alerts = max_alerts
        self.alerts: Deque[Alert] = deque(maxlen=max_alerts)
        self.alert_rules: Dict[str, Callable[[HealthSummary], Optional[Alert]]] = {}
        self.logger = logging.getLogger("alert_manager")
        self._lock = threading.Lock()
        self._alert_callbacks: List[Callable[[Alert], None]] = []
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    def add_alert_rule(self, name: str, rule: Callable[[HealthSummary], Optional[Alert]]):
        """添加告警规则"""
        self.alert_rules[name] = rule
        self.logger.info(f"添加告警规则: {name}")
    
    def check_alerts(self, health_summary: HealthSummary):
        """检查告警"""
        with self._lock:
            for rule_name, rule_func in self.alert_rules.items():
                try:
                    alert = rule_func(health_summary)
                    if alert:
                        self._trigger_alert(alert)
                except Exception as e:
                    self.logger.error(f"告警规则 {rule_name} 执行异常: {e}")
    
    def _trigger_alert(self, alert: Alert):
        """触发告警"""
        # 检查是否是重复告警
        recent_alerts = [a for a in self.alerts if not a.resolved and 
                        (datetime.now() - a.timestamp).total_seconds() < 3600]  # 1小时内
        
        duplicate = any(a.title == alert.title and a.level == alert.level 
                       for a in recent_alerts)
        
        if not duplicate:
            self.alerts.append(alert)
            self.logger.warning(f"触发告警: {alert.level.value} - {alert.title}")
            
            # 调用告警回调
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"告警回调异常: {e}")
    
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    self.logger.info(f"告警已解决: {alert_id}")
                    break
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        with self._lock:
            return [alert for alert in self.alerts if not alert.resolved]
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """获取告警历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        with self._lock:
            return [alert for alert in self.alerts if alert.timestamp >= cutoff_time]


class ConnectionMonitor:
    """连接监控器"""
    
    def __init__(self, 
                 check_interval: int = 30,
                 history_size: int = 100,
                 alert_enabled: bool = True):
        self.check_interval = check_interval
        self.history_size = history_size
        self.alert_enabled = alert_enabled
        
        self.health_checker = HealthChecker(check_interval, history_size)
        self.alert_manager = AlertManager() if alert_enabled else None
        self.logger = logging.getLogger("connection_monitor")
        
        # 设置健康检查回调
        self.health_checker.add_callback(self._on_health_check)
        
        # 添加默认告警规则
        if self.alert_manager:
            self._setup_default_alert_rules()
    
    def _on_health_check(self, metric: HealthMetric):
        """健康检查回调"""
        # 禁用健康检查失败日志，避免测试时输出过多信息
        # if not metric.success:
        #     self.logger.warning(f"健康检查失败: {metric.error_message}")
        
        # 检查告警
        if self.alert_manager:
            health_summary = self.health_checker.get_health_summary()
            self.alert_manager.check_alerts(health_summary)
    
    def _setup_default_alert_rules(self):
        """设置默认告警规则"""
        if not self.alert_manager:
            return
        
        # 连接失败告警
        def connection_failure_rule(summary: HealthSummary) -> Optional[Alert]:
            if summary.success_rate < 0.5:  # 成功率低于50%
                return Alert(
                    id=f"connection_failure_{int(time.time())}",
                    level=AlertLevel.CRITICAL,
                    title="连接严重故障",
                    message=f"连接成功率仅为 {summary.success_rate:.1%}，请立即检查",
                    timestamp=datetime.now(),
                    source="connection_monitor"
                )
            return None
        
        # 响应时间告警
        def response_time_rule(summary: HealthSummary) -> Optional[Alert]:
            if summary.avg_response_time > 5000:  # 响应时间超过5秒
                return Alert(
                    id=f"slow_response_{int(time.time())}",
                    level=AlertLevel.WARNING,
                    title="响应时间过慢",
                    message=f"平均响应时间为 {summary.avg_response_time:.0f}ms，超过阈值",
                    timestamp=datetime.now(),
                    source="connection_monitor"
                )
            return None
        
        # 连接降级告警
        def connection_degraded_rule(summary: HealthSummary) -> Optional[Alert]:
            if summary.status in [HealthStatus.POOR, HealthStatus.FAIR]:
                return Alert(
                    id=f"connection_degraded_{int(time.time())}",
                    level=AlertLevel.WARNING,
                    title="连接性能下降",
                    message=f"连接状态为 {summary.status.value}，成功率 {summary.success_rate:.1%}",
                    timestamp=datetime.now(),
                    source="connection_monitor"
                )
            return None
        
        self.alert_manager.add_alert_rule("connection_failure", connection_failure_rule)
        self.alert_manager.add_alert_rule("response_time", response_time_rule)
        self.alert_manager.add_alert_rule("connection_degraded", connection_degraded_rule)
    
    def start(self):
        """启动监控"""
        self.health_checker.start()
        self.logger.info("连接监控器已启动")
    
    def stop(self):
        """停止监控"""
        self.health_checker.stop()
        self.logger.info("连接监控器已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        health_summary = self.health_checker.get_health_summary()
        
        status = {
            "health": health_summary.to_dict(),
            "monitoring": {
                "check_interval": self.check_interval,
                "history_size": self.history_size,
                "total_metrics": len(self.health_checker.metrics_history)
            }
        }
        
        if self.alert_manager:
            active_alerts = self.alert_manager.get_active_alerts()
            status["alerts"] = {
                "active_count": len(active_alerts),
                "active_alerts": [alert.to_dict() for alert in active_alerts[-10:]],  # 最近10个
                "total_alerts": len(self.alert_manager.alerts)
            }
        
        return status
    
    def get_metrics_history(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """获取指标历史"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_metrics = [
            {
                "timestamp": metric.timestamp.isoformat(),
                "response_time": metric.response_time,
                "success": metric.success,
                "error_message": metric.error_message
            }
            for metric in self.health_checker.metrics_history
            if metric.timestamp >= cutoff_time
        ]
        return recent_metrics


# 全局监控器实例
_connection_monitor: Optional[ConnectionMonitor] = None
_monitor_lock = threading.Lock()


def get_connection_monitor() -> ConnectionMonitor:
    """获取全局连接监控器实例"""
    global _connection_monitor
    
    if _connection_monitor is None:
        with _monitor_lock:
            if _connection_monitor is None:
                _connection_monitor = ConnectionMonitor(
                    check_interval=30,
                    history_size=200,
                    alert_enabled=True
                )
                _connection_monitor.start()
    
    return _connection_monitor


def shutdown_connection_monitor():
    """关闭全局连接监控器"""
    global _connection_monitor
    
    if _connection_monitor:
        with _monitor_lock:
            if _connection_monitor:
                _connection_monitor.stop()
                _connection_monitor = None