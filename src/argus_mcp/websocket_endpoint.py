"""
WebSocket端点处理器
实现FastAPI WebSocket端点，处理客户端连接、消息路由和心跳检测
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from pydantic import ValidationError

from .data_models import WebSocketMessage, SubscriptionRequest, MessageType, HeartbeatMessage
from .websocket_server import WebSocketServer
from .config import ServerConfig

logger = logging.getLogger(__name__)


class WebSocketEndpointHandler:
    """WebSocket端点处理器"""
    
    def __init__(self, server: WebSocketServer, config: ServerConfig):
        self.server = server
        self.config = config
        self.heartbeat_interval = config.websocket.heartbeat_interval
        self.connection_timeout = config.websocket.connection_timeout
        self.max_message_size = config.websocket.max_message_size
        
    async def handle_websocket_connection(self, websocket: WebSocket, client_id: str = None):
        """处理WebSocket连接"""
        try:
            # 接受WebSocket连接
            await websocket.accept()
            
            # 注册连接
            connection_id = client_id or f"ws_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            await self.server.register_connection(websocket, connection_id)
            
            logger.info(f"WebSocket连接已建立: {connection_id}")
            
            # 创建任务处理心跳和消息
            heartbeat_task = asyncio.create_task(
                self._heartbeat_handler(websocket, connection_id)
            )
            message_task = asyncio.create_task(
                self._message_handler(websocket, connection_id)
            )
            
            # 等待任一任务完成
            done, pending = await asyncio.wait(
                [heartbeat_task, message_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 取消剩余任务
            for task in pending:
                task.cancel()
                
        except WebSocketException as e:
            logger.error(f"WebSocket连接错误: {e}")
            raise
        except Exception as e:
            logger.error(f"处理WebSocket连接时发生错误: {e}")
            raise
        finally:
            # 清理连接
            await self.server.unregister_connection(connection_id)
            logger.info(f"WebSocket连接已关闭: {connection_id}")
    
    async def _heartbeat_handler(self, websocket: WebSocket, connection_id: str):
        """心跳处理器"""
        last_heartbeat = datetime.now()
        
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                
                # 检查连接是否超时
                if datetime.now() - last_heartbeat > timedelta(seconds=self.connection_timeout):
                    logger.warning(f"连接超时: {connection_id}")
                    await websocket.close(code=1001, reason="Connection timeout")
                    break
                
                # 发送心跳消息
                try:
                    heartbeat_msg = HeartbeatMessage(
                        type=MessageType.HEARTBEAT,
                        timestamp=datetime.now().isoformat(),
                        connection_id=connection_id
                    )
                    await websocket.send_text(heartbeat_msg.model_dump_json())
                except Exception as e:
                    logger.error(f"发送心跳失败: {e}")
                    break
                    
        except asyncio.CancelledError:
            logger.debug(f"心跳处理器被取消: {connection_id}")
            raise
    
    async def _message_handler(self, websocket: WebSocket, connection_id: str):
        """消息处理器"""
        try:
            while True:
                try:
                    # 接收消息
                    message_text = await websocket.receive_text()
                    
                    if len(message_text.encode('utf-8')) > self.max_message_size:
                        await self._send_error(websocket, "消息过大")
                        continue
                    
                    # 解析消息
                    message_data = json.loads(message_text)
                    await self._process_message(websocket, connection_id, message_data)
                    
                except json.JSONDecodeError:
                    await self._send_error(websocket, "无效的JSON格式")
                except ValidationError as e:
                    await self._send_error(websocket, f"消息格式错误: {e}")
                except WebSocketDisconnect:
                    logger.info(f"客户端断开连接: {connection_id}")
                    break
                    
        except asyncio.CancelledError:
            logger.debug(f"消息处理器被取消: {connection_id}")
            raise
        except Exception as e:
            logger.error(f"消息处理错误: {e}")
            await self._send_error(websocket, "内部服务器错误")
    
    async def _process_message(self, websocket: WebSocket, connection_id: str, message_data: Dict[str, Any]):
        """处理具体消息"""
        try:
            message_type = message_data.get("type")
            
            if message_type == MessageType.SUBSCRIBE.value:
                await self._handle_subscribe(websocket, connection_id, message_data)
            elif message_type == MessageType.UNSUBSCRIBE.value:
                await self._handle_unsubscribe(websocket, connection_id, message_data)
            elif message_type == MessageType.HEARTBEAT.value:
                await self._handle_heartbeat(websocket, connection_id, message_data)
            else:
                await self._send_error(websocket, f"不支持的消息类型: {message_type}")
                
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_subscribe(self, websocket: WebSocket, connection_id: str, message_data: Dict[str, Any]):
        """处理订阅请求"""
        try:
            subscription_request = SubscriptionRequest(**message_data)
            
            # 验证订阅
            validation_result = await self.server.validate_subscription(
                connection_id, subscription_request
            )
            
            if not validation_result.is_valid:
                await self._send_error(websocket, validation_result.error_message)
                return
            
            # 添加订阅
            success = await self.server.add_subscription(connection_id, subscription_request)
            
            if success:
                response = WebSocketMessage(
                    type=MessageType.SUBSCRIBE_ACK,
                    data={"status": "success", "subscription_id": subscription_request.subscription_id},
                    connection_id=connection_id
                )
                await websocket.send_text(response.model_dump_json())
                logger.info(f"订阅成功: {connection_id} - {subscription_request.symbols}")
            else:
                await self._send_error(websocket, "订阅失败")
                
        except ValidationError as e:
            await self._send_error(websocket, f"订阅请求格式错误: {e}")
    
    async def _handle_unsubscribe(self, websocket: WebSocket, connection_id: str, message_data: Dict[str, Any]):
        """处理取消订阅请求"""
        try:
            subscription_id = message_data.get("subscription_id")
            symbols = message_data.get("symbols", [])
            
            if subscription_id:
                success = await self.server.remove_subscription(connection_id, subscription_id)
            elif symbols:
                success = await self.server.remove_symbols_subscription(connection_id, symbols)
            else:
                await self._send_error(websocket, "需要提供subscription_id或symbols")
                return
            
            if success:
                response = WebSocketMessage(
                    type=MessageType.UNSUBSCRIBE_ACK,
                    data={"status": "success"},
                    connection_id=connection_id
                )
                await websocket.send_text(response.model_dump_json())
                logger.info(f"取消订阅成功: {connection_id}")
            else:
                await self._send_error(websocket, "取消订阅失败")
                
        except Exception as e:
            await self._send_error(websocket, str(e))
    
    async def _handle_heartbeat(self, websocket: WebSocket, connection_id: str, message_data: Dict[str, Any]):
        """处理心跳消息"""
        try:
            response = HeartbeatMessage(
                type=MessageType.HEARTBEAT_ACK,
                timestamp=datetime.now().isoformat(),
                connection_id=connection_id
            )
            await websocket.send_text(response.model_dump_json())
        except Exception as e:
            logger.error(f"处理心跳消息失败: {e}")
    
    async def _send_error(self, websocket: WebSocket, error_message: str):
        """发送错误消息"""
        try:
            error_msg = WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": error_message},
                timestamp=datetime.now().isoformat()
            )
            await websocket.send_text(error_msg.model_dump_json())
        except Exception as e:
            logger.error(f"发送错误消息失败: {e}")


# FastAPI路由工厂函数
def create_websocket_routes(server: WebSocketServer, config: ServerConfig):
    """创建WebSocket路由"""
    handler = WebSocketEndpointHandler(server, config)
    
    async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
        """WebSocket端点"""
        await handler.handle_websocket_connection(websocket, client_id)
    
    return websocket_endpoint