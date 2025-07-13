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

# # 交易日历API 使用教程 (FastAPI)

# 本教程演示如何通过FastAPI数据服务获取交易日历。

# ## API调用方式
# 我们将使用 `requests` 库来调用在 `data_agent_service` 中定义的API。
import requests
import json

# FastAPI服务的地址
BASE_URL = "http://127.0.0.1:8000"

# 获取指定市场和日期范围的交易日历
# 示例：获取上海证券交易所2025年1月1日至2025年1月7日的交易日
market_code = "SH"
start_date_str = "20250101"
end_date_str = "20250107"

print(f"尝试从API获取 {market_code} 市场从 {start_date_str} 到 {end_date_str} 的交易日...")

try:
    # 调用FastAPI-get_trading_dates接口
    response = requests.get(
        f"{BASE_URL}/api/v1/get_trading_dates",
        params={
            "market": market_code,
            "start_date": start_date_str,
            "end_date": end_date_str,
        }
    )
    response.raise_for_status()  # 如果请求失败，则抛出HTTPError错误

    # 解析JSON响应
    trading_dates = response.json()
    print(f"从API获取到的交易日列表 ({market_code}): {trading_dates}")

except requests.exceptions.RequestException as e:
    print(f"调用API失败: {e}")
    print("请确保 data_agent_service 已在后台运行。")

# ## 实际应用场景
# ### 回测系统日期验证
# 与 `xtdata` 版本类似，此API可用于在量化回测中验证交易日。

# 示例：获取2025年第一季度的交易日历
try:
    q1_start = "20250101"
    q1_end = "20250331"
    print(f"\n从API获取 {market_code} 市场2025年第一季度 ({q1_start} - {q1_end}) 的交易日历...")

    response = requests.get(
        f"{BASE_URL}/api/v1/get_trading_dates",
        params={
            "market": market_code,
            "start_date": q1_start,
            "end_date": q1_end,
        }
    )
    response.raise_for_status()

    q1_trading_dates = response.json()
    print(f"2025年第一季度交易日数量: {len(q1_trading_dates)}")
    print(f"部分交易日: {q1_trading_dates[:5]} ... {q1_trading_dates[-5:]}")

except requests.exceptions.RequestException as e:
    print(f"调用API失败: {e}")
    print("请确保 a_agent_service 已在后台运行。")

# ## 实际应用场景
# ### 回测系统日期验证
# 与 `xtdata` 版本类似，此API可用于在量化回测中验证交易日。

# 示例：获取2025年第一季度的交易日历
try:
    q1_start = "20250101"
    q1_end = "20250331"
    print(f"\n从API获取 {market_code} 市场2025年第一季度 ({q1_start} - {q1_end}) 的交易日历...")

    response = requests.get(
        f"{BASE_URL}/api/v1/get_trading_dates",
        params={
            "market": market_code,
            "start_date": q1_start,
            "end_date": q1_end,
        }
    )
    response.raise_for_status()

    q1_trading_dates = response.json()
    print(f"2025年第一季度交易日数量: {len(q1_trading_dates)}")
    print(f"部分交易日: {q1_trading_dates[:5]} ... {q1_trading_dates[-5:]}")

except requests.exceptions.RequestException as e:
    print(f"回测场景演示失败: {e}")

# ## 错误处理与注意事项
# 当调用API时，需要处理几种常见的错误：
# - **服务未运行**：如果 `data_agent_service` 未启动，`requests` 将抛出 `ConnectionError`。
# - **请求参数错误**：如果API的必需参数（如 `market`）缺失，服务器可能返回4xx错误。
# - **服务器内部错误**：如果服务器在处理请求时遇到问题，可能会返回5xx错误。

# **解决方案**：
# 1. 确保在运行此脚本之前，已通过 `python data_agent_service/main.py` 启动了FastAPI服务。
# 2. 检查API的URL和参数是否正确。
# 3. 使用 `try...except` 块捕获潜在的 `requests.exceptions.RequestException` 异常。
