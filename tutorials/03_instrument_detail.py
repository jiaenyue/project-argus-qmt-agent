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

# # 实时合约信息API 使用教程

# ### 参数说明
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值值 |
# |--------|------|----------|------|--------|
# | symbol | str | 是 | 股票代码(格式:代码.交易所) | "600519.SH" |

# ## HTTP调用方式
import requests
import os  # 添加os模块导入

# 从环境获取API服务地址，默认为localhost:8000
API_BASE_URL = os.environ.get('DATA_AGENT_SERVICE_URL', 'http://localhost:8000')

try:
    response = requests.get(
        f"{API_BASE_URL}/instrument_detail",  # 添加/api/v1前缀
        params={"symbol": "600519.SH"},
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
    simulated_data = {"data": {"symbol": "600519.SH", "name": "贵州茅台", "last_price": 1812.5, "change_percent": 1.2}}
    print("模拟数据:", simulated_data)
except ValueError as e:
    print(str(e))

# ### 实际应用场景
# **实时监控仪表盘**：
# 在实时监控系统中展示股票的基本信息，如最新价格、涨跌幅、市值等关键指标。
#
# ```python
# # 获取多只股票详情
# symbols = ["600519.SH", "000001.SZ", "00700.HK"]
# 
# for symbol in symbols:
#     response = requests.get(
#         f"{API_BASE_URL}/instrument_detail",  # 添加前缀
#         params={"symbol": symbol},
#         timeout=3  # 添加超时
#     )
#     
#     # 业务数据验证
#     response_data = response.json()
#     if response_data.get('success'):
#         detail = response_data['data']
#         print(f"{symbol} 最新价: {detail['last_price']} 涨跌幅: {detail['change_percent']}%")
#     else:
#         error_msg = response_data.get('error', '未知错误')
#         print(f"{symbol}: {error_msg}")
# ```

# ### 错误处理
# | 错误码 | 含义 | 解决方案 |
# |--------|------|----------|
# | 400 | 参数缺失或格式错误 | 检查symbol格式是否正确 |
# | 404 | 服务未找到 | 确认API服务是否正常运行 |
# | 500 | 服务器内部 | 检查服务日志排查问题 |
# | 1003 | 无效股票代码 | 使用正确的股票代码格式(代码.交易所) |
# | 1006 | 股票信息不存在 | 确认股票代码是否正确且已上市 |

# ### 性能优化建议
# 1. **批量查询**：使用批量查询接口减少请求次数
# 2. **缓存机制**：对不常变动的信息(如公司名称)进行本地缓存
# 3. **按需请求**：只请求需要的字段减少响应大小
# 4. **连接池复用**：保持HTTP连接复用减少握手开销

# ### FAQ常见问题
# **Q: 是否支持查询港股和美股？**  
# A: 支持，港股代码后缀.HK，美股代码后缀.US
#
# **Q: 返回的数据包含哪些字段？**  
# A: 包含股票代码、名称、最新价、涨跌幅、市值、PE等核心指标
#
# **Q: 如何获取历史合约信息？**  
# A: 当前API只返回实时数据，历史数据需使用其他服务

# ## 注意事项
# - 确保服务运行在data-agent-service
# - 需要指定正确的股票代码symbol