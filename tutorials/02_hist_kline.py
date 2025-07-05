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

# # 历史K线API 使用教程

# ### 参数说明
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | symbol | str | 是 | 股票代码(格式:代码.交易所) | "600519.SH" |
# | start_date | str | 是 | 开始日期(YYYYMMDD) | "20230101" |
# | end_date | str | 是 | 结束日期(YYYYMMDD) | "20231231" |
# | frequency | str | 是 | K线周期(1d-日线,1m-1分钟) | "1d" |

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

def fetch_kline_with_retry(params, max_retries=3, retry_delay=1):
    """带重试机制的K线数据获取函数"""
    for attempt in range(max_retries):
        try:
            # 检查API服务状态
            status_response = requests.get(f"{API_BASE_URL}/api/v1/status", timeout=1)
            if status_response.status_code != 200:
                raise ConnectionError(f"API服务不可用: HTTP {status_response.status_code}")
                
            # 发送主请求
            response = requests.get(
                f"{API_BASE_URL}/api/v1/hist_kline",
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
                error_code = data.get('error_code', '未知')
                error_msg = data.get('message', '未知错误')
                raise ValueError(f"API业务错误 {error_code}: {error_msg}")
                
        except (requests.exceptions.RequestException, ValueError, ConnectionError) as e:
            if attempt < max_retries - 1:
                print(f"尝试失败 ({attempt+1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                raise

# 主请求参数
params = {
    "symbol": "600519.SH",
    "start_date": "20230101",
    "end_date": "20231231",
    "frequency": "1d"
}

try:
    # 使用带重试的请求函数
    result = fetch_kline_with_retry(params)
    
    if result:
        print("调用成功，数据样例:", result['data'][0] if result['data'] else "空数据集")
    else:
        raise RuntimeError("所有重试均失败")
        
except Exception as e:
    print(f"错误: {e}")
    print("切换到模拟模式...")
    print("⚠️ 警告: 使用模拟数据替代")
    # 生成完整的模拟数据
    simulated_data = {
        "success": True,
        "data": [
            {"date": "20230103", "open": 180.0, "high": 182.5, "low": 179.5, "close": 181.2, "volume": 100000},
            {"date": "20230104", "open": 181.5, "high": 183.8, "low": 180.8, "close": 182.0, "volume": 120000},
            {"date": "20230105", "open": 182.5, "high": 184.0, "low": 181.0, "close": 183.5, "volume": 95000},
            {"date": "20230106", "open": 183.0, "high": 185.5, "low": 182.5, "close": 184.8, "volume": 110000},
            {"date": "20230109", "open": 184.5, "high": 186.0, "low": 183.8, "close": 185.2, "volume": 105000}
        ]
    }
    print("模拟数据样例:", simulated_data['data'][0])

# ### 实际应用场景
# **量化策略回测**：
# 获取历史K线数据是量化策略回测的基础。通过本API获取指定股票的历史价格数据，用于计算策略指标和回测收益。
#
# ```python
# # 获取贵州茅台2023年日K线
# params = {
#     "symbol": "600519.SH",
#     "start_date": "20230101",
#     "end_date": "20231231",
#     "frequency": "1d"
# }
# 
# # 使用带重试的请求函数
# result = fetch_kline_with_retry(params)
# if result:
#     kline_data = result['data']
#     # 计算20日移动平均线
#     close_prices = [bar['close'] for bar in kline_data]
#     ma20 = sum(close_prices[-20:]) / 20
# ```

# ### 错误处理
# | 错误码 | 含义 | 解决方案 |
# |--------|------|----------|
# | 400 | 参数缺失或格式错误 | 检查symbol/start_date/end_date/frequency格式 |
# | 404 | 服务未找到 | 确认API服务是否正常运行 |
# | 500 | 服务器内部错误 | 检查服务日志排查问题 |
# | 1003 | 无效股票代码 | 使用正确的股票代码格式(代码.交易所) |
# | 1004 | 无效K线周期 | 使用支持的周期(1d,1m,5m等) |
# | 1005 | 日期范围超过限制 | 减少请求的时间范围 |

# ### 性能优化建议
# 1. **分页获取**：对于长时间范围的数据，使用分页参数分段获取
# 2. **本地存储**：将获取的数据存储在本地数据库避免重复请求
# 3. **压缩传输**：启用gzip压缩减少网络传输量
# 4. **字段过滤**：只请求需要的字段减少响应大小

# ### FAQ常见问题
# **Q: 是否支持获取分钟级K线数据？**  
# A: 支持，设置frequency参数为1m(1分钟)/5m(5分钟)/15m(15分钟)等
#
# **Q: 最多可以获取多长时间的K线数据？**  
# A: 默认最多365天，如需更长时间请分段获取
#
# **Q: 是否支持同时获取多只股票的K线？**  
# A: 当前API仅支持单只股票查询，多股票需多次调用

# ## 注意事项
# - 确保服务运行在data-agent-service
# - 需要指定正确的参数：symbol, start_date, end_date, frequency