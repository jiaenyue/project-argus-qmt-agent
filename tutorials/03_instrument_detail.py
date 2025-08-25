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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

# 学习目标 Learning Objectives


# 背景知识 Background Knowledge

💡 合约详情包含股票的基本属性和交易规则
💡 这些信息对投资决策和风险管理至关重要
💡 不同类型的股票有不同的交易特征

通过本教程，您将学会:
1. 了解股票基础信息的重要性
2. 掌握合约详情API的使用方法
3. 学会解读股票的各种属性
4. 理解如何利用基础信息进行筛选

合约详情信息API使用教程

本教程演示如何使用QMT数据代理服务获取股票合约的详细基础信息，
包括股票名称、交易所信息、股本结构等关键数据。

重要说明:
- 本教程仅使用来自API的真实合约数据
- 不再提供模拟数据功能
- 需要确保API服务正常运行和数据源连接有效
- 如果无法获取数据，将显示详细的错误信息

主要功能：
- 获取单个股票的详细信息
- 批量查询投资组合股票信息
- 股票基本面数据分析和可视化
- 适当的错误处理和用户指导
- 性能监控和统计

数据要求:
- 需要有效的合约信息数据源
- 确保股票代码格式正确（包含交易所后缀）
- 网络连接稳定，API服务响应正常
- 建议使用活跃交易的股票代码进行测试

作者: QMT数据代理服务团队
版本: 2.3
"""

import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 导入统一工具库
from common import (
    QMTAPIClient, 
    create_api_client, 
    safe_api_call,
    get_config,
    PerformanceMonitor,
    create_demo_context,
    format_number,
    format_response_time,
    print_api_result,
        # 合约详情提供了股票的基本属性，有助于筛选和分类
    print_section_header,
    print_subsection_header,
    validate_symbol_format
)

# 初始化工具
config = get_config()
demo_context = create_demo_context()
api_client = demo_context.api_client
performance_monitor = demo_context.performance_monitor


def get_single_instrument_detail(symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取单个股票的详细基础信息

    Args:
        symbol (str): 股票代码，格式为 "代码.交易所"，例如 "600519.SH"

    Returns:
        Optional[Dict[str, Any]]: 股票详细信息，失败时返回None
    """
    # 验证股票代码格式
    if not validate_symbol_format(symbol):
        print(f"警告: 股票代码 '{symbol}' 格式不正确，应为 'XXXXXX.SH' 或 'XXXXXX.SZ' 格式")

    # 调用API获取数据
    start_time = time.time()
    try:
        # 获取合约详细信息 - 返回股票的基础信息和属性
        result = api_client.get_instrument_detail(symbol)
    except Exception as e:
        result = {"code": -1, "message": str(e), "data": None}
    duration = time.time() - start_time

    # 记录性能数据
    success = result.get("code") == 0 and result.get("data") is not None
    # 获取合约详细信息 - 返回股票的基础信息和属性
    performance_monitor.record_api_call("get_instrument_detail", duration, success)

    if success:
        # API调用成功，返回真实数据
        data = result["data"]
        if isinstance(data, list) and len(data) > 0:
            return data[0]  # 单个股票查询返回列表的第一个元素
        elif isinstance(data, dict):
            return data
    else:
        # API调用失败，返回错误信息
        error_msg = result.get("message", "未知错误")
        print(f"  API调用失败: {error_msg}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  确认您的API密钥和访问权限是否正确设置")
        print("  如果问题持续存在，请联系数据服务提供商")

    return None


def get_multiple_instrument_details(symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    批量获取多个股票的详细基础信息

    Args:
        symbols (List[str]): 股票代码列表

    Returns:
        Dict[str, Optional[Dict[str, Any]]]: 股票代码到详细信息的映射
    """
    if not symbols:
        print("警告: 未提供股票代码列表")
        return {}

    results = {}

    # 验证股票代码格式
    valid_symbols = []
    for symbol in symbols:
        if validate_symbol_format(symbol):
            valid_symbols.append(symbol)
        else:
            print(f"警告: 股票代码 '{symbol}' 格式不正确，将被跳过")

    if not valid_symbols:
        print("错误: 没有有效的股票代码")
        return {}

    # 尝试批量查询
    start_time = time.time()
    try:
        # 获取合约详细信息 - 返回股票的基础信息和属性
        batch_result = api_client.get_instrument_detail(valid_symbols)
    except Exception as e:
        batch_result = {"code": -1, "message": str(e), "data": None}
    duration = time.time() - start_time

    # 记录性能数据
    success = batch_result.get("code") == 0 and batch_result.get("data") is not None
    # 获取合约详细信息 - 返回股票的基础信息和属性
    performance_monitor.record_api_call("get_instrument_detail_batch", duration, success)

    if success:
        # 批量查询成功
        data = batch_result["data"]
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "symbol" in item:
                    results[item["symbol"]] = item
        elif isinstance(data, dict):
            # 单个结果的情况
            if "symbol" in data:
                results[data["symbol"]] = data
    else:
        print(f"  批量查询失败: {batch_result.get('message', '未知错误')}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  确认您的API密钥和访问权限是否正确设置")

    # 对于未获取到的股票，返回错误信息
    for symbol in valid_symbols:
        if symbol not in results:
            print(f"  无法获取股票信息: {symbol}")
            print("  请检查股票代码是否正确，以及API服务是否可用")
            results[symbol] = None

    return results


def format_instrument_info(data: Dict[str, Any], detailed: bool = False) -> None:
    """
    格式化显示股票基础信息

    Args:
        data (Dict[str, Any]): 股票详细信息
        detailed (bool): 是否显示详细信息，默认为False
    """
    if not data:
        print("  无数据")
        return

    # 基础信息
    print(f"  股票名称: {data.get('name', 'N/A')}")
    print(f"  股票代码: {data.get('symbol', 'N/A')}")
    print(f"  交易所: {data.get('exchange', data.get('ExchangeID', 'N/A'))}")

    # 价格信息
    current_price = data.get("current_price", data.get("PreClose", "N/A"))
    if isinstance(current_price, (int, float)):
        print(f"  当前价格: {format_number(current_price)}")
    else:
        print(f"  前收盘价: {data.get('PreClose', 'N/A')}")

    # 股本信息
    total_volume = data.get("TotalVolume", data.get("total_volume", "N/A"))
    if isinstance(total_volume, (int, float)):
        print(f"  总股本: {format_number(total_volume)} 股")
    else:
        print(f"  总股本: {total_volume}")

    float_volume = data.get("FloatVolume", data.get("float_volume", "N/A"))
    if isinstance(float_volume, (int, float)):
        print(f"  流通股本: {format_number(float_volume)} 股")
    else:
        print(f"  流通股本: {float_volume}")

    # 交易状态
    is_trading = data.get("IsTrading", data.get("status", "N/A"))
    print(f"  是否可交易: {is_trading}")

    # 基本面数据
    if detailed:
        print("\n  --- 详细信息 ---")

        # 上市信息
        list_date = data.get("OpenDate", data.get("list_date", "N/A"))
        if list_date:
            try:
                # 尝试格式化日期显示
                if len(str(list_date)) == 8:  # YYYYMMDD格式
                    formatted_date = f"{list_date[:4]}-{list_date[4:6]}-{list_date[6:8]}"
                    print(f"  上市日期: {formatted_date}")
                else:
                    print(f"  上市日期: {list_date}")
            except:
                print(f"  上市日期: {list_date}")

        # 价格限制
        if "price_limit_up" in data:
            print(f"  涨停价: {format_number(data['price_limit_up'])}")
        if "price_limit_down" in data:
            print(f"  跌停价: {format_number(data['price_limit_down'])}")
        if "PriceTick" in data:
            print(f"  最小价格变动单位: {data['PriceTick']}")

        # 市值信息
        if "market_cap" in data:
            print(f"  总市值: {format_number(data['market_cap'])} 亿元")
        if "circulation_market_cap" in data:
            print(f"  流通市值: {format_number(data['circulation_market_cap'])} 亿元")

        # 估值指标
        if "pe_ratio" in data:
            print(f"  市盈率(PE): {format_number(data['pe_ratio'])}")
        if "pb_ratio" in data:
            print(f"  市净率(PB): {format_number(data['pb_ratio'])}")
        if "dividend_yield" in data:
            print(f"  股息率: {format_number(data['dividend_yield'])}%")

        # 其他指标
        if "beta" in data:
            print(f"  贝塔系数: {format_number(data['beta'])}")
        if "turnover_rate" in data:
            print(f"  换手率: {format_number(data['turnover_rate'])}%")

        # 其他可能的字段
        for key in ["sector", "industry", "currency", "lot_size"]:
            if key in data:
                print(f"  {key}: {data[key]}")

        # 统一规则代码
        if "UniCode" in data:
            print(f"  统一规则代码: {data['UniCode']}")


def analyze_stock_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析股票数据，提供投资参考指标

    Args:
        data (Dict[str, Any]): 股票详细信息

    Returns:
        Dict[str, Any]: 分析结果
    """
    if not data:
        return {"error": "无数据可分析"}

    analysis = {}

    # 基本信息
    analysis["symbol"] = data.get("symbol", "未知")
    analysis["name"] = data.get("name", "未知")

    # 估值分析
    pe_ratio = data.get("pe_ratio", data.get("pe", None))
    pb_ratio = data.get("pb_ratio", data.get("pb", None))
    dividend_yield = data.get("dividend_yield", None)

    if pe_ratio is not None and isinstance(pe_ratio, (int, float)):
        if pe_ratio < 0:
            analysis["pe_evaluation"] = "亏损"
        elif pe_ratio < 15:
            analysis["pe_evaluation"] = "低估值"
        elif pe_ratio < 30:
            analysis["pe_evaluation"] = "合理估值"
        elif pe_ratio < 50:
            analysis["pe_evaluation"] = "高估值"
        else:
            analysis["pe_evaluation"] = "极高估值"

    if pb_ratio is not None and isinstance(pb_ratio, (int, float)):
        if pb_ratio < 1:
            analysis["pb_evaluation"] = "低于净资产"
        elif pb_ratio < 2:
            analysis["pb_evaluation"] = "合理估值"
        elif pb_ratio < 5:
            analysis["pb_evaluation"] = "高估值"
        else:
            analysis["pb_evaluation"] = "极高估值"

    if dividend_yield is not None and isinstance(dividend_yield, (int, float)):
        if dividend_yield > 5:
            analysis["dividend_evaluation"] = "高股息"
        elif dividend_yield > 3:
            analysis["dividend_evaluation"] = "良好股息"
        elif dividend_yield > 1:
            analysis["dividend_evaluation"] = "一般股息"
        else:
            analysis["dividend_evaluation"] = "低股息"

    # 流通性分析
    turnover_rate = data.get("turnover_rate", None)
    if turnover_rate is not None and isinstance(turnover_rate, (int, float)):
        if turnover_rate > 15:
            analysis["liquidity"] = "极高流动性"
        elif turnover_rate > 10:
            analysis["liquidity"] = "高流动性"
        elif turnover_rate > 5:
            analysis["liquidity"] = "中等流动性"
        else:
            analysis["liquidity"] = "低流动性"

    # 市值分类
    market_cap = data.get("market_cap", None)
    if market_cap is not None and isinstance(market_cap, (int, float)):
        if market_cap > 5000:
            analysis["size"] = "超大盘股"
        elif market_cap > 1000:
            analysis["size"] = "大盘股"
        elif market_cap > 300:
            analysis["size"] = "中盘股"
        elif market_cap > 100:
            analysis["size"] = "小盘股"
        else:
            analysis["size"] = "微盘股"

    # 综合评估
    evaluation_points = 0
    evaluation_count = 0

    if "pe_evaluation" in analysis:
        if analysis["pe_evaluation"] in ["低估值", "合理估值"]:
            evaluation_points += 1
        evaluation_count += 1

    if "pb_evaluation" in analysis:
        if analysis["pb_evaluation"] in ["低于净资产", "合理估值"]:
            evaluation_points += 1
        evaluation_count += 1

    if "dividend_evaluation" in analysis:
        if analysis["dividend_evaluation"] in ["高股息", "良好股息"]:
            evaluation_points += 1
        evaluation_count += 1

    if evaluation_count > 0:
        score = evaluation_points / evaluation_count
        if score > 0.7:
            analysis["overall_evaluation"] = "投资价值较高"
        elif score > 0.3:
            analysis["overall_evaluation"] = "投资价值一般"
        else:
            analysis["overall_evaluation"] = "投资价值较低"
    else:
        analysis["overall_evaluation"] = "数据不足，无法评估"

    return analysis



# 操作步骤 Step-by-Step Guide

# 本教程将按以下步骤进行:
# 步骤 1: 准备股票代码列表
# 步骤 2: 调用合约详情API
# 步骤 3: 解析返回的详细信息
# 步骤 4: 验证数据的准确性
# 步骤 5: 演示基于属性的股票筛选

def demo_single_stock_query():
    """演示单个股票查询功能"""
    print_section_header("单个股票合约详情查询演示")

    # 演示股票代码
    demo_symbol = "600519.SH"  # 贵州茅台

    print_subsection_header(f"获取 {demo_symbol} 的基础信息")

    # 获取股票详情
    instrument_detail = get_single_instrument_detail(demo_symbol)

    if instrument_detail:
        print("✓ 成功获取股票信息:")
        # 显示详细信息
        format_instrument_info(instrument_detail, detailed=True)

        # 分析股票数据
        print_subsection_header(f"{demo_symbol} 投资分析")
        analysis = analyze_stock_data(instrument_detail)

        if "error" not in analysis:
            print(f"  股票: {analysis.get('name')} ({analysis.get('symbol')})")

            if "pe_evaluation" in analysis:
                print(f"  市盈率评估: {analysis['pe_evaluation']}")
            if "pb_evaluation" in analysis:
                print(f"  市净率评估: {analysis['pb_evaluation']}")
            if "dividend_evaluation" in analysis:
                print(f"  股息评估: {analysis['dividend_evaluation']}")
            if "liquidity" in analysis:
                print(f"  流动性: {analysis['liquidity']}")
            if "size" in analysis:
                print(f"  市值规模: {analysis['size']}")
            if "overall_evaluation" in analysis:
                print(f"  综合评估: {analysis['overall_evaluation']}")
        else:
            print(f"  无法分析: {analysis['error']}")
    else:
        print(f"✗ 未能获取 {demo_symbol} 的信息")


def demo_portfolio_query():
    """演示投资组合批量查询功能"""
    print_section_header("投资组合批量查询演示")

    # 定义示例投资组合
    portfolio_symbols = config.demo_symbols[:4]  # 使用配置中的示例股票

    print_subsection_header("批量获取投资组合股票信息")
    print(f"查询股票列表: {', '.join(portfolio_symbols)}")

    # 批量获取股票详情
    start_time = time.time()
    portfolio_details = get_multiple_instrument_details(portfolio_symbols)
    query_duration = time.time() - start_time

    success_count = len([v for v in portfolio_details.values() if v])
    total_count = len(portfolio_symbols)

    print(
        f"\n成功获取 {success_count} / {total_count} 只股票的信息 (耗时: {format_response_time(query_duration)}):"
    )

    # 显示股票信息
    for symbol, detail in portfolio_details.items():
        print(f"\n股票代码: {symbol}")
        if detail:
            format_instrument_info(detail)
        else:
            print("  无法获取该股票信息")

    # 投资组合分析
    if success_count > 0:
        print_subsection_header("投资组合分析")

        # 计算投资组合估值指标
        pe_values = []
        pb_values = []
        dividend_values = []
        market_caps = []

        for detail in portfolio_details.values():
            if not detail:
                continue

            if (
                "pe_ratio" in detail
                and isinstance(detail["pe_ratio"], (int, float))
                and detail["pe_ratio"] > 0
            ):
                pe_values.append(detail["pe_ratio"])

            if (
                "pb_ratio" in detail
                and isinstance(detail["pb_ratio"], (int, float))
                and detail["pb_ratio"] > 0
            ):
                pb_values.append(detail["pb_ratio"])

            if (
                "dividend_yield" in detail
                and isinstance(detail["dividend_yield"], (int, float))
                and detail["dividend_yield"] >= 0
            ):
                dividend_values.append(detail["dividend_yield"])

            if (
                "market_cap" in detail
                and isinstance(detail["market_cap"], (int, float))
                and detail["market_cap"] > 0
            ):
                market_caps.append(detail["market_cap"])

        # 显示投资组合统计
        if pe_values:
            avg_pe = sum(pe_values) / len(pe_values)
            print(f"  平均市盈率(PE): {format_number(avg_pe)}")

        if pb_values:
            avg_pb = sum(pb_values) / len(pb_values)
            print(f"  平均市净率(PB): {format_number(avg_pb)}")

        if dividend_values:
            avg_dividend = sum(dividend_values) / len(dividend_values)
            print(f"  平均股息率: {format_number(avg_dividend)}%")

        if market_caps:
            total_market_cap = sum(market_caps)
            print(f"  总市值: {format_number(total_market_cap)} 亿元")

        # 投资组合行业分布
        sectors = {}
        for detail in portfolio_details.values():
            if not detail:
                continue

            sector = detail.get("sector", "未知")
            if sector in sectors:
                sectors[sector] += 1
            else:
                sectors[sector] = 1

        if sectors:
            print("\n  行业分布:")
            for sector, count in sectors.items():
                percentage = count / success_count * 100
                print(f"    {sector}: {count}只 ({percentage:.1f}%)")


def demo_error_handling():
    """演示错误处理机制"""
    print_section_header("错误处理机制演示")

    # 测试无效股票代码
    invalid_symbols = ["INVALID.XX", "999999.SH", "000000.SZ"]

    print_subsection_header("无效股票代码处理")

    for symbol in invalid_symbols:
        print(f"\n测试无效代码: {symbol}")

        # 记录开始时间
        start_time = time.time()
        detail = get_single_instrument_detail(symbol)
        duration = time.time() - start_time

        if detail:
            print(f"  ✓ 获取到数据 (耗时: {format_response_time(duration)})")
            format_instrument_info(detail)

            # 显示数据来源
            print("\n  数据来源分析:")
            print("  此数据由API提供的真实市场数据")
        else:
            print(f"  ✗ 无法获取信息 (耗时: {format_response_time(duration)})")
            print("  可能的原因:")
            print("  - 股票代码格式无效")
            print("  - 股票不存在或已退市")
            print("  - API服务不可用")


def demo_performance_analysis():
    """演示性能分析功能"""
    print_section_header("性能分析演示")

    # 执行多次查询来收集性能数据
    test_symbols = ["600519.SH", "000001.SZ", "601318.SH"]

    print_subsection_header("执行性能测试")
    print("正在执行多次查询以收集性能数据...")

    for i in range(3):
        for symbol in test_symbols:
            start_time = time.time()
            detail = get_single_instrument_detail(symbol)
            duration = time.time() - start_time

            success = detail is not None
            print(
                f"  查询 {symbol}: {format_response_time(duration)} ({'成功' if success else '失败'})"
            )

    # 显示性能统计
    print_subsection_header("性能统计结果")
    performance_monitor.print_summary()


def main():
    """主函数 - 执行所有演示"""
    print_section_header("QMT 合约详情信息API使用教程")
    print("本教程演示如何使用统一API客户端获取股票合约的详细基础信息")
    print(f"演示时间: {demo_context.timestamp}")

    try:
        # 1. 单个股票查询演示
        demo_single_stock_query()

        # 2. 投资组合批量查询演示
        demo_portfolio_query()

        # 3. 错误处理演示
        demo_error_handling()

        # 4. 性能分析演示
        demo_performance_analysis()

        print_section_header("教程总结")
        print("✓ 单个股票查询功能正常")
        print("✓ 批量查询功能正常")
        print("✓ 错误处理机制有效")
        print("✓ 性能监控功能完整")
        print("\n教程执行完成！")

    except Exception as e:
        print(f"\n教程执行过程中发生错误: {e}")
        print("请检查API服务状态和网络连接")

    finally:
        # 清理资源
        api_client.close()


if __name__ == "__main__":
    main()


# 最佳实践 Best Practices

# 在实际应用中，建议遵循以下最佳实践:
# ✅ 定期更新股票基础信息
# ✅ 验证股票代码的有效性
# ✅ 关注股票的交易状态变化
# ✅ 利用基础信息进行风险评估