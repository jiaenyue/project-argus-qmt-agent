"""
增强的 WebSocket 端点和路由
根据 tasks.md 任务7要求实现的 FastAPI WebSocket 集成
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.routing import APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .websocket_models import (
    WebSocketMessage, MessageType, SubscriptionRequest, SubscriptionResponse,
    ErrorMessage, HeartbeatMessage, WebSocketConfig, ConnectionStatus,
    DataType, QuoteData, KLineData, TradeData, DepthData
)
from .websocket_connection_manager import WebSocketConnectionManager
from .subscription_manager import SubscriptionManager
from .data_publisher import DataPublisher, DataSourceConfig
from .message_router import MessageRouter
from .websocket_monitor import WebSocketMonitor
from .websocket_heartbeat import WebSocketHeartbeatManager, HeartbeatConfig

logger = logging.getLogger(__name__)

# 安全认证
security = HTTPBearer(auto_error=False)

class EnhancedWebSocketEndpoints:
    """增强的 WebSocket 端点管理器"""
    
    def __init__(
        self,
        max_connections: int = 1000,
        max_subscriptions_per_client: int = 100,
        heartbeat_interval: float = 30.0,
        connection_timeout: float = 60.0
    ):
        # WebSocket配置
        self.websocket_config = WebSocketConfig(
            max_connections=max_connections,
            max_subscriptions_per_client=max_subscriptions_per_client,
            heartbeat_interval=heartbeat_interval,
            connection_timeout=connection_timeout
        )
        
        # 核心组件
        self.connection_manager = WebSocketConnectionManager(self.websocket_config)
        self.subscription_manager = SubscriptionManager(max_subscriptions_per_client)
        self.data_publisher = DataPublisher(
            subscription_manager=self.subscription_manager,
            connection_manager=self.connection_manager,
            config=DataSourceConfig(source_type="mock")
        )
        self.message_router = MessageRouter(self.websocket_config)
        # Import AlertConfig locally to avoid circular imports
        from .websocket_monitor import AlertConfig
        self.monitor = WebSocketMonitor(AlertConfig())
        
        # 心跳管理器
        heartbeat_config = HeartbeatConfig(
            interval=heartbeat_interval,
            timeout=connection_timeout
        )
        self.heartbeat_manager = WebSocketHeartbeatManager(heartbeat_config)
        
        # 注册消息处理器
        self._register_message_handlers()
        
        # 心跳和清理任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        # 路由器
        self.router = APIRouter()
        self._setup_routes()
    
    def _register_message_handlers(self):
        """注册消息处理器"""
        self.message_router.register_handler(MessageType.SUBSCRIBE, self._handle_subscribe)
        self.message_router.register_handler(MessageType.UNSUBSCRIBE, self._handle_unsubscribe)
        self.message_router.register_handler(MessageType.GET_SUBSCRIPTIONS, self._handle_get_subscriptions)
        self.message_router.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
        self.message_router.register_handler(MessageType.PING, self._handle_ping)
        self.message_router.register_handler(MessageType.GET_STATS, self._handle_get_stats)
        logger.info("WebSocket message handlers registered")
    
    def _setup_routes(self):
        """设置路由"""
        @self.router.websocket("/ws/realtime")
        async def websocket_realtime_endpoint(
            websocket: WebSocket,
            token: Optional[str] = None
        ):
            """实时数据 WebSocket 端点"""
            await self._handle_websocket_connection(websocket, token)
        
        @self.router.websocket("/ws/market/{symbol}")
        async def websocket_symbol_endpoint(
            websocket: WebSocket,
            symbol: str,
            token: Optional[str] = None
        ):
            """特定股票的 WebSocket 端点"""
            await self._handle_websocket_connection(websocket, token, symbol)
        
        @self.router.websocket("/ws/market_data")
        async def websocket_market_data_endpoint(
            websocket: WebSocket,
            token: Optional[str] = None
        ):
            """兼容现有市场数据 WebSocket 端点"""
            await self._handle_websocket_connection(websocket, token)
        
        @self.router.get("/ws/status")
        async def websocket_status():
            """WebSocket 服务状态"""
            return await self._get_service_status()
        
        @self.router.get("/ws/connections")
        async def websocket_connections():
            """获取连接统计"""
            return await self._get_connection_stats()
        
        @self.router.get("/ws/health")
        async def websocket_health():
            """WebSocket 健康检查"""
            return await self._get_health_status()
        
        @self.router.post("/ws/broadcast")
        async def broadcast_message(message: Dict[str, Any]):
            """广播消息到所有连接"""
            return await self._broadcast_message(message)
        
        @self.router.post("/ws/disconnect/{client_id}")
        async def disconnect_client(client_id: str):
            """断开指定客户端连接"""
            return await self._disconnect_client(client_id)
    
    async def start(self):
        """启动 WebSocket 服务"""
        if self._is_running:
            logger.warning("WebSocket service already running")
            return
        
        logger.info("Starting Enhanced WebSocket Service")
        
        # 启动核心组件
        await self.connection_manager.start()
        await self.data_publisher.start()
        self.monitor.start_monitoring()
        await self.heartbeat_manager.start()
        
        # 启动后台任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self._is_running = True
        logger.info("Enhanced WebSocket Service started")
    
    async def stop(self):
        """停止 WebSocket 服务"""
        if not self._is_running:
            return
        
        logger.info("Stopping Enhanced WebSocket Service")
        
        # 停止后台任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # 停止核心组件
        await self.connection_manager.stop()
        await self.data_publisher.stop()
        self.monitor.stop_monitoring()
        await self.heartbeat_manager.stop()
        
        self._is_running = False
        logger.info("Enhanced WebSocket Service stopped")
    
    async def _handle_websocket_connection(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
        symbol: Optional[str] = None
    ):
        """处理 WebSocket 连接"""
        client_id = str(uuid.uuid4())
        
        try:
            # 建立连接
            connection_result = await self.connection_manager.connect(
                websocket, client_id, token
            )
            
            if not connection_result.success:
                await websocket.close(code=4000, reason=connection_result.message)
                return
            
            logger.info(f"WebSocket client {client_id} connected")
            
            # 启用心跳监控
            await self.heartbeat_manager.register_connection(client_id, websocket)
            
            # 发送欢迎消息
            await self._send_welcome_message(websocket, client_id, symbol)
            
            # 如果指定了股票代码，自动订阅
            if symbol:
                await self._auto_subscribe_symbol(client_id, symbol, websocket)
            
            # 消息处理循环
            await self._message_loop(websocket, client_id)
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket client {client_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket connection error for {client_id}: {e}")
        finally:
            # 清理连接
            await self.connection_manager.disconnect(client_id)
            await self.subscription_manager.unsubscribe_all(client_id)
            await self.heartbeat_manager.unregister_connection(client_id)
    
    async def _send_welcome_message(
        self,
        websocket: WebSocket,
        client_id: str,
        symbol: Optional[str] = None
    ):
        """发送欢迎消息"""
        welcome_data = {
            "client_id": client_id,
            "server_version": "2.0.0",
            "supported_data_types": [dt.value for dt in DataType],
            "max_subscriptions": self.websocket_config.max_subscriptions_per_client,
            "heartbeat_interval": self.websocket_config.heartbeat_interval,
            "timestamp": datetime.now().isoformat()
        }
        
        if symbol:
            welcome_data["auto_subscribed_symbol"] = symbol
        
        welcome_msg = WebSocketMessage(
            type=MessageType.WELCOME,
            data=welcome_data
        )
        
        await websocket.send_text(welcome_msg.model_dump_json())
    
    async def _auto_subscribe_symbol(
        self,
        client_id: str,
        symbol: str,
        websocket: WebSocket
    ):
        """自动订阅指定股票"""
        try:
            subscription_request = SubscriptionRequest(
                symbol=symbol,
                data_type=DataType.QUOTE,
                client_id=client_id
            )
            
            response = await self.subscription_manager.subscribe(
                client_id, subscription_request
            )
            
            # 发送订阅确认
            response_msg = WebSocketMessage(
                type=MessageType.SUBSCRIPTION_RESPONSE,
                data=response.model_dump()
            )
            
            await websocket.send_text(response_msg.model_dump_json())
            logger.info(f"Auto-subscribed client {client_id} to {symbol}")
            
        except Exception as e:
            logger.error(f"Auto-subscription failed for {client_id}, {symbol}: {e}")
    
    async def _message_loop(self, websocket: WebSocket, client_id: str):
        """消息处理循环"""
        try:
            while True:
                # 接收消息
                raw_message = await websocket.receive_text()
                
                # 更新连接活跃时间
                await self.connection_manager.update_heartbeat(client_id)
                await self.heartbeat_manager.update_heartbeat(client_id)
                
                # 路由消息
                result = await self.message_router.route_incoming_message(
                    client_id, raw_message, websocket
                )
                
                # 发送响应
                if result.success and result.response_data:
                    response_msg = WebSocketMessage(
                        type=MessageType.SUBSCRIPTION_RESPONSE,
                        data=result.response_data,
                        message_id=result.message_id
                    )
                    
                    formatted_response = await self.message_router.format_outgoing_message(
                        response_msg, client_id
                    )
                    
                    if isinstance(formatted_response, bytes):
                        await websocket.send_bytes(formatted_response)
                    else:
                        await websocket.send_text(formatted_response)
                
                elif not result.success:
                    error_msg = WebSocketMessage(
                        type=MessageType.ERROR,
                        data={
                            "error": result.error or result.message,
                            "message_id": result.message_id,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    await websocket.send_text(error_msg.model_dump_json())
                
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Message loop error for {client_id}: {e}")
            # 发送错误消息
            error_msg = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error": f"Internal error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            )
            try:
                await websocket.send_text(error_msg.model_dump_json())
            except:
                pass  # 连接可能已断开
    
    async def _heartbeat_loop(self):
        """心跳检测循环"""
        while self._is_running:
            try:
                await asyncio.sleep(self.websocket_config.heartbeat_interval)
                
                # 检查所有连接的心跳
                inactive_clients = await self.connection_manager.check_heartbeats()
                
                # 断开不活跃的连接
                for client_id in inactive_clients:
                    logger.info(f"Disconnecting inactive client: {client_id}")
                    await self.connection_manager.disconnect(client_id)
                    await self.subscription_manager.unsubscribe_all(client_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self._is_running:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                # 清理过期的订阅
                await self.subscription_manager.cleanup_expired_subscriptions()
                
                # 清理连接统计
                await self.connection_manager.cleanup_stats()
                
                # 更新监控指标
                await self.monitor.update_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    # 消息处理器
    async def _handle_subscribe(self, client_id: str, message: WebSocketMessage, websocket):
        """处理订阅消息"""
        try:
            subscription_request = SubscriptionRequest(**message.data)
            subscription_request.client_id = client_id
            
            # 验证订阅请求
            validation_result = await self.subscription_manager.validate_subscription_request(
                subscription_request
            )
            
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "error": ", ".join(validation_result["errors"]),
                    "message_id": message.message_id
                }
            
            # 添加订阅
            response = await self.subscription_manager.subscribe(
                client_id, subscription_request
            )
            
            logger.info(f"Client {client_id} subscribed to {subscription_request.symbol} {subscription_request.data_type}")
            
            return {
                "success": True,
                "response_data": response.model_dump(),
                "message_id": message.message_id
            }
            
        except Exception as e:
            logger.error(f"Subscribe error for {client_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message_id": message.message_id
            }
    
    async def _handle_unsubscribe(self, client_id: str, message: WebSocketMessage, websocket):
        """处理取消订阅消息"""
        try:
            subscription_id = message.data.get("subscription_id")
            
            if not subscription_id:
                return {
                    "success": False,
                    "error": "Missing subscription_id",
                    "message_id": message.message_id
                }
            
            success = await self.subscription_manager.unsubscribe(client_id, subscription_id)
            
            return {
                "success": success,
                "response_data": {
                    "subscription_id": subscription_id,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                },
                "message_id": message.message_id
            }
            
        except Exception as e:
            logger.error(f"Unsubscribe error for {client_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message_id": message.message_id
            }
    
    async def _handle_get_subscriptions(self, client_id: str, message: WebSocketMessage, websocket):
        """处理获取订阅列表消息"""
        try:
            subscriptions = await self.subscription_manager.get_client_subscriptions(client_id)
            
            return {
                "success": True,
                "response_data": {
                    "subscriptions": [sub.model_dump() for sub in subscriptions],
                    "count": len(subscriptions),
                    "timestamp": datetime.now().isoformat()
                },
                "message_id": message.message_id
            }
            
        except Exception as e:
            logger.error(f"Get subscriptions error for {client_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message_id": message.message_id
            }
    
    async def _handle_heartbeat(self, client_id: str, message: WebSocketMessage, websocket):
        """处理心跳消息"""
        try:
            # 计算延迟
            latency_ms = None
            if message.data and "client_time" in message.data:
                try:
                    client_time = datetime.fromisoformat(message.data["client_time"])
                    latency_ms = (datetime.now() - client_time).total_seconds() * 1000
                except:
                    pass
            
            # 更新心跳
            await self.connection_manager.update_heartbeat(client_id)
            await self.heartbeat_manager.update_heartbeat(client_id, latency_ms)
            
            return {
                "success": True,
                "response_data": {
                    "type": "heartbeat",
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat(),
                    "client_time": message.data.get("client_time") if message.data else None,
                    "latency_ms": latency_ms
                },
                "message_id": message.message_id
            }
            
        except Exception as e:
            logger.error(f"Heartbeat error for {client_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message_id": message.message_id
            }
    
    async def _handle_ping(self, client_id: str, message: WebSocketMessage, websocket):
        """处理 Ping 消息"""
        try:
            return {
                "success": True,
                "response_data": {
                    "type": "pong",
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat(),
                    "original_message_id": message.message_id
                },
                "message_id": message.message_id
            }
            
        except Exception as e:
            logger.error(f"Ping error for {client_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message_id": message.message_id
            }
    
    async def _handle_get_stats(self, client_id: str, message: WebSocketMessage, websocket):
        """处理获取统计信息消息"""
        try:
            connection_stats = self.connection_manager.get_stats()
            subscription_stats = await self.subscription_manager.get_subscription_stats()
            publisher_stats = await self.data_publisher.get_publisher_stats()
            from dataclasses import asdict
            monitor_stats = asdict(self.monitor.get_current_metrics())
            heartbeat_stats = self.heartbeat_manager.get_heartbeat_stats()
            
            stats = {
                "connections": connection_stats,
                "subscriptions": subscription_stats,
                "publisher": publisher_stats,
                "performance": monitor_stats,
                "heartbeat": heartbeat_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "response_data": stats,
                "message_id": message.message_id
            }
            
        except Exception as e:
            logger.error(f"Get stats error for {client_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message_id": message.message_id
            }
    
    # HTTP 端点处理器
    async def _get_service_status(self):
        """获取服务状态"""
        try:
            connection_stats = self.connection_manager.get_stats()
            subscription_stats = await self.subscription_manager.get_subscription_stats()
            heartbeat_stats = self.heartbeat_manager.get_heartbeat_stats()
            
            return {
                "status": "running" if self._is_running else "stopped",
                "connections": connection_stats,
                "subscriptions": subscription_stats,
                "heartbeat": heartbeat_stats,
                "uptime": datetime.now().isoformat(),
                "version": "2.0.0",
                "features": {
                    "heartbeat_detection": True,
                    "auto_reconnect": True,
                    "graceful_shutdown": True,
                    "message_compression": True,
                    "subscription_management": True
                }
            }
            
        except Exception as e:
            logger.error(f"Get service status error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_connection_stats(self):
        """获取连接统计"""
        try:
            stats = self.connection_manager.get_stats()
            stats["heartbeat"] = self.heartbeat_manager.get_heartbeat_stats()
            return stats
        except Exception as e:
            logger.error(f"Get connection stats error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_health_status(self):
        """获取健康状态"""
        try:
            healthy_connections = self.heartbeat_manager.get_healthy_connections()
            unhealthy_connections = self.heartbeat_manager.get_unhealthy_connections()
            
            return {
                "status": "healthy" if self._is_running else "unhealthy",
                "service_running": self._is_running,
                "total_connections": len(self.connection_manager.active_connections),
                "healthy_connections": len(healthy_connections),
                "unhealthy_connections": len(unhealthy_connections),
                "heartbeat_manager_running": self.heartbeat_manager.is_running,
                "data_publisher_running": self.data_publisher.is_running if hasattr(self.data_publisher, 'is_running') else True,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Get health status error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _broadcast_message(self, message: Dict[str, Any]):
        """广播消息"""
        try:
            broadcast_msg = WebSocketMessage(
                type=MessageType.STATUS,
                data=message
            )
            
            result = await self.connection_manager.broadcast_message(broadcast_msg)
            
            return {
                "success": True,
                "message": "Message broadcasted",
                "sent_count": result.sent_count,
                "failed_count": result.failed_count,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Broadcast message error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _disconnect_client(self, client_id: str):
        """断开指定客户端连接"""
        try:
            # 发送断开通知
            disconnect_msg = WebSocketMessage(
                type=MessageType.STATUS,
                data={
                    "type": "disconnect_notice",
                    "message": "Connection will be closed by server",
                    "reason": "Administrative disconnect",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # 尝试发送通知
            await self.connection_manager.send_message(client_id, disconnect_msg)
            
            # 等待一小段时间让客户端处理消息
            await asyncio.sleep(0.5)
            
            # 断开连接
            await self.connection_manager.disconnect(client_id)
            await self.subscription_manager.unsubscribe_all(client_id)
            await self.heartbeat_manager.unregister_connection(client_id)
            
            return {
                "success": True,
                "message": f"Client {client_id} disconnected",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Disconnect client error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# 全局实例 - 延迟初始化以避免导入时错误
enhanced_websocket_endpoints = None

def get_enhanced_websocket_endpoints():
    """获取增强的 WebSocket 端点实例"""
    global enhanced_websocket_endpoints
    if enhanced_websocket_endpoints is None:
        enhanced_websocket_endpoints = EnhancedWebSocketEndpoints()
    return enhanced_websocket_endpoints

# 导出路由器 - 延迟获取
def get_router():
    """获取 WebSocket 路由器"""
    return get_enhanced_websocket_endpoints().router

# 为了向后兼容，创建一个默认路由器
from fastapi.routing import APIRouter
router = APIRouter()

# 导出启动和停止函数
async def start_websocket_service():
    """启动 WebSocket 服务"""
    await enhanced_websocket_endpoints.start()

async def stop_websocket_service():
    """停止 WebSocket 服务"""
    await enhanced_websocket_endpoints.stop()

# 导出实例
__all__ = ["router", "get_enhanced_websocket_endpoints", "get_router", "start_websocket_service", "stop_websocket_service"]