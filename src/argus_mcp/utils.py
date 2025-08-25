"""Argus MCP Server - Utility functions.

This module provides utility functions for error handling,
retry mechanisms, and data formatting.
"""

import asyncio
import json
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union

# Setup logging
logger = logging.getLogger(__name__)

# Type variable for generic functions
T = TypeVar('T')


def format_error_response(error: Exception, context: str = "") -> Dict[str, Any]:
    """Format error response for MCP protocol."""
    error_msg = str(error)
    if context:
        error_msg = f"{context}: {error_msg}"
    
    return {
        "error": {
            "code": -32603,  # Internal error
            "message": error_msg,
            "data": {
                "type": type(error).__name__,
                "timestamp": time.time()
            }
        }
    }


def format_success_response(data: Any, metadata: Optional[Dict] = None) -> Dict[str, Any]:
    """Format success response for MCP protocol."""
    response = {
        "result": data,
        "timestamp": time.time()
    }
    
    if metadata:
        response["metadata"] = metadata
    
    return response


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0
) -> Any:
    """Retry function with exponential backoff."""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        except Exception as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded. Last error: {e}")
                raise e
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
            
            await asyncio.sleep(delay)
    
    # This should never be reached, but just in case
    if last_exception:
        raise last_exception


def validate_stock_code(code: str) -> bool:
    """Validate stock code format."""
    if not code or not isinstance(code, str):
        return False
    
    # Remove any whitespace
    code = code.strip()
    
    # Basic validation - should be 6 digits for Chinese stocks
    if len(code) == 6 and code.isdigit():
        return True
    
    # Allow codes with market suffix (e.g., "000001.SZ")
    if '.' in code:
        parts = code.split('.')
        if len(parts) == 2 and len(parts[0]) == 6 and parts[0].isdigit():
            return parts[1].upper() in ['SZ', 'SH', 'BJ']
    
    return False


def validate_date_format(date_str: str) -> bool:
    """Validate date format (YYYY-MM-DD or YYYYMMDD)."""
    if not date_str or not isinstance(date_str, str):
        return False
    
    # Remove any whitespace
    date_str = date_str.strip()
    
    # Check YYYY-MM-DD format
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        try:
            year = int(date_str[:4])
            month = int(date_str[5:7])
            day = int(date_str[8:10])
            return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
        except ValueError:
            return False
    
    # Check YYYYMMDD format
    if len(date_str) == 8 and date_str.isdigit():
        try:
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
        except ValueError:
            return False
    
    return False


def normalize_stock_codes(codes: Union[str, list]) -> list:
    """Normalize stock codes to a consistent format."""
    if isinstance(codes, str):
        codes = [codes]
    
    normalized = []
    for code in codes:
        if isinstance(code, str):
            code = code.strip().upper()
            if validate_stock_code(code):
                normalized.append(code)
            else:
                logger.warning(f"Invalid stock code format: {code}")
    
    return normalized


def sanitize_fields(fields: Union[str, list]) -> list:
    """Sanitize and validate field names."""
    if isinstance(fields, str):
        fields = [fields]
    
    # Common valid fields for market data
    valid_fields = {
        'open', 'high', 'low', 'close', 'volume', 'amount',
        'turnover', 'pctChg', 'preClose', 'adjClose',
        'vwap', 'bid1', 'ask1', 'bid1Size', 'ask1Size',
        'timestamp', 'date', 'time'
    }
    
    sanitized = []
    for field in fields:
        if isinstance(field, str):
            field = field.strip()
            if field in valid_fields or field.startswith('bid') or field.startswith('ask'):
                sanitized.append(field)
            else:
                logger.warning(f"Unknown field: {field}")
    
    return sanitized if sanitized else ['close']  # Default to 'close' if no valid fields


def calculate_cache_ttl(data_type: str, data_size: int = 0, access_frequency: float = 1.0) -> int:
    """Calculate cache TTL based on data type, size, and access patterns.
    
    This function now uses the optimized cache configuration for better performance.
    
    Args:
        data_type: Type of data being cached
        data_size: Size of data in bytes
        access_frequency: Access frequency (requests per minute)
        
    Returns:
        TTL in seconds
    """
    from .cache_config import cache_config
    return cache_config.calculate_ttl(data_type, data_size, access_frequency)


def performance_monitor(func: Callable) -> Callable:
    """Decorator to monitor function performance."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int = 100, time_window: int = 60):
        """Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def acquire(self) -> bool:
        """Acquire permission to make a call."""
        now = time.time()
        
        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        # Check if we can make a new call
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        
        return False
    
    def get_wait_time(self) -> float:
        """Get time to wait before next call is allowed."""
        if not self.calls:
            return 0.0
        
        oldest_call = min(self.calls)
        return max(0.0, self.time_window - (time.time() - oldest_call))


def format_market_data(data: Dict[str, Any], format_type: str = "standard") -> Dict[str, Any]:
    """Format market data for consistent output."""
    if not isinstance(data, dict):
        return data
    
    if format_type == "standard":
        # Ensure consistent field names and types
        formatted = {}
        for key, value in data.items():
            # Normalize field names
            normalized_key = key.lower().replace('_', '').replace('-', '')
            
            # Convert numeric strings to numbers where appropriate
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                try:
                    formatted[key] = float(value) if '.' in value else int(value)
                except ValueError:
                    formatted[key] = value
            else:
                formatted[key] = value
        
        return formatted
    
    return data


def create_tool_metadata(tool_name: str, execution_time: float, cache_hit: bool = False) -> Dict[str, Any]:
    """Create metadata for tool execution."""
    return {
        "tool_name": tool_name,
        "execution_time": round(execution_time, 3),
        "cache_hit": cache_hit,
        "timestamp": time.time()
    }