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
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | symbol | str | 是 | 股票代码(格式:代码.交易所) | "600519.SH" |
# | fields | str | 否 | 请求字段(逗号分隔,默认全部) | "open,high,low,close,volume" |

# ## HTTP调用方式
from xtquant import xtdata
import threading
import time

# ### xtdata库调用方式

# 定义数据推送回调函数
# 当订阅的全推行情数据有更新时，此函数会被调用
def on_full_tick_data(datas):
    """
    全推行情数据回调函数。
    datas: 字典，格式为 { stock_code : data }，其中data是最新分笔数据。
    """
    print(f"收到全推行情数据更新，时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}")
    for stock_code, data in datas.items():
        print(f"  合约代码: {stock_code}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}")

# 1. 订阅全推行情数据
# 使用 subscribe_whole_quote 订阅指定市场或合约的全推行情。
# 这里订阅沪深两市的所有合约的全推数据。
print("开始订阅沪深两市全推行情数据...")
# code_list 可以是市场代码列表，如 ['SH', 'SZ']，或合约代码列表，如 ['600519.SH', '000001.SZ']
# 订阅成功会返回一个订阅号 (seq)，失败返回 -1
subscribe_id = xtdata.subscribe_whole_quote(code_list=['SH', 'SZ'], callback=on_full_tick_data)

if subscribe_id != -1:
    print(f"全推行情订阅成功，订阅号: {subscribe_id}")
    # 2. 获取全推数据
    # 使用 get_full_tick 获取当前最新的全推数据快照。
    # 注意：get_full_tick 返回的是当前时刻的快照数据，不会触发回调。
    print("\n获取当前全推数据快照...")
    # code_list 参数与 subscribe_whole_quote 相同
    full_tick_data = xtdata.get_full_tick(code_list=['600519.SH', '000001.SZ'])
    
    if full_tick_data:
        print("成功获取全推数据快照:")
        for stock_code, data in full_tick_data.items():
            print(f"  合约代码: {stock_code}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}")
    else:
        print("未能获取全推数据快照，请确保MiniQmt已连接且有数据。")

    # 3. 阻塞线程以持续接收行情回调
    # xtdata.run() 会阻塞当前线程，使程序保持运行状态，以便持续接收订阅数据。
    # 在实际应用中，可以根据需要设置运行时间或通过其他方式控制程序的生命周期。
    print("\n程序将持续运行10秒以接收实时行情推送...")
    xtdata.run() # 这会阻塞直到程序被中断或连接断开
    time.sleep(10) # 模拟程序运行一段时间
    
    # 4. 反订阅行情数据
    # 使用 unsubscribe_quote 取消订阅，释放资源。
    print(f"\n反订阅全推行情数据，订阅号: {subscribe_id}...")
    xtdata.unsubscribe_quote(subscribe_id)
    print("反订阅成功。")
else:
    print("全推行情订阅失败，请检查xtdata连接和MiniQmt状态。")

# ### 实际应用场景
# **实时市场监控**：
# 订阅全推行情数据，实时监控整个市场的最新价格和成交量，用于高频交易策略或市场异动分析。
#
# ```python
# import xtdata
# import time
#
# # 定义回调函数，处理接收到的全推数据
# def on_market_update(datas):
#     for stock_code, data in datas.items():
#         # 打印关键行情信息，例如最新价、成交量
#         print(f"实时更新 - {stock_code}: 最新价={data.get('lastPrice')}, 成交量={data.get('volume')}")
#
# # 订阅沪深两市的全推行情
# # 传入市场代码列表 ['SH', 'SZ'] 表示订阅整个沪深市场
# subscribe_id_monitor = xtdata.subscribe_whole_quote(code_list=['SH', 'SZ'], callback=on_market_update)
#
# if subscribe_id_monitor != -1:
#     print(f"市场监控订阅成功，订阅号: {subscribe_id_monitor}")
#     # 持续运行以接收实时数据，例如运行30秒
#     print("开始实时监控市场行情，持续30秒...")
#     time.sleep(30)
#     # 取消订阅
#     xtdata.unsubscribe_quote(subscribe_id_monitor)
#     print("市场监控已停止。")
# else:
#     print("市场监控订阅失败。")
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
# 4. **压缩传输：启用gzip压缩减少网络传输量
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