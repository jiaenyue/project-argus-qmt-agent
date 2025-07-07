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

# # 最新行情数据API 使用教程 (基于xtdata库)
#
# 本教程演示如何使用 `xtdata` 库订阅和获取实时行情数据。
# `xtdata` 模块提供与 MiniQmt 的交互接口，用于处理行情数据请求并回传结果。
#
# **注意**: 本教程仅使用 `xtdata` 库进行数据交互，不涉及HTTP调用。
# 确保 MiniQmt 已正确运行并连接。

import time
import numpy as np # 导入numpy用于处理ndarray数据
import pandas as pd # 导入pandas用于处理DataFrame数据
from xtquant import xtdata # Corrected import for xtdata

# ## 1. 定义数据回调函数
# 当订阅的行情数据有更新时，`xtdata` 会通过此回调函数推送数据。
# 回调函数的格式为 `on_data(datas)`，其中 `datas` 是一个字典，
# 键为股票代码，值为该股票的最新行情数据列表。
def on_data(datas):
    """
    行情数据回调函数。
    datas: dict, 格式为 { stock_code : [data1, data2, ...] }
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 收到行情数据:")
    for stock_code in datas:
        # datas[stock_code] 是一个列表，包含该股票的最新数据点
        # 对于实时行情，通常列表只包含一个最新数据点
        for data in datas[stock_code]:
            # 根据period类型，data的字段会有所不同
            # 这里以tick数据为例，打印最新价和成交量
            # 如果是K线数据，字段会是'open', 'high', 'low', 'close', 'volume', 'amount'等
            if 'lastPrice' in data and 'volume' in data:
                print(f"  {stock_code}: 最新价={data['lastPrice']}, 成交量={data['volume']}")
            elif 'close' in data and 'volume' in data: # K线数据
                print(f"  {stock_code}: 收盘价={data['close']}, 成交量={data['volume']}")
            else:
                print(f"  {stock_code}: {data}")

# ## 2. 订阅单只股票的实时行情
# 使用 `xtdata.subscribe_quote` 函数订阅指定股票的行情数据。
# 参数 `count=0` 表示只订阅实时数据，不请求历史数据。
# `period='tick'` 表示订阅分笔数据。
#
# **参数说明**:
# - `stock_code`: 字符串，合约代码，例如 "600519.SH"。
# - `period`: 字符串，周期类型，例如 'tick', '1m', '5m', '1d' 等。
# - `count`: 整数，请求历史数据个数，`0` 表示不请求历史数据，只订阅实时推送。
# - `callback`: 回调函数，用于接收推送的行情数据。

print("\n--- 订阅单只股票实时行情 (600519.SH, tick数据) ---")
# 订阅贵州茅台(600519.SH)的分笔行情
subscribe_id_tick = xtdata.subscribe_quote(stock_code='600519.SH', period='tick', count=0, callback=on_data)
if subscribe_id_tick > 0:
    print(f"成功订阅 600519.SH tick行情，订阅号: {subscribe_id_tick}")
else:
    print("订阅 600519.SH tick行情失败。请检查MiniQmt连接和数据权限。")

print("\n--- 订阅单只股票实时行情 (000001.SZ, 1分钟K线数据) ---")
# 订阅平安银行(000001.SZ)的1分钟K线行情
subscribe_id_kline = xtdata.subscribe_quote(stock_code='000001.SZ', period='1m', count=0, callback=on_data)
if subscribe_id_kline > 0:
    print(f"成功订阅 000001.SZ 1分钟K线行情，订阅号: {subscribe_id_kline}")
else:
    print("订阅 000001.SZ 1分钟K线行情失败。请检查MiniQmt连接和数据权限。")

# ## 3. 主动获取最新行情数据
# 除了订阅推送，也可以使用 `xtdata.get_market_data` 主动从缓存中获取行情数据。
# 这对于获取当前最新快照或少量历史数据非常有用。
#
# **参数说明**:
# - `stock_list`: 列表，合约代码列表。
# - `period`: 字符串，周期类型。
# - `count`: 整数，获取数据个数，`-1` 表示获取所有缓存数据。
# - `field_list`: 列表，需要获取的字段列表，空列表表示获取所有字段。

print("\n--- 主动获取最新行情数据 (600519.SH, 1d日线数据) ---")
# 获取贵州茅台(600519.SH)的最新日线数据
# 注意：get_market_data获取的是缓存数据，如果之前没有订阅或下载过，可能为空
try:
    daily_data = xtdata.get_market_data(stock_list=['600519.SH'], period='1d', count=1)
    if daily_data and 'close' in daily_data and 'volume' in daily_data:
        print("获取到 600519.SH 最新日线数据:")
        # daily_data 返回的是一个字典，键是字段名，值是DataFrame
        # DataFrame的index是股票代码，columns是时间戳
        close_prices = daily_data['close']
        volumes = daily_data['volume']
        for stock in close_prices.index:
            # 获取最新的数据点（DataFrame的最后一列）
            latest_time = close_prices.columns[-1]
            latest_close = close_prices.loc[stock, latest_time]
            latest_volume = volumes.loc[stock, latest_time]
            print(f"  {stock}: 最新收盘价={latest_close}, 最新成交量={latest_volume}")
    else:
        print("未获取到 600519.SH 日线数据，可能需要先订阅或下载历史数据。")
except Exception as e:
    print(f"获取日线数据时发生错误: {e}")

# ## 4. 维持运行状态
# `xtdata.run()` 函数会阻塞当前线程，以持续接收和处理行情回调。
# 在实际应用中，如果你的程序有其他逻辑需要并行执行，可以考虑使用多线程或异步方式。
# 在教程中，我们使用 `run()` 来演示持续接收数据。
#
# **注意**: `run()` 会一直阻塞，直到程序被中断或连接断开。
# 为了演示效果，我们只运行一小段时间。

print("\n--- 阻塞线程接收行情回调 (运行10秒后自动停止) ---")
print("您将看到订阅的实时行情数据推送...")
print("注意：如果当前非交易时间，可能不会收到实时行情数据。")
try:
    # 在实际应用中，通常会直接调用 xtdata.run() 持续运行
    # 这里为了教程演示，我们模拟运行一段时间后停止
    xtdata.run() # 持续运行，直到被 stop_xtdata_run() 停止
    time.sleep(10) # 模拟运行10秒
except KeyboardInterrupt:
    print("\n用户中断。")
except Exception as e:
    print(f"xtdata.run() 发生错误: {e}")

# ## 5. 反订阅行情数据
# 当不再需要接收某个订阅的行情数据时，应使用 `xtdata.unsubscribe_quote` 进行反订阅，
# 释放资源。
#
# **参数说明**:
# - `seq`: 整数，订阅时返回的订阅号。

print("\n--- 反订阅行情数据 ---")
if subscribe_id_tick > 0:
    xtdata.unsubscribe_quote(subscribe_id_tick)
    print(f"已反订阅 600519.SH tick行情 (订阅号: {subscribe_id_tick})")
if subscribe_id_kline > 0:
    xtdata.unsubscribe_quote(subscribe_id_kline)
    print(f"已反订阅 000001.SZ 1分钟K线行情 (订阅号: {subscribe_id_kline})")

print("\n教程执行完毕。")