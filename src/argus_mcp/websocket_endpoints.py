"""
WebSocket端点
支持实时市场数据推送和双向通信
"""

import json
import logging
import asyncio
from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.routing import APIRouter
import uuid

from .enhanced_market_data import enhanced_market_data_service
from .auth_middleware import verify_websocket_token

logger = logging.getLogger(__name__)

router = APIRouter()

class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_subscriptions: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        """建立WebSocket连接"""
        await websocket.accept()
        
        if not client_id:
            client_id = str(uuid.uuid4())
        
        self.active_connections[client_id] = websocket
        self.client_subscriptions[client_id] = {}
        
        logger.info(f"WebSocket client {client_id} connected")
        return client_id
    
    async def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            # 取消所有订阅
            await enhanced_market_data_service.unsubscribe_real_time_data(client_id)
            
            # 移除连接
            del self.active_connections[client_id]
            if client_id in self.client_subscriptions:
                del self.client_subscriptions[client_id]
            
            logger.info(f"WebSocket client {client_id} disconnected")
    
    async def send_message(self, client_id: str, message: dict):
        """发送消息给指定客户端"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                await self.disconnect(client_id)
    
    async def broadcast(self, message: dict):
        """广播消息给所有客户端"""
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to broadcast to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected_clients:
            await self.disconnect(client_id)

# 全局WebSocket管理器
websocket_manager = WebSocketManager()

@router.websocket("/ws/market_data")
async def websocket_market_data_endpoint(websocket: WebSocket):
    """市场数据WebSocket端点"""
    client_id = None
    
    try:
        # 建立连接
        client_id = await websocket_manager.connect(websocket)
        
        # 发送欢迎消息
        welcome_message = {
            "type": "connection_established",
            "client_id": client_id,
            "message": "Connected to market data stream",
            "available_commands": [
                "subscribe",
                "unsubscribe", 
                "get_stats",
                "ping"
            ]
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # 消息处理循环
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 处理不同类型的消息
                await handle_websocket_message(client_id, message, websocket)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket client {client_id} disconnected")
                break
            except json.JSONDecodeError:
                error_message = {
                    "type": "error",
                    "message": "Invalid JSON format"
                }
                await websocket.send_text(json.dumps(error_message))
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                error_message = {
                    "type": "error", 
                    "message": f"Internal error: {str(e)}"
                }
                await websocket.send_text(json.dumps(error_message))
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    
    finally:
        if client_id:
            await websocket_manager.disconnect(client_id)

async def handle_websocket_message(client_id: str, message: dict, websocket: WebSocket):
    """处理WebSocket消息"""
    message_type = message.get("type")
    
    if message_type == "subscribe":
        await handle_subscribe_message(client_id, message, websocket)
    
    elif message_type == "unsubscribe":
        await handle_unsubscribe_message(client_id, message, websocket)
    
    elif message_type == "get_stats":
        await handle_get_stats_message(client_id, websocket)
    
    elif message_type == "ping":
        await handle_ping_message(client_id, websocket)
    
    elif message_type == "get_batch_data":
        await handle_batch_data_message(client_id, message, websocket)
    
    elif message_type == "get_streaming_data":
        await handle_streaming_data_message(client_id, message, websocket)
    
    else:
        error_message = {
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        }
        await websocket.send_text(json.dumps(error_message))

async def handle_subscribe_message(client_id: str, message: dict, websocket: WebSocket):
    """处理订阅消息"""
    try:
        symbols = message.get("symbols", [])
        fields = message.get("fields", ["open", "high", "low", "close", "volume"])
        frequency = message.get("frequency", 1000)  # 默认1秒
        
        if not symbols:
            error_message = {
                "type": "error",
                "message": "Symbols list is required"
            }
            await websocket.send_text(json.dumps(error_message))
            return
        
        # 订阅实时数据
        success = await enhanced_market_data_service.subscribe_real_time_data(
            client_id=client_id,
            symbols=symbols,
            fields=fields,
            frequency=frequency,
            websocket=websocket
        )
        
        if success:
            response_message = {
                "type": "subscription_confirmed",
                "symbols": symbols,
                "fields": fields,
                "frequency": frequency,
                "message": f"Subscribed to {len(symbols)} symbols"
            }
        else:
            response_message = {
                "type": "error",
                "message": "Failed to subscribe to market data"
            }
        
        await websocket.send_text(json.dumps(response_message))
        
    except Exception as e:
        logger.error(f"Error handling subscribe message: {e}")
        error_message = {
            "type": "error",
            "message": f"Subscription error: {str(e)}"
        }
        await websocket.send_text(json.dumps(error_message))

async def handle_unsubscribe_message(client_id: str, message: dict, websocket: WebSocket):
    """处理取消订阅消息"""
    try:
        success = await enhanced_market_data_service.unsubscribe_real_time_data(client_id)
        
        if success:
            response_message = {
                "type": "unsubscription_confirmed",
                "message": "Successfully unsubscribed from market data"
            }
        else:
            response_message = {
                "type": "error",
                "message": "No active subscription found"
            }
        
        await websocket.send_text(json.dumps(response_message))
        
    except Exception as e:
        logger.error(f"Error handling unsubscribe message: {e}")
        error_message = {
            "type": "error",
            "message": f"Unsubscription error: {str(e)}"
        }
        await websocket.send_text(json.dumps(error_message))

async def handle_get_stats_message(client_id: str, websocket: WebSocket):
    """处理获取统计信息消息"""
    try:
        stats = enhanced_market_data_service.get_service_stats()
        
        response_message = {
            "type": "stats_response",
            "data": stats
        }
        
        await websocket.send_text(json.dumps(response_message))
        
    except Exception as e:
        logger.error(f"Error handling get stats message: {e}")
        error_message = {
            "type": "error",
            "message": f"Stats error: {str(e)}"
        }
        await websocket.send_text(json.dumps(error_message))

async def handle_ping_message(client_id: str, websocket: WebSocket):
    """处理ping消息"""
    try:
        response_message = {
            "type": "pong",
            "timestamp": asyncio.get_event_loop().time(),
            "client_id": client_id
        }
        
        await websocket.send_text(json.dumps(response_message))
        
    except Exception as e:
        logger.error(f"Error handling ping message: {e}")

async def handle_batch_data_message(client_id: str, message: dict, websocket: WebSocket):
    """处理批量数据请求消息"""
    try:
        symbols = message.get("symbols", [])
        fields = message.get("fields", ["open", "high", "low", "close", "volume"])
        batch_size = message.get("batch_size", 100)
        
        if not symbols:
            error_message = {
                "type": "error",
                "message": "Symbols list is required"
            }
            await websocket.send_text(json.dumps(error_message))
            return
        
        # 获取批量数据
        batch_data = await enhanced_market_data_service.get_batch_market_data(
            symbols=symbols,
            fields=fields,
            batch_size=batch_size
        )
        
        response_message = {
            "type": "batch_data_response",
            "data": batch_data,
            "symbols_count": len(symbols),
            "results_count": len(batch_data)
        }
        
        await websocket.send_text(json.dumps(response_message))
        
    except Exception as e:
        logger.error(f"Error handling batch data message: {e}")
        error_message = {
            "type": "error",
            "message": f"Batch data error: {str(e)}"
        }
        await websocket.send_text(json.dumps(error_message))

async def handle_streaming_data_message(client_id: str, message: dict, websocket: WebSocket):
    """处理流式数据请求消息"""
    try:
        symbols = message.get("symbols", [])
        start_time = message.get("start_time")
        end_time = message.get("end_time")
        limit = message.get("limit", 1000)
        
        if not symbols:
            error_message = {
                "type": "error",
                "message": "Symbols list is required"
            }
            await websocket.send_text(json.dumps(error_message))
            return
        
        # 获取流式数据
        streaming_data = await enhanced_market_data_service.get_streaming_data(
            symbols=symbols,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # 转换为可序列化的格式
        serializable_data = []
        for data in streaming_data:
            serializable_data.append({
                "symbol": data.symbol,
                "timestamp": data.timestamp,
                "data": data.data,
                "sequence": data.sequence
            })
        
        response_message = {
            "type": "streaming_data_response",
            "data": serializable_data,
            "symbols_count": len(symbols),
            "results_count": len(serializable_data)
        }
        
        await websocket.send_text(json.dumps(response_message))
        
    except Exception as e:
        logger.error(f"Error handling streaming data message: {e}")
        error_message = {
            "type": "error",
            "message": f"Streaming data error: {str(e)}"
        }
        await websocket.send_text(json.dumps(error_message))

# 导出WebSocket管理器和路由
__all__ = ["router", "websocket_manager"]