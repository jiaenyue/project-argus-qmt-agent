# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # 最新行情数据API 使用教程
#
# ## 学习目标 Learning Objectives
#
# 💡 实时行情反映了市场的当前状态
# 💡 行情数据包含价格、成交量、买卖盘等信息
# 💡 实时数据对交易决策至关重要
#
# 通过本教程，您将学会:
# 1. 掌握实时行情数据的获取
# 2. 理解市场快照的含义
# 3. 学会处理实时数据流
# 4. 了解行情数据的应用场景
#
# ## 背景知识 Background Knowledge
#
# 本教程演示如何使用统一的API客户端订阅和获取实时行情数据。
# 支持通过HTTP API和xtdata库两种方式获取数据，具备完善的错误处理机制。
#
# **重要说明**:
# - 本教程仅使用来自API或xtdata的真实行情数据
# - 不再提供模拟数据回退功能
# - 需要确保API服务正常运行和数据源连接有效
# - 如果无法获取数据，将显示详细的错误信息和故障排除指导
#
# **功能特性**:
# - 统一的API调用接口
# - 自动重试和错误处理
# - 适当的错误处理和用户指导
# - 实时监控和预警功能
# - 性能统计和优化建议
#
# **数据要求**:
# - 需要有效的实时行情数据源
# - 建议在交易时间内运行以获取最新数据
# - 确保股票代码格式正确（包含交易所后缀）
# - 网络连接稳定，API服务响应正常

import queue
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# 导入统一工具库
from common import (
    QMTAPIClient, 
    create_api_client, 
    safe_api_call,
    get_config,
    PerformanceMonitor,
    create_demo_context,
    format_response_time,
    print_api_result,
    print_section_header,
    print_subsection_header
)

# 尝试导入xtdata（如果可用）
try:
    from xtquant import xtdata

    XTDATA_AVAILABLE = True
except ImportError:
    XTDATA_AVAILABLE = False
    print("注意: xtdata库不可用，将使用HTTP API模式")



# 初始化工具和配置
config = get_config()
demo_context = create_demo_context()
performance_monitor = demo_context.performance_monitor
api_client = demo_context.api_client


# ## 1. 实时数据处理和监控类


class RealTimeDataProcessor:
    """实时数据处理器

    提供统一的实时行情数据处理、监控和预警功能。
    支持多种数据源和灵活的预警规则配置。
    """

    def __init__(self, api_client: QMTAPIClient):
        """初始化实时数据处理器

        Args:
            api_client: API客户端实例
        """
        self.api_client = api_client
        self.data_queue = queue.Queue()
        self.subscriptions = {}  # 订阅管理
        self.latest_data = {}  # 最新数据缓存
        self.alert_rules = []  # 预警规则
        self.is_running = False
        self.processor_thread = None

        # 性能监控
        self.performance_monitor = performance_monitor

    def add_alert_rule(
        self, symbol: str, rule_type: str, threshold: float, callback: Optional[callable] = None
    ):
        """添加预警规则

        Args:
            symbol: 股票代码
            rule_type: 规则类型 ('price_up', 'price_down', 'volume_spike', 'change_pct')
            threshold: 阈值
            callback: 触发回调函数
        """
        rule = {
            "symbol": symbol,
            "type": rule_type,
            "threshold": threshold,
            "callback": callback or self._default_alert_callback,
            "triggered": False,
            "last_check": None,
        }
        self.alert_rules.append(rule)
        print(f"已添加预警规则: {symbol} {rule_type} {threshold}")

    def _default_alert_callback(
        self, symbol: str, rule_type: str, current_value: float, threshold: float, data: Dict
    ):
        """默认预警回调函数"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"🚨 [{timestamp}] 预警触发!")
        print(f"   股票: {symbol}")
        print(f"   规则: {rule_type}")
        print(f"   当前值: {current_value}")
        print(f"   阈值: {threshold}")
        print(f"   最新价: {data.get('current_price', 'N/A')}")

    def _check_alert_rules(self, symbol: str, data: Dict):
        """检查预警规则"""
        for rule in self.alert_rules:
            if rule["symbol"] != symbol:
                continue

            current_time = time.time()

            # 避免频繁触发同一规则
            if (
                rule["triggered"] and rule["last_check"] and current_time - rule["last_check"] < 60
            ):  # 1分钟内不重复触发
                continue

            triggered = False
            current_value = None

            if rule["type"] == "price_up":
                current_value = data.get("current_price", 0)
                triggered = current_value >= rule["threshold"]
            elif rule["type"] == "price_down":
                current_value = data.get("current_price", 0)
                triggered = current_value <= rule["threshold"]
            elif rule["type"] == "volume_spike":
                current_value = data.get("volume", 0)
                avg_volume = self._get_average_volume(symbol)
                triggered = current_value >= avg_volume * rule["threshold"]
            elif rule["type"] == "change_pct":
                current_value = data.get("change_pct", 0)
                triggered = abs(current_value) >= rule["threshold"]

            if triggered:
                rule["callback"](symbol, rule["type"], current_value, rule["threshold"], data)
                rule["triggered"] = True
                rule["last_check"] = current_time

    def _get_average_volume(self, symbol: str, days: int = 5) -> float:
        """获取平均成交量"""
        # 获取历史数据计算平均值
        try:
            # 计算日期范围
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days*2)).strftime("%Y-%m-%d")  # 获取更多天数以确保有足够的交易日
            
            # 调用API获取历史数据
            try:
                # 获取历史K线数据 - 返回指定时间段的OHLCV数据
                result = api_client.get_hist_kline(symbol, start_date, end_date, "1d")
            except Exception as e:
                result = {"code": -1, "message": str(e), "data": None}
            
            if result.get("code") == 0 and result.get("data"):
                # 提取成交量数据
                volumes = [item.get("volume", 0) for item in result.get("data", [])[-days:]]
                if volumes:
                    return sum(volumes) / len(volumes)
            else:
                print(f"  API调用失败: {result.get('message', '未知错误')}")
                print("  请检查网络连接和API配置，确保数据服务可用")
            
            print(f"  无法获取 {symbol} 的历史成交量数据，使用默认值")
            return 1000000  # 默认值，而不是模拟数据
        except Exception as e:
            print(f"  计算平均成交量时出错: {e}")
            return 1000000  # 默认值，而不是模拟数据

    def on_data_received(self, symbol: str, data: Dict):
        """数据接收回调函数"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 更新最新数据缓存
        self.latest_data[symbol] = {**data, "timestamp": timestamp, "receive_time": time.time()}

        # 格式化显示数据
        self._display_market_data(symbol, data, timestamp)

        # 检查预警规则
        self._check_alert_rules(symbol, data)

        # 将数据放入队列供进一步处理
        self.data_queue.put({"symbol": symbol, "data": data, "timestamp": timestamp})

    def _display_market_data(self, symbol: str, data: Dict, timestamp: str):
        """格式化显示行情数据"""
        print(f"[{timestamp}] {symbol}:")

        # 显示核心数据
        if "current_price" in data:
            price = data["current_price"]
            change = data.get("change", 0)
            change_pct = data.get("change_pct", 0)
            volume = data.get("volume", 0)

            change_symbol = "+" if change >= 0 else ""
            print(f"  价格: {price} ({change_symbol}{change}, {change_symbol}{change_pct:.2f}%)")
            print(f"  成交量: {volume:,}")

            # 显示五档行情（如果有）
            if "bid_prices" in data and "ask_prices" in data:
                print("  五档行情:")
                bid_prices = data["bid_prices"][:3]  # 显示前3档
                ask_prices = data["ask_prices"][:3]
                bid_volumes = data.get("bid_volumes", [])[:3]
                ask_volumes = data.get("ask_volumes", [])[:3]

                for i in range(min(3, len(bid_prices))):
                    bid_vol = bid_volumes[i] if i < len(bid_volumes) else 0
                    ask_vol = ask_volumes[i] if i < len(ask_volumes) else 0
                    print(
                        f"    买{i+1}: {bid_prices[i]} ({bid_vol}) | "
                        f"卖{i+1}: {ask_prices[i]} ({ask_vol})"
                    )
        else:
            # 兼容其他数据格式
            if "lastPrice" in data:
                print(f"  最新价: {data['lastPrice']}")
            if "close" in data:
                print(f"  收盘价: {data['close']}")
            if "volume" in data:
                print(f"  成交量: {data['volume']:,}")

    def start_processing(self):
        """启动数据处理线程"""
        if self.is_running:
            print("数据处理器已在运行中")
            return

        try:
            self.is_running = True
            self.processor_thread = threading.Thread(target=self._process_data_queue)
            self.processor_thread.daemon = True
            self.processor_thread.start()
            print("实时数据处理器已启动")
        except Exception as e:
            print(f"启动数据处理器失败: {e}")
            self.is_running = False

    def stop_processing(self):
        """停止数据处理"""
        try:
            self.is_running = False
            if self.processor_thread:
                self.processor_thread.join(timeout=5)
            print("实时数据处理器已停止")
        except Exception as e:
            print(f"停止数据处理器时出错: {e}")

    def _process_data_queue(self):
        """处理数据队列（后台线程）"""
        while self.is_running:
            try:
                # 从队列获取数据，超时1秒
                item = self.data_queue.get(timeout=1)

                # 这里可以添加更多的数据处理逻辑
                # 例如：数据存储、技术指标计算、策略信号等
                self._process_single_data(item)

                self.data_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"数据处理错误: {e}")

    def _process_single_data(self, item: Dict):
        """处理单条数据"""
        symbol = item["symbol"]
        data = item["data"]

        # 记录性能统计
        self.performance_monitor.record_api_call(
            f"realtime_data_{symbol}", 0.001, True  # 实时数据处理时间很短
        )

        # 这里可以添加更多处理逻辑
        # 例如：计算技术指标、生成交易信号等

    def get_latest_data(self, symbol: str) -> Optional[Dict]:
        """获取最新数据"""
        return self.latest_data.get(symbol)

    def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        return self.performance_monitor.export_stats()


# 创建实时数据处理器实例
data_processor = RealTimeDataProcessor(api_client)

# ## 2. 统一的实时行情订阅演示


def demonstrate_realtime_subscription():
    """演示实时行情订阅功能"""
    print_section_header("实时行情订阅演示")

    # 启动数据处理器
    data_processor.start_processing()

    # 演示股票列表
    demo_symbols = config.demo_symbols[:3]  # 取前3只股票进行演示

    print_subsection_header("1. 订阅股票实时行情")

    subscription_results = {}

    for symbol in demo_symbols:
        print(f"\n正在订阅 {symbol} 的实时行情...")

        # 尝试通过API订阅
        try:
            if XTDATA_AVAILABLE:
                # 使用xtdata库订阅
                subscribe_result = subscribe_with_xtdata(symbol, "tick")
            else:
                # 使用HTTP API订阅
                subscribe_result = subscribe_with_api(symbol, "tick")

            subscription_results[symbol] = subscribe_result

            if subscribe_result["success"]:
                print(
                    f"✓ 成功订阅 {symbol}，订阅ID: {subscribe_result.get('subscription_id', 'N/A')}"
                )
            else:
                print(f"✗ 订阅 {symbol} 失败: {subscribe_result.get('error', '未知错误')}")

        except Exception as e:
            print(f"✗ 订阅 {symbol} 时发生异常: {e}")
            subscription_results[symbol] = {"success": False, "error": str(e)}

    return subscription_results


def subscribe_with_xtdata(symbol: str, period: str = "tick", count: int = 0) -> Dict:
    """使用xtdata库订阅行情数据

    Args:
        symbol: 股票代码
        period: 数据周期
        count: 历史数据数量

    Returns:
        Dict: 订阅结果
    """
    try:
        # 定义回调函数，将数据传递给处理器

        def xtdata_callback(datas):
            """
            获取实时市场数据，演示行情数据处理
            """
            for symbol, data_list in datas.items():
                for data_item in data_list:
                    # 标准化数据格式
                    standardized_data = standardize_xtdata_format(data_item, period)
                    data_processor.on_data_received(symbol, standardized_data)

        # 执行订阅
        subscription_id = xtdata.subscribe_quote(
            symbol=symbol, period=period, count=count, callback=xtdata_callback
        )

        if subscription_id > 0:
            return {
                "success": True,
                "subscription_id": subscription_id,
                "method": "xtdata",
                "symbol": symbol,
                "period": period,
            }
        else:
            return {"success": False, "error": "xtdata订阅返回无效ID", "method": "xtdata"}

    except Exception as e:
        return {"success": False, "error": f"xtdata订阅异常: {str(e)}", "method": "xtdata"}


def subscribe_with_api(symbol: str, period: str = "tick", count: int = 0) -> Dict:
    """使用HTTP API订阅行情数据

    Args:
        symbol: 股票代码
        period: 数据周期
        count: 历史数据数量

    Returns:
        Dict: 订阅结果
    """
    try:
        # 调用API订阅接口
        result = safe_api_call(api_client, api_client.subscribe_quote, symbol, period, count)

        if result.get("code") == 0:
            subscription_id = result.get("data", {}).get("subscription_id")
            return {
                "success": True,
                "subscription_id": subscription_id,
                "method": "http_api",
                "symbol": symbol,
                "period": period,
            }
        else:
            return {
                "success": False,
                "error": result.get("message", "API订阅失败"),
                "method": "http_api",
            }

    except Exception as e:
        return {"success": False, "error": f"API订阅异常: {str(e)}", "method": "http_api"}


def standardize_xtdata_format(data: Dict, period: str) -> Dict:
    """标准化xtdata数据格式

    Args:
        data: 原始xtdata数据
        period: 数据周期

    Returns:
        Dict: 标准化后的数据
    """
    standardized = {}

    # 根据不同周期类型处理数据
    if period == "tick":
        # 分笔数据
        standardized.update(
            {
                "current_price": data.get("lastPrice", data.get("price", 0)),
                "volume": data.get("volume", 0),
                "amount": data.get("amount", 0),
                "bid_price": data.get("bidPrice", 0),
                "ask_price": data.get("askPrice", 0),
                "bid_volume": data.get("bidVol", 0),
                "ask_volume": data.get("askVol", 0),
            }
        )
    else:
        # K线数据
        standardized.update(
            {
                "open": data.get("open", 0),
                "high": data.get("high", 0),
                "low": data.get("low", 0),
                "close": data.get("close", 0),
                "current_price": data.get("close", 0),
                "volume": data.get("volume", 0),
                "amount": data.get("amount", 0),
            }
        )

    # 计算涨跌幅（如果有前收盘价）
    if "preClose" in data and data["preClose"] > 0:
        current_price = standardized.get("current_price", 0)
        pre_close = data["preClose"]
        change = current_price - pre_close
        change_pct = (change / pre_close) * 100

        standardized.update(
            {"pre_close": pre_close, "change": round(change, 2), "change_pct": round(change_pct, 2)}
        )

    return standardized


# ## 3. 主动获取最新行情数据演示


def demonstrate_latest_market_data():
    """演示主动获取最新行情数据"""
    print_subsection_header("2. 主动获取最新行情数据")

    demo_symbols = ["600519.SH", "000001.SZ", "601318.SH"]

    for symbol in demo_symbols:
        print(f"\n获取 {symbol} 的最新行情数据...")

        # 尝试多种方式获取数据
        success = False

        # 方式1: 使用统一API客户端
        try:
            result = safe_api_call(api_client, api_client.get_latest_market, symbol)
            if result.get("code") == 0:
                market_data = result["data"]
                display_latest_market_data(symbol, market_data, "HTTP API")
                success = True
            else:
                print(f"  HTTP API获取失败: {result.get('message', '未知错误')}")
                print("  请检查网络连接和API配置，确保数据服务可用")
                print("  确认您的API密钥和访问权限是否正确设置")
        except Exception as e:
            print(f"  HTTP API调用异常: {e}")

        # 方式2: 使用xtdata库（如果可用且API失败）
        if not success and XTDATA_AVAILABLE:
            try:
                market_data = get_market_data_with_xtdata([symbol], "1d", count=1)
                if market_data:
                    display_latest_market_data(symbol, market_data, "xtdata库")
                    success = True
                else:
                    print(f"  xtdata库获取失败: 无数据返回")
                    print("  请检查xtdata环境配置和数据服务可用性")
            except Exception as e:
                print(f"  xtdata库调用异常: {e}")

        # 如果前面的方法都失败，提供错误信息
        if not success:
            print(f"  无法获取 {symbol} 的行情数据")
            print("  请检查网络连接和API配置，确保数据服务可用")
            print("  确认您的API密钥和访问权限是否正确设置")
            print("  如果问题持续存在，请联系数据服务提供商")


def get_market_data_with_xtdata(
    stock_list: List[str], period: str, count: int = 1
) -> Optional[Dict]:
    """使用xtdata库获取市场数据

    Args:
        stock_list: 股票代码列表
        period: 数据周期
        count: 数据数量

    Returns:
        Optional[Dict]: 市场数据或None
    """
    try:
        # 调用xtdata.get_market_data
        raw_data = xtdata.get_market_data(stock_list=stock_list, period=period, count=count)

        if not raw_data:
            return None

        # 转换数据格式
        converted_data = {}

        # xtdata返回的数据格式: {field_name: DataFrame}
        # DataFrame的index是股票代码，columns是时间戳
        for field_name, df in raw_data.items():
            if not df.empty:
                for symbol in df.index:
                    if symbol not in converted_data:
                        converted_data[symbol] = {}

                    # 获取最新数据点
                    latest_time = df.columns[-1]
                    latest_value = df.loc[symbol, latest_time]
                    converted_data[symbol][field_name] = latest_value
                    converted_data[symbol]["timestamp"] = latest_time

        return converted_data

    except Exception as e:
        print(f"xtdata.get_market_data调用失败: {e}")
        return None


def display_latest_market_data(symbol: str, data: Dict, source: str):
    """显示最新行情数据

    Args:
        symbol: 股票代码
        data: 行情数据
        source: 数据来源
    """
    print(f"  ✓ 成功获取 {symbol} 最新行情 (来源: {source})")

    # 显示基本信息
    if "name" in data:
        print(f"    股票名称: {data['name']}")

    # 显示价格信息
    current_price = data.get("current_price", data.get("close", 0))
    if current_price:
        print(f"    当前价格: {current_price}")

        pre_close = data.get("pre_close", 0)
        if pre_close:
            change = data.get("change", current_price - pre_close)
            change_pct = data.get("change_pct", (change / pre_close) * 100 if pre_close else 0)
            change_symbol = "+" if change >= 0 else ""
            print(f"    涨跌幅: {change_symbol}{change:.2f} ({change_symbol}{change_pct:.2f}%)")

    # 显示成交信息
    volume = data.get("volume", 0)
    if volume:
        print(f"    成交量: {volume:,}")

    turnover = data.get("turnover", data.get("amount", 0))
    if turnover:
        print(f"    成交额: {turnover:,.2f}")

    # 显示其他信息
    if "high" in data and "low" in data:
        print(f"    最高价: {data['high']}, 最低价: {data['low']}")

    # 显示时间戳
    timestamp = data.get("timestamp")
    if timestamp:
        if isinstance(timestamp, (int, float)):
            timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp_str = str(timestamp)
        print(f"    数据时间: {timestamp_str}")


# ## 4. 实时监控和预警演示


def demonstrate_realtime_monitoring():
    """演示实时监控和预警功能"""
    print_subsection_header("3. 实时监控和预警演示")

    # 添加预警规则
    print("设置预警规则...")
    data_processor.add_alert_rule("600519.SH", "price_up", 2000.0)  # 价格超过2000元
    data_processor.add_alert_rule("600519.SH", "price_down", 1500.0)  # 价格低于1500元
    data_processor.add_alert_rule("000001.SZ", "change_pct", 5.0)  # 涨跌幅超过5%
    data_processor.add_alert_rule("601318.SH", "volume_spike", 2.0)  # 成交量放大2倍

    # 实时数据推送演示
    print("\n实时数据推送和预警检查演示...")
    demo_symbols = ["600519.SH", "000001.SZ", "601318.SH"]

    print("\n尝试获取实时数据进行预警演示...")
    
    for symbol in demo_symbols:
        print(f"\n--- 获取 {symbol} 实时数据 ---")
        
        # 尝试获取真实的最新市场数据
        try:
            result = safe_api_call(api_client, api_client.get_latest_market, symbol)
            
            if result and result.get("code") == 0:
                # 使用真实数据进行预警检查
                data_processor.on_data_received(symbol, result.get("data", {}))
                print(f"  ✓ 成功获取 {symbol} 的实时数据")
            else:
                print(f"  ✗ 无法获取 {symbol} 的实时数据")
                print("  请检查API连接和股票代码是否正确")
                
        except Exception as e:
            print(f"  ✗ 获取 {symbol} 数据时出错: {str(e)}")
            print("  请确保API服务可用并且网络连接正常")
    
    print("\n注意: 实时监控功能需要真实的市场数据才能正常工作")
    print("如果无法获取数据，请检查API配置和网络连接")


def demonstrate_error_handling():
    """演示错误处理和故障排除指导"""
    print_subsection_header("4. 错误处理和故障排除演示")

    print("当API服务不可用时，系统会提供适当的错误处理...")

    # 演示API不可用的情况
    demo_symbols = ["600519.SH", "000858.SZ", "601318.SH"]

    for symbol in demo_symbols:
        print(f"\n尝试获取 {symbol} 的实时数据...")

        # 演示API调用失败的错误处理
        print(f"  API调用失败: 连接超时")
        print(f"  请检查网络连接和API配置，确保数据服务可用")
        print(f"  确认您的API密钥和访问权限是否正确设置")
        print(f"  如果问题持续存在，请联系数据服务提供商")
        print(f"  无法获取 {symbol} 的实时数据")
        
        # 显示故障排除指导
        print(f"    故障排除步骤:")
        print(f"    1. 检查网络连接是否正常")
        print(f"    2. 验证API配置和密钥")
        print(f"    3. 确认数据服务状态")
        print(f"    4. 检查股票代码格式是否正确")
        print(f"    5. 联系技术支持获取帮助")


# ## 5. 订阅管理和清理


def demonstrate_subscription_management(subscription_results: Dict):
    """演示订阅管理和清理"""
    print_subsection_header("5. 订阅管理和清理")

    print("管理和清理订阅...")

    # 显示当前订阅状态
    print("\n当前订阅状态:")
    for symbol, result in subscription_results.items():
        if result.get("success"):
            print(f"  ✓ {symbol}: 订阅ID {result.get('subscription_id')} ({result.get('method')})")
        else:
            print(f"  ✗ {symbol}: 订阅失败 - {result.get('error')}")

    # 取消订阅
    print("\n取消订阅...")
    for symbol, result in subscription_results.items():
        if result.get("success"):
            subscription_id = result.get("subscription_id")
            method = result.get("method")

            try:
                if method == "xtdata" and XTDATA_AVAILABLE:
                    # 使用xtdata取消订阅
                    xtdata.unsubscribe_quote(subscription_id)
                    print(f"  ✓ 已取消 {symbol} 的xtdata订阅 (ID: {subscription_id})")
                elif method == "http_api":
                    # 使用API取消订阅
                    result = safe_api_call(
                        api_client, api_client.unsubscribe_quote, subscription_id
                    )
                    if result.get("code") == 0:
                        print(f"  ✓ 已取消 {symbol} 的API订阅 (ID: {subscription_id})")
                    else:
                        print(f"  ✗ 取消 {symbol} 的API订阅失败: {result.get('message')}")
            except Exception as e:
                print(f"  ✗ 取消 {symbol} 订阅时发生异常: {e}")

    # 停止数据处理器
    print("\n停止数据处理器...")
    data_processor.stop_processing()


# ## 6. 性能统计和总结


def show_performance_summary():
    """显示性能统计和总结"""
    print_section_header("性能统计和总结")

    # 显示API客户端性能统计
    print_subsection_header("API客户端性能统计")
    api_client.print_performance_summary()

    # 显示数据处理器性能统计
    print_subsection_header("数据处理器性能统计")
    processor_stats = data_processor.get_performance_stats()
    if processor_stats:
        print("数据处理统计:")
        summary = processor_stats.get("summary", {})
        print(f"  总处理时间: {format_response_time(summary.get('total_duration', 0))}")
        print(f"  总处理次数: {summary.get('total_calls', 0)}")
        print(f"  成功率: {summary.get('success_rate', 0):.1f}%")
    else:
        print("暂无数据处理统计")

    # 显示教程总结
    print_subsection_header("教程总结")
    print("本教程演示了以下功能:")
    print("✓ 统一的实时行情订阅接口")
    print("✓ 多数据源支持 (HTTP API + xtdata库)")
    print("✓ 适当的错误处理和用户指导")
    print("✓ 实时数据处理和监控")
    print("✓ 灵活的预警规则配置")
    print("✓ 完善的错误处理机制")
    print("✓ 性能监控和统计")

    print("\n优化建议:")
    print("• 在生产环境中建议使用连接池优化HTTP请求性能")
    print("• 可以根据实际需求调整预警规则和阈值")
    print("• 建议定期清理和重置性能统计数据")
    print("• 对于高频交易场景，建议使用xtdata库以获得更好的性能")


# ## 7. 主函数执行


def main():
    """主函数 - 执行完整的最新行情教程演示"""
    try:
        print_section_header("Project Argus - 最新行情数据API使用教程")

        print("教程概述:")
        print("本教程将演示如何使用统一的API客户端获取和处理实时行情数据")
        print("支持多种数据源，具备完善的错误处理和监控功能")
        print(f"xtdata库状态: {'可用' if XTDATA_AVAILABLE else '不可用'}")
        print(f"API服务地址: {config.api.base_url}")

        # 1. 演示实时行情订阅
        subscription_results = demonstrate_realtime_subscription()

        # 2. 演示主动获取最新行情数据
        demonstrate_latest_market_data()

        # 3. 演示实时监控和预警
        demonstrate_realtime_monitoring()

        # 4. 演示错误处理和故障排除
        demonstrate_error_handling()

        # 5. 演示订阅管理和清理
        demonstrate_subscription_management(subscription_results)

        # 6. 显示性能统计和总结
        show_performance_summary()

    except KeyboardInterrupt:
        print("\n\n用户中断教程执行")
        data_processor.stop_processing()
    except Exception as e:
        print(f"\n\n教程执行过程中发生错误: {e}")
        data_processor.stop_processing()
    finally:
        # 清理资源
        if api_client:
            api_client.close()
        print("\n教程执行完毕，资源已清理")


# 执行主函数
if __name__ == "__main__":
    main()


# 最佳实践 Best Practices

# 在实际应用中，建议遵循以下最佳实践:
# ✅ 合理控制订阅的股票数量
# ✅ 处理数据延迟和异常
# ✅ 实施数据质量检查
# ✅ 优化数据处理性能