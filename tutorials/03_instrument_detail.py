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
# | 参数名 | 类型 | 是否必填 | 说明 | 示例值 |
# |--------|------|----------|------|--------|
# | stock_code | str | 是 | 股票代码(格式:代码.交易所) | "600519.SH" |
# | iscomplete | bool | 否 | 是否获取全部字段，默认为False | False |

# ## HTTP调用方式
from xtquant import xtdata

# 获取单个股票的合约详情
# xtdata库的get_instrument_detail函数用于获取合约基础信息。
# 参数:
#   stock_code (str): 股票代码，格式为"代码.交易所"，例如"600519.SH"。
#   iscomplete (bool): 是否获取全部字段，默认为False。
# 返回:
#   dict: 包含合约详细信息的字典。如果找不到指定合约，则返回None。
symbol = "600519.SH"
print(f"正在获取 {symbol} 的合约详情...")
detail = xtdata.get_instrument_detail(symbol, iscomplete=False)

if detail:
    print(f"调用结果：{detail}")
    # 示例：打印部分关键信息
    print(f"股票名称: {detail.get('InstrumentName')}")
    print(f"交易所ID: {detail.get('ExchangeID')}")
    print(f"总股本: {detail.get('TotalVolume')}")
    print(f"流通股本: {detail.get('FloatVolume')}")
else:
    print(f"未找到 {symbol} 的合约详情，请检查股票代码或确保MiniQmt服务正常运行。")

# ### 实际应用场景
# **实时监控仪表盘**：
# 在实时监控系统中展示股票的基本信息，如最新价格、涨跌幅、市值等关键指标。
#
# ```python
# # 获取多只股票详情
# symbols = ["600519.SH", "000001.SZ", "00700.HK"]
#
# print("\n--- 批量获取合约详情示例 ---")
# for symbol in symbols:
#     detail = xtdata.get_instrument_detail(symbol, iscomplete=False)
#     if detail:
#         # 假设我们需要展示股票名称和总股本
#         name = detail.get('InstrumentName', 'N/A')
#         total_volume = detail.get('TotalVolume', 'N/A')
#         print(f"股票代码: {symbol}, 名称: {name}, 总股本: {total_volume}")
#     else:
#         print(f"未找到 {symbol} 的合约详情。")
# ```

# ### 错误处理
# `xtdata.get_instrument_detail` 函数在找不到合约时会返回 `None`。
#
# ```python
# # 错误处理示例
# print("\n--- 错误处理示例 ---")
# invalid_symbol = "INVALID.XX"
# print(f"正在尝试获取无效股票代码 {invalid_symbol} 的合约详情...")
# detail_invalid = xtdata.get_instrument_detail(invalid_symbol)
#
# if detail_invalid is None:
#     print(f"成功处理错误：未找到 {invalid_symbol} 的合约详情。")
# else:
#     print(f"意外：找到了 {invalid_symbol} 的合约详情。")
# ```
#
# 对于更底层的连接错误，`xtdata` 库通常会自行处理或抛出 `XtQuantError` 等特定异常。
#
# | 常见问题 | 解决方案 |
# |--------|----------|
# | 返回 `None` | 检查股票代码格式是否正确，或确认该股票是否存在。 |
# | 连接错误 | 确保MiniQmt服务正常运行，且xtdata已正确连接。 |

# ### 性能优化建议
# 1. **批量查询**：使用批量查询接口减少请求次数
# 2. **缓存机制**：对不常变动的信息(如公司名称)进行本地缓存
# 3. **按需请求**：只请求需要的字段减少响应大小
# 4. **连接池复用**：保持HTTP连接复用减少握手开销

# ### FAQ常见问题
# **Q: `get_instrument_detail` 返回的数据包含哪些字段？**  
# A: 默认情况下（`iscomplete=False`），返回常用字段如 `ExchangeID`, `InstrumentID`, `InstrumentName`, `TotalVolume`, `FloatVolume` 等。当 `iscomplete=True` 时，将返回所有可用字段，详见 `argus-doc/api/xtdata.md` 文档中的“合约信息字段列表”部分。
#
# **Q: 如何获取历史合约信息？**  
# A: `get_instrument_detail` 函数主要用于获取合约的基础静态信息。对于历史行情数据（如K线、分笔数据），应使用 `xtdata` 模块中的 `get_market_data` 或 `download_history_data` 等函数。
#
# **Q: 是否支持查询港股和美股？**  
# A: 支持。港股代码后缀为 `.HK`，美股代码后缀为 `.US`。
#
# ## 注意事项
# - 确保MiniQmt服务正常运行，xtdata库依赖于此服务获取数据。
# - 需要指定正确的股票代码 `stock_code`，格式为 `代码.交易所`。
# - `get_instrument_detail` 返回的是合约的基础信息，而非实时行情数据。实时行情数据请使用 `subscribe_quote` 或 `get_market_data`。