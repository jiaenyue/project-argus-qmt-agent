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

"""

# 学习目标 Learning Objectives


# 背景知识 Background Knowledge

💡 股票列表是构建投资组合的基础
💡 不同市场有不同的股票分类和编码规则
💡 股票列表会随时间变化（上市、退市）

通过本教程，您将学会:
1. 掌握获取股票列表的方法
2. 了解不同市场的股票分类
3. 学会处理大量股票数据
4. 理解股票列表在投资中的应用

板块股票列表API 使用教程 - Project Argus QMT 数据代理服务

本教程演示如何使用统一的API客户端获取板块分类信息和板块内的股票列表，
包括板块分析、投资组合构建和板块轮动策略示例。

重要说明:
- 本教程仅使用来自API的真实板块和股票数据
- 不再提供模拟数据功能
- 需要确保API服务正常运行和数据源连接有效
- 如果无法获取数据，将显示详细的错误信息和故障排除指导

主要功能:
1. 获取板块列表和成分股信息
2. 板块间比较分析
3. 投资组合构建示例
4. 板块轮动监控演示

数据要求:
- 需要有效的板块分类数据源
- 确保板块名称正确（如"银行"、"科技"等）
- 网络连接稳定，API服务响应正常
- 建议使用主流板块进行测试以确保数据可用性
"""

import datetime
import time
from typing import Any, Dict, List, Optional

# 导入统一工具库
from common import (
    QMTAPIClient, 
    create_api_client, 
    safe_api_call,
    get_config,
    PerformanceMonitor,
    format_number,
    format_response_time,
    print_api_result,
        # 股票列表是构建投资组合和市场分析的起点
    print_section_header,
    print_subsection_header
)

# 初始化工具
config = get_config()
api_client = create_api_client()
# Mock data generator instance removed
performance_monitor = PerformanceMonitor()


def download_sector_data_demo():
    """演示下载板块分类信息"""
    print_subsection_header("下载板块分类信息")
    print("正在下载板块数据，这可能需要一些时间...")

    start_time = time.time()
    # 使用股票列表API替代下载板块数据
    result = safe_api_call(api_client, api_client.get_stock_list, market="SH")
    duration = time.time() - start_time

    performance_monitor.record_api_call("get_stock_list", duration, result.get("code") == 0)

    if result.get("code") == 0:
        print(f"✓ 板块数据获取完成，耗时: {format_response_time(duration)}")
        print_api_result(result, "获取结果")
        # 股票列表是构建投资组合和市场分析的起点
    else:
        print(f"✗ 板块数据获取失败: {result.get('message', '未知错误')}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  确认您的API密钥和访问权限是否正确设置")
        print("  如果问题持续存在，请联系数据服务提供商")
        return []


def get_sector_list_demo():
    """演示获取板块列表"""
    print_subsection_header("获取所有板块列表")

    start_time = time.time()
    # 使用股票列表API替代板块列表API
    result = safe_api_call(api_client, api_client.get_stock_list, market="ALL")
    duration = time.time() - start_time

    performance_monitor.record_api_call("get_stock_list", duration, result.get("code") == 0)

    if result.get("code") != 0:
        print(f"  API调用失败: {result.get('message', '未知错误')}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  确认您的API密钥和访问权限是否正确设置")
        print("  无法获取股票列表数据")
        return []

    print_api_result(result, f"股票列表 (耗时: {format_response_time(duration)})")
        # 股票列表是构建投资组合和市场分析的起点

    return result.get("data", [])


def get_sector_stocks_demo(sector_name: str, real_timetag: str = None):
    """演示获取指定板块的成分股列表

    Args:
        sector_name: 板块名称
        real_timetag: 历史时间点 (YYYYMMDD格式)
    """
    time_desc = f"({real_timetag})" if real_timetag else "(最新)"
    print_subsection_header(f"获取 {sector_name} 成分股列表 {time_desc}")

    start_time = time.time()
    # 使用股票列表API替代板块成分股API
    result = safe_api_call(api_client, api_client.get_stock_list, sector=sector_name)
    duration = time.time() - start_time

    performance_monitor.record_api_call("get_stock_list", duration, result.get("code") == 0)

    if result.get("code") != 0:
        print(f"  API调用失败: {result.get('message', '未知错误')}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  确认您的API密钥和访问权限是否正确设置")
        print("  无法获取板块成分股数据")
        return []

    print_api_result(result, f"{sector_name} 成分股 (耗时: {format_response_time(duration)})")
        # 股票列表是构建投资组合和市场分析的起点

    return result.get("data", [])


def analyze_sector_performance(sectors: List[str]) -> Dict[str, Any]:
    """分析多个板块的表现对比

    Args:
        sectors: 板块名称列表

    Returns:
        Dict: 板块分析结果
    """
    if not sectors:
        print("  板块表现分析失败：板块列表为空")
        print("  请提供至少一个有效的板块名称")
        return {}
    
    print_subsection_header("板块表现分析")
    
    if len(sectors) > 20:
        print(f"  板块表现分析警告：板块数量较多（{len(sectors)}个）")
        print("  分析可能需要较长时间，建议分批处理")

    sector_analysis = {}
    failed_sectors = []

    for i, sector in enumerate(sectors, 1):
        print(f"\n正在分析板块 ({i}/{len(sectors)}): {sector}")

        if not sector or not isinstance(sector, str):
            print(f"  跳过无效板块名称: {sector}")
            failed_sectors.append(f"{sector}(无效名称)")
            continue

        try:
            # 获取板块成分股
            stocks = get_sector_stocks_demo(sector)
            if not stocks:
                print(f"  板块{sector}分析失败：未获取到成分股数据")
                print("  可能的原因：")
                print("    - 板块名称不正确或不存在")
                print("    - API服务暂时不可用")
                print("    - 该板块当前无成分股")
                failed_sectors.append(f"{sector}(无成分股)")
                continue
            
            if len(stocks) < 3:
                print(f"  板块{sector}分析警告：成分股数量较少（{len(stocks)}只）")
                print("  分析结果可能不够准确")
        
        except Exception as e:
            print(f"  板块{sector}分析出错：{e}")
            failed_sectors.append(f"{sector}(获取失败)")
            continue

        # 获取前10只股票的行情数据进行更全面的分析
        sample_size = min(10, len(stocks))
        sample_stocks = stocks[:sample_size]
        sector_data = []

        # 批量获取股票行情以提高效率
        stock_symbols = []
        for stock in sample_stocks:
            if isinstance(stock, dict):
                stock_symbol = stock.get("symbol", stock.get("code", str(stock)))
            else:
                stock_symbol = str(stock)
            stock_symbols.append(stock_symbol)

        # 使用批量API调用
        start_time = time.time()
        market_result = safe_api_call(api_client, api_client.get_latest_market, stock_symbols)
        duration = time.time() - start_time

        performance_monitor.record_api_call(
            "get_latest_market_batch", duration, market_result.get("code") == 0
        )

        if market_result.get("code") != 0:
            print(f"  批量行情获取失败: {market_result.get('message', '未知错误')}")
            print("  请检查网络连接和API配置，确保数据服务可用")
            print("  确认您的API密钥和访问权限是否正确设置")
            print("  无法获取股票行情数据")
            return {}

        if market_result.get("code") == 0:
            market_data = market_result["data"]

            for stock_symbol in stock_symbols:
                if isinstance(market_data, dict):
                    if stock_symbol in market_data:
                        stock_data = market_data[stock_symbol]
                    else:
                        # 如果批量数据中没有该股票，单独获取
                        single_result = safe_api_call(
                            api_client, api_client.get_latest_market, [stock_symbol]
                        )
                        if single_result.get("code") == 0:
                            stock_data = single_result["data"]
                        else:
                            continue
                else:
                    stock_data = market_data

                # 计算技术指标
                pe_ratio = stock_data.get("pe_ratio", 0)
                pb_ratio = stock_data.get("pb_ratio", 0)
                volume_ratio = stock_data.get("volume_ratio", 1.0)
                turnover_rate = stock_data.get("turnover_rate", 0)

                sector_data.append(
                    {
                        "symbol": stock_symbol,
                        "name": stock_data.get("name", stock_symbol),
                        "current_price": stock_data.get("current_price", 0),
                        "change_pct": stock_data.get("change_pct", 0),
                        "volume": stock_data.get("volume", 0),
                        "turnover": stock_data.get("turnover", 0),
                        "pe_ratio": pe_ratio,
                        "pb_ratio": pb_ratio,
                        "volume_ratio": volume_ratio,
                        "turnover_rate": turnover_rate,
                        "market_cap": stock_data.get("market_cap", 0),
                    }
                )

        if sector_data:
            # 计算板块统计数据
            avg_change = sum(s["change_pct"] for s in sector_data) / len(sector_data)
            total_volume = sum(s["volume"] for s in sector_data)
            total_turnover = sum(s["turnover"] for s in sector_data)
            avg_pe = sum(s["pe_ratio"] for s in sector_data if s["pe_ratio"] > 0) / max(
                1, len([s for s in sector_data if s["pe_ratio"] > 0])
            )
            avg_pb = sum(s["pb_ratio"] for s in sector_data if s["pb_ratio"] > 0) / max(
                1, len([s for s in sector_data if s["pb_ratio"] > 0])
            )
            avg_volume_ratio = sum(s["volume_ratio"] for s in sector_data) / len(sector_data)
            total_market_cap = sum(s["market_cap"] for s in sector_data if s["market_cap"] > 0)

            # 计算板块强度指标
            strength_score = calculate_sector_strength(sector_data)

            sector_analysis[sector] = {
                "stock_count": len(stocks),
                "sample_count": len(sector_data),
                "avg_change_pct": round(avg_change, 2),
                "total_volume": total_volume,
                "total_turnover": total_turnover,
                "avg_pe_ratio": round(avg_pe, 2),
                "avg_pb_ratio": round(avg_pb, 2),
                "avg_volume_ratio": round(avg_volume_ratio, 2),
                "total_market_cap": total_market_cap,
                "strength_score": strength_score,
                "top_stocks": sorted(sector_data, key=lambda x: x["change_pct"], reverse=True)[:5],
                "value_stocks": sorted(
                    [s for s in sector_data if s["pe_ratio"] > 0], key=lambda x: x["pe_ratio"]
                )[:3],
            }

            print(f"  板块股票数量: {format_number(len(stocks))}")
            print(f"  平均涨跌幅: {avg_change:+.2f}%")
            print(f"  总成交量: {format_number(total_volume)}")
            print(f"  总成交额: {format_number(total_turnover)}")
            print(f"  平均市盈率: {avg_pe:.2f}")
            print(f"  平均市净率: {avg_pb:.2f}")
            print(f"  平均量比: {avg_volume_ratio:.2f}")
            print(f"  板块强度: {strength_score:.2f}")

    return sector_analysis


def calculate_sector_strength(sector_data: List[Dict[str, Any]]) -> float:
    """计算板块强度指标

    Args:
        sector_data: 板块股票数据列表

    Returns:
        float: 板块强度评分 (0-100)
    """
    if not sector_data:
        print("  无法计算板块强度：板块数据为空")
        print("  请确保板块包含有效的股票数据")
        print("  建议检查API连接状态和板块查询参数")
        return 0.0
    
    # 检查数据完整性
    required_fields = ["change_pct", "volume_ratio"]
    incomplete_data = []
    
    for i, stock in enumerate(sector_data):
        missing_fields = [field for field in required_fields if field not in stock or stock[field] is None]
        if missing_fields:
            incomplete_data.append(f"股票{i+1}: 缺少{missing_fields}")
    
    if incomplete_data:
        print(f"  板块强度计算警告：部分数据不完整")
        for warning in incomplete_data[:3]:  # 只显示前3个警告
            print(f"    {warning}")
        if len(incomplete_data) > 3:
            print(f"    ... 还有{len(incomplete_data)-3}个类似问题")
        print("  数据不完整可能的原因：")
        print("    - API返回的数据格式不完整")
        print("    - 部分股票停牌或数据缺失")
        print("    - 数据源配置问题")
    
    # 过滤有效数据
    valid_data = []
    for stock in sector_data:
        if (stock.get("change_pct") is not None and 
            stock.get("volume_ratio") is not None and
            isinstance(stock.get("change_pct"), (int, float)) and
            isinstance(stock.get("volume_ratio"), (int, float))):
            valid_data.append(stock)
    
    if not valid_data:
        print("  无法计算板块强度：没有有效的股票数据")
        print("  需要包含'change_pct'和'volume_ratio'字段的完整数据")
        print("  建议检查：")
        print("    - 数据源是否正常返回股票行情数据")
        print("    - API接口是否包含涨跌幅和成交量比率信息")
        print("    - 查询的板块是否包含正常交易的股票")
        return 0.0
    
    if len(valid_data) < len(sector_data) * 0.5:
        print(f"  板块强度计算警告：有效数据量不足（{len(valid_data)}/{len(sector_data)}）")
        print("  计算结果可能不够准确")
        print("  建议：")
        print("    - 检查数据质量和完整性")
        print("    - 考虑选择包含更多活跃股票的板块")
        print("    - 验证API返回数据的格式和内容")
    
    # 检查数据量是否足够进行可靠计算
    if len(valid_data) < 3:
        print(f"  板块强度计算警告：有效股票数量过少（{len(valid_data)}只）")
        print("  至少需要3只股票才能进行可靠的板块强度计算")
        print("  当前计算结果仅供参考")

    try:
        # 涨跌幅权重 (40%)
        avg_change = sum(s["change_pct"] for s in valid_data) / len(valid_data)
        change_score = max(0, min(100, (avg_change + 10) * 5))  # 标准化到0-100

        # 成交量比权重 (30%)
        avg_volume_ratio = sum(s["volume_ratio"] for s in valid_data) / len(valid_data)
        volume_score = max(0, min(100, avg_volume_ratio * 50))  # 标准化到0-100

        # 上涨股票比例权重 (30%)
        rising_stocks = len([s for s in valid_data if s["change_pct"] > 0])
        rising_ratio = rising_stocks / len(valid_data)
        rising_score = rising_ratio * 100

        # 综合评分
        strength_score = change_score * 0.4 + volume_score * 0.3 + rising_score * 0.3

        return round(strength_score, 2)
    
    except Exception as e:
        print(f"  板块强度计算出错：{e}")
        print("  请检查数据格式和数值有效性")
        return 0.0


def build_portfolio_demo(sector_analysis: Dict[str, Any]):
    """演示基于板块分析的投资组合构建

    Args:
        sector_analysis: 板块分析结果
    """
    print_subsection_header("投资组合构建示例")

    if not sector_analysis:
        print("无板块分析数据，无法构建投资组合")
        return

    # 按不同指标排序板块
    sorted_by_performance = sorted(
        sector_analysis.items(), key=lambda x: x[1]["avg_change_pct"], reverse=True
    )

    sorted_by_strength = sorted(
        sector_analysis.items(), key=lambda x: x[1]["strength_score"], reverse=True
    )

    sorted_by_value = sorted(
        sector_analysis.items(),
        key=lambda x: x[1]["avg_pe_ratio"] if x[1]["avg_pe_ratio"] > 0 else 999,
        reverse=False,
    )

    print("板块表现排名:")
    for i, (sector, data) in enumerate(sorted_by_performance, 1):
        print(
            f"  {i}. {sector}: {data['avg_change_pct']:+.2f}% "
            f"(强度: {data['strength_score']:.1f}, PE: {data['avg_pe_ratio']:.1f}, "
            f"成交额: {format_number(data['total_turnover'])})"
        )

    # 构建多种投资组合策略
    print("\n投资组合构建策略:")

    # 策略1: 动量策略 - 选择表现最好的板块
    print("\n1. 动量策略投资组合:")
    momentum_portfolio = build_momentum_portfolio(sorted_by_performance, sector_analysis)
    display_portfolio(momentum_portfolio, "动量策略")

    # 策略2: 均衡策略 - 平衡不同板块
    print("\n2. 均衡策略投资组合:")
    balanced_portfolio = build_balanced_portfolio(sorted_by_performance, sector_analysis)
    display_portfolio(balanced_portfolio, "均衡策略")

    # 策略3: 价值策略 - 选择被低估的板块
    print("\n3. 价值策略投资组合:")
    value_portfolio = build_value_portfolio(sorted_by_value, sector_analysis)
    display_portfolio(value_portfolio, "价值策略")

    # 策略4: 强度策略 - 基于板块强度指标
    print("\n4. 强度策略投资组合:")
    strength_portfolio = build_strength_portfolio(sorted_by_strength, sector_analysis)
    display_portfolio(strength_portfolio, "强度策略")

    # 策略5: 防御策略 - 低波动稳健投资
    print("\n5. 防御策略投资组合:")
    defensive_portfolio = build_defensive_portfolio(sector_analysis)
    display_portfolio(defensive_portfolio, "防御策略")

    # 策略6: 成长策略 - 高成长潜力板块
    print("\n6. 成长策略投资组合:")
    growth_portfolio = build_growth_portfolio(sector_analysis)
    display_portfolio(growth_portfolio, "成长策略")

    # 投资组合对比分析
    print("\n投资组合对比分析:")
    portfolios = {
        "动量策略": momentum_portfolio,
        "均衡策略": balanced_portfolio,
        "价值策略": value_portfolio,
        "强度策略": strength_portfolio,
        "防御策略": defensive_portfolio,
        "成长策略": growth_portfolio,
    }

    compare_portfolios(portfolios)

    # 投资组合风险分析
    print("\n投资组合风险分析:")
    for name, portfolio in portfolios.items():
        analyze_portfolio_risk(portfolio, name)


def build_momentum_portfolio(
    sorted_sectors: List[tuple], sector_analysis: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """构建动量策略投资组合

    Args:
        sorted_sectors: 按表现排序的板块列表

    Returns:
        List[Dict]: 投资组合
    """
    portfolio = []
    # 选择表现最好的3个板块
    top_sectors = sorted_sectors[:3]

    for i, (sector, data) in enumerate(top_sectors):
        # 权重分配：第一名40%，第二名35%，第三名25%
        weights = [40, 35, 25]
        sector_weight = weights[i]

        # 从每个板块选择表现最好的2只股票
        selected_stocks = data["top_stocks"][:2]
        stock_weight = sector_weight / len(selected_stocks)

        for stock in selected_stocks:
            portfolio.append(
                {
                    "sector": sector,
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "change_pct": stock["change_pct"],
                    "current_price": stock["current_price"],
                    "weight": round(stock_weight, 1),
                    "strategy": "momentum",
                }
            )

    return portfolio


def build_balanced_portfolio(sorted_sectors: List[tuple], sector_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建均衡策略投资组合

    Args:
        sorted_sectors: 按表现排序的板块列表

    Returns:
        List[Dict]: 投资组合
    """
    portfolio = []
    # 选择不同表现的板块进行均衡配置
    if len(sorted_sectors) >= 5:
        selected_sectors = [
            sorted_sectors[0],  # 最好
            sorted_sectors[1],  # 次好
            sorted_sectors[len(sorted_sectors) // 2],  # 中等
            sorted_sectors[-2],  # 次差
            sorted_sectors[-1],  # 最差
        ]
    else:
        selected_sectors = sorted_sectors

    # 平均权重分配
    sector_weight = 100 / len(selected_sectors)

    for sector, data in selected_sectors:
        # 从每个板块选择1只代表性股票
        if data["top_stocks"]:
            stock = data["top_stocks"][0]
            portfolio.append(
                {
                    "sector": sector,
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "change_pct": stock["change_pct"],
                    "current_price": stock["current_price"],
                    "weight": round(sector_weight, 1),
                    "strategy": "balanced",
                }
            )

    return portfolio


def build_value_portfolio(sorted_sectors: List[tuple], sector_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建价值策略投资组合

    Args:
        sorted_sectors: 按表现排序的板块列表

    Returns:
        List[Dict]: 投资组合
    """
    portfolio = []
    # 选择表现较差但可能被低估的板块
    if len(sorted_sectors) >= 3:
        # 选择排名后50%的板块
        underperform_sectors = sorted_sectors[len(sorted_sectors) // 2 :]
        selected_sectors = underperform_sectors[:3]  # 最多选3个
    else:
        selected_sectors = sorted_sectors[-2:] if len(sorted_sectors) >= 2 else sorted_sectors

    # 权重分配：相对均衡但略微倾向于跌幅较小的
    total_weight = 100
    sector_weights = []

    for i, (sector, data) in enumerate(selected_sectors):
        # 跌幅越小权重越高
        base_weight = total_weight / len(selected_sectors)
        # 调整权重：跌幅小的增加权重
        adjustment = (data["avg_change_pct"] + 10) / 20  # 标准化到0-1
        adjusted_weight = base_weight * (0.8 + 0.4 * adjustment)
        sector_weights.append(adjusted_weight)

    # 标准化权重
    total_adjusted = sum(sector_weights)
    sector_weights = [w / total_adjusted * 100 for w in sector_weights]

    for i, (sector, data) in enumerate(selected_sectors):
        # 从每个板块选择1-2只股票
        selected_stocks = data["top_stocks"][:2]
        stock_weight = sector_weights[i] / len(selected_stocks)

        for stock in selected_stocks:
            portfolio.append(
                {
                    "sector": sector,
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "change_pct": stock["change_pct"],
                    "current_price": stock["current_price"],
                    "weight": round(stock_weight, 1),
                    "strategy": "value",
                }
            )

    return portfolio


def display_portfolio(portfolio: List[Dict[str, Any]], strategy_name: str):
    """显示投资组合详情

    Args:
        portfolio: 投资组合
        strategy_name: 策略名称
    """
    if not portfolio:
        print(f"  {strategy_name}: 无法构建投资组合")
        return

    print(f"  {strategy_name}组合详情:")
    total_weight = 0
    total_expected_return = 0

    for stock in portfolio:
        print(
            f"    {stock['symbol']} ({stock['name']}) - "
            f"板块: {stock['sector']}, 权重: {stock['weight']}%, "
            f"涨跌: {stock['change_pct']:+.2f}%, "
            f"价格: {stock['current_price']:.2f}"
        )
        total_weight += stock["weight"]
        total_expected_return += stock["change_pct"] * stock["weight"] / 100

    print(f"    总权重: {total_weight:.1f}%")
    print(f"    预期收益: {total_expected_return:+.2f}%")


def analyze_portfolio_risk(portfolio: List[Dict[str, Any]], strategy_name: str):
    """分析投资组合风险

    Args:
        portfolio: 投资组合
        strategy_name: 策略名称
    """
    if not portfolio:
        return

    # 计算风险指标
    returns = [stock["change_pct"] for stock in portfolio]
    weights = [stock["weight"] / 100 for stock in portfolio]

    # 加权平均收益
    weighted_return = sum(r * w for r, w in zip(returns, weights))

    # 收益波动性（简化计算）
    volatility = (sum((r - weighted_return) ** 2 * w for r, w in zip(returns, weights))) ** 0.5

    # 板块集中度
    sector_weights = {}
    for stock in portfolio:
        sector = stock["sector"]
        sector_weights[sector] = sector_weights.get(sector, 0) + stock["weight"]

    max_sector_weight = max(sector_weights.values()) if sector_weights else 0
    sector_count = len(sector_weights)

    print(f"  {strategy_name}风险分析:")
    print(f"    预期收益: {weighted_return:+.2f}%")
    print(f"    收益波动: {volatility:.2f}%")
    print(f"    板块数量: {sector_count}")
    print(f"    最大板块权重: {max_sector_weight:.1f}%")

    # 风险评级
    risk_level = "低"
    if volatility > 5 or max_sector_weight > 50:
        risk_level = "高"
    elif volatility > 3 or max_sector_weight > 35:
        risk_level = "中"

    print(f"    风险等级: {risk_level}")


def advanced_sector_comparison(sector_analysis: Dict[str, Any]):
    """高级板块比较分析

    Args:
        sector_analysis: 板块分析结果
    """
    print_subsection_header("高级板块比较分析")

    if not sector_analysis:
        print("无板块分析数据")
        return

    # 计算相关性分析
    print("板块相关性分析:")
    sectors = list(sector_analysis.keys())

    for i, sector1 in enumerate(sectors):
        for sector2 in sectors[i + 1 :]:
            # 简化的相关性计算（基于涨跌幅）
            corr = calculate_sector_correlation(sector_analysis[sector1], sector_analysis[sector2])
            print(f"  {sector1} vs {sector2}: 相关性 {corr:.2f}")

    # 资金流向分析
    print("\n资金流向分析:")
    sorted_by_volume = sorted(
        sector_analysis.items(), key=lambda x: x[1]["total_turnover"], reverse=True
    )

    print("成交额排名:")
    for i, (sector, data) in enumerate(sorted_by_volume, 1):
        flow_status = "流入" if data["avg_change_pct"] > 0 else "流出"
        print(f"  {i}. {sector}: {format_number(data['total_turnover'])} ({flow_status})")

    # 强弱势分析
    print("\n板块强弱势分析:")
    analyze_sector_strength(sector_analysis)


def calculate_sector_correlation(sector1_data: Dict, sector2_data: Dict) -> float:
    """计算板块间相关性（简化版）

    Args:
        sector1_data: 板块1数据
        sector2_data: 板块2数据

    Returns:
        float: 相关性系数
    """
    if not sector1_data or not sector2_data:
        print("  无法计算板块相关性：板块数据为空")
        print("  请确保两个板块都包含有效的分析数据")
        print("  建议检查板块数据获取过程是否正常")
        return 0.0
    
    # 检查必要字段
    required_fields = ["avg_change_pct", "total_volume"]
    
    for i, (name, data) in enumerate([("板块1", sector1_data), ("板块2", sector2_data)], 1):
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        if missing_fields:
            print(f"  无法计算板块相关性：{name}缺少必要字段 {missing_fields}")
            print("  需要包含'avg_change_pct'和'total_volume'字段的完整数据")
            print("  建议检查板块分析函数是否正确计算了这些指标")
            return 0.0
    
    try:
        # 简化的相关性计算，基于涨跌幅和成交量
        change1 = sector1_data["avg_change_pct"]
        change2 = sector2_data["avg_change_pct"]
        volume1 = sector1_data["total_volume"]
        volume2 = sector2_data["total_volume"]
        
        # 数据有效性检查
        if not all(isinstance(val, (int, float)) for val in [change1, change2, volume1, volume2]):
            print("  板块相关性计算警告：数据类型不正确")
            print("  涨跌幅和成交量应为数值类型")
            print("  请检查板块数据计算过程中的数据类型转换")
            return 0.0
        
        if volume1 <= 0 or volume2 <= 0:
            print("  板块相关性计算警告：成交量数据无效")
            print("  成交量应为正数")
            print("  可能的原因：")
            print("    - 板块内股票全部停牌")
            print("    - 数据源未提供成交量信息")
            print("    - 数据计算过程中出现错误")
            return 0.0
        
        # 检查数据合理性
        if abs(change1) > 50 or abs(change2) > 50:
            print("  板块相关性计算警告：涨跌幅数据异常")
            print(f"  板块1涨跌幅: {change1:.2f}%, 板块2涨跌幅: {change2:.2f}%")
            print("  请检查数据是否正确或是否存在异常情况")

        # 标准化数据
        change_corr = 1 - abs(change1 - change2) / 20  # 假设最大差异20%
        volume_corr = 1 - abs(volume1 - volume2) / max(volume1, volume2, 1)

        # 综合相关性
        correlation = (change_corr + volume_corr) / 2
        return max(0, min(1, correlation))
    
    except Exception as e:
        print(f"  板块相关性计算出错：{e}")
        print("  请检查数据格式和数值有效性")
        print("  建议：")
        print("    - 验证输入数据的结构和类型")
        print("    - 检查是否存在空值或异常值")
        print("    - 确认板块分析数据的计算逻辑")
        return 0.0


def analyze_sector_strength(sector_analysis: Dict[str, Any]):
    """分析板块强弱势

    Args:
        sector_analysis: 板块分析结果
    """
    for sector, data in sector_analysis.items():
        change_pct = data["avg_change_pct"]
        volume = data["total_volume"]
        turnover = data["total_turnover"]

        # 强弱势判断
        if change_pct > 2 and volume > 5000000:
            strength = "强势"
            emoji = "🚀"
        elif change_pct > 0 and volume > 2000000:
            strength = "偏强"
            emoji = "📈"
        elif change_pct < -2 or volume < 1000000:
            strength = "弱势"
            emoji = "📉"
        else:
            strength = "中性"
            emoji = "➡️"

        print(
            f"  {emoji} {sector}: {strength} "
            f"(涨跌: {change_pct:+.2f}%, 成交量: {format_number(volume)})"
        )


def sector_rotation_monitor_demo(sectors: List[str]):
    """演示板块轮动监控

    Args:
        sectors: 要监控的板块列表
    """
    print_subsection_header("板块轮动监控演示")

    print("正在监控板块轮动情况...")
    rotation_data = []

    for sector in sectors:
        print(f"\n监控板块: {sector}")

        # 获取板块成分股（限制数量以提高性能）
        stocks = get_sector_stocks_demo(sector)
        if not stocks:
            continue

        # 选择代表性股票进行监控
        sample_stocks = stocks[:3]  # 每个板块监控3只股票
        sector_performance = []

        for stock in sample_stocks:
            if isinstance(stock, dict):
                stock_symbol = stock.get("symbol", stock.get("code", str(stock)))
            else:
                stock_symbol = str(stock)

            # 获取实时行情
            market_result = safe_api_call(api_client, api_client.get_latest_market, [stock_symbol])
            if market_result.get("code") != 0:
                print(f"  无法获取 {stock_symbol} 的行情数据: {market_result.get('message', '未知错误')}")
                print("  请检查网络连接和API配置，确保数据服务可用")
                print("  确认您的API密钥和访问权限是否正确设置")
                continue

            if market_result.get("code") == 0:
                stock_data = market_result["data"]
                if isinstance(stock_data, dict) and stock_symbol in stock_data:
                    stock_data = stock_data[stock_symbol]

                sector_performance.append(
                    {
                        "symbol": stock_symbol,
                        "name": stock_data.get("name", stock_symbol),
                        "change_pct": stock_data.get("change_pct", 0),
                        "volume_ratio": stock_data.get("volume_ratio", 1.0),
                        "turnover_rate": stock_data.get("turnover_rate", 0),
                    }
                )

                print(
                    f"  {stock_symbol} ({stock_data.get('name', stock_symbol)}): "
                    f"{stock_data.get('change_pct', 0):+.2f}%, "
                    f"量比: {stock_data.get('volume_ratio', 1.0):.2f}"
                )

        if sector_performance:
            # 计算板块整体表现
            avg_change = sum(s["change_pct"] for s in sector_performance) / len(sector_performance)
            avg_volume_ratio = sum(s["volume_ratio"] for s in sector_performance) / len(
                sector_performance
            )

            rotation_data.append(
                {
                    "sector": sector,
                    "avg_change_pct": avg_change,
                    "avg_volume_ratio": avg_volume_ratio,
                    "momentum_score": avg_change * avg_volume_ratio,  # 简单的动量评分
                }
            )

            print(f"  板块平均涨跌: {avg_change:+.2f}%")
            print(f"  板块平均量比: {avg_volume_ratio:.2f}")

    # 板块轮动分析
    if rotation_data:
        print("\n板块轮动分析结果:")
        rotation_data.sort(key=lambda x: x["momentum_score"], reverse=True)

        print("板块动量排名 (涨跌幅 × 量比):")
        for i, data in enumerate(rotation_data, 1):
            status = (
                "🔥" if data["momentum_score"] > 2 else "📈" if data["momentum_score"] > 0 else "📉"
            )
            print(
                f"  {i}. {status} {data['sector']}: "
                f"动量评分 {data['momentum_score']:+.2f} "
                f"(涨跌: {data['avg_change_pct']:+.2f}%, 量比: {data['avg_volume_ratio']:.2f})"
            )

        # 轮动建议
        print("\n板块轮动建议:")
        hot_sectors = [d for d in rotation_data if d["momentum_score"] > 1]
        cold_sectors = [d for d in rotation_data if d["momentum_score"] < -1]

        if hot_sectors:
            print("  热点板块 (建议关注):")
            for sector_data in hot_sectors:
                print(f"    • {sector_data['sector']}")

        if cold_sectors:
            print("  冷门板块 (谨慎操作):")
            for sector_data in cold_sectors:
                print(f"    • {sector_data['sector']}")

        if not hot_sectors and not cold_sectors:
            print("  当前市场相对平衡，建议保持观望")


def build_strength_portfolio(
    sorted_by_strength: List[tuple], sector_analysis: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """构建强度策略投资组合

    Args:
        sorted_by_strength: 按强度排序的板块列表
        sector_analysis: 板块分析结果

    Returns:
        List[Dict]: 投资组合
    """
    portfolio = []
    # 选择强度最高的3个板块
    top_sectors = sorted_by_strength[:3]

    for i, (sector, data) in enumerate(top_sectors):
        # 权重分配：基于强度评分的动态权重
        strength_score = data["strength_score"]
        base_weight = 100 / len(top_sectors)  # 基础权重

        # 根据强度评分调整权重
        strength_factor = strength_score / 100  # 标准化强度评分
        adjusted_weight = base_weight * (0.8 + 0.4 * strength_factor)

        # 从每个板块选择强度指标最好的股票
        # 优先选择涨幅适中但量比较高的股票
        sector_stocks = data["top_stocks"]
        selected_stocks = []

        for stock in sector_stocks:
            # 计算股票强度评分（涨幅 + 量比）
            stock_strength = stock["change_pct"] * 0.6 + stock.get("volume_ratio", 1.0) * 20 * 0.4
            stock["stock_strength"] = stock_strength

        # 按股票强度排序，选择前2只
        sector_stocks.sort(key=lambda x: x.get("stock_strength", 0), reverse=True)
        selected_stocks = sector_stocks[:2]

        stock_weight = adjusted_weight / len(selected_stocks)

        for stock in selected_stocks:
            portfolio.append(
                {
                    "sector": sector,
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "change_pct": stock["change_pct"],
                    "current_price": stock["current_price"],
                    "volume_ratio": stock.get("volume_ratio", 1.0),
                    "strength_score": stock.get("stock_strength", 0),
                    "weight": round(stock_weight, 1),
                    "strategy": "strength",
                }
            )

    return portfolio


def build_defensive_portfolio(sector_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建防御策略投资组合

    Args:
        sector_analysis: 板块分析结果

    Returns:
        List[Dict]: 投资组合
    """
    portfolio = []

    # 选择低波动、稳健的板块（银行、公用事业等）
    defensive_sectors = []
    for sector, data in sector_analysis.items():
        # 防御性板块特征：涨跌幅相对稳定，PE较低
        avg_change = abs(data["avg_change_pct"])
        avg_pe = data.get("avg_pe_ratio", 20)

        # 计算防御性评分
        stability_score = max(0, 10 - avg_change)  # 波动越小评分越高
        value_score = max(0, 30 - avg_pe) / 3  # PE越低评分越高
        defensive_score = stability_score + value_score

        defensive_sectors.append((sector, data, defensive_score))

    # 按防御性评分排序，选择前3个
    defensive_sectors.sort(key=lambda x: x[2], reverse=True)
    selected_sectors = defensive_sectors[:3]

    # 平均权重分配
    sector_weight = 100 / len(selected_sectors)

    for sector, data, score in selected_sectors:
        # 从每个板块选择1-2只最稳健的股票
        sector_stocks = data["top_stocks"]

        # 选择涨跌幅相对稳定的股票
        stable_stocks = []
        for stock in sector_stocks:
            if abs(stock["change_pct"]) <= 3:  # 涨跌幅不超过3%
                stable_stocks.append(stock)

        # 如果没有稳定的股票，选择涨跌幅最小的
        if not stable_stocks:
            stable_stocks = sorted(sector_stocks, key=lambda x: abs(x["change_pct"]))[:2]
        else:
            stable_stocks = stable_stocks[:2]

        stock_weight = sector_weight / len(stable_stocks)

        for stock in stable_stocks:
            portfolio.append(
                {
                    "sector": sector,
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "change_pct": stock["change_pct"],
                    "current_price": stock["current_price"],
                    "defensive_score": score,
                    "weight": round(stock_weight, 1),
                    "strategy": "defensive",
                }
            )

    return portfolio


def build_growth_portfolio(sector_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建成长策略投资组合

    Args:
        sector_analysis: 板块分析结果

    Returns:
        List[Dict]: 投资组合
    """
    portfolio = []

    # 选择高成长潜力的板块（科技、新能源等）
    growth_sectors = []
    for sector, data in sector_analysis.items():
        # 成长性板块特征：涨幅较高，成交活跃
        avg_change = data["avg_change_pct"]
        avg_volume_ratio = data.get("avg_volume_ratio", 1.0)
        total_turnover = data["total_turnover"]

        # 计算成长性评分
        momentum_score = max(0, avg_change * 2)  # 涨幅贡献
        activity_score = min(10, avg_volume_ratio * 3)  # 活跃度贡献
        scale_score = min(5, total_turnover / 1000000000)  # 规模贡献
        growth_score = momentum_score + activity_score + scale_score

        growth_sectors.append((sector, data, growth_score))

    # 按成长性评分排序，选择前3个
    growth_sectors.sort(key=lambda x: x[2], reverse=True)
    selected_sectors = growth_sectors[:3]

    for i, (sector, data, score) in enumerate(selected_sectors):
        # 权重分配：成长性越高权重越大
        base_weight = 100 / len(selected_sectors)
        growth_factor = score / max(1, max(s[2] for s in selected_sectors))
        adjusted_weight = base_weight * (0.7 + 0.6 * growth_factor)

        # 从每个板块选择成长性最好的股票
        sector_stocks = data["top_stocks"]

        # 选择涨幅较高且成交活跃的股票
        growth_stocks = []
        for stock in sector_stocks:
            if stock["change_pct"] > 0 and stock.get("volume_ratio", 1.0) > 1.2:
                growth_stocks.append(stock)

        # 如果没有符合条件的股票，选择涨幅最高的
        if not growth_stocks:
            growth_stocks = sorted(sector_stocks, key=lambda x: x["change_pct"], reverse=True)[:2]
        else:
            growth_stocks = growth_stocks[:2]

        stock_weight = adjusted_weight / len(growth_stocks)

        for stock in growth_stocks:
            portfolio.append(
                {
                    "sector": sector,
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "change_pct": stock["change_pct"],
                    "current_price": stock["current_price"],
                    "volume_ratio": stock.get("volume_ratio", 1.0),
                    "growth_score": score,
                    "weight": round(stock_weight, 1),
                    "strategy": "growth",
                }
            )

    return portfolio


def compare_portfolios(portfolios: Dict[str, List[Dict[str, Any]]]):
    """对比分析多个投资组合

    Args:
        portfolios: 投资组合字典
    """
    print_subsection_header("投资组合对比分析")

    comparison_data = []

    for name, portfolio in portfolios.items():
        if not portfolio:
            continue

        # 计算组合统计数据
        total_return = sum(stock["change_pct"] * stock["weight"] / 100 for stock in portfolio)
        total_weight = sum(stock["weight"] for stock in portfolio)
        stock_count = len(portfolio)

        # 计算板块分散度
        sectors = set(stock["sector"] for stock in portfolio)
        sector_count = len(sectors)

        # 计算最大单一持仓权重
        max_weight = max(stock["weight"] for stock in portfolio) if portfolio else 0

        # 计算风险评分（简化）
        returns = [stock["change_pct"] for stock in portfolio]
        volatility = (
            (sum((r - total_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 0
        )

        comparison_data.append(
            {
                "name": name,
                "expected_return": total_return,
                "total_weight": total_weight,
                "stock_count": stock_count,
                "sector_count": sector_count,
                "max_weight": max_weight,
                "volatility": volatility,
                "sharpe_ratio": total_return / max(volatility, 0.1),  # 简化的夏普比率
            }
        )

    # 显示对比结果
    print("投资组合对比表:")
    print(
        f"{'策略名称':<12} {'预期收益':<8} {'股票数':<6} {'板块数':<6} {'最大权重':<8} {'波动率':<8} {'夏普比率':<8}"
    )
    print("-" * 70)

    for data in comparison_data:
        print(
            f"{data['name']:<12} {data['expected_return']:>+6.2f}% "
            f"{data['stock_count']:>6} {data['sector_count']:>6} "
            f"{data['max_weight']:>6.1f}% {data['volatility']:>6.2f}% "
            f"{data['sharpe_ratio']:>6.2f}"
        )

    # 推荐最佳组合
    print("\n组合推荐:")

    # 最高收益组合
    best_return = max(comparison_data, key=lambda x: x["expected_return"])
    print(f"  最高收益: {best_return['name']} ({best_return['expected_return']:+.2f}%)")

    # 最佳风险调整收益组合
    best_sharpe = max(comparison_data, key=lambda x: x["sharpe_ratio"])
    print(f"  最佳夏普比率: {best_sharpe['name']} ({best_sharpe['sharpe_ratio']:.2f})")

    # 最分散组合
    best_diversified = max(comparison_data, key=lambda x: x["sector_count"])
    print(f"  最佳分散: {best_diversified['name']} ({best_diversified['sector_count']}个板块)")


def main():
    """主函数 - 执行板块股票列表教程演示"""
    print_section_header("板块股票列表API 使用教程")

    try:
        # 1. 下载板块数据
        download_sector_data_demo()

        # 2. 获取板块列表
        sectors = get_sector_list_demo()

        # 3. 演示获取不同板块的成分股
        demo_sectors = ["银行", "白酒", "科技"]
        for sector in demo_sectors:
            get_sector_stocks_demo(sector)

        # 4. 获取历史成分股示例
        get_sector_stocks_demo("沪深300", "20230101")

        # 5. 板块表现分析
        sector_analysis = analyze_sector_performance(demo_sectors)

        # 6. 投资组合构建演示
        build_portfolio_demo(sector_analysis)

        # 7. 板块轮动监控演示
        monitor_sectors = ["银行", "白酒", "科技", "医药", "新能源"]
        sector_rotation_monitor_demo(monitor_sectors)

        # 8. 显示性能统计
        print_section_header("性能统计")
        performance_monitor.print_summary()

        # 9. 实际应用建议
        print_section_header("实际应用建议")
        print("板块轮动策略要点:")
        print("  • 定期监控各板块的相对强弱")
        print("  • 关注成交量变化，确认资金流向")
        print("  • 结合宏观经济和政策因素分析")
        print("  • 设置止损点，控制单一板块风险")
        print("  • 分散投资，避免过度集中")

        print("\n注意事项:")
        print("  • 板块数据更新频率相对较低，建议每日或每周更新")
        print("  • 股票代码格式为 代码.市场 (如 600519.SH, 000001.SZ)")
        print("  • 实际投资决策需要结合更多基本面和技术面分析")
        print("  • 本教程仅供学习参考，不构成投资建议")

    except Exception as e:
        print(f"教程执行过程中发生错误: {e}")
        print("请检查API服务是否正常运行，或查看错误日志获取详细信息")

    finally:
        # 清理资源
        api_client.close()
        print("\n教程执行完成")


if __name__ == "__main__":
    main()

# 操作步骤 Step-by-Step Guide

# 本教程将按以下步骤进行:
# 步骤 1: 指定目标市场
# 步骤 2: 获取完整股票列表
# 步骤 3: 分析股票分布和特征
# 步骤 4: 实施数据过滤和分类
# 步骤 5: 展示列表数据的实际应用


# 最佳实践 Best Practices

# 在实际应用中，建议遵循以下最佳实践:
# ✅ 定期更新股票列表
# ✅ 处理股票代码的标准化
# ✅ 考虑股票的流动性和市值
# ✅ 建立股票分类和标签体系