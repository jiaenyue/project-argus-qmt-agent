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
增强历史K线API 使用教程 - Project Argus QMT 数据代理服务

本教程演示如何使用增强的历史K线API获取股票的历史价格数据，
包括多周期支持、数据质量监控、缓存优化和标准化数据格式。

# 学习目标 Learning Objectives

通过本教程，您将学会:
1. 掌握增强历史K线API的使用方法
2. 理解多周期数据获取和转换机制
3. 学会数据质量验证和监控技术
4. 了解缓存机制和性能优化策略
5. 掌握标准化数据格式的使用
6. 学会异常处理和错误恢复机制

# 背景知识 Background Knowledge

💡 增强API支持8种时间周期：1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M
💡 数据质量监控包括完整性、准确性、一致性和及时性检查
💡 智能缓存根据数据周期设置不同的TTL策略
💡 标准化格式确保数据的一致性和兼容性
💡 OHLCV数据经过逻辑验证和异常检测

增强功能特性:
- 多周期支持: 支持从1分钟到月线的8种周期
- 数据质量监控: 实时监控数据完整性和准确性
- 智能缓存: 根据周期自动设置缓存策略
- 标准化格式: 统一的JSON格式和数据类型
- 错误处理: 完善的异常处理和重试机制
- 性能优化: 批量获取和并发处理支持

参数说明:
- symbol: 股票代码(格式:代码.交易所) 如 "600519.SH"
- start_date: 开始日期(YYYY-MM-DD) 如 "2023-01-01"
- end_date: 结束日期(YYYY-MM-DD) 如 "2023-12-31"
- period: K线周期(1m/5m/15m/30m/1h/1d/1w/1M) 如 "1d"
- include_quality: 是否包含质量指标 (True/False)
- normalize: 是否标准化数据格式 (True/False)

数据要求:
- 需要有效的历史数据访问权限
- 建议使用近期日期范围以确保数据可用性
- 确保股票代码格式正确（包含交易所后缀）
- 网络连接稳定，API服务响应正常
"""

import time
import asyncio
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

import numpy as np
import pandas as pd

try:
    import psutil
except ImportError:
    psutil = None

# 导入通用工具库
from common import (
    create_api_client, 
    safe_api_call,
    get_config,
    create_demo_context,
    format_number,
    format_response_time,
    print_api_result,
    print_section_header,
    print_subsection_header
)

# 导入增强API相关模块
try:
    from src.argus_mcp.api.enhanced_historical_api import (
        EnhancedHistoricalDataAPI,
        HistoricalDataRequest,
        MultiPeriodRequest,
        QualityCheckRequest
    )
    from src.argus_mcp.data_models.historical_data import SupportedPeriod
    ENHANCED_API_AVAILABLE = True
except ImportError:
    ENHANCED_API_AVAILABLE = False
    print("⚠️  增强API模块未找到，将使用基础API功能")

# 初始化工具和配置
config = get_config()
demo_context = create_demo_context()
performance_monitor = demo_context.performance_monitor
api_client = create_api_client()

# 初始化增强API（如果可用）
if ENHANCED_API_AVAILABLE:
    enhanced_api = EnhancedHistoricalDataAPI()
else:
    enhanced_api = None


# 获取历史K线数据 - 返回指定时间段的OHLCV数据
def get_hist_kline_data(
    symbol: str, start_date: str, end_date: str, frequency: str = "1d"
) -> pd.DataFrame:
    """获取历史K线数据并转换为DataFrame

    Args:
        symbol: 股票代码
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        frequency: K线周期

    Returns:
        pd.DataFrame: 历史K线数据，如果获取失败则返回空DataFrame
    """
    print_subsection_header(f"获取 {symbol} 历史K线数据")
    print(f"  时间范围: {start_date} 至 {end_date}")
    print(f"  数据周期: {frequency}")

    # 调用API获取数据
    try:
        # 获取历史K线数据 - 返回指定时间段的OHLCV数据
        result = api_client.get_hist_kline(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
        )
    except Exception as e:
        result = {"code": -1, "message": str(e), "data": None}

    if result.get("code") != 0:
        print(f"  API调用失败: {result.get('message', '未知错误')}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  确认您的API密钥和访问权限是否正确设置")
        print("  如果问题持续存在，请联系数据服务提供商")
        print("  无法获取历史K线数据，返回空DataFrame")
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])

    # 处理返回数据
    if result and result.get("code") == 0:
        kline_data_list = result.get("data", [])
        if not kline_data_list:
            # 如果数据为空，创建一个空的DataFrame但带有正确的列
            print("  API返回的数据为空，请检查查询参数是否正确")
            print("  可能原因: 日期范围内没有交易数据，或股票代码不正确")
            df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
            df.set_index("date", inplace=True)
            return df
            
        # 检查数据格式
        if not isinstance(kline_data_list, list):

            # 如果数据是字典格式，尝试提取有用的数据
            if isinstance(kline_data_list, dict):
                # 尝试提取OHLCV数据
                if all(k in kline_data_list for k in ['open', 'high', 'low', 'close', 'volume']):
                    # 提取数据并创建DataFrame
                    data = {
                        'open': kline_data_list['open'],
                        'high': kline_data_list['high'],
                        'low': kline_data_list['low'],
                        'close': kline_data_list['close'],
                        'volume': kline_data_list['volume'],
                    }
                    
                    # 如果有amount字段，也添加进来
                    if 'amount' in kline_data_list:
                        data['amount'] = kline_data_list['amount']
                    
                    # 创建索引
                    if 'date' in kline_data_list:
                        dates = pd.to_datetime(kline_data_list['date'])
                    elif 'time' in kline_data_list:
                        dates = pd.to_datetime(kline_data_list['time'], unit='ms')
                    else:
                        # 如果没有日期字段，返回空DataFrame
                        print("  字典格式数据中缺少日期或时间字段")
                        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
                    
                    # 创建DataFrame
                    df = pd.DataFrame(data, index=dates)
                    print(f"  成功从字典格式提取数据，共 {len(df)} 条记录")
                    return df
            
            # 如果无法从字典提取数据，返回空DataFrame
            print("  无法从API返回数据中提取有效信息")
            print("  请检查API返回的数据格式")
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
            
            # 返回空DataFrame
            print("  无法处理API返回的数据格式")
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])

        # 转换为DataFrame
        df = pd.DataFrame(kline_data_list)

        # 处理日期索引
        if "date" in df.columns:
            # 处理不同的日期格式
            if df["date"].dtype == "object":
                # 字符串格式日期
                if len(str(df["date"].iloc[0])) == 8:  # YYYYMMDD格式
                    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
                else:
                    df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
        elif "time" in df.columns:
            # 时间戳格式
            if df["time"].dtype in ["int64", "float64"]:
                df["time"] = pd.to_datetime(df["time"], unit="ms")
            else:
                df["time"] = pd.to_datetime(df["time"])
            df.set_index("time", inplace=True)

            # 确保数值列的数据类型正确
            numeric_columns = ["open", "high", "low", "close", "volume", "amount"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            print(f"  成功获取 {len(df)} 条K线数据")
            return df
        else:
            print("  API返回数据为空")
            return pd.DataFrame()
    else:
        print(f"  数据获取失败: {result.get('message', '未知错误')}")
        return pd.DataFrame()


def display_kline_summary(df: pd.DataFrame, symbol: str) -> None:
    """显示K线数据摘要信息

    Args:
        df: K线数据DataFrame
        symbol: 股票代码
    """
    if df.empty:
        print(f"  {symbol} - 无K线数据可显示")
        print("  可能的原因:")
        print("    • API调用失败或返回空数据")
        print("    • 网络连接问题")
        print("    • 股票代码不存在或已停牌")
        print("    • 查询日期范围内无交易数据")
        print("  建议:")
        print("    • 检查网络连接和API服务状态")
        print("    • 验证股票代码是否正确")
        print("    • 确认查询的日期范围包含交易日")
        print("    • 检查API配置和认证信息")
        return

    print_subsection_header(f"{symbol} K线数据摘要")
    print(f"  数据条数: {len(df)}")
    
    # 确保索引是日期类型
    if isinstance(df.index, pd.DatetimeIndex):
        print(f"  时间范围: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}")
    else:
        try:
            # 尝试转换索引为日期类型
            date_index = pd.to_datetime(df.index)
            print(f"  时间范围: {date_index[0].strftime('%Y-%m-%d')} 至 {date_index[-1].strftime('%Y-%m-%d')}")
        except:
            # 如果无法转换，显示原始索引
            print(f"  索引范围: {df.index[0]} 至 {df.index[-1]}")
    
    print(f"  价格区间: {df['low'].min():.2f} - {df['high'].max():.2f}")
    print(f"  平均成交量: {format_number(df['volume'].mean())}")

    print("\n  数据样例:")
    print(df.head().to_string())

    # 显示最新数据
    if len(df) > 0:
        latest = df.iloc[-1]
        
        # 显示日期
        if isinstance(df.index, pd.DatetimeIndex):
            date_str = df.index[-1].strftime('%Y-%m-%d')
        else:
            try:
                date_str = pd.to_datetime(df.index[-1]).strftime('%Y-%m-%d')
            except:
                date_str = str(df.index[-1])
                
        print(f"\n  最新数据 ({date_str}):")
        print(f"    开盘价: {latest['open']:.2f}")
        print(f"    最高价: {latest['high']:.2f}")
        print(f"    最低价: {latest['low']:.2f}")
        print(f"    收盘价: {latest['close']:.2f}")
        print(f"    成交量: {format_number(latest['volume'])}")
        print(f"    成交额: {format_number(latest['amount'])}")


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标

    Args:
        df: K线数据DataFrame

    Returns:
        pd.DataFrame: 包含技术指标的DataFrame
    """
    if df.empty:
        print("  无法计算技术指标：数据为空")
        print("  请确保已获取到有效的K线数据")
        print("  建议检查API连接状态和查询参数设置")
        return df
    
    # 检查必要的数据列
    required_columns = ["close"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"  无法计算技术指标：缺少必要数据列 {missing_columns}")
        print("  需要包含'close'列的完整K线数据")
        print("  请检查数据源是否返回了完整的OHLC数据")
        return df
    
    # 检查数据有效性
    if df["close"].isna().all():
        print("  无法计算技术指标：收盘价数据全部为空")
        print("  请检查数据质量和数据源配置")
        return df
    
    data_length = len(df)
    if data_length < 5:
        print(f"  数据量严重不足：当前仅{data_length}条记录")
        print("  技术指标计算需要足够的历史数据：")
        print("    - 移动平均线(MA5): 至少5条记录")
        print("    - 移动平均线(MA10): 至少10条记录") 
        print("    - 移动平均线(MA20): 至少20条记录")
        print("    - RSI指标: 至少14条记录")
        print("  建议扩大查询日期范围以获取更多历史数据")
        if data_length < 2:
            print("  数据量过少，无法进行任何技术指标计算")
            return df

    result_df = df.copy()

    # 移动平均线
    if data_length >= 5:
        result_df["MA5"] = result_df["close"].rolling(window=5).mean()
    else:
        print("  跳过MA5计算：需要至少5条数据记录")
        
    if data_length >= 10:
        result_df["MA10"] = result_df["close"].rolling(window=10).mean()
    else:
        print("  跳过MA10计算：需要至少10条数据记录")
        
    if data_length >= 20:
        result_df["MA20"] = result_df["close"].rolling(window=20).mean()
    else:
        print("  跳过MA20计算：需要至少20条数据记录")

    # 价格变化（需要至少2条数据）
    if data_length >= 2:
        result_df["price_change"] = result_df["close"].diff()
        result_df["price_change_pct"] = result_df["close"].pct_change() * 100
    else:
        print("  跳过价格变化计算：需要至少2条数据记录")

    # 成交量移动平均
    if "volume" in result_df.columns and data_length >= 5:
        result_df["volume_MA5"] = result_df["volume"].rolling(window=5).mean()
    elif "volume" not in result_df.columns:
        print("  跳过成交量移动平均计算：缺少成交量数据")
    else:
        print("  跳过成交量移动平均计算：需要至少5条数据记录")

    # RSI指标 (简化版)
    if data_length >= 14:
        try:
            delta = result_df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            
            # 避免除零错误
            rs = gain / loss.replace(0, np.nan)
            result_df["RSI"] = 100 - (100 / (1 + rs))
        except Exception as e:
            print(f"  RSI计算出错：{e}")
    else:
        print("  跳过RSI计算：需要至少14条数据记录")

    return result_df



# 操作步骤 Step-by-Step Guide

# 本教程将按以下步骤进行:
# 步骤 1: 设置查询参数（股票代码、时间范围、周期）
# 步骤 2: 调用历史K线API获取数据
# 步骤 3: 验证数据的完整性和逻辑性
# 步骤 4: 处理数据异常和缺失值
# 步骤 5: 展示数据分析和可视化示例

def demo_basic_kline_analysis():
    """基础K线数据分析演示"""
    print_section_header("历史K线API基础功能演示")

    # 演示参数
    symbol = config.demo_symbols[0]  # 贵州茅台
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    frequency = "1d"

    try:
        # 获取数据
        kline_df = get_hist_kline_data(symbol, start_date, end_date, frequency)

        # 如果数据为空，提示用户
        if kline_df.empty:
            print("  未获取到数据，请检查API连接和参数设置")
            print("  确保数据服务可用，并且查询参数正确")
            print("  请尝试调整日期范围或检查股票代码是否正确")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "amount"])

        # 确保索引是日期类型
        if not isinstance(kline_df.index, pd.DatetimeIndex):
            try:
                kline_df.index = pd.to_datetime(kline_df.index)
            except:
                # 如果无法转换为日期索引，创建一个新的日期索引
                old_index = kline_df.index.copy()
                kline_df.index = pd.date_range(start=start_date, periods=len(kline_df))
                print(f"  注意: 索引已从 {old_index[0]} 转换为日期格式 {kline_df.index[0].strftime('%Y-%m-%d')}")

        # 显示数据摘要
        display_kline_summary(kline_df, symbol)

        # 计算技术指标
        print_subsection_header("技术指标计算")
        kline_with_indicators = calculate_technical_indicators(kline_df)

        if len(kline_with_indicators) >= 20:
            latest_data = kline_with_indicators.iloc[-1]
            print(f"  最新技术指标:")
            print(f"    MA5:  {latest_data.get('MA5', 0):.2f}")
            print(f"    MA10: {latest_data.get('MA10', 0):.2f}")
            print(f"    MA20: {latest_data.get('MA20', 0):.2f}")
            if "RSI" in latest_data and not pd.isna(latest_data["RSI"]):
                print(f"    RSI:  {latest_data['RSI']:.2f}")

        # 简单的趋势分析
        print_subsection_header("趋势分析")
        if len(kline_df) >= 2:
            recent_change = kline_df["close"].iloc[-1] - kline_df["close"].iloc[-2]
            recent_change_pct = (recent_change / kline_df["close"].iloc[-2]) * 100
            print(f"  最近一日变化: {recent_change:+.2f} ({recent_change_pct:+.2f}%)")

            # 计算近期波动率
            if len(kline_df) >= 20:
                volatility = kline_df["close"].pct_change().rolling(20).std() * 100
                print(f"  20日波动率: {volatility.iloc[-1]:.2f}%")

        return kline_df
    except Exception as e:
        print(f"  分析过程中出错: {str(e)}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        print("  如果问题持续存在，请联系技术支持")
        # 返回一个空的DataFrame，不生成模拟数据
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "amount"])


def demo_api_comparison():
    """API与本地库对比演示"""
    print_section_header("API与本地库对比演示")

    # 导入数据格式标准化函数和比较函数
    from normalize_xtdata import normalize_xtdata_format, compare_dataframes

    # 演示参数
    symbol = config.demo_symbols[0]  # 贵州茅台
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    frequency = "1d"

    print_subsection_header("使用API获取数据")

    # 获取API数据
    data = get_hist_kline_data(symbol, start_date, end_date, frequency)
    
    if not data.empty:
        print(f"  成功获取 {len(data)} 条API数据")
        
        # 确保索引是日期类型
        if isinstance(data.index, pd.DatetimeIndex):
            print(f"  数据日期范围: {data.index[0].strftime('%Y-%m-%d')} 至 {data.index[-1].strftime('%Y-%m-%d')}")
        else:
            try:
                # 尝试转换索引为日期类型
                data.index = pd.to_datetime(data.index)
                print(f"  数据日期范围: {data.index[0].strftime('%Y-%m-%d')} 至 {data.index[-1].strftime('%Y-%m-%d')}")
            except:
                # 如果无法转换，显示原始索引
                print(f"  数据索引范围: {data.index[0]} 至 {data.index[-1]}")
        
        print(f"  数据列: {data.columns.tolist()}")
        
        # 显示API数据样例
        print("\n  API数据样例:")
        print(data.head().to_string())
    else:
        print("  API数据获取失败或为空")

    print_subsection_header("使用本地库获取数据")

    try:
        # 尝试导入xtdata库
        from xtquant import xtdata

        # 转换日期格式为xtdata需要的格式
        start_time = start_date.replace("-", "")
        end_time = end_date.replace("-", "")
        stock_list = [symbol]

        print(f"  正在通过xtdata获取 {symbol} 从 {start_date} 到 {end_date} 的数据...")

        # 调用xtdata.get_market_data - 使用正确的参数
        local_kline_data_raw = xtdata.get_market_data(
            field_list=[],  # 空列表表示获取所有字段
            stock_list=stock_list,
            period=frequency,
            start_time=start_time,
            end_time=end_time,
            count=-1,  # -1表示获取全部数据
            dividend_type='none',  # 不复权
            fill_data=True  # 填充数据
        )

        # 检查返回数据类型并进行适当处理
        if local_kline_data_raw is None:
            print("  xtdata返回数据为空")
            print("  请检查xtdata环境配置和数据服务可用性")
            print("  确保xtdata库已正确安装并且有权限访问数据")
            return pd.DataFrame()
            
        # 处理不同的返回类型
        try:
            if isinstance(local_kline_data_raw, dict):
                # 检查是否有数据字段
                if 'close' in local_kline_data_raw:
                    # 从字典中提取DataFrame
                    local_kline_data = local_kline_data_raw['close']
                    if isinstance(local_kline_data, pd.DataFrame):
                        if symbol in local_kline_data.index:
                            # 提取单只股票的数据
                            local_kline_data = local_kline_data.loc[symbol].to_frame().T
                            local_kline_data.index = pd.to_datetime(local_kline_data.index)
                        else:
                            print(f"  未在返回数据中找到股票代码 {symbol}")
                            return pd.DataFrame()
                    else:
                        print(f"  xtdata返回的close字段不是DataFrame: {type(local_kline_data)}")
                        return pd.DataFrame()
                    
                    # 尝试从其他字段提取更多数据
                    for field in ['open', 'high', 'low', 'volume', 'amount']:
                        if field in local_kline_data_raw:
                            field_data = local_kline_data_raw[field]
                            if isinstance(field_data, pd.DataFrame) and symbol in field_data.index:
                                local_kline_data[field] = field_data.loc[symbol]
                else:
                    print("  xtdata返回数据中没有找到价格字段")
                    return pd.DataFrame()
            elif isinstance(local_kline_data_raw, pd.DataFrame):
                # 如果直接返回DataFrame
                if symbol in local_kline_data_raw.index:
                    local_kline_data = local_kline_data_raw.xs(symbol, level="symbol", drop_level=True)
                    local_kline_data.index = pd.to_datetime(local_kline_data.index)
                else:
                    local_kline_data = local_kline_data_raw
                    local_kline_data.index = pd.to_datetime(local_kline_data.index)
            else:
                print(f"  xtdata返回未知数据格式: {type(local_kline_data_raw)}")
                return pd.DataFrame()
        except Exception as e:
            print(f"  处理xtdata返回数据时出错: {str(e)}")
            return pd.DataFrame()

        # 标准化数据格式
        local_kline_data = normalize_xtdata_format(local_kline_data, data)

        print(f"  成功获取 {len(local_kline_data)} 条xtdata数据")
        print(f"  数据日期范围: {local_kline_data.index[0].strftime('%Y-%m-%d')} 至 {local_kline_data.index[-1].strftime('%Y-%m-%d')}")
        print(f"  数据列: {local_kline_data.columns.tolist()}")

        # 显示数据样例
        print("\n  xtdata数据样例:")
        print(local_kline_data.head().to_string())

        # 计算移动平均线
        if len(local_kline_data) >= 20 and "close" in local_kline_data.columns:
            close_prices = local_kline_data["close"].tolist()
            ma20 = sum(close_prices[-20:]) / 20
            print(f"\n  20日移动平均线 (xtdata): {ma20:.2f}")
        else:
            print("\n  数据不足，无法计算移动平均线")

        # 数据对比
        if not data.empty:
            print_subsection_header("数据对比分析")
            
            # 使用比较函数生成详细报告
            comparison_report = compare_dataframes(data, local_kline_data)
            
            # 显示基本统计信息
            print(f"  API数据条数: {comparison_report['api_data_count']}")
            print(f"  xtdata数据条数: {comparison_report['xtdata_count']}")
            print(f"  共同日期数: {comparison_report['common_dates_count']}")
            
            # 显示日期范围
            if comparison_report['api_date_range']['start'] and comparison_report['api_date_range']['end']:
                print(f"  API数据日期范围: {comparison_report['api_date_range']['start']} 至 {comparison_report['api_date_range']['end']}")
            if comparison_report['xtdata_date_range']['start'] and comparison_report['xtdata_date_range']['end']:
                print(f"  xtdata数据日期范围: {comparison_report['xtdata_date_range']['start']} 至 {comparison_report['xtdata_date_range']['end']}")
            
            # 显示字段差异统计
            if comparison_report['common_dates_count'] > 0 and 'field_comparison' in comparison_report:
                print("\n  字段差异统计:")
                for field, stats in comparison_report['field_comparison'].items():
                    print(f"    {field}:")
                    print(f"      最大差异: {stats['max_diff']:.4f}")
                    print(f"      平均差异: {stats['mean_diff']:.4f}")
                    print(f"      标准差: {stats['std_diff']:.4f}")
                    if stats['max_rel_diff_pct'] is not None:
                        print(f"      最大相对差异: {stats['max_rel_diff_pct']:.2f}%")
                    if stats['mean_rel_diff_pct'] is not None:
                        print(f"      平均相对差异: {stats['mean_rel_diff_pct']:.2f}%")
            
            # 显示最近几天的详细对比
            if 'recent_comparison' in comparison_report:
                print("\n  最近日期详细对比:")
                for day_data in comparison_report['recent_comparison']:
                    print(f"    {day_data['date']}:")
                    for field in ['close', 'open', 'high', 'low']:
                        if field in day_data:
                            field_data = day_data[field]
                            diff_str = f"{field_data['diff']:+.4f}" if field_data['diff'] is not None else "N/A"
                            diff_pct_str = f"({field_data['diff_pct']:+.2f}%)" if field_data['diff_pct'] is not None else ""
                            print(f"      {field}: API={field_data['api']:.2f}, xtdata={field_data['xtdata']:.2f}, 差异={diff_str} {diff_pct_str}")
            else:
                print("  没有找到共同的日期数据进行对比")

        return local_kline_data

    except ImportError:
        print("  xtdata库未安装或不可用")
        print("  请确保已正确安装和配置xtdata环境")
        return pd.DataFrame()
    except TypeError as e:
        print(f"  xtdata参数类型错误: {e}")
        print("  请检查传递给xtdata.get_market_data的参数类型")
        return pd.DataFrame()
    except AttributeError as e:
        print(f"  xtdata属性错误: {e}")
        print("  可能是xtdata版本不兼容或API变更")
        return pd.DataFrame()
    except ValueError as e:
        print(f"  xtdata值错误: {e}")
        print("  请检查日期格式或其他参数值")
        return pd.DataFrame()
    except Exception as e:
        print(f"  xtdata调用失败: {e}")
        print("  请确保xtdata环境已正确配置，并且数据服务可用")
        return pd.DataFrame()


def demo_multiple_frequencies():
    """多周期K线数据演示"""
    print_section_header("多周期K线数据演示")

    symbol = config.demo_symbols[0]
    start_date = "2023-12-01"
    end_date = "2023-12-31"

    frequencies = ["1d", "1w"]  # 日线和周线

    for freq in frequencies:
        print_subsection_header(f"{freq} 周期数据")
        kline_data = get_hist_kline_data(symbol, start_date, end_date, freq)

        if not kline_data.empty:
            print(f"  获取到 {len(kline_data)} 条 {freq} 数据")
            print(f"  价格区间: {kline_data['low'].min():.2f} - {kline_data['high'].max():.2f}")

            # 显示最新几条数据
            if len(kline_data) >= 3:
                print("\n  最新3条数据:")
                recent_data = kline_data.tail(3)[["open", "high", "low", "close", "volume"]]
                print(recent_data.to_string())


def demo_error_handling():
    """错误处理演示"""
    print_section_header("错误处理演示")

    # 测试无效股票代码
    print_subsection_header("无效股票代码测试")
    invalid_symbol = "INVALID.XX"
    result = safe_api_call(
        api_client, api_client.get_hist_kline, invalid_symbol, "2023-01-01", "2023-01-31", "1d"
    )
    print_api_result(result, "无效股票代码结果")

    # 测试无效日期范围
    print_subsection_header("无效日期范围测试")
    result = safe_api_call(
        api_client, api_client.get_hist_kline, "600519.SH", "2025-01-01", "2025-12-31", "1d"
    )
    print_api_result(result, "未来日期结果")

    # 测试无效频率
    print_subsection_header("无效频率测试")
    result = safe_api_call(
        api_client, api_client.get_hist_kline, "600519.SH", "2023-01-01", "2023-01-31", "invalid"
    )
    print_api_result(result, "无效频率结果")


# ==================== 增强API功能演示 ====================

def demo_enhanced_multi_period_data():
    """演示增强API的多周期数据获取功能"""
    print_section_header("增强API - 多周期数据获取演示")
    
    if not ENHANCED_API_AVAILABLE:
        print("❌ 增强API不可用，跳过多周期演示")
        return
    
    symbol = config.demo_symbols[0]  # 贵州茅台
    start_date = "2024-01-01"
    end_date = "2024-01-31"
    
    # 支持的多个周期
    periods = ["1d", "1w", "1h", "15m"]
    
    print(f"股票代码: {symbol}")
    print(f"时间范围: {start_date} 至 {end_date}")
    print(f"查询周期: {', '.join(periods)}")
    
    try:
        # 创建多周期请求
        if ENHANCED_API_AVAILABLE:
            # 使用增强API获取多周期数据
            for period in periods:
                print_subsection_header(f"{period} 周期数据")
                
                request = HistoricalDataRequest(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=SupportedPeriod(period),
                    include_quality_metrics=True,
                    normalize_data=True,
                    use_cache=True
                )
                
                # 异步调用增强API
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    response = loop.run_until_complete(
                        enhanced_api.get_historical_data(request)
                    )
                    
                    if response.success:
                        print(f"  ✅ 成功获取 {len(response.data)} 条 {period} 数据")
                        print(f"  📊 数据质量评分: {response.quality_report.get('overall_score', 'N/A') if response.quality_report else 'N/A'}")
                        print(f"  🚀 缓存命中: {response.metadata.get('cache_hit', False)}")
                        print(f"  ⏱️  响应时间: {response.metadata.get('response_time_ms', 0)}ms")
                        
                        # 显示数据样例
                        if response.data:
                            sample_data = response.data[0]
                            print(f"  📈 首条数据: {sample_data}")
                    else:
                        print(f"  ❌ 获取 {period} 数据失败: {response.metadata.get('error', '未知错误')}")
                        
                finally:
                    loop.close()
        
    except Exception as e:
        print(f"❌ 多周期数据获取失败: {str(e)}")
        print("  建议检查增强API服务状态和网络连接")


def demo_enhanced_data_quality_monitoring():
    """演示增强API的数据质量监控功能"""
    print_section_header("增强API - 数据质量监控演示")
    
    if not ENHANCED_API_AVAILABLE:
        print("❌ 增强API不可用，跳过数据质量监控演示")
        return
    
    symbol = config.demo_symbols[0]
    start_date = "2024-01-01"
    end_date = "2024-01-05"
    
    print(f"股票代码: {symbol}")
    print(f"时间范围: {start_date} 至 {end_date}")
    
    # 测试不同周期的数据质量
    test_periods = ["1d", "1h", "15m"]
    
    for period in test_periods:
        print_subsection_header(f"{period} 周期数据质量检查")
        
        try:
            request = HistoricalDataRequest(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=SupportedPeriod(period),
                include_quality_metrics=True,
                normalize_data=True
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    enhanced_api.get_historical_data(request)
                )
                
                if response.success and response.quality_report:
                    quality = response.quality_report
                    print(f"  📊 数据质量报告:")
                    print(f"    完整性评分: {quality.get('completeness_rate', 0):.2%}")
                    print(f"    准确性评分: {quality.get('accuracy_score', 0):.2f}")
                    print(f"    一致性评分: {quality.get('consistency_score', 0):.2f}")
                    print(f"    及时性评分: {quality.get('timeliness_score', 0):.2f}")
                    print(f"    异常数据数量: {quality.get('anomaly_count', 0)}")
                    
                    # 计算综合质量等级
                    avg_score = (
                        quality.get('completeness_rate', 0) +
                        quality.get('accuracy_score', 0) +
                        quality.get('consistency_score', 0) +
                        quality.get('timeliness_score', 0)
                    ) / 4
                    
                    if avg_score >= 0.9:
                        quality_level = "优秀 ⭐⭐⭐"
                    elif avg_score >= 0.8:
                        quality_level = "良好 ⭐⭐"
                    elif avg_score >= 0.7:
                        quality_level = "一般 ⭐"
                    else:
                        quality_level = "较差 ❌"
                    
                    print(f"    综合质量等级: {quality_level}")
                    
                    # 显示质量问题（如果有）
                    if quality.get('issues'):
                        print(f"  ⚠️  发现质量问题:")
                        for issue in quality.get('issues', [])[:3]:  # 只显示前3个问题
                            print(f"    - {issue}")
                else:
                    print(f"  ❌ 质量检查失败: {response.metadata.get('error', '未知错误')}")
                    
            finally:
                loop.close()
                
        except Exception as e:
            print(f"  ❌ {period} 周期质量检查出错: {str(e)}")


def demo_enhanced_caching_performance():
    """演示增强API的缓存性能优化"""
    print_section_header("增强API - 缓存性能优化演示")
    
    if not ENHANCED_API_AVAILABLE:
        print("❌ 增强API不可用，跳过缓存性能演示")
        return
    
    symbol = config.demo_symbols[0]
    start_date = "2024-01-01"
    end_date = "2024-01-05"
    period = "1d"
    
    print(f"股票代码: {symbol}")
    print(f"时间范围: {start_date} 至 {end_date}")
    print(f"数据周期: {period}")
    
    try:
        request = HistoricalDataRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=SupportedPeriod(period),
            include_quality_metrics=True,
            use_cache=True
        )
        
        # 第一次请求（冷缓存）
        print_subsection_header("第一次请求 (冷缓存)")
        start_time = time.time()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response1 = loop.run_until_complete(
                enhanced_api.get_historical_data(request)
            )
            first_request_time = (time.time() - start_time) * 1000
            
            if response1.success:
                print(f"  ⏱️  响应时间: {first_request_time:.0f}ms")
                print(f"  🚀 缓存命中: {response1.metadata.get('cache_hit', False)}")
                print(f"  📊 数据条数: {len(response1.data)}")
            
            # 第二次请求（热缓存）
            print_subsection_header("第二次请求 (热缓存)")
            start_time = time.time()
            
            response2 = loop.run_until_complete(
                enhanced_api.get_historical_data(request)
            )
            second_request_time = (time.time() - start_time) * 1000
            
            if response2.success:
                print(f"  ⏱️  响应时间: {second_request_time:.0f}ms")
                print(f"  🚀 缓存命中: {response2.metadata.get('cache_hit', False)}")
                print(f"  📊 数据条数: {len(response2.data)}")
                
                # 计算性能提升
                if first_request_time > 0:
                    improvement = (first_request_time - second_request_time) / first_request_time * 100
                    print(f"\n🚀 缓存性能提升: {improvement:.1f}%")
                    
                    # 显示缓存策略信息
                    print(f"\n📋 缓存策略信息:")
                    print(f"  缓存TTL: {response2.metadata.get('cache_ttl_seconds', 'N/A')}秒")
                    print(f"  缓存键: {response2.metadata.get('cache_key', 'N/A')}")
            
        finally:
            loop.close()
            
    except Exception as e:
        print(f"❌ 缓存性能测试失败: {str(e)}")


def demo_enhanced_data_validation():
    """演示增强API的数据验证功能"""
    print_section_header("增强API - 数据验证演示")
    
    if not ENHANCED_API_AVAILABLE:
        print("❌ 增强API不可用，跳过数据验证演示")
        return
    
    symbol = config.demo_symbols[0]
    start_date = "2024-01-01"
    end_date = "2024-01-05"
    
    print(f"股票代码: {symbol}")
    print(f"时间范围: {start_date} 至 {end_date}")
    
    try:
        request = HistoricalDataRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=SupportedPeriod.DAILY,
            include_quality_metrics=True,
            normalize_data=True
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                enhanced_api.get_historical_data(request)
            )
            
            if response.success and response.data:
                print(f"✅ 成功获取并验证 {len(response.data)} 条数据")
                
                # 显示数据验证结果
                print_subsection_header("OHLC逻辑验证")
                valid_count = 0
                invalid_count = 0
                
                for i, record in enumerate(response.data[:5]):  # 检查前5条数据
                    try:
                        open_price = float(record.get('open', 0))
                        high_price = float(record.get('high', 0))
                        low_price = float(record.get('low', 0))
                        close_price = float(record.get('close', 0))
                        
                        # OHLC逻辑验证
                        is_valid = (
                            high_price >= max(open_price, close_price) and
                            low_price <= min(open_price, close_price) and
                            high_price >= low_price
                        )
                        
                        if is_valid:
                            valid_count += 1
                            status = "✅ 有效"
                        else:
                            invalid_count += 1
                            status = "❌ 无效"
                        
                        print(f"  记录 {i+1}: O={open_price:.2f}, H={high_price:.2f}, L={low_price:.2f}, C={close_price:.2f} - {status}")
                        
                    except (ValueError, TypeError) as e:
                        invalid_count += 1
                        print(f"  记录 {i+1}: 数据格式错误 - ❌ 无效")
                
                print(f"\n📊 验证统计:")
                print(f"  有效记录: {valid_count}")
                print(f"  无效记录: {invalid_count}")
                print(f"  验证通过率: {valid_count/(valid_count+invalid_count)*100:.1f}%")
                
                # 显示标准化格式信息
                print_subsection_header("标准化格式验证")
                if response.data:
                    sample_record = response.data[0]
                    print(f"  标准化字段:")
                    for key, value in sample_record.items():
                        print(f"    {key}: {type(value).__name__} = {value}")
            else:
                print(f"❌ 数据验证失败: {response.metadata.get('error', '未知错误')}")
                
        finally:
            loop.close()
            
    except Exception as e:
        print(f"❌ 数据验证出错: {str(e)}")


def demo_enhanced_error_handling():
    """演示增强API的错误处理机制"""
    print_section_header("增强API - 错误处理演示")
    
    if not ENHANCED_API_AVAILABLE:
        print("❌ 增强API不可用，跳过错误处理演示")
        return
    
    # 测试场景列表
    test_cases = [
        {
            "name": "无效股票代码",
            "symbol": "INVALID.XX",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "period": SupportedPeriod.DAILY
        },
        {
            "name": "无效日期格式",
            "symbol": "600519.SH",
            "start_date": "2024-13-01",  # 无效月份
            "end_date": "2024-01-05",
            "period": SupportedPeriod.DAILY
        },
        {
            "name": "未来日期范围",
            "symbol": "600519.SH",
            "start_date": "2025-01-01",
            "end_date": "2025-01-05",
            "period": SupportedPeriod.DAILY
        }
    ]
    
    for test_case in test_cases:
        print_subsection_header(test_case["name"])
        
        try:
            request = HistoricalDataRequest(
                symbol=test_case["symbol"],
                start_date=test_case["start_date"],
                end_date=test_case["end_date"],
                period=test_case["period"],
                include_quality_metrics=False
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    enhanced_api.get_historical_data(request)
                )
                
                if response.success:
                    print(f"  ✅ 意外成功: 获取到 {len(response.data)} 条数据")
                else:
                    print(f"  ❌ 预期失败: {response.metadata.get('error', '未知错误')}")
                    
                    # 显示错误详情
                    if 'error_details' in response.metadata:
                        details = response.metadata['error_details']
                        print(f"  📋 错误详情:")
                        print(f"    错误类型: {details.get('error_type', 'N/A')}")
                        print(f"    错误代码: {details.get('error_code', 'N/A')}")
                        print(f"    重试次数: {details.get('retry_count', 0)}")
                        
            finally:
                loop.close()
                
        except Exception as e:
            print(f"  ❌ 异常处理: {str(e)}")


def demo_enhanced_performance_optimization():
    """演示增强API的性能优化功能"""
    print_section_header("增强API - 性能优化演示")
    
    if not ENHANCED_API_AVAILABLE:
        print("❌ 增强API不可用，跳过性能优化演示")
        return
    
    symbols = config.demo_symbols[:3]  # 使用前3只股票
    start_date = "2024-01-01"
    end_date = "2024-01-05"
    
    print(f"测试股票: {', '.join(symbols)}")
    print(f"时间范围: {start_date} 至 {end_date}")
    
    # 批量获取演示
    print_subsection_header("批量数据获取性能测试")
    
    start_time = time.time()
    results = []
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 并发获取多只股票数据
            tasks = []
            for symbol in symbols:
                request = HistoricalDataRequest(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=SupportedPeriod.DAILY,
                    include_quality_metrics=True,
                    use_cache=True
                )
                task = enhanced_api.get_historical_data(request)
                tasks.append(task)
            
            # 等待所有任务完成
            responses = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            
            total_time = (time.time() - start_time) * 1000
            
            print(f"  ⏱️  总耗时: {total_time:.0f}ms")
            print(f"  📊 并发请求数: {len(symbols)}")
            print(f"  🚀 平均每请求: {total_time/len(symbols):.0f}ms")
            
            # 统计结果
            success_count = 0
            total_records = 0
            cache_hits = 0
            
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    print(f"  ❌ {symbols[i]}: 请求异常 - {str(response)}")
                elif response.success:
                    success_count += 1
                    total_records += len(response.data)
                    if response.metadata.get('cache_hit'):
                        cache_hits += 1
                    print(f"  ✅ {symbols[i]}: {len(response.data)} 条数据, 缓存命中: {response.metadata.get('cache_hit', False)}")
                else:
                    print(f"  ❌ {symbols[i]}: {response.metadata.get('error', '未知错误')}")
            
            print(f"\n📈 性能统计:")
            print(f"  成功率: {success_count}/{len(symbols)} ({success_count/len(symbols)*100:.1f}%)")
            print(f"  总数据量: {total_records} 条")
            print(f"  缓存命中率: {cache_hits}/{len(symbols)} ({cache_hits/len(symbols)*100:.1f}%)")
            
        finally:
            loop.close()
            
    except Exception as e:
        print(f"❌ 批量获取失败: {str(e)}")


def demo_enhanced_best_practices():
    """演示增强API的最佳实践"""
    print_section_header("增强API - 最佳实践演示")
    
    if not ENHANCED_API_AVAILABLE:
        print("❌ 增强API不可用，跳过最佳实践演示")
        return
    
    print("📋 增强API使用最佳实践:")
    
    print_subsection_header("1. 合理选择数据周期")
    print("  • 日内分析: 使用 1m, 5m, 15m, 30m")
    print("  • 短期分析: 使用 1h, 1d")
    print("  • 中长期分析: 使用 1w, 1M")
    print("  • 数据量考虑: 短周期数据量大，建议限制时间范围")
    
    print_subsection_header("2. 启用质量监控")
    print("  • 生产环境建议启用 include_quality_metrics=True")
    print("  • 定期检查数据质量报告")
    print("  • 设置质量阈值告警")
    
    print_subsection_header("3. 优化缓存使用")
    print("  • 频繁查询的数据启用缓存 use_cache=True")
    print("  • 不同周期有不同的缓存TTL:")
    print("    - 分钟级数据: 1小时")
    print("    - 小时级数据: 4-8小时")
    print("    - 日线数据: 24小时")
    print("    - 周月线数据: 7天")
    
    print_subsection_header("4. 错误处理策略")
    print("  • 实现重试机制，建议3次重试")
    print("  • 使用指数退避策略")
    print("  • 记录详细的错误日志")
    print("  • 提供降级方案")
    
    print_subsection_header("5. 性能优化建议")
    print("  • 使用异步调用提高并发性能")
    print("  • 批量获取多只股票数据")
    print("  • 合理设置请求超时时间")
    print("  • 监控API响应时间和成功率")
    
    # 实际演示最佳实践
    symbol = config.demo_symbols[0]
    start_date = "2024-01-01"
    end_date = "2024-01-03"
    
    print_subsection_header("最佳实践示例代码")
    
    try:
        # 示例：正确的API调用方式
        request = HistoricalDataRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=SupportedPeriod.DAILY,
            include_quality_metrics=True,  # 启用质量监控
            normalize_data=True,           # 启用数据标准化
            use_cache=True,               # 启用缓存
            max_records=1000              # 限制返回记录数
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                enhanced_api.get_historical_data(request)
            )
            
            if response.success:
                print(f"  ✅ 最佳实践调用成功:")
                print(f"    数据条数: {len(response.data)}")
                print(f"    质量评分: {response.quality_report.get('overall_score', 'N/A') if response.quality_report else 'N/A'}")
                print(f"    缓存命中: {response.metadata.get('cache_hit', False)}")
                print(f"    响应时间: {response.metadata.get('response_time_ms', 0)}ms")
            else:
                print(f"  ❌ 调用失败: {response.metadata.get('error')}")
                
        finally:
            loop.close()
            
    except Exception as e:
        print(f"❌ 最佳实践演示失败: {str(e)}")


def calculate_advanced_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算高级技术指标 - 优化版本

    Args:
        df: K线数据DataFrame

    Returns:
        pd.DataFrame: 包含高级技术指标的DataFrame
    """
    if df.empty:
        print("  无法计算高级技术指标：数据为空")
        print("  请确保已获取到有效的K线数据")
        print("  建议检查API连接状态和查询参数设置")
        return df
    
    # 检查必要的数据列
    required_columns = ["close", "high", "low"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"  无法计算高级技术指标：缺少必要数据列 {missing_columns}")
        print("  需要包含'close', 'high', 'low'列的完整K线数据")
        print("  请检查数据源是否返回了完整的OHLC数据")
        return df
    
    # 检查数据有效性
    invalid_columns = []
    for col in required_columns:
        if df[col].isna().all():
            invalid_columns.append(col)
    
    if invalid_columns:
        print(f"  无法计算高级技术指标：以下数据列全部为空 {invalid_columns}")
        print("  请检查数据质量和数据源配置")
        return df
    
    data_length = len(df)
    if data_length < 26:
        print(f"  数据量不足：当前{data_length}条记录")
        print("  高级技术指标计算需要充足的历史数据：")
        print("    - MACD指标: 至少26条记录（推荐50+）")
        print("    - 布林带: 至少20条记录（推荐40+）")
        print("    - KDJ指标: 至少9条记录（推荐30+）")
        print("    - 威廉指标: 至少14条记录（推荐30+）")
        print("    - CCI指标: 至少20条记录（推荐40+）")
        print("    - ATR指标: 至少14条记录（推荐30+）")
        print("  建议扩大查询日期范围以获取更多历史数据")
        if data_length < 9:
            print("  数据量过少，无法进行任何高级技术指标计算")
            return df

    result_df = df.copy()

    # 优化：使用向量化操作提高计算效率
    close_prices = result_df["close"]
    high_prices = result_df["high"]
    low_prices = result_df["low"]

    # MACD指标 - 优化计算
    if data_length >= 26:
        try:
            ema12 = close_prices.ewm(span=12, adjust=False).mean()
            ema26 = close_prices.ewm(span=26, adjust=False).mean()
            result_df["MACD"] = ema12 - ema26
            result_df["MACD_signal"] = result_df["MACD"].ewm(span=9, adjust=False).mean()
            result_df["MACD_histogram"] = result_df["MACD"] - result_df["MACD_signal"]
        except Exception as e:
            print(f"  MACD计算出错：{e}")
    else:
        print("  跳过MACD计算：需要至少26条数据记录")

    # 布林带 - 优化计算
    if data_length >= 20:
        try:
            bb_period = 20
            bb_std_dev = 2
            sma20 = close_prices.rolling(window=bb_period, min_periods=bb_period).mean()
            std20 = close_prices.rolling(window=bb_period, min_periods=bb_period).std()

            result_df["BB_middle"] = sma20
            result_df["BB_upper"] = sma20 + (std20 * bb_std_dev)
            result_df["BB_lower"] = sma20 - (std20 * bb_std_dev)
            result_df["BB_width"] = result_df["BB_upper"] - result_df["BB_lower"]

            # 避免除零错误
            bb_width_safe = result_df["BB_width"].replace(0, np.nan)
            result_df["BB_position"] = (close_prices - result_df["BB_lower"]) / bb_width_safe
        except Exception as e:
            print(f"  布林带计算出错：{e}")
    else:
        print("  跳过布林带计算：需要至少20条数据记录")

    # KDJ指标 - 优化计算
    if data_length >= 9:
        try:
            kdj_period = 9
            low_min = low_prices.rolling(window=kdj_period, min_periods=kdj_period).min()
            high_max = high_prices.rolling(window=kdj_period, min_periods=kdj_period).max()

            # 避免除零错误
            hml_diff = high_max - low_min
            hml_diff_safe = hml_diff.replace(0, np.nan)
            rsv = (close_prices - low_min) / hml_diff_safe * 100

            result_df["K"] = rsv.ewm(com=2, adjust=False).mean()
            result_df["D"] = result_df["K"].ewm(com=2, adjust=False).mean()
            result_df["J"] = 3 * result_df["K"] - 2 * result_df["D"]
        except Exception as e:
            print(f"  KDJ计算出错：{e}")
    else:
        print("  跳过KDJ计算：需要至少9条数据记录")

    # 新增：威廉指标 (Williams %R)
    if data_length >= 14:
        try:
            wr_period = 14
            high_max_wr = high_prices.rolling(window=wr_period, min_periods=wr_period).max()
            low_min_wr = low_prices.rolling(window=wr_period, min_periods=wr_period).min()

            hml_diff_wr = high_max_wr - low_min_wr
            hml_diff_wr_safe = hml_diff_wr.replace(0, np.nan)
            result_df["WR"] = (high_max_wr - close_prices) / hml_diff_wr_safe * -100
        except Exception as e:
            print(f"  威廉指标计算出错：{e}")
    else:
        print("  跳过威廉指标计算：需要至少14条数据记录")

    # 新增：商品通道指数 (CCI)
    if data_length >= 20:
        try:
            cci_period = 20
            typical_price = (high_prices + low_prices + close_prices) / 3
            sma_tp = typical_price.rolling(window=cci_period, min_periods=cci_period).mean()
            mad = typical_price.rolling(window=cci_period, min_periods=cci_period).apply(
                lambda x: np.mean(np.abs(x - x.mean())), raw=True
            )

            # 避免除零错误
            mad_safe = mad.replace(0, np.nan)
            result_df["CCI"] = (typical_price - sma_tp) / (0.015 * mad_safe)
        except Exception as e:
            print(f"  CCI计算出错：{e}")
    else:
        print("  跳过CCI计算：需要至少20条数据记录")

    # 新增：平均真实波幅 (ATR)
    if data_length >= 14:
        try:
            atr_period = 14
            prev_close = close_prices.shift(1)

            tr1 = high_prices - low_prices
            tr2 = np.abs(high_prices - prev_close)
            tr3 = np.abs(low_prices - prev_close)

            true_range = np.maximum(tr1, np.maximum(tr2, tr3))
            result_df["ATR"] = true_range.rolling(window=atr_period, min_periods=atr_period).mean()
        except Exception as e:
            print(f"  ATR计算出错：{e}")
    else:
        print("  跳过ATR计算：需要至少14条数据记录")

    return result_df


def create_visualization_data(df: pd.DataFrame, symbol: str) -> dict:
    """创建可视化数据结构（优化内存使用）

    Args:
        df: K线数据DataFrame
        symbol: 股票代码

    Returns:
        dict: 可视化数据字典
    """
    if df.empty:
        print("  无法创建可视化数据：K线数据为空")
        print("  请确保已获取到有效的K线数据")
        return {
            "symbol": symbol,
            "error": "数据为空",
            "message": "无法创建可视化数据，请检查数据源"
        }

    # 确保索引是日期类型
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except:
            # 如果无法转换为日期索引，创建一个新的日期索引
            df.index = pd.date_range(start="2023-01-01", periods=len(df))

    # 智能采样策略：保留关键数据点
    max_points = 200  # 限制最大数据点数
    if len(df) > max_points:
        # 使用分层采样：保留最近的数据点更多，历史数据点较少
        recent_points = min(100, len(df) // 2)  # 最近数据保留更多
        historical_points = max_points - recent_points

        # 最近数据
        recent_df = df.tail(recent_points)

        # 历史数据采样
        if len(df) > recent_points:
            historical_df = df.iloc[:-recent_points]
            if len(historical_df) > historical_points:
                step = len(historical_df) // historical_points
                historical_sampled = historical_df.iloc[::step]
            else:
                historical_sampled = historical_df

            sampled_df = pd.concat([historical_sampled, recent_df]).sort_index()
        else:
            sampled_df = recent_df
    else:
        sampled_df = df.copy()

    # 计算技术指标
    sampled_df = calculate_advanced_indicators(sampled_df)

    # 构建优化的可视化数据结构
    viz_data = {
        "symbol": symbol,
        "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in sampled_df.index],
        "ohlc": {
            "open": sampled_df["open"].round(2).tolist(),
            "high": sampled_df["high"].round(2).tolist(),
            "low": sampled_df["low"].round(2).tolist(),
            "close": sampled_df["close"].round(2).tolist(),
        },
        "volume": sampled_df["volume"].astype(int).tolist(),
        "indicators": {},
        "metadata": {
            "total_points": len(df),
            "sampled_points": len(sampled_df),
            "compression_ratio": len(sampled_df) / len(df) if len(df) > 0 else 1,
            "date_range": {
                "start": df.index[0].strftime("%Y-%m-%d") if hasattr(df.index[0], "strftime") else str(df.index[0]),
                "end": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1]),
            },
        },
    }

    # 添加技术指标数据（包含新增指标）
    indicator_columns = [
        "MA5",
        "MA10",
        "MA20",
        "RSI",
        "MACD",
        "MACD_signal",
        "BB_upper",
        "BB_middle",
        "BB_lower",
        "K",
        "D",
        "J",
        "WR",
        "CCI",
        "ATR",
    ]

    for col in indicator_columns:
        if col in sampled_df.columns:
            # 使用更高效的数据类型转换
            values = sampled_df[col].round(2).fillna(0)
            viz_data["indicators"][col] = values.tolist()

    return viz_data


def generate_analysis_report(df: pd.DataFrame, symbol: str) -> dict:
    """生成分析报告

    Args:
        df: K线数据DataFrame
        symbol: 股票代码

    Returns:
        dict: 分析报告
    """
    if df.empty:
        print("  无法生成分析报告：K线数据为空")
        print("  请确保已获取到有效的K线数据")
        return {
            "symbol": symbol,
            "error": "数据为空",
            "message": "无法生成分析报告，请检查数据源和API连接"
        }
    
    required_columns = ["close", "high", "low", "open", "volume"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"  无法生成完整分析报告：缺少必要数据列 {missing_columns}")
        print("  需要包含完整的OHLCV数据")
        return {
            "symbol": symbol,
            "error": "数据不完整",
            "message": f"缺少必要数据列: {missing_columns}",
            "missing_columns": missing_columns
        }
    
    if len(df) < 2:
        print(f"  分析报告警告：数据量不足（{len(df)}条记录）")
        print("  建议至少20条记录以获得准确的分析结果")

    # 计算高级技术指标
    df_with_indicators = calculate_advanced_indicators(df)

    # 基础统计
    latest = df_with_indicators.iloc[-1]
    price_stats = {
        "current_price": float(latest["close"]),
        "price_change": (
            float(latest["close"] - df_with_indicators.iloc[-2]["close"])
            if len(df_with_indicators) > 1
            else 0
        ),
        "price_change_pct": (
            float(
                (
                    (latest["close"] - df_with_indicators.iloc[-2]["close"])
                    / df_with_indicators.iloc[-2]["close"]
                    * 100
                )
            )
            if len(df_with_indicators) > 1
            else 0
        ),
        "high_52w": float(df_with_indicators["high"].max()),
        "low_52w": float(df_with_indicators["low"].min()),
        "avg_volume": int(df_with_indicators["volume"].mean()),
    }

    # 技术分析
    technical_analysis = {}

    # 趋势分析
    if "MA20" in df_with_indicators.columns and not pd.isna(latest["MA20"]):
        if latest["close"] > latest["MA20"]:
            trend = "上升趋势"
        else:
            trend = "下降趋势"
        technical_analysis["trend"] = trend
        technical_analysis["ma20_distance"] = float(
            (latest["close"] - latest["MA20"]) / latest["MA20"] * 100
        )

    # RSI分析
    if "RSI" in df_with_indicators.columns and not pd.isna(latest["RSI"]):
        rsi_value = float(latest["RSI"])
        if rsi_value > 70:
            rsi_signal = "超买"
        elif rsi_value < 30:
            rsi_signal = "超卖"
        else:
            rsi_signal = "正常"
        technical_analysis["rsi"] = {"value": rsi_value, "signal": rsi_signal}

    # MACD分析
    if "MACD" in df_with_indicators.columns and not pd.isna(latest["MACD"]):
        macd_value = float(latest["MACD"])
        macd_signal = float(latest["MACD_signal"]) if not pd.isna(latest["MACD_signal"]) else 0
        if macd_value > macd_signal:
            macd_trend = "金叉"
        else:
            macd_trend = "死叉"
        technical_analysis["macd"] = {
            "value": macd_value,
            "signal": macd_signal,
            "trend": macd_trend,
        }

    # 布林带分析
    if "BB_position" in df_with_indicators.columns and not pd.isna(latest["BB_position"]):
        bb_pos = float(latest["BB_position"])
        if bb_pos > 0.8:
            bb_signal = "接近上轨"
        elif bb_pos < 0.2:
            bb_signal = "接近下轨"
        else:
            bb_signal = "中轨附近"
        technical_analysis["bollinger"] = {"position": bb_pos, "signal": bb_signal}

    # 波动率分析
    if len(df_with_indicators) >= 20:
        volatility_series = df_with_indicators["close"].pct_change().rolling(20).std() * 100
        volatility = float(volatility_series.iloc[-1]) if not volatility_series.empty and not pd.isna(volatility_series.iloc[-1]) else 0.0
        technical_analysis["volatility"] = volatility

    # 成交量分析
    if "volume" in df_with_indicators.columns:
        volume_ma5 = df_with_indicators["volume"].rolling(5).mean()
        if not volume_ma5.empty and not pd.isna(volume_ma5.iloc[-1]):
            volume_trend = (
                "放量"
                if latest["volume"] > volume_ma5.iloc[-1] * 1.5
                else "缩量"
                if latest["volume"] < volume_ma5.iloc[-1] * 0.5
                else "正常"
            )
            technical_analysis["volume"] = {
                "value": int(latest["volume"]),
                "ma5": int(volume_ma5.iloc[-1]),
                "trend": volume_trend,
            }

    # 汇总报告
    report = {
        "symbol": symbol,
        "price_stats": price_stats,
        "technical_analysis": technical_analysis,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return report


def demo_advanced_visualization():
    """高级可视化和分析演示"""
    print_section_header("高级可视化和分析演示")

    # 演示参数
    symbol = config.demo_symbols[0]  # 贵州茅台
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    frequency = "1d"

    # 获取数据
    kline_df = get_hist_kline_data(symbol, start_date, end_date, frequency)

    # 检查数据是否为空
    if kline_df.empty:
        print("  未获取到数据，无法进行高级可视化分析")
        print("  请检查API连接和参数设置")
        return {}, {}

    # 确保索引是日期类型
    if not isinstance(kline_df.index, pd.DatetimeIndex):
        try:
            kline_df.index = pd.to_datetime(kline_df.index)
        except Exception as e:
            print(f"  无法转换数据索引为日期格式: {str(e)}")
            print("  数据格式可能存在问题，请检查数据源")
            return {}, {}

    # 创建优化的可视化数据结构
    print_subsection_header("创建优化的可视化数据结构")
    viz_data = create_visualization_data(kline_df, symbol)

    # 显示可视化数据结构的基本信息
    print(f"  数据点数: {viz_data['metadata']['total_points']} (原始) -> {viz_data['metadata']['sampled_points']} (采样)")
    print(f"  压缩比例: {viz_data['metadata']['compression_ratio']:.2f}")
    print(f"  日期范围: {viz_data['metadata']['date_range']['start']} 至 {viz_data['metadata']['date_range']['end']}")
    print(f"  指标数量: {len(viz_data['indicators'])}")

    # 生成分析报告
    print_subsection_header("生成分析报告")
    report = generate_analysis_report(kline_df, symbol)

    # 显示分析报告
    print(f"  股票代码: {report['symbol']}")
    print(f"  当前价格: {report['price_stats']['current_price']:.2f}")
    print(f"  价格变化: {report['price_stats']['price_change']:+.2f} ({report['price_stats']['price_change_pct']:+.2f}%)")
    print(f"  52周区间: {report['price_stats']['low_52w']:.2f} - {report['price_stats']['high_52w']:.2f}")
    print(f"  平均成交量: {format_number(report['price_stats']['avg_volume'])}")

    # 显示技术分析结果
    if "trend" in report["technical_analysis"]:
        print(f"\n  趋势分析: {report['technical_analysis']['trend']}")
        print(f"  MA20距离: {report['technical_analysis']['ma20_distance']:+.2f}%")

    if "rsi" in report["technical_analysis"]:
        print(f"\n  RSI指标: {report['technical_analysis']['rsi']['value']:.2f} ({report['technical_analysis']['rsi']['signal']})")

    if "macd" in report["technical_analysis"]:
        print(f"\n  MACD指标: {report['technical_analysis']['macd']['value']:+.4f} ({report['technical_analysis']['macd']['trend']})")

    if "bollinger" in report["technical_analysis"]:
        print(f"\n  布林带位置: {report['technical_analysis']['bollinger']['position']:.2f} ({report['technical_analysis']['bollinger']['signal']})")

    if "volatility" in report["technical_analysis"]:
        print(f"\n  20日波动率: {report['technical_analysis']['volatility']:.2f}%")

    if "volume" in report["technical_analysis"]:
        print(f"\n  成交量分析: {format_number(report['technical_analysis']['volume']['value'])} ({report['technical_analysis']['volume']['trend']})")
        print(f"  5日均量: {format_number(report['technical_analysis']['volume']['ma5'])}")

    return viz_data, report


def main():
    """主函数"""
    print_section_header("历史K线API教程")

    try:
        # 基础K线数据分析演示
        kline_df = demo_basic_kline_analysis()

        # API与本地库对比演示
        demo_api_comparison()

        # 多周期K线数据演示
        demo_multiple_frequencies()

        # 错误处理演示
        demo_error_handling()

        # 高级可视化和分析演示
        demo_advanced_visualization()

    except KeyboardInterrupt:
        print("\n\n用户中断教程执行")
    except Exception as e:
        print(f"\n\n教程执行过程中发生错误: {e}")
        print("请检查API服务状态和网络连接")
    finally:
        print("\n教程执行完毕")


def run_all_demonstrations():
    """运行所有演示功能"""
    print("🚀 历史K线API完整演示开始")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 基础API演示
        print_section_header("基础API功能演示")
        demo_basic_kline_analysis()
        demo_multiple_frequencies()
        demo_api_comparison()
        demo_error_handling()
        demo_advanced_visualization()
        
        # 增强API演示（如果可用）
        if ENHANCED_API_AVAILABLE:
            print_section_header("增强API功能演示")
            demo_enhanced_multi_period_data()
            demo_enhanced_data_quality_monitoring()
            demo_enhanced_caching_performance()
            demo_enhanced_data_validation()
            demo_enhanced_error_handling()
            demo_enhanced_performance_optimization()
            demo_enhanced_best_practices()
        else:
            print_section_header("增强API功能不可用")
            print("⚠️  增强API模块未找到或未正确配置")
            print("   请确保已安装并配置增强API相关模块")
            print("   当前仅运行基础API功能演示")
        
        print(f"\n{'='*60}")
        print(" 🎉 所有演示完成!")
        print(f"{'='*60}")
        
        # 显示功能总结
        print("\n📋 功能总结:")
        print("✅ 基础历史K线数据获取")
        print("✅ 多周期数据支持")
        print("✅ 数据格式标准化")
        print("✅ 技术指标计算")
        print("✅ 错误处理机制")
        print("✅ 高级可视化和分析")
        
        if ENHANCED_API_AVAILABLE:
            print("✅ 增强API多周期支持")
            print("✅ 数据质量监控")
            print("✅ 智能缓存优化")
            print("✅ 数据验证功能")
            print("✅ 性能优化策略")
            print("✅ 最佳实践指导")
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {str(e)}")
        print("   请检查API服务状态和网络连接")


if __name__ == "__main__":
    # 可以选择运行完整演示或单独的main函数
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        run_all_demonstrations()
    else:
        main()


# ==================== 最佳实践指南 ====================

"""
增强API最佳实践指南:

1. 数据周期选择策略:
   • 日内交易: 1m, 5m, 15m (数据量大，建议限制时间范围)
   • 短期分析: 30m, 1h, 1d (平衡精度和性能)
   • 中长期分析: 1w, 1M (数据量小，可查询较长时间范围)

2. 缓存使用策略:
   • 启用缓存: use_cache=True (提高响应速度)
   • 缓存TTL: 系统自动根据周期设置
   • 热点数据: 系统自动预加载常用股票数据

3. 数据质量监控:
   • 生产环境: include_quality_metrics=True
   • 质量阈值: 完整性>90%, 准确性>0.95
   • 异常处理: 自动过滤异常数据点

4. 性能优化建议:
   • 使用异步调用: await enhanced_api.get_historical_data()
   • 批量获取: 并发请求多只股票
   • 合理分页: max_records参数控制返回数据量
   • 监控指标: 响应时间、缓存命中率、成功率

5. 错误处理机制:
   • 重试策略: 自动重试3次，指数退避
   • 降级方案: 缓存数据或基础API
   • 日志记录: 详细的错误信息和堆栈跟踪
   • 告警机制: 质量下降或服务异常时告警

6. 数据验证规则:
   • OHLC逻辑: High >= max(Open,Close) >= min(Open,Close) >= Low
   • 数值范围: 价格>0, 成交量>=0
   • 时间序列: 数据按时间正序排列
   • 数据完整性: 检查缺失值和异常值

在实际应用中，建议遵循以下最佳实践:
✅ 验证OHLC数据的逻辑关系
✅ 启用数据质量监控和告警
✅ 合理选择时间周期以平衡精度和性能
✅ 实施智能缓存策略减少API调用
✅ 使用异步调用提高并发性能
✅ 实现完善的错误处理和重试机制
✅ 定期监控API性能和数据质量指标
"""