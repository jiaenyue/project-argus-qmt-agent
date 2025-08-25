"""
WebSocket 实时数据系统 - 主服务器
根据 tasks.md 任务5要求实现的WebSocket服务器
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed, WebSocketException

from .websocket_models import (
    WebSocketMessage, MessageType, SubscriptionRequest, SubscriptionResponse,
    ErrorMessage, HeartbeatMessage, WebSocketConfig, MessageHandleResult,
    DataType
)
from .websocket_connection_manager import WebSocketConnectionManager
from .subscription_manager import SubscriptionManager
from .data_publisher import DataPublisher, DataSourceConfig
from .message_router import MessageRouter, MessageFormatter

logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket 实时数据服务器 - 整合所有组件的主服务器"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        max_connections: int = 1000,
        max_subscriptions_per_client: int = 100,
        data_source_config: DataSourceConfig = None,
        websocket_config: WebSocketConfig = None
    ):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        
        # WebSocket配置
        self.websocket_config = websocket_config or WebSocketConfig(
            max_connections=max_connections,
            max_subscriptions_per_client=max_subscriptions_per_client
        )
        
        # 核心组件
        self.connection_manager = WebSocketConnectionManager(
            max_connections=max_connections
        )
        self.subscription_manager = SubscriptionManager(
            max_subscriptions_per_client=max_subscriptions_per_client
        )
        self.data_publisher = DataPublisher(
            subscription_manager=self.subscription_manager,
            connection_manager=self.connection_manager,
            config=data_source_config or DataSourceConfig()
        )
        
        # 消息路由器
        self.message_router = MessageRouter(self.websocket_config)
        self._register_message_handlers()
        
        # 服务器状态
        self.server = None
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        
        # 统计信息
        self.server_stats = {
            "start_time": None,
            "total_connections": 0,
            "total_messages": 0,
            "total_subscriptions": 0
        }
    
    def _register_message_handlers(self):
        """注册消息处理器"""
        self.message_router.register_handler(MessageType.SUBSCRIBE, self._handle_subscribe_message)
        self.message_router.register_handler(MessageType.UNSUBSCRIBE, self._handle_unsubscribe_message)
        self.message_router.register_handler(MessageType.GET_SUBSCRIPTIONS, self._handle_get_subscriptions_message)
        self.message_router.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat_message)
        self.message_router.register_handler(MessageType.GET_STATS, self._handle_get_stats_message)
        self.message_router.register_handler(MessageType.PING, self._handle_ping_message)
        logger.info("Message handlers registered")
    
    async def start(self):
        """启动WebSocket服务器"""
        if self.is_running:
            logger.warning("WebSocketServer already running")
            return
        
        try:
            logger.info(f"Starting WebSocketServer on {self.host}:{self.port}")
            
            # 启动数据发布器
            await self.data_publisher.start()
            
            # 启动WebSocket服务器
            self.server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port,
                max_size=2**20,  # 1MB
                max_queue=2**5,  # 32
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10
            )
            
            self.is_running = True
            self.server_stats["start_time"] = datetime.now()
            
            logger.info(f"WebSocketServer started on {self.host}:{self.port}")
            
            # 等待关闭事件
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error starting WebSocketServer: {e}")
            raise
    
    async def stop(self):
        """停止WebSocket服务器"""
        if not self.is_running:
            return
        
        logger.info("Stopping WebSocketServer...")
        
        try:
            # 停止数据发布器
            await self.data_publisher.stop()
            
            # 停止连接管理器
            await self.connection_manager.stop()
            
            # 清理消息路由器
            await self.message_router.cleanup()
            
            # 关闭WebSocket服务器
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            self.is_running = False
            self._shutdown_event.set()
            
            logger.info("WebSocketServer stopped")
            
        except Exception as e:
            logger.error(f"Error stopping WebSocketServer: {e}")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """处理WebSocket连接"""
        client_id = None
        
        try:
            # 获取客户端信息
            client_info = self._get_client_info(websocket)
            client_id = client_info["client_id"]
            
            logger.info(f"New connection from {client_id} - {client_info}")
            
            # 注册连接
            await self.connection_manager.register_connection(
                client_id, websocket, client_info
            )
            
            self.server_stats["total_connections"] += 1
            
            # 发送欢迎消息
            await self._send_welcome_message(websocket, client_id)
            
            # 处理消息
            async for message in websocket:
                await self._handle_message(websocket, client_id, message)
                
        except ConnectionClosed:
            logger.info(f"Connection closed for client {client_id}")
        except WebSocketException as e:
            logger.error(f"WebSocket error for client {client_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error handling connection for {client_id}: {e}")
        finally:
            # 清理连接
            if client_id:
                await self.connection_manager.unregister_connection(client_id)
                # 清理该客户端的所有订阅
                await self.subscription_manager.unsubscribe_all(client_id)
    
    def _get_client_info(self, websocket: WebSocketServerProtocol) -> Dict[str, Any]:
        """获取客户端信息"""
        remote_addr = websocket.remote_address
        return {
            "client_id": f"{remote_addr[0]}:{remote_addr[1]}",
            "remote_address": f"{remote_addr[0]}:{remote_addr[1]}",
            "user_agent": websocket.request_headers.get("User-Agent", "Unknown"),
            "connected_at": datetime.now().isoformat(),
            "path": websocket.path
        }
    
    async def _send_welcome_message(self, websocket: WebSocketServerProtocol, client_id: str):
        """发送欢迎消息"""
        welcome_msg = WebSocketMessage(
            type=MessageType.WELCOME,
            data={
                "client_id": client_id,
                "server_version": "1.0.0",
                "supported_data_types": [dt.value for dt in DataType],
                "max_subscriptions": self.subscription_manager.max_subscriptions_per_client,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        await websocket.send(welcome_msg.model_dump_json())
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, client_id: str, raw_message: str):
        """处理接收到的消息 - 使用MessageRouter"""
        try:
            self.server_stats["total_messages"] += 1
            
            # 使用MessageRouter路由消息
            result = await self.message_router.route_incoming_message(
                client_id, raw_message, websocket
            )
            
            # 如果处理成功且有响应数据，发送响应
            if result.success and result.response_data:
                response_message = WebSocketMessage(
                    type=MessageType.SUBSCRIPTION_RESPONSE,  # 根据实际情况调整
                    data=result.response_data
                )
                
                formatted_response = await self.message_router.format_outgoing_message(
                    response_message, client_id
                )
                
                if isinstance(formatted_response, bytes):
                    await websocket.send(formatted_response)
                else:
                    await websocket.send(formatted_response)
            
            # 如果处理失败，发送错误消息
            elif not result.success:
                error_message = MessageFormatter.format_error_message(
                    error=result.error or result.message,
                    client_id=client_id,
                    message_id=result.message_id
                )
                
                formatted_error = await self.message_router.format_outgoing_message(
                    error_message, client_id
                )
                
                if isinstance(formatted_error, bytes):
                    await websocket.send(formatted_error)
                else:
                    await websocket.send(formatted_error)
                
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
            # 发送通用错误消息
            error_message = MessageFormatter.format_error_message(
                error=f"Internal error: {str(e)}",
                client_id=client_id
            )
            try:
                await websocket.send(error_message.model_dump_json())
            except Exception as send_error:
                logger.error(f"Failed to send error message to {client_id}: {send_error}")
    
    async def _handle_subscribe(self, websocket: WebSocketServerProtocol, client_id: str, message: WebSocketMessage):
        """处理订阅请求"""
        try:
            subscription_request = SubscriptionRequest(**message.data)
            
            # 验证订阅请求
            validation_result = await self.subscription_manager.validate_subscription_request(
                subscription_request
            )
            
            if not validation_result["is_valid"]:
                await self._send_error(
                    websocket, client_id, ", ".join(validation_result["errors"])
                )
                return
            
            # 添加订阅
            response = await self.subscription_manager.subscribe(
                client_id, subscription_request
            )
            
            # 发送响应
            response_message = WebSocketMessage(
                type=MessageType.SUBSCRIPTION_RESPONSE,
                data=response.model_dump()
            )
            
            await websocket.send(response_message.model_dump_json())
            
            self.server_stats["total_subscriptions"] += 1
            
            logger.info(f"Client {client_id} subscribed to {subscription_request.symbol} {subscription_request.data_type}")
            
        except Exception as e:
            logger.error(f"Error handling subscribe for {client_id}: {e}")
            await self._send_error(websocket, client_id, f"Subscribe error: {e}")
    
    async def _handle_unsubscribe(self, websocket: WebSocketServerProtocol, client_id: str, message: WebSocketMessage):
        """处理取消订阅请求"""
        try:
            subscription_id = message.data.get("subscription_id")
            
            if not subscription_id:
                await self._send_error(websocket, client_id, "Missing subscription_id")
                return
            
            # 取消订阅
            success = await self.subscription_manager.unsubscribe(client_id, subscription_id)
            
            # 发送响应
            response = WebSocketMessage(
                type=MessageType.UNSUBSCRIBE_RESPONSE,
                data={
                    "subscription_id": subscription_id,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            await websocket.send(response.model_dump_json())
            
            if success:
                self.server_stats["total_subscriptions"] = max(0, self.server_stats["total_subscriptions"] - 1)
                logger.info(f"Client {client_id} unsubscribed from {subscription_id}")
            
        except Exception as e:
            logger.error(f"Error handling unsubscribe for {client_id}: {e}")
            await self._send_error(websocket, client_id, f"Unsubscribe error: {e}")
    
    async def _handle_get_subscriptions(self, websocket: WebSocketServerProtocol, client_id: str):
        """处理获取订阅列表请求"""
        try:
            subscriptions = await self.subscription_manager.get_client_subscriptions(client_id)
            
            response = WebSocketMessage(
                type=MessageType.SUBSCRIPTION_LIST,
                data={
                    "subscriptions": [sub.model_dump() for sub in subscriptions],
                    "count": len(subscriptions),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            await websocket.send(response.model_dump_json())
            
        except Exception as e:
            logger.error(f"Error getting subscriptions for {client_id}: {e}")
            await self._send_error(websocket, client_id, f"Get subscriptions error: {e}")
    
    async def _handle_heartbeat(self, websocket: WebSocketServerProtocol, client_id: str, message: WebSocketMessage):
        """处理心跳消息"""
        try:
            # 更新连接状态
            await self.connection_manager.update_heartbeat(client_id)
            
            # 发送心跳响应
            response = WebSocketMessage(
                type=MessageType.HEARTBEAT,
                data={
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat(),
                    "client_time": message.data.get("client_time")
                }
            )
            
            await websocket.send(response.model_dump_json())
            
        except Exception as e:
            logger.error(f"Error handling heartbeat for {client_id}: {e}")
    
    async def _handle_get_stats(self, websocket: WebSocketServerProtocol, client_id: str):
        """处理获取统计信息请求"""
        try:
            # 获取各种统计信息
            connection_stats = self.connection_manager.get_stats()
            subscription_stats = await self.subscription_manager.get_subscription_stats()
            publisher_stats = await self.data_publisher.get_publisher_stats()
            
            stats = {
                "server": {
                    "start_time": self.server_stats["start_time"].isoformat() if self.server_stats["start_time"] else None,
                    "total_connections": self.server_stats["total_connections"],
                    "total_messages": self.server_stats["total_messages"],
                    "total_subscriptions": self.server_stats["total_subscriptions"],
                    "uptime": str(datetime.now() - self.server_stats["start_time"]) if self.server_stats["start_time"] else "0:00:00"
                },
                "connections": connection_stats,
                "subscriptions": subscription_stats,
                "publisher": publisher_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            response = WebSocketMessage(
                type=MessageType.STATS,
                data=stats
            )
            
            await websocket.send(response.model_dump_json())
            
        except Exception as e:
            logger.error(f"Error getting stats for {client_id}: {e}")
            await self._send_error(websocket, client_id, f"Get stats error: {e}")
    
    async def _send_error(self, websocket: WebSocketServerProtocol, client_id: str, error_message: str):
        """发送错误消息"""
        try:
            error = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error": error_message,
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            await websocket.send(error.model_dump_json())
            
        except Exception as e:
            logger.error(f"Error sending error message to {client_id}: {e}")
    
    async def get_server_stats(self) -> Dict[str, Any]:
        """获取服务器统计信息"""
        if not self.is_running:
            return {"status": "stopped"}
        
        try:
            connection_stats = self.connection_manager.get_stats()
            subscription_stats = await self.subscription_manager.get_subscription_stats()
            publisher_stats = await self.data_publisher.get_publisher_stats()
            
            return {
                "status": "running",
                "server": {
                    "start_time": self.server_stats["start_time"].isoformat() if self.server_stats["start_time"] else None,
                    "total_connections": self.server_stats["total_connections"],
                    "total_messages": self.server_stats["total_messages"],
                    "total_subscriptions": self.server_stats["total_subscriptions"],
                    "uptime": str(datetime.now() - self.server_stats["start_time"]) if self.server_stats["start_time"] else "0:00:00"
                },
                "connections": connection_stats,
                "subscriptions": subscription_stats,
                "publisher": publisher_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting server stats: {e}")
            return {"status": "error", "error": str(e)}
    
    async def restart(self):
        """重启服务器"""
        logger.info("Restarting WebSocketServer...")
        await self.stop()
        await asyncio.sleep(1)  # 等待完全停止
        await self.start()


    # MessageRouter兼容的消息处理器方法
    async def _handle_subscribe_message(self, client_id: str, message: WebSocketMessage, websocket) -> MessageHandleResult:
        """处理订阅消息 - MessageRouter兼容版本"""
        try:
            subscription_request = SubscriptionRequest(**message.data)
            
            # 验证订阅请求
            validation_result = await self.subscription_manager.validate_subscription_request(
                subscription_request
            )
            
            if not validation_result["is_valid"]:
                return MessageHandleResult(
                    success=False,
                    message="Subscription validation failed",
                    message_id=message.message_id,
                    error=", ".join(validation_result["errors"])
                )
            
            # 添加订阅
            response = await self.subscription_manager.subscribe(
                client_id, subscription_request
            )
            
            self.server_stats["total_subscriptions"] += 1
            logger.info(f"Client {client_id} subscribed to {subscription_request.symbol} {subscription_request.data_type}")
            
            return MessageHandleResult(
                success=True,
                message="Subscription successful",
                message_id=message.message_id,
                response_data=response.model_dump()
            )
            
        except Exception as e:
            logger.error(f"Error handling subscribe for {client_id}: {e}")
            return MessageHandleResult(
                success=False,
                message="Subscribe error",
                message_id=message.message_id,
                error=str(e)
            )
    
    async def _handle_unsubscribe_message(self, client_id: str, message: WebSocketMessage, websocket) -> MessageHandleResult:
        """处理取消订阅消息 - MessageRouter兼容版本"""
        try:
            subscription_id = message.data.get("subscription_id")
            
            if not subscription_id:
                return MessageHandleResult(
                    success=False,
                    message="Missing subscription_id",
                    message_id=message.message_id,
                    error="Missing subscription_id"
                )
            
            # 取消订阅
            success = await self.subscription_manager.unsubscribe(client_id, subscription_id)
            
            if success:
                self.server_stats["total_subscriptions"] = max(0, self.server_stats["total_subscriptions"] - 1)
                logger.info(f"Client {client_id} unsubscribed from {subscription_id}")
            
            return MessageHandleResult(
                success=success,
                message="Unsubscribe successful" if success else "Unsubscribe failed",
                message_id=message.message_id,
                response_data={
                    "subscription_id": subscription_id,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling unsubscribe for {client_id}: {e}")
            return MessageHandleResult(
                success=False,
                message="Unsubscribe error",
                message_id=message.message_id,
                error=str(e)
            )
    
    async def _handle_get_subscriptions_message(self, client_id: str, message: WebSocketMessage, websocket) -> MessageHandleResult:
        """处理获取订阅列表消息 - MessageRouter兼容版本"""
        try:
            subscriptions = await self.subscription_manager.get_client_subscriptions(client_id)
            
            return MessageHandleResult(
                success=True,
                message="Subscriptions retrieved",
                message_id=message.message_id,
                response_data={
                    "subscriptions": [sub.model_dump() for sub in subscriptions],
                    "count": len(subscriptions),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting subscriptions for {client_id}: {e}")
            return MessageHandleResult(
                success=False,
                message="Get subscriptions error",
                message_id=message.message_id,
                error=str(e)
            )
    
    async def _handle_heartbeat_message(self, client_id: str, message: WebSocketMessage, websocket) -> MessageHandleResult:
        """处理心跳消息 - MessageRouter兼容版本"""
        try:
            # 更新连接状态
            await self.connection_manager.update_heartbeat(client_id)
            
            return MessageHandleResult(
                success=True,
                message="Heartbeat processed",
                message_id=message.message_id,
                response_data={
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat(),
                    "client_time": message.data.get("client_time") if message.data else None
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling heartbeat for {client_id}: {e}")
            return MessageHandleResult(
                success=False,
                message="Heartbeat error",
                message_id=message.message_id,
                error=str(e)
            )
    
    async def _handle_get_stats_message(self, client_id: str, message: WebSocketMessage, websocket) -> MessageHandleResult:
        """处理获取统计信息消息 - MessageRouter兼容版本"""
        try:
            # 获取各种统计信息
            connection_stats = self.connection_manager.get_stats()
            subscription_stats = await self.subscription_manager.get_subscription_stats()
            publisher_stats = await self.data_publisher.get_publisher_stats()
            router_stats = await self.message_router.get_routing_stats()
            
            stats = {
                "server": {
                    "start_time": self.server_stats["start_time"].isoformat() if self.server_stats["start_time"] else None,
                    "total_connections": self.server_stats["total_connections"],
                    "total_messages": self.server_stats["total_messages"],
                    "total_subscriptions": self.server_stats["total_subscriptions"],
                    "uptime": str(datetime.now() - self.server_stats["start_time"]) if self.server_stats["start_time"] else "0:00:00"
                },
                "connections": connection_stats,
                "subscriptions": subscription_stats,
                "publisher": publisher_stats,
                "router": router_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            return MessageHandleResult(
                success=True,
                message="Stats retrieved",
                message_id=message.message_id,
                response_data=stats
            )
            
        except Exception as e:
            logger.error(f"Error getting stats for {client_id}: {e}")
            return MessageHandleResult(
                success=False,
                message="Get stats error",
                message_id=message.message_id,
                error=str(e)
            )
    
    async def _handle_ping_message(self, client_id: str, message: WebSocketMessage, websocket) -> MessageHandleResult:
        """处理Ping消息 - MessageRouter兼容版本"""
        try:
            return MessageHandleResult(
                success=True,
                message="Pong",
                message_id=message.message_id,
                response_data={
                    "type": "pong",
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat(),
                    "original_message_id": message.message_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling ping for {client_id}: {e}")
            return MessageHandleResult(
                success=False,
                message="Ping error",
                message_id=message.message_id,
                error=str(e)
            )


# 服务器启动脚本
async def main():
    """服务器启动入口"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建服务器实例
    server = WebSocketServer(
        host="localhost",
        port=8765,
        max_connections=1000,
        max_subscriptions_per_client=100,
        data_source_config=DataSourceConfig(
            source_type="mock",
            update_interval=1.0
        )
    )
    
    try:
        # 启动服务器
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        # 停止服务器
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())