"""
Data loaders for cache preloader.

This module contains specific data loading functions for different data types
used by the cache preloader system.
"""

import time
import asyncio
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DataLoaders:
    """Collection of data loading functions for cache preloading."""
    
    def __init__(self, cache_manager, data_service_client):
        """Initialize data loaders.
        
        Args:
            cache_manager: Cache manager instance
            data_service_client: Data service client for loading data
        """
        self.cache_manager = cache_manager
        self.data_service_client = data_service_client
        
        # Import cache_config here to avoid circular imports
        try:
            from ..cache_config import cache_config
            self.cache_config = cache_config
        except ImportError:
            logger.warning("Could not import cache_config, using defaults")
            self.cache_config = None
    
    def _get_ttl(self, data_type: str) -> int:
        """Get TTL for data type."""
        if self.cache_config:
            return self.cache_config.calculate_ttl(data_type)
        
        # Default TTLs
        defaults = {
            'trading_dates': 86400,  # 24 hours
            'stock_list': 1800,      # 30 minutes
            'market_status': 60,     # 1 minute
            'instrument_detail': 3600 # 1 hour
        }
        return defaults.get(data_type, 3600)
    
    def load_trading_dates(self, data_type: str) -> List[Dict[str, Any]]:
        """Load trading dates data.
        
        Args:
            data_type: Data type identifier
            
        Returns:
            List of cache items to store
        """
        try:
            logger.debug("Loading trading dates data")
            
            # In a real implementation, this would call the actual data service
            # For now, return mock data that represents typical trading dates
            current_year = time.strftime("%Y")
            
            # Generate some sample trading dates
            trading_dates = []
            base_date = f"{current_year}-01-01"
            
            # This would typically come from the data service
            sample_dates = [
                f"{current_year}-01-02", f"{current_year}-01-03", 
                f"{current_year}-01-04", f"{current_year}-01-05",
                f"{current_year}-01-08", f"{current_year}-01-09"
            ]
            
            result = [
                {
                    'key': f'trading_dates:{current_year}',
                    'data': sample_dates,
                    'ttl': self._get_ttl('trading_dates')
                }
            ]
            
            # Cache the data
            for item in result:
                asyncio.create_task(self.cache_manager.set(
                    item['key'], item['data'], item['ttl'], 'trading_dates'
                ))
            
            logger.debug(f"Loaded {len(sample_dates)} trading dates")
            return result
            
        except Exception as e:
            logger.error(f"Error loading trading dates: {e}")
            return []
    
    def load_stock_list(self, data_type: str) -> List[Dict[str, Any]]:
        """Load stock list data.
        
        Args:
            data_type: Data type identifier
            
        Returns:
            List of cache items to store
        """
        try:
            logger.debug("Loading stock list data")
            
            # Mock stock list data
            stock_data = [
                {'code': '000001', 'name': '平安银行', 'market': 'SZ'},
                {'code': '000002', 'name': '万科A', 'market': 'SZ'},
                {'code': '600000', 'name': '浦发银行', 'market': 'SH'},
                {'code': '600036', 'name': '招商银行', 'market': 'SH'},
                {'code': '000858', 'name': '五粮液', 'market': 'SZ'},
                {'code': '600519', 'name': '贵州茅台', 'market': 'SH'}
            ]
            
            result = [
                {
                    'key': 'stock_list:all',
                    'data': stock_data,
                    'ttl': self._get_ttl('stock_list')
                }
            ]
            
            # Also create market-specific lists
            sz_stocks = [s for s in stock_data if s['market'] == 'SZ']
            sh_stocks = [s for s in stock_data if s['market'] == 'SH']
            
            result.extend([
                {
                    'key': 'stock_list:SZ',
                    'data': sz_stocks,
                    'ttl': self._get_ttl('stock_list')
                },
                {
                    'key': 'stock_list:SH',
                    'data': sh_stocks,
                    'ttl': self._get_ttl('stock_list')
                }
            ])
            
            # Cache the data
            for item in result:
                asyncio.create_task(self.cache_manager.set(
                    item['key'], item['data'], item['ttl'], 'stock_list'
                ))
            
            logger.debug(f"Loaded {len(stock_data)} stocks")
            return result
            
        except Exception as e:
            logger.error(f"Error loading stock list: {e}")
            return []
    
    def load_market_status(self, data_type: str) -> List[Dict[str, Any]]:
        """Load market status data.
        
        Args:
            data_type: Data type identifier
            
        Returns:
            List of cache items to store
        """
        try:
            logger.debug("Loading market status data")
            
            current_time = time.time()
            current_hour = int(time.strftime("%H"))
            
            # Determine market status based on time
            # Simplified logic: market open 9:30-15:00 on weekdays
            is_weekday = time.strftime("%w") not in ['0', '6']  # 0=Sunday, 6=Saturday
            is_trading_hours = 9 <= current_hour < 15
            
            status = "open" if (is_weekday and is_trading_hours) else "closed"
            
            market_data = {
                'status': status,
                'timestamp': current_time,
                'trading_day': time.strftime("%Y-%m-%d"),
                'session': 'morning' if current_hour < 12 else 'afternoon'
            }
            
            result = [
                {
                    'key': 'market_status:current',
                    'data': market_data,
                    'ttl': self._get_ttl('market_status')
                }
            ]
            
            # Cache the data
            for item in result:
                asyncio.create_task(self.cache_manager.set(
                    item['key'], item['data'], item['ttl'], 'market_status'
                ))
            
            logger.debug(f"Loaded market status: {status}")
            return result
            
        except Exception as e:
            logger.error(f"Error loading market status: {e}")
            return []
    
    def load_popular_instruments(self, data_type: str) -> List[Dict[str, Any]]:
        """Load popular instrument details.
        
        Args:
            data_type: Data type identifier
            
        Returns:
            List of cache items to store
        """
        try:
            logger.debug("Loading popular instruments data")
            
            # Mock popular instrument codes (would come from analytics)
            popular_codes = [
                '000001', '000002', '600000', '600036', 
                '000858', '600519', '002415', '000166'
            ]
            
            result = []
            
            for code in popular_codes:
                # Mock instrument detail data
                instrument_data = {
                    'code': code,
                    'name': f'Stock {code}',
                    'market': 'SZ' if code.startswith('000') or code.startswith('002') else 'SH',
                    'sector': 'Finance' if code in ['000001', '600000', '600036'] else 'Consumer',
                    'listing_date': '2000-01-01',
                    'total_shares': 1000000000,
                    'float_shares': 800000000,
                    'market_cap': 50000000000
                }
                
                key = f'instrument:{code}'
                
                result.append({
                    'key': key,
                    'data': instrument_data,
                    'ttl': self._get_ttl('instrument_detail')
                })
                
                # Cache the data
                asyncio.create_task(self.cache_manager.set(
                    key, instrument_data, 
                    self._get_ttl('instrument_detail'), 
                    'instrument_detail'
                ))
            
            logger.debug(f"Loaded {len(popular_codes)} popular instruments")
            return result
            
        except Exception as e:
            logger.error(f"Error loading popular instruments: {e}")
            return []
    
    def load_sector_data(self, data_type: str) -> List[Dict[str, Any]]:
        """Load sector/industry data.
        
        Args:
            data_type: Data type identifier
            
        Returns:
            List of cache items to store
        """
        try:
            logger.debug("Loading sector data")
            
            # Mock sector data
            sectors = [
                {
                    'code': 'finance',
                    'name': '金融',
                    'stocks': ['000001', '600000', '600036'],
                    'market_cap': 5000000000000,
                    'pe_ratio': 6.5
                },
                {
                    'code': 'consumer',
                    'name': '消费',
                    'stocks': ['000858', '600519'],
                    'market_cap': 3000000000000,
                    'pe_ratio': 25.8
                },
                {
                    'code': 'technology',
                    'name': '科技',
                    'stocks': ['002415', '000166'],
                    'market_cap': 2000000000000,
                    'pe_ratio': 35.2
                }
            ]
            
            result = []
            
            # Cache overall sector list
            result.append({
                'key': 'sectors:all',
                'data': sectors,
                'ttl': self._get_ttl('stock_list')
            })
            
            # Cache individual sector data
            for sector in sectors:
                key = f'sector:{sector["code"]}'
                result.append({
                    'key': key,
                    'data': sector,
                    'ttl': self._get_ttl('stock_list')
                })
            
            # Cache the data
            for item in result:
                asyncio.create_task(self.cache_manager.set(
                    item['key'], item['data'], item['ttl'], 'stock_list'
                ))
            
            logger.debug(f"Loaded {len(sectors)} sectors")
            return result
            
        except Exception as e:
            logger.error(f"Error loading sector data: {e}")
            return []
    
    def load_market_indices(self, data_type: str) -> List[Dict[str, Any]]:
        """Load market indices data.
        
        Args:
            data_type: Data type identifier
            
        Returns:
            List of cache items to store
        """
        try:
            logger.debug("Loading market indices data")
            
            current_time = time.time()
            
            # Mock index data
            indices = [
                {
                    'code': '000001',
                    'name': '上证指数',
                    'value': 3200.50,
                    'change': 15.30,
                    'change_pct': 0.48,
                    'volume': 250000000000,
                    'timestamp': current_time
                },
                {
                    'code': '399001',
                    'name': '深证成指',
                    'value': 11500.80,
                    'change': -25.60,
                    'change_pct': -0.22,
                    'volume': 180000000000,
                    'timestamp': current_time
                },
                {
                    'code': '399006',
                    'name': '创业板指',
                    'value': 2450.30,
                    'change': 8.90,
                    'change_pct': 0.36,
                    'volume': 120000000000,
                    'timestamp': current_time
                }
            ]
            
            result = []
            
            # Cache overall indices list
            result.append({
                'key': 'indices:all',
                'data': indices,
                'ttl': self._get_ttl('market_status')
            })
            
            # Cache individual index data
            for index in indices:
                key = f'index:{index["code"]}'
                result.append({
                    'key': key,
                    'data': index,
                    'ttl': self._get_ttl('market_status')
                })
            
            # Cache the data
            for item in result:
                asyncio.create_task(self.cache_manager.set(
                    item['key'], item['data'], item['ttl'], 'market_status'
                ))
            
            logger.debug(f"Loaded {len(indices)} market indices")
            return result
            
        except Exception as e:
            logger.error(f"Error loading market indices: {e}")
            return []
    
    def get_loader_function(self, data_type: str):
        """Get the appropriate loader function for a data type.
        
        Args:
            data_type: Data type to load
            
        Returns:
            Loader function or None if not found
        """
        loaders = {
            'trading_dates': self.load_trading_dates,
            'stock_list': self.load_stock_list,
            'market_status': self.load_market_status,
            'instrument_detail': self.load_popular_instruments,
            'sector_data': self.load_sector_data,
            'market_indices': self.load_market_indices
        }
        
        return loaders.get(data_type)
    
    def get_available_data_types(self) -> List[str]:
        """Get list of available data types that can be preloaded.
        
        Returns:
            List of data type names
        """
        return [
            'trading_dates',
            'stock_list', 
            'market_status',
            'instrument_detail',
            'sector_data',
            'market_indices'
        ]