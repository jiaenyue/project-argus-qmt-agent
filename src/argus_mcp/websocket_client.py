"""
WebSocket客户端SDK
提供易于使用的客户端API，支持连接管理、订阅管理和错误处理
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid
import time
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class SubscriptionConfig:
    """订阅配置"""
    symbols: List[str]
    data_types: List[str]
    update_frequency: str = "realtime"
    filters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}


@dataclass
class ConnectionConfig:
    """连接配置"""
    url: str
    api_key: Optional[str] = None
    max_reconnect_attempts: int = 5
    reconnect_delay: float = 1.0
    heartbeat_interval: int = 30
    timeout: int = 10
    max_subscriptions: int = 100


class WebSocketClient:
    """WebSocket客户端"""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.websocket = None
        self.subscriptions: Dict[str, SubscriptionConfig] = {}
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.connection_id = None
        self.last_heartbeat = None
        self.reconnect_attempts = 0
        self._heartbeat_task = None
        self._message_queue = asyncio.Queue()
        self._running = False
        
        # 统计信息
        self.stats = {
            "messages_received": 0,
            "messages_sent": 0,
            "reconnect_count": 0,
            "errors": 0,
            "connection_start_time": None
        }
    
    async def connect(self) -> bool:
        """连接到服务器"""
        try:
            self.state = ConnectionState.CONNECTING
            logger.info(f"连接到WebSocket服务器: {self.config.url}")
            
            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            self.websocket = await websockets.connect(
                self.config.url,
                extra_headers=headers,
                ping_interval=self.config.heartbeat_interval,
                ping_timeout=self.config.timeout
            )
            
            self.state = ConnectionState.CONNECTED
            self.connection_id = str(uuid.uuid4())
            self.stats["connection_start_time"] = datetime.now()
            self.reconnect_attempts = 0
            
            # 启动心跳和消息处理
            self._running = True
            self._start_tasks()
            
            logger.info(f"连接成功，连接ID: {self.connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.state = ConnectionState.DISCONNECTED
        logger.info("连接已断开")
    
    async def subscribe(self, subscription_id: str, config: SubscriptionConfig) -> bool:
        """订阅数据"""
        if self.state != ConnectionState.CONNECTED:
            logger.error("未连接到服务器")
            return False
        
        if len(self.subscriptions) >= self.config.max_subscriptions:
            logger.error("达到最大订阅数量限制")
            return False
        
        message = {
            "type": "subscribe",
            "id": subscription_id,
            "symbols": config.symbols,
            "data_types": config.data_types,
            "update_frequency": config.update_frequency,
            "filters": config.filters
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            self.subscriptions[subscription_id] = config
            self.stats["messages_sent"] += 1
            logger.info(f"订阅成功: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"订阅失败: {e}")
            return False
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        if subscription_id not in self.subscriptions:
            logger.warning(f"订阅不存在: {subscription_id}")
            return False
        
        message = {
            "type": "unsubscribe",
            "id": subscription_id
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            del self.subscriptions[subscription_id]
            self.stats["messages_sent"] += 1
            logger.info(f"取消订阅成功: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            return False
    
    def add_message_handler(self, data_type: str, handler: Callable):
        """添加消息处理器"""
        if data_type not in self.message_handlers:
            self.message_handlers[data_type] = []
        self.message_handlers[data_type].append(handler)
    
    def remove_message_handler(self, data_type: str, handler: Callable):
        """移除消息处理器"""
        if data_type in self.message_handlers:
            try:
                self.message_handlers[data_type].remove(handler)
            except ValueError:
                pass
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        uptime = None
        if self.stats["connection_start_time"]:
            uptime = datetime.now() - self.stats["connection_start_time"]
        
        return {
            **self.stats,
            "state": self.state.value,
            "connection_id": self.connection_id,
            "subscriptions_count": len(self.subscriptions),
            "uptime": str(uptime) if uptime else None
        }
    
    def _start_tasks(self):
        """启动后台任务"""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._message_handler_loop())
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running and self.state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                if self.websocket:
                    await self.websocket.send(json.dumps({"type": "heartbeat"}))
                    self.last_heartbeat = datetime.now()
            except Exception as e:
                logger.error(f"心跳失败: {e}")
                if self._running:
                    await self._handle_reconnection()
    
    async def _message_handler_loop(self):
        """消息处理循环"""
        while self._running:
            try:
                if self.websocket:
                    message = await self.websocket.recv()
                    await self._process_message(message)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("连接关闭")
                if self._running:
                    await self._handle_reconnection()
                break
            except Exception as e:
                logger.error(f"消息处理错误: {e}")
                self.stats["errors"] += 1
    
    async def _process_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            self.stats["messages_received"] += 1
            
            message_type = data.get("type")
            
            if message_type == "data":
                await self._handle_data_message(data)
            elif message_type == "error":
                await self._handle_error_message(data)
            elif message_type == "heartbeat_response":
                self.last_heartbeat = datetime.now()
            
        except json.JSONDecodeError:
            logger.error(f"无效的消息格式: {message}")
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
    
    async def _handle_data_message(self, data: Dict):
        """处理数据消息"""
        data_type = data.get("data_type")
        if data_type in self.message_handlers:
            for handler in self.message_handlers[data_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"消息处理器错误: {e}")
    
    async def _handle_error_message(self, data: Dict):
        """处理错误消息"""
        logger.error(f"收到服务器错误: {data}")
        self.stats["errors"] += 1
    
    async def _handle_reconnection(self):
        """处理重连"""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("达到最大重连次数")
            self.state = ConnectionState.ERROR
            await self.disconnect()
            return
        
        self.state = ConnectionState.RECONNECTING
        self.reconnect_attempts += 1
        self.stats["reconnect_count"] += 1
        
        delay = min(self.config.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 30)
        logger.info(f"{delay}秒后重试连接...")
        
        await asyncio.sleep(delay)
        
        if await self.connect():
            # 重连成功，重新订阅
            for sub_id, config in self.subscriptions.items():
                await self.subscribe(sub_id, config)
    
    async def wait_for_connection(self, timeout: int = 30) -> bool:
        """等待连接建立"""
        start_time = time.time()
        while self.state in [ConnectionState.CONNECTING, ConnectionState.RECONNECTING]:
            if time.time() - start_time > timeout:
                return False
            await asyncio.sleep(0.1)
        return self.state == ConnectionState.CONNECTED


class WebSocketClientManager:
    """客户端管理器"""
    
    def __init__(self):
        self.clients: Dict[str, WebSocketClient] = {}
    
    def create_client(self, client_id: str, config: ConnectionConfig) -> WebSocketClient:
        """创建客户端"""
        if client_id in self.clients:
            raise ValueError(f"客户端已存在: {client_id}")
        
        client = WebSocketClient(config)
        self.clients[client_id] = client
        return client
    
    async def remove_client(self, client_id: str):
        """移除客户端"""
        if client_id in self.clients:
            await self.clients[client_id].disconnect()
            del self.clients[client_id]
    
    def get_client(self, client_id: str) -> Optional[WebSocketClient]:
        """获取客户端"""
        return self.clients.get(client_id)
    
    async def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有客户端统计"""
        stats = {}
        for client_id, client in self.clients.items():
            stats[client_id] = await client.get_stats()
        return stats
    
    async def close_all(self):
        """关闭所有客户端"""
        tasks = []
        for client in self.clients.values():
            tasks.append(client.disconnect())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.clients.clear()


class QuickStartClient:
    """快速开始客户端"""
    
    @staticmethod
    async def create(url: str, api_key: str = None) -> WebSocketClient:
        """创建快速开始客户端"""
        config = ConnectionConfig(
            url=url,
            api_key=api_key,
            max_reconnect_attempts=3,
            reconnect_delay=1.0
        )
        
        client = WebSocketClient(config)
        return client
    
    @staticmethod
    async def subscribe_stocks(client: WebSocketClient, symbols: List[str], 
                             handler: Callable) -> str:
        """订阅股票数据"""
        subscription_id = f"stocks_{int(time.time())}"
        config = SubscriptionConfig(
            symbols=symbols,
            data_types=["price", "volume"],
            update_frequency="realtime"
        )
        
        client.add_message_handler("price", handler)
        client.add_message_handler("volume", handler)
        
        await client.subscribe(subscription_id, config)
        return subscription_id