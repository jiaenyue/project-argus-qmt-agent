"""
WebSocket性能监控和告警系统
实现实时性能指标收集、统计和告警功能
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics

# Define monitoring models locally since they're not in data_models
from enum import Enum

class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class AlertConfig:
    """告警配置"""
    max_connections: int = 1000
    max_latency_ms: float = 100.0
    max_error_rate: float = 0.05
    max_memory_mb: float = 512.0
    max_cpu_percent: float = 80.0
    monitoring_interval: float = 10.0
    latency_threshold_ms: float = 100.0

@dataclass
class WebSocketMetrics:
    """WebSocket指标"""
    timestamp: datetime
    active_connections: int = 0
    total_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    average_latency: float = 0.0
    uptime: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

logger = logging.getLogger(__name__)


@dataclass
class ConnectionMetrics:
    """连接指标"""
    connection_id: str
    start_time: datetime
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    latency_samples: deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class SystemMetrics:
    """系统级指标"""
    active_connections: int = 0
    total_connections: int = 0
    messages_per_second: float = 0.0
    bytes_per_second: float = 0.0
    average_latency: float = 0.0
    error_rate: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0


class WebSocketMonitor:
    """WebSocket性能监控器"""
    
    def __init__(self, alert_config: AlertConfig):
        self.alert_config = alert_config
        self.connection_metrics: Dict[str, ConnectionMetrics] = {}
        self.system_metrics = SystemMetrics()
        self.alerts: List[Dict] = []
        self.alert_callbacks: List[Callable] = []
        
        # 统计窗口
        self.metrics_history = deque(maxlen=3600)  # 1小时的历史数据
        self.last_cleanup = datetime.now()
        
        # 监控任务
        self.monitoring_task: Optional[asyncio.Task] = None
        
    def start_monitoring(self):
        """启动监控"""
        if self.monitoring_task is None or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("WebSocket监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            logger.info("WebSocket监控已停止")
    
    def add_connection(self, connection_id: str):
        """添加连接"""
        if connection_id not in self.connection_metrics:
            self.connection_metrics[connection_id] = ConnectionMetrics(
                connection_id=connection_id,
                start_time=datetime.now()
            )
            self.system_metrics.total_connections += 1
            self.system_metrics.active_connections = len(self.connection_metrics)
    
    def remove_connection(self, connection_id: str):
        """移除连接"""
        if connection_id in self.connection_metrics:
            del self.connection_metrics[connection_id]
            self.system_metrics.active_connections = len(self.connection_metrics)
    
    def record_message_sent(self, connection_id: str, message_size: int):
        """记录发送消息"""
        if connection_id in self.connection_metrics:
            metrics = self.connection_metrics[connection_id]
            metrics.messages_sent += 1
            metrics.bytes_sent += message_size
            metrics.last_activity = datetime.now()
    
    def record_message_received(self, connection_id: str, message_size: int):
        """记录接收消息"""
        if connection_id in self.connection_metrics:
            metrics = self.connection_metrics[connection_id]
            metrics.messages_received += 1
            metrics.bytes_received += message_size
            metrics.last_activity = datetime.now()
    
    def record_error(self, connection_id: str, error_type: str):
        """记录错误"""
        if connection_id in self.connection_metrics:
            self.connection_metrics[connection_id].error_count += 1
        
        # 触发告警
        self._check_error_rate_alert(connection_id, error_type)
    
    def record_latency(self, connection_id: str, latency_ms: float):
        """记录延迟"""
        if connection_id in self.connection_metrics:
            self.connection_metrics[connection_id].latency_samples.append(latency_ms)
            self._check_latency_alert(connection_id, latency_ms)
    
    def get_current_metrics(self) -> WebSocketMetrics:
        """获取当前指标"""
        now = datetime.now()
        
        # 计算系统级指标
        total_messages_sent = sum(m.messages_sent for m in self.connection_metrics.values())
        total_messages_received = sum(m.messages_received for m in self.connection_metrics.values())
        total_errors = sum(m.error_count for m in self.connection_metrics.values())
        
        # 计算平均延迟
        all_latencies = []
        for metrics in self.connection_metrics.values():
            all_latencies.extend(metrics.latency_samples)
        
        avg_latency = statistics.mean(all_latencies) if all_latencies else 0.0
        
        return WebSocketMetrics(
            timestamp=now,
            active_connections=self.system_metrics.active_connections,
            total_connections=self.system_metrics.total_connections,
            messages_sent=total_messages_sent,
            messages_received=total_messages_received,
            errors=total_errors,
            average_latency=avg_latency,
            uptime=(now - min(m.start_time for m in self.connection_metrics.values())).total_seconds()
                     if self.connection_metrics else 0.0
        )
    
    def get_connection_details(self, connection_id: str) -> Optional[Dict]:
        """获取连接详细信息"""
        if connection_id not in self.connection_metrics:
            return None
        
        metrics = self.connection_metrics[connection_id]
        avg_latency = statistics.mean(metrics.latency_samples) if metrics.latency_samples else 0.0
        
        return {
            "connection_id": connection_id,
            "start_time": metrics.start_time.isoformat(),
            "duration": (datetime.now() - metrics.start_time).total_seconds(),
            "messages_sent": metrics.messages_sent,
            "messages_received": metrics.messages_received,
            "bytes_sent": metrics.bytes_sent,
            "bytes_received": metrics.bytes_received,
            "error_count": metrics.error_count,
            "average_latency": avg_latency,
            "last_activity": metrics.last_activity.isoformat()
        }
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)
    
    def _check_error_rate_alert(self, connection_id: str, error_type: str):
        """检查错误率告警"""
        if connection_id not in self.connection_metrics:
            return
        
        metrics = self.connection_metrics[connection_id]
        total_messages = metrics.messages_sent + metrics.messages_received
        
        if total_messages > 0:
            error_rate = metrics.error_count / total_messages
            if error_rate > self.alert_config.error_rate_threshold:
                self._trigger_alert(
                    AlertLevel.WARNING,
                    f"连接 {connection_id} 错误率过高: {error_rate:.2%}",
                    {"connection_id": connection_id, "error_type": error_type, "error_rate": error_rate}
                )
    
    def _check_latency_alert(self, connection_id: str, latency_ms: float):
        """检查延迟告警"""
        if latency_ms > self.alert_config.latency_threshold_ms:
            self._trigger_alert(
                AlertLevel.WARNING,
                f"连接 {connection_id} 延迟过高: {latency_ms:.2f}ms",
                {"connection_id": connection_id, "latency_ms": latency_ms}
            )
    
    def _check_connection_count_alert(self):
        """检查连接数告警"""
        if self.system_metrics.active_connections > self.alert_config.max_connections:
            self._trigger_alert(
                AlertLevel.CRITICAL,
                f"连接数过多: {self.system_metrics.active_connections}",
                {"active_connections": self.system_metrics.active_connections}
            )
    
    def _trigger_alert(self, level: AlertLevel, message: str, data: Dict):
        """触发告警"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
            "data": data
        }
        
        self.alerts.append(alert)
        logger.warning(f"告警触发: {message}")
        
        # 调用回调
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(alert))
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"告警回调失败: {e}")
    
    async def _monitoring_loop(self):
        """监控循环"""
        try:
            while True:
                await asyncio.sleep(self.alert_config.monitoring_interval)
                
                # 清理过期数据
                self._cleanup_old_data()
                
                # 检查告警
                self._check_connection_count_alert()
                
                # 记录系统指标
                metrics = self.get_current_metrics()
                self.metrics_history.append(metrics)
                
                # 日志记录
                logger.debug(f"系统指标: {metrics.model_dump_json()}")
                
        except asyncio.CancelledError:
            logger.info("监控循环已取消")
        except Exception as e:
            logger.error(f"监控循环错误: {e}")
    
    def _cleanup_old_data(self):
        """清理过期数据"""
        now = datetime.now()
        
        # 清理超过1小时无活动的连接
        inactive_connections = []
        for connection_id, metrics in self.connection_metrics.items():
            if now - metrics.last_activity > timedelta(hours=1):
                inactive_connections.append(connection_id)
        
        for connection_id in inactive_connections:
            self.remove_connection(connection_id)
            logger.debug(f"清理过期连接: {connection_id}")
    
    def get_metrics_summary(self) -> Dict:
        """获取指标摘要"""
        current = self.get_current_metrics()
        
        # 计算趋势
        if len(self.metrics_history) >= 2:
            recent = list(self.metrics_history)[-10:]  # 最近10个样本
            if len(recent) >= 2:
                latency_trend = statistics.mean(m.average_latency for m in recent[-5:]) - \
                              statistics.mean(m.average_latency for m in recent[:5])
            else:
                latency_trend = 0.0
        else:
            latency_trend = 0.0
        
        return {
            "current_metrics": current.model_dump(),
            "trends": {
                "latency_trend": latency_trend,
                "connection_growth": self.system_metrics.total_connections
            },
            "alerts_count": len(self.alerts),
            "recent_alerts": self.alerts[-5:] if self.alerts else []
        }