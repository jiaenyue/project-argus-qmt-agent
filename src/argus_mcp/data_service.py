"""Data Service Module.

This module provides a unified interface for accessing data from the data_agent_service.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .tools import DataServiceClient

logger = logging.getLogger(__name__)


class DataService:
    """Service class for accessing data from data_agent_service."""
    
    def __init__(self, base_url: str = None):
        """Initialize data service."""
        self.base_url = base_url
        self._client = None
        
    async def _get_client(self) -> DataServiceClient:
        """Get or create data service client."""
        if self._client is None:
            self._client = DataServiceClient(self.base_url)
        return self._client
        
    async def close(self):
        """Close data service client."""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def get_trading_dates(self, year: int = None, market: str = "SH", 
                               start_time: str = None, end_time: str = None, 
                               count: int = -1) -> List[str]:
        """Get trading dates for specified year or date range."""
        try:
            # If year is specified, create date range for that year
            if year and not start_time and not end_time:
                start_time = f"{year}-01-01"
                end_time = f"{year}-12-31"
            
            async with DataServiceClient(self.base_url) as client:
                return await client.get_trading_dates(
                    market=market,
                    start_time=start_time,
                    end_time=end_time,
                    count=count
                )
        except Exception as e:
            logger.error(f"Error getting trading dates: {e}")
            return []
    
    async def get_stock_list(self, market: str = "SH") -> List[str]:
        """Get stock list for specified market."""
        try:
            async with DataServiceClient(self.base_url) as client:
                return await client.get_stock_list(sector_name=market)
        except Exception as e:
            logger.error(f"Error getting stock list: {e}")
            return []
    
    async def get_market_status(self) -> Dict[str, Any]:
        """Get current market status."""
        try:
            # This is a placeholder - implement based on actual API
            return {
                "status": "open",
                "timestamp": datetime.now().isoformat(),
                "market": "SH"
            }
        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            return {}
    
    async def get_latest_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """Get latest market data for specified symbols."""
        try:
            async with DataServiceClient(self.base_url) as client:
                return await client.get_latest_market_data(symbols)
        except Exception as e:
            logger.error(f"Error getting latest market data: {e}")
            return {}
    
    async def get_instrument_detail(self, symbol: str) -> Dict[str, Any]:
        """Get instrument detail for specified symbol."""
        try:
            async with DataServiceClient(self.base_url) as client:
                return await client.get_instrument_detail(symbol)
        except Exception as e:
            logger.error(f"Error getting instrument detail: {e}")
            return {}
    
    async def get_sector_performance(self) -> Dict[str, Any]:
        """Get sector performance data."""
        try:
            # This is a placeholder - implement based on actual API
            return {
                "sectors": [],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting sector performance: {e}")
            return {}
    
    async def get_historical_data(self, symbol: str, period: str = "1d",
                                 start_time: str = None, end_time: str = None,
                                 count: int = None) -> List[Dict[str, Any]]:
        """Get historical market data for specified symbol."""
        try:
            async with DataServiceClient(self.base_url) as client:
                return await client.get_history_market_data(
                    symbol=symbol,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    count=count
                )
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return []
    
    async def get_full_market_data(self, symbol: str, fields: List[str] = None) -> Dict[str, Any]:
        """Get full market data for specified symbol."""
        try:
            async with DataServiceClient(self.base_url) as client:
                return await client.get_full_market_data(symbol, fields)
        except Exception as e:
            logger.error(f"Error getting full market data: {e}")
            return {}