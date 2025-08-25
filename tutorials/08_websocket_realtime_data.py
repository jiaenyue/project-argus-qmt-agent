#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebSocket 实时数据订阅教程

本教程演示如何使用 WebSocket 接口订阅和接收实时行情数据，
包括连接管理、订阅管理、数据处理和错误处理等核心功能。

学习目标：
1. 理解 WebSocket 实时数据推送的基本概念
2. 掌握 WebSocket 连接建立和管理
3. 学会订阅和取消订阅实时数据
4. 了解实时数据的处理和展示方法
5. 掌握 WebSocket 错误处理和重连机制

前置条件：
- 已完成基础教程（01-07）的学习
- WebSocket 服务已启动（端口 8765）
- 了解异步编程基础概念

作者: Argus 开发团队
创建时间: 2025-01-15
最后更新: 2025-01-15
"""

import asyncio
import json
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketRealtimeClient:
    """WebSocket 实时数据客户端
    
    提供完整的 WebSocket 实时数据订阅功能，包括：
    - 连接管理和自动重连
    - 订阅管理和数据接收
    - 心跳检测和状态监控
    - 错误处理和恢复机制
    """
    
    def __init__(self, uri: str = "ws://localhost:8765", client_id: str = None):
        """初始化客户端
        
        Args:
            uri: WebSocket 服务器地址
            client_id: 客户端标识符
        """
        self.uri = uri
        self.client_id = client_id or f"tutorial_client_{int(time.time())}"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        
        # 连接状态
        self.is_connected = False
        self.is_running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
        # 订阅管理
        self.subscriptions: Dict[str, Dict[str, Any]] = {}
        self.subscription_responses: Dict[str, Dict[str, Any]] = {}
        
        # 数据统计
        self.message_count = 0
        self.data_received = 0
        self.last_heartbeat = None
        self.connection_start_time = None
        
        # 异步任务
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.receive_task: Optional[asyncio.Task] = None
        
        # 回调函数
        self.on_market_data = None
        self.on_kline_data = None
        self.on_connection_status = None
        self.on_error = None
    
    async def connect(self) -> bool:
        """连接到 WebSocket 服务器
        
        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info(f"客户端 {self.client_id} 正在连接到 {self.uri}")
            
            # 建立 WebSocket 连接
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_connected = True
            self.is_running = True
            self.connection_start_time = datetime.now()
            self.reconnect_attempts = 0
            
            logger.info(f"客户端 {self.client_id} 连接成功")
            
            # 启动心跳任务
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # 启动消息接收任务
            self.receive_task = asyncio.create_task(self._receive_loop())
            
            # 触发连接状态回调
            if self.on_connection_status:
                await self.on_connection_status("connected", {
                    "client_id": self.client_id,
                    "server_uri": self.uri,
                    "connection_time": self.connection_start_time.isoformat()
                })
            
            return True
            
        except Exception as e:
            logger.error(f"客户端 {self.client_id} 连接失败: {e}")
            self.is_connected = False
            
            # 触发错误回调
            if self.on_error:
                await self.on_error("connection_failed", str(e))
            
            return False
    
    async def disconnect(self):
        """断开连接"""
        logger.info(f"客户端 {self.client_id} 正在断开连接")
        
        self.is_running = False
        self.is_connected = False
        
        # 取消异步任务
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass
        
        # 关闭 WebSocket 连接
        if self.websocket:
            await self.websocket.close()
        
        # 触发连接状态回调
        if self.on_connection_status:
            await self.on_connection_status("disconnected", {
                "client_id": self.client_id,
                "disconnect_time": datetime.now().isoformat()
            })
        
        logger.info(f"客户端 {self.client_id} 已断开连接")
    
    async def subscribe(self, symbol: str, data_type: str = "quote", frequency: str = None) -> bool:
        """订阅实时数据
        
        Args:
            symbol: 股票代码（如 "000001.SZ"）
            data_type: 数据类型（quote/kline/trade/depth）
            frequency: K线周期（仅对 kline 类型有效）
            
        Returns:
            bool: 订阅是否成功
        """
        if not self.is_connected:
            logger.error("未连接到服务器，无法订阅")
            return False
        
        try:
            # 构建订阅请求
            subscription_request = {
                "type": "subscribe",
                "data": {
                    "symbol": symbol,
                    "data_type": data_type,
                    "client_id": self.client_id
                }
            }
            
            # 添加频率参数（如果适用）
            if frequency and data_type == "kline":
                subscription_request["data"]["frequency"] = frequency
            
            # 发送订阅请求
            await self.websocket.send(json.dumps(subscription_request))
            
            # 记录订阅信息
            subscription_key = f"{symbol}_{data_type}_{frequency or 'default'}"
            self.subscriptions[subscription_key] = {
                "symbol": symbol,
                "data_type": data_type,
                "frequency": frequency,
                "subscribed_at": datetime.now().isoformat(),
                "status": "pending"
            }
            
            logger.info(f"已发送订阅请求: {symbol} ({data_type})")
            return True
            
        except Exception as e:
            logger.error(f"订阅失败: {e}")
            if self.on_error:
                await self.on_error("subscription_failed", str(e))
            return False
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅
        
        Args:
            subscription_id: 订阅ID
            
        Returns:
            bool: 取消订阅是否成功
        """
        if not self.is_connected:
            logger.error("未连接到服务器，无法取消订阅")
            return False
        
        try:
            # 构建取消订阅请求
            unsubscribe_request = {
                "type": "unsubscribe",
                "data": {
                    "subscription_id": subscription_id
                }
            }
            
            # 发送取消订阅请求
            await self.websocket.send(json.dumps(unsubscribe_request))
            
            logger.info(f"已发送取消订阅请求: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            if self.on_error:
                await self.on_error("unsubscription_failed", str(e))
            return False
    
    async def get_subscriptions(self) -> Dict[str, Any]:
        """获取当前订阅列表
        
        Returns:
            Dict: 订阅信息
        """
        if not self.is_connected:
            return {"error": "未连接到服务器"}
        
        try:
            # 构建获取订阅请求
            request = {
                "type": "get_subscriptions",
                "data": {}
            }
            
            # 发送请求
            await self.websocket.send(json.dumps(request))
            
            logger.info("已发送获取订阅列表请求")
            return {"status": "requested"}
            
        except Exception as e:
            logger.error(f"获取订阅列表失败: {e}")
            return {"error": str(e)}
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取服务器统计信息
        
        Returns:
            Dict: 统计信息
        """
        if not self.is_connected:
            return {"error": "未连接到服务器"}
        
        try:
            # 构建获取统计请求
            request = {
                "type": "get_stats",
                "data": {}
            }
            
            # 发送请求
            await self.websocket.send(json.dumps(request))
            
            logger.info("已发送获取统计信息请求")
            return {"status": "requested"}
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}
    
    async def _receive_loop(self):
        """消息接收循环"""
        try:
            while self.is_running and self.websocket:
                try:
                    # 接收消息
                    message_str = await asyncio.wait_for(
                        self.websocket.recv(), timeout=1.0
                    )
                    
                    # 解析消息
                    message = json.loads(message_str)
                    
                    # 处理消息
                    await self._handle_message(message)
                    
                    # 更新统计
                    self.message_count += 1
                    
                except asyncio.TimeoutError:
                    continue
                except ConnectionClosed:
                    logger.warning(f"客户端 {self.client_id} 连接被服务器关闭")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"消息解析失败: {e}")
                    continue
                except Exception as e:
                    logger.error(f"接收消息时出错: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"消息接收循环出错: {e}")
        finally:
            self.is_connected = False
            
            # 尝试重连
            if self.is_running:
                await self._attempt_reconnect()
    
    async def _handle_message(self, message: Dict[str, Any]):
        """处理接收到的消息
        
        Args:
            message: 消息内容
        """
        message_type = message.get("type", "unknown")
        data = message.get("data", {})
        timestamp = message.get("timestamp", datetime.now().isoformat())
        
        logger.debug(f"收到消息: {message_type}")
        
        if message_type == "welcome":
            # 欢迎消息
            logger.info(f"收到服务器欢迎消息: {data}")
            
        elif message_type == "subscription_response":
            # 订阅响应
            await self._handle_subscription_response(data)
            
        elif message_type == "market_data":
            # 实时行情数据
            await self._handle_market_data(data, timestamp)
            
        elif message_type == "kline_data":
            # K线数据
            await self._handle_kline_data(data, timestamp)
            
        elif message_type == "trade_data":
            # 成交明细数据
            await self._handle_trade_data(data, timestamp)
            
        elif message_type == "depth_data":
            # 深度行情数据
            await self._handle_depth_data(data, timestamp)
            
        elif message_type == "subscription_list":
            # 订阅列表响应
            logger.info(f"当前订阅列表: {data}")
            
        elif message_type == "stats":
            # 统计信息响应
            logger.info(f"服务器统计信息: {data}")
            
        elif message_type == "heartbeat":
            # 心跳响应
            await self._handle_heartbeat_response(data)
            
        elif message_type == "error":
            # 错误消息
            await self._handle_error_message(data)
            
        else:
            logger.debug(f"未知消息类型: {message_type}")
    
    async def _handle_subscription_response(self, data: Dict[str, Any]):
        """处理订阅响应
        
        Args:
            data: 响应数据
        """
        subscription_id = data.get("subscription_id")
        status = data.get("status")
        symbol = data.get("symbol")
        data_type = data.get("data_type")
        message = data.get("message", "")
        
        logger.info(f"订阅响应: {symbol} ({data_type}) - {status} - {message}")
        
        # 更新订阅状态
        subscription_key = f"{symbol}_{data_type}_default"
        if subscription_key in self.subscriptions:
            self.subscriptions[subscription_key]["status"] = status
            self.subscriptions[subscription_key]["subscription_id"] = subscription_id
        
        # 记录订阅响应
        if subscription_id:
            self.subscription_responses[subscription_id] = data
    
    async def _handle_market_data(self, data: Dict[str, Any], timestamp: str):
        """处理实时行情数据
        
        Args:
            data: 行情数据
            timestamp: 时间戳
        """
        symbol = data.get("symbol", "")
        last_price = data.get("last_price", 0)
        change = data.get("change", 0)
        change_percent = data.get("change_percent", 0)
        volume = data.get("volume", 0)
        
        logger.info(f"📈 {symbol}: ¥{last_price} ({change:+.4f}, {change_percent:+.2f}%) 成交量: {volume}")
        
        # 更新数据统计
        self.data_received += 1
        
        # 触发回调
        if self.on_market_data:
            await self.on_market_data(data, timestamp)
    
    async def _handle_kline_data(self, data: Dict[str, Any], timestamp: str):
        """处理K线数据
        
        Args:
            data: K线数据
            timestamp: 时间戳
        """
        symbol = data.get("symbol", "")
        period = data.get("period", "")
        open_price = data.get("open", 0)
        high_price = data.get("high", 0)
        low_price = data.get("low", 0)
        close_price = data.get("close", 0)
        volume = data.get("volume", 0)
        
        logger.info(f"📊 {symbol} ({period}): O:{open_price} H:{high_price} L:{low_price} C:{close_price} V:{volume}")
        
        # 更新数据统计
        self.data_received += 1
        
        # 触发回调
        if self.on_kline_data:
            await self.on_kline_data(data, timestamp)
    
    async def _handle_trade_data(self, data: Dict[str, Any], timestamp: str):
        """处理成交明细数据
        
        Args:
            data: 成交数据
            timestamp: 时间戳
        """
        symbol = data.get("symbol", "")
        price = data.get("price", 0)
        volume = data.get("volume", 0)
        direction = data.get("direction", "")
        
        direction_emoji = "🔴" if direction == "sell" else "🟢" if direction == "buy" else "⚪"
        logger.info(f"💰 {symbol}: {direction_emoji} ¥{price} × {volume}")
        
        # 更新数据统计
        self.data_received += 1
    
    async def _handle_depth_data(self, data: Dict[str, Any], timestamp: str):
        """处理深度行情数据
        
        Args:
            data: 深度数据
            timestamp: 时间戳
        """
        symbol = data.get("symbol", "")
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        
        logger.info(f"📋 {symbol} 深度: 买盘{len(bids)}档 卖盘{len(asks)}档")
        
        # 显示前3档买卖盘
        if bids:
            logger.info(f"   买盘: {bids[:3]}")
        if asks:
            logger.info(f"   卖盘: {asks[:3]}")
        
        # 更新数据统计
        self.data_received += 1
    
    async def _handle_heartbeat_response(self, data: Dict[str, Any]):
        """处理心跳响应
        
        Args:
            data: 心跳数据
        """
        server_time = data.get("server_time")
        client_time = data.get("client_time")
        
        self.last_heartbeat = datetime.now()
        
        # 计算延迟
        if server_time:
            try:
                server_dt = datetime.fromisoformat(server_time.replace('Z', '+00:00'))
                latency = (datetime.now() - server_dt).total_seconds() * 1000
                logger.debug(f"心跳延迟: {latency:.2f}ms")
            except:
                pass
    
    async def _handle_error_message(self, data: Dict[str, Any]):
        """处理错误消息
        
        Args:
            data: 错误数据
        """
        error = data.get("error", "未知错误")
        client_id = data.get("client_id", "")
        
        logger.error(f"服务器错误: {error}")
        
        # 触发错误回调
        if self.on_error:
            await self.on_error("server_error", error)
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        try:
            while self.is_running and self.is_connected:
                await asyncio.sleep(25)  # 每25秒发送一次心跳
                
                if self.is_running and self.is_connected:
                    try:
                        heartbeat_msg = {
                            "type": "heartbeat",
                            "data": {
                                "client_time": datetime.now().isoformat(),
                                "client_id": self.client_id
                            }
                        }
                        
                        await self.websocket.send(json.dumps(heartbeat_msg))
                        logger.debug("发送心跳")
                        
                    except Exception as e:
                        logger.error(f"发送心跳失败: {e}")
                        break
                        
        except asyncio.CancelledError:
            logger.debug("心跳循环被取消")
        except Exception as e:
            logger.error(f"心跳循环出错: {e}")
    
    async def _attempt_reconnect(self):
        """尝试重连"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"重连次数已达上限 ({self.max_reconnect_attempts})，停止重连")
            return
        
        self.reconnect_attempts += 1
        wait_time = min(2 ** self.reconnect_attempts, 30)  # 指数退避，最大30秒
        
        logger.info(f"第 {self.reconnect_attempts} 次重连尝试，等待 {wait_time} 秒...")
        await asyncio.sleep(wait_time)
        
        if await self.connect():
            logger.info("重连成功")
            
            # 重新订阅之前的数据
            await self._resubscribe()
        else:
            logger.error("重连失败")
            await self._attempt_reconnect()
    
    async def _resubscribe(self):
        """重新订阅之前的数据"""
        logger.info("重新订阅之前的数据...")
        
        for subscription_key, subscription_info in self.subscriptions.items():
            if subscription_info["status"] == "active":
                await self.subscribe(
                    subscription_info["symbol"],
                    subscription_info["data_type"],
                    subscription_info.get("frequency")
                )
                
                # 等待一小段时间避免请求过快
                await asyncio.sleep(0.1)
    
    def get_client_stats(self) -> Dict[str, Any]:
        """获取客户端统计信息
        
        Returns:
            Dict: 统计信息
        """
        uptime = None
        if self.connection_start_time:
            uptime = str(datetime.now() - self.connection_start_time)
        
        return {
            "client_id": self.client_id,
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "connection_start_time": self.connection_start_time.isoformat() if self.connection_start_time else None,
            "uptime": uptime,
            "message_count": self.message_count,
            "data_received": self.data_received,
            "subscriptions_count": len(self.subscriptions),
            "active_subscriptions": len([s for s in self.subscriptions.values() if s["status"] == "active"]),
            "reconnect_attempts": self.reconnect_attempts,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None
        }


async def demo_basic_subscription():
    """演示基本订阅功能"""
    print("\n" + "="*60)
    print("🚀 WebSocket 基本订阅演示")
    print("="*60)
    
    # 创建客户端
    client = WebSocketRealtimeClient(
        uri="ws://localhost:8765",
        client_id="demo_basic_client"
    )
    
    # 设置回调函数
    async def on_market_data(data, timestamp):
        symbol = data.get("symbol", "")
        price = data.get("last_price", 0)
        change_pct = data.get("change_percent", 0)
        print(f"📈 实时行情: {symbol} = ¥{price} ({change_pct:+.2f}%)")
    
    async def on_connection_status(status, info):
        print(f"🔗 连接状态: {status}")
        if status == "connected":
            print(f"   客户端ID: {info['client_id']}")
            print(f"   连接时间: {info['connection_time']}")
    
    async def on_error(error_type, error_message):
        print(f"❌ 错误: {error_type} - {error_message}")
    
    client.on_market_data = on_market_data
    client.on_connection_status = on_connection_status
    client.on_error = on_error
    
    try:
        # 连接到服务器
        if await client.connect():
            print("✅ 连接成功")
            
            # 等待欢迎消息
            await asyncio.sleep(2)
            
            # 订阅实时行情
            print("\n📡 订阅实时行情数据...")
            await client.subscribe("000001.SZ", "quote")
            await client.subscribe("600519.SH", "quote")
            
            # 运行30秒
            print("⏰ 运行30秒，观察实时数据...")
            await asyncio.sleep(30)
            
            # 获取订阅列表
            print("\n📋 获取订阅列表...")
            await client.get_subscriptions()
            await asyncio.sleep(2)
            
            # 获取统计信息
            print("\n📊 获取统计信息...")
            await client.get_stats()
            await asyncio.sleep(2)
            
            # 显示客户端统计
            stats = client.get_client_stats()
            print(f"\n📈 客户端统计:")
            print(f"   连接时长: {stats['uptime']}")
            print(f"   接收消息: {stats['message_count']}")
            print(f"   接收数据: {stats['data_received']}")
            print(f"   订阅数量: {stats['subscriptions_count']}")
            
        else:
            print("❌ 连接失败")
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
    finally:
        # 断开连接
        await client.disconnect()
        print("👋 演示结束")


async def demo_multiple_data_types():
    """演示多种数据类型订阅"""
    print("\n" + "="*60)
    print("🎯 WebSocket 多数据类型订阅演示")
    print("="*60)
    
    # 创建客户端
    client = WebSocketRealtimeClient(
        uri="ws://localhost:8765",
        client_id="demo_multi_client"
    )
    
    # 设置回调函数
    async def on_market_data(data, timestamp):
        symbol = data.get("symbol", "")
        price = data.get("last_price", 0)
        volume = data.get("volume", 0)
        print(f"📈 行情: {symbol} = ¥{price} 成交量: {volume}")
    
    async def on_kline_data(data, timestamp):
        symbol = data.get("symbol", "")
        period = data.get("period", "")
        close = data.get("close", 0)
        volume = data.get("volume", 0)
        print(f"📊 K线: {symbol} ({period}) 收盘: ¥{close} 成交量: {volume}")
    
    client.on_market_data = on_market_data
    client.on_kline_data = on_kline_data
    
    try:
        # 连接到服务器
        if await client.connect():
            print("✅ 连接成功")
            await asyncio.sleep(2)
            
            # 订阅不同类型的数据
            print("\n📡 订阅多种数据类型...")
            
            # 实时行情
            await client.subscribe("000001.SZ", "quote")
            await asyncio.sleep(0.5)
            
            # K线数据
            await client.subscribe("000001.SZ", "kline", "1m")
            await asyncio.sleep(0.5)
            
            # 成交明细（如果支持）
            await client.subscribe("000001.SZ", "trade")
            await asyncio.sleep(0.5)
            
            # 深度行情（如果支持）
            await client.subscribe("000001.SZ", "depth")
            await asyncio.sleep(0.5)
            
            # 运行60秒观察数据
            print("⏰ 运行60秒，观察不同类型的实时数据...")
            await asyncio.sleep(60)
            
        else:
            print("❌ 连接失败")
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
    finally:
        await client.disconnect()
        print("👋 演示结束")


async def demo_reconnection():
    """演示重连机制"""
    print("\n" + "="*60)
    print("🔄 WebSocket 重连机制演示")
    print("="*60)
    
    # 创建客户端
    client = WebSocketRealtimeClient(
        uri="ws://localhost:8765",
        client_id="demo_reconnect_client"
    )
    
    # 设置回调函数
    async def on_connection_status(status, info):
        if status == "connected":
            print(f"🟢 已连接 - {info.get('client_id', '')}")
        elif status == "disconnected":
            print(f"🔴 已断开 - {info.get('disconnect_time', '')}")
    
    async def on_market_data(data, timestamp):
        symbol = data.get("symbol", "")
        price = data.get("last_price", 0)
        print(f"📈 {symbol}: ¥{price}")
    
    client.on_connection_status = on_connection_status
    client.on_market_data = on_market_data
    
    try:
        # 连接到服务器
        if await client.connect():
            print("✅ 初始连接成功")
            await asyncio.sleep(2)
            
            # 订阅数据
            await client.subscribe("000001.SZ", "quote")
            print("📡 已订阅数据")
            
            # 运行一段时间
            print("⏰ 运行20秒...")
            await asyncio.sleep(20)
            
            # 模拟连接断开（这里只是演示，实际中可能是网络问题）
            print("\n🔌 模拟连接断开...")
            await client.disconnect()
            
            # 等待一段时间
            await asyncio.sleep(5)
            
            # 重新连接
            print("🔄 尝试重新连接...")
            if await client.connect():
                print("✅ 重连成功")
                
                # 重新订阅
                await client.subscribe("000001.SZ", "quote")
                print("📡 重新订阅数据")
                
                # 继续运行
                print("⏰ 继续运行20秒...")
                await asyncio.sleep(20)
            
        else:
            print("❌ 连接失败")
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
    finally:
        await client.disconnect()
        print("👋 演示结束")


async def main():
    """主函数 - 运行所有演示"""
    print("🎓 WebSocket 实时数据订阅教程")
    print("本教程将演示 WebSocket 实时数据订阅的各种功能")
    print("\n请确保 WebSocket 服务已启动（端口 8765）")
    
    # 检查服务器连接
    try:
        test_client = WebSocketRealtimeClient()
        if not await test_client.connect():
            print("❌ 无法连接到 WebSocket 服务器")
            print("请确保服务器已启动：python -m src.argus_mcp.websocket_server")
            return
        await test_client.disconnect()
        print("✅ WebSocket 服务器连接正常")
    except Exception as e:
        print(f"❌ 服务器连接检查失败: {e}")
        return
    
    try:
        # 运行演示
        await demo_basic_subscription()
        
        print("\n" + "="*60)
        input("按 Enter 键继续下一个演示...")
        
        await demo_multiple_data_types()
        
        print("\n" + "="*60)
        input("按 Enter 键继续下一个演示...")
        
        await demo_reconnection()
        
    except KeyboardInterrupt:
        print("\n⏹️ 教程被用户中断")
    except Exception as e:
        print(f"❌ 教程运行出错: {e}")
    
    print("\n🎉 WebSocket 实时数据订阅教程完成！")
    print("\n📚 学习要点总结：")
    print("1. WebSocket 连接建立和管理")
    print("2. 实时数据订阅和取消订阅")
    print("3. 多种数据类型的处理")
    print("4. 心跳检测和连接状态监控")
    print("5. 自动重连和错误处理机制")
    print("\n💡 下一步建议：")
    print("- 学习 WebSocket 与 REST API 的结合使用")
    print("- 探索 WebSocket 性能优化技巧")
    print("- 了解 WebSocket 在生产环境中的部署")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 教程结束")
    except Exception as e:
        logger.error(f"教程运行失败: {e}")
        sys.exit(1)