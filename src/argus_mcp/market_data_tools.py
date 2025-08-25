"""Market Data Tools - 包装MCP工具函数的便捷类。

这个模块提供了一个MarketDataTools类，用于包装现有的MCP工具函数，
使其更容易在测试和其他场景中使用。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .tools import (
    get_trading_dates_tool,
    get_stock_list_tool,
    get_instrument_detail_tool,
    get_history_market_data_tool,
    get_latest_market_data_tool,
    get_full_market_data_tool
)
from .models import (
    GetTradingDatesInput,
    GetStockListInput,
    GetInstrumentDetailInput,
    GetHistoryMarketDataInput,
    GetLatestMarketDataInput,
    GetFullMarketDataInput
)

logger = logging.getLogger(__name__)


class MarketDataTools:
    """市场数据工具类
    
    提供对MCP工具函数的便捷访问接口，支持同步和异步调用。
    """
    
    def __init__(self):
        """初始化市场数据工具"""
        self.logger = logger
        
    async def get_trading_dates(self, market: str, start_time: str = None, 
                               end_time: str = None, count: int = -1) -> List[str]:
        """获取交易日期
        
        Args:
            market: 市场代码，如'SH'或'SZ'
            start_time: 开始日期，格式YYYYMMDD（可选）
            end_time: 结束日期，格式YYYYMMDD（可选）
            count: 返回的交易日期数量，-1表示全部
            
        Returns:
            交易日期列表
        """
        input_data = GetTradingDatesInput(
            market=market,
            start_time=start_time,
            end_time=end_time,
            count=count
        )
        
        response = await get_trading_dates_tool(input_data)
        if response.success:
            return response.data
        else:
            self.logger.error(f"Failed to get trading dates: {response.error}")
            return []
            
    async def get_stock_list(self, sector_name: str) -> List[str]:
        """获取股票列表
        
        Args:
            sector_name: 板块名称，如'沪深A股'
            
        Returns:
            股票代码列表
        """
        input_data = GetStockListInput(sector_name=sector_name)
        
        response = await get_stock_list_tool(input_data)
        if response.success:
            return response.data
        else:
            self.logger.error(f"Failed to get stock list: {response.error}")
            return []
            
    async def get_instrument_detail(self, symbol: str) -> Dict[str, Any]:
        """获取股票详情
        
        Args:
            symbol: 股票代码，如'600519.SH'
            
        Returns:
            股票详细信息字典
        """
        input_data = GetInstrumentDetailInput(code=symbol)
        
        response = await get_instrument_detail_tool(input_data)
        if response.success:
            return response.data
        else:
            self.logger.error(f"Failed to get instrument detail: {response.error}")
            return {}
            
    async def get_history_market_data(self, symbol: str, period: str = "1d",
                                    start_time: str = None, end_time: str = None,
                                    count: int = None) -> List[Dict[str, Any]]:
        """获取历史市场数据
        
        Args:
            symbol: 股票代码，如'600519.SH'
            period: K线周期，如'1d', '1h', '5m'等
            start_time: 开始时间，格式YYYYMMDD（可选）
            end_time: 结束时间，格式YYYYMMDD（可选）
            count: 返回的数据条数（可选）
            
        Returns:
            历史市场数据列表
        """
        input_data = GetHistoryMarketDataInput(
            symbol=symbol,
            period=period,
            start_time=start_time,
            end_time=end_time,
            count=count
        )
        
        response = await get_history_market_data_tool(input_data)
        if response.success:
            return response.data
        else:
            self.logger.error(f"Failed to get history market data: {response.error}")
            return []
            
    async def get_latest_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取最新市场数据
        
        Args:
            symbols: 股票代码列表，如['600519.SH', '000001.SZ']
            
        Returns:
            最新市场数据字典
        """
        input_data = GetLatestMarketDataInput(codes=symbols)
        
        response = await get_latest_market_data_tool(input_data)
        if response.success:
            return response.data
        else:
            self.logger.error(f"Failed to get latest market data: {response.error}")
            return {}
            
    async def get_full_market_data(self, symbol: str, fields: List[str] = None) -> Dict[str, Any]:
        """获取完整市场数据
        
        Args:
            symbol: 股票代码，如'600519.SH'
            fields: 数据字段列表（可选），如['open', 'high', 'low', 'close']
            
        Returns:
            完整市场数据字典
        """
        input_data = GetFullMarketDataInput(
            symbol=symbol,
            fields=fields
        )
        
        response = await get_full_market_data_tool(input_data)
        if response.success:
            return response.data
        else:
            self.logger.error(f"Failed to get full market data: {response.error}")
            return {}
            
    # 同步版本的方法（使用asyncio.run）
    def get_trading_dates_sync(self, market: str, start_time: str = None, 
                              end_time: str = None, count: int = -1) -> List[str]:
        """获取交易日期（同步版本）"""
        return asyncio.run(self.get_trading_dates(market, start_time, end_time, count))
        
    def get_stock_list_sync(self, sector_name: str) -> List[str]:
        """获取股票列表（同步版本）"""
        return asyncio.run(self.get_stock_list(sector_name))
        
    def get_instrument_detail_sync(self, symbol: str) -> Dict[str, Any]:
        """获取股票详情（同步版本）"""
        return asyncio.run(self.get_instrument_detail(symbol))
        
    def get_history_market_data_sync(self, symbol: str, period: str = "1d",
                                   start_time: str = None, end_time: str = None,
                                   count: int = None) -> List[Dict[str, Any]]:
        """获取历史市场数据（同步版本）"""
        return asyncio.run(self.get_history_market_data(symbol, period, start_time, end_time, count))
        
    def get_latest_market_data_sync(self, symbols: List[str]) -> Dict[str, Any]:
        """获取最新市场数据（同步版本）"""
        return asyncio.run(self.get_latest_market_data(symbols))
        
    def get_full_market_data_sync(self, symbol: str, fields: List[str] = None) -> Dict[str, Any]:
        """获取完整市场数据（同步版本）"""
        return asyncio.run(self.get_full_market_data(symbol, fields))