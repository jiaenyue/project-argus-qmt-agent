#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
历史K线API 使用教程 (简化版) - Project Argus QMT 数据代理服务

本教程演示如何使用历史K线API获取股票的历史价格数据，
包括基本的数据获取、格式转换和简单的数据分析。
"""

import pandas as pd
import numpy as np
import datetime
import time
from typing import Dict, List, Any, Optional

# 导入统一工具库
from common.api_client import QMTAPIClient, create_api_client, safe_api_call
from common.mock_data import MockDataGenerator
from common.utils import print_section_header, print_subsection_header, print_api_result
from common.config import get_config

# 初始化工具
config = get_config()
api_client = create_api_client()
mock_generator = MockDataGenerator()


def main():
    """主函数"""
    print_section_header("历史K线API使用教程 (简化版)")
    
    # 演示参数
    symbol = "600519.SH"  # 贵州茅台
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    frequency = "1d"
    
    print_subsection_header(f"获取 {symbol} 历史K线数据")
    print(f"  时间范围: {start_date} 至 {end_date}")
    print(f"  数据周期: {frequency}")
    
    # 创建示例数据
    print("  创建示例数据用于演示")
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    data = {
        'open': [100 + i*0.1 for i in range(len(dates))],
        'high': [101 + i*0.1 for i in range(len(dates))],
        'low': [99 + i*0.1 for i in range(len(dates))],
        'close': [100.5 + i*0.1 for i in range(len(dates))],
        'volume': [1000000 + i*1000 for i in range(len(dates))],
        'amount': [100000000 + i*100000 for i in range(len(dates))]
    }
    df = pd.DataFrame(data, index=dates)
    
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
    print("  移动平均线:")
    print(f"    MA5: {df['ma5'].iloc[-1]:.2f}")
    print(f"    MA10: {df['ma10'].iloc[-1]:.2f}")
    print(f"    MA20: {df['ma20'].iloc[-1]:.2f}")
    
    print("  MACD指标:")
    print(f"    DIF: {df['dif'].iloc[-1]:.4f}")
    print(f"    DEA: {df['dea'].iloc[-1]:.4f}")
    print(f"    MACD: {df['macd'].iloc[-1]:.4f}")
    
    print("\n教程演示完成")


if __name__ == "__main__":
    main()