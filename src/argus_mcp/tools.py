"""Argus MCP Server - Tool implementations.

This module implements the core tool functions that integrate with
the existing data_agent_service to provide data access capabilities.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import aiohttp
from .models import (
    GetTradingDatesInput,
    GetStockListInput,
    GetInstrumentDetailInput,
    GetHistoryMarketDataInput,
    GetLatestMarketDataInput,
    GetFullMarketDataInput,
    TradingDatesResponse,
    StockListResponse,
    InstrumentDetailResponse,
    MarketDataResponse,
    ToolResponse
)
from .decorators import (
    with_cache,
    with_retry,
    with_all_optimizations
)
from .performance_monitor import monitor_performance
from .utils import format_error_response, retry_with_backoff

# Setup logging
logger = logging.getLogger(__name__)

# Import configuration
from .config import config

# Default data service URL from config
DATA_SERVICE_URL = config.data_service_url


class DataServiceClient:
    """客户端类，用于与data_agent_service进行HTTP通信"""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or config.data_service_url
        self.api_key = api_key or "demo_key_123"  # 使用默认演示密钥
        self.session = None
        
    async def __aenter__(self):
        # 创建带有API密钥的会话
        headers = {"X-API-Key": self.api_key}
        self.session = aiohttp.ClientSession(headers=headers)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def close(self):
        """关闭客户端会话"""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """发送HTTP请求到data_agent_service"""
        if not self.session:
            raise RuntimeError("Client session not initialized")
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP request failed: {response.status}, message='{response.reason}', url='{url}'")
        except Exception as e:
            raise Exception(f"Request error: {str(e)}")
            
    async def get_trading_dates(self, market: str, start_time: str = None, 
                               end_time: str = None, count: int = -1) -> List[str]:
        """获取交易日期"""
        params = {"market": market, "count": count}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
            
        response = await self._make_request("/api/v1/get_trading_dates", params)
        return response.get("data", [])
        
    async def get_stock_list(self, sector_name: str) -> List[str]:
        """获取股票列表"""
        params = {"sector_name": sector_name}
        response = await self._make_request("/api/v1/stock_list_in_sector", params)
        return response.get("data", [])
        
    async def get_instrument_detail(self, symbol: str) -> dict:
        """获取股票详情"""
        response = await self._make_request(f"/api/v1/instrument_detail/{symbol}")
        return response.get("data", {})
        
    async def get_history_market_data(self, symbol: str, period: str = "1d",
                                    start_time: str = None, end_time: str = None,
                                    count: int = None) -> List[dict]:
        """获取历史市场数据"""
        params = {"symbol": symbol, "period": period}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if count:
            params["count"] = count
            
        response = await self._make_request("/api/v1/hist_kline", params)
        return response.get("data", [])
        
    async def get_latest_market_data(self, symbols: List[str]) -> dict:
        """获取最新市场数据"""
        symbols_str = ",".join(symbols)
        params = {"symbols": symbols_str}
        response = await self._make_request("/api/v1/latest_market_data", params)
        return response.get("data", {})
        
    async def get_full_market_data(self, symbol: str, fields: List[str] = None) -> dict:
        """获取完整市场数据"""
        params = {"symbol": symbol}
        if fields:
            params["fields"] = ",".join(fields)
            
        response = await self._make_request("/api/v1/full_market_data", params)
        return response.get("data", {})


# 工具元数据创建函数
def create_tool_metadata(tool_name: str, tool_info: dict) -> dict:
    """创建MCP工具元数据"""
    return {
        "name": tool_name,
        "description": tool_info["description"],
        "inputSchema": {
            "type": "object",
            "properties": tool_info["parameters"],
            "required": list(tool_info["parameters"].keys())
        }
    }

# 全局客户端实例
_client = DataServiceClient()

# 工具清理函数
async def cleanup_tools():
    """清理工具资源"""
    try:
        if _client:
            await _client.close()
        logger.info("Tools cleanup completed")
    except Exception as e:
        logger.error(f"Error during tools cleanup: {str(e)}")


@monitor_performance()
@with_cache(ttl=3600)
@with_retry(max_attempts=3)
async def get_trading_dates_tool(input_data: GetTradingDatesInput) -> TradingDatesResponse:
    """获取交易日期的MCP工具包装器"""
    async with DataServiceClient() as client:
        try:
            # 调用data_agent_service的API
            trading_dates = await client.get_trading_dates(
                market=input_data.market,
                start_time=getattr(input_data, 'start_date', None),
                end_time=getattr(input_data, 'end_date', None),
                count=getattr(input_data, 'count', -1)
            )
            
            return TradingDatesResponse(
                success=True,
                data=trading_dates,
                message="Trading dates retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting trading dates: {str(e)}")
            return TradingDatesResponse(
                success=False,
                data=[],
                message=f"Error: {str(e)}"
            )


@monitor_performance()
@with_cache(ttl=600)
@with_retry(max_attempts=3)
async def get_stock_list_tool(input_data: GetStockListInput) -> StockListResponse:
    """获取股票列表的MCP工具包装器"""
    async with DataServiceClient() as client:
        try:
            # 调用data_agent_service的API
            stock_list = await client.get_stock_list(
                sector_name=input_data.sector
            )
            
            return StockListResponse(
                success=True,
                data=stock_list,
                message="Stock list retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting stock list: {str(e)}")
            return StockListResponse(
                success=False,
                data=[],
                message=f"Error: {str(e)}"
            )


@monitor_performance()
@with_cache(ttl=300)
@with_retry(max_attempts=3)
async def get_instrument_detail_tool(input_data: GetInstrumentDetailInput) -> InstrumentDetailResponse:
    """获取股票详情的MCP工具包装器"""
    async with DataServiceClient() as client:
        try:
            # 调用data_agent_service的API
            instrument_detail = await client.get_instrument_detail(
                symbol=input_data.code
            )
            
            return InstrumentDetailResponse(
                success=True,
                data=instrument_detail,
                message="Instrument detail retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting instrument detail: {str(e)}")
            return InstrumentDetailResponse(
                success=False,
                data={},
                message=f"Error: {str(e)}"
            )


@monitor_performance()
@with_cache(ttl=1800)
@with_retry(max_attempts=3)
async def get_history_market_data_tool(input_data: GetHistoryMarketDataInput) -> MarketDataResponse:
    """获取历史市场数据的MCP工具包装器"""
    async with DataServiceClient() as client:
        try:
            # 调用data_agent_service的API
            # 注意：GetHistoryMarketDataInput使用codes字段，但API需要单个symbol
            # 这里取第一个代码作为示例，实际应该处理多个代码
            symbol = input_data.codes[0] if input_data.codes else ""
            history_data = await client.get_history_market_data(
                symbol=symbol,
                period=input_data.period,
                start_time=input_data.start_date,
                end_time=input_data.end_date,
                count=getattr(input_data, 'count', None)
            )
            
            return MarketDataResponse(
                success=True,
                data=history_data,
                message="History market data retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting history market data: {str(e)}")
            return MarketDataResponse(
                success=False,
                data=[],
                message=f"Error: {str(e)}"
            )


@monitor_performance()
@with_cache(ttl=30)
@with_retry(max_attempts=3)
async def get_latest_market_data_tool(input_data: GetLatestMarketDataInput) -> MarketDataResponse:
    """获取最新市场数据的MCP工具包装器"""
    async with DataServiceClient() as client:
        try:
            # 调用data_agent_service的API
            latest_data = await client.get_latest_market_data(
                symbols=input_data.codes
            )
            
            return MarketDataResponse(
                success=True,
                data=latest_data,
                message="Latest market data retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting latest market data: {str(e)}")
            return MarketDataResponse(
                success=False,
                data={},
                message=f"Error: {str(e)}"
            )


@monitor_performance()
@with_cache(ttl=60)
@with_retry(max_attempts=3)
async def get_full_market_data_tool(input_data: GetFullMarketDataInput) -> MarketDataResponse:
    """获取完整市场数据的MCP工具包装器"""
    async with DataServiceClient() as client:
        try:
            # 调用data_agent_service的API
            # 注意：GetFullMarketDataInput使用codes字段，但API需要单个symbol
            # 这里取第一个代码作为示例，实际应该处理多个代码
            symbol = input_data.codes[0] if input_data.codes else ""
            full_data = await client.get_full_market_data(
                symbol=symbol,
                fields=input_data.fields
            )
            
            return MarketDataResponse(
                success=True,
                data=full_data,
                message="Full market data retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting full market data: {str(e)}")
            return MarketDataResponse(
                success=False,
                data={},
                message=f"Error: {str(e)}"
            )


# 工具注册表
TOOL_REGISTRY = {
    "get_trading_dates": {
        "function": get_trading_dates_tool,
        "input_model": GetTradingDatesInput,
        "description": "获取指定市场的交易日期列表",
        "parameters": {
            "market": "市场代码，如'SH'或'SZ'",
            "start_time": "开始日期，格式YYYYMMDD（可选）",
            "end_time": "结束日期，格式YYYYMMDD（可选）",
            "count": "返回的交易日期数量，-1表示全部"
        }
    },
    "get_stock_list": {
        "function": get_stock_list_tool,
        "input_model": GetStockListInput,
        "description": "获取指定板块的股票列表",
        "parameters": {
            "sector_name": "板块名称，如'沪深A股'"
        }
    },
    "get_instrument_detail": {
        "function": get_instrument_detail_tool,
        "input_model": GetInstrumentDetailInput,
        "description": "获取指定股票的详细信息",
        "parameters": {
            "symbol": "股票代码，如'600519.SH'"
        }
    },
    "get_history_market_data": {
        "function": get_history_market_data_tool,
        "input_model": GetHistoryMarketDataInput,
        "description": "获取股票的历史市场数据",
        "parameters": {
            "symbol": "股票代码，如'600519.SH'",
            "period": "K线周期，如'1d', '1h', '5m'等",
            "start_time": "开始时间，格式YYYYMMDD（可选）",
            "end_time": "结束时间，格式YYYYMMDD（可选）",
            "count": "返回的数据条数（可选）"
        }
    },
    "get_latest_market_data": {
        "function": get_latest_market_data_tool,
        "input_model": GetLatestMarketDataInput,
        "description": "获取股票的最新市场数据",
        "parameters": {
            "symbols": "股票代码列表，如['600519.SH', '000001.SZ']"
        }
    },
    "get_full_market_data": {
        "function": get_full_market_data_tool,
        "input_model": GetFullMarketDataInput,
        "description": "获取股票的完整市场数据",
        "parameters": {
            "symbol": "股票代码，如'600519.SH'",
            "fields": "数据字段列表（可选），如['open', 'high', 'low', 'close']"
        }
    }
}


async def cleanup_tools():
    """Cleanup tool resources."""
    await _client.close()