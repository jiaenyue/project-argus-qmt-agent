#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebSocket 与 REST API 集成教程

本教程演示如何将 WebSocket 实时数据推送与 REST API 历史数据查询相结合，
构建完整的金融数据应用，包括数据一致性验证、缓存策略和性能优化。

学习目标：
1. 理解 WebSocket 与 REST API 的互补关系
2. 掌握实时数据与历史数据的结合使用
3. 学会数据一致性验证和缓存策略
4. 了解混合数据源的性能优化方法
5. 构建完整的实时监控应用

前置条件：
- 已完成 WebSocket 基础教程（08）
- 已完成 REST API 教程（01-07）
- REST API 服务已启动（端口 8000）
- WebSocket 服务已启动（端口 8765）

作者: Argus 开发团队
创建时间: 2025-01-15
最后更新: 2025-01-15
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
import websockets
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

# 导入之前的 WebSocket 客户端
from tutorials.common.api_client import create_api_client
from tutorials.common.utils import print_section_header, format_number

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegratedDataClient:
    """集成数据客户端
    
    结合 WebSocket 实时数据和 REST API 历史数据，
    提供统一的数据访问接口和缓存管理。
    """
    
    def __init__(self, 
                 rest_api_url: str = "http://localhost:8000",
                 websocket_url: str = "ws://localhost:8765",
                 client_id: str = None):
        """初始化集成客户端
        
        Args:
            rest_api_url: REST API 服务地址
            websocket_url: WebSocket 服务地址
            client_id: 客户端标识符
        """
        self.rest_api_url = rest_api_url
        self.websocket_url = websocket_url
        self.client_id = client_id or f"integrated_client_{int(time.time())}"
        
        # REST API 客户端
        self.api_client = create_api_client(base_url=rest_api_url)
        
        # WebSocket 连接
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_running = False
        
        # 数据缓存
        self.realtime_cache: Dict[str, Dict[str, Any]] = {}
        self.historical_cache: Dict[str, pd.DataFrame] = {}
        self.subscription_cache: Dict[str, Dict[str, Any]] = {}
        
        # 数据统计
        self.stats = {
            "rest_api_calls": 0,
            "websocket_messages": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "data_consistency_checks": 0,
            "consistency_errors": 0
        }
        
        # 回调函数
        self.on_realtime_data = None
        self.on_data_update = None
        self.on_consistency_error = None
    
    async def connect(self) -> bool:
        """连接到 WebSocket 服务
        
        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info(f"连接到 WebSocket 服务: {self.websocket_url}")
            
            self.websocket = await websockets.connect(
                self.websocket_url,
                ping_interval=20,
                ping_timeout=10
            )
            
            self.is_connected = True
            self.is_running = True
            
            # 启动消息接收任务
            asyncio.create_task(self._receive_loop())
            
            logger.info("WebSocket 连接成功")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开 WebSocket 连接"""
        self.is_running = False
        self.is_connected = False
        
        if self.websocket:
            await self.websocket.close()
        
        logger.info("WebSocket 连接已断开")
    
    def get_historical_data(self, symbol: str, start_date: str, end_date: str, 
                          use_cache: bool = True) -> Optional[pd.DataFrame]:
        """获取历史数据（REST API）
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用缓存
            
        Returns:
            DataFrame: 历史数据
        """
        cache_key = f"{symbol}_{start_date}_{end_date}"
        
        # 检查缓存
        if use_cache and cache_key in self.historical_cache:
            self.stats["cache_hits"] += 1
            logger.debug(f"从缓存获取历史数据: {symbol}")
            return self.historical_cache[cache_key]
        
        try:
            # 调用 REST API
            logger.info(f"从 REST API 获取历史数据: {symbol} ({start_date} - {end_date})")
            
            result = self.api_client.get_hist_kline(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            self.stats["rest_api_calls"] += 1
            self.stats["cache_misses"] += 1
            
            if result and "data" in result:
                # 转换为 DataFrame
                df = pd.DataFrame(result["data"])
                
                # 数据类型转换
                if not df.empty:
                    df["date"] = pd.to_datetime(df["date"])
                    numeric_columns = ["open", "high", "low", "close", "volume", "amount"]
                    for col in numeric_columns:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    
                    # 缓存数据
                    if use_cache:
                        self.historical_cache[cache_key] = df
                    
                    logger.info(f"获取到 {len(df)} 条历史数据")
                    return df
                else:
                    logger.warning(f"历史数据为空: {symbol}")
                    return pd.DataFrame()
            else:
                logger.error(f"获取历史数据失败: {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"获取历史数据出错: {e}")
            return None
    
    async def subscribe_realtime_data(self, symbol: str, data_type: str = "quote") -> bool:
        """订阅实时数据（WebSocket）
        
        Args:
            symbol: 股票代码
            data_type: 数据类型
            
        Returns:
            bool: 订阅是否成功
        """
        if not self.is_connected:
            logger.error("WebSocket 未连接，无法订阅")
            return False
        
        try:
            subscription_request = {
                "type": "subscribe",
                "data": {
                    "symbol": symbol,
                    "data_type": data_type,
                    "client_id": self.client_id
                }
            }
            
            await self.websocket.send(json.dumps(subscription_request))
            
            # 记录订阅信息
            subscription_key = f"{symbol}_{data_type}"
            self.subscription_cache[subscription_key] = {
                "symbol": symbol,
                "data_type": data_type,
                "subscribed_at": datetime.now(),
                "status": "pending"
            }
            
            logger.info(f"已订阅实时数据: {symbol} ({data_type})")
            return True
            
        except Exception as e:
            logger.error(f"订阅实时数据失败: {e}")
            return False
    
    def get_latest_price(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取最新价格（优先使用实时缓存，否则调用 REST API）
        
        Args:
            symbol: 股票代码
            use_cache: 是否使用缓存
            
        Returns:
            Dict: 最新价格信息
        """
        # 优先使用实时缓存
        if use_cache and symbol in self.realtime_cache:
            cache_data = self.realtime_cache[symbol]
            cache_time = cache_data.get("timestamp")
            
            # 检查缓存是否新鲜（5分钟内）
            if cache_time:
                try:
                    cache_dt = datetime.fromisoformat(cache_time)
                    if (datetime.now() - cache_dt).total_seconds() < 300:
                        self.stats["cache_hits"] += 1
                        logger.debug(f"从实时缓存获取价格: {symbol}")
                        return cache_data
                except:
                    pass
        
        # 调用 REST API 获取最新行情
        try:
            logger.info(f"从 REST API 获取最新价格: {symbol}")
            
            result = self.api_client.get_latest_market([symbol])
            self.stats["rest_api_calls"] += 1
            self.stats["cache_misses"] += 1
            
            if result and "data" in result and symbol in result["data"]:
                price_data = result["data"][symbol]
                price_data["timestamp"] = datetime.now().isoformat()
                
                # 更新缓存
                if use_cache:
                    self.realtime_cache[symbol] = price_data
                
                return price_data
            else:
                logger.error(f"获取最新价格失败: {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"获取最新价格出错: {e}")
            return None
    
    async def _receive_loop(self):
        """WebSocket 消息接收循环"""
        try:
            while self.is_running and self.websocket:
                try:
                    message_str = await asyncio.wait_for(
                        self.websocket.recv(), timeout=1.0
                    )
                    
                    message = json.loads(message_str)
                    await self._handle_websocket_message(message)
                    
                    self.stats["websocket_messages"] += 1
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"接收 WebSocket 消息出错: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket 接收循环出错: {e}")
        finally:
            self.is_connected = False
    
    async def _handle_websocket_message(self, message: Dict[str, Any]):
        """处理 WebSocket 消息
        
        Args:
            message: 消息内容
        """
        message_type = message.get("type", "unknown")
        data = message.get("data", {})
        timestamp = message.get("timestamp", datetime.now().isoformat())
        
        if message_type == "market_data":
            # 处理实时行情数据
            symbol = data.get("symbol", "")
            
            # 更新实时缓存
            self.realtime_cache[symbol] = {
                **data,
                "timestamp": timestamp,
                "source": "websocket"
            }
            
            # 触发回调
            if self.on_realtime_data:
                await self.on_realtime_data(symbol, data, timestamp)
            
            if self.on_data_update:
                await self.on_data_update("realtime", symbol, data)
            
        elif message_type == "subscription_response":
            # 更新订阅状态
            symbol = data.get("symbol", "")
            data_type = data.get("data_type", "")
            status = data.get("status", "")
            
            subscription_key = f"{symbol}_{data_type}"
            if subscription_key in self.subscription_cache:
                self.subscription_cache[subscription_key]["status"] = status
            
            logger.info(f"订阅状态更新: {symbol} ({data_type}) - {status}")
    
    async def verify_data_consistency(self, symbol: str) -> Dict[str, Any]:
        """验证实时数据与 REST API 数据的一致性
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 一致性检查结果
        """
        self.stats["data_consistency_checks"] += 1
        
        try:
            # 获取实时数据
            realtime_data = self.realtime_cache.get(symbol)
            
            # 获取 REST API 数据
            rest_data = self.get_latest_price(symbol, use_cache=False)
            
            if not realtime_data or not rest_data:
                return {
                    "symbol": symbol,
                    "consistent": False,
                    "error": "数据不完整",
                    "realtime_available": bool(realtime_data),
                    "rest_available": bool(rest_data)
                }
            
            # 比较价格数据
            realtime_price = float(realtime_data.get("last_price", 0))
            rest_price = float(rest_data.get("current_price", 0))
            
            # 计算价格差异（允许小幅差异）
            price_diff = abs(realtime_price - rest_price)
            price_diff_pct = (price_diff / rest_price * 100) if rest_price > 0 else 0
            
            # 判断是否一致（允许0.1%的差异）
            is_consistent = price_diff_pct <= 0.1
            
            if not is_consistent:
                self.stats["consistency_errors"] += 1
                
                if self.on_consistency_error:
                    await self.on_consistency_error(symbol, {
                        "realtime_price": realtime_price,
                        "rest_price": rest_price,
                        "difference": price_diff,
                        "difference_pct": price_diff_pct
                    })
            
            return {
                "symbol": symbol,
                "consistent": is_consistent,
                "realtime_price": realtime_price,
                "rest_price": rest_price,
                "difference": price_diff,
                "difference_pct": price_diff_pct,
                "realtime_timestamp": realtime_data.get("timestamp"),
                "rest_timestamp": rest_data.get("timestamp")
            }
            
        except Exception as e:
            logger.error(f"数据一致性检查出错: {e}")
            return {
                "symbol": symbol,
                "consistent": False,
                "error": str(e)
            }
    
    def get_combined_data(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """获取组合数据（历史数据 + 实时数据）
        
        Args:
            symbol: 股票代码
            days: 历史数据天数
            
        Returns:
            Dict: 组合数据
        """
        try:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 获取历史数据
            historical_df = self.get_historical_data(
                symbol,
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d")
            )
            
            # 获取实时数据
            realtime_data = self.realtime_cache.get(symbol)
            
            result = {
                "symbol": symbol,
                "historical_data": historical_df,
                "realtime_data": realtime_data,
                "data_points": len(historical_df) if historical_df is not None else 0,
                "has_realtime": bool(realtime_data),
                "last_update": datetime.now().isoformat()
            }
            
            # 如果有实时数据，计算一些统计信息
            if historical_df is not None and not historical_df.empty and realtime_data:
                last_close = historical_df.iloc[-1]["close"]
                current_price = float(realtime_data.get("last_price", 0))
                
                result.update({
                    "last_close": last_close,
                    "current_price": current_price,
                    "price_change": current_price - last_close,
                    "price_change_pct": (current_price - last_close) / last_close * 100 if last_close > 0 else 0
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取组合数据出错: {e}")
            return {"symbol": symbol, "error": str(e)}
    
    def get_client_stats(self) -> Dict[str, Any]:
        """获取客户端统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            "client_id": self.client_id,
            "websocket_connected": self.is_connected,
            "realtime_cache_size": len(self.realtime_cache),
            "historical_cache_size": len(self.historical_cache),
            "active_subscriptions": len([s for s in self.subscription_cache.values() if s["status"] == "active"]),
            "stats": self.stats.copy()
        }


class RealTimeMonitorApp:
    """实时监控应用
    
    结合 WebSocket 和 REST API 构建的实时股票监控应用
    """
    
    def __init__(self, symbols: List[str]):
        """初始化监控应用
        
        Args:
            symbols: 监控的股票列表
        """
        self.symbols = symbols
        self.client = IntegratedDataClient()
        self.data_history: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in symbols}
        self.is_running = False
        
        # 设置回调
        self.client.on_realtime_data = self._on_realtime_data
        self.client.on_consistency_error = self._on_consistency_error
    
    async def start(self):
        """启动监控应用"""
        print_section_header("启动实时监控应用")
        
        # 连接 WebSocket
        if not await self.client.connect():
            print("❌ WebSocket 连接失败")
            return
        
        print("✅ WebSocket 连接成功")
        
        # 订阅实时数据
        print("📡 订阅实时数据...")
        for symbol in self.symbols:
            await self.client.subscribe_realtime_data(symbol, "quote")
            await asyncio.sleep(0.1)  # 避免请求过快
        
        print(f"✅ 已订阅 {len(self.symbols)} 只股票的实时数据")
        
        # 获取历史数据作为基准
        print("📊 获取历史数据...")
        for symbol in self.symbols:
            historical_data = self.client.get_historical_data(
                symbol,
                (datetime.now() - timedelta(days=5)).strftime("%Y%m%d"),
                datetime.now().strftime("%Y%m%d")
            )
            
            if historical_data is not None and not historical_data.empty:
                print(f"✅ {symbol}: 获取到 {len(historical_data)} 条历史数据")
            else:
                print(f"⚠️ {symbol}: 历史数据获取失败")
        
        self.is_running = True
        print("🚀 监控应用已启动")
    
    async def stop(self):
        """停止监控应用"""
        self.is_running = False
        await self.client.disconnect()
        print("⏹️ 监控应用已停止")
    
    async def _on_realtime_data(self, symbol: str, data: Dict[str, Any], timestamp: str):
        """处理实时数据
        
        Args:
            symbol: 股票代码
            data: 实时数据
            timestamp: 时间戳
        """
        # 记录数据历史
        self.data_history[symbol].append({
            "timestamp": timestamp,
            "price": float(data.get("last_price", 0)),
            "volume": int(data.get("volume", 0)),
            "change_pct": float(data.get("change_percent", 0))
        })
        
        # 保持历史数据在合理范围内
        if len(self.data_history[symbol]) > 100:
            self.data_history[symbol] = self.data_history[symbol][-100:]
        
        # 显示实时数据
        price = data.get("last_price", 0)
        change_pct = data.get("change_percent", 0)
        volume = data.get("volume", 0)
        
        change_emoji = "🔴" if change_pct < 0 else "🟢" if change_pct > 0 else "⚪"
        print(f"{change_emoji} {symbol}: ¥{price} ({change_pct:+.2f}%) 成交量: {format_number(volume)}")
    
    async def _on_consistency_error(self, symbol: str, error_info: Dict[str, Any]):
        """处理数据一致性错误
        
        Args:
            symbol: 股票代码
            error_info: 错误信息
        """
        print(f"⚠️ 数据一致性警告 {symbol}:")
        print(f"   实时价格: ¥{error_info['realtime_price']}")
        print(f"   REST价格: ¥{error_info['rest_price']}")
        print(f"   差异: {error_info['difference_pct']:.2f}%")
    
    async def run_monitoring(self, duration: int = 60):
        """运行监控
        
        Args:
            duration: 监控时长（秒）
        """
        if not self.is_running:
            await self.start()
        
        print(f"⏰ 开始监控 {duration} 秒...")
        
        start_time = time.time()
        last_consistency_check = 0
        
        while self.is_running and (time.time() - start_time) < duration:
            await asyncio.sleep(1)
            
            # 每30秒进行一次数据一致性检查
            if time.time() - last_consistency_check > 30:
                print("\n🔍 进行数据一致性检查...")
                for symbol in self.symbols:
                    if symbol in self.client.realtime_cache:
                        result = await self.client.verify_data_consistency(symbol)
                        if result["consistent"]:
                            print(f"✅ {symbol}: 数据一致")
                        else:
                            print(f"❌ {symbol}: 数据不一致 - {result.get('error', '未知错误')}")
                
                last_consistency_check = time.time()
                print()
        
        # 显示统计信息
        stats = self.client.get_client_stats()
        print("\n📊 监控统计:")
        print(f"   REST API 调用: {stats['stats']['rest_api_calls']}")
        print(f"   WebSocket 消息: {stats['stats']['websocket_messages']}")
        print(f"   缓存命中: {stats['stats']['cache_hits']}")
        print(f"   缓存未命中: {stats['stats']['cache_misses']}")
        print(f"   一致性检查: {stats['stats']['data_consistency_checks']}")
        print(f"   一致性错误: {stats['stats']['consistency_errors']}")
    
    def plot_realtime_data(self, symbol: str):
        """绘制实时数据图表
        
        Args:
            symbol: 股票代码
        """
        if symbol not in self.data_history or not self.data_history[symbol]:
            print(f"❌ 没有 {symbol} 的实时数据")
            return
        
        data = self.data_history[symbol]
        
        # 提取数据
        timestamps = [datetime.fromisoformat(d["timestamp"]) for d in data]
        prices = [d["price"] for d in data]
        volumes = [d["volume"] for d in data]
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # 价格图
        ax1.plot(timestamps, prices, 'b-', linewidth=2)
        ax1.set_ylabel('价格 (¥)')
        ax1.set_title(f'{symbol} 实时数据')
        ax1.grid(True, alpha=0.3)
        
        # 成交量图
        ax2.bar(timestamps, volumes, width=0.0001, alpha=0.7, color='orange')
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('时间')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()


async def demo_basic_integration():
    """演示基本集成功能"""
    print_section_header("WebSocket 与 REST API 基本集成演示")
    
    # 创建集成客户端
    client = IntegratedDataClient()
    
    try:
        # 连接 WebSocket
        if await client.connect():
            print("✅ WebSocket 连接成功")
            
            # 测试股票
            symbol = "000001.SZ"
            
            # 获取历史数据
            print(f"\n📊 获取 {symbol} 历史数据...")
            historical_data = client.get_historical_data(
                symbol,
                (datetime.now() - timedelta(days=7)).strftime("%Y%m%d"),
                datetime.now().strftime("%Y%m%d")
            )
            
            if historical_data is not None and not historical_data.empty:
                print(f"✅ 获取到 {len(historical_data)} 条历史数据")
                print(f"   最新收盘价: ¥{historical_data.iloc[-1]['close']}")
            
            # 订阅实时数据
            print(f"\n📡 订阅 {symbol} 实时数据...")
            await client.subscribe_realtime_data(symbol, "quote")
            
            # 等待实时数据
            print("⏰ 等待实时数据...")
            await asyncio.sleep(10)
            
            # 获取最新价格
            print(f"\n💰 获取 {symbol} 最新价格...")
            latest_price = client.get_latest_price(symbol)
            if latest_price:
                print(f"✅ 最新价格: ¥{latest_price.get('current_price', 'N/A')}")
                print(f"   数据来源: {latest_price.get('source', 'REST API')}")
            
            # 验证数据一致性
            print(f"\n🔍 验证 {symbol} 数据一致性...")
            consistency_result = await client.verify_data_consistency(symbol)
            if consistency_result["consistent"]:
                print("✅ 数据一致性检查通过")
            else:
                print(f"❌ 数据一致性检查失败: {consistency_result.get('error', '未知错误')}")
            
            # 获取组合数据
            print(f"\n📈 获取 {symbol} 组合数据...")
            combined_data = client.get_combined_data(symbol, days=5)
            print(f"✅ 历史数据点: {combined_data['data_points']}")
            print(f"   实时数据: {'有' if combined_data['has_realtime'] else '无'}")
            
            if "price_change_pct" in combined_data:
                print(f"   价格变化: {combined_data['price_change_pct']:+.2f}%")
            
            # 显示统计信息
            stats = client.get_client_stats()
            print(f"\n📊 客户端统计:")
            print(f"   REST API 调用: {stats['stats']['rest_api_calls']}")
            print(f"   WebSocket 消息: {stats['stats']['websocket_messages']}")
            print(f"   缓存命中率: {stats['stats']['cache_hits']/(stats['stats']['cache_hits']+stats['stats']['cache_misses'])*100:.1f}%")
            
        else:
            print("❌ WebSocket 连接失败")
            
    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
    finally:
        await client.disconnect()


async def demo_realtime_monitoring():
    """演示实时监控应用"""
    print_section_header("实时监控应用演示")
    
    # 监控的股票列表
    symbols = ["000001.SZ", "600519.SH", "000002.SZ"]
    
    # 创建监控应用
    monitor = RealTimeMonitorApp(symbols)
    
    try:
        # 启动监控
        await monitor.start()
        
        # 运行监控
        await monitor.run_monitoring(duration=60)
        
        # 绘制图表（如果有数据）
        print("\n📈 生成实时数据图表...")
        for symbol in symbols:
            if symbol in monitor.data_history and monitor.data_history[symbol]:
                print(f"绘制 {symbol} 实时数据图表...")
                # monitor.plot_realtime_data(symbol)  # 注释掉以避免在无GUI环境中出错
                print(f"✅ {symbol} 图表数据已准备就绪")
        
    except Exception as e:
        print(f"❌ 监控应用出错: {e}")
    finally:
        await monitor.stop()


async def demo_performance_comparison():
    """演示性能对比"""
    print_section_header("性能对比演示")
    
    client = IntegratedDataClient()
    
    try:
        if await client.connect():
            print("✅ 连接成功")
            
            symbol = "000001.SZ"
            
            # 订阅实时数据
            await client.subscribe_realtime_data(symbol, "quote")
            await asyncio.sleep(5)  # 等待实时数据
            
            # 测试缓存性能
            print("\n🚀 测试缓存性能...")
            
            # 第一次调用（缓存未命中）
            start_time = time.time()
            price1 = client.get_latest_price(symbol, use_cache=False)
            time1 = time.time() - start_time
            
            # 第二次调用（缓存命中）
            start_time = time.time()
            price2 = client.get_latest_price(symbol, use_cache=True)
            time2 = time.time() - start_time
            
            print(f"REST API 调用时间: {time1*1000:.2f}ms")
            print(f"缓存调用时间: {time2*1000:.2f}ms")
            print(f"性能提升: {time1/time2:.1f}x")
            
            # 测试历史数据缓存
            print("\n📊 测试历史数据缓存...")
            
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")
            
            # 第一次调用
            start_time = time.time()
            hist1 = client.get_historical_data(symbol, start_date, end_date, use_cache=False)
            time1 = time.time() - start_time
            
            # 第二次调用（缓存命中）
            start_time = time.time()
            hist2 = client.get_historical_data(symbol, start_date, end_date, use_cache=True)
            time2 = time.time() - start_time
            
            print(f"首次获取历史数据: {time1*1000:.2f}ms")
            print(f"缓存获取历史数据: {time2*1000:.2f}ms")
            print(f"性能提升: {time1/time2:.1f}x")
            
            # 显示最终统计
            stats = client.get_client_stats()
            print(f"\n📊 最终统计:")
            print(f"   总缓存命中: {stats['stats']['cache_hits']}")
            print(f"   总缓存未命中: {stats['stats']['cache_misses']}")
            print(f"   缓存命中率: {stats['stats']['cache_hits']/(stats['stats']['cache_hits']+stats['stats']['cache_misses'])*100:.1f}%")
            
        else:
            print("❌ 连接失败")
            
    except Exception as e:
        print(f"❌ 性能测试出错: {e}")
    finally:
        await client.disconnect()


async def main():
    """主函数"""
    print("🎓 WebSocket 与 REST API 集成教程")
    print("本教程演示如何结合使用 WebSocket 实时数据和 REST API 历史数据")
    
    # 检查服务连接
    try:
        # 检查 REST API
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ REST API 服务连接正常")
        else:
            print("❌ REST API 服务连接异常")
            return
    except:
        print("❌ 无法连接到 REST API 服务")
        print("请确保服务已启动：python data_agent_service/main.py")
        return
    
    try:
        # 检查 WebSocket
        test_client = IntegratedDataClient()
        if await test_client.connect():
            print("✅ WebSocket 服务连接正常")
            await test_client.disconnect()
        else:
            print("❌ 无法连接到 WebSocket 服务")
            print("请确保服务已启动：python -m src.argus_mcp.websocket_server")
            return
    except Exception as e:
        print(f"❌ WebSocket 连接检查失败: {e}")
        return
    
    try:
        # 运行演示
        await demo_basic_integration()
        
        print("\n" + "="*60)
        input("按 Enter 键继续下一个演示...")
        
        await demo_realtime_monitoring()
        
        print("\n" + "="*60)
        input("按 Enter 键继续下一个演示...")
        
        await demo_performance_comparison()
        
    except KeyboardInterrupt:
        print("\n⏹️ 教程被用户中断")
    except Exception as e:
        print(f"❌ 教程运行出错: {e}")
    
    print("\n🎉 WebSocket 与 REST API 集成教程完成！")
    print("\n📚 学习要点总结：")
    print("1. WebSocket 实时数据与 REST API 历史数据的结合使用")
    print("2. 数据缓存策略和性能优化")
    print("3. 数据一致性验证和错误处理")
    print("4. 实时监控应用的构建")
    print("5. 混合数据源的统一管理")
    print("\n💡 下一步建议：")
    print("- 学习 WebSocket 性能优化技巧")
    print("- 探索更复杂的实时数据分析")
    print("- 了解生产环境部署最佳实践")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 教程结束")
    except Exception as e:
        logger.error(f"教程运行失败: {e}")
        sys.exit(1)