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

# # 完整行情数据API 使用教程

# ### 参数说明
# | 参数名 | 类型 | 是否必填 | 极明 | 示例值 |
# |--------|------|----------|------|--------|
# | symbol | str | 是 | 股票代码(格式:代码.交易所) | "600519.SH" |
# | fields | str | 否 | 请求字段(逗号分隔,默认全部) | "open,high,low,close,volume" |

# ## HTTP调用方式
import requests
import os  # 添加os模块导入

# 从环境变量获取API服务地址，默认为localhost:8000
API_BASE_URL = os.environ.get('DATA_AGENT_SERVICE_URL', 'http://localhost:8000')

try:
    response = requests.get(
        f"{API_BASE_URL}/full_market",  # 添加/api/v1前缀
        params={"symbol": "600519.SH", "fields": "open,high,low,close,volume"},
        timeout=3  # 添加3秒超时
    )
    response.raise_for_status()  # 检查HTTP错误
    
    response_data = response.json()
    
    # 检查API返回的成功标志
    if response_data.get('success'):
        data = response_data['data']
        print("调用结果：", data)
    else:
        error_msg = response_data.get('error', '未知错误')
        raise ValueError(f"API调用失败: {error_msg}")
        
except requests.exceptions.RequestException as e:
    print(f"网络请求错误: {str(e)}")
    print("切换到模拟模式...")
    # 模拟数据示例
    simulated_data = {"data": [{"date": "20230103", "open": 180.0, "high": 182.5, "low": 179.5, "close": 181.2}]}
    print("模拟数据:", simulated_data)
except ValueError as e:
    print(str(e))

# ### 实际应用场景
# **深度行情分析**：
# 获取股票的完整行情数据用于深度技术分析和策略决策。
#
# ```python
# # 获取贵州茅台完整行情数据
# response = requests.get(
#     f"{API_BASE_URL}/full_market",  # 添加前缀
#     params={"symbol": "600519.SH", "fields": "open,high,low,close,volume,amount,pe,pb"},
#     timeout=3  # 添加超时
# )
# 
# response_data = response.json()
# if response_data.get('success'):
#     full_data = response_data['data']
#     # 计算技术指标
#     close_prices = [day['close'] for day in full_data]
#     rsi = calculate_rsi(close_prices)
#     print(f"RSI指标: {rsi[-1]:.2f}")
# else:
#     error_msg = response_data.get('error', '未知错误')
#     print(f"API调用失败: {error_msg}")
# ```

# ### 错误处理
# | 错误码 | 含义 | 解决方案 |
# |--------|------|----------|
# | 400 | 参数缺失或格式错误 | 检查symbol/fields格式 |
# | 404 | 服务未找到 | 确认API服务是否正常运行 |
# | 500 | 服务器内部错误 | 检查服务日志排查问题 |
# | 1003 | 无效股票代码 | 使用正确的股票代码格式(代码.交易所) |
# | 1010 | 无效字段名 | 检查字段名是否在支持列表中 |

# ### 性能优化建议
# 1. **按需请求**：只请求需要的字段减少响应大小
# 2. **分页获取**：历史数据量过大时分页获取
# 3. **本地缓存**：对历史数据进行本地存储避免重复请求
# 4. **压缩传输极：启用gzip压缩减少网络传输量
# 5. **增量更新**：只获取最新变更数据减少传输量

# ### FAQ常见问题
# **Q: 支持哪些字段？**  
# A: 支持open,high,low,close,volume,amount,turnover,pe,pb等常用字段
#
# **Q: 是否支持获取多个股票的完整数据？**  
# A: 当前API只支持单只股票查询，多股票需多次调用
#
# **Q: 数据更新频率是多少？**  
# A: 日线数据每日收盘后更新，分钟线数据实时更新

# ## 注意事项
# - 确保服务运行在data-agent-service
# - 需要指定股票代码symbol和要获取的字段fields