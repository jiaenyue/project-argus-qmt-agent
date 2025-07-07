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

# # 股票详情API 使用教程

# ### 参数说明
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | symbol | str | 是 | 股票代码(格式:代码.交易所) | "600519.SH" |

# ## HTTP调用方式
from xtquant import xtdata

# ## 获取合约基础信息 (get_instrument_detail)
# `get_instrument_detail` 函数用于获取指定股票代码的详细基础信息。
# 参数:
# - `stock_code`: 股票代码，格式为 "代码.交易所"，例如 "600519.SH"。
# - `iscomplete`: 布尔值，是否获取全部字段，默认为 `False`。设置为 `True` 可以获取更详细的信息。

print("--- 获取贵州茅台 (600519.SH) 的基础信息 ---")
instrument_detail = xtdata.get_instrument_detail("600519.SH")
if instrument_detail:
    print(f"股票名称: {instrument_detail.get('InstrumentName')}")
    print(f"交易所ID: {instrument_detail.get('ExchangeID')}")
    print(f"前收盘价: {instrument_detail.get('PreClose')}")
    print(f"总股本: {instrument_detail.get('TotalVolume')}")
    print(f"流通股本: {instrument_detail.get('FloatVolume')}")
    print(f"是否可交易: {instrument_detail.get('IsTrading')}")
else:
    print("未找到贵州茅台 (600519.SH) 的信息，请检查股票代码或数据服务。")

print("\n--- 获取贵州茅台 (600519.SH) 的完整基础信息 ---")
instrument_detail_complete = xtdata.get_instrument_detail("600519.SH", iscomplete=True)
if instrument_detail_complete:
    print("完整信息示例 (部分字段):")
    print(f"  统一规则代码: {instrument_detail_complete.get('UniCode')}")
    print(f"  上市日期 (股票): {instrument_detail_complete.get('OpenDate')}")
    print(f"  最小价格变动单位: {instrument_detail_complete.get('PriceTick')}")
else:
    print("未找到贵州茅台 (600519.SH) 的完整信息。")

# ## 获取合约类型 (get_instrument_type)
# `get_instrument_type` 函数用于获取指定股票代码的合约类型。
# 参数:
# - `stock_code`: 股票代码，格式为 "代码.交易所"，例如 "600519.SH"。
# 返回值:
# - 字典，包含各种类型（如 'stock', 'fund', 'etf', 'index'）及其对应的布尔值。

print("\n--- 获取贵州茅台 (600519.SH) 的合约类型 ---")
instrument_type = xtdata.get_instrument_type("600519.SH")
if instrument_type:
    print(f"是否为股票: {instrument_type.get('stock')}")
    print(f"是否为基金: {instrument_type.get('fund')}")
    print(f"是否为ETF: {instrument_type.get('etf')}")
    print(f"是否为指数: {instrument_type.get('index')}")
else:
    print("未找到贵州茅台 (600519.SH) 的合约类型信息。")

print("\n--- 获取上证指数 (000001.SH) 的合约类型 ---")
index_type = xtdata.get_instrument_type("000001.SH")
if index_type:
    print(f"是否为股票: {index_type.get('stock')}")
    print(f"是否为基金: {index_type.get('fund')}")
    print(f"是否为ETF: {index_type.get('etf')}")
    print(f"是否为指数: {index_type.get('index')}")
else:
    print("未找到上证指数 (000001.SH) 的合约类型信息。")

# ### 实际应用场景
# **投资组合信息查询**：
# 在投资组合管理系统中获取持仓股票的基础信息，用于展示和初步分析。
#
# ```python
# # 获取投资组合中股票详情
# portfolio = ["600519.SH", "000001.SZ", "600036.SH"]
#
# print("\n--- 查询投资组合中股票的基础信息 ---")
# for symbol in portfolio:
#     detail = xtdata.get_instrument_detail(symbol)
#     if detail:
#         print(f"\n股票代码: {symbol}")
#         print(f"  名称: {detail.get('InstrumentName')}")
#         print(f"  前收盘价: {detail.get('PreClose')}")
#         print(f"  总股本: {detail.get('TotalVolume')}")
#         print(f"  流通股本: {detail.get('FloatVolume')}")
#     else:
#         print(f"\n未找到 {symbol} 的信息。")
# ```

# ### FAQ常见问题
# **Q: `get_instrument_detail` 返回的字段含义是什么？**
# A: 详细字段含义请参考 `argus-doc/api/xtdata.md` 文档中“合约信息字段列表”部分。
#
# **Q: 如何获取历史基本面数据？**
# A: `get_instrument_detail` 和 `get_instrument_type` 仅返回实时或静态的基础信息。历史基本面数据需要使用 `xtdata` 模块中的其他接口，例如 `get_financial_data`。