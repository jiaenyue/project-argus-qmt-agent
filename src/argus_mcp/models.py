"""Argus MCP Server - Data models and input validation.

This module defines Pydantic models for input validation and data structures
used by the MCP tools.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class GetTradingDatesInput(BaseModel):
    """Input model for get_trading_dates tool."""
    
    market: str = Field(
        default="SH",
        description="市场代码，如 'SH'（上海）或 'SZ'（深圳）"
    )
    
    @field_validator('market')
    @classmethod
    def validate_market(cls, v):
        """Validate market code."""
        valid_markets = ['SH', 'SZ', 'BJ', 'HK', 'US']
        if v.upper() not in valid_markets:
            raise ValueError(f"市场代码必须是以下之一: {valid_markets}")
        return v.upper()


class GetStockListInput(BaseModel):
    """Input model for get_stock_list tool."""
    
    sector: str = Field(
        default="沪深A股",
        description="板块代码或名称"
    )
    
    limit: Optional[int] = Field(
        default=None,
        description="返回结果数量限制",
        ge=1,
        le=5000
    )


class GetInstrumentDetailInput(BaseModel):
    """Input model for get_instrument_detail tool."""
    
    code: str = Field(
        description="股票代码，如 '000001.SZ' 或 '600000.SH'"
    )
    
    iscomplete: bool = Field(
        default=True,
        description="是否返回完整的股票信息"
    )
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v):
        """Validate stock code format."""
        if not v:
            raise ValueError("股票代码不能为空")
        
        # Basic format validation
        if '.' not in v:
            raise ValueError("股票代码格式错误，应包含市场后缀，如 '000001.SZ'")
        
        code_part, market_part = v.split('.', 1)
        
        if not code_part.isdigit() or len(code_part) != 6:
            raise ValueError("股票代码应为6位数字")
        
        valid_markets = ['SH', 'SZ', 'BJ', 'HK']
        if market_part.upper() not in valid_markets:
            raise ValueError(f"市场后缀必须是以下之一: {valid_markets}")
        
        return f"{code_part}.{market_part.upper()}"


class GetHistoryMarketDataInput(BaseModel):
    """Input model for get_history_market_data tool."""
    
    codes: List[str] = Field(
        description="股票代码列表",
        min_length=1,
        max_length=100
    )
    
    period: str = Field(
        default="1d",
        description="数据周期：1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M"
    )
    
    start_date: Optional[str] = Field(
        default=None,
        description="开始日期，格式：YYYY-MM-DD"
    )
    
    end_date: Optional[str] = Field(
        default=None,
        description="结束日期，格式：YYYY-MM-DD"
    )
    
    fields: List[str] = Field(
        default=["open", "high", "low", "close", "volume"],
        description="数据字段列表"
    )
    
    @field_validator('codes')
    @classmethod
    def validate_codes(cls, v):
        """Validate stock codes."""
        validated_codes = []
        for code in v:
            if '.' not in code:
                raise ValueError(f"股票代码格式错误: {code}，应包含市场后缀")
            
            code_part, market_part = code.split('.', 1)
            if not code_part.isdigit() or len(code_part) != 6:
                raise ValueError(f"股票代码格式错误: {code}，应为6位数字")
            
            validated_codes.append(f"{code_part}.{market_part.upper()}")
        
        return validated_codes
    
    @field_validator('period')
    @classmethod
    def validate_period(cls, v):
        """Validate period format."""
        valid_periods = ['1m', '5m', '15m', '30m', '1h', '1d', '1w', '1M']
        if v not in valid_periods:
            raise ValueError(f"数据周期必须是以下之一: {valid_periods}")
        return v
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v):
        """Validate date format."""
        if v is None:
            return v
        
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f"日期格式错误: {v}，应为 YYYY-MM-DD")
    
    @field_validator('fields')
    @classmethod
    def validate_fields(cls, v):
        """Validate field names."""
        valid_fields = [
            'open', 'high', 'low', 'close', 'volume', 'amount',
            'pre_close', 'change', 'change_pct', 'turnover',
            'vwap', 'adj_close', 'adj_factor'
        ]
        
        for field in v:
            if field not in valid_fields:
                raise ValueError(f"无效的字段名: {field}，有效字段: {valid_fields}")
        
        return v


class GetLatestMarketDataInput(BaseModel):
    """Input model for get_latest_market_data tool."""
    
    codes: List[str] = Field(
        description="股票代码列表",
        min_length=1,
        max_length=200
    )
    
    fields: List[str] = Field(
        default=["last_price", "change", "change_pct", "volume"],
        description="数据字段列表"
    )
    
    @field_validator('codes')
    @classmethod
    def validate_codes(cls, v):
        """Validate stock codes."""
        validated_codes = []
        for code in v:
            if '.' not in code:
                raise ValueError(f"股票代码格式错误: {code}，应包含市场后缀")
            
            code_part, market_part = code.split('.', 1)
            if not code_part.isdigit() or len(code_part) != 6:
                raise ValueError(f"股票代码格式错误: {code}，应为6位数字")
            
            validated_codes.append(f"{code_part}.{market_part.upper()}")
        
        return validated_codes
    
    @field_validator('fields')
    @classmethod
    def validate_fields(cls, v):
        """Validate field names for latest market data."""
        valid_fields = [
            'last_price', 'pre_close', 'open', 'high', 'low',
            'volume', 'amount', 'change', 'change_pct', 'turnover',
            'bid_price', 'ask_price', 'bid_volume', 'ask_volume',
            'market_cap', 'pe_ratio', 'pb_ratio'
        ]
        
        for field in v:
            if field not in valid_fields:
                raise ValueError(f"无效的字段名: {field}，有效字段: {valid_fields}")
        
        return v


class GetFullMarketDataInput(BaseModel):
    """Input model for get_full_market_data tool."""
    
    codes: List[str] = Field(
        description="股票代码列表",
        min_length=1,
        max_length=50
    )
    
    period: str = Field(
        default="1d",
        description="数据周期：1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M"
    )
    
    start_date: Optional[str] = Field(
        default=None,
        description="开始日期，格式：YYYY-MM-DD"
    )
    
    fields: List[str] = Field(
        default=["open", "high", "low", "close", "volume"],
        description="数据字段列表"
    )
    
    include_latest: bool = Field(
        default=True,
        description="是否包含最新实时数据"
    )
    
    @field_validator('codes')
    @classmethod
    def validate_codes(cls, v):
        """Validate stock codes."""
        validated_codes = []
        for code in v:
            if '.' not in code:
                raise ValueError(f"股票代码格式错误: {code}，应包含市场后缀")
            
            code_part, market_part = code.split('.', 1)
            if not code_part.isdigit() or len(code_part) != 6:
                raise ValueError(f"股票代码格式错误: {code}，应为6位数字")
            
            validated_codes.append(f"{code_part}.{market_part.upper()}")
        
        return validated_codes
    
    @field_validator('period')
    @classmethod
    def validate_period(cls, v):
        """Validate period format."""
        valid_periods = ['1m', '5m', '15m', '30m', '1h', '1d', '1w', '1M']
        if v not in valid_periods:
            raise ValueError(f"数据周期必须是以下之一: {valid_periods}")
        return v
    
    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v):
        """Validate start date format."""
        if v is None:
            return v
        
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f"日期格式错误: {v}，应为 YYYY-MM-DD")
    
    @field_validator('fields')
    @classmethod
    def validate_fields(cls, v):
        """Validate field names."""
        valid_fields = [
            'open', 'high', 'low', 'close', 'volume', 'amount',
            'pre_close', 'change', 'change_pct', 'turnover',
            'vwap', 'adj_close', 'adj_factor', 'last_price'
        ]
        
        for field in v:
            if field not in valid_fields:
                raise ValueError(f"无效的字段名: {field}，有效字段: {valid_fields}")
        
        return v


# Response models for structured output
class ToolResponse(BaseModel):
    """Base response model for tool outputs."""
    
    success: bool = Field(description="操作是否成功")
    data: Optional[Any] = Field(default=None, description="返回的数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据信息")


class TradingDatesResponse(ToolResponse):
    """Response model for trading dates."""
    
    data: Optional[List[str]] = Field(default=None, description="交易日期列表")


class StockListResponse(ToolResponse):
    """Response model for stock list."""
    
    data: Optional[List[str]] = Field(default=None, description="股票代码列表")


class InstrumentDetailResponse(ToolResponse):
    """Response model for instrument detail."""
    
    data: Optional[Dict[str, Any]] = Field(default=None, description="股票详细信息")


class MarketDataResponse(ToolResponse):
    """Response model for market data."""
    
    data: Optional[Dict[str, Any]] = Field(default=None, description="行情数据")