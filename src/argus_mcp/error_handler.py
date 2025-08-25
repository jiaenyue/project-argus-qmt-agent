"""
错误处理和恢复机制
实现自定义异常、错误恢复策略和故障转移功能
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any, Type
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import traceback
import json

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "authentication_error"
    SUBSCRIPTION_ERROR = "subscription_error"
    DATA_SOURCE_ERROR = "data_source_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    INTERNAL_ERROR = "internal_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class RecoveryStrategy(Enum):
    """恢复策略枚举"""
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAKER = "circuit_breaker"
    DEGRADE = "degrade"
    FAIL_FAST = "fail_fast"


@dataclass
class ErrorContext:
    """错误上下文"""
    error_type: ErrorType
    message: str
    connection_id: Optional[str] = None
    timestamp: datetime = None
    stack_trace: str = None
    metadata: Dict[str, Any] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class WebSocketError(Exception):
    """WebSocket基础异常"""
    
    def __init__(self, error_type: ErrorType, message: str, 
                 connection_id: str = None, metadata: Dict = None):
        super().__init__(message)
        self.error_type = error_type
        self.connection_id = connection_id
        self.metadata = metadata or {}


class ConnectionError(WebSocketError):
    """连接异常"""
    def __init__(self, message: str, connection_id: str = None):
        super().__init__(ErrorType.CONNECTION_ERROR, message, connection_id)


class AuthenticationError(WebSocketError):
    """认证异常"""
    def __init__(self, message: str, connection_id: str = None):
        super().__init__(ErrorType.AUTHENTICATION_ERROR, message, connection_id)


class SubscriptionError(WebSocketError):
    """订阅异常"""
    def __init__(self, message: str, connection_id: str = None):
        super().__init__(ErrorType.SUBSCRIPTION_ERROR, message, connection_id)


class DataSourceError(WebSocketError):
    """数据源异常"""
    def __init__(self, message: str, connection_id: str = None, source: str = None):
        metadata = {"source": source} if source else {}
        super().__init__(ErrorType.DATA_SOURCE_ERROR, message, connection_id, metadata)


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.last_failure_time: Dict[str, datetime] = {}
        self.circuit_states: Dict[str, str] = defaultdict(lambda: "closed")  # closed, open, half-open
        
    def should_allow_request(self, key: str) -> bool:
        """是否应该允许请求"""
        if self.circuit_states[key] == "closed":
            return True
        
        if self.circuit_states[key] == "open":
            if datetime.now() - self.last_failure_time[key] > timedelta(seconds=self.recovery_timeout):
                self.circuit_states[key] = "half-open"
                return True
            return False
        
        # half-open状态允许一个请求
        return True
    
    def record_success(self, key: str):
        """记录成功"""
        self.failure_counts[key] = 0
        self.circuit_states[key] = "closed"
    
    def record_failure(self, key: str):
        """记录失败"""
        self.failure_counts[key] += 1
        self.last_failure_time[key] = datetime.now()
        
        if self.failure_counts[key] >= self.failure_threshold:
            self.circuit_states[key] = "open"
            logger.warning(f"熔断器开启: {key}")
    
    def get_state(self, key: str) -> str:
        """获取熔断器状态"""
        return self.circuit_states[key]


class RetryPolicy:
    """重试策略"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, exponential: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential = exponential
    
    def get_delay(self, retry_count: int) -> float:
        """获取重试延迟"""
        if self.exponential:
            delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
        else:
            delay = min(self.base_delay * (retry_count + 1), self.max_delay)
        return delay
    
    def should_retry(self, error_type: ErrorType, retry_count: int) -> bool:
        """是否应该重试"""
        if retry_count >= self.max_retries:
            return False
        
        # 可重试的错误类型
        retryable_errors = {
            ErrorType.CONNECTION_ERROR,
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.DATA_SOURCE_ERROR
        }
        
        return error_type in retryable_errors


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, retry_policy: RetryPolicy = None, 
                 circuit_breaker: CircuitBreaker = None):
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.error_log: List[ErrorContext] = []
        self.error_callbacks: List[Callable] = []
        self.recovery_strategies: Dict[ErrorType, RecoveryStrategy] = {}
        
        # 默认恢复策略
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        """设置默认恢复策略"""
        self.recovery_strategies = {
            ErrorType.CONNECTION_ERROR: RecoveryStrategy.RETRY,
            ErrorType.NETWORK_ERROR: RecoveryStrategy.RETRY,
            ErrorType.TIMEOUT_ERROR: RecoveryStrategy.RETRY,
            ErrorType.DATA_SOURCE_ERROR: RecoveryStrategy.FALLBACK,
            ErrorType.AUTHENTICATION_ERROR: RecoveryStrategy.FAIL_FAST,
            ErrorType.VALIDATION_ERROR: RecoveryStrategy.FAIL_FAST,
            ErrorType.RESOURCE_EXHAUSTION: RecoveryStrategy.DEGRADE,
            ErrorType.RATE_LIMIT_ERROR: RecoveryStrategy.CIRCUIT_BREAKER,
            ErrorType.INTERNAL_ERROR: RecoveryStrategy.FAIL_FAST
        }
    
    def handle_error(self, error: WebSocketError, context: Dict = None) -> Dict[str, Any]:
        """处理错误"""
        error_context = ErrorContext(
            error_type=error.error_type,
            message=str(error),
            connection_id=error.connection_id,
            stack_trace=traceback.format_exc(),
            metadata=context or {}
        )
        
        # 记录错误
        self.error_log.append(error_context)
        if len(self.error_log) > 1000:  # 限制日志大小
            self.error_log.pop(0)
        
        # 记录到日志
        logger.error(f"WebSocket错误: {error_context.message}", extra={
            "error_type": error.error_type.value,
            "connection_id": error.connection_id,
            "metadata": error_context.metadata
        })
        
        # 执行恢复策略
        recovery_result = self._execute_recovery_strategy(error_context)
        
        # 触发回调
        self._trigger_callbacks(error_context, recovery_result)
        
        return recovery_result
    
    def _execute_recovery_strategy(self, error_context: ErrorContext) -> Dict[str, Any]:
        """执行恢复策略"""
        strategy = self.recovery_strategies.get(error_context.error_type, RecoveryStrategy.FAIL_FAST)
        
        if strategy == RecoveryStrategy.RETRY:
            return self._handle_retry(error_context)
        elif strategy == RecoveryStrategy.FALLBACK:
            return self._handle_fallback(error_context)
        elif strategy == RecoveryStrategy.CIRCUIT_BREAKER:
            return self._handle_circuit_breaker(error_context)
        elif strategy == RecoveryStrategy.DEGRADE:
            return self._handle_degrade(error_context)
        else:  # FAIL_FAST
            return self._handle_fail_fast(error_context)
    
    def _handle_retry(self, error_context: ErrorContext) -> Dict[str, Any]:
        """处理重试策略"""
        key = error_context.connection_id or "global"
        
        if not self.circuit_breaker.should_allow_request(key):
            return {
                "action": "circuit_breaker_open",
                "message": "熔断器开启，请求被拒绝",
                "circuit_state": self.circuit_breaker.get_state(key)
            }
        
        if self.retry_policy.should_retry(error_context.error_type, error_context.retry_count):
            delay = self.retry_policy.get_delay(error_context.retry_count)
            return {
                "action": "retry",
                "delay": delay,
                "retry_count": error_context.retry_count + 1,
                "max_retries": self.retry_policy.max_retries
            }
        
        self.circuit_breaker.record_failure(key)
        return {
            "action": "max_retries_exceeded",
            "message": "达到最大重试次数",
            "fallback_available": True
        }
    
    def _handle_fallback(self, error_context: ErrorContext) -> Dict[str, Any]:
        """处理降级策略"""
        fallback_actions = {
            ErrorType.DATA_SOURCE_ERROR: "使用缓存数据",
            ErrorType.RESOURCE_EXHAUSTION: "减少数据推送频率",
            ErrorType.CONNECTION_ERROR: "切换到备用服务器"
        }
        
        action = fallback_actions.get(error_context.error_type, "使用默认响应")
        return {
            "action": "fallback",
            "fallback_action": action,
            "message": f"已启用降级策略: {action}"
        }
    
    def _handle_circuit_breaker(self, error_context: ErrorContext) -> Dict[str, Any]:
        """处理熔断器策略"""
        key = error_context.connection_id or "global"
        
        if not self.circuit_breaker.should_allow_request(key):
            return {
                "action": "circuit_breaker_open",
                "message": "熔断器开启，请求被拒绝",
                "circuit_state": self.circuit_breaker.get_state(key),
                "recovery_time": self.circuit_breaker.recovery_timeout
            }
        
        return {
            "action": "circuit_breaker_closed",
            "message": "熔断器关闭，允许请求"
        }
    
    def _handle_degrade(self, error_context: ErrorContext) -> Dict[str, Any]:
        """处理服务降级"""
        degrade_actions = {
            ErrorType.RESOURCE_EXHAUSTION: {
                "reduce_data_frequency": True,
                "disable_non_critical_features": True,
                "use_simplified_protocol": True
            }
        }
        
        actions = degrade_actions.get(error_context.error_type, {})
        return {
            "action": "degrade",
            "degrade_actions": actions,
            "message": "服务已降级以维持基本功能"
        }
    
    def _handle_fail_fast(self, error_context: ErrorContext) -> Dict[str, Any]:
        """处理快速失败"""
        return {
            "action": "fail_fast",
            "message": "错误无法恢复，立即失败",
            "error_type": error_context.error_type.value,
            "should_disconnect": error_context.error_type in [
                ErrorType.AUTHENTICATION_ERROR,
                ErrorType.VALIDATION_ERROR
            ]
        }
    
    def record_success(self, connection_id: str = None):
        """记录成功"""
        key = connection_id or "global"
        self.circuit_breaker.record_success(key)
    
    def register_callback(self, callback: Callable):
        """注册错误回调"""
        self.error_callbacks.append(callback)
    
    def _trigger_callbacks(self, error_context: ErrorContext, recovery_result: Dict):
        """触发回调"""
        for callback in self.error_callbacks:
            try:
                callback(error_context, recovery_result)
            except Exception as e:
                logger.error(f"错误回调失败: {e}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        if not self.error_log:
            return {"message": "无错误记录"}
        
        # 按类型统计错误
        error_counts = {}
        for error in self.error_log:
            error_type = error.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        # 最近错误
        recent_errors = [
            {
                "timestamp": error.timestamp.isoformat(),
                "type": error.error_type.value,
                "message": error.message,
                "connection_id": error.connection_id
            }
            for error in self.error_log[-10:]
        ]
        
        return {
            "total_errors": len(self.error_log),
            "error_counts": error_counts,
            "recent_errors": recent_errors,
            "circuit_breaker_states": dict(self.circuit_breaker.circuit_states)
        }
    
    def get_connection_errors(self, connection_id: str) -> List[ErrorContext]:
        """获取特定连接的错误"""
        return [
            error for error in self.error_log
            if error.connection_id == connection_id
        ]
    
    def clear_errors(self, connection_id: str = None):
        """清除错误记录"""
        if connection_id:
            self.error_log = [
                error for error in self.error_log
                if error.connection_id != connection_id
            ]
        else:
            self.error_log.clear()
    
    def update_recovery_strategy(self, error_type: ErrorType, strategy: RecoveryStrategy):
        """更新恢复策略"""
        self.recovery_strategies[error_type] = strategy
        logger.info(f"更新恢复策略: {error_type.value} -> {strategy.value}")


class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
        self.recovery_tasks: Dict[str, asyncio.Task] = {}
        
    async def handle_with_recovery(self, operation: Callable, *args, **kwargs):
        """执行带恢复的操作"""
        try:
            result = await operation(*args, **kwargs)
            self.error_handler.record_success(kwargs.get('connection_id'))
            return {"success": True, "result": result}
        
        except WebSocketError as e:
            recovery_result = self.error_handler.handle_error(e, kwargs)
            
            if recovery_result["action"] == "retry":
                return await self._retry_operation(operation, *args, **kwargs)
            
            return {"success": False, "recovery": recovery_result}
        
        except Exception as e:
            # 包装为WebSocketError
            wrapped_error = WebSocketError(
                ErrorType.INTERNAL_ERROR,
                str(e),
                kwargs.get('connection_id')
            )
            recovery_result = self.error_handler.handle_error(wrapped_error, kwargs)
            return {"success": False, "recovery": recovery_result}
    
    async def _retry_operation(self, operation: Callable, *args, **kwargs):
        """重试操作"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(2 ** attempt)  # 指数退避
                result = await operation(*args, **kwargs)
                return {"success": True, "result": result, "retry_count": attempt + 1}
            except Exception as e:
                if attempt == max_retries - 1:
                    return {"success": False, "error": str(e), "retry_count": attempt + 1}
        
        return {"success": False, "error": "Max retries exceeded"}