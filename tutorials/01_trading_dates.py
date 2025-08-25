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

# -*- coding: utf-8 -*-
"""

# 学习目标 Learning Objectives


# 背景知识 Background Knowledge

💡 交易日历是金融市场的基础数据，定义了市场的开市和休市时间
💡 不同市场（如沪深、港股、美股）有不同的交易日安排
💡 交易日数据在回测、策略分析和风险管理中起关键作用

通过本教程，您将学会:
1. 理解交易日历的重要性和应用场景
2. 掌握交易日期API的调用方法
3. 学会处理和验证日期数据
4. 了解不同市场的交易日差异

交易日历API使用教程 - Project Argus QMT 数据代理服务

本教程演示如何使用统一的API客户端获取交易日历数据，
包括基础查询、日期范围查询、回测应用等实际场景。

重要说明:
- 本教程仅使用来自API或xtdata的真实数据
- 需要确保API服务正常运行（端口8000/8001）
- 需要有效的数据源连接（xtquant或其他数据提供商）
- 如果API调用失败，将显示错误信息而不是生成模拟数据

功能特性:
- 统一的API客户端调用
- 自动错误处理和重试机制
- 适当的错误处理和用户指导
- 性能监控和统计
- 实际应用场景演示

数据要求:
- 需要有效的市场数据连接
- 建议在交易时间内运行以获取最新数据
- 确保网络连接稳定
"""

import datetime
from typing import Any, Dict, List

# 导入统一工具库
from common import (
    create_api_client, 
    safe_api_call, 
    get_config,
    create_demo_context,
    get_date_range,
    print_api_result,
        # 交易日期数据包含了市场的开市日期，可用于回测和策略分析
    print_section_header,
    print_subsection_header
)

# 保留xtdata导入以支持本地库调用演示
try:
    from xtquant import xtdata

    XTDATA_AVAILABLE = True
except ImportError:
    XTDATA_AVAILABLE = False
    print("注意: xtdata库不可用，将跳过本地库演示")

# 初始化工具和配置
config = get_config()
demo_context = create_demo_context()
performance_monitor = demo_context.performance_monitor


def _call_api_with_fallback(client, api_method_name, **kwargs):
    """统一的API调用和错误处理函数

    Args:
        client: API客户端实例
        api_method_name (str): API方法名称
        **kwargs: API方法参数

    Returns:
        Dict: API调用结果，包含错误信息（如果失败）
    """
    # 获取API方法
    api_method = getattr(client, api_method_name)

    # 尝试API调用
    try:
        result = api_method(**kwargs)
    except Exception as e:
        result = {"code": -1, "message": str(e), "data": None}

    # 如果API失败，返回详细的错误信息
    if result.get("code") != 0:
        print(f"  API调用失败: {result.get('message', '未知错误')}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  确认您的API密钥和访问权限是否正确设置")
        print("  如果问题持续存在，请联系数据服务提供商")

    return result



# 操作步骤 Step-by-Step Guide

# 本教程将按以下步骤进行:
# 步骤 1: 连接API服务并验证可用性
# 步骤 2: 获取指定市场的交易日期
# 步骤 3: 验证日期数据的完整性和格式
# 步骤 4: 对比不同市场的交易日差异
# 步骤 5: 演示交易日在实际应用中的使用

def demo_basic_trading_dates():
    """演示基础交易日历查询功能"""
    print_subsection_header("基础交易日历查询")

    with create_api_client() as client:
        # 演示1: 获取指定日期范围的交易日
        market = "SH"
        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        print(f"获取 {market} 市场 {start_date} 到 {end_date} 的交易日...")
        result = _call_api_with_fallback(
            # 获取交易日历数据 - 返回指定市场的交易日期列表
            client, "get_trading_dates", market=market, start_date=start_date, end_date=end_date
        )
        print_api_result(result, f"{market}市场交易日历")
        # 交易日期数据包含了市场的开市日期，可用于回测和策略分析

        # 演示2: 获取最近N个交易日
        print(f"\n获取 {market} 市场最近5个交易日...")
        # 获取交易日历数据 - 返回指定市场的交易日期列表
        result_recent = _call_api_with_fallback(client, "get_trading_dates", market=market, count=5)
        print_api_result(result_recent, f"{market}市场最近交易日")
        # 交易日期数据包含了市场的开市日期，可用于回测和策略分析


def demo_multi_market_comparison():
    """演示多市场交易日历对比"""
    print_subsection_header("多市场交易日历对比")

    with create_api_client() as client:
        markets = config.demo_markets
        start_date, end_date = get_date_range(7)  # 最近7天

        market_data = {}

        for market in markets:
            print(f"获取 {market} 市场交易日历...")
            result = _call_api_with_fallback(
                # 获取交易日历数据 - 返回指定市场的交易日期列表
                client, "get_trading_dates", market=market, start_date=start_date, end_date=end_date
            )

            if result.get("code") == 0:
                market_data[market] = result["data"]
                print(f"  {market}: {len(result['data'])} 个交易日")
            else:
                print(f"  {market}: 获取失败")

        # 分析市场差异
        if len(market_data) > 1:
            print("\n市场交易日对比分析:")
            all_dates = set()
            for dates in market_data.values():
                all_dates.update(dates)

            common_dates = set(market_data[markets[0]])
            for market in markets[1:]:
                if market in market_data:
                    common_dates &= set(market_data[market])

            print(f"  共同交易日: {len(common_dates)} 天")
            print(f"  总交易日: {len(all_dates)} 天")
        else:
            print("\n无法进行市场对比分析（数据不足）")


def demo_xtdata_local_calls():
    """演示xtdata本地库调用"""
    if not XTDATA_AVAILABLE:
        print_subsection_header("xtdata本地库调用 (跳过 - 库不可用)")
        return

    print_subsection_header("xtdata本地库调用演示")

    market = "SH"
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=7)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    try:
        print(f"通过xtdata获取 {market} 市场 {start_date} 到 {end_date} 的交易日...")
        # 获取交易日历数据 - 返回指定市场的交易日期列表
        local_dates = xtdata.get_trading_dates(
            market=market, start_time=start_date, end_time=end_date
        )
        print(f"  结果: {local_dates}")

        print(f"\n通过xtdata获取 {market} 市场最近5个交易日...")
        # 获取交易日历数据 - 返回指定市场的交易日期列表
        recent_dates = xtdata.get_trading_dates(market=market, count=5)
        print(f"  结果: {recent_dates}")

    except Exception as e:
        print(f"xtdata调用失败: {e}")
        print("请检查xtdata环境配置和数据服务可用性")
        print("无法获取交易日数据")


def demo_backtest_application():
    """演示回测系统中的交易日历应用"""
    print_subsection_header("回测系统应用场景")

    with create_api_client() as client:
        # 获取一个季度的交易日历用于回测
        market = "SH"
        start_date = (datetime.date.today() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
        end_date = "2025-03-31"

        print(f"获取 {market} 市场 2025年第一季度交易日历...")
        result = _call_api_with_fallback(
            # 获取交易日历数据 - 返回指定市场的交易日期列表
            client, "get_trading_dates", market=market, start_date=start_date, end_date=end_date
        )

        if result.get("code") == 0:
            trading_dates = result["data"]
            print(f"  获取到 {len(trading_dates)} 个交易日")
            print(f"  日期范围: {trading_dates[0]} 到 {trading_dates[-1]}")

            # 回测引擎使用交易日历演示
            print("\n回测引擎处理演示:")
            processed_count = 0
            for date in trading_dates[:10]:  # 限制处理数量
                # 回测逻辑演示
                processed_count += 1

            print(f"  处理了 {processed_count} 个交易日的回测数据")

            # 统计分析
            print(f"\n交易日历统计:")
            print(f"  总交易日: {len(trading_dates)}")
            print(f"  平均每月交易日: {len(trading_dates) / 3:.1f}")
        else:
            print("  无法获取交易日历数据，回测演示跳过")


def demo_error_handling():
    """演示错误处理和降级机制"""
    print_subsection_header("错误处理演示")

    # 创建一个会失败的客户端（错误的URL）
    print("尝试连接到无效的API服务...")
    try:
        with create_api_client(base_url="http://invalid-url:9999") as client:
            # 获取交易日历数据 - 返回指定市场的交易日期列表
            result = _call_api_with_fallback(client, "get_trading_dates", market="SH", count=5)
            print_api_result(result, "错误处理演示结果")
        # 交易日期数据包含了市场的开市日期，可用于回测和策略分析

    except Exception as e:
        print(f"演示异常处理: {e}")
        print("API服务不可用，请检查网络连接和服务状态")
        print("无法获取交易日数据")


def print_usage_guide():
    """打印使用指南和注意事项"""
    print_subsection_header("使用指南和注意事项")

    print(
        """
API参数说明:
  market     : 市场代码 (SH-上交所, SZ-深交所)
  start_date : 开始日期 (YYYY-MM-DD格式)
  end_date   : 结束日期 (YYYY-MM-DD格式)  
  count      : 返回数量 (-1表示全部, >0表示指定数量)

常见错误和解决方案:
  1. 连接错误 - 确保API服务运行在 http://127.0.0.1:8000
  2. 参数错误 - 检查市场代码和日期格式
  3. 超时错误 - 检查网络连接和服务状态
  4. 数据为空 - 可能是非交易日期间或参数错误

最佳实践:
  - 使用统一的API客户端进行调用
  - 实现错误处理和重试机制
  - 提供清晰的错误信息和故障排除指导
  - 监控API调用性能和成功率
"""
    )


def main():
    """主函数 - 执行所有演示"""
    print_section_header("交易日历API使用教程")

    try:
        # 基础功能演示
        demo_basic_trading_dates()

        # 多市场对比演示
        demo_multi_market_comparison()

        # 本地库调用演示
        demo_xtdata_local_calls()

        # 实际应用场景演示
        demo_backtest_application()

        # 错误处理演示
        demo_error_handling()

        # 使用指南
        print_usage_guide()

        # 性能统计
        print_section_header("性能统计报告")
        performance_monitor.print_summary()

    except Exception as e:
        print(f"教程执行出错: {e}")

    finally:
        print_section_header("教程完成")


if __name__ == "__main__":
    main()