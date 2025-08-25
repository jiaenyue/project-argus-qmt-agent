#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据获取重试机制模块
提供智能重试策略、失败恢复和错误分类功能
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError


class RetryErrorType(Enum):
    """重试错误类型"""
    NETWORK_ERROR = "network_error"          # 网络错误
    TIMEOUT_ERROR = "timeout_error"          # 超时错误
    CONNECTION_ERROR = "connection_error"    # 连接错误
    DATA_ERROR = "data_error"                # 数据错误
    RATE_LIMIT_ERROR = "rate_limit_error"    # 限流错误
    SERVER_ERROR = "server_error"            # 服务器错误
    AUTHENTICATION_ERROR = "auth_error"      # 认证错误
    UNKNOWN_ERROR = "unknown_error"          # 未知错误


class RetryStrategy(Enum):
    """重试策略"""
    FIXED_DELAY = "fixed_delay"              # 固定延迟
    EXPONENTIAL_BACKOFF = "exponential"      # 指数退避
    LINEAR_BACKOFF = "linear"                # 线性退避
    JITTERED_EXPONENTIAL = "jittered_exp"    # 带抖动的指数退避


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3                    # 最大重试次数
    base_delay: float = 1.0                  # 基础延迟时间(秒)
    max_delay: float = 60.0                  # 最大延迟时间(秒)
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0          # 退避倍数
    jitter: bool = True                      # 是否添加抖动
    timeout: Optional[float] = 30.0          # 单次请求超时时间
    retryable_errors: List[RetryErrorType] = field(default_factory=lambda: [
        RetryErrorType.NETWORK_ERROR,
        RetryErrorType.TIMEOUT_ERROR,
        RetryErrorType.CONNECTION_ERROR,
        RetryErrorType.RATE_LIMIT_ERROR,
        RetryErrorType.SERVER_ERROR
    ])


@dataclass
class RetryAttempt:
    """重试尝试记录"""
    attempt_number: int
    timestamp: datetime
    error_type: RetryErrorType
    error_message: str
    delay_before_retry: float
    success: bool = False
    response_time: Optional[float] = None


@dataclass
class RetryResult:
    """重试结果"""
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    total_attempts: int = 0
    total_time: float = 0.0
    attempts: List[RetryAttempt] = field(default_factory=list)
    
    @property
    def final_error_type(self) -> Optional[RetryErrorType]:
        """获取最终错误类型"""
        if self.attempts:
            return self.attempts[-1].error_type
        return None


class RetryableError(Exception):
    """可重试的错误基类"""
    
    def __init__(self, message: str, error_type: RetryErrorType, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.error_type = error_type
        self.original_error = original_error


class NetworkRetryableError(RetryableError):
    """网络相关的可重试错误"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, RetryErrorType.NETWORK_ERROR, original_error)


class TimeoutRetryableError(RetryableError):
    """超时相关的可重试错误"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, RetryErrorType.TIMEOUT_ERROR, original_error)


class ConnectionRetryableError(RetryableError):
    """连接相关的可重试错误"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, RetryErrorType.CONNECTION_ERROR, original_error)


class RateLimitRetryableError(RetryableError):
    """限流相关的可重试错误"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, RetryErrorType.RATE_LIMIT_ERROR, original_error)


class ErrorClassifier:
    """错误分类器"""
    
    @staticmethod
    def classify_error(error: Exception) -> RetryErrorType:
        """分类错误类型"""
        error_str = str(error).lower()
        error_type_name = type(error).__name__.lower()
        
        # 检查是否是已知的可重试错误
        if isinstance(error, RetryableError):
            return error.error_type
        
        # 网络错误
        if any(keyword in error_str for keyword in [
            'network', 'connection refused', 'connection reset', 'connection timeout',
            'dns', 'host unreachable', 'no route to host'
        ]) or 'connectionerror' in error_type_name:
            return RetryErrorType.NETWORK_ERROR
        
        # 超时错误
        if any(keyword in error_str for keyword in [
            'timeout', 'timed out', 'read timeout', 'connect timeout'
        ]) or 'timeout' in error_type_name:
            return RetryErrorType.TIMEOUT_ERROR
        
        # 连接错误
        if any(keyword in error_str for keyword in [
            'connection', 'connect failed', 'socket error', 'broken pipe'
        ]):
            return RetryErrorType.CONNECTION_ERROR
        
        # 限流错误
        if any(keyword in error_str for keyword in [
            'rate limit', 'too many requests', '429', 'quota exceeded'
        ]):
            return RetryErrorType.RATE_LIMIT_ERROR
        
        # 服务器错误
        if any(keyword in error_str for keyword in [
            '500', '502', '503', '504', 'internal server error', 'bad gateway',
            'service unavailable', 'gateway timeout'
        ]):
            return RetryErrorType.SERVER_ERROR
        
        # 认证错误
        if any(keyword in error_str for keyword in [
            '401', '403', 'unauthorized', 'forbidden', 'authentication'
        ]):
            return RetryErrorType.AUTHENTICATION_ERROR
        
        # 数据错误
        if any(keyword in error_str for keyword in [
            'json', 'parse', 'decode', 'invalid data', 'malformed'
        ]):
            return RetryErrorType.DATA_ERROR
        
        return RetryErrorType.UNKNOWN_ERROR


class RetryManager:
    """重试管理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger("retry_manager")
        self.error_classifier = ErrorClassifier()
    
    def calculate_delay(self, attempt: int) -> float:
        """计算延迟时间"""
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
        elif self.config.strategy == RetryStrategy.JITTERED_EXPONENTIAL:
            base_delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
            delay = base_delay
        else:
            delay = self.config.base_delay
        
        # 添加抖动
        if self.config.jitter:
            jitter_range = delay * 0.1  # 10% 抖动
            delay += random.uniform(-jitter_range, jitter_range)
        
        # 限制最大延迟
        return min(delay, self.config.max_delay)
    
    def is_retryable_error(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        error_type = self.error_classifier.classify_error(error)
        return error_type in self.config.retryable_errors
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> RetryResult:
        """执行函数并进行重试"""
        start_time = time.time()
        attempts = []
        
        for attempt_num in range(1, self.config.max_attempts + 1):
            attempt_start = time.time()
            
            try:
                self.logger.debug(f"执行尝试 {attempt_num}/{self.config.max_attempts}")
                
                # 执行函数
                if self.config.timeout:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(func, *args, **kwargs)
                        try:
                            result = future.result(timeout=self.config.timeout)
                        except FutureTimeoutError:
                            raise TimeoutRetryableError(f"函数执行超时 ({self.config.timeout}秒)")
                else:
                    result = func(*args, **kwargs)
                
                response_time = time.time() - attempt_start
                
                # 成功执行
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    timestamp=datetime.now(),
                    error_type=RetryErrorType.UNKNOWN_ERROR,  # 成功时不重要
                    error_message="",
                    delay_before_retry=0.0,
                    success=True,
                    response_time=response_time
                )
                attempts.append(attempt)
                
                total_time = time.time() - start_time
                self.logger.info(f"函数执行成功，尝试次数: {attempt_num}, 总耗时: {total_time:.2f}秒")
                
                return RetryResult(
                    success=True,
                    result=result,
                    total_attempts=attempt_num,
                    total_time=total_time,
                    attempts=attempts
                )
                
            except Exception as error:
                response_time = time.time() - attempt_start
                error_type = self.error_classifier.classify_error(error)
                
                # 计算下次重试延迟
                delay = 0.0
                if attempt_num < self.config.max_attempts and self.is_retryable_error(error):
                    delay = self.calculate_delay(attempt_num)
                
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    timestamp=datetime.now(),
                    error_type=error_type,
                    error_message=str(error),
                    delay_before_retry=delay,
                    success=False,
                    response_time=response_time
                )
                attempts.append(attempt)
                
                self.logger.warning(
                    f"尝试 {attempt_num} 失败: {error_type.value} - {error}"
                )
                
                # 检查是否应该重试
                if attempt_num >= self.config.max_attempts:
                    self.logger.error(f"达到最大重试次数 ({self.config.max_attempts})，放弃重试")
                    break
                
                if not self.is_retryable_error(error):
                    self.logger.error(f"错误类型 {error_type.value} 不可重试，放弃重试")
                    break
                
                # 等待后重试
                if delay > 0:
                    self.logger.info(f"等待 {delay:.2f} 秒后重试...")
                    time.sleep(delay)
        
        # 所有重试都失败
        total_time = time.time() - start_time
        final_error = attempts[-1] if attempts else None
        
        self.logger.error(
            f"函数执行最终失败，总尝试次数: {len(attempts)}, 总耗时: {total_time:.2f}秒"
        )
        
        return RetryResult(
            success=False,
            error=Exception(final_error.error_message if final_error else "未知错误"),
            total_attempts=len(attempts),
            total_time=total_time,
            attempts=attempts
        )


def retry_on_failure(config: Optional[RetryConfig] = None):
    """重试装饰器"""
    def decorator(func: Callable) -> Callable:
        retry_manager = RetryManager(config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = retry_manager.execute_with_retry(func, *args, **kwargs)
            if result.success:
                return result.result
            else:
                raise result.error or Exception("重试失败")
        
        return wrapper
    return decorator


# 预定义的重试配置
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    strategy=RetryStrategy.JITTERED_EXPONENTIAL
)

CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    strategy=RetryStrategy.FIXED_DELAY
)

NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=4,
    base_delay=1.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_errors=[
        RetryErrorType.NETWORK_ERROR,
        RetryErrorType.TIMEOUT_ERROR,
        RetryErrorType.CONNECTION_ERROR
    ]
)


# 数据获取专用重试配置
DATA_FETCH_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    strategy=RetryStrategy.JITTERED_EXPONENTIAL,
    timeout=15.0,
    retryable_errors=[
        RetryErrorType.NETWORK_ERROR,
        RetryErrorType.TIMEOUT_ERROR,
        RetryErrorType.CONNECTION_ERROR,
        RetryErrorType.SERVER_ERROR,
        RetryErrorType.RATE_LIMIT_ERROR
    ]
)

QMT_CONNECTION_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    timeout=30.0,
    retryable_errors=[
        RetryErrorType.CONNECTION_ERROR,
        RetryErrorType.NETWORK_ERROR,
        RetryErrorType.TIMEOUT_ERROR
    ]
)

MARKET_DATA_RETRY_CONFIG = RetryConfig(
    max_attempts=4,
    base_delay=1.0,
    max_delay=45.0,
    strategy=RetryStrategy.JITTERED_EXPONENTIAL,
    timeout=20.0,
    retryable_errors=[
        RetryErrorType.NETWORK_ERROR,
        RetryErrorType.TIMEOUT_ERROR,
        RetryErrorType.CONNECTION_ERROR,
        RetryErrorType.SERVER_ERROR,
        RetryErrorType.DATA_ERROR
    ]
)


class DataFetchRetryManager(RetryManager):
    """数据获取专用重试管理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        super().__init__(config or DATA_FETCH_RETRY_CONFIG)
        self.data_fetch_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_requests': 0,
            'total_retry_attempts': 0,
            'avg_response_time': 0.0,
            'error_distribution': {}
        }
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> RetryResult:
        """执行数据获取函数并进行重试"""
        self.data_fetch_stats['total_requests'] += 1
        
        result = super().execute_with_retry(func, *args, **kwargs)
        
        # 更新统计信息
        if result.success:
            self.data_fetch_stats['successful_requests'] += 1
        else:
            self.data_fetch_stats['failed_requests'] += 1
            
            # 记录错误分布
            if result.final_error_type:
                error_type = result.final_error_type.value
                self.data_fetch_stats['error_distribution'][error_type] = \
                    self.data_fetch_stats['error_distribution'].get(error_type, 0) + 1
        
        if result.total_attempts > 1:
            self.data_fetch_stats['retry_requests'] += 1
            self.data_fetch_stats['total_retry_attempts'] += (result.total_attempts - 1)
        
        # 更新平均响应时间
        total_successful = self.data_fetch_stats['successful_requests']
        if total_successful > 0:
            current_avg = self.data_fetch_stats['avg_response_time']
            new_avg = ((current_avg * (total_successful - 1)) + result.total_time) / total_successful
            self.data_fetch_stats['avg_response_time'] = new_avg
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据获取统计信息"""
        stats = self.data_fetch_stats.copy()
        
        # 计算成功率
        total = stats['total_requests']
        if total > 0:
            stats['success_rate'] = stats['successful_requests'] / total
            stats['retry_rate'] = stats['retry_requests'] / total
        else:
            stats['success_rate'] = 0.0
            stats['retry_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.data_fetch_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_requests': 0,
            'total_retry_attempts': 0,
            'avg_response_time': 0.0,
            'error_distribution': {}
        }


# 全局数据获取重试管理器实例
_global_data_fetch_retry_manager = DataFetchRetryManager()


def get_data_fetch_retry_manager() -> DataFetchRetryManager:
    """获取全局数据获取重试管理器"""
    return _global_data_fetch_retry_manager


# 便捷函数
def retry_with_exponential_backoff(max_attempts: int = 3, base_delay: float = 1.0):
    """指数退避重试装饰器"""
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF
    )
    return retry_on_failure(config)


def retry_network_errors(max_attempts: int = 3):
    """网络错误重试装饰器"""
    return retry_on_failure(NETWORK_RETRY_CONFIG._replace(max_attempts=max_attempts))


def retry_data_fetch(config: Optional[RetryConfig] = None):
    """数据获取重试装饰器"""
    def decorator(func: Callable) -> Callable:
        retry_manager = DataFetchRetryManager(config)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                # 直接调用原函数，如果抛出HTTPException则不进行重试
                return await func(*args, **kwargs)
            except Exception as e:
                # 如果是HTTPException，直接抛出，不进行重试
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    raise e
                
                # 对于其他异常，使用重试机制
                def sync_func():
                    # 在同步上下文中运行异步函数
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(func(*args, **kwargs))
                    finally:
                        loop.close()
                
                result = retry_manager.execute_with_retry(sync_func)
                if result.success:
                    return result.result
                else:
                    # 记录详细的失败信息
                    error_msg = f"数据获取失败: {result.error}"
                    if result.attempts:
                        last_attempt = result.attempts[-1]
                        error_msg += f" (错误类型: {last_attempt.error_type.value})"
                    
                    raise Exception(error_msg)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                # 直接调用原函数，如果抛出HTTPException则不进行重试
                return func(*args, **kwargs)
            except Exception as e:
                # 如果是HTTPException，直接抛出，不进行重试
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    raise e
                
                # 对于其他异常，使用重试机制
                result = retry_manager.execute_with_retry(func, *args, **kwargs)
                if result.success:
                    return result.result
                else:
                    # 记录详细的失败信息
                    error_msg = f"数据获取失败: {result.error}"
                    if result.attempts:
                        last_attempt = result.attempts[-1]
                        error_msg += f" (错误类型: {last_attempt.error_type.value})"
                    
                    raise Exception(error_msg)
        
        # 检查函数是否是异步的
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator


def retry_qmt_connection(max_attempts: int = 3):
    """QMT连接重试装饰器"""
    return retry_on_failure(QMT_CONNECTION_RETRY_CONFIG._replace(max_attempts=max_attempts))


def retry_market_data(max_attempts: int = 4):
    """市场数据获取重试装饰器"""
    return retry_on_failure(MARKET_DATA_RETRY_CONFIG._replace(max_attempts=max_attempts))