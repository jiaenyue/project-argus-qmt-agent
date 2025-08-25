"""
增强的历史数据API端点
集成新的EnhancedHistoricalDataAPI功能，提供多周期支持和数据质量验证
"""

import asyncio
from typing import Optional, List, Dict, Any
import json
import sys
import os
import traceback
import time
import re
import logging
from datetime import datetime, timedelta
from contextvars import ContextVar

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 配置日志
logger = logging.getLogger(__name__)

# 请求追踪ID上下文变量
request_id_context: ContextVar[str] = ContextVar('request_id', default='unknown')

def get_request_id() -> str:
    """获取当前请求的追踪ID"""
    return request_id_context.get('unknown')

def set_request_id(request_id: str):
    """设置当前请求的追踪ID"""
    request_id_context.set(request_id)

# 导入增强的历史数据API
from src.argus_mcp.api.enhanced_historical_api import (
    EnhancedHistoricalDataAPI, 
    HistoricalDataRequest,
    MultiPeriodRequest
)
from src.argus_mcp.data_models.historical_data import SupportedPeriod
from src.argus_mcp.exceptions.historical_data_exceptions import (
    HistoricalDataException,
    ErrorCategory,
    DataSourceError,
    DataValidationError
)

class EnhancedXTQuantHandler:
    """增强的XTQuant处理器，集成新的历史数据API功能"""
    
    def __init__(self):
        """初始化增强处理器"""
        self.api = EnhancedHistoricalDataAPI()
        
    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串为datetime对象"""
        try:
            return datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                raise ValueError(f"无效的日期格式: {date_str}，支持YYYYMMDD或YYYY-MM-DD")
    
    def _map_frequency(self, frequency: str) -> SupportedPeriod:
        """映射频率字符串到SupportedPeriod枚举"""
        frequency_map = {
            '1m': SupportedPeriod.MINUTE_1,
            '5m': SupportedPeriod.MINUTE_5,
            '15m': SupportedPeriod.MINUTE_15,
            '30m': SupportedPeriod.MINUTE_30,
            '1h': SupportedPeriod.HOUR_1,
            '2h': SupportedPeriod.HOUR_2,
            '4h': SupportedPeriod.HOUR_4,
            '1d': SupportedPeriod.DAY_1,
            '1w': SupportedPeriod.WEEK_1,
            '1M': SupportedPeriod.MONTH_1
        }
        
        if frequency not in frequency_map:
            raise ValueError(f"不支持的频率: {frequency}，支持: {list(frequency_map.keys())}")
        
        return frequency_map[frequency]
    
    def _validate_symbol(self, symbol: str) -> bool:
        """验证股票代码格式"""
        if not symbol or not isinstance(symbol, str):
            return False
        
        # 支持格式：600519.SH, 000001.SZ, AAPL.US 等
        pattern = r'^[A-Z0-9]{4,8}\.[A-Z]{2,3}$'
        return bool(re.match(pattern, symbol.upper()))
    
    async def get_enhanced_hist_kline(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        frequency: str = "1d",
        include_quality: bool = False,
        validate_data: bool = True
    ) -> Dict[str, Any]:
        """
        获取增强的历史K线数据
        
        Args:
            symbol: 股票代码，格式：600519.SH
            start_date: 开始日期，格式：YYYYMMDD或YYYY-MM-DD
            end_date: 结束日期，格式：YYYYMMDD或YYYY-MM-DD
            frequency: K线周期，支持：1m,5m,15m,30m,1h,1d,1w,1M
            include_quality: 是否包含数据质量信息
            validate_data: 是否验证数据质量
            
        Returns:
            Dict: 包含K线数据的响应
        """
        start_time = time.time()
        request_id = get_request_id()
        
        try:
            # 参数验证
            if not symbol:
                return {
                    "success": False, 
                    "message": "symbol参数不能为空", 
                    "status": 400,
                    "request_id": request_id
                }
            
            if not self._validate_symbol(symbol):
                return {
                    "success": False, 
                    "message": f"无效的股票代码格式: {symbol}，正确格式如：600519.SH", 
                    "status": 400,
                    "request_id": request_id
                }
            
            if not start_date or not end_date:
                return {
                    "success": False, 
                    "message": "start_date和end_date参数不能为空", 
                    "status": 400,
                    "request_id": request_id
                }
            
            # 解析日期
            try:
                start_dt = self._parse_date(start_date)
                end_dt = self._parse_date(end_date)
            except ValueError as e:
                return {
                    "success": False, 
                    "message": str(e), 
                    "status": 400,
                    "request_id": request_id
                }
            
            if start_dt > end_dt:
                return {
                    "success": False, 
                    "message": "开始日期不能晚于结束日期", 
                    "status": 400,
                    "request_id": request_id
                }
            
            # 映射频率
            try:
                period = self._map_frequency(frequency)
            except ValueError as e:
                return {
                    "success": False, 
                    "message": str(e), 
                    "status": 400,
                    "request_id": request_id
                }
            
            # 创建请求对象
            request = HistoricalDataRequest(
                symbol=symbol,
                start_date=start_dt.strftime('%Y-%m-%d'),
                end_date=end_dt.strftime('%Y-%m-%d'),
                period=period,
                include_quality_metrics=include_quality,
                normalize_data=validate_data,
                use_cache=True
            )
            
            # 获取增强的历史数据
            response = await self.api.get_historical_data(request)
            
            # 转换数据格式
            kline_data = []
            if response.data:
                for item in response.data:
                    kline_data.append({
                        "time": item.get("timestamp", ""),
                        "open": item.get("open", 0),
                        "high": item.get("high", 0),
                        "low": item.get("low", 0),
                        "close": item.get("close", 0),
                        "volume": item.get("volume", 0),
                        "amount": item.get("amount", 0)
                    })
            
            # 构建响应
            result = {
                "success": True,
                "data": kline_data,
                "count": len(kline_data),
                "metadata": {
                    "symbol": symbol,
                    "period": frequency,
                    "start_date": start_dt.strftime('%Y-%m-%d'),
                    "end_date": end_dt.strftime('%Y-%m-%d'),
                    "request_id": request_id,
                    "response_time": time.time() - start_time
                }
            }
            
            # 添加数据质量信息
            if include_quality and response.quality_report:
                result["quality_metrics"] = response.quality_report
            
            # 添加性能统计
            if response.metadata:
                result["performance_metrics"] = {
                    "cached": response.metadata.get("cached", False),
                    "normalized": response.metadata.get("normalized", False),
                    "quality_checked": response.metadata.get("quality_checked", False),
                    "source": response.metadata.get("source", "unknown")
                }
            
            logger.info(
                f"成功获取增强历史K线数据",
                extra={
                    "request_id": request_id,
                    "symbol": symbol,
                    "period": frequency,
                    "start_date": start_dt.strftime('%Y-%m-%d'),
                    "end_date": end_dt.strftime('%Y-%m-%d'),
                    "count": len(kline_data),
                    "response_time": time.time() - start_time
                }
            )
            
            return result
            
        except HistoricalDataException as e:
            logger.error(
                f"获取历史数据失败: {str(e)}",
                extra={
                    "request_id": request_id,
                    "symbol": symbol,
                    "error_type": e.category.value,
                    "error_code": getattr(e, 'error_code', 'unknown')
                }
            )
            return {
                "success": False,
                "message": str(e),
                "status": 500,
                "error_category": e.category.value,
                "request_id": request_id
            }
            
        except Exception as e:
            logger.error(
                f"获取历史数据时发生未预期错误: {str(e)}",
                extra={
                    "request_id": request_id,
                    "symbol": symbol,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            return {
                "success": False,
                "message": f"获取历史数据失败: {str(e)}",
                "status": 500,
                "request_id": request_id
            }
    
    async def get_backward_compatible_hist_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        frequency: str = "1d"
    ) -> Dict[str, Any]:
        """
        向后兼容的历史K线数据接口
        保持与原有API相同的响应格式
        
        Args:
            symbol: 股票代码
            start_date: 开始日期，格式：YYYYMMDD
            end_date: 结束日期，格式：YYYYMMDD
            frequency: K线周期
            
        Returns:
            Dict: 向后兼容的响应格式
        """
        try:
            # 使用增强API获取数据
            enhanced_result = await self.get_enhanced_hist_kline(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                include_quality=False,
                validate_data=True
            )
            
            if not enhanced_result["success"]:
                return enhanced_result
            
            # 转换为向后兼容的格式
            data = enhanced_result["data"]
            compatible_data = []
            
            for item in data:
                compatible_data.append({
                    "time": item["time"],
                    "open": item["open"],
                    "high": item["high"],
                    "low": item["low"],
                    "close": item["close"],
                    "volume": item["volume"]
                })
            
            return {
                "success": True,
                "data": compatible_data,
                "status": 200
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to fetch historical kline data: {str(e)}",
                "status": 500
            }

    async def get_multi_period_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        periods: List[str] = None,
        include_quality: bool = False,
        validate_data: bool = True
    ) -> Dict[str, Any]:
        """
        获取多个周期的历史数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            periods: 周期列表，如["1d", "1w", "1M"]
            include_quality: 是否包含数据质量信息
            validate_data: 是否验证数据质量
            
        Returns:
            Dict: 多周期数据响应
        """
        start_time = time.time()
        request_id = get_request_id()
        
        try:
            # 参数验证
            if not periods:
                periods = ["1d", "1w", "1M"]
            
            # 验证股票代码
            if not self._validate_symbol(symbol):
                return {
                    "success": False,
                    "message": f"无效的股票代码格式: {symbol}",
                    "status": 400,
                    "request_id": request_id
                }
            
            # 解析日期
            try:
                start_dt = self._parse_date(start_date)
                end_dt = self._parse_date(end_date)
            except ValueError as e:
                return {
                    "success": False,
                    "message": str(e),
                    "status": 400,
                    "request_id": request_id
                }
            
            # 映射周期
            mapped_periods = []
            for period in periods:
                try:
                    mapped_periods.append(self._map_frequency(period))
                except ValueError as e:
                    return {
                        "success": False,
                        "message": str(e),
                        "status": 400,
                        "request_id": request_id
                    }
            
            # 创建多周期请求对象
            multi_request = MultiPeriodRequest(
                symbol=symbol,
                start_date=start_dt.strftime('%Y-%m-%d'),
                end_date=end_dt.strftime('%Y-%m-%d'),
                periods=mapped_periods,
                include_quality_metrics=include_quality
            )
            
            # 获取多周期数据
            response = await self.api.get_multi_period_data(multi_request)
            
            # 构建响应
            result = {
                "success": True,
                "data": {},
                "metadata": {
                    "symbol": symbol,
                    "periods": periods,
                    "start_date": start_dt.strftime('%Y-%m-%d'),
                    "end_date": end_dt.strftime('%Y-%m-%d'),
                    "request_id": request_id,
                    "response_time": time.time() - start_time
                }
            }
            
            # 处理各周期数据
            for period_str, period_data in response.data.items():
                kline_data = []
                if period_data:
                    for item in period_data:
                        kline_data.append({
                            "time": item.get("timestamp", ""),
                            "open": item.get("open", 0),
                            "high": item.get("high", 0),
                            "low": item.get("low", 0),
                            "close": item.get("close", 0),
                            "volume": item.get("volume", 0),
                            "amount": item.get("amount", 0)
                        })
                
                result["data"][period_str] = {
                    "data": kline_data,
                    "count": len(kline_data)
                }
                
                # 添加质量信息
                if include_quality and response.quality_reports.get(period_str):
                    quality_report = response.quality_reports[period_str]
                    if quality_report:
                        result["data"][period_str]["quality_metrics"] = quality_report
            
            return result
            
        except Exception as e:
            logger.error(
                f"获取多周期数据失败: {str(e)}",
                extra={
                    "request_id": request_id,
                    "symbol": symbol,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            return {
                "success": False,
                "message": f"获取多周期数据失败: {str(e)}",
                "status": 500,
                "request_id": request_id
            }

    def validate_data_quality(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        验证数据质量
        
        Args:
            data: K线数据列表
            
        Returns:
            Dict: 数据质量验证结果
        """
        if not data:
            return {
                "is_valid": False,
                "issues": ["数据为空"],
                "quality_score": 0.0
            }
        
        issues = []
        quality_score = 1.0
        
        # 检查时间序列连续性
        timestamps = [item["time"] for item in data]
        if len(timestamps) != len(set(timestamps)):
            issues.append("存在重复时间戳")
            quality_score *= 0.8
        
        # 检查价格数据合理性
        for item in data:
            prices = [item["open"], item["high"], item["low"], item["close"]]
            
            # 检查价格是否为正数
            if any(p <= 0 for p in prices):
                issues.append("存在非正价格")
                quality_score *= 0.9
                break
            
            # 检查高低价关系
            if item["high"] < max(prices) or item["low"] > min(prices):
                issues.append("高低价关系异常")
                quality_score *= 0.95
                break
            
            # 检查成交量
            if item["volume"] < 0:
                issues.append("成交量为负数")
                quality_score *= 0.9
                break
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "quality_score": quality_score,
            "data_points": len(data)
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 缓存统计信息
        """
        try:
            # 获取API的缓存统计（如果API有此方法）
            if hasattr(self.api, 'get_cache_stats'):
                cache_stats = self.api.get_cache_stats()
                
                return {
                    "cache_enabled": True,
                    "cache_size": cache_stats.get("cache_size", 0),
                    "cache_hits": cache_stats.get("cache_hits", 0),
                    "cache_misses": cache_stats.get("cache_misses", 0),
                    "hit_ratio": cache_stats.get("hit_ratio", 0.0),
                    "last_updated": datetime.now().isoformat()
                }
            else:
                return {
                    "cache_enabled": True,
                    "message": "缓存统计功能暂不可用",
                    "last_updated": datetime.now().isoformat()
                }
        except Exception as e:
            logger.warning(f"获取缓存统计失败: {str(e)}")
            return {
                "cache_enabled": False,
                "error": str(e)
            }
    
    async def clear_cache(self) -> Dict[str, Any]:
        """
        清除缓存
        
        Returns:
            Dict: 清除结果
        """
        try:
            # 检查API是否有清除缓存方法
            if hasattr(self.api, 'clear_cache'):
                await self.api.clear_cache()
                return {
                    "success": True,
                    "message": "缓存已清除",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "message": "清除缓存功能暂不可用"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"清除缓存失败: {str(e)}"
            }
    
    async def get_data_sources(self) -> Dict[str, Any]:
        """
        获取可用数据源信息
        
        Returns:
            Dict: 数据源信息
        """
        try:
            # 检查API是否有获取数据源方法
            if hasattr(self.api, 'get_data_sources'):
                sources = await self.api.get_data_sources()
                
                return {
                    "success": True,
                    "data_sources": [
                        {
                            "name": getattr(source, 'name', 'unknown'),
                            "type": getattr(source, 'type', 'unknown'),
                            "description": getattr(source, 'description', ''),
                            "is_available": getattr(source, 'is_available', False),
                            "last_updated": getattr(source, 'last_updated', None)
                        }
                        for source in sources
                    ]
                }
            else:
                return {
                    "success": True,
                    "data_sources": [
                        {
                            "name": "xtquant",
                            "type": "market_data",
                            "description": "XTQuant数据源",
                            "is_available": True,
                            "last_updated": datetime.now().isoformat()
                        }
                    ]
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"获取数据源信息失败: {str(e)}"
            }
    
    async def batch_get_hist_kline(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        frequency: str = "1d",
        include_quality: bool = False,
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        批量获取历史K线数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: K线周期
            include_quality: 是否包含数据质量信息
            max_concurrent: 最大并发数
            
        Returns:
            Dict: 批量数据响应
        """
        start_time = time.time()
        request_id = get_request_id()
        
        if not symbols:
            return {
                "success": False,
                "message": "symbols参数不能为空",
                "status": 400,
                "request_id": request_id
            }
        
        # 验证所有股票代码
        invalid_symbols = [s for s in symbols if not self._validate_symbol(s)]
        if invalid_symbols:
            return {
                "success": False,
                "message": f"无效的股票代码: {invalid_symbols}",
                "status": 400,
                "request_id": request_id
            }
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_single_symbol(symbol):
            async with semaphore:
                return await self.get_enhanced_hist_kline(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=frequency,
                    include_quality=include_quality
                )
        
        # 并发获取所有数据
        tasks = [fetch_single_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        successful_data = {}
        failed_symbols = {}
        
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                failed_symbols[symbol] = str(result)
            elif result.get("success"):
                successful_data[symbol] = result
            else:
                failed_symbols[symbol] = result.get("message", "未知错误")
        
        return {
            "success": True,
            "data": successful_data,
            "failed": failed_symbols,
            "summary": {
                "total": len(symbols),
                "successful": len(successful_data),
                "failed": len(failed_symbols),
                "success_rate": len(successful_data) / len(symbols) if symbols else 0
            },
            "metadata": {
                "request_id": request_id,
                "response_time": time.time() - start_time,
                "max_concurrent": max_concurrent
            }
        }
    
    async def monitor_data_quality(
        self,
        symbols: List[str],
        frequency: str = "1d",
        check_interval: int = 300
    ) -> Dict[str, Any]:
        """
        监控数据质量
        
        Args:
            symbols: 监控的股票代码列表
            frequency: 监控频率
            check_interval: 检查间隔（秒）
            
        Returns:
            Dict: 监控结果
        """
        request_id = get_request_id()
        
        # 获取最新数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        try:
            batch_result = await self.batch_get_hist_kline(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                include_quality=True,
                max_concurrent=3
            )
            
            if not batch_result["success"]:
                return batch_result
            
            # 分析质量数据
            quality_summary = {}
            for symbol, data in batch_result["data"].items():
                if "quality_metrics" in data:
                    quality_summary[symbol] = {
                        "overall_score": data["quality_metrics"].get("overall_score", 0.0),
                        "completeness_score": data["quality_metrics"].get("completeness_score", 0.0),
                        "accuracy_score": data["quality_metrics"].get("accuracy_score", 0.0),
                        "consistency_score": data["quality_metrics"].get("consistency_score", 0.0),
                        "last_check": datetime.now().isoformat()
                    }
            
            return {
                "success": True,
                "quality_summary": quality_summary,
                "check_interval": check_interval,
                "next_check": (datetime.now() + timedelta(seconds=check_interval)).isoformat(),
                "request_id": request_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"监控数据质量失败: {str(e)}",
                "request_id": request_id
            }