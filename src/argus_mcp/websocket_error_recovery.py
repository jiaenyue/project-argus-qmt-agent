"""
WebSocket 实时数据系统 - 错误恢复服务
集成错误处理器与现有WebSocket组件的恢复服务
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

from .websocket_error_handler import (
    WebSocketErrorHandler, WebSocketError, ConnectionError, SubscriptionError,
    DataPublishError, NetworkError, TimeoutError, ErrorContext, ErrorCategory,
    ErrorSeverity, RecoveryAction
)
from .websocket_models import (
    WebSocketMessage, MessageType, ErrorMessage, StatusMessage, Alert
)

logger = logging.getLogger(__name__)


@dataclass
class RecoveryContext:
    """恢复上下文"""
    client_id: Optional[str] = None
    websocket: Optional[Any] = None  # WebSocket连接对象
    connection_manager: Optional[Any] = None
    subscription_manager: Optional[Any] = None
    data_publisher: Optional[Any] = None
    message_router: Optional[Any] = None
    original_operation: Optional[Callable] = None
    operation_args: tuple = field(default_factory=tuple)
    operation_kwargs: Dict[str, Any] = field(default_factory=dict)


class WebSocketErrorRecoveryService:
    """WebSocket错误恢复服务"""
    
    def __init__(
        self,
        error_handler: WebSocketErrorHandler,
        connection_manager=None,
        subscription_manager=None,
        data_publisher=None,
        message_router=None
    ):
        self.error_handler = error_handler
        self.connection_manager = connection_manager
        self.subscription_manager = subscription_manager
        self.data_publisher = data_publisher
        self.message_router = message_router
        
        # 注册恢复处理器
        self._register_recovery_handlers()
        
        # 恢复统计
        self.recovery_stats = {
            "successful_reconnections": 0,
            "failed_reconnections": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "clients_disconnected": 0,
            "services_degraded": 0,
            "failovers_executed": 0
        }
        
        # 缓冲区用于存储失败的操作
        self.operation_buffer: List[Dict[str, Any]] = []
        self.max_buffer_size = 10000
        
        # 故障转移配置
        self.failover_endpoints = []
        self.current_endpoint_index = 0
        
        logger.info("WebSocket Error Recovery Service initialized")
    
    def _register_recovery_handlers(self):
        """注册恢复处理器"""
        # 注册自定义错误处理器
        self.error_handler.register_error_handler(
            ErrorCategory.CONNECTION, self._handle_connection_recovery
        )
        self.error_handler.register_error_handler(
            ErrorCategory.SUBSCRIPTION, self._handle_subscription_recovery
        )
        self.error_handler.register_error_handler(
            ErrorCategory.DATA_PUBLISH, self._handle_data_publish_recovery
        )
        self.error_handler.register_error_handler(
            ErrorCategory.NETWORK, self._handle_network_recovery
        )
        self.error_handler.register_error_handler(
            ErrorCategory.TIMEOUT, self._handle_timeout_recovery
        )
        
        logger.info("Recovery handlers registered")
    
    async def handle_error_with_recovery(
        self,
        error: Exception,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """处理错误并执行恢复"""
        try:
            # 创建错误上下文
            error_context = ErrorContext(
                client_id=recovery_context.client_id,
                operation=recovery_context.original_operation.__name__ if recovery_context.original_operation else None,
                additional_data={
                    "has_websocket": recovery_context.websocket is not None,
                    "has_connection_manager": recovery_context.connection_manager is not None,
                    "has_subscription_manager": recovery_context.subscription_manager is not None
                }
            )
            
            # 转换为WebSocket错误
            websocket_error = self._convert_to_websocket_error(error, error_context)
            
            # 使用错误处理器处理错误
            result = await self.error_handler.handle_error(
                websocket_error,
                context=error_context,
                custom_recovery=lambda e, s: self._execute_recovery_with_context(e, s, recovery_context)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in recovery service: {e}")
            return {
                "success": False,
                "error": f"Recovery service error: {str(e)}",
                "recovery_action": "none"
            }
    
    def _convert_to_websocket_error(self, error: Exception, context: ErrorContext) -> WebSocketError:
        """将普通异常转换为WebSocket错误"""
        error_message = str(error)
        
        # 根据错误类型和消息内容推断错误分类
        if "connection" in error_message.lower() or "websocket" in error_message.lower():
            return ConnectionError(error_message, context, error)
        elif "subscription" in error_message.lower() or "subscribe" in error_message.lower():
            return SubscriptionError(error_message, context, error)
        elif "publish" in error_message.lower() or "data" in error_message.lower():
            return DataPublishError(error_message, context, error)
        elif "network" in error_message.lower() or "timeout" in error_message.lower():
            return NetworkError(error_message, context, error)
        elif "timeout" in error_message.lower():
            return TimeoutError(error_message, context, error)
        else:
            return WebSocketError(error_message, ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM, context, error)
    
    async def _execute_recovery_with_context(
        self,
        error: WebSocketError,
        strategy,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在恢复上下文中执行恢复策略"""
        try:
            if strategy.action == RecoveryAction.RECONNECT:
                return await self._reconnect_with_context(error, recovery_context)
            elif strategy.action == RecoveryAction.RETRY:
                return await self._retry_with_context(error, strategy, recovery_context)
            elif strategy.action == RecoveryAction.DISCONNECT:
                return await self._disconnect_with_context(error, recovery_context)
            elif strategy.action == RecoveryAction.NOTIFY_CLIENT:
                return await self._notify_client_with_context(error, recovery_context)
            elif strategy.action == RecoveryAction.BUFFER_AND_RETRY:
                return await self._buffer_and_retry_with_context(error, strategy, recovery_context)
            elif strategy.action == RecoveryAction.FAILOVER:
                return await self._failover_with_context(error, recovery_context)
            elif strategy.action == RecoveryAction.DEGRADE_SERVICE:
                return await self._degrade_service_with_context(error, recovery_context)
            else:
                return {
                    "success": False,
                    "error": f"Unknown recovery action: {strategy.action}",
                    "recovery_action": strategy.action.value
                }
                
        except Exception as e:
            logger.error(f"Recovery execution failed: {e}")
            return {
                "success": False,
                "error": f"Recovery execution failed: {str(e)}",
                "recovery_action": strategy.action.value
            }
    
    async def _reconnect_with_context(
        self,
        error: WebSocketError,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在上下文中执行重连"""
        try:
            client_id = recovery_context.client_id
            
            if not client_id or not self.connection_manager:
                return {
                    "success": False,
                    "error": "Missing client_id or connection_manager for reconnection",
                    "recovery_action": "reconnect"
                }
            
            logger.info(f"Attempting to reconnect client {client_id}")
            
            # 清理现有连接
            await self.connection_manager.unregister_connection(client_id)
            
            # 等待一小段时间
            await asyncio.sleep(1.0)
            
            # 尝试重新建立连接（这里需要根据实际的连接管理器API调整）
            # 在实际实现中，可能需要触发客户端重连或使用备用连接
            
            self.recovery_stats["successful_reconnections"] += 1
            
            return {
                "success": True,
                "recovery_action": "reconnect",
                "message": f"Client {client_id} reconnection initiated"
            }
            
        except Exception as e:
            self.recovery_stats["failed_reconnections"] += 1
            logger.error(f"Reconnection failed for {recovery_context.client_id}: {e}")
            return {
                "success": False,
                "error": f"Reconnection failed: {str(e)}",
                "recovery_action": "reconnect"
            }
    
    async def _retry_with_context(
        self,
        error: WebSocketError,
        strategy,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在上下文中执行重试"""
        if not recovery_context.original_operation:
            return {
                "success": False,
                "error": "No original operation to retry",
                "recovery_action": "retry"
            }
        
        for attempt in range(strategy.max_retries):
            try:
                delay = strategy.retry_delays[min(attempt, len(strategy.retry_delays) - 1)]
                await asyncio.sleep(delay)
                
                logger.info(f"Retrying operation {recovery_context.original_operation.__name__}, attempt {attempt + 1}")
                
                # 执行原始操作
                result = await recovery_context.original_operation(
                    *recovery_context.operation_args,
                    **recovery_context.operation_kwargs
                )
                
                self.recovery_stats["successful_retries"] += 1
                
                return {
                    "success": True,
                    "recovery_action": "retry",
                    "attempts": attempt + 1,
                    "result": result
                }
                
            except Exception as e:
                if attempt == strategy.max_retries - 1:
                    self.recovery_stats["failed_retries"] += 1
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
    
    async def _disconnect_with_context(
        self,
        error: WebSocketError,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在上下文中断开连接"""
        try:
            client_id = recovery_context.client_id
            
            if client_id and self.connection_manager:
                await self.connection_manager.unregister_connection(client_id)
                
                # 清理订阅
                if self.subscription_manager:
                    await self.subscription_manager.unsubscribe_all(client_id)
            
            # 关闭WebSocket连接
            if recovery_context.websocket:
                try:
                    await recovery_context.websocket.close()
                except Exception as e:
                    logger.warning(f"Error closing websocket: {e}")
            
            self.recovery_stats["clients_disconnected"] += 1
            
            return {
                "success": True,
                "recovery_action": "disconnect",
                "message": f"Client {client_id} disconnected"
            }
            
        except Exception as e:
            logger.error(f"Disconnect failed for {recovery_context.client_id}: {e}")
            return {
                "success": False,
                "error": f"Disconnect failed: {str(e)}",
                "recovery_action": "disconnect"
            }
    
    async def _notify_client_with_context(
        self,
        error: WebSocketError,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在上下文中通知客户端"""
        try:
            if not recovery_context.websocket:
                return {
                    "success": False,
                    "error": "No websocket connection to send notification",
                    "recovery_action": "notify_client"
                }
            
            # 创建错误消息
            error_message = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error_type": error.category.value,
                    "message": error.message,
                    "client_id": recovery_context.client_id,
                    "timestamp": datetime.now().isoformat(),
                    "recovery_action": "notification_sent"
                }
            )
            
            # 发送错误消息
            await recovery_context.websocket.send(error_message.model_dump_json())
            
            return {
                "success": True,
                "recovery_action": "notify_client",
                "message": "Client notified of error"
            }
            
        except Exception as e:
            logger.error(f"Client notification failed: {e}")
            return {
                "success": False,
                "error": f"Client notification failed: {str(e)}",
                "recovery_action": "notify_client"
            }
    
    async def _buffer_and_retry_with_context(
        self,
        error: WebSocketError,
        strategy,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在上下文中缓冲并重试"""
        try:
            # 将操作添加到缓冲区
            if len(self.operation_buffer) < self.max_buffer_size:
                buffered_operation = {
                    "timestamp": datetime.now(),
                    "error_id": error.context.error_id,
                    "client_id": recovery_context.client_id,
                    "operation": recovery_context.original_operation,
                    "args": recovery_context.operation_args,
                    "kwargs": recovery_context.operation_kwargs,
                    "retry_count": 0,
                    "max_retries": strategy.max_retries
                }
                
                self.operation_buffer.append(buffered_operation)
                
                # 异步处理缓冲的操作
                asyncio.create_task(self._process_buffered_operation(buffered_operation))
                
                return {
                    "success": True,
                    "recovery_action": "buffer_and_retry",
                    "message": "Operation buffered for retry"
                }
            else:
                return {
                    "success": False,
                    "error": "Buffer is full, cannot buffer more operations",
                    "recovery_action": "buffer_full"
                }
                
        except Exception as e:
            logger.error(f"Buffer and retry failed: {e}")
            return {
                "success": False,
                "error": f"Buffer and retry failed: {str(e)}",
                "recovery_action": "buffer_and_retry"
            }
    
    async def _process_buffered_operation(self, buffered_operation: Dict[str, Any]):
        """处理缓冲的操作"""
        try:
            operation = buffered_operation["operation"]
            args = buffered_operation["args"]
            kwargs = buffered_operation["kwargs"]
            
            # 等待一段时间后重试
            await asyncio.sleep(1.0)
            
            # 执行操作
            await operation(*args, **kwargs)
            
            # 从缓冲区移除成功的操作
            if buffered_operation in self.operation_buffer:
                self.operation_buffer.remove(buffered_operation)
            
            logger.info(f"Buffered operation {operation.__name__} executed successfully")
            
        except Exception as e:
            buffered_operation["retry_count"] += 1
            
            if buffered_operation["retry_count"] < buffered_operation["max_retries"]:
                # 重新安排重试
                asyncio.create_task(self._process_buffered_operation(buffered_operation))
            else:
                # 达到最大重试次数，从缓冲区移除
                if buffered_operation in self.operation_buffer:
                    self.operation_buffer.remove(buffered_operation)
                
                logger.error(f"Buffered operation {operation.__name__} failed after {buffered_operation['max_retries']} retries: {e}")
    
    async def _failover_with_context(
        self,
        error: WebSocketError,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在上下文中执行故障转移"""
        try:
            if not self.failover_endpoints:
                return {
                    "success": False,
                    "error": "No failover endpoints configured",
                    "recovery_action": "failover"
                }
            
            # 切换到下一个端点
            self.current_endpoint_index = (self.current_endpoint_index + 1) % len(self.failover_endpoints)
            new_endpoint = self.failover_endpoints[self.current_endpoint_index]
            
            logger.info(f"Failing over to endpoint: {new_endpoint}")
            
            # 在实际实现中，这里应该重新配置数据源或服务端点
            
            self.recovery_stats["failovers_executed"] += 1
            
            return {
                "success": True,
                "recovery_action": "failover",
                "new_endpoint": new_endpoint,
                "message": f"Failed over to {new_endpoint}"
            }
            
        except Exception as e:
            logger.error(f"Failover failed: {e}")
            return {
                "success": False,
                "error": f"Failover failed: {str(e)}",
                "recovery_action": "failover"
            }
    
    async def _degrade_service_with_context(
        self,
        error: WebSocketError,
        recovery_context: RecoveryContext
    ) -> Dict[str, Any]:
        """在上下文中降级服务"""
        try:
            logger.warning("Degrading service due to error")
            
            # 降级数据发布器
            if self.data_publisher:
                await self.data_publisher.degrade_service()
            
            # 限制新连接
            if self.connection_manager:
                await self.connection_manager.enable_connection_limiting()
            
            self.recovery_stats["services_degraded"] += 1
            
            return {
                "success": True,
                "recovery_action": "degrade_service",
                "message": "Service degraded to maintain stability"
            }
            
        except Exception as e:
            logger.error(f"Service degradation failed: {e}")
            return {
                "success": False,
                "error": f"Service degradation failed: {str(e)}",
                "recovery_action": "degrade_service"
            }
    
    # 分类特定的恢复处理器
    async def _handle_connection_recovery(self, error: WebSocketError, strategy) -> Dict[str, Any]:
        """处理连接恢复"""
        # 这个方法会被错误处理器调用，但实际的恢复逻辑在_execute_recovery_with_context中
        return {
            "success": True,
            "recovery_action": "connection_recovery_delegated",
            "message": "Connection recovery delegated to recovery service"
        }
    
    async def _handle_subscription_recovery(self, error: WebSocketError, strategy) -> Dict[str, Any]:
        """处理订阅恢复"""
        return {
            "success": True,
            "recovery_action": "subscription_recovery_delegated",
            "message": "Subscription recovery delegated to recovery service"
        }
    
    async def _handle_data_publish_recovery(self, error: WebSocketError, strategy) -> Dict[str, Any]:
        """处理数据发布恢复"""
        return {
            "success": True,
            "recovery_action": "data_publish_recovery_delegated",
            "message": "Data publish recovery delegated to recovery service"
        }
    
    async def _handle_network_recovery(self, error: WebSocketError, strategy) -> Dict[str, Any]:
        """处理网络恢复"""
        return {
            "success": True,
            "recovery_action": "network_recovery_delegated",
            "message": "Network recovery delegated to recovery service"
        }
    
    async def _handle_timeout_recovery(self, error: WebSocketError, strategy) -> Dict[str, Any]:
        """处理超时恢复"""
        return {
            "success": True,
            "recovery_action": "timeout_recovery_delegated",
            "message": "Timeout recovery delegated to recovery service"
        }
    
    def configure_failover_endpoints(self, endpoints: List[str]):
        """配置故障转移端点"""
        self.failover_endpoints = endpoints
        self.current_endpoint_index = 0
        logger.info(f"Configured {len(endpoints)} failover endpoints")
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """获取恢复统计"""
        return {
            **self.recovery_stats,
            "buffer_size": len(self.operation_buffer),
            "max_buffer_size": self.max_buffer_size,
            "failover_endpoints_count": len(self.failover_endpoints),
            "current_endpoint_index": self.current_endpoint_index,
            "error_handler_stats": self.error_handler.get_error_stats()
        }
    
    async def clear_buffer(self) -> int:
        """清空操作缓冲区"""
        cleared_count = len(self.operation_buffer)
        self.operation_buffer.clear()
        logger.info(f"Cleared {cleared_count} buffered operations")
        return cleared_count
    
    async def process_pending_operations(self) -> Dict[str, int]:
        """处理待处理的操作"""
        processed = 0
        failed = 0
        
        operations_to_process = self.operation_buffer.copy()
        
        for operation in operations_to_process:
            try:
                await self._process_buffered_operation(operation)
                processed += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to process buffered operation: {e}")
        
        return {"processed": processed, "failed": failed}
    
    async def cleanup(self):
        """清理恢复服务"""
        await self.clear_buffer()
        await self.error_handler.cleanup()
        logger.info("Error recovery service cleaned up")


# 恢复服务装饰器
def with_error_recovery(recovery_service: WebSocketErrorRecoveryService):
    """错误恢复装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 尝试从参数中提取恢复上下文信息
            client_id = None
            websocket = None
            
            # 简单的参数检查来提取上下文
            for arg in args:
                if hasattr(arg, 'client_id'):
                    client_id = getattr(arg, 'client_id')
                if hasattr(arg, 'websocket'):
                    websocket = getattr(arg, 'websocket')
            
            recovery_context = RecoveryContext(
                client_id=client_id,
                websocket=websocket,
                connection_manager=recovery_service.connection_manager,
                subscription_manager=recovery_service.subscription_manager,
                data_publisher=recovery_service.data_publisher,
                message_router=recovery_service.message_router,
                original_operation=func,
                operation_args=args,
                operation_kwargs=kwargs
            )
            
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Operation {func.__name__} failed, attempting recovery: {e}")
                recovery_result = await recovery_service.handle_error_with_recovery(e, recovery_context)
                
                if recovery_result.get("success"):
                    # 如果恢复成功且有结果，返回结果
                    if "result" in recovery_result:
                        return recovery_result["result"]
                    else:
                        return recovery_result
                else:
                    # 恢复失败，重新抛出原始异常
                    raise e
        
        return wrapper
    return decorator