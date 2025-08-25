"""
WebSocket 心跳检测和自动重连机制
实现客户端和服务端的心跳检测、连接状态监控和自动重连功能
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

from .websocket_models import (
    WebSocketMessage, MessageType, HeartbeatMessage, ConnectionStatus
)

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatConfig:
    """心跳配置"""
    interval: float = 30.0  # 心跳间隔（秒）
    timeout: float = 60.0   # 心跳超时（秒）
    max_missed_heartbeats: int = 3  # 最大丢失心跳次数
    reconnect_interval: float = 5.0  # 重连间隔（秒）
    max_reconnect_attempts: int = 5  # 最大重连尝试次数


@dataclass
class ConnectionHealth:
    """连接健康状态"""
    client_id: str
    last_heartbeat: datetime
    missed_heartbeats: int = 0
    is_healthy: bool = True
    reconnect_attempts: int = 0
    connection_start_time: datetime = field(default_factory=datetime.now)
    total_heartbeats_sent: int = 0
    total_heartbeats_received: int = 0
    average_latency_ms: float = 0.0


class WebSocketHeartbeatManager:
    """WebSocket 心跳管理器"""
    
    def __init__(self, config: HeartbeatConfig = None):
        self.config = config or HeartbeatConfig()
        self.connection_health: Dict[str, ConnectionHealth] = {}
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 回调函数
        self.on_connection_lost: Optional[Callable[[str], None]] = None
        self.on_connection_restored: Optional[Callable[[str], None]] = None
        self.on_heartbeat_timeout: Optional[Callable[[str], None]] = None
    
    async def start(self):
        """启动心跳管理器"""
        if self.is_running:
            logger.warning("HeartbeatManager already running")
            return
        
        self.is_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("WebSocket HeartbeatManager started")
    
    async def stop(self):
        """停止心跳管理器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止所有心跳任务
        for task in self.heartbeat_tasks.values():
            task.cancel()
        
        # 等待任务完成
        if self.heartbeat_tasks:
            await asyncio.gather(*self.heartbeat_tasks.values(), return_exceptions=True)
        
        # 停止清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.heartbeat_tasks.clear()
        self.connection_health.clear()
        logger.info("WebSocket HeartbeatManager stopped")
    
    async def register_connection(self, client_id: str, websocket) -> bool:
        """注册连接进行心跳监控"""
        try:
            if client_id in self.connection_health:
                logger.warning(f"Connection {client_id} already registered for heartbeat")
                return False
            
            # 创建连接健康状态
            health = ConnectionHealth(
                client_id=client_id,
                last_heartbeat=datetime.now()
            )
            
            self.connection_health[client_id] = health
            
            # 启动心跳任务
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(client_id, websocket)
            )
            self.heartbeat_tasks[client_id] = heartbeat_task
            
            logger.info(f"Registered connection {client_id} for heartbeat monitoring")
            return True
            
        except Exception as e:
            logger.error(f"Error registering connection {client_id} for heartbeat: {e}")
            return False
    
    async def unregister_connection(self, client_id: str):
        """取消注册连接"""
        try:
            # 停止心跳任务
            if client_id in self.heartbeat_tasks:
                task = self.heartbeat_tasks.pop(client_id)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # 移除健康状态
            if client_id in self.connection_health:
                del self.connection_health[client_id]
            
            logger.info(f"Unregistered connection {client_id} from heartbeat monitoring")
            
        except Exception as e:
            logger.error(f"Error unregistering connection {client_id}: {e}")
    
    async def update_heartbeat(self, client_id: str, latency_ms: float = None):
        """更新连接心跳"""
        try:
            if client_id not in self.connection_health:
                logger.warning(f"Connection {client_id} not registered for heartbeat")
                return
            
            health = self.connection_health[client_id]
            health.last_heartbeat = datetime.now()
            health.missed_heartbeats = 0
            health.total_heartbeats_received += 1
            
            # 更新延迟统计
            if latency_ms is not None:
                if health.average_latency_ms == 0:
                    health.average_latency_ms = latency_ms
                else:
                    # 使用指数移动平均
                    health.average_latency_ms = (health.average_latency_ms * 0.8) + (latency_ms * 0.2)
            
            # 如果连接之前不健康，现在恢复了
            if not health.is_healthy:
                health.is_healthy = True
                health.reconnect_attempts = 0
                logger.info(f"Connection {client_id} health restored")
                
                if self.on_connection_restored:
                    try:
                        await self.on_connection_restored(client_id)
                    except Exception as e:
                        logger.error(f"Error in connection restored callback: {e}")
            
        except Exception as e:
            logger.error(f"Error updating heartbeat for {client_id}: {e}")
    
    async def _heartbeat_loop(self, client_id: str, websocket):
        """心跳循环"""
        try:
            while self.is_running and client_id in self.connection_health:
                await asyncio.sleep(self.config.interval)
                
                health = self.connection_health.get(client_id)
                if not health:
                    break
                
                try:
                    # 发送心跳消息
                    heartbeat_msg = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        data={
                            "client_id": client_id,
                            "server_time": datetime.now().isoformat(),
                            "sequence": health.total_heartbeats_sent + 1
                        }
                    )
                    
                    await websocket.send_text(heartbeat_msg.model_dump_json())
                    health.total_heartbeats_sent += 1
                    
                    # 检查心跳超时
                    time_since_last_heartbeat = datetime.now() - health.last_heartbeat
                    
                    if time_since_last_heartbeat.total_seconds() > self.config.timeout:
                        health.missed_heartbeats += 1
                        logger.warning(f"Missed heartbeat for {client_id}, count: {health.missed_heartbeats}")
                        
                        # 检查是否超过最大丢失次数
                        if health.missed_heartbeats >= self.config.max_missed_heartbeats:
                            health.is_healthy = False
                            logger.error(f"Connection {client_id} unhealthy, missed {health.missed_heartbeats} heartbeats")
                            
                            if self.on_heartbeat_timeout:
                                try:
                                    await self.on_heartbeat_timeout(client_id)
                                except Exception as e:
                                    logger.error(f"Error in heartbeat timeout callback: {e}")
                            
                            # 触发连接丢失回调
                            if self.on_connection_lost:
                                try:
                                    await self.on_connection_lost(client_id)
                                except Exception as e:
                                    logger.error(f"Error in connection lost callback: {e}")
                            
                            break
                    
                except Exception as e:
                    logger.error(f"Error sending heartbeat to {client_id}: {e}")
                    health.missed_heartbeats += 1
                    
                    if health.missed_heartbeats >= self.config.max_missed_heartbeats:
                        health.is_healthy = False
                        break
                
        except asyncio.CancelledError:
            logger.info(f"Heartbeat loop cancelled for {client_id}")
        except Exception as e:
            logger.error(f"Heartbeat loop error for {client_id}: {e}")
        finally:
            # 清理
            if client_id in self.heartbeat_tasks:
                del self.heartbeat_tasks[client_id]
    
    async def _cleanup_loop(self):
        """清理循环"""
        try:
            while self.is_running:
                await asyncio.sleep(60)  # 每分钟清理一次
                
                current_time = datetime.now()
                unhealthy_connections = []
                
                for client_id, health in self.connection_health.items():
                    # 检查长时间未活跃的连接
                    time_since_last_heartbeat = current_time - health.last_heartbeat
                    
                    if time_since_last_heartbeat.total_seconds() > (self.config.timeout * 2):
                        unhealthy_connections.append(client_id)
                
                # 清理不健康的连接
                for client_id in unhealthy_connections:
                    logger.info(f"Cleaning up unhealthy connection: {client_id}")
                    await self.unregister_connection(client_id)
                
        except asyncio.CancelledError:
            logger.info("Heartbeat cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Heartbeat cleanup loop error: {e}")
    
    def get_connection_health(self, client_id: str) -> Optional[ConnectionHealth]:
        """获取连接健康状态"""
        return self.connection_health.get(client_id)
    
    def get_all_connection_health(self) -> Dict[str, ConnectionHealth]:
        """获取所有连接健康状态"""
        return self.connection_health.copy()
    
    def get_healthy_connections(self) -> List[str]:
        """获取健康连接列表"""
        return [
            client_id for client_id, health in self.connection_health.items()
            if health.is_healthy
        ]
    
    def get_unhealthy_connections(self) -> List[str]:
        """获取不健康连接列表"""
        return [
            client_id for client_id, health in self.connection_health.items()
            if not health.is_healthy
        ]
    
    def get_heartbeat_stats(self) -> Dict[str, Any]:
        """获取心跳统计信息"""
        total_connections = len(self.connection_health)
        healthy_connections = len(self.get_healthy_connections())
        unhealthy_connections = total_connections - healthy_connections
        
        total_heartbeats_sent = sum(h.total_heartbeats_sent for h in self.connection_health.values())
        total_heartbeats_received = sum(h.total_heartbeats_received for h in self.connection_health.values())
        
        average_latency = 0.0
        if self.connection_health:
            average_latency = sum(h.average_latency_ms for h in self.connection_health.values()) / len(self.connection_health)
        
        return {
            "total_connections": total_connections,
            "healthy_connections": healthy_connections,
            "unhealthy_connections": unhealthy_connections,
            "total_heartbeats_sent": total_heartbeats_sent,
            "total_heartbeats_received": total_heartbeats_received,
            "average_latency_ms": round(average_latency, 2),
            "config": {
                "interval": self.config.interval,
                "timeout": self.config.timeout,
                "max_missed_heartbeats": self.config.max_missed_heartbeats
            }
        }


class WebSocketReconnectManager:
    """WebSocket 重连管理器"""
    
    def __init__(self, config: HeartbeatConfig = None):
        self.config = config or HeartbeatConfig()
        self.reconnect_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        
        # 回调函数
        self.on_reconnect_attempt: Optional[Callable[[str, int], None]] = None
        self.on_reconnect_success: Optional[Callable[[str], None]] = None
        self.on_reconnect_failed: Optional[Callable[[str], None]] = None
    
    async def start(self):
        """启动重连管理器"""
        if self.is_running:
            logger.warning("ReconnectManager already running")
            return
        
        self.is_running = True
        logger.info("WebSocket ReconnectManager started")
    
    async def stop(self):
        """停止重连管理器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止所有重连任务
        for task in self.reconnect_tasks.values():
            task.cancel()
        
        # 等待任务完成
        if self.reconnect_tasks:
            await asyncio.gather(*self.reconnect_tasks.values(), return_exceptions=True)
        
        self.reconnect_tasks.clear()
        logger.info("WebSocket ReconnectManager stopped")
    
    async def schedule_reconnect(
        self,
        client_id: str,
        reconnect_callback: Callable[[], Any]
    ):
        """安排重连"""
        if client_id in self.reconnect_tasks:
            logger.warning(f"Reconnect already scheduled for {client_id}")
            return
        
        reconnect_task = asyncio.create_task(
            self._reconnect_loop(client_id, reconnect_callback)
        )
        self.reconnect_tasks[client_id] = reconnect_task
        
        logger.info(f"Scheduled reconnect for {client_id}")
    
    async def cancel_reconnect(self, client_id: str):
        """取消重连"""
        if client_id in self.reconnect_tasks:
            task = self.reconnect_tasks.pop(client_id)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            logger.info(f"Cancelled reconnect for {client_id}")
    
    async def _reconnect_loop(self, client_id: str, reconnect_callback: Callable):
        """重连循环"""
        attempt = 0
        
        try:
            while self.is_running and attempt < self.config.max_reconnect_attempts:
                attempt += 1
                
                logger.info(f"Reconnect attempt {attempt}/{self.config.max_reconnect_attempts} for {client_id}")
                
                if self.on_reconnect_attempt:
                    try:
                        await self.on_reconnect_attempt(client_id, attempt)
                    except Exception as e:
                        logger.error(f"Error in reconnect attempt callback: {e}")
                
                try:
                    # 尝试重连
                    result = await reconnect_callback()
                    
                    if result:
                        logger.info(f"Reconnect successful for {client_id}")
                        
                        if self.on_reconnect_success:
                            try:
                                await self.on_reconnect_success(client_id)
                            except Exception as e:
                                logger.error(f"Error in reconnect success callback: {e}")
                        
                        break
                    
                except Exception as e:
                    logger.error(f"Reconnect attempt {attempt} failed for {client_id}: {e}")
                
                # 等待重连间隔
                if attempt < self.config.max_reconnect_attempts:
                    await asyncio.sleep(self.config.reconnect_interval * attempt)  # 指数退避
            
            else:
                # 重连失败
                logger.error(f"All reconnect attempts failed for {client_id}")
                
                if self.on_reconnect_failed:
                    try:
                        await self.on_reconnect_failed(client_id)
                    except Exception as e:
                        logger.error(f"Error in reconnect failed callback: {e}")
        
        except asyncio.CancelledError:
            logger.info(f"Reconnect loop cancelled for {client_id}")
        except Exception as e:
            logger.error(f"Reconnect loop error for {client_id}: {e}")
        finally:
            # 清理
            if client_id in self.reconnect_tasks:
                del self.reconnect_tasks[client_id]


# 导出主要组件
__all__ = [
    "HeartbeatConfig",
    "ConnectionHealth", 
    "WebSocketHeartbeatManager",
    "WebSocketReconnectManager"
]