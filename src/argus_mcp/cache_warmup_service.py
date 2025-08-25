"""Cache Warmup Service.

This service preloads frequently accessed data into cache to improve hit rates.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta

from .cache_config import cache_config, DataType
from .data_service import DataService

logger = logging.getLogger(__name__)


class CacheWarmupService:
    """Service for preloading cache with frequently accessed data."""
    
    def __init__(self, cache_manager, data_service: DataService):
        """Initialize cache warmup service."""
        self.cache_manager = cache_manager
        self.data_service = data_service
        
        # Warmup configuration
        self.warmup_enabled = True
        self.warmup_interval = 1800  # 30 minutes
        self.startup_warmup_delay = 60  # 1 minute after startup
        
        # Warmup priorities
        self.warmup_priorities = {
            DataType.TRADING_DATES: 10,
            DataType.STOCK_LIST: 9,
            DataType.MARKET_STATUS: 8,
            DataType.LATEST_DATA: 7,
            DataType.INSTRUMENT_DETAIL: 6,
            DataType.SECTOR_DATA: 5,
            DataType.HISTORICAL_DATA: 4,
            DataType.FULL_DATA: 3
        }
        
        # Warmup state
        self._warmup_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._last_warmup = 0
        self._warmup_stats = {
            'total_warmups': 0,
            'successful_warmups': 0,
            'failed_warmups': 0,
            'last_warmup_duration': 0,
            'items_warmed': 0
        }
        
        logger.info("Cache warmup service initialized")
    
    async def start(self):
        """Start cache warmup service."""
        if self._is_running:
            logger.warning("Cache warmup service already running")
            return
        
        self._is_running = True
        self._warmup_task = asyncio.create_task(self._warmup_loop())
        
        # Perform initial warmup after delay
        asyncio.create_task(self._initial_warmup())
        
        logger.info("Cache warmup service started")
    
    async def stop(self):
        """Stop cache warmup service."""
        self._is_running = False
        self.warmup_enabled = False
        
        if self._warmup_task:
            self._warmup_task.cancel()
            try:
                await self._warmup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cache warmup service stopped")
    
    async def _initial_warmup(self):
        """Perform initial cache warmup after startup."""
        await asyncio.sleep(self.startup_warmup_delay)
        
        if self.warmup_enabled:
            logger.info("Starting initial cache warmup")
            await self.warmup_cache()
    
    async def _warmup_loop(self):
        """Main warmup loop."""
        while self._is_running and self.warmup_enabled:
            try:
                current_time = time.time()
                
                # Check if it's time for warmup
                if current_time - self._last_warmup >= self.warmup_interval:
                    await self.warmup_cache()
                
                # Sleep for a short interval
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in warmup loop: {e}")
                await asyncio.sleep(60)
    
    async def warmup_cache(self):
        """Perform cache warmup."""
        if not self.warmup_enabled:
            return
        
        start_time = time.time()
        self._warmup_stats['total_warmups'] += 1
        items_warmed = 0
        
        logger.info("Starting cache warmup")
        
        try:
            # Sort data types by priority
            sorted_types = sorted(
                self.warmup_priorities.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for data_type, priority in sorted_types:
                if not self.warmup_enabled:
                    break
                
                try:
                    # Check if this data type should be preloaded
                    if cache_config.should_preload(data_type):
                        warmed_count = await self._warmup_data_type(data_type)
                        items_warmed += warmed_count
                        
                        # Small delay between data types
                        await asyncio.sleep(0.1)
                
                except Exception as e:
                    logger.error(f"Error warming up {data_type.value}: {e}")
                    self._warmup_stats['failed_warmups'] += 1
            
            # Update statistics
            duration = time.time() - start_time
            self._warmup_stats['successful_warmups'] += 1
            self._warmup_stats['last_warmup_duration'] = duration
            self._warmup_stats['items_warmed'] += items_warmed
            self._last_warmup = time.time()
            
            logger.info(f"Cache warmup completed in {duration:.2f}s, warmed {items_warmed} items")
            
        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")
            self._warmup_stats['failed_warmups'] += 1
    
    async def _warmup_data_type(self, data_type: DataType) -> int:
        """Warmup specific data type."""
        items_warmed = 0
        
        try:
            if data_type == DataType.TRADING_DATES:
                # Warmup trading dates for current and next year
                current_year = datetime.now().year
                for year in [current_year, current_year + 1]:
                    try:
                        dates = await self.data_service.get_trading_dates(year)
                        if dates:
                            cache_key = f"trading_dates_{year}"
                            await self.cache_manager.set(
                                cache_key,
                                dates,
                                ttl=cache_config.get_cache_rule(data_type).ttl
                            )
                            items_warmed += 1
                    except Exception as e:
                        logger.debug(f"Failed to warmup trading dates for {year}: {e}")
            
            elif data_type == DataType.STOCK_LIST:
                # Warmup stock lists for major markets
                markets = ['SH', 'SZ', 'BJ']  # Shanghai, Shenzhen, Beijing
                for market in markets:
                    try:
                        stocks = await self.data_service.get_stock_list(market)
                        if stocks:
                            cache_key = f"stock_list_{market}"
                            await self.cache_manager.set(
                                cache_key,
                                stocks,
                                ttl=cache_config.get_cache_rule(data_type).ttl
                            )
                            items_warmed += 1
                    except Exception as e:
                        logger.debug(f"Failed to warmup stock list for {market}: {e}")
            
            elif data_type == DataType.MARKET_STATUS:
                # Warmup current market status
                try:
                    status = await self.data_service.get_market_status()
                    if status:
                        cache_key = "market_status_current"
                        await self.cache_manager.set(
                            cache_key,
                            status,
                            ttl=cache_config.get_cache_rule(data_type).ttl
                        )
                        items_warmed += 1
                except Exception as e:
                    logger.debug(f"Failed to warmup market status: {e}")
            
            elif data_type == DataType.LATEST_DATA:
                # Warmup latest data for popular stocks
                popular_stocks = await self._get_popular_stocks()
                for stock_code in popular_stocks[:50]:  # Top 50 popular stocks
                    try:
                        data = await self.data_service.get_latest_market_data([stock_code])
                        if data:
                            cache_key = f"latest_data_{stock_code}"
                            await self.cache_manager.set(
                                cache_key,
                                data,
                                ttl=cache_config.get_cache_rule(data_type).ttl
                            )
                            items_warmed += 1
                    except Exception as e:
                        logger.debug(f"Failed to warmup latest data for {stock_code}: {e}")
            
            elif data_type == DataType.INSTRUMENT_DETAIL:
                # Warmup instrument details for major indices and ETFs
                major_instruments = [
                    '000001.SH',  # 上证指数
                    '399001.SZ',  # 深证成指
                    '399006.SZ',  # 创业板指
                    '510300.SH',  # 沪深300ETF
                    '159919.SZ',  # 沪深300ETF
                ]
                
                for instrument in major_instruments:
                    try:
                        detail = await self.data_service.get_instrument_detail(instrument)
                        if detail:
                            cache_key = f"instrument_detail_{instrument}"
                            await self.cache_manager.set(
                                cache_key,
                                detail,
                                ttl=cache_config.get_cache_rule(data_type).ttl
                            )
                            items_warmed += 1
                    except Exception as e:
                        logger.debug(f"Failed to warmup instrument detail for {instrument}: {e}")
            
            elif data_type == DataType.SECTOR_DATA:
                # Warmup sector performance data
                try:
                    sector_data = await self.data_service.get_sector_performance()
                    if sector_data:
                        cache_key = "sector_performance_current"
                        await self.cache_manager.set(
                            cache_key,
                            sector_data,
                            ttl=cache_config.get_cache_rule(data_type).ttl
                        )
                        items_warmed += 1
                except Exception as e:
                    logger.debug(f"Failed to warmup sector data: {e}")
        
        except Exception as e:
            logger.error(f"Error in warmup for {data_type.value}: {e}")
        
        return items_warmed
    
    async def _get_popular_stocks(self) -> List[str]:
        """Get list of popular stocks for warmup."""
        try:
            # Try to get from cache first
            popular_stocks = await self.cache_manager.get("popular_stocks_list")
            if popular_stocks:
                return popular_stocks
            
            # Default popular stocks (major indices components)
            default_popular = [
                '000001.SZ', '000002.SZ', '000858.SZ', '002415.SZ',
                '600000.SH', '600036.SH', '600519.SH', '600887.SH',
                '000858.SZ', '002594.SZ', '300059.SZ', '300750.SZ'
            ]
            
            # Cache the list
            await self.cache_manager.set(
                "popular_stocks_list",
                default_popular,
                ttl=3600  # 1 hour
            )
            
            return default_popular
            
        except Exception as e:
            logger.error(f"Error getting popular stocks: {e}")
            return []
    
    async def force_warmup(self, data_types: Optional[List[DataType]] = None):
        """Force immediate cache warmup for specific data types."""
        if data_types is None:
            data_types = list(DataType)
        
        logger.info(f"Forcing warmup for data types: {[dt.value for dt in data_types]}")
        
        items_warmed = 0
        for data_type in data_types:
            try:
                warmed_count = await self._warmup_data_type(data_type)
                items_warmed += warmed_count
            except Exception as e:
                logger.error(f"Error in forced warmup for {data_type.value}: {e}")
        
        logger.info(f"Forced warmup completed, warmed {items_warmed} items")
        return items_warmed
    
    def get_warmup_stats(self) -> Dict[str, Any]:
        """Get warmup statistics."""
        return {
            'enabled': self.warmup_enabled,
            'is_running': self._is_running,
            'interval_seconds': self.warmup_interval,
            'last_warmup_timestamp': self._last_warmup,
            'stats': self._warmup_stats.copy(),
            'next_warmup_in_seconds': max(0, self.warmup_interval - (time.time() - self._last_warmup))
        }
    
    def configure_warmup(self, enabled: bool = None, interval: int = None):
        """Configure warmup settings."""
        if enabled is not None:
            self.warmup_enabled = enabled
            logger.info(f"Cache warmup {'enabled' if enabled else 'disabled'}")
        
        if interval is not None:
            self.warmup_interval = interval
            logger.info(f"Cache warmup interval set to {interval} seconds")


# Global warmup service instance
warmup_service = None


def get_warmup_service(cache_manager=None, data_service=None):
    """Get global warmup service instance."""
    global warmup_service
    if warmup_service is None and cache_manager is not None and data_service is not None:
        warmup_service = CacheWarmupService(cache_manager, data_service)
    return warmup_service