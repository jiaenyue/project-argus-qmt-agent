# -*- coding: utf-8 -*-
"""
Historical data models for the enhanced historical data system.

This module defines the core data models used for historical K-line data processing,
validation, and standardization.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from dataclasses import dataclass


class SupportedPeriod(str, Enum):
    """Supported time periods for historical data."""
    
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"
    
    # Legacy aliases for backward compatibility
    DAILY = "1d"
    HOURLY = "1h"
    WEEKLY = "1w"
    MONTHLY = "1M"


@dataclass
class DataQualityMetrics:
    """Data quality metrics for historical data."""
    
    completeness_rate: float    # 数据完整性比率 (0-1)
    accuracy_score: float       # 数据准确性评分 (0-1)
    timeliness_score: float     # 数据及时性评分 (0-1)
    consistency_score: float    # 数据一致性评分 (0-1)
    anomaly_count: int         # 异常数据数量
    total_records: int         # 总记录数
    missing_records: int       # 缺失记录数
    invalid_ohlc_count: int    # OHLC逻辑错误数量


class ValidationResult(BaseModel):
    """Result of data validation."""
    
    is_valid: bool = Field(description="数据是否有效")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表")
    quality_score: float = Field(default=1.0, description="数据质量评分 (0-1)")


class StandardKLineData(BaseModel):
    """Standardized K-line data model."""
    
    timestamp: datetime = Field(description="时间戳，ISO 8601格式")
    open: Decimal = Field(description="开盘价，精确到4位小数")
    high: Decimal = Field(description="最高价，精确到4位小数")
    low: Decimal = Field(description="最低价，精确到4位小数")
    close: Decimal = Field(description="收盘价，精确到4位小数")
    volume: int = Field(description="成交量，整数")
    amount: Decimal = Field(description="成交额，精确到2位小数")
    quality_score: float = Field(default=1.0, description="数据质量评分 (0-1)")
    code: Optional[str] = Field(default=None, description="股票代码")
    
    @field_validator('open', 'high', 'low', 'close')
    @classmethod
    def validate_price_precision(cls, v):
        """Validate price precision to 4 decimal places."""
        if v is not None:
            # Round to 4 decimal places
            return Decimal(str(v)).quantize(Decimal('0.0001'))
        return v
    
    @field_validator('amount')
    @classmethod
    def validate_amount_precision(cls, v):
        """Validate amount precision to 2 decimal places."""
        if v is not None:
            # Round to 2 decimal places
            return Decimal(str(v)).quantize(Decimal('0.01'))
        return v
    
    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v):
        """Validate volume is non-negative integer."""
        if v is not None and v < 0:
            raise ValueError("成交量不能为负数")
        return v
    
    @field_validator('quality_score')
    @classmethod
    def validate_quality_score(cls, v):
        """Validate quality score is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("质量评分必须在0-1之间")
        return v


class PeriodInfo(BaseModel):
    """Information about a supported period."""
    
    period: str = Field(description="周期标识符")
    description: str = Field(description="周期描述")
    min_interval_seconds: int = Field(description="最小间隔秒数")
    max_history_days: int = Field(description="最大历史天数")
    cache_ttl_seconds: int = Field(description="缓存TTL秒数")


class ResponseMetadata(BaseModel):
    """Metadata for historical data response."""
    
    symbol: str = Field(description="股票代码")
    period: str = Field(description="数据周期")
    start_date: str = Field(description="开始日期")
    end_date: str = Field(description="结束日期")
    total_count: int = Field(description="总记录数")
    data_quality: DataQualityMetrics = Field(description="数据质量指标")
    cache_hit: bool = Field(description="是否命中缓存")
    response_time_ms: int = Field(description="响应时间毫秒")


class HistoricalDataResponse(BaseModel):
    """Response model for historical data requests."""
    
    code: int = Field(description="响应代码")
    message: str = Field(description="响应消息")
    data: List[StandardKLineData] = Field(description="K线数据列表")
    metadata: ResponseMetadata = Field(description="响应元数据")


class KLineDataRequest(BaseModel):
    """Request model for historical K-line data."""
    
    symbol: str = Field(description="股票代码")
    start_date: str = Field(description="开始日期 YYYY-MM-DD")
    end_date: str = Field(description="结束日期 YYYY-MM-DD")
    period: str = Field(description="数据周期")
    fields: Optional[List[str]] = Field(default=None, description="字段列表")
    format: str = Field(default="standard", description="数据格式")
    
    @field_validator('period')
    @classmethod
    def validate_period(cls, v):
        """Validate period is supported."""
        try:
            SupportedPeriod(v)
            return v
        except ValueError:
            valid_periods = [p.value for p in SupportedPeriod]
            raise ValueError(f"不支持的周期: {v}，支持的周期: {valid_periods}")
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v):
        """Validate date format."""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f"日期格式错误: {v}，应为 YYYY-MM-DD")


class AnomalyReport(BaseModel):
    """Report for data anomalies."""
    
    timestamp: datetime = Field(description="异常数据时间戳")
    anomaly_type: str = Field(description="异常类型")
    description: str = Field(description="异常描述")
    severity: str = Field(description="严重程度: low, medium, high")
    suggested_action: str = Field(description="建议处理方式")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="原始数据")


class DataSourceInfo(BaseModel):
    """Information about data source."""
    
    source_name: str = Field(description="数据源名称")
    priority: int = Field(description="优先级")
    is_available: bool = Field(description="是否可用")
    last_update: Optional[datetime] = Field(default=None, description="最后更新时间")
    error_count: int = Field(default=0, description="错误次数")
    success_rate: float = Field(default=1.0, description="成功率")