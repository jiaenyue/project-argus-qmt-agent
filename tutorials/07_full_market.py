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
# 支持通过HTTP API和xtdata库两种方式获取数据，具备完善的错误处理和降级机制。
#
# **功能特性**:
# - 统一的API调用接口
# - 自动重试和错误处理
# - API不可用时自动切换到模拟数据
# - 深度行情分析和可视化
# - 性能优化和大数据处理

import time
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

# 导入统一工具库
from common.api_client import QMTAPIClient, create_api_client, safe_api_call
from common.mock_data import MockDataGenerator
from common.utils import (
    print_section_header, print_subsection_header, print_api_result,
    PerformanceMonitor, format_response_time, create_demo_context
)
from common.config import get_config

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
performance_monitor = demo_context['performance_monitor']
api_client = create_api_client(enable_monitoring=True)
mock_generator = MockDataGenerator()


# ## 1. 深度行情数据处理类

class MarketDepthAnalyzer:
    """深度行情数据分析器
    
    提供完整行情数据的处理、分析和可视化功能。
    支持多种数据源和高效的大数据处理。
    """
    
    def __init__(self, api_client: QMTAPIClient, mock_generator: MockDataGenerator):
        """初始化深度行情分析器
        
        Args:
            api_client: API客户端实例
            mock_generator: 模拟数据生成器
        """
        self.api_client = api_client
        self.mock_generator = mock_generator
        self.data_cache = {}  # 数据缓存
        self.subscriptions = {}  # 订阅管理
        self.data_queue = queue.Queue()  # 数据处理队列
        self.is_running = False
        self.processor_thread = None
        
        # 性能监控
        self.performance_monitor = PerformanceMonitor()
        
        # 市场统计数据
        self.market_stats = {
            'SH': {'up_count': 0, 'down_count': 0, 'flat_count': 0, 'total': 0},
            'SZ': {'up_count': 0, 'down_count': 0, 'flat_count': 0, 'total': 0}
        }
        
        # 板块统计数据
        self.sector_stats = defaultdict(lambda: {'up_count': 0, 'down_count': 0, 'flat_count': 0, 'total': 0})
    
    def start_processing(self):
        """启动数据处理线程"""
        if self.is_running:
            print("数据处理器已在运行中")
            return
        
        self.is_running = True
        self.processor_thread = threading.Thread(target=self._process_data_queue)
        self.processor_thread.daemon = True
        self.processor_thread.start()
        print("深度行情数据处理器已启动")
    
    def stop_processing(self):
        """停止数据处理"""
        self.is_running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=5)
        print("深度行情数据处理器已停止")
    
    def _process_data_queue(self):
        """处理数据队列（后台线程）"""
        while self.is_running:
            try:
                # 从队列获取数据，超时1秒
                item = self.data_queue.get(timeout=1)
                
                # 处理数据
                self._process_market_data(item)
                
                self.data_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"数据处理错误: {e}")
    
    def _process_market_data(self, data_item: Dict):
        """处理市场数据
        
        Args:
            data_item: 市场数据项
        """
        data_type = data_item.get('type', 'unknown')
        data = data_item.get('data', {})
        
        if data_type == 'full_market':
            # 处理完整行情数据
            self._update_market_stats(data)
            
            # 记录性能统计
            self.performance_monitor.record_api_call(
                'process_full_market', 
                0.005,  # 处理时间很短
                True
            )
        elif data_type == 'tick_data':
            # 处理逐笔成交数据
            symbol = data_item.get('symbol', '')
            if symbol:
                self._process_tick_data(symbol, data)
    
    def _update_market_stats(self, market_data: List[Dict]):
        """更新市场统计数据
        
        Args:
            market_data: 市场数据列表
        """
        # 重置统计数据
        for market in self.market_stats:
            self.market_stats[market] = {'up_count': 0, 'down_count': 0, 'flat_count': 0, 'total': 0}
        
        self.sector_stats.clear()
        
        # 统计涨跌家数
        for stock_data in market_data:
            symbol = stock_data.get('symbol', '')
            if not symbol:
                continue
                
            # 提取市场和板块信息
            market = symbol.split('.')[-1] if '.' in symbol else ''
            sector = stock_data.get('sector', 'unknown')
            
            # 判断涨跌
            change = stock_data.get('change', 0)
            
            # 更新市场统计
            if market in self.market_stats:
                self.market_stats[market]['total'] += 1
                
                if change > 0:
                    self.market_stats[market]['up_count'] += 1
                elif change < 0:
                    self.market_stats[market]['down_count'] += 1
                else:
                    self.market_stats[market]['flat_count'] += 1
            
            # 更新板块统计
            self.sector_stats[sector]['total'] += 1
            
            if change > 0:
                self.sector_stats[sector]['up_count'] += 1
            elif change < 0:
                self.sector_stats[sector]['down_count'] += 1
            else:
                self.sector_stats[sector]['flat_count'] += 1
    
    def _process_tick_data(self, symbol: str, tick_data: Dict):
        """处理逐笔成交数据
        
        Args:
            symbol: 股票代码
            tick_data: 逐笔成交数据
        """
        # 缓存数据
        if symbol not in self.data_cache:
            self.data_cache[symbol] = {
                'ticks': [],
                'last_update': time.time()
            }
        
        # 添加新数据
        self.data_cache[symbol]['ticks'].append(tick_data)
        self.data_cache[symbol]['last_update'] = time.time()
        
        # 限制缓存大小
        max_ticks = 1000  # 最多保留1000条逐笔数据
        if len(self.data_cache[symbol]['ticks']) > max_ticks:
            self.data_cache[symbol]['ticks'] = self.data_cache[symbol]['ticks'][-max_ticks:]
    
    def get_market_stats(self) -> Dict:
        """获取市场统计数据
        
        Returns:
            Dict: 市场统计数据
        """
        return {
            'markets': self.market_stats,
            'sectors': dict(self.sector_stats),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_market_breadth(self) -> Dict:
        """获取市场宽度指标
        
        Returns:
            Dict: 市场宽度指标
        """
        breadth = {}
        
        for market, stats in self.market_stats.items():
            if stats['total'] > 0:
                advance_decline_ratio = stats['up_count'] / max(stats['down_count'], 1)
                breadth_index = (stats['up_count'] - stats['down_count']) / stats['total'] * 100
                
                breadth[market] = {
                    'advance_decline_ratio': round(advance_decline_ratio, 2),
                    'breadth_index': round(breadth_index, 2),
                    'up_percent': round(stats['up_count'] / stats['total'] * 100, 2),
                    'down_percent': round(stats['down_count'] / stats['total'] * 100, 2),
                    'flat_percent': round(stats['flat_count'] / stats['total'] * 100, 2)
                }
        
        return breadth
    
    def get_sector_performance(self, top_n: int = 5) -> Dict:
        """获取板块表现排名
        
        Args:
            top_n: 返回前N个板块
            
        Returns:
            Dict: 板块表现数据
        """
        # 计算板块强度指标
        sector_strength = []
        
        for sector, stats in self.sector_stats.items():
            if stats['total'] >= 5:  # 至少包含5只股票
                strength = (stats['up_count'] - stats['down_count']) / stats['total'] * 100
                sector_strength.append({
                    'sector': sector,
                    'strength': strength,
                    'up_count': stats['up_count'],
                    'down_count': stats['down_count'],
                    'total': stats['total'],
                    'up_percent': round(stats['up_count'] / stats['total'] * 100, 2)
                })
        
        # 按强度排序
        sector_strength.sort(key=lambda x: x['strength'], reverse=True)
        
        return {
            'top_sectors': sector_strength[:top_n],
            'bottom_sectors': sector_strength[-top_n:],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def analyze_tick_data(self, symbol: str) -> Dict:
        """分析逐笔成交数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 分析结果
        """
        if symbol not in self.data_cache or not self.data_cache[symbol]['ticks']:
            return {'error': '无可用数据'}
        
        ticks = self.data_cache[symbol]['ticks']
        
        # 提取价格和成交量
        prices = [tick.get('price', 0) for tick in ticks]
        volumes = [tick.get('volume', 0) for tick in ticks]
        
        # 计算统计指标
        avg_price = sum(prices) / len(prices) if prices else 0
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        price_volatility = np.std(prices) if len(prices) > 1 else 0
        
        # 分析买卖盘口
        buy_orders = [tick for tick in ticks if tick.get('direction') == 'B']
        sell_orders = [tick for tick in ticks if tick.get('direction') == 'S']
        
        buy_volume = sum(tick.get('volume', 0) for tick in buy_orders)
        sell_volume = sum(tick.get('volume', 0) for tick in sell_orders)
        
        # 计算买卖比
        buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')
        
        return {
            'symbol': symbol,
            'tick_count': len(ticks),
            'avg_price': round(avg_price, 2),
            'avg_volume': round(avg_volume, 2),
            'price_volatility': round(price_volatility, 4),
            'buy_count': len(buy_orders),
            'sell_count': len(sell_orders),
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'buy_sell_ratio': round(buy_sell_ratio, 2),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def visualize_market_breadth(self):
        """可视化市场宽度指标"""
        try:
            breadth = self.get_market_breadth()
            
            if not breadth:
                print("暂无市场宽度数据可视化")
                return
            
            # 创建图表
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 准备数据
            markets = list(breadth.keys())
            up_percents = [breadth[m]['up_percent'] for m in markets]
            down_percents = [breadth[m]['down_percent'] for m in markets]
            flat_percents = [breadth[m]['flat_percent'] for m in markets]
            
            # 绘制堆叠柱状图
            width = 0.35
            ax.bar(markets, up_percents, width, label='上涨', color='red')
            ax.bar(markets, down_percents, width, bottom=up_percents, label='下跌', color='green')
            ax.bar(markets, flat_percents, width, bottom=[up + down for up, down in zip(up_percents, down_percents)], 
                  label='平盘', color='gray')
            
            # 添加标签和图例
            ax.set_ylabel('百分比')
            ax.set_title('市场涨跌分布')
            ax.legend()
            
            # 显示图表
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            print(f"可视化市场宽度时出错: {e}")
    
    def visualize_sector_performance(self, top_n: int = 5):
        """可视化板块表现
        
        Args:
            top_n: 显示前N个板块
        """
        try:
            sector_data = self.get_sector_performance(top_n)
            
            if not sector_data or not sector_data['top_sectors']:
                print("暂无板块表现数据可视化")
                return
            
            # 创建图表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # 准备数据 - 最强板块
            top_sectors = sector_data['top_sectors']
            top_names = [s['sector'] for s in top_sectors]
            top_strengths = [s['strength'] for s in top_sectors]
            
            # 绘制最强板块
            bars1 = ax1.bar(top_names, top_strengths, color='red')
            ax1.set_title('最强板块')
            ax1.set_ylabel('强度指标')
            
            # 为柱状图添加数值标签
            for bar in bars1:
                height = bar.get_height()
                ax1.annotate(f'{height:.1f}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3),  # 3点垂直偏移
                            textcoords="offset points",
                            ha='center', va='bottom')
            
            # 准备数据 - 最弱板块
            bottom_sectors = sector_data['bottom_sectors']
            bottom_names = [s['sector'] for s in bottom_sectors]
            bottom_strengths = [s['strength'] for s in bottom_sectors]
            
            # 绘制最弱板块
            bars2 = ax2.bar(bottom_names, bottom_strengths, color='green')
            ax2.set_title('最弱板块')
            ax2.set_ylabel('强度指标')
            
            # 为柱状图添加数值标签
            for bar in bars2:
                height = bar.get_height()
                ax2.annotate(f'{height:.1f}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3 if height >= 0 else -15),
                            textcoords="offset points",
                            ha='center', va='bottom')
            
            # 显示图表
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            print(f"可视化板块表现时出错: {e}")
    
    def get_performance_stats(self) -> Dict:
        """获取性能统计
        
        Returns:
            Dict: 性能统计数据
        """
        return self.performance_monitor.export_stats()

# 创建深度行情分析器实例
market_analyzer = MarketDepthAnalyzer(api_client, mock_generator)


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
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"收到全推行情数据更新，时间: {timestamp}")
        
        for symbol, data in datas.items():
            # 将数据放入处理队列
            market_analyzer.data_queue.put({
                'type': 'tick_data',
                'symbol': symbol,
                'data': data,
                'timestamp': timestamp
            })
            
            # 显示部分数据
            print(f"  合约代码: {symbol}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}")
    
    # 订阅全推行情数据
    print("\n开始订阅沪深两市全推行情数据...")
    
    subscription_id = None
    
    # 尝试使用xtdata库订阅
    if XTDATA_AVAILABLE:
        try:
            subscription_id = xtdata.subscribe_whole_quote(
                code_list=['SH', 'SZ'], 
                callback=on_full_tick_data
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
            result = safe_api_call(
                api_client,
                api_client.subscribe_whole_quote,
                ['SH', 'SZ']
            )
            
            if result.get('code') == 0:
                subscription_id = result.get('data', {}).get('subscription_id')
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
    
    demo_symbols = ['600519.SH', '000001.SZ', '601318.SH']
    
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
                    print(f"  合约代码: {symbol}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}")
                success = True
            else:
                print("未能获取全推数据快照，尝试使用API...")
        except Exception as e:
            print(f"xtdata.get_full_tick调用异常: {e}")
    
    # 方式2: 使用统一API客户端
    if not success:
        try:
            print("\n尝试使用API获取全推数据快照...")
            result = safe_api_call(
                api_client,
                api_client.get_full_tick,
                demo_symbols
            )
            
            if result.get('code') == 0:
                full_tick_data = result['data']
                print("成功通过API获取全推数据快照:")
                for symbol, data in full_tick_data.items():
                    print(f"  合约代码: {symbol}, 最新价: {data.get('lastPrice')}, 成交量: {data.get('volume')}")
                success = True
            else:
                print(f"API获取失败: {result.get('message', '未知错误')}")
        except Exception as e:
            print(f"API调用异常: {e}")
    
    # 方式3: 使用模拟数据
    if not success:
        print("\n使用模拟数据生成全推数据快照...")
        mock_result = mock_generator.generate_full_tick(demo_symbols)
        
        if mock_result.get('code') == 0:
            full_tick_data = mock_result['data']
            print("成功生成模拟全推数据快照:")
            for symbol, data in full_tick_data.items():
                print(f"  合约代码: {symbol}, 最新价: {data.get('current_price', data.get('lastPrice'))}, 成交量: {data.get('volume')}")
            success = True
        else:
            print("模拟数据生成失败")
    
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
        result = safe_api_call(
            api_client,
            api_client.get_full_market,
            market='SH'  # 获取上证市场数据
        )
        
        if result.get('code') == 0:
            market_data = result['data']
            print(f"成功获取完整市场数据，共 {len(market_data)} 条记录")
            success = True
        else:
            print(f"API获取失败: {result.get('message', '未知错误')}")
    except Exception as e:
        print(f"API调用异常: {e}")
    
    # 方式2: 使用模拟数据
    if not success:
        print("\n使用模拟数据生成完整市场数据...")
        mock_result = mock_generator.generate_full_market(market='SH')
        
        if mock_result.get('code') == 0:
            market_data = mock_result['data']
            print(f"成功生成模拟市场数据，共 {len(market_data)} 条记录")
            success = True
        else:
            print("模拟数据生成失败")
    
    # 将数据传入分析器
    if market_data:
        market_analyzer.data_queue.put({
            'type': 'full_market',
            'data': market_data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # 等待数据处理完成
        time.sleep(1)
    
    # 演示市场宽度分析
    print_subsection_header("2. 市场宽度分析")
    
    market_stats = market_analyzer.get_market_stats()
    print("\n市场涨跌统计:")
    
    for market, stats in market_stats.get('markets', {}).items():
        total = stats.get('total', 0)
        if total > 0:
            up_count = stats.get('up_count', 0)
            down_count = stats.get('down_count', 0)
            flat_count = stats.get('flat_count', 0)
            
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
        print("\n注意: 在支持可视化的环境中，可以调用 market_analyzer.visualize_market_breadth() 查看图表")
    except Exception as e:
        print(f"\n可视化市场宽度时出错: {e}")
    
    # 演示板块表现分析
    print_subsection_header("3. 板块表现分析")
    
    sector_performance = market_analyzer.get_sector_performance(top_n=3)
    
    print("\n最强板块:")
    for sector in sector_performance.get('top_sectors', []):
        print(f"  {sector['sector']}: 强度 {sector['strength']:.1f}, 上涨率 {sector['up_percent']}%")
    
    print("\n最弱板块:")
    for sector in sector_performance.get('bottom_sectors', []):
        print(f"  {sector['sector']}: 强度 {sector['strength']:.1f}, 上涨率 {sector['up_percent']}%")
    
    # 可视化板块表现（如果在支持可视化的环境中）
    try:
        # 尝试可视化，但不中断程序流程
        # market_analyzer.visualize_sector_performance()
        print("\n注意: 在支持可视化的环境中，可以调用 market_analyzer.visualize_sector_performance() 查看图表")
    except Exception as e:
        print(f"\n可视化板块表现时出错: {e}")
    
    return market_data

# ## 4. 大数据量处理优化演示

def demonstrate_large_data_processing():
    """演示大数据量处理优化"""
    print_section_header("大数据量处理优化演示")
    
    # 生成大量模拟数据
    print_subsection_header("1. 生成大量模拟数据")
    
    stock_count = 1000  # 模拟1000只股票
    print(f"\n生成 {stock_count} 只股票的模拟数据...")
    
    # 创建股票代码列表
    sh_stocks = [f"60{i:04d}.SH" for i in range(500)]
    sz_stocks = [f"00{i:04d}.SZ" for i in range(500)]
    all_stocks = sh_stocks + sz_stocks
    
    # 记录开始时间
    start_time = time.time()
    
    # 批量生成数据
    batch_size = 100  # 每批处理100只股票
    batches = [all_stocks[i:i+batch_size] for i in range(0, len(all_stocks), batch_size)]
    
    total_data_points = 0
    
    for i, batch in enumerate(batches):
        print(f"处理第 {i+1}/{len(batches)} 批数据...")
        
        # 生成批量数据
        mock_result = mock_generator.generate_full_market(symbols=batch)
        
        if mock_result.get('code') == 0:
            batch_data = mock_result['data']
            total_data_points += len(batch_data)
            
            # 将数据传入分析器
            market_analyzer.data_queue.put({
                'type': 'full_market',
                'data': batch_data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    
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
    for market, stats in market_stats.get('markets', {}).items():
        total = stats.get('total', 0)
        if total > 0:
            print(f"\n{market}市场 (共 {total} 只股票):")
            print(f"  上涨: {stats.get('up_count', 0)} 只 ({stats.get('up_count', 0)/total*100:.1f}%)")
            print(f"  下跌: {stats.get('down_count', 0)} 只 ({stats.get('down_count', 0)/total*100:.1f}%)")
    
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
            result = safe_api_call(
                api_client,
                api_client.unsubscribe_quote,
                subscription_id
            )
            
            if result.get('code') == 0:
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
        summary = processor_stats.get('summary', {})
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
    print("✓ 自动降级到模拟数据")
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
    """主函数 - 执行完整的深度行情分析教程演示"""
    try:
        print_section_header("Project Argus - 完整行情数据API使用教程")
        
        print("教程概述:")
        print("本教程将演示如何使用统一的API客户端获取和分析完整行情数据")
        print("支持多种数据源，提供深度行情分析和大数据处理优化")
        print(f"xtdata库状态: {'可用' if XTDATA_AVAILABLE else '不可用'}")
        print(f"API服务地址: {config.api.base_url}")
        
        # 1. 演示全推行情数据订阅
        subscription_id = demonstrate_full_market_subscription()
        
        # 2. 演示获取全推数据快照
        demonstrate_full_tick_snapshot()
        
        # 3. 演示深度行情分析
        demonstrate_market_depth_analysis()
        
        # 4. 演示大数据量处理优化
        demonstrate_large_data_processing()
        
        # 5. 演示订阅管理和清理
        demonstrate_subscription_management(subscription_id)
        
        # 6. 显示性能统计和总结
        show_performance_summary()
        
    except KeyboardInterrupt:
        print("\n\n用户中断教程执行")
        market_analyzer.stop_processing()
    except Exception as e:
        print(f"\n\n教程执行过程中发生错误: {e}")
        market_analyzer.stop_processing()
    finally:
        # 清理资源
        if api_client:
            api_client.close()
        print("\n教程执行完毕，资源已清理")

# 执行主函数
if __name__ == "__main__":
    main()