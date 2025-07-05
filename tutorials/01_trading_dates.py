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
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | market | str | 是 | 交易所代码(SH-上交所,SZ-深交所) | "SH" |
# | start_date | str | 是 | 开始日期(YYYYMMDD) | "20250101" |
# | end_date | str | 是 | 结束日期(YYYYMMDD) | "20250107" |

# ## HTTP调用方式
import requests
import os
import time
import socket

def find_available_port():
    """动态检测可用端口"""
    for port in [8000, 58610, 8001]:
        try:
            with socket.socket() as s:
                s.settimeout(1)
                s.connect(("localhost", port))
                return port
        except:
            continue
    return None

# 动态获取API服务地址
if 'DATA_AGENT_SERVICE_URL' in os.environ:
    API_BASE_URL = os.environ['DATA_AGENT_SERVICE_URL']
else:
    detected_port = find_available_port()
    API_BASE_URL = f"http://localhost:{detected_port}" if detected_port else 'http://localhost:8000'
    print(f"⚠️ 使用动态检测的API地址: {API_BASE_URL}")

def fetch_trading_dates_with_retry(params, max_retries=3, retry_delay=1):
    """带重试机制的交易日历获取函数"""
    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/v1/get_trading_dates",
                params=params,
                timeout=3
            )
            response.raise_for_status()
            
            # 业务数据验证
            data = response.json()
            if 'success' in data and data['success']:
                if 'data' in data:
                    return data
                else:
                    raise ValueError("API响应缺少'data'字段")
            else:
                error_msg = data.get('error', '未知错误')
                raise ValueError(f"API业务错误: {error_msg}")
                
        except (requests.exceptions.RequestException, ValueError) as e:
            if attempt < max_retries - 1:
                print(f"尝试失败 ({attempt+1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                raise

# 主请求参数
params = {
    "market": "SH",
    "start_date": "20250101",
    "end_date": "20250107"
}

try:
    # 使用带重试的请求函数
    result = fetch_trading_dates_with_retry(params)
    print("调用结果：", result['data'])
    
except Exception as e:
    print(f"错误: {e}")
    print("切换到模拟模式...")
    # 生成完整的模拟数据
    simulated_data = {
        "success": True,
        "data": ["20250102", "20250103", "20250106"]
    }
    print("模拟数据:", simulated_data['data'])

# ## MCP调用方式
import asyncio
import nest_asyncio
nest_asyncio.apply()

try:
    from src.xtquantai.server import MCPClient
except ImportError:
    print("警告：未找到本地MCPClient实现")
    class MCPClient:
        def __init__(self, host, port):
            print(f"模拟MCP客户端: {host}:{port}")

        async def call(self, method, **params):
            return {"status": "success", "method": method, "params": params}

async def main():
    try:
        client = MCPClient("localhost", 8000)
        result = await client.call("get_trading_dates", market="SH", start_date="20250101", end_date="20250107")
        print("调用结果：", result)
    except Exception as e:
        print(f"MCP调用失败: {e}")
        print("切换到模拟模式...")
        simulated_result = {"status": "success", "data": ["20250102", "20250103", "20250106"]}
        print("模拟数据:", simulated_result)

asyncio.run(main())





# ### 实际应用场景
# **回测系统日期验证**：
# 在量化回测中，需要验证策略在交易日和非交易日的执行情况。通过本API获取指定时间段的交易日历，用于回测引擎的日期过滤。
#
# ```python
# # 获取2025年Q1交易日历
# response = requests.get(
#     f"{API_BASE_URL}/api/v1/get_trading_dates",
#     params={"market": "SH", "start_date": "20250101", "end_date": "20250331"},
#     timeout=3
# )
# 
# # 业务数据验证
# data = response.json()
# if 'data' not in data:
#     raise ValueError("API响应缺少'data'字段")
#     
# trading_dates = data['data']
#
# # 在回测引擎中使用
# for date in trading_dates:
#     run_backtest(date)
# ```

# ### 错误处理
# | 错误码 | 含义 | 解决方案 |
# |--------|------|----------|
# | 400 | 参数缺失或格式错误 | 检查market/start_date/end_date参数格式 |
# | 404 | 服务未找到 | 确认API服务是否正常运行 |
# | 500 | 服务器内部错误 | 检查服务日志排查问题 |
# | 1001 | 无效交易所代码 | 使用有效的交易所代码(SH/SZ) |
# | 1002 | 日期范围不合法 | 确保start_date ≤ end_date |

# ### 性能优化建议
# 1. **客户端缓存**：交易日历数据变化频率低，可在客户端缓存结果，有效期为1天
# 2. **批量请求**：避免频繁调用，一次性获取较长时间范围的数据
# 3. **压缩传输**：启用gzip压缩减少网络传输量

# ### FAQ常见问题
# **Q: 为什么返回的交易日历包含非交易日？**  
# A: 本API只返回交易日，确保参数中的market值正确且服务数据源已更新
#
# **Q: 如何获取国际市场的交易日历？**  
# A: 当前API仅支持中国A股市场(SH/SZ)，国际交易日历需使用其他服务
#
# **Q: 日期格式是否支持YYYY-MM-DD？**  
# A: 仅支持YYYYMMDD格式，需去除分隔符

# ## 注意事项
# - 确保服务运行在localhost:8000
# - MCP客户端需要预先配置
