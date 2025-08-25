"""
增强历史K线API使用教程 - Project Argus QMT 数据代理服务

本教程演示如何使用增强的历史K线API获取股票的历史价格数据，
包括多周期支持、数据质量监控、缓存优化和标准化数据格式。

学习目标:
1. 掌握增强API的使用方法
2. 理解多周期数据获取和转换
3. 学会数据质量验证和监控
4. 了解缓存机制和性能优化
5. 掌握标准化数据格式的使用

增强功能特性:
- 多周期支持: 1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M
- 数据质量监控: 完整性、准确性、一致性检查
- 智能缓存: 根据周期设置不同TTL
- 标准化格式: 统一的JSON格式和数据类型
- 错误处理: 完善的异常处理和重试机制
"""

import asyncio
import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedHistoricalDataDemo:
    """增强历史数据API演示类"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def print_section_header(self, title: str):
        """打印章节标题"""
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
    
    def print_subsection_header(self, title: str):
        """打印子章节标题"""
        print(f"\n{'-'*40}")
        print(f" {title}")
        print(f"{'-'*40}")
    
    def get_enhanced_kline_data(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        frequency: str = "1d",
        include_quality: bool = True,
        normalize: bool = True
    ) -> Dict[str, Any]:
        """
        获取增强的历史K线数据
        
        Args:
            symbol: 股票代码，如 "600519.SH"
            start_date: 开始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
            frequency: 数据周期，支持 1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M
            include_quality: 是否包含质量指标
            normalize: 是否标准化数据
            
        Returns:
            Dict: API响应数据
        """
        params = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
            "enhanced": True,
            "include_quality": include_quality,
            "normalize": normalize
        }
        
        try:
            response = self.session.get(f"{self.base_url}/hist_kline", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def get_multi_period_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        periods: List[str],
        include_quality: bool = True
    ) -> Dict[str, Any]:
        """
        获取多周期历史数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            periods: 周期列表
            include_quality: 是否包含质量指标
            
        Returns:
            Dict: 多周期数据响应
        """
        params = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "periods": ",".join(periods),
            "include_quality": include_quality
        }
        
        try:
            response = self.session.get(f"{self.base_url}/multi_period_data", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"多周期API请求失败: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def demo_basic_enhanced_api(self):
        """演示基础增强API功能"""
        self.print_section_header("基础增强API演示")
        
        # 获取贵州茅台日线数据
        symbol = "600519.SH"
        start_date = "20240101"
        end_date = "20240131"
        
        print(f"股票代码: {symbol}")
        print(f"时间范围: {start_date} - {end_date}")
        print(f"数据周期: 日线(1d)")
        
        result = self.get_enhanced_kline_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            frequency="1d",
            include_quality=True,
            normalize=True
        )
        
        if result.get("success"):
            data = result.get("data", [])
            quality_report = result.get("quality_report", {})
            metadata = result.get("metadata", {})
            
            print(f"\n✅ 成功获取数据:")
            print(f"  数据条数: {len(data)}")
            print(f"  缓存命中: {metadata.get('cache_hit', False)}")
            print(f"  响应时间: {metadata.get('response_time_ms', 0)}ms")
            
            if quality_report:
                print(f"\n📊 数据质量报告:")
                print(f"  完整性: {quality_report.get('completeness_rate', 0):.2%}")
                print(f"  准确性: {quality_report.get('accuracy_score', 0):.2f}")
                print(f"  一致性: {quality_report.get('consistency_score', 0):.2f}")
                print(f"  异常数据: {quality_report.get('anomaly_count', 0)}条")
            
            if data:
                print(f"\n📈 数据样例 (前3条):")
                for i, record in enumerate(data[:3]):
                    print(f"  {i+1}. {record}")
        else:
            print(f"❌ 获取数据失败: {result.get('message')}")
    
    def demo_multi_period_api(self):
        """演示多周期API功能"""
        self.print_section_header("多周期API演示")
        
        symbol = "600519.SH"
        start_date = "20240101"
        end_date = "20240131"
        periods = ["1d", "1w"]
        
        print(f"股票代码: {symbol}")
        print(f"时间范围: {start_date} - {end_date}")
        print(f"数据周期: {', '.join(periods)}")
        
        result = self.get_multi_period_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            periods=periods,
            include_quality=True
        )
        
        if result.get("success"):
            data = result.get("data", {})
            quality_reports = result.get("quality_reports", {})
            metadata = result.get("metadata", {})
            
            print(f"\n✅ 成功获取多周期数据:")
            
            for period, period_data in data.items():
                print(f"\n📊 {period}周期数据:")
                print(f"  数据条数: {len(period_data)}")
                
                if period in quality_reports:
                    quality = quality_reports[period]
                    print(f"  完整性: {quality.get('completeness_rate', 0):.2%}")
                    print(f"  准确性: {quality.get('accuracy_score', 0):.2f}")
                
                if period_data:
                    print(f"  首条数据: {period_data[0]}")
                    print(f"  末条数据: {period_data[-1]}")
        else:
            print(f"❌ 获取多周期数据失败: {result.get('message')}")
    
    def demo_data_quality_monitoring(self):
        """演示数据质量监控功能"""
        self.print_section_header("数据质量监控演示")
        
        symbol = "600519.SH"
        start_date = "20240101"
        end_date = "20240105"
        
        # 获取不同周期的数据进行质量对比
        frequencies = ["1d", "1h", "15m"]
        
        for freq in frequencies:
            self.print_subsection_header(f"{freq}周期数据质量")
            
            result = self.get_enhanced_kline_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                frequency=freq,
                include_quality=True
            )
            
            if result.get("success"):
                quality_report = result.get("quality_report", {})
                data = result.get("data", [])
                
                print(f"数据条数: {len(data)}")
                print(f"完整性评分: {quality_report.get('completeness_rate', 0):.2%}")
                print(f"准确性评分: {quality_report.get('accuracy_score', 0):.2f}")
                print(f"及时性评分: {quality_report.get('timeliness_score', 0):.2f}")
                print(f"一致性评分: {quality_report.get('consistency_score', 0):.2f}")
                print(f"异常数据数量: {quality_report.get('anomaly_count', 0)}")
                
                # 显示数据质量等级
                avg_score = (
                    quality_report.get('completeness_rate', 0) +
                    quality_report.get('accuracy_score', 0) +
                    quality_report.get('consistency_score', 0)
                ) / 3
                
                if avg_score >= 0.9:
                    quality_level = "优秀 ⭐⭐⭐"
                elif avg_score >= 0.8:
                    quality_level = "良好 ⭐⭐"
                elif avg_score >= 0.7:
                    quality_level = "一般 ⭐"
                else:
                    quality_level = "较差 ❌"
                
                print(f"数据质量等级: {quality_level}")
            else:
                print(f"❌ 获取{freq}数据失败: {result.get('message')}")
    
    def demo_caching_performance(self):
        """演示缓存性能优化"""
        self.print_section_header("缓存性能演示")
        
        symbol = "600519.SH"
        start_date = "20240101"
        end_date = "20240105"
        frequency = "1d"
        
        print("第一次请求 (冷缓存):")
        start_time = datetime.now()
        result1 = self.get_enhanced_kline_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency
        )
        first_request_time = (datetime.now() - start_time).total_seconds() * 1000
        
        if result1.get("success"):
            metadata1 = result1.get("metadata", {})
            print(f"  响应时间: {first_request_time:.0f}ms")
            print(f"  缓存命中: {metadata1.get('cache_hit', False)}")
            print(f"  数据条数: {len(result1.get('data', []))}")
        
        print("\n第二次请求 (热缓存):")
        start_time = datetime.now()
        result2 = self.get_enhanced_kline_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency
        )
        second_request_time = (datetime.now() - start_time).total_seconds() * 1000
        
        if result2.get("success"):
            metadata2 = result2.get("metadata", {})
            print(f"  响应时间: {second_request_time:.0f}ms")
            print(f"  缓存命中: {metadata2.get('cache_hit', False)}")
            print(f"  数据条数: {len(result2.get('data', []))}")
            
            # 计算性能提升
            if first_request_time > 0:
                improvement = (first_request_time - second_request_time) / first_request_time * 100
                print(f"\n🚀 缓存性能提升: {improvement:.1f}%")
    
    def demo_error_handling(self):
        """演示错误处理机制"""
        self.print_section_header("错误处理演示")
        
        # 测试无效股票代码
        self.print_subsection_header("无效股票代码测试")
        result = self.get_enhanced_kline_data(
            symbol="INVALID.XX",
            start_date="20240101",
            end_date="20240105"
        )
        print(f"结果: {result.get('success')}")
        print(f"错误信息: {result.get('message')}")
        
        # 测试无效日期格式
        self.print_subsection_header("无效日期格式测试")
        result = self.get_enhanced_kline_data(
            symbol="600519.SH",
            start_date="2024-01-01",  # 错误格式
            end_date="20240105"
        )
        print(f"结果: {result.get('success')}")
        print(f"错误信息: {result.get('message')}")
        
        # 测试无效周期
        self.print_subsection_header("无效周期测试")
        result = self.get_enhanced_kline_data(
            symbol="600519.SH",
            start_date="20240101",
            end_date="20240105",
            frequency="invalid"
        )
        print(f"结果: {result.get('success')}")
        print(f"错误信息: {result.get('message')}")
    
    def demo_data_analysis(self):
        """演示数据分析功能"""
        self.print_section_header("数据分析演示")
        
        symbol = "600519.SH"
        start_date = "20240101"
        end_date = "20240131"
        
        result = self.get_enhanced_kline_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            frequency="1d"
        )
        
        if result.get("success"):
            data = result.get("data", [])
            
            if data:
                # 转换为DataFrame进行分析
                df = pd.DataFrame(data)
                
                # 确保数值列是正确的数据类型
                numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                print(f"📊 {symbol} 数据分析结果:")
                print(f"  数据期间: {start_date} - {end_date}")
                print(f"  交易天数: {len(df)}")
                
                if 'close' in df.columns:
                    close_prices = df['close'].dropna()
                    if len(close_prices) > 0:
                        print(f"  期间最高价: {close_prices.max():.2f}")
                        print(f"  期间最低价: {close_prices.min():.2f}")
                        print(f"  期间平均价: {close_prices.mean():.2f}")
                        print(f"  期间涨跌幅: {((close_prices.iloc[-1] / close_prices.iloc[0]) - 1) * 100:.2f}%")
                
                if 'volume' in df.columns:
                    volumes = df['volume'].dropna()
                    if len(volumes) > 0:
                        print(f"  平均成交量: {volumes.mean():.0f}")
                        print(f"  最大成交量: {volumes.max():.0f}")
        else:
            print(f"❌ 数据分析失败: {result.get('message')}")
    
    def run_all_demos(self):
        """运行所有演示"""
        print("🚀 增强历史K线API演示开始")
        print(f"服务器地址: {self.base_url}")
        print("注意: 请确保API服务器正在运行")
        
        try:
            self.demo_basic_enhanced_api()
            self.demo_multi_period_api()
            self.demo_data_quality_monitoring()
            self.demo_caching_performance()
            self.demo_error_handling()
            self.demo_data_analysis()
            
            print(f"\n{'='*60}")
            print(" 🎉 所有演示完成!")
            print(f"{'='*60}")
            
        except Exception as e:
            logger.error(f"演示过程中发生错误: {str(e)}")
            print(f"❌ 演示失败: {str(e)}")


def main():
    """主函数"""
    demo = EnhancedHistoricalDataDemo()
    demo.run_all_demos()


if __name__ == "__main__":
    main()