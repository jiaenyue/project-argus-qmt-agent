"""Argus MCP Server - Decorators.

This module provides decorators for caching, retry logic,
performance monitoring, and other cross-cutting concerns.
"""

import time
import random
import asyncio
from functools import wraps
from typing import Callable, Optional, Any, Union, Tuple
import logging

from .cache_manager import CacheManager
from .performance_monitor import PerformanceMonitor, get_global_monitor

# Setup logging
logger = logging.getLogger(__name__)


def with_cache(
    cache_manager: Optional[CacheManager] = None,
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None
):
    """Decorator for caching function results.
    
    Args:
        cache_manager: Cache manager instance (uses global if None)
        ttl: Time to live for cached results
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Get cache manager
                cache = cache_manager
                if cache is None:
                    # Try to get from global context or skip caching
                    if hasattr(async_wrapper, '_cache_manager'):
                        cache = async_wrapper._cache_manager
                    else:
                        logger.warning(f"No cache manager available for {func.__name__}")
                        return await func(*args, **kwargs)
                
                # Create cache key
                prefix = key_prefix or func.__name__
                cache_key = f"{prefix}_{cache.create_key(*args, **kwargs)}"
                
                # Try to get from cache
                try:
                    cached_result = await cache.get(cache_key)
                    if cached_result is not None:
                        logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                        return cached_result
                except Exception as e:
                    logger.warning(f"Cache get error for {func.__name__}: {e}")
                
                # Execute function and cache result
                try:
                    result = await func(*args, **kwargs)
                    await cache.set(cache_key, result, ttl)
                    logger.debug(f"Cached result for {func.__name__}: {cache_key}")
                    return result
                except Exception as e:
                    logger.error(f"Function execution error for {func.__name__}: {e}")
                    raise
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, just call directly without caching for now
                logger.warning(f"Sync function {func.__name__} called with async cache decorator")
                return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for adding retry logic to functions.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff_factor: Multiplier for delay after each attempt
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to retry on
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exception = None
                current_delay = delay
                
                for attempt in range(max_attempts):
                    try:
                        result = await func(*args, **kwargs)
                        if attempt > 0:
                            logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                        return result
                    
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt == max_attempts - 1:
                            logger.error(
                                f"{func.__name__} failed after {max_attempts} attempts: {e}"
                            )
                            break
                        
                        # Add jitter to delay
                        jittered_delay = current_delay * (0.5 + random.random() * 0.5)
                        
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {jittered_delay:.2f}s"
                        )
                        
                        await asyncio.sleep(jittered_delay)
                        current_delay = min(current_delay * backoff_factor, max_delay)
                    
                    except Exception as e:
                        # Don't retry on unexpected exceptions
                        logger.error(f"{func.__name__} failed with unexpected error: {e}")
                        raise
                
                # Re-raise the last exception if all attempts failed
                if last_exception:
                    raise last_exception
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                last_exception = None
                current_delay = delay
                
                for attempt in range(max_attempts):
                    try:
                        result = func(*args, **kwargs)
                        if attempt > 0:
                            logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                        return result
                    
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt == max_attempts - 1:
                            logger.error(
                                f"{func.__name__} failed after {max_attempts} attempts: {e}"
                            )
                            break
                        
                        # Add jitter to delay
                        jittered_delay = current_delay * (0.5 + random.random() * 0.5)
                        
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {jittered_delay:.2f}s"
                        )
                        
                        import time
                        time.sleep(jittered_delay)
                        current_delay = min(current_delay * backoff_factor, max_delay)
                    
                    except Exception as e:
                        # Don't retry on unexpected exceptions
                        logger.error(f"{func.__name__} failed with unexpected error: {e}")
                        raise
                
                # Re-raise the last exception if all attempts failed
                if last_exception:
                    raise last_exception
            
            return sync_wrapper
    
    return decorator


def with_performance_monitoring(
    operation_name: Optional[str] = None,
    monitor: Optional[PerformanceMonitor] = None
):
    """Decorator for monitoring function performance.
    
    Args:
        operation_name: Name for the operation (defaults to function name)
        monitor: Performance monitor instance (uses global if None)
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Get monitor
                perf_monitor = monitor or get_global_monitor()
                
                start_time = time.time()
                success = True
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start_time
                    
                    if perf_monitor:
                        perf_monitor.record_operation(op_name, duration, success)
                        perf_monitor.record_metric(f"{op_name}_duration", duration)
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Get monitor
                perf_monitor = monitor or get_global_monitor()
                
                start_time = time.time()
                success = True
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start_time
                    
                    if perf_monitor:
                        perf_monitor.record_operation(op_name, duration, success)
                        perf_monitor.record_metric(f"{op_name}_duration", duration)
            
            return sync_wrapper
    
    return decorator


def with_timeout(timeout_seconds: float):
    """Decorator for adding timeout to async functions.
    
    Args:
        timeout_seconds: Timeout in seconds
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    logger.error(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
                    raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we can't easily implement timeout without threading
                # Just log a warning and call the function directly
                logger.warning(f"Timeout decorator applied to sync function {func.__name__}, timeout ignored")
                return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def with_rate_limit(
    max_calls: int,
    time_window: float,
    key_func: Optional[Callable] = None
):
    """Decorator for rate limiting function calls.
    
    Args:
        max_calls: Maximum number of calls allowed
        time_window: Time window in seconds
        key_func: Function to generate rate limit key from args
    """
    call_history = {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                rate_key = key_func(*args, **kwargs)
            else:
                rate_key = "global"
            
            current_time = time.time()
            
            # Clean old entries
            if rate_key in call_history:
                call_history[rate_key] = [
                    call_time for call_time in call_history[rate_key]
                    if current_time - call_time < time_window
                ]
            else:
                call_history[rate_key] = []
            
            # Check rate limit
            if len(call_history[rate_key]) >= max_calls:
                logger.warning(
                    f"Rate limit exceeded for {func.__name__} (key: {rate_key})"
                )
                raise Exception(f"Rate limit exceeded: {max_calls} calls per {time_window}s")
            
            # Record call and execute
            call_history[rate_key].append(current_time)
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception
):
    """Decorator implementing circuit breaker pattern.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time to wait before trying to close circuit
        expected_exception: Exception type that triggers circuit breaker
    """
    def decorator(func: Callable) -> Callable:
        state = {
            'failure_count': 0,
            'last_failure_time': None,
            'state': 'closed'  # closed, open, half-open
        }
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_time = time.time()
            
            # Check if circuit should be half-open
            if (state['state'] == 'open' and 
                state['last_failure_time'] and
                current_time - state['last_failure_time'] > recovery_timeout):
                state['state'] = 'half-open'
                logger.info(f"Circuit breaker for {func.__name__} is now half-open")
            
            # Reject calls if circuit is open
            if state['state'] == 'open':
                logger.warning(f"Circuit breaker for {func.__name__} is open")
                raise Exception(f"Circuit breaker is open for {func.__name__}")
            
            try:
                result = await func(*args, **kwargs)
                
                # Reset on success
                if state['failure_count'] > 0:
                    logger.info(f"Circuit breaker for {func.__name__} reset after success")
                    state['failure_count'] = 0
                    state['state'] = 'closed'
                
                return result
            
            except expected_exception as e:
                state['failure_count'] += 1
                state['last_failure_time'] = current_time
                
                if state['failure_count'] >= failure_threshold:
                    state['state'] = 'open'
                    logger.error(
                        f"Circuit breaker for {func.__name__} opened after "
                        f"{failure_threshold} failures"
                    )
                
                raise
        
        return wrapper
    
    return decorator


def with_logging(
    level: int = logging.INFO,
    include_args: bool = False,
    include_result: bool = False
):
    """Decorator for adding logging to functions.
    
    Args:
        level: Logging level
        include_args: Whether to log function arguments
        include_result: Whether to log function result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            func_logger = logging.getLogger(func.__module__)
            
            # Log function entry
            if include_args:
                func_logger.log(level, f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            else:
                func_logger.log(level, f"Calling {func.__name__}")
            
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log success
                if include_result:
                    func_logger.log(
                        level, 
                        f"{func.__name__} completed in {duration:.3f}s with result: {result}"
                    )
                else:
                    func_logger.log(level, f"{func.__name__} completed in {duration:.3f}s")
                
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                func_logger.error(
                    f"{func.__name__} failed after {duration:.3f}s with error: {e}"
                )
                raise
        
        return wrapper
    
    return decorator


# Convenience function for combining multiple decorators
def with_all_optimizations(
    cache_manager: Optional[CacheManager] = None,
    cache_ttl: Optional[int] = None,
    max_retries: int = 3,
    timeout: Optional[float] = None,
    monitor: Optional[PerformanceMonitor] = None
):
    """Decorator that applies all common optimizations.
    
    Args:
        cache_manager: Cache manager for caching
        cache_ttl: Cache TTL in seconds
        max_retries: Maximum retry attempts
        timeout: Timeout in seconds
        monitor: Performance monitor
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in reverse order (innermost first)
        decorated_func = func
        
        # Performance monitoring (innermost)
        decorated_func = with_performance_monitoring(monitor=monitor)(decorated_func)
        
        # Retry logic
        if max_retries > 1:
            decorated_func = with_retry(max_attempts=max_retries)(decorated_func)
        
        # Timeout
        if timeout:
            decorated_func = with_timeout(timeout)(decorated_func)
        
        # Caching (outermost)
        if cache_manager:
            decorated_func = with_cache(
                cache_manager=cache_manager, 
                ttl=cache_ttl
            )(decorated_func)
        
        return decorated_func
    
    return decorator