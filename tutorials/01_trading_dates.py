# -*- coding: utf-8 -*-
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

# # 交易日历API 使用教程

# ### 参数说明
# `xtdata.get_trading_dates` 函数用于获取指定市场在给定时间范围内的交易日列表。
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | market | str | 是 | 市场代码 (例如 "SH" - 上交所, "SZ" - 深交所) | "SH" |
# | start_time | str | 否 | 起始日期 (YYYYMMDD)。为空表示当前市场首个交易日时间。 | "20250101" |
# | end_time | str | 否 | 结束日期 (YYYYMMDD)。为空表示当前时间。 | "20250107" |
# | count | int | 否 | 数据个数。大于0时，若指定了start_time, end_time，则以end_time为基准向前取count条；若start_time, end_time缺省，默认取本地数据最新的count条数据；若start_time, end_time, count都缺省时，默认取本地全部数据。默认值为-1，表示返回全部。 | -1 |

# ## xtdata库调用方式
# 首先，我们需要导入 `xtdata` 库。
from xtquant import xtdata
import datetime

# 为了演示，我们获取最近的交易日。
# 注意：`xtdata` 库需要连接到MiniQmt以获取数据。请确保MiniQmt已正确运行并连接到行情服务器。

# 获取指定市场和日期范围的交易日历
# 示例：获取上海证券交易所2025年1月1日至2025年1月7日的交易日
market_code = "SH"
start_date_str = "20250101"
end_date_str = "20250107"

print(f"尝试获取 {market_code} 市场从 {start_date_str} 到 {end_date_str} 的交易日...")

try:
    # 调用xtdata.get_trading_dates函数
    trading_dates = xtdata.get_trading_dates(
        market=market_code,
        start_time=start_date_str,
        end_time=end_date_str
    )
    print(f"获取到的交易日列表 ({market_code}): {trading_dates}")

    # 进一步示例：获取最近5个交易日
    print("\n尝试获取最近5个交易日...")
    recent_trading_dates = xtdata.get_trading_dates(
        market=market_code,
        count=5 # 使用count参数获取最近的交易日
    )
    print(f"最近5个交易日列表 ({market_code}): {recent_trading_dates}")
except Exception as e:
    print(f"调用xtdata.get_trading_dates失败: {e}")
    print("请确保MiniQmt已正确运行并连接到行情服务器，且数据服务可用。")
# ## 实际应用场景
# ### 回测系统日期验证
# 在量化回测中，需要验证策略在交易日和非交易日的执行情况。通过 `xtdata.get_trading_dates` API 获取指定时间段的交易日历，用于回测引擎的日期过滤。

# 示例：获取2025年第一季度的交易日历
try:
    q1_start = "20250101"
    q1_end = "20250331"
    print(f"\n获取 {market_code} 市场2025年第一季度 ({q1_start} - {q1_end}) 的交易日历...")
    q1_trading_dates = xtdata.get_trading_dates(
        market=market_code,
        start_time=q1_start,
        end_time=q1_end
    )
    print(f"2025年第一季度交易日数量: {len(q1_trading_dates)}")
    print(f"部分交易日: {q1_trading_dates[:5]} ... {q1_trading_dates[-5:]}")

    # 模拟在回测引擎中使用交易日
    def run_backtest(date):
        """模拟回测函数"""
        # print(f"在 {date} 执行回测逻辑...")
        pass

    print("\n模拟在回测引擎中遍历交易日...")
    for date in q1_trading_dates:
        run_backtest(date)
    print("回测日历遍历完成。")
except Exception as e:
    print(f"回测场景演示失败: {e}")

# ## 错误处理与注意事项
# 当调用 `xtdata` 库函数时，如果遇到错误，通常会抛出Python异常。
# 常见的错误原因可能包括：
# - **MiniQmt未运行或连接失败**：`xtdata` 依赖于MiniQmt提供数据服务。
# - **参数错误**：传入的 `market` 代码不正确，或者日期格式不符合 `YYYYMMDD`。
# - **数据服务问题**：MiniQmt连接的行情服务器数据源未更新或不可用。

# **解决方案**：
# 1. 确保MiniQmt客户端已启动并登录。
# 2. 检查MiniQmt的行情连接状态，确保数据源正常。
# 3. 仔细核对 `get_trading_dates` 函数的参数，确保 `market` 代码（如"SH", "SZ"）和日期格式（`YYYYMMDD`）正确无误。
# 4. 对于日期范围，确保 `start_time` 不晚于 `end_time`。

# `xtdata` 库的 `get_trading_dates` 函数返回的是一个日期字符串列表，例如 `['20250102', '20250103', '20250106']`。
# 该函数只返回交易日，不会包含节假日或周末。
