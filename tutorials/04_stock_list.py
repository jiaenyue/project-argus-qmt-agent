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

# 本教程演示如何使用 `xtdata` 库获取板块分类信息和板块内的股票列表。
# `xtdata` 库是 `xtquant` 的行情模块，提供精简直接的数据，满足量化交易者的数据需求。

# ## 导入 `xtdata` 库
# 首先，我们需要导入 `xtdata` 库。
from xtquant import xtdata
import datetime

# ## 下载板块分类信息
# 在获取板块列表或板块成分股之前，需要先下载板块分类信息。
# `download_sector_data()` 函数用于下载板块分类信息，它是一个同步执行的函数，下载完成后返回。
print("开始下载板块分类信息...")
xtdata.download_sector_data()
print("板块分类信息下载完成。")

# ## 获取板块列表
# `get_sector_list()` 函数用于获取所有可用的板块列表。
# 返回值是一个包含板块名称的列表。
print("\n获取所有板块列表:")
sector_list = xtdata.get_sector_list()
if sector_list:
    print(f"可用板块数量: {len(sector_list)}")
    print("前20个板块示例:")
    for i, sector in enumerate(sector_list[:20]): # 打印前20个板块作为示例
        print(f"  {i+1}. {sector}")
    if len(sector_list) > 20:
        print(f"  ... (共 {len(sector_list)} 个板块)")
else:
    print("未获取到任何板块信息，请检查数据是否已正确下载。")

# ## 获取板块成分股列表
# `get_stock_list_in_sector(sector_name, real_timetag)` 函数用于获取指定板块的成分股列表。
# 参数说明：
# - `sector_name`: 字符串，板块名称，例如 "沪深A股", "科创板", "创业板" 等。
# - `real_timetag`: 可选参数，时间戳（毫秒）或日期字符串（'YYYYMMDD'）。
#   如果缺省，则获取最新的成分股列表；如果指定，则获取对应时间的历史成分股列表。

# ### 示例1: 获取“沪深A股”的最新成分股列表
print("\n获取“沪深A股”的最新成分股列表:")
a_shares_stocks = xtdata.get_stock_list_in_sector("沪深A股")
if a_shares_stocks:
    print(f"“沪深A股”成分股数量: {len(a_shares_stocks)}")
    print("前20个“沪深A股”成分股示例:")
    for i, stock in enumerate(a_shares_stocks[:20]): # 打印前20个股票作为示例
        print(f"  {i+1}. {stock}")
    if len(a_shares_stocks) > 20:
        print(f"  ... (共 {len(a_shares_stocks)} 个成分股)")
else:
    print("未获取到“沪深A股”成分股列表，请检查板块名称或数据。")

# ### 示例2: 获取“科创板”的最新成分股列表
print("\n获取“科创板”的最新成分股列表:")
kcb_stocks = xtdata.get_stock_list_in_sector("科创板")
if kcb_stocks:
    print(f"“科创板”成分股数量: {len(kcb_stocks)}")
    print("前20个“科创板”成分股示例:")
    for i, stock in enumerate(kcb_stocks[:20]): # 打印前20个股票作为示例
        print(f"  {i+1}. {stock}")
    if len(kcb_stocks) > 20:
        print(f"  ... (共 {len(kcb_stocks)} 个成分股)")
else:
    print("未获取到“科创板”成分股列表，请检查板块名称或数据。")

# ### 示例3: 获取指定日期“沪深300”的历史成分股列表
# 假设我们要获取2023年1月1日的“沪深300”成分股列表。
# 注意：`real_timetag` 参数可以是日期字符串 'YYYYMMDD' 或毫秒时间戳。
# 如果该日期没有数据，可能会返回空列表。
target_date = '20230101'
print(f"\n获取{target_date}“沪深300”的历史成分股列表:")
hs300_stocks_hist = xtdata.get_stock_list_in_sector("沪深300", real_timetag=target_date)
if hs300_stocks_hist:
    print(f"{target_date}“沪深300”成分股数量: {len(hs300_stocks_hist)}")
    print(f"前20个{target_date}“沪深300”成分股示例:")
    for i, stock in enumerate(hs300_stocks_hist[:20]): # 打印前20个股票作为示例
        print(f"  {i+1}. {stock}")
    if len(hs300_stocks_hist) > 20:
        print(f"  ... (共 {len(hs300_stocks_hist)} 个成分股)")
else:
    print(f"未获取到{target_date}“沪深300”的历史成分股列表，可能该日期无数据或板块不存在。")

# ## 实际应用场景
# **板块轮动监控**：
# 监控特定板块内所有股票的实时表现，用于板块轮动策略的执行。
# 以下是一个概念性示例，实际应用中需要结合实时行情数据获取和分析逻辑。
#
# ```python
# # 假设我们已经下载了板块数据
# # xtdata.download_sector_data()
#
# # 获取“创业板”所有股票列表
# cyb_stocks = xtdata.get_stock_list_in_sector("创业板")
#
# if cyb_stocks:
#     print(f"\n开始监控“创业板”股票表现 (概念性示例):")
#     for stock_code in cyb_stocks[:3]: # 仅演示前3只股票
#         print(f"正在分析股票: {stock_code}")
#         # 实际应用中，这里会调用xtdata.get_market_data 或订阅实时行情
#         # 例如：
#         # quote_data = xtdata.get_market_data(stock_list=[stock_code], period='tick', count=1)
#         # if quote_data and stock_code in quote_data.get('lastPrice', {}):
#         #     print(f"  {stock_code} 最新价: {quote_data['lastPrice'][stock_code].iloc[-1]}")
#         # else:
#         #     print(f"  未能获取 {stock_code} 的实时行情。")
# else:
#     print("\n未能获取“创业板”成分股列表，无法进行板块轮动监控。")
# ```

# ## 注意事项
# - 确保 `xtdata` 库已正确安装并能连接到行情服务。
# - `download_sector_data()` 仅需不频繁调用，例如每日或每周更新一次，因为板块数据变化不频繁。
# - `get_stock_list_in_sector` 返回的股票代码格式为 `代码.市场` (例如 `600519.SH`, `000001.SZ`)。