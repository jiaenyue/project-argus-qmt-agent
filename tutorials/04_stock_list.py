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

# # 板块股票列表API 使用教程

# ### 参数说明
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | sector | str | 是 | 板块名称(沪深A股/科创板/创业板等) | "沪深A股" |

# ## HTTP调用方式
import requests
import os  # 添加os模块导入

# 从环境变量获取API服务地址，默认为localhost:8000
API_BASE_URL = os.environ.get('DATA_AGENT_SERVICE_URL', 'http://localhost:8000')

try:
    response = requests.get(
        f"{API_BASE_URL}/stock_list",  # 添加/api/v1前缀
        params={"sector": "沪深A股"},
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
    simulated_data = {"data": [{"symbol": "600519.SH", "name": "贵州茅台"}, {"symbol": "000001.SZ", "name": "平安银行"}]}
    print("模拟数据:", simulated_data)
except ValueError as e:
    print(str(e))

# ### 实际应用场景
# **板块轮动监控**：
# 监控特定板块内所有股票的实时表现，用于板块轮动策略的执行。
#
# ```python
# # 获取科创板所有股票列表
# response = requests.get(
#     f"{API_BASE_URL}/stock_list",  # 添加前缀
#     params={"sector": "科创板"},
#     timeout=3  # 添加超时
# )
# 
# response_data = response.json()
# if response_data.get('success'):
#     stocks = response_data['data']
#     # 监控板块内股票表现
#     for stock in stocks:
#         symbol = stock['symbol']
#         # 获取实时行情并分析
#         quote = get_realtime_quote(symbol)
#         analyze_performance(quote)
# else:
#     error_msg = response_data.get('error', '未知错误')
#     print(f"API调用失败: {error_msg}")
# ```

# ### 错误处理
# | 错误码 | 含义 | 解决方案 |
# |--------|------|----------|
# | 400 | 参数缺失或格式错误 | 检查sector参数格式 |
# | 404 | 服务未找到 | 确认API服务是否正常运行 |
# | 500 | 服务器内部错误 | 检查服务日志排查问题 |
# | 1007 | 无效板块名称 | 使用支持的板块名称(沪深A股/科创板/创业板等) |
# | 1008 | 板块数据未更新 | 联系管理员更新板块数据 |

# ### 性能优化建议
# 1. **缓存结果**：板块股票列表变化不频繁，可缓存结果有效期为1天
# 2. **增量更新**：只请求变更的股票列表减少数据传输
# 3. **压缩传输**：启用gzip压缩减少网络传输量
# 4. **客户端过滤**：获取完整列表后在客户端按需过滤

# ### FAQ常见问题
# **Q: 支持哪些板块类型？**  
# A: 支持沪深A股、科创板、创业板、沪深300、中证500等主要板块
#
# **Q: 返回的股票列表包含哪些信息？**  
# A: 包含股票代码、名称、所属交易所等基本信息
#
# **Q: 如何获取自定义板块的股票列表？**  
# A: 当前API仅支持预定义板块，自定义板块需使用其他服务

# ## 注意事项
# - 确保服务运行在data-agent-service
# - 需要指定正确的板块名称sector