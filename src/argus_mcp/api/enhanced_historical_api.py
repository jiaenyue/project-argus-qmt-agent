"""
增强的历史数据API

集成多周期数据、缓存管理、数据质量监控和标准化功能的增强API
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from decimal import Decimal
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
import pandas as pd

from ..data_models.historical_data import (
    StandardKLineData, DataQualityMetrics, ValidationResult, SupportedPeriod
)
from ..processors.data_normalizer import DataNormalizer
from ..processors.multi_period_processor import MultiPeriodProcessor
from ..monitoring.data_quality_monitor import DataQualityMonitor, QualityReport
from ..cache.historical_data_cache import HistoricalDataCache, get_historical_cache


# Pydantic模型定义
class HistoricalDataRequest(BaseModel):
    """历史数据请求模型"""
    symbol: str = Field(..., description="股票代码，格式如: 600519.SH")
    start_date: str = Field(..., description="开始日期，格式: YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期，格式: YYYY-MM-DD")
    period: SupportedPeriod = Field(SupportedPeriod.DAILY, description="数据周期")
    include_quality_metrics: bool = Field(True, description="是否包含质量指标")
    normalize_data: bool = Field(True, description="是否标准化数据格式")
    use_cache: bool = Field(True, description="是否使用缓存")
    max_records: Optional[int] = Field(None, description="最大返回记录数")


class HistoricalDataResponse(BaseModel):
    """历史数据响应模型"""
    success: bool
    symbol: str
    period: str
    start_date: str
    end_date: str
    total_records: int
    data: List[Dict[str, Any]]
    quality_report: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]


class MultiPeriodRequest(BaseModel):
    """多周期数据请求模型"""
    symbol: str = Field(..., description="股票代码")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    periods: List[SupportedPeriod] = Field(..., description="周期列表")
    include_quality_metrics: bool = Field(True, description="是否包含质量指标")


class MultiPeriodResponse(BaseModel):
    """多周期数据响应模型"""
    success: bool
    symbol: str
    start_date: str
    end_date: str
    data: Dict[str, List[Dict[str, Any]]]  # 周期到数据的映射
    quality_reports: Dict[str, Optional[Dict[str, Any]]]
    metadata: Dict[str, Any]


class QualityCheckRequest(BaseModel):
    """质量检查请求模型"""
    symbol: str = Field(..., description="股票代码")
    period: SupportedPeriod = Field(..., description="数据周期")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")


class QualityCheckResponse(BaseModel):
    """质量检查响应模型"""
    success: bool
    symbol: str
    period: str
    quality_score: float
    issues: List[Dict[str, Any]]
    metrics: Dict[str, float]
    total_records: int


class EnhancedHistoricalDataAPI:
    """
    增强的历史数据API
    
    提供以下功能：
    - 多周期历史数据查询
    - 数据质量监控和报告
    - 缓存管理和优化
    - 数据格式标准化
    - 批量数据获取
    - 实时质量检查
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 初始化各个处理器
        self.data_normalizer = DataNormalizer()
        self.period_processor = MultiPeriodProcessor()
        self.quality_monitor = DataQualityMonitor()
        self.cache = get_historical_cache()
        
        # 后台任务队列
        self.background_tasks = set()
    
    async def get_historical_data(
        self, 
        request: HistoricalDataRequest,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> HistoricalDataResponse:
        """
        获取增强的历史数据
        
        Args:
            request: 历史数据请求
            background_tasks: 后台任务（可选）
            
        Returns:
            HistoricalDataResponse: 增强的历史数据响应
        """
        try:
            # 参数验证
            self._validate_request(request)
            
            # 检查缓存
            cache_key = self._generate_cache_key(request)
            if request.use_cache:
                cached_data = await self._get_from_cache(cache_key)
                if cached_data:
                    return cached_data
            
            # 获取基础数据（这里应该从实际数据源获取）
            raw_data = await self._fetch_raw_data(
                request.symbol, 
                request.start_date, 
                request.end_date, 
                request.period
            )
            
            if not raw_data:
                return HistoricalDataResponse(
                    success=False,
                    symbol=request.symbol,
                    period=request.period.value,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    total_records=0,
                    data=[],
                    metadata={"error": "No data available"}
                )
            
            # 数据标准化和模型转换
            if request.normalize_data:
                normalized_data = self.data_normalizer.normalize_kline_data(
                    raw_data, 
                    symbol=request.symbol,
                    period=request.period.value
                )
            else:
                # 将原始数据转换为StandardKLineData格式
                normalized_data = []
                for item in raw_data:
                    try:
                        # 处理时间戳
                        timestamp = item.get('datetime') or item.get('timestamp')
                        if isinstance(timestamp, str):
                            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        elif not isinstance(timestamp, datetime):
                            timestamp = datetime.now()
                        
                        # 确保时间戳有时区信息
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        
                        kline_data = StandardKLineData(
                            timestamp=timestamp,
                            open=Decimal(str(item.get('open', 0))),
                            high=Decimal(str(item.get('high', 0))),
                            low=Decimal(str(item.get('low', 0))),
                            close=Decimal(str(item.get('close', 0))),
                            volume=int(item.get('volume', 0)),
                            amount=Decimal(str(item.get('amount', 0))),
                            quality_score=1.0,
                            code=item.get('code', request.symbol)
                        )
                        normalized_data.append(kline_data)
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Skipping invalid data item: {e}")
                        continue
            
            # 质量检查
            quality_report = None
            if request.include_quality_metrics:
                quality_report = self.quality_monitor.check_data_quality(
                    normalized_data, 
                    request.symbol, 
                    request.period.value
                )
            
            # 应用记录数限制
            final_data = normalized_data
            if request.max_records and len(normalized_data) > request.max_records:
                final_data = normalized_data[-request.max_records:]
            
            # 转换为字典格式，确保字段名称一致性
            data_dicts = []
            for item in final_data:
                data_dict = {
                    'timestamp': item.timestamp.isoformat() if hasattr(item.timestamp, 'isoformat') else str(item.timestamp),
                    'open': float(item.open),
                    'high': float(item.high),
                    'low': float(item.low),
                    'close': float(item.close),
                    'volume': int(item.volume),
                    'amount': float(item.amount),
                    'quality_score': float(item.quality_score)
                }
                data_dicts.append(data_dict)
            
            # 构建响应
            quality_report_dict = None
            if quality_report:
                try:
                    # Try to convert to dict if it's a dataclass
                    if hasattr(quality_report, '__dataclass_fields__'):
                        quality_report_dict = asdict(quality_report)
                    elif hasattr(quality_report, '__dict__'):
                        # If it's a regular object with attributes
                        quality_report_dict = {
                            'quality_score': getattr(quality_report, 'quality_score', 0.0),
                            'issues': getattr(quality_report, 'issues', []),
                            'metrics': getattr(quality_report, 'metrics', {})
                        }
                    else:
                        # If it's already a dict or other type
                        quality_report_dict = quality_report
                except Exception as e:
                    self.logger.warning(f"Failed to convert quality report: {e}")
                    quality_report_dict = {"error": "Failed to process quality report"}
            
            response = HistoricalDataResponse(
                success=True,
                symbol=request.symbol,
                period=request.period.value,
                start_date=request.start_date,
                end_date=request.end_date,
                total_records=len(final_data),
                data=data_dicts,
                quality_report=quality_report_dict,
                metadata={
                    "source": "enhanced_api",
                    "cached": False,
                    "normalized": request.normalize_data,
                    "quality_checked": request.include_quality_metrics
                }
            )
            
            # 缓存结果
            if request.use_cache:
                await self._cache_result(cache_key, response)
            
            # 后台质量分析（可选）
            if background_tasks and quality_report and quality_report.quality_score < 80:
                background_tasks.add_task(
                    self._log_quality_issue, 
                    request.symbol, 
                    request.period.value, 
                    quality_report
                )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error getting historical data: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_multi_period_data(
        self, 
        request: MultiPeriodRequest,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> MultiPeriodResponse:
        """
        获取多周期历史数据
        
        Args:
            request: 多周期数据请求
            background_tasks: 后台任务（可选）
            
        Returns:
            MultiPeriodResponse: 多周期数据响应
        """
        try:
            self._validate_multi_period_request(request)
            
            results = {}
            quality_reports = {}
            
            # 并行获取不同周期的数据
            tasks = []
            for period in request.periods:
                task = self.get_historical_data(
                    HistoricalDataRequest(
                        symbol=request.symbol,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        period=period,
                        include_quality_metrics=request.include_quality_metrics,
                        normalize_data=True,
                        use_cache=True
                    ),
                    background_tasks
                )
                tasks.append((period, task))
            
            # 等待所有任务完成
            for period, task in tasks:
                response = await task
                if response.success:
                    results[period.value] = response.data
                    if response.quality_report:
                        quality_reports[period.value] = response.quality_report
                    else:
                        quality_reports[period.value] = None
                else:
                    results[period.value] = []
                    quality_reports[period.value] = None
            
            return MultiPeriodResponse(
                success=True,
                symbol=request.symbol,
                start_date=request.start_date,
                end_date=request.end_date,
                data=results,
                quality_reports=quality_reports,
                metadata={
                    "total_periods": len(request.periods),
                    "source": "enhanced_api"
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error getting multi-period data: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def check_data_quality(
        self, 
        request: QualityCheckRequest
    ) -> QualityCheckResponse:
        """
        检查数据质量
        
        Args:
            request: 质量检查请求
            
        Returns:
            QualityCheckResponse: 质量检查结果
        """
        try:
            # 获取数据用于质量检查
            historical_request = HistoricalDataRequest(
                symbol=request.symbol,
                start_date=request.start_date,
                end_date=request.end_date,
                period=request.period,
                include_quality_metrics=True,
                normalize_data=True,
                use_cache=True
            )
            
            response = await self.get_historical_data(historical_request)
            
            if not response.success:
                return QualityCheckResponse(
                    success=False,
                    symbol=request.symbol,
                    period=request.period.value,
                    quality_score=0.0,
                    issues=[],
                    metrics={},
                    total_records=0
                )
            
            # 从响应中提取质量报告
            quality_report = response.quality_report
            if quality_report:
                # Convert quality report safely
                issues_list = []
                if quality_report.get("issues"):
                    for issue in quality_report["issues"]:
                        if hasattr(issue, '__dataclass_fields__'):
                            issues_list.append(asdict(issue))
                        elif hasattr(issue, '__dict__'):
                            issues_list.append(issue.__dict__)
                        else:
                            issues_list.append(issue)
                
                metrics_dict = {}
                if quality_report.get("metrics"):
                    metrics = quality_report["metrics"]
                    if hasattr(metrics, '__dataclass_fields__'):
                        metrics_dict = asdict(metrics)
                    elif hasattr(metrics, '__dict__'):
                        metrics_dict = metrics.__dict__
                    else:
                        metrics_dict = metrics
                
                return QualityCheckResponse(
                    success=True,
                    symbol=request.symbol,
                    period=request.period.value,
                    quality_score=quality_report["quality_score"],
                    issues=issues_list,
                    metrics=metrics_dict,
                    total_records=response.total_records
                )
            else:
                # 如果没有质量报告，进行快速检查
                data_objects = [StandardKLineData(**item) for item in response.data]
                quick_report = self.quality_monitor.check_data_quality(
                    data_objects, request.symbol, request.period.value
                )
                
                # Convert quick report safely
                issues_list = []
                for issue in quick_report.issues:
                    if hasattr(issue, '__dataclass_fields__'):
                        issues_list.append(asdict(issue))
                    elif hasattr(issue, '__dict__'):
                        issues_list.append(issue.__dict__)
                    else:
                        issues_list.append(issue)
                
                metrics_dict = {}
                if hasattr(quick_report.metrics, '__dataclass_fields__'):
                    metrics_dict = asdict(quick_report.metrics)
                elif hasattr(quick_report.metrics, '__dict__'):
                    metrics_dict = quick_report.metrics.__dict__
                else:
                    metrics_dict = quick_report.metrics
                
                return QualityCheckResponse(
                    success=True,
                    symbol=request.symbol,
                    period=request.period.value,
                    quality_score=quick_report.quality_score,
                    issues=issues_list,
                    metrics=metrics_dict,
                    total_records=response.total_records
                )
                
        except Exception as e:
            self.logger.error(f"Error checking data quality: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_batch_data(
        self, 
        symbols: List[str],
        start_date: str,
        end_date: str,
        period: SupportedPeriod,
        max_concurrent: int = 5
    ) -> Dict[str, HistoricalDataResponse]:
        """
        批量获取历史数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期
            max_concurrent: 最大并发数
            
        Returns:
            Dict[str, HistoricalDataResponse]: 股票代码到响应的映射
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_single_symbol(symbol: str) -> tuple:
            async with semaphore:
                request = HistoricalDataRequest(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period,
                    include_quality_metrics=True,
                    normalize_data=True,
                    use_cache=True
                )
                response = await self.get_historical_data(request)
                return symbol, response
        
        # 并发获取所有股票数据
        tasks = [fetch_single_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        responses = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Batch fetch error: {str(result)}")
            else:
                symbol, response = result
                responses[symbol] = response
        
        return responses
    
    def _validate_request(self, request: HistoricalDataRequest) -> None:
        """验证请求参数"""
        if not request.symbol:
            raise ValueError("Symbol is required")
        
        try:
            datetime.strptime(request.start_date, "%Y-%m-%d")
            datetime.strptime(request.end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format, use YYYY-MM-DD")
        
        if request.start_date > request.end_date:
            raise ValueError("Start date must be before end date")
    
    def _validate_multi_period_request(self, request: MultiPeriodRequest) -> None:
        """验证多周期请求参数"""
        if not request.symbol:
            raise ValueError("Symbol is required")
        
        if not request.periods:
            raise ValueError("At least one period is required")
        
        try:
            datetime.strptime(request.start_date, "%Y-%m-%d")
            datetime.strptime(request.end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format, use YYYY-MM-DD")
    
    def _generate_cache_key(self, request: HistoricalDataRequest) -> str:
        """生成缓存键"""
        return f"enhanced_{request.symbol}_{request.period.value}_{request.start_date}_{request.end_date}"
    
    async def _get_from_cache(self, cache_key: str) -> Optional[HistoricalDataResponse]:
        """从缓存获取数据"""
        try:
            cached_data = await self.cache.get_kline_data(cache_key)
            if cached_data:
                # 将缓存数据转换为响应格式
                if isinstance(cached_data, list):
                    # 假设缓存的是数据列表
                    return HistoricalDataResponse(
                        success=True,
                        symbol="",  # 从cache_key中提取
                        period="",  # 从cache_key中提取
                        start_date="",
                        end_date="",
                        total_records=len(cached_data),
                        data=cached_data,
                        metadata={"source": "cache", "cached": True}
                    )
                elif isinstance(cached_data, dict) and 'data' in cached_data:
                    # 假设缓存的是完整响应
                    return HistoricalDataResponse(**cached_data)
        except Exception as e:
            self.logger.warning(f"Cache retrieval error: {str(e)}")
        return None
    
    async def _cache_result(self, cache_key: str, response: HistoricalDataResponse) -> None:
        """缓存结果"""
        try:
            # 缓存响应数据，设置适当的TTL
            cache_data = {
                "success": response.success,
                "symbol": response.symbol,
                "period": response.period,
                "start_date": response.start_date,
                "end_date": response.end_date,
                "total_records": response.total_records,
                "data": response.data,
                "metadata": response.metadata
            }
            
            # 根据周期设置不同的TTL
            ttl_mapping = {
                "1m": 300,    # 5分钟
                "5m": 900,    # 15分钟
                "15m": 1800,  # 30分钟
                "30m": 3600,  # 1小时
                "1h": 7200,   # 2小时
                "1d": 86400,  # 24小时
                "1w": 604800, # 7天
                "1M": 2592000 # 30天
            }
            
            ttl = ttl_mapping.get(response.period, 3600)  # 默认1小时
            await self.cache.cache_kline_data(cache_key, cache_data, ttl=ttl)
            
        except Exception as e:
            self.logger.warning(f"Cache storage error: {str(e)}")
    
    async def _fetch_raw_data(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        period: SupportedPeriod
    ) -> List[Dict[str, Any]]:
        """
        从xtquant数据源获取原始历史数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 数据周期
            
        Returns:
            List[Dict]: 原始K线数据
            
        Raises:
            ImportError: 如果xtquant库不可用
            ValueError: 如果参数无效或数据获取失败
        """
        try:
            # 导入xtquant库
            xtdata = self._import_xtdata()
            
            # 转换日期格式为xtquant需要的格式 (YYYYMMDD)
            start_date_xt = start_date.replace('-', '')
            end_date_xt = end_date.replace('-', '')
            
            # 映射周期到xtquant格式
            period_mapping = {
                SupportedPeriod.MINUTE_1: '1m',
                SupportedPeriod.MINUTE_5: '5m',
                SupportedPeriod.MINUTE_15: '15m',
                SupportedPeriod.MINUTE_30: '30m',
                SupportedPeriod.HOUR_1: '1h',
                SupportedPeriod.HOUR_2: '2h',
                SupportedPeriod.HOUR_4: '4h',
                SupportedPeriod.DAY_1: '1d',
                SupportedPeriod.WEEK_1: '1w',
                SupportedPeriod.MONTH_1: '1M'
            }
            
            xt_period = period_mapping.get(period)
            if not xt_period:
                raise ValueError(f"不支持的周期: {period}")
            
            self.logger.info(f"从xtquant获取数据: {symbol}, {xt_period}, {start_date_xt}-{end_date_xt}")
            
            # 调用xtquant API获取历史数据
            df = xtdata.get_market_data_ex(
                stock_list=[symbol],
                period=xt_period,
                start_time=start_date_xt,
                end_time=end_date_xt,
                fill_data=True,
                dividend_type='none'
            )
            
            if df is None:
                self.logger.warning(f"未获取到数据: {symbol}, {xt_period}, {start_date_xt}-{end_date_xt}")
                return []
            
            # 检查是否为空数据
            if isinstance(df, dict):
                if not df or symbol not in df or df[symbol].empty:
                    self.logger.warning(f"未获取到数据: {symbol}, {xt_period}, {start_date_xt}-{end_date_xt}")
                    return []
            elif hasattr(df, 'empty') and df.empty:
                self.logger.warning(f"未获取到数据: {symbol}, {xt_period}, {start_date_xt}-{end_date_xt}")
                return []
            
            # 处理xtquant返回的数据结构
            stock_df = None
            if isinstance(df, dict) and symbol in df:
                # 字典格式：{symbol: DataFrame}
                stock_df = df[symbol]
            elif hasattr(df, 'columns') and hasattr(df.columns, 'levels'):
                # MultiIndex columns case
                if symbol in df.columns.levels[0]:
                    stock_df = df[symbol]
            elif hasattr(df, 'columns') and not hasattr(df.columns, 'levels'):
                # 单股票DataFrame，直接使用
                stock_df = df
            else:
                self.logger.warning(f"返回数据中未找到股票 {symbol}")
                return []
            
            if stock_df is None or stock_df.empty:
                self.logger.warning(f"股票 {symbol} 的数据为空")
                return []
            
            # 转换为字典列表格式
            data = []
            for timestamp, row in stock_df.iterrows():
                try:
                    # 确保时间戳格式正确
                    if hasattr(timestamp, 'to_pydatetime'):
                        dt = timestamp.to_pydatetime()
                    elif isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    else:
                        dt = timestamp
                    
                    # 确保时间戳有时区信息
                    if hasattr(dt, 'tzinfo') and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    
                    # 安全获取数据，处理不同的列名格式
                    open_val = row.get('open') or row.get('Open') or 0
                    high_val = row.get('high') or row.get('High') or 0
                    low_val = row.get('low') or row.get('Low') or 0
                    close_val = row.get('close') or row.get('Close') or 0
                    volume_val = row.get('volume') or row.get('Volume') or 0
                    amount_val = row.get('amount') or row.get('Amount') or 0
                    
                    data_item = {
                        "datetime": dt,
                        "timestamp": dt,
                        "open": float(open_val) if open_val is not None else 0.0,
                        "high": float(high_val) if high_val is not None else 0.0,
                        "low": float(low_val) if low_val is not None else 0.0,
                        "close": float(close_val) if close_val is not None else 0.0,
                        "volume": int(volume_val) if volume_val is not None else 0,
                        "amount": float(amount_val) if amount_val is not None else 0.0,
                        "code": symbol
                    }
                    
                    # 基本数据验证
                    if data_item["open"] <= 0 and data_item["close"] <= 0:
                        self.logger.warning(f"跳过无效价格数据: {timestamp}")
                        continue
                        
                    data.append(data_item)
                except Exception as e:
                    self.logger.warning(f"跳过无效数据行 {timestamp}: {str(e)}")
                    continue
            
            self.logger.info(f"成功获取 {len(data)} 条数据记录")
            return data
            
        except ImportError:
            raise
        except Exception as e:
            self.logger.error(f"获取xtquant数据失败: {str(e)}")
            # 如果是连接或数据源问题，尝试使用备用方法
            return await self._fetch_raw_data_fallback(symbol, start_date, end_date, period)
    
    async def _fetch_raw_data_fallback(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: SupportedPeriod
    ) -> List[Dict[str, Any]]:
        """
        备用数据获取方法，使用简化的xtquant API
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期
            
        Returns:
            List[Dict]: 原始K线数据
        """
        try:
            xtdata = self._import_xtdata()
            
            # 转换日期格式
            start_date_xt = start_date.replace('-', '')
            end_date_xt = end_date.replace('-', '')
            
            # 使用简化的API
            period_mapping = {
                SupportedPeriod.MINUTE_1: '1m',
                SupportedPeriod.MINUTE_5: '5m', 
                SupportedPeriod.MINUTE_15: '15m',
                SupportedPeriod.MINUTE_30: '30m',
                SupportedPeriod.HOUR_1: '1h',
                SupportedPeriod.DAY_1: '1d',
                SupportedPeriod.WEEK_1: '1w',
                SupportedPeriod.MONTH_1: '1M'
            }
            
            xt_period = period_mapping.get(period, '1d')
            
            self.logger.info(f"使用备用方法获取数据: {symbol}, {xt_period}")
            
            # 尝试使用get_market_data方法
            df = xtdata.get_market_data(
                stock_code=symbol,
                period=xt_period,
                start_time=start_date_xt,
                end_time=end_date_xt
            )
            
            if df is None or df.empty:
                self.logger.warning(f"备用方法也未获取到数据: {symbol}")
                return []
            
            # 转换数据格式
            data = []
            for timestamp, row in df.iterrows():
                try:
                    # 处理时间戳
                    if hasattr(timestamp, 'to_pydatetime'):
                        dt = timestamp.to_pydatetime()
                    elif isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    else:
                        dt = timestamp
                    
                    # 确保时间戳有时区信息
                    if hasattr(dt, 'tzinfo') and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    
                    # 安全获取数据
                    open_val = row.get('open') or row.get('Open') or 0
                    high_val = row.get('high') or row.get('High') or 0
                    low_val = row.get('low') or row.get('Low') or 0
                    close_val = row.get('close') or row.get('Close') or 0
                    volume_val = row.get('volume') or row.get('Volume') or 0
                    amount_val = row.get('amount') or row.get('Amount') or 0
                    
                    data_item = {
                        "datetime": dt,
                        "timestamp": dt,
                        "open": float(open_val) if open_val is not None else 0.0,
                        "high": float(high_val) if high_val is not None else 0.0,
                        "low": float(low_val) if low_val is not None else 0.0,
                        "close": float(close_val) if close_val is not None else 0.0,
                        "volume": int(volume_val) if volume_val is not None else 0,
                        "amount": float(amount_val) if amount_val is not None else 0.0,
                        "code": symbol
                    }
                    
                    # 基本数据验证
                    if data_item["open"] <= 0 and data_item["close"] <= 0:
                        self.logger.warning(f"备用方法跳过无效价格数据: {timestamp}")
                        continue
                        
                    data.append(data_item)
                except Exception as e:
                    self.logger.warning(f"备用方法跳过无效数据行: {str(e)}")
                    continue
            
            self.logger.info(f"备用方法成功获取 {len(data)} 条数据记录")
            return data
            
        except ImportError:
            raise
        except Exception as e:
            self.logger.error(f"备用数据获取方法也失败: {str(e)}")
            raise ValueError(f"无法从任何数据源获取数据: {str(e)}")
    
    def _import_xtdata(self):
        """导入xtquant库，便于测试时mock"""
        try:
            from xtquant import xtdata
            return xtdata
        except ImportError as e:
            raise ImportError(f"无法导入xtquant库，请确保miniQMT客户端正在运行: {str(e)}")
    
    async def _log_quality_issue(
        self, 
        symbol: str, 
        period: str, 
        quality_report: QualityReport
    ) -> None:
        """记录质量问题"""
        self.logger.warning(
            f"Quality issue detected for {symbol} ({period}): "
            f"score={quality_report.quality_score}, "
            f"issues={len(quality_report.issues)}"
        )


# FastAPI路由定义
def create_enhanced_api_router(api: EnhancedHistoricalDataAPI) -> FastAPI:
    """创建增强API路由"""
    router = FastAPI(title="Enhanced Historical Data API", version="2.0.0")
    
    @router.get("/historical-data", response_model=HistoricalDataResponse)
    async def get_historical_data_endpoint(
        symbol: str = Query(..., description="股票代码"),
        start_date: str = Query(..., description="开始日期 (YYYY-MM-DD)"),
        end_date: str = Query(..., description="结束日期 (YYYY-MM-DD)"),
        period: SupportedPeriod = Query(SupportedPeriod.DAILY, description="数据周期"),
        include_quality_metrics: bool = Query(True, description="包含质量指标"),
        normalize_data: bool = Query(True, description="标准化数据"),
        use_cache: bool = Query(True, description="使用缓存"),
        max_records: Optional[int] = Query(None, description="最大记录数")
    ):
        """获取增强的历史数据"""
        request = HistoricalDataRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            include_quality_metrics=include_quality_metrics,
            normalize_data=normalize_data,
            use_cache=use_cache,
            max_records=max_records
        )
        return await api.get_historical_data(request)
    
    @router.get("/multi-period", response_model=MultiPeriodResponse)
    async def get_multi_period_data_endpoint(
        symbol: str = Query(..., description="股票代码"),
        start_date: str = Query(..., description="开始日期 (YYYY-MM-DD)"),
        end_date: str = Query(..., description="结束日期 (YYYY-MM-DD)"),
        periods: str = Query(..., description="周期列表，逗号分隔，如: 1d,1h,30m"),
        include_quality_metrics: bool = Query(True, description="包含质量指标")
    ):
        """获取多周期历史数据"""
        period_list = [SupportedPeriod(p.strip()) for p in periods.split(",")]
        request = MultiPeriodRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            periods=period_list,
            include_quality_metrics=include_quality_metrics
        )
        return await api.get_multi_period_data(request)
    
    @router.get("/quality-check", response_model=QualityCheckResponse)
    async def check_data_quality_endpoint(
        symbol: str = Query(..., description="股票代码"),
        period: SupportedPeriod = Query(..., description="数据周期"),
        start_date: str = Query(..., description="开始日期 (YYYY-MM-DD)"),
        end_date: str = Query(..., description="结束日期 (YYYY-MM-DD)")
    ):
        """检查数据质量"""
        request = QualityCheckRequest(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date
        )
        return await api.check_data_quality(request)
    
    @router.get("/batch-data")
    async def get_batch_data_endpoint(
        symbols: str = Query(..., description="股票代码列表，逗号分隔"),
        start_date: str = Query(..., description="开始日期 (YYYY-MM-DD)"),
        end_date: str = Query(..., description="结束日期 (YYYY-MM-DD)"),
        period: SupportedPeriod = Query(SupportedPeriod.DAILY, description="数据周期")
    ):
        """批量获取历史数据"""
        symbol_list = [s.strip() for s in symbols.split(",")]
        results = await api.get_batch_data(
            symbol_list, start_date, end_date, period
        )
        
        return {
            "success": True,
            "symbols": symbol_list,
            "results": {k: asdict(v) if hasattr(v, '__dict__') else v 
                       for k, v in results.items()}
        }
    
    return router


# 全局API实例
_enhanced_api: Optional[EnhancedHistoricalDataAPI] = None


def get_enhanced_api() -> EnhancedHistoricalDataAPI:
    """获取增强API实例"""
    global _enhanced_api
    if _enhanced_api is None:
        _enhanced_api = EnhancedHistoricalDataAPI()
    return _enhanced_api