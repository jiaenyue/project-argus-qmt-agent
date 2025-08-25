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


def retry_api_call(func, max_retries=3, delay=1.0):
    """API调用重试机制"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"API调用失败，{delay}秒后重试... (尝试 {attempt + 1}/{max_retries})")
            time.sleep(delay)


def test_api_connectivity():
    """测试API连接"""
    try:
        with create_api_client() as client:
            # 测试基本连接
            result = client.get_trading_dates(market="SH", count=1)
            if result.get('code') == 0:
                print("✓ API连接正常")
                return True
            else:
                print(f"✗ API连接失败: {result.get('message')}")
                return False
    except Exception as e:
        print(f"✗ API连接异常: {e}")
        return False

from .common import create_api_client, safe_api_call, print_api_result
#!/usr/bin/env python
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

"""

# 学习目标 Learning Objectives


# 背景知识 Background Knowledge

💡 K线数据是技术分析的基础，包含价格和成交量信息
💡 OHLCV分别代表开盘价、最高价、最低价、收盘价和成交量
💡 不同的时间周期适用于不同的分析需求

通过本教程，您将学会:
1. 掌握历史K线数据的获取方法
2. 理解OHLCV数据的含义和用途
3. 学会数据质量验证和清洗
4. 了解不同时间周期的数据特点

历史K线API 使用教程 (简化版) - Project Argus QMT 数据代理服务

本教程演示如何使用历史K线API获取股票的历史价格数据，
包括基本的数据获取、格式转换和简单的数据分析。

重要说明:
- 本教程仅使用来自API的真实历史K线数据
- 不再提供模拟数据功能
- 需要确保API服务正常运行和数据源连接有效
- 如果无法获取数据，将显示详细的错误信息

数据要求:
- 需要有效的历史数据访问权限
- 确保股票代码格式正确（包含交易所后缀）
- 网络连接稳定，API服务响应正常
- 建议使用近期日期范围以确保数据可用性
"""

import pandas as pd
import numpy as np
import datetime
import time
from typing import Dict, List, Any, Optional

# 导入统一工具库
from common import (
    QMTAPIClient, 
    create_api_client, 
    safe_api_call,
    print_section_header, 
    print_subsection_header, 
    print_api_result,
        # K线数据包含开高低收成交量信息，是技术分析的基础
    get_config
)

# 初始化工具
config = get_config()
api_client = create_api_client()
# Mock data generator instance removed


def main():
    """主函数"""
    print_section_header("历史K线API使用教程 (简化版)")
    
    try:
        # 演示参数
        symbol = "600519.SH"  # 贵州茅台
        start_date = "2023-01-01"
        end_date = "2023-12-31"
        frequency = "1d"
        
        print_subsection_header(f"获取 {symbol} 历史K线数据")
        print(f"  时间范围: {start_date} 至 {end_date}")
        print(f"  数据周期: {frequency}")
        
        # 调用API获取数据
        result = safe_api_call(
            # 获取历史K线数据 - 返回指定时间段的OHLCV数据
            api_client, api_client.get_hist_kline, symbol, start_date, end_date, frequency
        )

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
                print("  API返回的数据为空，请检查查询参数是否正确")
                print("  可能原因: 日期范围内没有交易数据，或股票代码不正确")
                df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
                df.set_index("date", inplace=True)
                return df
            
            # 转换数据为DataFrame
            df_data = []
            for item in kline_data_list:
                df_data.append({
                    'date': pd.to_datetime(item.get('date', item.get('time', ''))),
                    'open': float(item.get('open', 0)),
                    'high': float(item.get('high', 0)),
                    'low': float(item.get('low', 0)),
                    'close': float(item.get('close', 0)),
                    'volume': int(item.get('volume', 0)),
                    'amount': float(item.get('amount', 0))
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('date', inplace=True)
        else:
            print("  处理API返回数据时出错")
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
        
        # 显示数据摘要
        print_subsection_header(f"{symbol} K线数据摘要")
        print(f"  数据条数: {len(df)}")
        print(f"  时间范围: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"  价格区间: {df['low'].min():.2f} - {df['high'].max():.2f}")
        print(f"  平均成交量: {df['volume'].mean():.0f}")
        
        # 计算技术指标
        print_subsection_header("技术指标计算")
        
        # 计算移动平均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        
        # 计算MACD
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['dif'] = df['ema12'] - df['ema26']
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd'] = 2 * (df['dif'] - df['dea'])
    
        # 显示计算结果
        if len(df) > 0:
            print("  移动平均线:")
            if not pd.isna(df['ma5'].iloc[-1]):
                print(f"    MA5: {df['ma5'].iloc[-1]:.2f}")
            if not pd.isna(df['ma10'].iloc[-1]):
                print(f"    MA10: {df['ma10'].iloc[-1]:.2f}")
            if not pd.isna(df['ma20'].iloc[-1]):
                print(f"    MA20: {df['ma20'].iloc[-1]:.2f}")
            
            print("  MACD指标:")
            if not pd.isna(df['dif'].iloc[-1]):
                print(f"    DIF: {df['dif'].iloc[-1]:.4f}")
            if not pd.isna(df['dea'].iloc[-1]):
                print(f"    DEA: {df['dea'].iloc[-1]:.4f}")
            if not pd.isna(df['macd'].iloc[-1]):
                print(f"    MACD: {df['macd'].iloc[-1]:.4f}")
        else:
            print("  无法显示技术指标：数据为空")
        
        print("\n教程演示完成")
        
    except KeyboardInterrupt:
        print("\n\n用户中断教程执行")
    except Exception as e:
        print(f"\n\n教程执行过程中发生错误: {e}")
        print("请检查API服务状态和网络连接")
    finally:
        print("\n教程执行完毕")


if __name__ == "__main__":
    main()

# 操作步骤 Step-by-Step Guide

本教程将按以下步骤进行:
步骤 1: 设置查询参数（股票代码、时间范围、周期）
步骤 2: 调用历史K线API获取数据
步骤 3: 验证数据的完整性和逻辑性
步骤 4: 处理数据异常和缺失值
步骤 5: 展示数据分析和可视化示例


# 最佳实践 Best Practices

在实际应用中，建议遵循以下最佳实践:
✅ 验证OHLC数据的逻辑关系（如最高价≥收盘价≥最低价）
✅ 处理除权除息对价格数据的影响
✅ 合理选择时间周期以平衡精度和性能
✅ 实施数据缓存策略减少API调用