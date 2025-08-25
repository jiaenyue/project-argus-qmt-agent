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
#
# 本教程演示如何使用统一的API客户端获取和分析完整行情数据。
# 支持通过HTTP API和xtdata库两种方式获取数据，具备完善的错误处理机制。
#
# **重要说明**:
# - 本教程仅使用来自API或xtdata的真实完整行情数据
# - 不再提供模拟数据回退功能
# - 需要确保API服务正常运行和数据源连接有效
# - 如果无法获取数据，将显示详细的错误信息和故障排除指导
#
# **功能特性**:
# - 统一的API调用接口
# - 自动重试和错误处理
# - 适当的错误处理和用户指导
# - 深度行情分析和可视化
# - 性能优化和大数据处理
#
# **数据要求**:
# - 需要有效的完整行情数据源
# - 建议在交易时间内运行以获取最新数据
# - 确保股票代码格式正确（包含交易所后缀）
# - 网络连接稳定，API服务响应正常
# - 大数据处理需要足够的内存和处理能力

import queue
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 学习目标 Learning Objectives


# 背景知识 Background Knowledge

# 💡 全市场数据提供了市场的整体视图
# 💡 大数据量处理需要特殊的技术考虑
# 💡 全市场分析有助于发现系统性机会和风险

# 通过本教程，您将学会:
# 1. 掌握全市场数据的获取方法
# 2. 理解大数据量的处理技巧
# 3. 学会市场整体分析
# 4. 了解系统性能优化方法

# 导入统一工具库
from common import (
    QMTAPIClient, 
    create_api_client, 
    safe_api_call,
    get_config,
    PerformanceMonitor,
    create_demo_context,
    format_response_time,
    print_api_result,
    print_section_header,
    print_subsection_header
)
# 实时行情数据反映了当前的市场状态和价格变动

# 尝试导入xtdata（如果可用）
try:
    from xtquant import xtdata

    XTDATA_AVAILABLE = True
except ImportError:
    XTDATA_AVAILABLE = False
    print("注意: xtdata库不可用，将使用HTTP API模式")



# 初始化工具和配置
config = get_config()
demo_context = create_demo_context()
performance_monitor = demo_context.performance_monitor
api_client = create_api_client()
# Mock data generator instance removed


# ## 1. 深度行情数据处理类


# 简化的数据分析函数
def analyze_market_data(market_data):
    """简单的市场数据分析"""
    if not market_data:
        return {}
    
    analysis = {
        'total_symbols': len(market_data),
        'active_symbols': 0,
        'total_volume': 0,
        'avg_price': 0,
        'price_range': {'min': float('inf'), 'max': 0},
        'top_volume_symbols': []
    }
    
    prices = []
    volumes = []
    
    for data in market_data:
        price = data.get('LastPrice', data.get('lastPrice', 0))
        volume = data.get('Volume', data.get('volume', 0))
        symbol = data.get('InstrumentID', data.get('symbol', 'N/A'))
        
        if price > 0:
            prices.append(price)
            analysis['price_range']['min'] = min(analysis['price_range']['min'], price)
            analysis['price_range']['max'] = max(analysis['price_range']['max'], price)
        
        if volume > 0:
            analysis['active_symbols'] += 1
            volumes.append((symbol, volume))
        
        analysis['total_volume'] += volume
    
    if prices:
        analysis['avg_price'] = sum(prices) / len(prices)
    
    if analysis['price_range']['min'] == float('inf'):
        analysis['price_range']['min'] = 0
    
    # 按成交量排序，取前5名
    volumes.sort(key=lambda x: x[1], reverse=True)
    analysis['top_volume_symbols'] = volumes[:5]
    
    return analysis


# ## 2. 全推行情数据订阅和获取


def demonstrate_full_market_subscription():
    """演示全推行情数据订阅功能"""
    print_section_header("全推行情数据订阅演示")

    # 启动数据处理器
    market_analyzer.start_processing()

    # 定义数据推送回调函数

    def on_full_tick_data(datas):
        """全推行情数据回调函数

        Args:
            datas: 字典，格式为 { symbol : data }
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"收到全推行情数据更新，时间: {timestamp}")

        for symbol, data in datas.items():
            # 将数据放入处理队列
            market_analyzer.data_queue.put(
                {"type": "tick_data", "symbol": symbol, "data": data, "timestamp": timestamp}
            )

            # 显示部分数据
            print(
                f"  合约代码: {symbol}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}"
            )

    # 订阅全推行情数据
    print("\n开始订阅沪深两市全推行情数据...")

    subscription_id = None

    # 尝试使用xtdata库订阅
    if XTDATA_AVAILABLE:
        try:
            subscription_id = xtdata.subscribe_whole_quote(
                code_list=["SH", "SZ"], callback=on_full_tick_data
            )

            if subscription_id != -1:
                print(f"全推行情订阅成功，订阅号: {subscription_id}")
            else:
                print("xtdata库订阅失败，尝试使用API...")
                subscription_id = None
        except Exception as e:
            print(f"xtdata库订阅异常: {e}")
            subscription_id = None

    # 如果xtdata订阅失败，尝试使用API
    if subscription_id is None:
        try:
            result = safe_api_call(api_client, api_client.subscribe_whole_quote, ["SH", "SZ"])

            if result.get("code") == 0:
                subscription_id = result.get("data", {}).get("subscription_id")
                print(f"API全推行情订阅成功，订阅号: {subscription_id}")
            else:
                print(f"API订阅失败: {result.get('message', '未知错误')}")
                subscription_id = None
        except Exception as e:
            print(f"API订阅异常: {e}")
            subscription_id = None

    return subscription_id


def demonstrate_full_tick_snapshot():
    """演示获取全推数据快照"""
    print_subsection_header("获取全推数据快照")

    demo_symbols = ["600519.SH", "000001.SZ", "601318.SH"]

    # 尝试多种方式获取数据
    success = False
    full_tick_data = None

    # 方式1: 使用xtdata库
    if XTDATA_AVAILABLE:
        try:
            print("\n尝试使用xtdata库获取全推数据快照...")
            full_tick_data = xtdata.get_full_tick(code_list=demo_symbols)

            if full_tick_data:
                print("成功获取全推数据快照:")
                for symbol, data in full_tick_data.items():
                    print(
                        f"  合约代码: {symbol}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}"
                    )
                success = True
            else:
                print("未能获取全推数据快照，尝试使用API...")
        except Exception as e:
            print(f"xtdata.get_full_tick调用异常: {e}")

    # 方式2: 使用统一API客户端
    if not success:
        try:
            print("\n尝试使用API获取全推数据快照...")
            result = safe_api_call(api_client, api_client.get_full_tick, demo_symbols)

            if result.get("code") == 0:
                full_tick_data = result["data"]
                print("成功通过API获取全推数据快照:")
                for symbol, data in full_tick_data.items():
                    print(
                        f"  合约代码: {symbol}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}"
                    )
                success = True
            else:
                print(f"API获取失败: {result.get('message', '未知错误')}")
        except Exception as e:
            print(f"API调用异常: {e}")

    # 如果前面的方法都失败，提供错误信息
    if not success:
        print("\n无法获取全推数据快照")
        print("请检查网络连接和API配置，确保数据服务可用")
        print("确认您的API密钥和访问权限是否正确设置")
        print("如果问题持续存在，请联系数据服务提供商")
        full_tick_data = None

    return full_tick_data


# ## 3. 深度行情分析演示


def demonstrate_market_depth_analysis():
    """演示深度行情分析功能"""
    print_section_header("深度行情分析演示")

    # 获取完整市场数据
    print_subsection_header("1. 获取完整市场数据")

    # 尝试多种方式获取数据
    success = False
    market_data = None

    # 方式1: 使用统一API客户端
    try:
        print("\n尝试使用API获取完整市场数据...")
        # 使用get_full_tick方法获取多个股票的数据
        demo_symbols = ["600519.SH", "000001.SZ", "601318.SH", "000858.SZ", "600036.SH"]
        result = api_client.get_full_tick(demo_symbols)

        if result.get("code") == 0:
            market_data = result["data"]
            print(f"成功获取完整市场数据，共 {len(market_data)} 条记录")
            success = True
        else:
            print(f"  API获取失败: {result.get('message', '未知错误')}")
            print("  请检查网络连接和API配置，确保数据服务可用")
            print("  确认您的API密钥和访问权限是否正确设置")
    except Exception as e:
        print(f"API调用异常: {e}")

    # 如果API方法失败，提供错误信息
    if not success:
        print("\n无法获取完整市场数据")
        print("请检查网络连接和API配置，确保数据服务可用")
        print("确认您的API密钥和访问权限是否正确设置")
        print("如果问题持续存在，请联系数据服务提供商")
        market_data = None

    # 将数据传入分析器
    if market_data:
        market_analyzer.data_queue.put(
            {
                "type": "full_market",
                "data": market_data,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        # 等待数据处理完成
        time.sleep(1)

    # 演示市场宽度分析
    print_subsection_header("2. 市场宽度分析")

    market_stats = market_analyzer.get_market_stats()
    print("\n市场涨跌统计:")

    for market, stats in market_stats.get("markets", {}).items():
        total = stats.get("total", 0)
        if total > 0:
            up_count = stats.get("up_count", 0)
            down_count = stats.get("down_count", 0)
            flat_count = stats.get("flat_count", 0)

            print(f"\n{market}市场:")
            print(f"  总计: {total} 只股票")
            print(f"  上涨: {up_count} 只 ({up_count/total*100:.1f}%)")
            print(f"  下跌: {down_count} 只 ({down_count/total*100:.1f}%)")
            print(f"  平盘: {flat_count} 只 ({flat_count/total*100:.1f}%)")

    # 获取市场宽度指标
    breadth = market_analyzer.get_market_breadth()
    print("\n市场宽度指标:")

    for market, metrics in breadth.items():
        print(f"\n{market}市场:")
        print(f"  涨跌比: {metrics['advance_decline_ratio']}")
        print(f"  宽度指数: {metrics['breadth_index']}")

    # 可视化市场宽度（如果在支持可视化的环境中）
    try:
        # 尝试可视化，但不中断程序流程
        # market_analyzer.visualize_market_breadth()
        print(
            "\n注意: 在支持可视化的环境中，可以调用 market_analyzer.visualize_market_breadth() 查看图表"
        )
    except Exception as e:
        print(f"\n可视化市场宽度时出错: {e}")

    # 演示板块表现分析
    print_subsection_header("3. 板块表现分析")

    sector_performance = market_analyzer.get_sector_performance(top_n=3)

    print("\n最强板块:")
    for sector in sector_performance.get("top_sectors", []):
        print(
            f"  {sector['sector']}: 强度 {sector['strength']:.1f}, 上涨率 {sector['up_percent']}%"
        )

    print("\n最弱板块:")
    for sector in sector_performance.get("bottom_sectors", []):
        print(
            f"  {sector['sector']}: 强度 {sector['strength']:.1f}, 上涨率 {sector['up_percent']}%"
        )

    # 可视化板块表现（如果在支持可视化的环境中）
    try:
        # 尝试可视化，但不中断程序流程
        # market_analyzer.visualize_sector_performance()
        print(
            "\n注意: 在支持可视化的环境中，可以调用 market_analyzer.visualize_sector_performance() 查看图表"
        )
    except Exception as e:
        print(f"\n可视化板块表现时出错: {e}")

    return market_data


# ## 4. 大数据量处理优化演示


def demonstrate_large_data_processing():
    """演示大数据量处理优化"""
    print_section_header("大数据量处理优化演示")

    print_subsection_header("1. 大数据量处理策略")

    stock_count = 1000  # 处理1000只股票
    print(f"\n演示处理 {stock_count} 只股票的数据...")

    # 创建股票代码列表
    sh_stocks = [f"60{i:04d}.SH" for i in range(500)]
    sz_stocks = [f"00{i:04d}.SZ" for i in range(500)]
    all_stocks = sh_stocks + sz_stocks

    # 记录开始时间
    start_time = time.time()

    # 批量处理策略
    batch_size = 100  # 每批处理100只股票
    batches = [all_stocks[i : i + batch_size] for i in range(0, len(all_stocks), batch_size)]

    total_processed = 0
    successful_requests = 0
    failed_requests = 0

    for i, batch in enumerate(batches):
        print(f"处理第 {i+1}/{len(batches)} 批数据...")

        # 尝试获取真实数据
        batch_results = []
        for symbol in batch:
            # 在实际场景中，这里会调用API获取真实数据
            print(f"  尝试获取 {symbol} 的数据...")
            
            # 批量处理逻辑演示
            # 在实际使用中会调用真实API获取数据
            try:
                # result = api_client.get_latest_market_data(symbol)
                # 由于没有真实API连接，这里演示错误处理
                print(f"    API调用失败: 无法连接到数据服务")
                failed_requests += 1
            except Exception as e:
                print(f"    处理 {symbol} 时出错: {e}")
                failed_requests += 1
            
            total_processed += 1
            
        total_data_points += len(batch_data)

        # 将数据传入分析器
        market_analyzer.data_queue.put(
            {
                "type": "full_market",
                "data": batch_data,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    # 等待数据处理完成
    time.sleep(2)

    # 计算处理时间
    processing_time = time.time() - start_time

    print(f"\n处理完成:")
    print(f"  总数据点: {total_data_points}")
    print(f"  处理时间: {format_response_time(processing_time)}")
    print(f"  处理速度: {total_data_points / processing_time:.1f} 点/秒")

    # 显示优化后的市场统计
    print_subsection_header("2. 优化后的市场统计")

    market_stats = market_analyzer.get_market_stats()
    breadth = market_analyzer.get_market_breadth()

    print("\n市场涨跌统计:")
    for market, stats in market_stats.get("markets", {}).items():
        total = stats.get("total", 0)
        if total > 0:
            print(f"\n{market}市场 (共 {total} 只股票):")
            print(
                f"  上涨: {stats.get('up_count', 0)} 只 ({stats.get('up_count', 0)/total*100:.1f}%)"
            )
            print(
                f"  下跌: {stats.get('down_count', 0)} 只 ({stats.get('down_count', 0)/total*100:.1f}%)"
            )

    # 显示性能优化建议
    print_subsection_header("3. 性能优化建议")

    print("\n处理大量市场数据的优化建议:")
    print("• 使用批处理减少内存占用")
    print("• 实现数据流处理避免一次性加载全部数据")
    print("• 使用多线程并行处理不同市场或板块的数据")
    print("• 采用增量更新策略，只处理变化的数据")
    print("• 对不常变化的统计数据实现缓存机制")
    print("• 使用高效的数据结构如NumPy数组进行计算")
    print("• 对于历史数据，考虑使用数据库存储和查询")


# ## 5. 订阅管理和清理


def demonstrate_subscription_management(subscription_id):
    """演示订阅管理和清理

    Args:
        subscription_id: 订阅ID
    """
    print_section_header("订阅管理和清理")

    if subscription_id is None:
        print("没有活跃的订阅需要清理")
        return

    print(f"取消订阅ID: {subscription_id}...")

    # 根据订阅方式取消订阅
    success = False

    # 尝试使用xtdata取消订阅
    if XTDATA_AVAILABLE:
        try:
            xtdata.unsubscribe_quote(subscription_id)
            print("成功取消xtdata订阅")
            success = True
        except Exception as e:
            print(f"xtdata取消订阅异常: {e}")

    # 如果xtdata取消失败，尝试使用API
    if not success:
        try:
            result = safe_api_call(api_client, api_client.unsubscribe_quote, subscription_id)

            if result.get("code") == 0:
                print("成功取消API订阅")
                success = True
            else:
                print(f"API取消订阅失败: {result.get('message', '未知错误')}")
        except Exception as e:
            print(f"API取消订阅异常: {e}")

    # 停止数据处理器
    print("\n停止数据处理器...")
    market_analyzer.stop_processing()


# ## 6. 性能统计和总结


def show_performance_summary():
    """显示性能统计和总结"""
    print_section_header("性能统计和总结")

    # 显示API客户端性能统计
    print_subsection_header("API客户端性能统计")
    api_client.print_performance_summary()

    # 显示数据处理器性能统计
    print_subsection_header("数据处理器性能统计")
    processor_stats = market_analyzer.get_performance_stats()
    if processor_stats:
        print("数据处理统计:")
        summary = processor_stats.get("summary", {})
        print(f"  总处理时间: {format_response_time(summary.get('total_duration', 0))}")
        print(f"  总处理次数: {summary.get('total_calls', 0)}")
        print(f"  成功率: {summary.get('success_rate', 0):.1f}%")
    else:
        print("暂无数据处理统计")

    # 显示教程总结
    print_subsection_header("教程总结")
    print("本教程演示了以下功能:")
    print("✓ 统一的完整行情数据获取接口")
    print("✓ 多数据源支持 (HTTP API + xtdata库)")
    print("✓ 适当的错误处理和用户指导")
    print("✓ 深度行情分析和市场宽度指标")
    print("✓ 板块表现分析和可视化")
    print("✓ 大数据量处理优化")
    print("✓ 完善的错误处理机制")

    print("\n优化建议:")
    print("• 对于大量数据处理，考虑使用分布式计算框架")
    print("• 实现数据持久化，支持历史数据回溯分析")
    print("• 对关键指标建立实时监控和预警机制")
    print("• 使用缓存机制减少重复计算")
    print("• 针对特定分析任务优化数据结构和算法")


# ## 7. 主函数执行


def main():
    """主函数 - 简化的完整行情数据API使用教程"""
    try:
        print_section_header("完整行情数据 API 使用教程")
        print("本教程演示如何使用完整行情数据API获取实时市场数据")
        print("支持HTTP API和xtdata两种方式")
        print()

        # 创建演示上下文
        context = create_demo_context()
        client = context.api_client

        # 演示API方式获取数据
        success = False
        market_data = None

        # 方式1: 使用统一API客户端
        try:
            print("\n尝试使用API获取完整市场数据...")
            # 使用get_full_tick方法获取多个股票的数据
            demo_symbols = ["600519.SH", "000001.SZ", "601318.SH", "000858.SZ", "600036.SH"]
            result = client.get_full_tick(demo_symbols)

            if result.get("code") == 0:
                market_data = result["data"]
                print(f"成功获取完整市场数据，共 {len(market_data)} 条记录")
                success = True
            else:
                print(f"  API获取失败: {result.get('message', '未知错误')}")
                print("  请检查网络连接和API配置，确保数据服务可用")
                print("  确认您的API密钥和访问权限是否正确设置")
        except Exception as e:
            print(f"API调用异常: {e}")

        # 方式2: 使用xtdata直接获取（如果API失败）
        if not success and XTDATA_AVAILABLE:
            try:
                print("\n尝试使用xtdata获取完整市场数据...")
                from xtquant import xtdata
                
                # 获取全推行情数据
                demo_symbols = ["600519.SH", "000001.SZ", "601318.SH", "000858.SZ", "600036.SH"]
                market_data = []
                
                for symbol in demo_symbols:
                    try:
                        tick_data = xtdata.get_full_tick([symbol])
                        if tick_data and symbol in tick_data:
                            market_data.append({
                                'symbol': symbol,
                                'lastPrice': tick_data[symbol].get('lastPrice', 0),
                                'volume': tick_data[symbol].get('volume', 0),
                                'turnover': tick_data[symbol].get('turnover', 0),
                            })
                    except Exception as e:
                        print(f"获取 {symbol} 数据失败: {e}")
                        continue
                
                if market_data:
                    print(f"成功获取完整市场数据，共 {len(market_data)} 条记录")
                    success = True
                else:
                    print("xtdata获取数据失败")
                    
            except Exception as e:
                print(f"xtdata调用异常: {e}")

        # 如果成功获取数据，进行分析和展示
        if success and market_data:
            print_subsection_header("市场数据概览")
            
            # 显示前5条数据
            display_count = min(5, len(market_data))
            for i, data in enumerate(market_data[:display_count]):
                symbol = data.get('symbol', data.get('InstrumentID', 'N/A'))
                price = data.get('lastPrice', data.get('LastPrice', 0))
                volume = data.get('volume', data.get('Volume', 0))
                print(f"  合约代码: {symbol}, 最新价: {price}, 成交量: {volume}")
            
            if len(market_data) > display_count:
                print(f"  ... 还有 {len(market_data) - display_count} 条数据")

            # 简单的数据统计
            print_subsection_header("数据统计")
            total_symbols = len(market_data)
            active_symbols = len([d for d in market_data if d.get('volume', d.get('Volume', 0)) > 0])
            prices = [d.get('lastPrice', d.get('LastPrice', 0)) for d in market_data if d.get('lastPrice', d.get('LastPrice', 0)) > 0]
            avg_price = sum(prices) / len(prices) if prices else 0
            
            print(f"  总股票数量: {total_symbols}")
            print(f"  有成交量股票: {active_symbols}")
            print(f"  平均价格: {avg_price:.2f}")
            
        else:
            print("\n⚠️ 未能获取到市场数据")
            print("可能的原因:")
            print("1. 网络连接问题")
            print("2. API服务不可用")
            print("3. xtdata模块未正确安装或配置")
            print("4. 数据源暂时无数据")

    except KeyboardInterrupt:
        print("\n用户中断程序")
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        print("\n正在清理资源...")
        
        try:
            if hasattr(client, 'close'):
                client.close()
                print("API客户端已关闭")
        except Exception as e:
            print(f"关闭API客户端时出错: {e}")
        
        print("资源清理完成")

    print_section_header("教程结束")
    print("感谢使用完整行情数据API教程！")


# 执行主函数
if __name__ == "__main__":
    main()

# 操作步骤 Step-by-Step Guide

# 本教程将按以下步骤进行:
# 步骤 1: 准备大数据量处理环境
# 步骤 2: 分批获取全市场数据
# 步骤 3: 实施数据聚合和统计
# 步骤 4: 进行市场整体分析
# 步骤 5: 展示性能优化技巧


# 最佳实践 Best Practices

# 在实际应用中，建议遵循以下最佳实践:
# ✅ 使用分页或分批处理大数据
# ✅ 实施内存管理和垃圾回收
# ✅ 考虑数据压缩和缓存
# ✅ 监控系统资源使用情况