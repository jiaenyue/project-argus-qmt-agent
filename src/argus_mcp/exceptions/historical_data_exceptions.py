"""
历史数据异常处理模块

定义历史数据系统的自定义异常类和错误处理机制
"""

from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
import logging
import traceback
import asyncio
from functools import wraps
import time


class ErrorCategory(Enum):
    """错误分类枚举"""
    DATASOURCE_ERROR = "datasource_error"      # 数据源错误
    VALIDATION_ERROR = "validation_error"      # 数据验证错误
    CACHE_ERROR = "cache_error"               # 缓存错误
    NETWORK_ERROR = "network_error"           # 网络错误
    TIMEOUT_ERROR = "timeout_error"           # 超时错误
    RATE_LIMIT_ERROR = "rate_limit_error"     # 限流错误
    AUTH_ERROR = "auth_error"                 # 认证错误
    UNKNOWN_ERROR = "unknown_error"           # 未知错误


class HistoricalDataException(Exception):
    """历史数据系统基础异常类"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR,
        symbol: Optional[str] = None,
        period: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.symbol = symbol
        self.period = period
        self.details = details or {}
        self.timestamp = timestamp or datetime.now()
        self.traceback = traceback.format_exc()


class DataSourceError(HistoricalDataException):
    """数据源错误"""
    
    def __init__(self, message: str, symbol: str, period: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.DATASOURCE_ERROR,
            symbol=symbol,
            period=period,
            **kwargs
        )


class DataValidationError(HistoricalDataException):
    """数据验证错误"""
    
    def __init__(self, message: str, symbol: str, period: str, validation_errors: list, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION_ERROR,
            symbol=symbol,
            period=period,
            details={"validation_errors": validation_errors},
            **kwargs
        )


class CacheOperationError(HistoricalDataException):
    """缓存操作错误"""
    
    def __init__(self, message: str, operation: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CACHE_ERROR,
            details={"operation": operation},
            **kwargs
        )


class NetworkTimeoutError(HistoricalDataException):
    """网络超时错误"""
    
    def __init__(self, message: str, timeout: float, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT_ERROR,
            details={"timeout": timeout},
            **kwargs
        )


class RateLimitError(HistoricalDataException):
    """限流错误"""
    
    def __init__(self, message: str, retry_after: Optional[float] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RATE_LIMIT_ERROR,
            details={"retry_after": retry_after},
            **kwargs
        )


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_stats = {
            "total_errors": 0,
            "errors_by_category": {},
            "errors_by_symbol": {}
        }
    
    def handle_error(self, error: HistoricalDataException) -> None:
        """处理异常"""
        self.error_stats["total_errors"] += 1
        
        # 按分类统计
        category = error.category.value
        if category not in self.error_stats["errors_by_category"]:
            self.error_stats["errors_by_category"][category] = 0
        self.error_stats["errors_by_category"][category] += 1
        
        # 按股票代码统计
        if error.symbol:
            symbol = error.symbol
            if symbol not in self.error_stats["errors_by_symbol"]:
                self.error_stats["errors_by_symbol"][symbol] = 0
            self.error_stats["errors_by_symbol"][symbol] += 1
        
        # 记录日志
        self.logger.error(
            f"[{error.category.value}] {error.message} "
            f"Symbol: {error.symbol}, Period: {error.period}, "
            f"Details: {error.details}"
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return self.error_stats.copy()


class RetryConfig:
    """重试配置"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        exponential_base: float = 2.0
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.exponential_base = exponential_base


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)
    
    def should_retry(self, error: HistoricalDataException, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= self.config.max_attempts:
            return False
        
        # 可重试的错误类型
        retryable_categories = [
            ErrorCategory.DATASOURCE_ERROR,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.TIMEOUT_ERROR,
            ErrorCategory.RATE_LIMIT_ERROR
        ]
        
        return error.category in retryable_categories
    
    def calculate_delay(self, attempt: int, error: HistoricalDataException) -> float:
        """计算重试延迟"""
        if error.category == ErrorCategory.RATE_LIMIT_ERROR:
            # 限流错误使用指定的重试时间
            retry_after = error.details.get("retry_after")
            if retry_after:
                return min(retry_after, self.config.max_delay)
        
        # 指数退避策略
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        return min(delay, self.config.max_delay)


def retry_with_backoff(config: Optional[RetryConfig] = None):
    """重试装饰器"""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            retry_handler = RetryHandler(config)
            last_error = None
            
            for attempt in range(retry_handler.config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except HistoricalDataException as e:
                    last_error = e
                    
                    if not retry_handler.should_retry(e, attempt):
                        raise e
                    
                    delay = retry_handler.calculate_delay(attempt, e)
                    retry_handler.logger.warning(
                        f"Retry attempt {attempt + 1} for {func.__name__} "
                        f"after {delay:.2f}s delay due to: {e.message}"
                    )
                    
                    await asyncio.sleep(delay)
                except Exception as e:
                    # 非HistoricalDataException不处理重试
                    raise e
            
            raise last_error
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            retry_handler = RetryHandler(config)
            last_error = None
            
            for attempt in range(retry_handler.config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except HistoricalDataException as e:
                    last_error = e
                    
                    if not retry_handler.should_retry(e, attempt):
                        raise e
                    
                    delay = retry_handler.calculate_delay(attempt, e)
                    retry_handler.logger.warning(
                        f"Retry attempt {attempt + 1} for {func.__name__} "
                        f"after {delay:.2f}s delay due to: {e.message}"
                    )
                    
                    time.sleep(delay)
                except Exception as e:
                    raise e
            
            raise last_error
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = HistoricalDataException
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call_succeeded(self):
        """调用成功"""
        self.failure_count = 0
        self.state = "closed"
    
    def call_failed(self):
        """调用失败"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if self.last_failure_time:
                time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
                if time_since_failure >= self.recovery_timeout:
                    self.state = "half-open"
                    return True
            return False
        
        return True  # half-open state


def circuit_breaker_handler(circuit_breaker: CircuitBreaker):
    """熔断器装饰器"""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not circuit_breaker.can_execute():
                raise HistoricalDataException(
                    f"Circuit breaker is {circuit_breaker.state}",
                    category=ErrorCategory.UNKNOWN_ERROR
                )
            
            try:
                result = await func(*args, **kwargs)
                circuit_breaker.call_succeeded()
                return result
            except circuit_breaker.expected_exception as e:
                circuit_breaker.call_failed()
                raise e
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not circuit_breaker.can_execute():
                raise HistoricalDataException(
                    f"Circuit breaker is {circuit_breaker.state}",
                    category=ErrorCategory.UNKNOWN_ERROR
                )
            
            try:
                result = func(*args, **kwargs)
                circuit_breaker.call_succeeded()
                return result
            except circuit_breaker.expected_exception as e:
                circuit_breaker.call_failed()
                raise e
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator