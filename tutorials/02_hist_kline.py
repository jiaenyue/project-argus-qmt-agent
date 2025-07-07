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
from xtquant import xtdata
import pandas as pd

# ## xtdata库调用方式

# 主请求参数
stock_list = ["600519.SH"]
start_time = "20250630" # 尝试获取上周的数据
end_time = "20250704"   # 尝试获取上周的数据
period = "1d"

try:
    # 尝试下载历史数据，确保数据可用
    print(f"正在下载 {stock_list[0]} 从 {start_time} 到 {end_time} 的 {period} K线数据...")
    xtdata.download_history_data(
        stock_list[0],
        period,
        start_time=start_time,
        end_time=end_time
    )
    print("数据下载完成。")

    # 使用xtdata库获取K线数据
    kline_data = xtdata.get_market_data(
        stock_list=stock_list,
        period=period,
        start_time=start_time,
        end_time=end_time,
        field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
    )
    
    print(f"获取到的kline_data类型: {type(kline_data)}")
    if isinstance(kline_data, dict) and kline_data: # 检查是否为非空字典
        print(f"kline_data的键: {kline_data.keys()}")
        # 检查每个字段的DataFrame是否包含目标股票的数据且不为空
        all_fields_present_and_not_empty = True
        for field in ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']:
            if field not in kline_data or kline_data[field].empty or stock_list[0] not in kline_data[field].index:
                all_fields_present_and_not_empty = False
                print(f"字段 '{field}' 的数据缺失或为空，或股票 '{stock_list[0]}' 的数据在字段 '{field}' 中缺失。")
                break
        
        if all_fields_present_and_not_empty:
            print("调用成功，数据样例:")
            first_stock_code = stock_list[0]
            # 获取实际数据中的第一个日期作为示例
            # 假设所有字段的DataFrame都有相同的日期列
            if not kline_data['open'].empty and not kline_data['open'].columns.empty:
                example_date = kline_data['open'].columns[0] # 获取第一个日期
                print(f"示例日期: {example_date}")

                print(f"股票 {first_stock_code} 在 {example_date} 的开盘价: {kline_data['open'][example_date][first_stock_code]}")
                print(f"股票 {first_stock_code} 在 {example_date} 的收盘价: {kline_data['close'][example_date][first_stock_code]}")
                print(f"股票 {first_stock_code} 在 {example_date} 的最高价: {kline_data['high'][example_date][first_stock_code]}")
                print(f"股票 {first_stock_code} 在 {example_date} 的最低价: {kline_data['low'][example_date][first_stock_code]}")
                print(f"股票 {first_stock_code} 在 {example_date} 的成交量: {kline_data['volume'][example_date][first_stock_code]}")
                print(f"股票 {first_stock_code} 在 {example_date} 的成交额: {kline_data['amount'][example_date][first_stock_code]}")
                print(f"股票 {first_stock_code} 在 {example_date} 的时间戳: {kline_data['time'][example_date][first_stock_code]}")
            else:
                print("开盘价数据为空或没有日期列，无法获取示例数据。")
        else:
            print("未获取到完整数据或数据为空。")
    else:
        print("kline_data不是预期的非空字典类型。")
except Exception as e:
    print(f"获取数据失败: {e}")
    print("请确保MiniQmt已运行并连接成功，且数据权限正常。")

# ### 实际应用场景
# **量化策略回测**：
# 获取历史K线数据是量化策略回测的基础。通过xtdata库获取指定股票的历史价格数据，用于计算策略指标和回测收益。
#
# ```python
# # 获取贵州茅台2023年日K线
# stock_list = ["600519.SH"]
# start_time = "20230101"
# end_time = "20231231"
# period = "1d"
#
# kline_data = xtdata.get_market_data(
#     stock_list=stock_list,
#     period=period,
#     start_time=start_time,
#     end_time=end_time,
#     field_list=['close'] # 只获取收盘价用于计算均线
# )
#
# if kline_data and stock_list[0] in kline_data['close'] and not kline_data['close'].empty:
#     close_prices = kline_data['close'][stock_list[0]].tolist()
#     # 计算20日移动平均线
#     if len(close_prices) >= 20:
#         ma20 = sum(close_prices[-20:]) / 20
#         print(f"贵州茅台20日移动平均线: {ma20}")
#     else:
#         print("数据不足20条，无法计算20日移动平均线。")
# else:
#     print("未获取到K线数据，无法计算移动平均线。")
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