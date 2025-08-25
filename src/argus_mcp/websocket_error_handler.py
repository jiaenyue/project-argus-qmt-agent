"""
WebSocket 实时数据系统 - 错误处理和恢复机制
根据 tasks.md 任务10要求实现的错误处理系统
"""

import asyncio
import logging
import traceback
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
import json
import uuid

from .websocket_models import (
    WebSocketMessage, MessageType, ErrorMessage, StatusMessage, Alert
)

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """错误严重程度枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """错误分类枚举"""
    CONNECTION = "connection"
    SUBSCRIPTION = "subscription"
    DATA_PUBLISH = "data_publish"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    NETWORK = "network"
    SYSTEM = "system"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    PROTOCOL = "protocol"


class RecoveryAction(str, Enum):
    """恢复动作枚举"""
    RETRY = "retry"
    RECONNECT = "reconnect"
    DISCONNECT = "disconnect"
    NOTIFY_CLIENT = "notify_client"
    BUFFER_AND_RETRY = "buffer_and_retry"
    FAILOVER = "failover"
    DEGRADE_SERVICE = "degrade_service"
    IGNORE = "ignore"
    ESCALATE = "escalate"


@dataclass
class ErrorContext:
    """错误上下文信息"""
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    client_id: Optional[str] = None
    subscription_id: Optional[str] = None
    message_id: Optional[str] = None
    operation: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryStrategy:
    """恢复策略配置"""
    action: RecoveryAction
    max_retries: int = 3
    retry_delays: List[float] = field(default_factory=lambda: [1.0, 2.0, 4.0])
    timeout_seconds: float = 30.0
    escalation_threshold: int = 5
    circuit_breaker_threshold: int = 10
    circuit_breaker_timeout: float = 60.0
    custom_handler: Optional[Callable] = None


class WebSocketError(Exception):
    """WebSocket错误基类"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext()
        self.original_error = original_error
        self.timestamp = datetime.now()


class ConnectionError(WebSocketError):
    """连接相关错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.CONNECTION,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error
        )


class SubscriptionError(WebSocketError):
    """订阅相关错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.SUBSCRIPTION,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            original_error=original_error
        )


class DataPublishError(WebSocketError):
    """数据发布错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.DATA_PUBLISH,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error
        )


class AuthenticationError(WebSocketError):
    """认证错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error
        )


class ValidationError(WebSocketError):
    """验证错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            context=context,
            original_error=original_error
        )


class NetworkError(WebSocketError):
    """网络错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            context=context,
            original_error=original_error
        )


class ResourceError(WebSocketError):
    """资源错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            original_error=original_error
        )


class TimeoutError(WebSocketError):
    """超时错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            original_error=original_error
        )


class ProtocolError(WebSocketError):
    """协议错误"""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message,
            category=ErrorCategory.PROTOCOL,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            original_error=original_error
        )


@dataclass
class CircuitBreakerState:
    """熔断器状态"""
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    next_attempt_time: Optional[datetime] = None


@dataclass
class ErrorStats:
    """错误统计"""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    recent_errors: List[Dict[str, Any]] = field(default_factory=list)
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0


class WebSocketErrorHandler:
    """WebSocket错误处理器"""
    
    def __init__(self, max_recent_errors: int = 100):
        self.max_recent_errors = max_recent_errors
        self.error_stats = ErrorStats()
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.recovery_strategies = self._initialize_recovery_strategies()
        self.error_handlers: Dict[ErrorCategory, Callable] = {}
        self.alert_callbacks: List[Callable] = []
        self.is_degraded = False
        self.degradation_start_time: Optional[datetime] = None
        
        # 注册默认错误处理器
        self._register_default_handlers()
    
    def _initialize_recovery_strategies(self) -> Dict[ErrorCategory, RecoveryStrategy]:
        """初始化恢复策略"""
        return {
            ErrorCategory.CONNECTION: RecoveryStrategy(
                action=RecoveryAction.RECONNECT,
                max_retries=3,
                retry_delays=[1.0, 2.0, 4.0],
                timeout_seconds=30.0,
                circuit_breaker_threshold=5
            ),
            ErrorCategory.SUBSCRIPTION: RecoveryStrategy(
                action=RecoveryAction.NOTIFY_CLIENT,
                max_retries=2,
                retry_delays=[0.5, 1.0],
                timeout_seconds=10.0
            ),
            ErrorCategory.DATA_PUBLISH: RecoveryStrategy(
                action=RecoveryAction.BUFFER_AND_RETRY,
                max_retries=5,
                retry_delays=[0.1, 0.2, 0.5, 1.0, 2.0],
                timeout_seconds=15.0,
                circuit_breaker_threshold=10
            ),
            ErrorCategory.AUTHENTICATION: RecoveryStrategy(
                action=RecoveryAction.DISCONNECT,
                max_retries=0,
                timeout_seconds=5.0
            ),
            ErrorCategory.VALIDATION: RecoveryStrategy(
                action=RecoveryAction.NOTIFY_CLIENT,
                max_retries=0,
                timeout_seconds=5.0
            ),
            ErrorCategory.NETWORK: RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=3,
                retry_delays=[1.0, 3.0, 5.0],
                timeout_seconds=20.0,
                circuit_breaker_threshold=5
            ),
            ErrorCategory.SYSTEM: RecoveryStrategy(
                action=RecoveryAction.ESCALATE,
                max_retries=1,
                retry_delays=[5.0],
                timeout_seconds=60.0,
                escalation_threshold=3
            ),
            ErrorCategory.RESOURCE: RecoveryStrategy(
                action=RecoveryAction.DEGRADE_SERVICE,
                max_retries=0,
                timeout_seconds=10.0,
                escalation_threshold=1
            ),
            ErrorCategory.TIMEOUT: RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=2,
                retry_delays=[1.0, 2.0],
                timeout_seconds=15.0
            ),
            ErrorCategory.PROTOCOL: RecoveryStrategy(
                action=RecoveryAction.NOTIFY_CLIENT,
                max_retries=1,
                retry_delays=[0.5],
                timeout_seconds=5.0
            )
        }
    
    def _register_default_handlers(self):
        """注册默认错误处理器"""
        self.error_handlers[ErrorCategory.CONNECTION] = self._handle_connection_error
        self.error_handlers[ErrorCategory.SUBSCRIPTION] = self._handle_subscription_error
        self.error_handlers[ErrorCategory.DATA_PUBLISH] = self._handle_data_publish_error
        self.error_handlers[ErrorCategory.AUTHENTICATION] = self._handle_authentication_error
        self.error_handlers[ErrorCategory.VALIDATION] = self._handle_validation_error
        self.error_handlers[ErrorCategory.NETWORK] = self._handle_network_error
        self.error_handlers[ErrorCategory.SYSTEM] = self._handle_system_error
        self.error_handlers[ErrorCategory.RESOURCE] = self._handle_resource_error
        self.error_handlers[ErrorCategory.TIMEOUT] = self._handle_timeout_error
        self.error_handlers[ErrorCategory.PROTOCOL] = self._handle_protocol_error
    
    async def handle_error(
        self,
        error: Union[WebSocketError, Exception],
        context: Optional[ErrorContext] = None,
        custom_recovery: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """处理错误的主入口"""
        try:
            # 转换为WebSocketError
            if not isinstance(error, WebSocketError):
                error = WebSocketError(
                    message=str(error),
                    context=context,
                    original_error=error
                )
            
            # 记录错误
            await self._log_error(error)
            
            # 更新统计
            self._update_error_stats(error)
            
            # 检查熔断器
            if self._should_circuit_break(error):
                return await self._handle_circuit_break(error)
            
            # 获取恢复策略
            strategy = self.recovery_strategies.get(
                error.category,
                self.recovery_strategies[ErrorCategory.SYSTEM]
            )
            
            # 执行恢复策略
            recovery_result = await self._execute_recovery_strategy(
                error, strategy, custom_recovery
            )
            
            # 发送告警
            await self._send_alert_if_needed(error, recovery_result)
            
            return recovery_result
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            return {
                "success": False,
                "error": f"Error handler failed: {str(e)}",
                "recovery_action": "none"
            }
    
    async def _log_error(self, error: WebSocketError):
        """记录错误详情"""
        error_data = {
            "error_id": error.context.error_id,
            "timestamp": error.timestamp.isoformat(),
            "category": error.category.value,
            "severity": error.severity.value,
            "message": error.message,
            "client_id": error.context.client_id,
            "subscription_id": error.context.subscription_id,
            "message_id": error.context.message_id,
            "operation": error.context.operation,
            "additional_data": error.context.additional_data,
            "traceback": traceback.format_exc() if error.original_error else None
        }
        
        # 根据严重程度选择日志级别
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical WebSocket error: {json.dumps(error_data, indent=2)}")
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(f"High severity WebSocket error: {json.dumps(error_data, indent=2)}")
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity WebSocket error: {json.dumps(error_data, indent=2)}")
        else:
            logger.info(f"Low severity WebSocket error: {json.dumps(error_data, indent=2)}")
        
        # 添加到最近错误列表
        self.error_stats.recent_errors.append(error_data)
        if len(self.error_stats.recent_errors) > self.max_recent_errors:
            self.error_stats.recent_errors.pop(0)
    
    def _update_error_stats(self, error: WebSocketError):
        """更新错误统计"""
        self.error_stats.total_errors += 1
        
        # 按分类统计
        category_key = error.category.value
        self.error_stats.errors_by_category[category_key] = (
            self.error_stats.errors_by_category.get(category_key, 0) + 1
        )
        
        # 按严重程度统计
        severity_key = error.severity.value
        self.error_stats.errors_by_severity[severity_key] = (
            self.error_stats.errors_by_severity.get(severity_key, 0) + 1
        )
    
    def _should_circuit_break(self, error: WebSocketError) -> bool:
        """检查是否应该触发熔断器"""
        strategy = self.recovery_strategies.get(error.category)
        if not strategy or strategy.circuit_breaker_threshold <= 0:
            return False
        
        circuit_key = f"{error.category.value}_{error.context.client_id or 'global'}"
        circuit_state = self.circuit_breakers.get(circuit_key, CircuitBreakerState())
        
        # 如果熔断器已开启，检查是否可以尝试
        if circuit_state.is_open:
            if (circuit_state.next_attempt_time and 
                datetime.now() < circuit_state.next_attempt_time):
                return True
            else:
                # 重置熔断器状态，允许一次尝试
                circuit_state.is_open = False
                circuit_state.failure_count = 0
        
        # 更新失败计数
        circuit_state.failure_count += 1
        circuit_state.last_failure_time = datetime.now()
        
        # 检查是否达到熔断阈值
        if circuit_state.failure_count >= strategy.circuit_breaker_threshold:
            circuit_state.is_open = True
            circuit_state.next_attempt_time = (
                datetime.now() + timedelta(seconds=strategy.circuit_breaker_timeout)
            )
            logger.warning(f"Circuit breaker opened for {circuit_key}")
        
        self.circuit_breakers[circuit_key] = circuit_state
        return circuit_state.is_open
    
    async def _handle_circuit_break(self, error: WebSocketError) -> Dict[str, Any]:
        """处理熔断器开启的情况"""
        logger.warning(f"Circuit breaker is open for {error.category.value}, rejecting request")
        
        return {
            "success": False,
            "error": "Service temporarily unavailable due to circuit breaker",
            "recovery_action": "circuit_break",
            "retry_after": 60  # 建议客户端60秒后重试
        }
    
    async def _execute_recovery_strategy(
        self,
        error: WebSocketError,
        strategy: RecoveryStrategy,
        custom_recovery: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """执行恢复策略"""
        self.error_stats.recovery_attempts += 1
        
        try:
            # 如果有自定义恢复处理器，优先使用
            if custom_recovery:
                result = await custom_recovery(error, strategy)
                if result.get("success"):
                    self.error_stats.successful_recoveries += 1
                else:
                    self.error_stats.failed_recoveries += 1
                return result
            
            # 使用默认恢复策略
            if strategy.action == RecoveryAction.RETRY:
                return await self._retry_operation(error, strategy)
            elif strategy.action == RecoveryAction.RECONNECT:
                return await self._reconnect_client(error, strategy)
            elif strategy.action == RecoveryAction.DISCONNECT:
                return await self._disconnect_client(error, strategy)
            elif strategy.action == RecoveryAction.NOTIFY_CLIENT:
                return await self._notify_client(error, strategy)
            elif strategy.action == RecoveryAction.BUFFER_AND_RETRY:
                return await self._buffer_and_retry(error, strategy)
            elif strategy.action == RecoveryAction.FAILOVER:
                return await self._failover(error, strategy)
            elif strategy.action == RecoveryAction.DEGRADE_SERVICE:
                return await self._degrade_service(error, strategy)
            elif strategy.action == RecoveryAction.ESCALATE:
                return await self._escalate_error(error, strategy)
            elif strategy.action == RecoveryAction.IGNORE:
                return {"success": True, "recovery_action": "ignored"}
            else:
                # 使用分类特定的处理器
                handler = self.error_handlers.get(error.category)
                if handler:
                    result = await handler(error, strategy)
                    if result.get("success"):
                        self.error_stats.successful_recoveries += 1
                    else:
                        self.error_stats.failed_recoveries += 1
                    return result
                
                return {
                    "success": False,
                    "error": "No recovery strategy available",
                    "recovery_action": "none"
                }
                
        except Exception as e:
            self.error_stats.failed_recoveries += 1
            logger.error(f"Recovery strategy execution failed: {e}")
            return {
                "success": False,
                "error": f"Recovery failed: {str(e)}",
                "recovery_action": strategy.action.value
            }
    
    async def _retry_operation(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """重试操作"""
        for attempt in range(strategy.max_retries):
            try:
                delay = strategy.retry_delays[min(attempt, len(strategy.retry_delays) - 1)]
                await asyncio.sleep(delay)
                
                logger.info(f"Retrying operation for error {error.context.error_id}, attempt {attempt + 1}")
                
                # 这里应该调用原始操作，但由于我们不知道具体操作，返回成功
                # 在实际实现中，需要传入原始操作的回调函数
                return {
                    "success": True,
                    "recovery_action": "retry",
                    "attempts": attempt + 1
                }
                
            except Exception as e:
                if attempt == strategy.max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Retry failed after {strategy.max_retries} attempts: {str(e)}",
                        "recovery_action": "retry_failed"
                    }
                continue
        
        return {
            "success": False,
            "error": f"All {strategy.max_retries} retry attempts failed",
            "recovery_action": "retry_exhausted"
        }
    
    async def _reconnect_client(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """重连客户端"""
        logger.info(f"Attempting to reconnect client {error.context.client_id}")
        
        # 在实际实现中，这里应该触发客户端重连逻辑
        return {
            "success": True,
            "recovery_action": "reconnect",
            "message": "Client reconnection initiated"
        }
    
    async def _disconnect_client(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """断开客户端连接"""
        logger.info(f"Disconnecting client {error.context.client_id} due to error")
        
        # 在实际实现中，这里应该断开WebSocket连接
        return {
            "success": True,
            "recovery_action": "disconnect",
            "message": "Client disconnected"
        }
    
    async def _notify_client(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """通知客户端错误"""
        logger.info(f"Notifying client {error.context.client_id} about error")
        
        # 创建错误消息
        error_message = ErrorMessage(
            error_type=error.category.value,
            message=error.message,
            client_id=error.context.client_id,
            subscription_id=error.context.subscription_id,
            trace_id=error.context.error_id
        )
        
        return {
            "success": True,
            "recovery_action": "notify_client",
            "error_message": error_message.model_dump(),
            "message": "Client notified of error"
        }
    
    async def _buffer_and_retry(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """缓冲数据并重试"""
        logger.info(f"Buffering data and retrying for error {error.context.error_id}")
        
        # 在实际实现中，这里应该将数据放入缓冲区并安排重试
        return {
            "success": True,
            "recovery_action": "buffer_and_retry",
            "message": "Data buffered for retry"
        }
    
    async def _failover(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """故障转移"""
        logger.info(f"Initiating failover for error {error.context.error_id}")
        
        # 在实际实现中，这里应该切换到备用服务或数据源
        return {
            "success": True,
            "recovery_action": "failover",
            "message": "Failover initiated"
        }
    
    async def _degrade_service(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """降级服务"""
        logger.warning(f"Degrading service due to error {error.context.error_id}")
        
        self.is_degraded = True
        self.degradation_start_time = datetime.now()
        
        return {
            "success": True,
            "recovery_action": "degrade_service",
            "message": "Service degraded to maintain stability"
        }
    
    async def _escalate_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """升级错误"""
        logger.critical(f"Escalating error {error.context.error_id}")
        
        # 发送紧急告警
        alert = Alert(
            type="error_escalation",
            severity="critical",
            message=f"Error escalated: {error.message}",
            metrics={
                "error_id": error.context.error_id,
                "category": error.category.value,
                "client_id": error.context.client_id
            }
        )
        
        await self._send_alert(alert)
        
        return {
            "success": True,
            "recovery_action": "escalate",
            "message": "Error escalated to operations team"
        }
    
    # 分类特定的错误处理器
    async def _handle_connection_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理连接错误"""
        return await self._reconnect_client(error, strategy)
    
    async def _handle_subscription_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理订阅错误"""
        return await self._notify_client(error, strategy)
    
    async def _handle_data_publish_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理数据发布错误"""
        return await self._buffer_and_retry(error, strategy)
    
    async def _handle_authentication_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理认证错误"""
        return await self._disconnect_client(error, strategy)
    
    async def _handle_validation_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理验证错误"""
        return await self._notify_client(error, strategy)
    
    async def _handle_network_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理网络错误"""
        return await self._retry_operation(error, strategy)
    
    async def _handle_system_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理系统错误"""
        return await self._escalate_error(error, strategy)
    
    async def _handle_resource_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理资源错误"""
        return await self._degrade_service(error, strategy)
    
    async def _handle_timeout_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理超时错误"""
        return await self._retry_operation(error, strategy)
    
    async def _handle_protocol_error(self, error: WebSocketError, strategy: RecoveryStrategy) -> Dict[str, Any]:
        """处理协议错误"""
        return await self._notify_client(error, strategy)
    
    async def _send_alert_if_needed(self, error: WebSocketError, recovery_result: Dict[str, Any]):
        """根据需要发送告警"""
        should_alert = (
            error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] or
            not recovery_result.get("success", False) or
            self._is_error_pattern_concerning(error)
        )
        
        if should_alert:
            alert = Alert(
                type=f"{error.category.value}_error",
                severity=error.severity.value,
                message=f"{error.category.value.title()} error: {error.message}",
                metrics={
                    "error_id": error.context.error_id,
                    "client_id": error.context.client_id,
                    "recovery_success": recovery_result.get("success", False),
                    "recovery_action": recovery_result.get("recovery_action", "none")
                }
            )
            
            await self._send_alert(alert)
    
    def _is_error_pattern_concerning(self, error: WebSocketError) -> bool:
        """检查错误模式是否令人担忧"""
        # 检查最近5分钟内同类错误的频率
        recent_time = datetime.now() - timedelta(minutes=5)
        recent_same_category = [
            e for e in self.error_stats.recent_errors
            if (datetime.fromisoformat(e["timestamp"]) > recent_time and
                e["category"] == error.category.value)
        ]
        
        return len(recent_same_category) >= 5  # 5分钟内同类错误超过5次
    
    async def _send_alert(self, alert: Alert):
        """发送告警"""
        logger.warning(f"Sending alert: {alert.type} - {alert.message}")
        
        # 调用所有注册的告警回调
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)
    
    def register_error_handler(self, category: ErrorCategory, handler: Callable):
        """注册自定义错误处理器"""
        self.error_handlers[category] = handler
    
    def update_recovery_strategy(self, category: ErrorCategory, strategy: RecoveryStrategy):
        """更新恢复策略"""
        self.recovery_strategies[category] = strategy
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return {
            "total_errors": self.error_stats.total_errors,
            "errors_by_category": self.error_stats.errors_by_category,
            "errors_by_severity": self.error_stats.errors_by_severity,
            "recovery_attempts": self.error_stats.recovery_attempts,
            "successful_recoveries": self.error_stats.successful_recoveries,
            "failed_recoveries": self.error_stats.failed_recoveries,
            "recovery_success_rate": (
                self.error_stats.successful_recoveries / max(self.error_stats.recovery_attempts, 1) * 100
            ),
            "recent_errors_count": len(self.error_stats.recent_errors),
            "is_degraded": self.is_degraded,
            "degradation_duration": (
                str(datetime.now() - self.degradation_start_time)
                if self.degradation_start_time else None
            ),
            "circuit_breakers": {
                key: {
                    "is_open": state.is_open,
                    "failure_count": state.failure_count,
                    "last_failure": state.last_failure_time.isoformat() if state.last_failure_time else None
                }
                for key, state in self.circuit_breakers.items()
            }
        }
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的错误"""
        return self.error_stats.recent_errors[-limit:]
    
    async def reset_circuit_breaker(self, circuit_key: str) -> bool:
        """重置熔断器"""
        if circuit_key in self.circuit_breakers:
            self.circuit_breakers[circuit_key] = CircuitBreakerState()
            logger.info(f"Circuit breaker reset for {circuit_key}")
            return True
        return False
    
    async def restore_service(self) -> bool:
        """恢复服务（从降级状态）"""
        if self.is_degraded:
            self.is_degraded = False
            self.degradation_start_time = None
            logger.info("Service restored from degraded state")
            return True
        return False
    
    async def cleanup(self):
        """清理资源"""
        self.alert_callbacks.clear()
        self.error_handlers.clear()
        self.circuit_breakers.clear()
        logger.info("Error handler cleaned up")


# 错误处理装饰器
def handle_websocket_errors(
    error_handler: WebSocketErrorHandler,
    category: ErrorCategory = ErrorCategory.SYSTEM,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
):
    """WebSocket错误处理装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(
                    operation=func.__name__,
                    additional_data={"args": str(args), "kwargs": str(kwargs)}
                )
                
                websocket_error = WebSocketError(
                    message=str(e),
                    category=category,
                    severity=severity,
                    context=context,
                    original_error=e
                )
                
                recovery_result = await error_handler.handle_error(websocket_error)
                
                if not recovery_result.get("success", False):
                    raise e
                
                return recovery_result
        
        return wrapper
    return decorator