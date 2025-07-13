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

# # 历史K线API 使用教程 (FastAPI)

# ### 参数说明
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | symbol | str | 是 | 股票代码(格式:代码.交易所) | "600519.SH" |
# | start_date | str | 是 | 开始日期(YYYYMMDD) | "20230101" |
# | end_date | str | 是 | 结束日期(YYYYMMDD) | "20231231" |
# | frequency | str | 是 | K线周期(1d-日线,1m-1分钟) | "1d" |

# ## HTTP调用方式
import requests
import pandas as pd

# FastAPI服务的地址
BASE_URL = "http://127.0.0.1:8000"

# 主请求参数
stock_code = "600519.SH"
start_date = "20250630"
end_date = "20250704"
period = "1d"

try:
    print(f"正在从API获取 {stock_code} 从 {start_date} 到 {end_date} 的 {period} K线数据...")

    response = requests.get(
        f"{BASE_URL}/api/v1/hist_kline",
        params={
            "symbol": stock_code,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": period,
        }
    )
    response.raise_for_status()

    kline_data = response.json()
    if kline_data:
        df = pd.DataFrame(kline_data)
        print("调用成功，数据样例:")
        print(df.head())
    else:
        print("未获取到K线数据。")

except requests.exceptions.RequestException as e:
    print(f"获取数据失败: {e}")
    print("请确保data_agent_service已运行并连接成功。")

# ### 实际应用场景
# **量化策略回测**：
# 获取历史K线数据是量化策略回测的基础。通过API获取指定股票的历史价格数据，用于计算策略指标和回测收益。
#
# ```python
# # 获取贵州茅台2023年日K线
# stock_code = "600519.SH"
# start_date = "20230101"
# end_date = "20231231"
# period = "1d"
#
# response = requests.get(
#     f"{BASE_URL}/api/v1/hist_kline",
#     params={
#         "symbol": stock_code,
#         "start_date": start_date,
#         "end_date": end_date,
#         "frequency": period,
#     }
# )
#
# if response.status_code == 200:
#     kline_data = response.json()
#     if kline_data:
#         df = pd.DataFrame(kline_data)
#         close_prices = df['close'].tolist()
#         # 计算20日移动平均线
#         if len(close_prices) >= 20:
#             ma20 = sum(close_prices[-20:]) / 20
#             print(f"贵州茅台20日移动平均线: {ma20}")
#         else:
#             print("数据不足20条，无法计算20日移动平均线。")
#     else:
#         print("未获取到K线数据，无法计算移动平均线。")

# ### 错误处理
# | 错误码 | 含义 | 解决方案 |
# |--------|------|----------|
# | 400 | 参数缺失或格式错误 | 检查symbol/start_date/end_date/frequency格式 |
# | 404 | 服务未找到 | 确认API服务是否正常运行 |
# | 500 | 服务器内部错误 | 检查服务日志排查问题 |

# ### 性能优化建议
# 1. **本地存储**：将获取的数据存储在本地数据库避免重复请求
# 2. **压缩传输**：启用gzip压缩减少网络传输量

# ### FAQ常见问题
# **Q: 是否支持获取分钟级K线数据？**
# A: 支持，设置frequency参数为1m(1分钟)/5m(5分钟)/15m(15分钟)等
#
# **Q: 最多可以获取多长时间的K线数据？**
# A: 请参考xtdata的限制，如需更长时间请分段获取
#
# **Q: 是否支持同时获取多只股票的K线？**
# A: 当前API仅支持单只股票查询，多股票需多次调用

# ## 注意事项
# - 确保服务运行在data-agent-service
# - 需要指定正确的参数：symbol, start_date, end_date, frequency
