"""
WebSocket 实时数据系统 - 连接管理器
根据 tasks.md 任务2要求实现的 WebSocket 连接管理器
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from .websocket_models import (
    WebSocketConnection, ConnectionStatus, ConnectionStats, 
    ConnectionResult, WebSocketMessage, MessageType, StatusMessage,
    HeartbeatMessage, WebSocketConfig, ErrorMessage
)

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """WebSocket连接管理器 - 管理WebSocket连接的生命周期和状态"""
    
    def __init__(self, config: Optional[WebSocketConfig] = None):
        self.config = config or WebSocketConfig()
        self.active_connections: Dict[str, WebSocketConnection] = {}
        self.websocket_objects: Dict[str, WebSocket] = {}
        self.connection_stats = ConnectionStats()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
    async def start(self) -> None:
        """启动连接管理器"""
        logger.info("Starting WebSocket Connection Manager")
        self._cleanup_task = asyncio.create_task(self._cleanup_inactive_connections())
        self._monitoring_task = asyncio.create_task(self._monitor_connections())
        
    async def stop(self) -> None:
        """停止连接管理器"""
        logger.info("Stopping WebSocket Connection Manager")
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
            
        # 关闭所有连接
        for client_id in list(self.active_connections.keys()):
            await self.disconnect(client_id)
            
    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        auth_token: Optional[str] = None
    ) -> ConnectionResult:
        """
        建立WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
            client_id: 客户端唯一标识
            auth_token: 认证令牌
            
        Returns:
            ConnectionResult: 连接结果
        """
        try:
            # 检查连接数限制
            if len(self.active_connections) >= self.config.max_connections:
                return ConnectionResult(
                    success=False,
                    client_id=client_id,
                    message=f"连接数已达上限: {self.config.max_connections}",
                    error="MAX_CONNECTIONS_EXCEEDED"
                )
                
            # 检查是否已连接
            if client_id in self.active_connections:
                logger.warning(f"Client {client_id} already connected, disconnecting old connection")
                await self.disconnect(client_id)
                
            # 认证检查
            auth_info = None
            if auth_token:
                auth_info = await self._authenticate(auth_token)
                if not auth_info:
                    return ConnectionResult(
                        success=False,
                        client_id=client_id,
                        message="认证失败",
                        error="AUTHENTICATION_FAILED"
                    )
            
            # 接受连接
            await websocket.accept()
            
            # 创建连接信息
            connection = WebSocketConnection(
                client_id=client_id,
                connected_at=datetime.now(),
                last_ping=datetime.now(),
                auth_info=auth_info,
                remote_address=self._get_remote_address(websocket),
                status=ConnectionStatus.CONNECTED
            )
            
            # 存储连接
            async with self._lock:
                self.active_connections[client_id] = connection
                self.websocket_objects[client_id] = websocket
                self.connection_stats.total_connections += 1
                self.connection_stats.active_connections = len(self.active_connections)
                
            logger.info(f"Client {client_id} connected successfully")
            
            # 发送连接确认
            await self._send_connection_confirmation(client_id)
            
            return ConnectionResult(
                success=True,
                client_id=client_id,
                message="连接成功",
                connection_info=connection
            )
            
        except Exception as e:
            logger.error(f"Failed to connect client {client_id}: {str(e)}")
            return ConnectionResult(
                success=False,
                client_id=client_id,
                message=f"连接失败: {str(e)}",
                error="CONNECTION_FAILED"
            )
    
    async def disconnect(self, client_id: str) -> None:
        """
        断开WebSocket连接
        
        Args:
            client_id: 客户端唯一标识
        """
        try:
            if client_id not in self.active_connections:
                return
                
            async with self._lock:
                connection = self.active_connections.pop(client_id, None)
                websocket = self.websocket_objects.pop(client_id, None)
                
                if websocket:
                    try:
                        await websocket.close()
                    except Exception as e:
                        logger.warning(f"Error closing websocket for {client_id}: {e}")
                
                if connection:
                    connection.status = ConnectionStatus.DISCONNECTED
                    self.connection_stats.active_connections = len(self.active_connections)
                    
            logger.info(f"Client {client_id} disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting client {client_id}: {e}")
    
    async def send_message(
        self,
        client_id: str,
        message: WebSocketMessage
    ) -> bool:
        """
        向指定客户端发送消息
        
        Args:
            client_id: 客户端唯一标识
            message: 要发送的消息
            
        Returns:
            bool: 发送是否成功
        """
        try:
            if client_id not in self.websocket_objects:
                logger.warning(f"Client {client_id} not found")
                return False
                
            websocket = self.websocket_objects[client_id]
            
            # 准备消息
            message_json = message.model_dump_json()
            
            # 检查消息大小
            if len(message_json.encode('utf-8')) > self.config.max_message_size:
                logger.error(f"Message too large for client {client_id}")
                return False
            
            # 发送消息
            await websocket.send_text(message_json)
            
            # 更新统计
            async with self._lock:
                if client_id in self.active_connections:
                    self.active_connections[client_id].message_count += 1
                    self.active_connections[client_id].bytes_sent += len(message_json.encode('utf-8'))
                self.connection_stats.messages_sent += 1
                self.connection_stats.bytes_sent += len(message_json.encode('utf-8'))
                
            return True
            
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during send")
            await self.disconnect(client_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to {client_id}: {e}")
            return False
    
    async def broadcast_message(
        self,
        message: WebSocketMessage,
        target_clients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        向多个客户端广播消息
        
        Args:
            message: 要广播的消息
            target_clients: 目标客户端列表，None表示所有客户端
            
        Returns:
            Dict: 广播结果统计
        """
        if target_clients is None:
            target_clients = list(self.active_connections.keys())
            
        success_count = 0
        failure_count = 0
        errors = []
        
        start_time = asyncio.get_event_loop().time()
        
        # 并发发送消息
        tasks = []
        for client_id in target_clients:
            if client_id in self.active_connections:
                tasks.append(self.send_message(client_id, message))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({
                    "client_id": target_clients[i],
                    "error": str(result)
                })
                failure_count += 1
            elif result:
                success_count += 1
            else:
                failure_count += 1
        
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return {
            "total_clients": len(target_clients),
            "success_count": success_count,
            "failure_count": failure_count,
            "errors": errors,
            "elapsed_ms": elapsed_ms
        }
    
    async def send_heartbeat(self, client_id: str) -> bool:
        """发送心跳消息"""
        try:
            if client_id not in self.active_connections:
                return False
                
            connection = self.active_connections[client_id]
            heartbeat = HeartbeatMessage(
                client_id=client_id,
                connection_uptime=(datetime.now() - connection.connected_at).total_seconds()
            )
            
            message = WebSocketMessage(
                type=MessageType.PING,
                data=heartbeat.model_dump()
            )
            
            return await self.send_message(client_id, message)
        except Exception as e:
            logger.error(f"Error sending heartbeat to {client_id}: {e}")
            return False
    
    async def get_connection_stats(self) -> ConnectionStats:
        """获取连接统计信息"""
        async with self._lock:
            return self.connection_stats.model_copy()
    
    async def get_client_connections(self) -> List[WebSocketConnection]:
        """获取所有客户端连接信息"""
        async with self._lock:
            return list(self.active_connections.values())
    
    async def get_client_connection(self, client_id: str) -> Optional[WebSocketConnection]:
        """获取指定客户端连接信息"""
        return self.active_connections.get(client_id)
    
    async def update_client_activity(self, client_id: str) -> None:
        """更新客户端最后活动时间"""
        async with self._lock:
            if client_id in self.active_connections:
                self.active_connections[client_id].last_ping = datetime.now()
    
    async def update_heartbeat(self, client_id: str) -> None:
        """更新客户端心跳时间"""
        await self.update_client_activity(client_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计信息（同步版本）"""
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.connection_stats.total_connections,
            "messages_sent": self.connection_stats.messages_sent,
            "messages_received": self.connection_stats.messages_received,
            "bytes_sent": self.connection_stats.bytes_sent,
            "bytes_received": self.connection_stats.bytes_received,
            "connection_errors": self.connection_stats.connection_errors,
            "average_latency_ms": self.connection_stats.average_latency_ms,
            "uptime_start": self.connection_stats.uptime_start.isoformat()
        }
    
    async def cleanup_inactive_connections(self) -> int:
        """清理不活跃的连接"""
        try:
            cutoff_time = datetime.now() - timedelta(seconds=self.config.heartbeat_interval * 3)
            clients_to_disconnect = []
            
            async with self._lock:
                for client_id, connection in self.active_connections.items():
                    if connection.last_ping < cutoff_time:
                        clients_to_disconnect.append(client_id)
            
            for client_id in clients_to_disconnect:
                logger.info(f"Cleaning up inactive connection: {client_id}")
                await self.disconnect(client_id)
                
            return len(clients_to_disconnect)
            
        except Exception as e:
            logger.error(f"Error cleaning up connections: {e}")
            return 0
    
    async def _authenticate(self, auth_token: str) -> Optional[Dict[str, Any]]:
        """
        认证用户
        
        Args:
            auth_token: 认证令牌
            
        Returns:
            Optional[Dict]: 认证信息，失败返回None
        """
        # TODO: 实现实际的认证逻辑
        # 这里可以集成现有的认证系统
        return {
            "user_id": "user_123",
            "permissions": ["read_market_data", "subscribe_realtime"],
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
        }
    
    async def _send_connection_confirmation(self, client_id: str) -> None:
        """发送连接确认消息"""
        try:
            connection = self.active_connections.get(client_id)
            if not connection:
                return
                
            status_message = StatusMessage(
                type="connection_established",
                message="WebSocket连接已建立",
                details={
                    "client_id": client_id,
                    "connected_at": connection.connected_at.isoformat(),
                    "heartbeat_interval": self.config.heartbeat_interval
                }
            )
            
            message = WebSocketMessage(
                type=MessageType.STATUS,
                data=status_message.model_dump()
            )
            
            await self.send_message(client_id, message)
            
        except Exception as e:
            logger.error(f"Error sending connection confirmation to {client_id}: {e}")
    
    def _get_remote_address(self, websocket: WebSocket) -> str:
        """获取客户端远程地址"""
        try:
            client = websocket.client
            return f"{client.host}:{client.port}"
        except:
            return "unknown"
    
    async def _cleanup_inactive_connections(self) -> None:
        """后台清理任务"""
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                cleaned = await self.cleanup_inactive_connections()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} inactive connections")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def _monitor_connections(self) -> None:
        """监控连接状态"""
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                # 发送心跳给所有连接
                tasks = []
                for client_id in list(self.active_connections.keys()):
                    tasks.append(self.send_heartbeat(client_id))
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring task: {e}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            "status": "healthy" if self.connection_stats.active_connections >= 0 else "unhealthy",
            "active_connections": self.connection_stats.active_connections,
            "total_connections": self.connection_stats.total_connections,
            "messages_sent": self.connection_stats.messages_sent,
            "messages_received": self.connection_stats.messages_received,
            "uptime": (datetime.now() - self.connection_stats.uptime_start).total_seconds()
        }