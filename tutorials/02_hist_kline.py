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
历史K线API 使用教程 - Project Argus QMT 数据代理服务

本教程演示如何使用历史K线API获取股票的历史价格数据，
包括API调用、数据处理、技术指标计算和可视化展示。

参数说明:
- symbol: 股票代码(格式:代码.交易所) 如 "600519.SH"
- start_date: 开始日期(YYYY-MM-DD) 如 "2023-01-01"  
- end_date: 结束日期(YYYY-MM-DD) 如 "2023-12-31"
- frequency: K线周期(1d-日线,1m-1分钟) 如 "1d"
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
try:
    import psutil
except ImportError:
    psutil = None

# 导入通用工具库
from common.api_client import create_api_client, safe_api_call
from common.mock_data import MockDataGenerator
from common.utils import (
    print_section_header, print_subsection_header, print_api_result,
    format_response_time, create_demo_context, format_number
)
from common.config import get_config

# 初始化工具和配置
config = get_config()
demo_context = create_demo_context()
performance_monitor = demo_context['performance_monitor']
api_client = create_api_client(enable_monitoring=True)
mock_generator = MockDataGenerator()


def get_hist_kline_data(symbol: str, start_date: str, end_date: str, frequency: str = "1d") -> pd.DataFrame:
    """获取历史K线数据并转换为DataFrame
    
    Args:
        symbol: 股票代码
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        frequency: K线周期
        
    Returns:
        pd.DataFrame: 历史K线数据
    """
    print_subsection_header(f"获取 {symbol} 历史K线数据")
    print(f"  时间范围: {start_date} 至 {end_date}")
    print(f"  数据周期: {frequency}")
    
    # 调用API获取数据
    result = safe_api_call(api_client, api_client.get_hist_kline, symbol, start_date, end_date, frequency)
    
    if result.get('code') != 0:
        print("  API调用失败，使用模拟数据")
        result = mock_generator.generate_hist_kline(symbol, start_date.replace('-', ''), end_date.replace('-', ''), frequency)
    
    # 处理返回数据
    if result and result.get("code") == 0:
        kline_data_list = result.get("data", [])
        if kline_data_list:
            # 转换为DataFrame
            df = pd.DataFrame(kline_data_list)
            
            # 处理日期索引
            if 'date' in df.columns:
                # 处理不同的日期格式
                if df['date'].dtype == 'object':
                    # 字符串格式日期
                    if len(str(df['date'].iloc[0])) == 8:  # YYYYMMDD格式
                        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                    else:
                        df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            elif 'time' in df.columns:
                # 时间戳格式
                if df['time'].dtype in ['int64', 'float64']:
                    df['time'] = pd.to_datetime(df['time'], unit='ms')
                else:
                    df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
            
            # 确保数值列的数据类型正确
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
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
        print("  无数据可显示")
        return
    
    print_subsection_header(f"{symbol} K线数据摘要")
    print(f"  数据条数: {len(df)}")
    print(f"  时间范围: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"  价格区间: {df['low'].min():.2f} - {df['high'].max():.2f}")
    print(f"  平均成交量: {format_number(df['volume'].mean())}")
    
    print("\n  数据样例:")
    print(df.head().to_string())
    
    # 显示最新数据
    if len(df) > 0:
        latest = df.iloc[-1]
        print(f"\n  最新数据 ({df.index[-1].strftime('%Y-%m-%d')}):")
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
    if df.empty or 'close' not in df.columns:
        return df
    
    result_df = df.copy()
    
    # 移动平均线
    result_df['MA5'] = result_df['close'].rolling(window=5).mean()
    result_df['MA10'] = result_df['close'].rolling(window=10).mean()
    result_df['MA20'] = result_df['close'].rolling(window=20).mean()
    
    # 价格变化
    result_df['price_change'] = result_df['close'].diff()
    result_df['price_change_pct'] = result_df['close'].pct_change() * 100
    
    # 成交量移动平均
    result_df['volume_MA5'] = result_df['volume'].rolling(window=5).mean()
    
    # RSI指标 (简化版)
    if len(result_df) >= 14:
        delta = result_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        result_df['RSI'] = 100 - (100 / (1 + rs))
    
    return result_df


def demo_basic_kline_analysis():
    """基础K线数据分析演示"""
    print_section_header("历史K线API基础功能演示")
    
    # 演示参数
    symbol = config.demo_symbols[0]  # 贵州茅台
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    frequency = "1d"
    
    # 获取数据
    kline_df = get_hist_kline_data(symbol, start_date, end_date, frequency)
    
    if not kline_df.empty:
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
            if 'RSI' in latest_data and not pd.isna(latest_data['RSI']):
                print(f"    RSI:  {latest_data['RSI']:.2f}")
        
        # 简单的趋势分析
        print_subsection_header("趋势分析")
        if len(kline_df) >= 2:
            recent_change = kline_df['close'].iloc[-1] - kline_df['close'].iloc[-2]
            recent_change_pct = (recent_change / kline_df['close'].iloc[-2]) * 100
            print(f"  最近一日变化: {recent_change:+.2f} ({recent_change_pct:+.2f}%)")
            
            # 计算近期波动率
            if len(kline_df) >= 20:
                volatility = kline_df['close'].pct_change().rolling(20).std() * 100
                print(f"  20日波动率: {volatility.iloc[-1]:.2f}%")
    
    return kline_df


def demo_api_comparison():
    """API与本地库对比演示"""
    print_section_header("API与本地库对比演示")
    
    # 演示参数
    symbol = config.demo_symbols[0]  # 贵州茅台
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    frequency = "1d"
    
    print_subsection_header("使用API获取数据")
    
    # 获取API数据
    api_data = get_hist_kline_data(symbol, start_date, end_date, frequency)
    
    print_subsection_header("使用本地库获取数据")
    
    try:
        # 尝试导入xtdata库
        from xtquant import xtdata
        
        # 转换日期格式为xtdata需要的格式
        start_time = start_date.replace('-', '')
        end_time = end_date.replace('-', '')
        stock_list = [symbol]
        
        print(f"  正在通过xtdata获取 {symbol} 从 {start_date} 到 {end_date} 的数据...")
        
        # 调用xtdata.get_market_data
        local_kline_data_raw = xtdata.get_market_data(stock_list, frequency, start_time, end_time)
        
        if not local_kline_data_raw.empty:
            # 提取单只股票的数据
            local_kline_data = local_kline_data_raw.xs(symbol, level='symbol', drop_level=True)
            local_kline_data.index = pd.to_datetime(local_kline_data.index)
            
            print(f"  成功获取 {len(local_kline_data)} 条xtdata数据")
            print(f"  数据列: {local_kline_data.columns.tolist()}")
            
            # 显示数据样例
            print("\n  xtdata数据样例:")
            print(local_kline_data.head().to_string())
            
            # 计算移动平均线
            if len(local_kline_data) >= 20 and 'close' in local_kline_data.columns:
                close_prices = local_kline_data['close'].tolist()
                ma20 = sum(close_prices[-20:]) / 20
                print(f"\n  20日移动平均线 (xtdata): {ma20:.2f}")
            else:
                print("\n  数据不足，无法计算移动平均线")
                
            # 数据对比
            if not api_data.empty:
                print_subsection_header("数据对比分析")
                print(f"  API数据条数: {len(api_data)}")
                print(f"  xtdata数据条数: {len(local_kline_data)}")
                
                # 找到共同的日期范围进行对比
                common_dates = api_data.index.intersection(local_kline_data.index)
                if len(common_dates) > 0:
                    print(f"  共同日期数: {len(common_dates)}")
                    
                    # 对比最后几天的收盘价
                    if len(common_dates) >= 5:
                        recent_dates = common_dates[-5:]
                        print("\n  最近5日收盘价对比:")
                        for date in recent_dates:
                            api_close = api_data.loc[date, 'close'] if date in api_data.index else 'N/A'
                            xt_close = local_kline_data.loc[date, 'close'] if date in local_kline_data.index else 'N/A'
                            print(f"    {date.strftime('%Y-%m-%d')}: API={api_close:.2f}, xtdata={xt_close:.2f}")
                else:
                    print("  没有找到共同的日期数据")
            
            return local_kline_data
        else:
            print("  xtdata返回数据为空")
            return pd.DataFrame()
            
    except ImportError:
        print("  xtdata库未安装或不可用")
        print("  请确保已正确安装和配置xtdata环境")
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
            print(f"  价格范围: {kline_data['low'].min():.2f} - {kline_data['high'].max():.2f}")
            
            # 显示最新几条数据
            if len(kline_data) >= 3:
                print("\n  最新3条数据:")
                recent_data = kline_data.tail(3)[['open', 'high', 'low', 'close', 'volume']]
                print(recent_data.to_string())


def demo_error_handling():
    """错误处理演示"""
    print_section_header("错误处理演示")
    
    # 测试无效股票代码
    print_subsection_header("无效股票代码测试")
    invalid_symbol = "INVALID.XX"
    result = safe_api_call(api_client, api_client.get_hist_kline, invalid_symbol, "2023-01-01", "2023-01-31", "1d")
    print_api_result(result, "无效股票代码结果")
    
    # 测试无效日期范围
    print_subsection_header("无效日期范围测试")
    result = safe_api_call(api_client, api_client.get_hist_kline, "600519.SH", "2025-01-01", "2025-12-31", "1d")
    print_api_result(result, "未来日期结果")
    
    # 测试无效频率
    print_subsection_header("无效频率测试")
    result = safe_api_call(api_client, api_client.get_hist_kline, "600519.SH", "2023-01-01", "2023-01-31", "invalid")
    print_api_result(result, "无效频率结果")


def calculate_advanced_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算高级技术指标 - 优化版本
    
    Args:
        df: K线数据DataFrame
        
    Returns:
        pd.DataFrame: 包含高级技术指标的DataFrame
    """
    if df.empty or 'close' not in df.columns:
        return df
    
    result_df = df.copy()
    
    # 优化：使用向量化操作提高计算效率
    close_prices = result_df['close']
    high_prices = result_df['high']
    low_prices = result_df['low']
    
    # MACD指标 - 优化计算
    if len(result_df) >= 26:
        ema12 = close_prices.ewm(span=12, adjust=False).mean()
        ema26 = close_prices.ewm(span=26, adjust=False).mean()
        result_df['MACD'] = ema12 - ema26
        result_df['MACD_signal'] = result_df['MACD'].ewm(span=9, adjust=False).mean()
        result_df['MACD_histogram'] = result_df['MACD'] - result_df['MACD_signal']
    
    # 布林带 - 优化计算
    if len(result_df) >= 20:
        bb_period = 20
        bb_std_dev = 2
        sma20 = close_prices.rolling(window=bb_period, min_periods=bb_period).mean()
        std20 = close_prices.rolling(window=bb_period, min_periods=bb_period).std()
        
        result_df['BB_middle'] = sma20
        result_df['BB_upper'] = sma20 + (std20 * bb_std_dev)
        result_df['BB_lower'] = sma20 - (std20 * bb_std_dev)
        result_df['BB_width'] = result_df['BB_upper'] - result_df['BB_lower']
        
        # 避免除零错误
        bb_width_safe = result_df['BB_width'].replace(0, np.nan)
        result_df['BB_position'] = (close_prices - result_df['BB_lower']) / bb_width_safe
    
    # KDJ指标 - 优化计算
    if len(result_df) >= 9:
        kdj_period = 9
        low_min = low_prices.rolling(window=kdj_period, min_periods=kdj_period).min()
        high_max = high_prices.rolling(window=kdj_period, min_periods=kdj_period).max()
        
        # 避免除零错误
        hml_diff = high_max - low_min
        hml_diff_safe = hml_diff.replace(0, np.nan)
        rsv = (close_prices - low_min) / hml_diff_safe * 100
        
        result_df['K'] = rsv.ewm(com=2, adjust=False).mean()
        result_df['D'] = result_df['K'].ewm(com=2, adjust=False).mean()
        result_df['J'] = 3 * result_df['K'] - 2 * result_df['D']
    
    # 新增：威廉指标 (Williams %R)
    if len(result_df) >= 14:
        wr_period = 14
        high_max_wr = high_prices.rolling(window=wr_period, min_periods=wr_period).max()
        low_min_wr = low_prices.rolling(window=wr_period, min_periods=wr_period).min()
        
        hml_diff_wr = high_max_wr - low_min_wr
        hml_diff_wr_safe = hml_diff_wr.replace(0, np.nan)
        result_df['WR'] = (high_max_wr - close_prices) / hml_diff_wr_safe * -100
    
    # 新增：商品通道指数 (CCI)
    if len(result_df) >= 20:
        cci_period = 20
        typical_price = (high_prices + low_prices + close_prices) / 3
        sma_tp = typical_price.rolling(window=cci_period, min_periods=cci_period).mean()
        mad = typical_price.rolling(window=cci_period, min_periods=cci_period).apply(
            lambda x: np.mean(np.abs(x - x.mean())), raw=True
        )
        
        # 避免除零错误
        mad_safe = mad.replace(0, np.nan)
        result_df['CCI'] = (typical_price - sma_tp) / (0.015 * mad_safe)
    
    # 新增：平均真实波幅 (ATR)
    if len(result_df) >= 14:
        atr_period = 14
        prev_close = close_prices.shift(1)
        
        tr1 = high_prices - low_prices
        tr2 = np.abs(high_prices - prev_close)
        tr3 = np.abs(low_prices - prev_close)
        
        true_range = np.maximum(tr1, np.maximum(tr2, tr3))
        result_df['ATR'] = true_range.rolling(window=atr_period, min_periods=atr_period).mean()
    
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
        return {}
    
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
        'symbol': symbol,
        'dates': sampled_df.index.strftime('%Y-%m-%d').tolist(),
        'ohlc': {
            'open': sampled_df['open'].round(2).tolist(),
            'high': sampled_df['high'].round(2).tolist(),
            'low': sampled_df['low'].round(2).tolist(),
            'close': sampled_df['close'].round(2).tolist()
        },
        'volume': sampled_df['volume'].astype(int).tolist(),
        'indicators': {},
        'metadata': {
            'total_points': len(df),
            'sampled_points': len(sampled_df),
            'compression_ratio': len(sampled_df) / len(df) if len(df) > 0 else 1,
            'date_range': {
                'start': df.index[0].strftime('%Y-%m-%d'),
                'end': df.index[-1].strftime('%Y-%m-%d')
            }
        }
    }
    
    # 添加技术指标数据（包含新增指标）
    indicator_columns = ['MA5', 'MA10', 'MA20', 'RSI', 'MACD', 'MACD_signal', 
                        'BB_upper', 'BB_middle', 'BB_lower', 'K', 'D', 'J',
                        'WR', 'CCI', 'ATR']
    
    for col in indicator_columns:
        if col in sampled_df.columns:
            # 使用更高效的数据类型转换
            values = sampled_df[col].round(2).fillna(0)
            viz_data['indicators'][col] = values.tolist()
    
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
        return {'error': '无数据可分析'}
    
    # 计算高级技术指标
    df_with_indicators = calculate_advanced_indicators(df)
    
    # 基础统计
    latest = df_with_indicators.iloc[-1]
    price_stats = {
        'current_price': float(latest['close']),
        'price_change': float(latest['close'] - df_with_indicators.iloc[-2]['close']) if len(df_with_indicators) > 1 else 0,
        'price_change_pct': float(((latest['close'] - df_with_indicators.iloc[-2]['close']) / df_with_indicators.iloc[-2]['close'] * 100)) if len(df_with_indicators) > 1 else 0,
        'high_52w': float(df_with_indicators['high'].max()),
        'low_52w': float(df_with_indicators['low'].min()),
        'avg_volume': int(df_with_indicators['volume'].mean())
    }
    
    # 技术分析
    technical_analysis = {}
    
    # 趋势分析
    if 'MA20' in df_with_indicators.columns and not pd.isna(latest['MA20']):
        if latest['close'] > latest['MA20']:
            trend = '上升趋势'
        else:
            trend = '下降趋势'
        technical_analysis['trend'] = trend
        technical_analysis['ma20_distance'] = float((latest['close'] - latest['MA20']) / latest['MA20'] * 100)
    
    # RSI分析
    if 'RSI' in df_with_indicators.columns and not pd.isna(latest['RSI']):
        rsi_value = float(latest['RSI'])
        if rsi_value > 70:
            rsi_signal = '超买'
        elif rsi_value < 30:
            rsi_signal = '超卖'
        else:
            rsi_signal = '正常'
        technical_analysis['rsi'] = {'value': rsi_value, 'signal': rsi_signal}
    
    # MACD分析
    if 'MACD' in df_with_indicators.columns and not pd.isna(latest['MACD']):
        macd_value = float(latest['MACD'])
        macd_signal = float(latest['MACD_signal']) if not pd.isna(latest['MACD_signal']) else 0
        if macd_value > macd_signal:
            macd_trend = '金叉'
        else:
            macd_trend = '死叉'
        technical_analysis['macd'] = {
            'value': macd_value,
            'signal': macd_signal,
            'trend': macd_trend
        }
    
    # 布林带分析
    if 'BB_position' in df_with_indicators.columns and not pd.isna(latest['BB_position']):
        bb_pos = float(latest['BB_position'])
        if bb_pos > 0.8:
            bb_signal = '接近上轨'
        elif bb_pos < 0.2:
            bb_signal = '接近下轨'
        else:
            bb_signal = '中轨附近'
        technical_analysis['bollinger'] = {'position': bb_pos, 'signal': bb_signal}
    
    # 波动率分析
    if len(df_with_indicators) >= 20:
        volatility = float(df_with_indicators['close'].pct_change().rolling(20).std() * 100)
        technical_analysis['volatility'] = volatility
    
    return {
        'symbol': symbol,
        'analysis_date': df_with_indicators.index[-1].strftime('%Y-%m-%d'),
        'price_stats': price_stats,
        'technical_analysis': technical_analysis,
        'data_points': len(df_with_indicators)
    }


def generate_chart_config(viz_data: dict, analysis_report: dict) -> dict:
    """生成图表配置
    
    Args:
        viz_data: 可视化数据
        analysis_report: 分析报告
        
    Returns:
        dict: 图表配置
    """
    if not viz_data or 'error' in analysis_report:
        return {'main_chart': 'K线图', 'sub_charts': [], 'theme': '默认'}
    
    # 基础图表配置
    chart_config = {
        'main_chart': 'K线图',
        'sub_charts': [],
        'theme': '默认',
        'indicators': {
            'main_panel': [],
            'sub_panels': []
        },
        'colors': {
            'up': '#ff4757',      # 上涨红色
            'down': '#2ed573',    # 下跌绿色
            'ma5': '#ffa502',     # MA5橙色
            'ma10': '#3742fa',    # MA10蓝色
            'ma20': '#ff6b81',    # MA20粉色
            'volume': '#70a1ff'   # 成交量蓝色
        },
        'layout': {
            'main_height': 0.7,   # 主图占比70%
            'sub_height': 0.3     # 副图占比30%
        }
    }
    
    # 根据可用指标配置图表
    available_indicators = viz_data.get('indicators', {})
    
    # 主图指标（价格相关）
    main_indicators = []
    if 'MA5' in available_indicators:
        main_indicators.append('MA5')
    if 'MA10' in available_indicators:
        main_indicators.append('MA10')
    if 'MA20' in available_indicators:
        main_indicators.append('MA20')
    if 'BB_upper' in available_indicators and 'BB_lower' in available_indicators:
        main_indicators.extend(['BB_upper', 'BB_middle', 'BB_lower'])
    
    chart_config['indicators']['main_panel'] = main_indicators
    
    # 副图指标
    sub_indicators = []
    if 'RSI' in available_indicators:
        sub_indicators.append('RSI')
        chart_config['sub_charts'].append('RSI')
    if 'MACD' in available_indicators:
        sub_indicators.append('MACD')
        chart_config['sub_charts'].append('MACD')
    if 'K' in available_indicators and 'D' in available_indicators:
        sub_indicators.extend(['K', 'D', 'J'])
        chart_config['sub_charts'].append('KDJ')
    
    chart_config['indicators']['sub_panels'] = sub_indicators
    
    # 根据技术分析结果调整主题
    if 'technical_analysis' in analysis_report:
        tech = analysis_report['technical_analysis']
        
        # 根据趋势调整颜色主题
        if tech.get('trend') == '上升趋势':
            chart_config['theme'] = '牛市主题'
            chart_config['colors']['background'] = '#f8f9fa'
        elif tech.get('trend') == '下降趋势':
            chart_config['theme'] = '熊市主题'
            chart_config['colors']['background'] = '#343a40'
        
        # 根据波动率调整布局
        volatility = tech.get('volatility', 0)
        if volatility > 5.0:  # 高波动率
            chart_config['layout']['sub_height'] = 0.4  # 增加副图比例
            chart_config['layout']['main_height'] = 0.6
    
    return chart_config


def create_enhanced_visualization():
    """高级可视化演示 - 优化版本"""
    print_section_header("高级可视化和分析演示")
    
    symbol = config.demo_symbols[0]
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    
    # 获取数据
    kline_df = get_hist_kline_data(symbol, start_date, end_date, "1d")
    
    if kline_df.empty:
        print("  无法获取数据，跳过可视化演示")
        return
    
    print_subsection_header("创建优化的可视化数据结构")
    viz_data = create_visualization_data(kline_df, symbol)
    
    if viz_data:
        print(f"  数据点数量: {len(viz_data['dates'])}")
        print(f"  价格范围: {min(viz_data['ohlc']['low']):.2f} - {max(viz_data['ohlc']['high']):.2f}")
        print(f"  可用指标: {list(viz_data['indicators'].keys())}")
        
        # 显示最新的技术指标值
        if viz_data['indicators']:
            print("\n  最新技术指标:")
            for indicator, values in viz_data['indicators'].items():
                if values and values[-1] != 0:
                    print(f"    {indicator}: {values[-1]:.2f}")
    
    print_subsection_header("生成增强分析报告")
    analysis_report = generate_analysis_report(kline_df, symbol)
    
    if 'error' not in analysis_report:
        print(f"  分析日期: {analysis_report['analysis_date']}")
        print(f"  当前价格: {analysis_report['price_stats']['current_price']:.2f}")
        print(f"  价格变化: {analysis_report['price_stats']['price_change']:+.2f} ({analysis_report['price_stats']['price_change_pct']:+.2f}%)")
        
        if 'technical_analysis' in analysis_report:
            tech = analysis_report['technical_analysis']
            if 'trend' in tech:
                print(f"  趋势判断: {tech['trend']}")
            if 'rsi' in tech:
                print(f"  RSI信号: {tech['rsi']['signal']} ({tech['rsi']['value']:.2f})")
            if 'macd' in tech:
                print(f"  MACD信号: {tech['macd']['trend']}")
            if 'volatility' in tech:
                print(f"  波动率: {tech['volatility']:.2f}%")
    
    # 新增：生成图表配置
    chart_config = generate_chart_config(viz_data, analysis_report)
    print_subsection_header("图表配置生成")
    print(f"  主图表类型: {chart_config.get('main_chart', 'K线图')}")
    print(f"  副图指标: {', '.join(chart_config.get('sub_charts', []))}")
    print(f"  颜色主题: {chart_config.get('theme', '默认')}")
    
    return viz_data, analysis_report, chart_config


def demo_performance_optimization():
    """性能优化演示"""
    print_section_header("性能优化演示")
    
    import time
    import os
    
    # 检查psutil是否可用
    if psutil is None:
        print("  psutil库不可用，跳过内存监控")
        process = None
    else:
        # 获取当前进程
        process = psutil.Process(os.getpid())
    
    print_subsection_header("内存使用优化测试")
    
    # 记录初始内存使用
    if process:
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"  初始内存使用: {initial_memory:.2f} MB")
    else:
        initial_memory = 0
        print("  内存监控不可用，跳过内存统计")
    
    # 测试大量数据处理
    symbols = config.demo_symbols[:3]  # 限制测试股票数量
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    
    start_time = time.time()
    processed_data = []
    
    for i, symbol in enumerate(symbols, 1):
        print(f"  [{i}/{len(symbols)}] 处理 {symbol}...")
        
        # 获取数据
        kline_df = get_hist_kline_data(symbol, start_date, end_date, "1d")
        
        if not kline_df.empty:
            # 使用优化的可视化数据创建（限制数据点）
            viz_data = create_visualization_data(kline_df, symbol)
            processed_data.append(viz_data)
            
            # 显示内存使用
            if process:
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"    数据点: {len(viz_data.get('dates', []))}, 内存: {current_memory:.2f} MB")
            else:
                print(f"    数据点: {len(viz_data.get('dates', []))}")
    
    end_time = time.time()
    
    if process:
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
    else:
        memory_growth = 0
    
    print_subsection_header("性能统计")
    print(f"  处理时间: {end_time - start_time:.2f} 秒")
    if process:
        print(f"  内存增长: {memory_growth:.2f} MB")
    print(f"  平均每股票处理时间: {(end_time - start_time) / len(symbols):.2f} 秒")
    print(f"  数据压缩率: {len(processed_data)} 个可视化数据集")
    
    # 性能优化建议
    print_subsection_header("性能优化建议")
    optimization_tips = [
        "数据采样: 对于长时间序列，使用采样减少数据点",
        "内存管理: 及时释放不需要的DataFrame",
        "批量处理: 合并多个API调用减少网络开销",
        "缓存策略: 缓存计算结果避免重复计算",
        "异步处理: 使用异步IO提高并发性能"
    ]
    
    for tip in optimization_tips:
        print(f"  • {tip}")
    
    return processed_data


def demo_advanced_trading_strategies():
    """高级交易策略分析演示 - 新增功能"""
    print_section_header("高级交易策略分析演示")
    
    symbol = config.demo_symbols[0]
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    
    # 获取数据
    kline_df = get_hist_kline_data(symbol, start_date, end_date, "1d")
    
    if kline_df.empty:
        print("  无法获取数据，跳过策略分析演示")
        return
    
    # 计算高级技术指标
    df_with_indicators = calculate_advanced_indicators(kline_df)
    
    print_subsection_header("策略1: 均线交叉策略")
    if 'MA5' in df_with_indicators.columns and 'MA20' in df_with_indicators.columns:
        # 计算均线交叉信号
        ma5 = df_with_indicators['MA5']
        ma20 = df_with_indicators['MA20']
        
        # 创建交叉信号
        df_with_indicators['golden_cross'] = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
        df_with_indicators['death_cross'] = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))
        
        # 统计交叉次数
        golden_crosses = df_with_indicators['golden_cross'].sum()
        death_crosses = df_with_indicators['death_cross'].sum()
        
        print(f"  金叉次数: {golden_crosses}")
        print(f"  死叉次数: {death_crosses}")
        
        # 显示最近的交叉信号
        recent_signals = df_with_indicators[df_with_indicators['golden_cross'] | df_with_indicators['death_cross']].tail(3)
        if not recent_signals.empty:
            print("\n  最近的交叉信号:")
            for idx, row in recent_signals.iterrows():
                signal_type = "金叉" if row['golden_cross'] else "死叉"
                print(f"    {idx.strftime('%Y-%m-%d')}: {signal_type} (MA5={row['MA5']:.2f}, MA20={row['MA20']:.2f})")
    
    print_subsection_header("策略2: RSI超买超卖策略")
    if 'RSI' in df_with_indicators.columns:
        # 创建RSI信号
        df_with_indicators['rsi_oversold'] = df_with_indicators['RSI'] < 30
        df_with_indicators['rsi_overbought'] = df_with_indicators['RSI'] > 70
        
        # 统计信号次数
        oversold_count = df_with_indicators['rsi_oversold'].sum()
        overbought_count = df_with_indicators['rsi_overbought'].sum()
        
        print(f"  超卖信号次数: {oversold_count}")
        print(f"  超买信号次数: {overbought_count}")
        
        # 显示最近的RSI信号
        recent_rsi_signals = df_with_indicators[df_with_indicators['rsi_oversold'] | df_with_indicators['rsi_overbought']].tail(3)
        if not recent_rsi_signals.empty:
            print("\n  最近的RSI信号:")
            for idx, row in recent_rsi_signals.iterrows():
                signal_type = "超卖" if row['rsi_oversold'] else "超买"
                print(f"    {idx.strftime('%Y-%m-%d')}: {signal_type} (RSI={row['RSI']:.2f}, 价格={row['close']:.2f})")
    
    print_subsection_header("策略3: 布林带突破策略")
    if all(col in df_with_indicators.columns for col in ['BB_upper', 'BB_lower']):
        # 创建布林带突破信号
        df_with_indicators['bb_upper_break'] = df_with_indicators['close'] > df_with_indicators['BB_upper']
        df_with_indicators['bb_lower_break'] = df_with_indicators['close'] < df_with_indicators['BB_lower']
        
        # 统计突破次数
        upper_breaks = df_with_indicators['bb_upper_break'].sum()
        lower_breaks = df_with_indicators['bb_lower_break'].sum()
        
        print(f"  上轨突破次数: {upper_breaks}")
        print(f"  下轨突破次数: {lower_breaks}")
        
        # 显示最近的突破信号
        recent_bb_signals = df_with_indicators[df_with_indicators['bb_upper_break'] | df_with_indicators['bb_lower_break']].tail(3)
        if not recent_bb_signals.empty:
            print("\n  最近的布林带突破信号:")
            for idx, row in recent_bb_signals.iterrows():
                signal_type = "上轨突破" if row['bb_upper_break'] else "下轨突破"
                print(f"    {idx.strftime('%Y-%m-%d')}: {signal_type} (价格={row['close']:.2f}, 上轨={row.get('BB_upper', 0):.2f}, 下轨={row.get('BB_lower', 0):.2f})")
    
    # 策略回测简单示例
    print_subsection_header("简单策略回测示例")
    print("  注: 这是一个简化的回测示例，实际交易需要考虑更多因素")
    
    # 初始资金
    initial_capital = 100000
    position = 0
    cash = initial_capital
    trades = []
    
    # 使用MA5和MA20交叉策略进行简单回测
    if 'MA5' in df_with_indicators.columns and 'MA20' in df_with_indicators.columns:
        for idx, row in df_with_indicators.iterrows():
            if pd.isna(row['MA5']) or pd.isna(row['MA20']):
                continue
                
            # 金叉买入信号
            if row['MA5'] > row['MA20'] and (position == 0):
                # 计算可买入股数
                shares = int(cash / row['close'] / 100) * 100  # 按手(100股)购买
                if shares > 0:
                    cost = shares * row['close']
                    cash -= cost
                    position += shares
                    trades.append({
                        'date': idx.strftime('%Y-%m-%d'),
                        'type': '买入',
                        'price': row['close'],
                        'shares': shares,
                        'cost': cost,
                        'cash': cash
                    })
            
            # 死叉卖出信号
            elif row['MA5'] < row['MA20'] and position > 0:
                # 卖出所有持仓
                proceeds = position * row['close']
                cash += proceeds
                trades.append({
                    'date': idx.strftime('%Y-%m-%d'),
                    'type': '卖出',
                    'price': row['close'],
                    'shares': position,
                    'proceeds': proceeds,
                    'cash': cash
                })
                position = 0
    
    # 计算最终资产
    final_value = cash
    if position > 0:
        final_value += position * df_with_indicators['close'].iloc[-1]
    
    # 计算收益率
    profit = final_value - initial_capital
    profit_pct = (profit / initial_capital) * 100
    
    print(f"  初始资金: {format_number(initial_capital)} 元")
    print(f"  最终资产: {format_number(final_value)} 元")
    print(f"  总收益: {format_number(profit)} 元 ({profit_pct:.2f}%)")
    print(f"  交易次数: {len(trades)}")
    
    # 显示部分交易记录
    if trades:
        print("\n  交易记录示例 (最多显示3条):")
        for trade in trades[:3]:
            print(f"    {trade['date']} {trade['type']} {trade['shares']}股 @ {trade['price']:.2f}")
    
    return df_with_indicators


def main():
    """主函数"""
    print_section_header("历史K线API教程")
    
    # 基础功能演示
    kline_df = demo_basic_kline_analysis()
    
    # API与本地库对比演示
    demo_api_comparison()
    
    # 多周期数据演示
    demo_multiple_frequencies()
    
    # 错误处理演示
    demo_error_handling()
    
    # 高级可视化和分析演示
    create_enhanced_visualization()
    
    # 性能优化演示
    demo_performance_optimization()
    
    # 高级交易策略分析演示
    demo_advanced_trading_strategies()
    
    # 显示性能统计
    if performance_monitor:
        performance_monitor.print_summary()


if __name__ == "__main__":
    main()