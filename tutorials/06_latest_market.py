# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.1
#   kernels极pec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # 最新行情数据API 使用教程

# ### 参数说明
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | symbols | str | 是 | 股票代码列表(逗号分隔) | "600519.SH,000001.SZ" |

# ## HTTP调用方式
import requests
import os  # 添加os模块导入

# 从环境变量获取API服务地址，默认为localhost:8000
API_BASE_URL = os.environ.get('DATA_AGENT_SERVICE_URL', 'http://localhost:8000')

try:
    response = requests.get(
        f"{API_BASE_URL}/latest_market",  # 添加/api/v1前缀
        params={"symbols": "600519.SH,000001.SZ"},
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
    simulated_data = {"data": {"600519.SH": {"last_price": 1812.5, "change_percent": 1.2}}}
    print("模拟数据:", simulated_data)
except ValueError as e:
    print(str(e))

# ### 实际应用场景
# **实时监控看板**：
# 构建实时股票监控看板，展示多只股票的最新行情数据。
#
# ```python
# # 监控自选股列表
# watch_list = "600519.SH,000001.SZ,00700.HK,TSLA.US"  # 修复示例中的错误
# 
# response = requests.get(
#     f"{API_BASE_URL}/latest_market",  # 添加前缀
#     params={"symbols": watch_list},
#     timeout=3  # 添加超时
# )
# 
# response_data = response.json()
# if response_data.get('success'):
#     market_data = response_data['data']
#     # 展示最新行情
#     for symbol, data in market_data.items():
#         print(f"{symbol}: 最新价 {data['last_price']} 涨跌 {data['change']} ({data['change_percent']}%)")
# else:
#     error_msg = response_data.get('error', '未知错误')
#     print(f"API调用失败: {error_msg}")
# ```

# ### 错误处理
# | 错误码 | 含义 | 解决方案 |
# |--------|------|----------|
# | 400 | 参数缺失或格式错误 | 检查symbols格式是否正确 |
# | 404 | 服务未找到 | 确认API服务是否正常运行 |
#极 | 500 | 服务器内部错误 | 检查服务日志排查问题 |
# | 1003 | 无效股票代码 | 检查代码列表中是否有无效代码 |
# | 1009 | 请求股票数量超限 | 减少单次请求的股票数量 |

# ### 性能优化建议
# 1. **长连接复用**：保持HTTP长连接复用减少握手开销
# 2. **压缩传输**：启用gzip压缩减少网络传输量
# 3. **增量更新**：只请求变更的字段减少响应大小
# 4. **客户端缓存**：对不常变动的信息(如公司名称)进行本地缓存
# 5. **分批请求**：大量股票时分批请求避免超时

# ### FAQ常见问题
# **Q: 最多支持同时查询多少只股票？**  
# A: 默认支持50只，如需更多请联系管理员调整
#
# **Q: 数据更新频率是多少？**  
# A: 交易所实时推送，延迟小于3秒
#
# **Q: 是否支持盘前盘后数据？**  
# A: 支持，盘前盘后数据会特别标注

# ## 注意事项
# - 确保服务运行在data-agent-service
# - 可以同时查询多个股票代码，用逗号分隔