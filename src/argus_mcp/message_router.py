"""
WebSocket 消息路由和处理系统
根据 tasks.md 任务4要求实现的消息路由器
"""

import asyncio
import json
import gzip
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from enum import Enum
import uuid

from .websocket_models import (
    WebSocketMessage, MessageType, SubscriptionRequest, SubscriptionResponse,
    ErrorMessage, ValidationResult, MessageHandleResult, BroadcastResult,
    WebSocketConfig
)

logger = logging.getLogger(__name__)


class CompressionType(str, Enum):
    """压缩类型枚举"""
    NONE = "none"
    GZIP = "gzip"


class MessagePriority(str, Enum):
    """消息优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MessageRouter:
    """WebSocket消息路由器 - 处理消息路由、格式化、验证和压缩"""
    
    def __init__(self, config: WebSocketConfig = None):
        self.config = config or WebSocketConfig()
        
        # 消息处理器注册表
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # 消息统计
        self.message_stats = {
            "total_processed": 0,
            "total_routed": 0,
            "total_compressed": 0,
            "total_batched": 0,
            "total_errors": 0,
            "compression_ratio": 0.0,
            "average_processing_time_ms": 0.0
        }
        
        # 消息确认跟踪
        self.pending_acknowledgments: Dict[str, Dict[str, Any]] = {}
        
        # 批量消息缓冲区
        self.message_batches: Dict[str, List[WebSocketMessage]] = {}
        self.batch_timers: Dict[str, asyncio.Task] = {}
        
        # 消息压缩缓存
        self.compression_cache: Dict[str, bytes] = {}
        self.cache_max_size = 1000
        
        logger.info("MessageRouter initialized")
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[message_type] = handler
        logger.debug(f"Registered handler for message type: {message_type}")
    
    def unregister_handler(self, message_type: MessageType):
        """注销消息处理器"""
        if message_type in self.message_handlers:
            del self.message_handlers[message_type]
            logger.debug(f"Unregistered handler for message type: {message_type}")
    
    async def route_incoming_message(
        self,
        client_id: str,
        raw_message: str,
        websocket = None
    ) -> MessageHandleResult:
        """路由处理传入的消息"""
        start_time = datetime.now()
        
        try:
            # 解析消息
            message_data = json.loads(raw_message)
            message = WebSocketMessage(**message_data)
            
            # 验证消息
            validation_result = await self.validate_message(message_data)
            if not validation_result.is_valid:
                return MessageHandleResult(
                    success=False,
                    message="Message validation failed",
                    message_id=message.message_id,
                    error=", ".join(validation_result.errors)
                )
            
            # 检查消息处理器
            if message.type not in self.message_handlers:
                return MessageHandleResult(
                    success=False,
                    message=f"No handler for message type: {message.type}",
                    message_id=message.message_id,
                    error=f"Unsupported message type: {message.type}"
                )
            
            # 调用消息处理器
            handler = self.message_handlers[message.type]
            result = await handler(client_id, message, websocket)
            
            # 更新统计信息
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_processing_stats(processing_time)
            
            self.message_stats["total_processed"] += 1
            self.message_stats["total_routed"] += 1
            
            return result
            
        except json.JSONDecodeError as e:
            self.message_stats["total_errors"] += 1
            return MessageHandleResult(
                success=False,
                message="Invalid JSON format",
                message_id=str(uuid.uuid4()),
                error=f"JSON decode error: {str(e)}"
            )
        except Exception as e:
            self.message_stats["total_errors"] += 1
            logger.error(f"Error routing message from {client_id}: {e}")
            return MessageHandleResult(
                success=False,
                message="Internal routing error",
                message_id=str(uuid.uuid4()),
                error=str(e)
            )
    
    async def format_outgoing_message(
        self,
        message: WebSocketMessage,
        client_id: str = None,
        compression: bool = None
    ) -> Union[str, bytes]:
        """格式化输出消息"""
        try:
            # 设置消息元数据
            if not message.metadata:
                message.metadata = {}
            
            message.metadata.update({
                "formatted_at": datetime.now().isoformat(),
                "client_id": client_id,
                "server_version": "1.0.0"
            })
            
            # 序列化消息
            message_json = message.model_dump_json()
            
            # 检查是否需要压缩
            should_compress = (
                compression if compression is not None 
                else (self.config.enable_compression and len(message_json) > self.config.compression_threshold)
            )
            
            if should_compress:
                return await self.compress_message(message_json)
            else:
                return message_json
                
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            # 返回错误消息
            error_msg = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error": "Message formatting error",
                    "details": str(e),
                    "original_message_id": message.message_id
                }
            )
            return error_msg.model_dump_json()
    
    async def compress_message(self, message: str) -> bytes:
        """压缩消息"""
        try:
            # 检查压缩缓存
            cache_key = hash(message)
            if str(cache_key) in self.compression_cache:
                return self.compression_cache[str(cache_key)]
            
            # 压缩消息
            compressed = gzip.compress(message.encode('utf-8'))
            
            # 更新缓存
            if len(self.compression_cache) < self.cache_max_size:
                self.compression_cache[str(cache_key)] = compressed
            
            # 更新统计信息
            self.message_stats["total_compressed"] += 1
            compression_ratio = len(compressed) / len(message.encode('utf-8'))
            self._update_compression_ratio(compression_ratio)
            
            logger.debug(f"Compressed message: {len(message)} -> {len(compressed)} bytes (ratio: {compression_ratio:.2f})")
            
            return compressed
            
        except Exception as e:
            logger.error(f"Error compressing message: {e}")
            return message.encode('utf-8')
    
    async def decompress_message(self, compressed_data: bytes) -> str:
        """解压缩消息"""
        try:
            return gzip.decompress(compressed_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error decompressing message: {e}")
            raise
    
    async def validate_message(self, message_data: Dict[str, Any]) -> ValidationResult:
        """验证消息格式和内容"""
        errors = []
        warnings = []
        
        try:
            # 检查必需字段
            required_fields = ["type", "timestamp"]
            for field in required_fields:
                if field not in message_data:
                    errors.append(f"Missing required field: {field}")
            
            # 验证消息类型
            if "type" in message_data:
                try:
                    MessageType(message_data["type"])
                except ValueError:
                    errors.append(f"Invalid message type: {message_data['type']}")
            
            # 验证时间戳
            if "timestamp" in message_data:
                try:
                    datetime.fromisoformat(message_data["timestamp"].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    errors.append("Invalid timestamp format")
            
            # 检查消息大小
            message_size = len(json.dumps(message_data).encode('utf-8'))
            if message_size > self.config.max_message_size:
                errors.append(f"Message size ({message_size}) exceeds limit ({self.config.max_message_size})")
            
            # 验证特定消息类型的数据
            if "type" in message_data and "data" in message_data:
                type_validation = await self._validate_message_type_data(
                    message_data["type"], message_data["data"]
                )
                errors.extend(type_validation.get("errors", []))
                warnings.extend(type_validation.get("warnings", []))
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                data=message_data
            )
            
        except Exception as e:
            logger.error(f"Error validating message: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=warnings
            )
    
    async def _validate_message_type_data(self, message_type: str, data: Any) -> Dict[str, List[str]]:
        """验证特定消息类型的数据"""
        errors = []
        warnings = []
        
        try:
            if message_type == MessageType.SUBSCRIBE:
                # 验证订阅请求
                if not isinstance(data, dict):
                    errors.append("Subscribe data must be an object")
                else:
                    required_fields = ["symbol", "data_type"]
                    for field in required_fields:
                        if field not in data:
                            errors.append(f"Missing required field in subscribe data: {field}")
                    
                    # 验证股票代码格式
                    if "symbol" in data and not isinstance(data["symbol"], str):
                        errors.append("Symbol must be a string")
                    
                    # 验证数据类型
                    if "data_type" in data:
                        try:
                            from .websocket_models import DataType
                            DataType(data["data_type"])
                        except ValueError:
                            errors.append(f"Invalid data_type: {data['data_type']}")
            
            elif message_type == MessageType.UNSUBSCRIBE:
                # 验证取消订阅请求
                if not isinstance(data, dict):
                    errors.append("Unsubscribe data must be an object")
                else:
                    if "subscription_id" not in data:
                        errors.append("Missing subscription_id in unsubscribe data")
            
            elif message_type == MessageType.HEARTBEAT:
                # 验证心跳消息
                if not isinstance(data, dict):
                    warnings.append("Heartbeat data should be an object")
                else:
                    if "client_time" not in data:
                        warnings.append("Missing client_time in heartbeat data")
            
        except Exception as e:
            errors.append(f"Type validation error: {str(e)}")
        
        return {"errors": errors, "warnings": warnings}
    
    async def batch_messages(
        self,
        client_id: str,
        messages: List[WebSocketMessage],
        max_batch_size: int = None
    ) -> List[List[WebSocketMessage]]:
        """批量处理消息"""
        if not self.config.enable_batching:
            return [[msg] for msg in messages]
        
        max_size = max_batch_size or 10
        batches = []
        
        for i in range(0, len(messages), max_size):
            batch = messages[i:i + max_size]
            batches.append(batch)
        
        self.message_stats["total_batched"] += len(batches)
        
        return batches
    
    async def add_to_batch(self, client_id: str, message: WebSocketMessage):
        """添加消息到批处理队列"""
        if not self.config.enable_batching:
            return False
        
        if client_id not in self.message_batches:
            self.message_batches[client_id] = []
        
        self.message_batches[client_id].append(message)
        
        # 设置批处理定时器
        if client_id not in self.batch_timers:
            self.batch_timers[client_id] = asyncio.create_task(
                self._flush_batch_after_delay(client_id)
            )
        
        return True
    
    async def _flush_batch_after_delay(self, client_id: str):
        """延迟刷新批处理队列"""
        await asyncio.sleep(self.config.flush_interval)
        
        if client_id in self.message_batches and self.message_batches[client_id]:
            # 这里应该调用实际的发送函数，但由于这是路由器，我们只是清空队列
            batch = self.message_batches[client_id].copy()
            self.message_batches[client_id].clear()
            
            logger.debug(f"Flushed batch for client {client_id}: {len(batch)} messages")
        
        # 清理定时器
        if client_id in self.batch_timers:
            del self.batch_timers[client_id]
    
    async def request_acknowledgment(
        self,
        message_id: str,
        client_id: str,
        timeout_seconds: int = None
    ) -> bool:
        """请求消息确认"""
        timeout = timeout_seconds or self.config.message_timeout
        
        # 记录待确认消息
        self.pending_acknowledgments[message_id] = {
            "client_id": client_id,
            "timestamp": datetime.now(),
            "timeout": timeout
        }
        
        # 设置超时任务
        asyncio.create_task(self._handle_acknowledgment_timeout(message_id, timeout))
        
        return True
    
    async def handle_acknowledgment(self, message_id: str, client_id: str) -> bool:
        """处理消息确认"""
        if message_id in self.pending_acknowledgments:
            ack_info = self.pending_acknowledgments[message_id]
            
            if ack_info["client_id"] == client_id:
                del self.pending_acknowledgments[message_id]
                logger.debug(f"Received acknowledgment for message {message_id} from {client_id}")
                return True
            else:
                logger.warning(f"Acknowledgment client mismatch for message {message_id}")
                return False
        else:
            logger.warning(f"Received acknowledgment for unknown message {message_id}")
            return False
    
    async def _handle_acknowledgment_timeout(self, message_id: str, timeout: int):
        """处理确认超时"""
        await asyncio.sleep(timeout)
        
        if message_id in self.pending_acknowledgments:
            ack_info = self.pending_acknowledgments[message_id]
            logger.warning(f"Message acknowledgment timeout: {message_id} from {ack_info['client_id']}")
            del self.pending_acknowledgments[message_id]
    
    def _update_processing_stats(self, processing_time_ms: float):
        """更新处理时间统计"""
        current_avg = self.message_stats["average_processing_time_ms"]
        total_processed = self.message_stats["total_processed"]
        
        if total_processed == 0:
            self.message_stats["average_processing_time_ms"] = processing_time_ms
        else:
            # 计算移动平均
            self.message_stats["average_processing_time_ms"] = (
                (current_avg * total_processed + processing_time_ms) / (total_processed + 1)
            )
    
    def _update_compression_ratio(self, ratio: float):
        """更新压缩比统计"""
        current_ratio = self.message_stats["compression_ratio"]
        total_compressed = self.message_stats["total_compressed"]
        
        if total_compressed <= 1:
            self.message_stats["compression_ratio"] = ratio
        else:
            # 计算移动平均
            self.message_stats["compression_ratio"] = (
                (current_ratio * (total_compressed - 1) + ratio) / total_compressed
            )
    
    async def get_routing_stats(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        return {
            "message_stats": self.message_stats.copy(),
            "pending_acknowledgments": len(self.pending_acknowledgments),
            "active_batches": len(self.message_batches),
            "cache_size": len(self.compression_cache),
            "registered_handlers": list(self.message_handlers.keys()),
            "timestamp": datetime.now().isoformat()
        }
    
    async def clear_cache(self):
        """清理缓存"""
        self.compression_cache.clear()
        logger.info("Message router cache cleared")
    
    async def cleanup(self):
        """清理资源"""
        # 取消所有批处理定时器
        for timer in self.batch_timers.values():
            if not timer.done():
                timer.cancel()
        
        self.batch_timers.clear()
        self.message_batches.clear()
        self.pending_acknowledgments.clear()
        self.compression_cache.clear()
        
        logger.info("MessageRouter cleanup completed")


class MessageFormatter:
    """消息格式化器 - 专门处理消息格式化"""
    
    @staticmethod
    def format_error_message(
        error: str,
        client_id: str = None,
        message_id: str = None,
        details: Dict[str, Any] = None
    ) -> WebSocketMessage:
        """格式化错误消息"""
        return WebSocketMessage(
            type=MessageType.ERROR,
            data={
                "error": error,
                "client_id": client_id,
                "original_message_id": message_id,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def format_status_message(
        status: str,
        message: str,
        details: Dict[str, Any] = None
    ) -> WebSocketMessage:
        """格式化状态消息"""
        return WebSocketMessage(
            type=MessageType.STATUS,
            data={
                "status": status,
                "message": message,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def format_subscription_response(
        subscription_id: str,
        status: str,
        message: str,
        symbol: str,
        data_type: str,
        client_id: str
    ) -> WebSocketMessage:
        """格式化订阅响应消息"""
        return WebSocketMessage(
            type=MessageType.SUBSCRIPTION_RESPONSE,
            data={
                "subscription_id": subscription_id,
                "status": status,
                "message": message,
                "symbol": symbol,
                "data_type": data_type,
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def format_market_data_message(
        symbol: str,
        data_type: str,
        data: Dict[str, Any],
        subscription_id: str = None
    ) -> WebSocketMessage:
        """格式化市场数据消息"""
        message_type_map = {
            "quote": MessageType.MARKET_DATA,
            "kline": MessageType.KLINE_DATA,
            "trade": MessageType.TRADE_DATA,
            "depth": MessageType.DEPTH_DATA
        }
        
        return WebSocketMessage(
            type=message_type_map.get(data_type, MessageType.MARKET_DATA),
            data={
                "symbol": symbol,
                "data_type": data_type,
                "subscription_id": subscription_id,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
        )


class MessageValidator:
    """消息验证器 - 专门处理消息验证"""
    
    @staticmethod
    def validate_subscription_request(data: Dict[str, Any]) -> ValidationResult:
        """验证订阅请求"""
        errors = []
        warnings = []
        
        # 检查必需字段
        required_fields = ["symbol", "data_type"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # 验证股票代码
        if "symbol" in data:
            symbol = data["symbol"]
            if not isinstance(symbol, str) or not symbol.strip():
                errors.append("Symbol must be a non-empty string")
            elif len(symbol) > 20:
                errors.append("Symbol too long (max 20 characters)")
        
        # 验证数据类型
        if "data_type" in data:
            try:
                from .websocket_models import DataType
                DataType(data["data_type"])
            except ValueError:
                errors.append(f"Invalid data_type: {data['data_type']}")
        
        # 验证频率（如果提供）
        if "frequency" in data and data["frequency"]:
            frequency = data["frequency"]
            valid_frequencies = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
            if frequency not in valid_frequencies:
                warnings.append(f"Unusual frequency: {frequency}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data=data
        )
    
    @staticmethod
    def validate_client_id(client_id: str) -> ValidationResult:
        """验证客户端ID"""
        errors = []
        
        if not client_id:
            errors.append("Client ID cannot be empty")
        elif not isinstance(client_id, str):
            errors.append("Client ID must be a string")
        elif len(client_id) > 100:
            errors.append("Client ID too long (max 100 characters)")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )