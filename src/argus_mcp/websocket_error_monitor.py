"""
WebSocket 实时数据系统 - 错误监控和日志系统
提供详细的错误追踪、日志记录和监控功能
"""

import asyncio
import logging
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from pathlib import Path
import aiofiles
from collections import defaultdict, deque

from .websocket_error_handler import WebSocketError, ErrorCategory, ErrorSeverity
from .websocket_models import Alert, StatusMessage

logger = logging.getLogger(__name__)


@dataclass
class ErrorLogEntry:
    """错误日志条目"""
    error_id: str
    timestamp: datetime
    category: str
    severity: str
    message: str
    client_id: Optional[str] = None
    subscription_id: Optional[str] = None
    operation: Optional[str] = None
    stack_trace: Optional[str] = None
    recovery_action: Optional[str] = None
    recovery_success: bool = False
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorPattern:
    """错误模式"""
    pattern_id: str
    category: str
    frequency: int
    time_window: timedelta
    threshold: int
    description: str
    is_active: bool = True
    last_triggered: Optional[datetime] = None


@dataclass
class MonitoringMetrics:
    """监控指标"""
    timestamp: datetime
    total_errors: int
    errors_by_category: Dict[str, int]
    errors_by_severity: Dict[str, int]
    error_rate_per_minute: float
    recovery_success_rate: float
    active_patterns: int
    degraded_services: int
    circuit_breakers_open: int


class WebSocketErrorMonitor:
    """WebSocket错误监控器"""
    
    def __init__(
        self,
        log_file_path: str = "logs/websocket_errors.log",
        max_log_entries: int = 10000,
        pattern_detection_enabled: bool = True,
        metrics_collection_interval: float = 60.0
    ):
        self.log_file_path = Path(log_file_path)
        self.max_log_entries = max_log_entries
        self.pattern_detection_enabled = pattern_detection_enabled
        self.metrics_collection_interval = metrics_collection_interval
        
        # 确保日志目录存在
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 内存中的错误日志
        self.error_logs: deque = deque(maxlen=max_log_entries)
        
        # 错误模式检测
        self.error_patterns: Dict[str, ErrorPattern] = {}
        self.pattern_callbacks: List[Callable] = []
        
        # 监控指标
        self.metrics_history: deque = deque(maxlen=1440)  # 24小时的分钟级数据
        self.current_metrics = MonitoringMetrics(
            timestamp=datetime.now(),
            total_errors=0,
            errors_by_category={},
            errors_by_severity={},
            error_rate_per_minute=0.0,
            recovery_success_rate=0.0,
            active_patterns=0,
            degraded_services=0,
            circuit_breakers_open=0
        )
        
        # 告警回调
        self.alert_callbacks: List[Callable] = []
        
        # 监控任务
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        
        # 错误统计
        self.error_counts = defaultdict(int)
        self.recovery_stats = {"successful": 0, "failed": 0}
        
        # 初始化错误模式
        self._initialize_default_patterns()
        
        logger.info(f"WebSocket Error Monitor initialized with log file: {self.log_file_path}")
    
    def _initialize_default_patterns(self):
        """初始化默认错误模式"""
        default_patterns = [
            ErrorPattern(
                pattern_id="connection_storm",
                category="connection",
                frequency=10,
                time_window=timedelta(minutes=5),
                threshold=10,
                description="High frequency connection errors"
            ),
            ErrorPattern(
                pattern_id="subscription_cascade",
                category="subscription",
                frequency=20,
                time_window=timedelta(minutes=10),
                threshold=20,
                description="Cascading subscription failures"
            ),
            ErrorPattern(
                pattern_id="data_publish_failure",
                category="data_publish",
                frequency=15,
                time_window=timedelta(minutes=5),
                threshold=15,
                description="Repeated data publishing failures"
            ),
            ErrorPattern(
                pattern_id="network_instability",
                category="network",
                frequency=8,
                time_window=timedelta(minutes=3),
                threshold=8,
                description="Network instability pattern"
            ),
            ErrorPattern(
                pattern_id="authentication_attacks",
                category="authentication",
                frequency=5,
                time_window=timedelta(minutes=1),
                threshold=5,
                description="Potential authentication attacks"
            )
        ]
        
        for pattern in default_patterns:
            self.error_patterns[pattern.pattern_id] = pattern
    
    async def start_monitoring(self):
        """启动监控"""
        if self.is_monitoring:
            logger.warning("Error monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Error monitoring started")
    
    async def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Error monitoring stopped")
    
    async def _monitoring_loop(self):
        """监控循环"""
        try:
            while self.is_monitoring:
                await self._collect_metrics()
                await self._detect_patterns()
                await self._check_alerts()
                await asyncio.sleep(self.metrics_collection_interval)
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
    
    async def log_error(
        self,
        error: WebSocketError,
        recovery_action: Optional[str] = None,
        recovery_success: bool = False,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """记录错误"""
        try:
            # 创建错误日志条目
            log_entry = ErrorLogEntry(
                error_id=error.context.error_id,
                timestamp=error.timestamp,
                category=error.category.value,
                severity=error.severity.value,
                message=error.message,
                client_id=error.context.client_id,
                subscription_id=error.context.subscription_id,
                operation=error.context.operation,
                stack_trace=traceback.format_exc() if error.original_error else None,
                recovery_action=recovery_action,
                recovery_success=recovery_success,
                additional_data=additional_data or {}
            )
            
            # 添加到内存日志
            self.error_logs.append(log_entry)
            
            # 写入文件
            await self._write_log_to_file(log_entry)
            
            # 更新统计
            self._update_error_statistics(log_entry)
            
            # 检测模式
            if self.pattern_detection_enabled:
                await self._check_error_patterns(log_entry)
            
            logger.debug(f"Error logged: {error.context.error_id}")
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
    
    async def _write_log_to_file(self, log_entry: ErrorLogEntry):
        """将日志写入文件"""
        try:
            log_data = {
                "error_id": log_entry.error_id,
                "timestamp": log_entry.timestamp.isoformat(),
                "category": log_entry.category,
                "severity": log_entry.severity,
                "message": log_entry.message,
                "client_id": log_entry.client_id,
                "subscription_id": log_entry.subscription_id,
                "operation": log_entry.operation,
                "stack_trace": log_entry.stack_trace,
                "recovery_action": log_entry.recovery_action,
                "recovery_success": log_entry.recovery_success,
                "additional_data": log_entry.additional_data
            }
            
            async with aiofiles.open(self.log_file_path, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(log_data, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"Failed to write log to file: {e}")
    
    def _update_error_statistics(self, log_entry: ErrorLogEntry):
        """更新错误统计"""
        self.error_counts[log_entry.category] += 1
        self.error_counts[f"severity_{log_entry.severity}"] += 1
        
        if log_entry.recovery_action:
            if log_entry.recovery_success:
                self.recovery_stats["successful"] += 1
            else:
                self.recovery_stats["failed"] += 1
    
    async def _check_error_patterns(self, log_entry: ErrorLogEntry):
        """检查错误模式"""
        try:
            current_time = datetime.now()
            
            for pattern in self.error_patterns.values():
                if not pattern.is_active or pattern.category != log_entry.category:
                    continue
                
                # 计算时间窗口内的错误数量
                window_start = current_time - pattern.time_window
                recent_errors = [
                    entry for entry in self.error_logs
                    if (entry.timestamp >= window_start and 
                        entry.category == pattern.category)
                ]
                
                # 检查是否达到阈值
                if len(recent_errors) >= pattern.threshold:
                    await self._trigger_pattern_alert(pattern, recent_errors)
                    
        except Exception as e:
            logger.error(f"Error in pattern detection: {e}")
    
    async def _trigger_pattern_alert(self, pattern: ErrorPattern, recent_errors: List[ErrorLogEntry]):
        """触发模式告警"""
        try:
            # 避免重复告警
            if (pattern.last_triggered and 
                datetime.now() - pattern.last_triggered < timedelta(minutes=5)):
                return
            
            pattern.last_triggered = datetime.now()
            
            alert = Alert(
                type="error_pattern_detected",
                severity="high",
                message=f"Error pattern detected: {pattern.description}",
                metrics={
                    "pattern_id": pattern.pattern_id,
                    "category": pattern.category,
                    "error_count": len(recent_errors),
                    "threshold": pattern.threshold,
                    "time_window_minutes": pattern.time_window.total_seconds() / 60,
                    "affected_clients": list(set(
                        e.client_id for e in recent_errors if e.client_id
                    ))
                }
            )
            
            await self._send_alert(alert)
            
            # 调用模式回调
            for callback in self.pattern_callbacks:
                try:
                    await callback(pattern, recent_errors)
                except Exception as e:
                    logger.error(f"Pattern callback failed: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to trigger pattern alert: {e}")
    
    async def _collect_metrics(self):
        """收集监控指标"""
        try:
            current_time = datetime.now()
            
            # 计算过去一分钟的错误率
            one_minute_ago = current_time - timedelta(minutes=1)
            recent_errors = [
                entry for entry in self.error_logs
                if entry.timestamp >= one_minute_ago
            ]
            
            # 按分类统计
            errors_by_category = defaultdict(int)
            errors_by_severity = defaultdict(int)
            
            for entry in self.error_logs:
                errors_by_category[entry.category] += 1
                errors_by_severity[entry.severity] += 1
            
            # 计算恢复成功率
            total_recoveries = self.recovery_stats["successful"] + self.recovery_stats["failed"]
            recovery_success_rate = (
                self.recovery_stats["successful"] / max(total_recoveries, 1) * 100
            )
            
            # 统计活跃模式
            active_patterns = sum(1 for p in self.error_patterns.values() if p.is_active)
            
            # 创建指标对象
            metrics = MonitoringMetrics(
                timestamp=current_time,
                total_errors=len(self.error_logs),
                errors_by_category=dict(errors_by_category),
                errors_by_severity=dict(errors_by_severity),
                error_rate_per_minute=len(recent_errors),
                recovery_success_rate=recovery_success_rate,
                active_patterns=active_patterns,
                degraded_services=0,  # 这个需要从外部系统获取
                circuit_breakers_open=0  # 这个需要从错误处理器获取
            )
            
            self.current_metrics = metrics
            self.metrics_history.append(metrics)
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
    
    async def _detect_patterns(self):
        """检测错误模式"""
        # 这个方法在_check_error_patterns中已经实现
        # 这里可以添加更复杂的模式检测逻辑
        pass
    
    async def _check_alerts(self):
        """检查告警条件"""
        try:
            current_metrics = self.current_metrics
            
            # 检查错误率告警
            if current_metrics.error_rate_per_minute > 10:  # 每分钟超过10个错误
                alert = Alert(
                    type="high_error_rate",
                    severity="high",
                    message=f"High error rate detected: {current_metrics.error_rate_per_minute} errors/minute",
                    metrics={"error_rate": current_metrics.error_rate_per_minute}
                )
                await self._send_alert(alert)
            
            # 检查恢复成功率告警
            if current_metrics.recovery_success_rate < 80:  # 恢复成功率低于80%
                alert = Alert(
                    type="low_recovery_rate",
                    severity="medium",
                    message=f"Low recovery success rate: {current_metrics.recovery_success_rate:.1f}%",
                    metrics={"recovery_rate": current_metrics.recovery_success_rate}
                )
                await self._send_alert(alert)
                
        except Exception as e:
            logger.error(f"Failed to check alerts: {e}")
    
    async def _send_alert(self, alert: Alert):
        """发送告警"""
        logger.warning(f"Alert: {alert.type} - {alert.message}")
        
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)
    
    def register_pattern_callback(self, callback: Callable):
        """注册模式检测回调"""
        self.pattern_callbacks.append(callback)
    
    def add_error_pattern(self, pattern: ErrorPattern):
        """添加错误模式"""
        self.error_patterns[pattern.pattern_id] = pattern
        logger.info(f"Added error pattern: {pattern.pattern_id}")
    
    def remove_error_pattern(self, pattern_id: str) -> bool:
        """移除错误模式"""
        if pattern_id in self.error_patterns:
            del self.error_patterns[pattern_id]
            logger.info(f"Removed error pattern: {pattern_id}")
            return True
        return False
    
    def enable_pattern(self, pattern_id: str) -> bool:
        """启用错误模式"""
        if pattern_id in self.error_patterns:
            self.error_patterns[pattern_id].is_active = True
            return True
        return False
    
    def disable_pattern(self, pattern_id: str) -> bool:
        """禁用错误模式"""
        if pattern_id in self.error_patterns:
            self.error_patterns[pattern_id].is_active = False
            return True
        return False
    
    def get_error_logs(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        client_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[ErrorLogEntry]:
        """获取错误日志"""
        filtered_logs = list(self.error_logs)
        
        # 应用过滤条件
        if category:
            filtered_logs = [log for log in filtered_logs if log.category == category]
        
        if severity:
            filtered_logs = [log for log in filtered_logs if log.severity == severity]
        
        if client_id:
            filtered_logs = [log for log in filtered_logs if log.client_id == client_id]
        
        if start_time:
            filtered_logs = [log for log in filtered_logs if log.timestamp >= start_time]
        
        if end_time:
            filtered_logs = [log for log in filtered_logs if log.timestamp <= end_time]
        
        # 按时间倒序排列并限制数量
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered_logs[:limit]
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        return {
            "total_errors": len(self.error_logs),
            "errors_by_category": dict(self.error_counts),
            "recovery_stats": self.recovery_stats.copy(),
            "current_metrics": {
                "timestamp": self.current_metrics.timestamp.isoformat(),
                "total_errors": self.current_metrics.total_errors,
                "errors_by_category": self.current_metrics.errors_by_category,
                "errors_by_severity": self.current_metrics.errors_by_severity,
                "error_rate_per_minute": self.current_metrics.error_rate_per_minute,
                "recovery_success_rate": self.current_metrics.recovery_success_rate,
                "active_patterns": self.current_metrics.active_patterns
            },
            "active_patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "category": p.category,
                    "description": p.description,
                    "threshold": p.threshold,
                    "last_triggered": p.last_triggered.isoformat() if p.last_triggered else None
                }
                for p in self.error_patterns.values() if p.is_active
            ]
        }
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取指标历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "total_errors": m.total_errors,
                "error_rate_per_minute": m.error_rate_per_minute,
                "recovery_success_rate": m.recovery_success_rate,
                "errors_by_category": m.errors_by_category,
                "errors_by_severity": m.errors_by_severity
            }
            for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]
    
    async def export_logs(
        self,
        output_file: str,
        format: str = "json",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> bool:
        """导出错误日志"""
        try:
            logs = self.get_error_logs(
                limit=len(self.error_logs),
                start_time=start_time,
                end_time=end_time
            )
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == "json":
                log_data = [
                    {
                        "error_id": log.error_id,
                        "timestamp": log.timestamp.isoformat(),
                        "category": log.category,
                        "severity": log.severity,
                        "message": log.message,
                        "client_id": log.client_id,
                        "subscription_id": log.subscription_id,
                        "operation": log.operation,
                        "recovery_action": log.recovery_action,
                        "recovery_success": log.recovery_success,
                        "additional_data": log.additional_data
                    }
                    for log in logs
                ]
                
                async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(log_data, indent=2, ensure_ascii=False))
            
            elif format.lower() == "csv":
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.writer(output)
                
                # 写入标题行
                writer.writerow([
                    "error_id", "timestamp", "category", "severity", "message",
                    "client_id", "subscription_id", "operation", "recovery_action",
                    "recovery_success"
                ])
                
                # 写入数据行
                for log in logs:
                    writer.writerow([
                        log.error_id, log.timestamp.isoformat(), log.category,
                        log.severity, log.message, log.client_id, log.subscription_id,
                        log.operation, log.recovery_action, log.recovery_success
                    ])
                
                async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                    await f.write(output.getvalue())
            
            logger.info(f"Exported {len(logs)} error logs to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            return False
    
    async def cleanup(self):
        """清理监控器"""
        await self.stop_monitoring()
        self.error_logs.clear()
        self.metrics_history.clear()
        self.alert_callbacks.clear()
        self.pattern_callbacks.clear()
        logger.info("Error monitor cleaned up")


# 监控装饰器
def monitor_errors(error_monitor: WebSocketErrorMonitor):
    """错误监控装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                # 如果是WebSocketError，直接记录
                if isinstance(e, WebSocketError):
                    await error_monitor.log_error(e)
                else:
                    # 转换为WebSocketError并记录
                    from .websocket_error_handler import ErrorContext
                    context = ErrorContext(operation=func.__name__)
                    websocket_error = WebSocketError(
                        message=str(e),
                        context=context,
                        original_error=e
                    )
                    await error_monitor.log_error(websocket_error)
                
                raise e
        
        return wrapper
    return decorator