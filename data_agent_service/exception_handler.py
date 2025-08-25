#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常处理和恢复机制模块
提供智能异常分类、自动恢复策略和错误上报功能
"""

import asyncio
import logging
import threading
import time
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union, Deque
from concurrent.futures import ThreadPoolExecutor


class ExceptionSeverity(Enum):
    """异常严重程度"""
    LOW = "low"                    # 低 - 不影响核心功能
    MEDIUM = "medium"              # 中 - 影响部分功能
    HIGH = "high"                  # 高 - 影响核心功能
    CRITICAL = "critical"          # 严重 - 系统不可用


class RecoveryStrategy(Enum):
    """恢复策略"""
    IGNORE = "ignore"              # 忽略错误
    RETRY = "retry"                # 重试操作
    RESTART = "restart"            # 重启组件
    ESCALATE = "escalate"          # 上报处理
    CIRCUIT_BREAK = "circuit_break" # 熔断
    # FALLBACK策略已移除 - 项目不再支持任何形式的回退机制


class ExceptionCategory(Enum):
    """异常分类"""
    NETWORK_ERROR = "network"      # 网络异常
    DATA_ERROR = "data"            # 数据异常
    SYSTEM_ERROR = "system"        # 系统异常
    BUSINESS_ERROR = "business"    # 业务异常
    SECURITY_ERROR = "security"    # 安全异常
    RESOURCE_ERROR = "resource"    # 资源异常
    UNKNOWN_ERROR = "unknown"      # 未知异常


@dataclass
class ExceptionInfo:
    """异常信息"""
    exception_type: str
    exception_message: str
    category: ExceptionCategory
    severity: ExceptionSeverity
    recovery_strategy: RecoveryStrategy
    timestamp: datetime
    traceback_info: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempts: int = 0
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "recovery_strategy": self.recovery_strategy.value,
            "timestamp": self.timestamp.isoformat(),
            "traceback_info": self.traceback_info,
            "context": self.context,
            "recovery_attempts": self.recovery_attempts,
            "resolved": self.resolved,
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None
        }


@dataclass
class RecoveryAction:
    """恢复动作"""
    name: str
    action: Callable[[], bool]     # 返回True表示恢复成功
    max_attempts: int = 3
    delay_between_attempts: float = 1.0
    timeout: Optional[float] = None


class ExceptionClassifier:
    """异常分类器"""
    
    def __init__(self):
        self.classification_rules: Dict[str, Callable[[Exception], Optional[tuple]]] = {}
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """设置默认分类规则"""
        
        # 网络异常规则
        def network_rule(exc: Exception) -> Optional[tuple]:
            error_str = str(exc).lower()
            error_type = type(exc).__name__.lower()
            
            network_keywords = [
                'connection', 'network', 'timeout', 'dns', 'socket',
                'unreachable', 'refused', 'reset', 'broken pipe'
            ]
            
            if any(keyword in error_str or keyword in error_type for keyword in network_keywords):
                if 'timeout' in error_str or 'timeout' in error_type:
                    return (ExceptionCategory.NETWORK_ERROR, ExceptionSeverity.MEDIUM, RecoveryStrategy.RETRY)
                else:
                    return (ExceptionCategory.NETWORK_ERROR, ExceptionSeverity.HIGH, RecoveryStrategy.RETRY)
            return None
        
        # 数据异常规则
        def data_rule(exc: Exception) -> Optional[tuple]:
            error_str = str(exc).lower()
            error_type = type(exc).__name__.lower()
            
            data_keywords = [
                'json', 'parse', 'decode', 'encode', 'format', 'invalid data',
                'malformed', 'corrupt', 'missing field', 'type error'
            ]
            
            if any(keyword in error_str or keyword in error_type for keyword in data_keywords):
                return (ExceptionCategory.DATA_ERROR, ExceptionSeverity.MEDIUM, RecoveryStrategy.ESCALATE)
            return None
        
        # 系统异常规则
        def system_rule(exc: Exception) -> Optional[tuple]:
            error_type = type(exc).__name__.lower()
            
            if error_type in ['systemexit', 'keyboardinterrupt', 'memoryerror', 'oserror']:
                return (ExceptionCategory.SYSTEM_ERROR, ExceptionSeverity.CRITICAL, RecoveryStrategy.RESTART)
            return None
        
        # 资源异常规则
        def resource_rule(exc: Exception) -> Optional[tuple]:
            error_str = str(exc).lower()
            error_type = type(exc).__name__.lower()
            
            resource_keywords = [
                'memory', 'disk', 'file', 'permission', 'access denied',
                'quota', 'limit', 'resource', 'busy'
            ]
            
            if any(keyword in error_str or keyword in error_type for keyword in resource_keywords):
                if 'memory' in error_str or 'memoryerror' in error_type:
                    return (ExceptionCategory.RESOURCE_ERROR, ExceptionSeverity.CRITICAL, RecoveryStrategy.RESTART)
                else:
                    return (ExceptionCategory.RESOURCE_ERROR, ExceptionSeverity.MEDIUM, RecoveryStrategy.ESCALATE)
            return None
        
        # 安全异常规则
        def security_rule(exc: Exception) -> Optional[tuple]:
            error_str = str(exc).lower()
            
            security_keywords = [
                'unauthorized', 'forbidden', 'authentication', 'permission',
                'access denied', 'security', 'certificate', 'ssl'
            ]
            
            if any(keyword in error_str for keyword in security_keywords):
                return (ExceptionCategory.SECURITY_ERROR, ExceptionSeverity.HIGH, RecoveryStrategy.ESCALATE)
            return None
        
        self.classification_rules = {
            "network": network_rule,
            "data": data_rule,
            "system": system_rule,
            "resource": resource_rule,
            "security": security_rule
        }
    
    def classify(self, exception: Exception) -> tuple:
        """分类异常"""
        for rule_name, rule_func in self.classification_rules.items():
            try:
                result = rule_func(exception)
                if result:
                    return result
            except Exception as e:
                logging.error(f"异常分类规则 {rule_name} 执行失败: {e}")
        
        # 默认分类
        return (ExceptionCategory.UNKNOWN_ERROR, ExceptionSeverity.MEDIUM, RecoveryStrategy.RETRY)
    
    def add_rule(self, name: str, rule: Callable[[Exception], Optional[tuple]]):
        """添加自定义分类规则"""
        self.classification_rules[name] = rule


class RecoveryManager:
    """恢复管理器"""
    
    def __init__(self):
        self.recovery_actions: Dict[RecoveryStrategy, List[RecoveryAction]] = defaultdict(list)
        self.logger = logging.getLogger("recovery_manager")
        self._setup_default_actions()
    
    def _setup_default_actions(self):
        """设置默认恢复动作"""
        
        # 重试动作
        def simple_retry() -> bool:
            """简单重试"""
            time.sleep(1)
            return True
        
        # 连接重置动作
        def reset_connection() -> bool:
            """重置连接"""
            try:
                # 这里可以添加具体的连接重置逻辑
                self.logger.info("正在重置连接...")
                time.sleep(2)
                return True
            except Exception as e:
                self.logger.error(f"连接重置失败: {e}")
                return False
        
        # 清理缓存动作
        def clear_cache() -> bool:
            """清理缓存"""
            try:
                self.logger.info("正在清理缓存...")
                # 这里可以添加具体的缓存清理逻辑
                return True
            except Exception as e:
                self.logger.error(f"缓存清理失败: {e}")
                return False
        
        self.add_recovery_action(RecoveryStrategy.RETRY, RecoveryAction(
            name="simple_retry",
            action=simple_retry,
            max_attempts=3,
            delay_between_attempts=1.0
        ))
        
        # FALLBACK恢复动作已移除 - 项目不再支持任何形式的回退机制
        # 所有连接问题和缓存问题都应该通过RETRY或ESCALATE策略处理
    
    def add_recovery_action(self, strategy: RecoveryStrategy, action: RecoveryAction):
        """添加恢复动作"""
        self.recovery_actions[strategy].append(action)
        self.logger.info(f"添加恢复动作: {strategy.value} -> {action.name}")
    
    def execute_recovery(self, strategy: RecoveryStrategy, context: Dict[str, Any] = None) -> bool:
        """执行恢复策略"""
        if strategy == RecoveryStrategy.IGNORE:
            return True
        
        if strategy == RecoveryStrategy.ESCALATE:
            self.logger.error("异常需要人工处理")
            return False
        
        actions = self.recovery_actions.get(strategy, [])
        if not actions:
            self.logger.warning(f"没有找到恢复策略 {strategy.value} 的动作")
            return False
        
        for action in actions:
            self.logger.info(f"执行恢复动作: {action.name}")
            
            for attempt in range(action.max_attempts):
                try:
                    if action.timeout:
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(action.action)
                            success = future.result(timeout=action.timeout)
                    else:
                        success = action.action()
                    
                    if success:
                        self.logger.info(f"恢复动作 {action.name} 执行成功")
                        return True
                    else:
                        self.logger.warning(f"恢复动作 {action.name} 执行失败，尝试 {attempt + 1}/{action.max_attempts}")
                        
                except Exception as e:
                    self.logger.error(f"恢复动作 {action.name} 执行异常: {e}")
                
                if attempt < action.max_attempts - 1:
                    time.sleep(action.delay_between_attempts)
        
        self.logger.error(f"恢复策略 {strategy.value} 执行失败")
        return False


class ExceptionHandler:
    """异常处理器"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.exception_history: Deque[ExceptionInfo] = deque(maxlen=max_history)
        self.classifier = ExceptionClassifier()
        self.recovery_manager = RecoveryManager()
        self.logger = logging.getLogger("exception_handler")
        self._lock = threading.Lock()
        
        # 异常统计
        self.exception_stats: Dict[str, int] = defaultdict(int)
        self.recovery_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    def handle_exception(self, 
                        exception: Exception, 
                        context: Dict[str, Any] = None,
                        auto_recover: bool = True) -> ExceptionInfo:
        """处理异常"""
        # 分类异常
        category, severity, recovery_strategy = self.classifier.classify(exception)
        
        # 创建异常信息
        exception_info = ExceptionInfo(
            exception_type=type(exception).__name__,
            exception_message=str(exception),
            category=category,
            severity=severity,
            recovery_strategy=recovery_strategy,
            timestamp=datetime.now(),
            traceback_info=traceback.format_exc(),
            context=context or {}
        )
        
        # 记录异常
        with self._lock:
            self.exception_history.append(exception_info)
            self.exception_stats[category.value] += 1
        
        # 记录日志
        log_level = self._get_log_level(severity)
        self.logger.log(
            log_level,
            f"处理异常: {category.value} - {severity.value} - {exception_info.exception_message}"
        )
        
        # 自动恢复
        if auto_recover and recovery_strategy != RecoveryStrategy.ESCALATE:
            recovery_success = self._attempt_recovery(exception_info)
            if recovery_success:
                exception_info.resolved = True
                exception_info.resolution_time = datetime.now()
        
        return exception_info
    
    def _get_log_level(self, severity: ExceptionSeverity) -> int:
        """获取日志级别"""
        level_map = {
            ExceptionSeverity.LOW: logging.INFO,
            ExceptionSeverity.MEDIUM: logging.WARNING,
            ExceptionSeverity.HIGH: logging.ERROR,
            ExceptionSeverity.CRITICAL: logging.CRITICAL
        }
        return level_map.get(severity, logging.WARNING)
    
    def _attempt_recovery(self, exception_info: ExceptionInfo) -> bool:
        """尝试恢复"""
        strategy = exception_info.recovery_strategy
        
        self.logger.info(f"尝试恢复策略: {strategy.value}")
        
        max_recovery_attempts = 3
        for attempt in range(max_recovery_attempts):
            exception_info.recovery_attempts += 1
            
            try:
                success = self.recovery_manager.execute_recovery(strategy, exception_info.context)
                
                with self._lock:
                    self.recovery_stats[strategy.value]["success" if success else "failure"] += 1
                
                if success:
                    self.logger.info(f"恢复成功，尝试次数: {attempt + 1}")
                    return True
                else:
                    self.logger.warning(f"恢复失败，尝试次数: {attempt + 1}/{max_recovery_attempts}")
                    
            except Exception as recovery_error:
                self.logger.error(f"恢复过程异常: {recovery_error}")
                with self._lock:
                    self.recovery_stats[strategy.value]["error"] += 1
            
            if attempt < max_recovery_attempts - 1:
                time.sleep(2 ** attempt)  # 指数退避
        
        self.logger.error(f"恢复策略 {strategy.value} 最终失败")
        return False
    
    def get_exception_stats(self, hours: int = 24) -> Dict[str, Any]:
        """获取异常统计"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_exceptions = [
                exc for exc in self.exception_history 
                if exc.timestamp >= cutoff_time
            ]
        
        # 按类别统计
        category_stats = defaultdict(int)
        severity_stats = defaultdict(int)
        recovery_stats = defaultdict(int)
        resolved_count = 0
        
        for exc in recent_exceptions:
            category_stats[exc.category.value] += 1
            severity_stats[exc.severity.value] += 1
            recovery_stats[exc.recovery_strategy.value] += 1
            if exc.resolved:
                resolved_count += 1
        
        return {
            "time_window_hours": hours,
            "total_exceptions": len(recent_exceptions),
            "resolved_exceptions": resolved_count,
            "resolution_rate": resolved_count / len(recent_exceptions) if recent_exceptions else 0,
            "category_breakdown": dict(category_stats),
            "severity_breakdown": dict(severity_stats),
            "recovery_strategy_breakdown": dict(recovery_stats),
            "recovery_success_rates": {
                strategy: {
                    "total": sum(stats.values()),
                    "success_rate": stats["success"] / sum(stats.values()) if sum(stats.values()) > 0 else 0
                }
                for strategy, stats in self.recovery_stats.items()
            }
        }
    
    def get_recent_exceptions(self, count: int = 50) -> List[Dict[str, Any]]:
        """获取最近的异常"""
        with self._lock:
            recent = list(self.exception_history)[-count:]
        
        return [exc.to_dict() for exc in reversed(recent)]


def exception_handler_decorator(handler: ExceptionHandler, 
                              auto_recover: bool = True,
                              reraise: bool = False):
    """异常处理装饰器（支持同步和异步函数）"""
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    context = {
                        "function": func.__name__,
                        "args": str(args)[:200],  # 限制长度
                        "kwargs": str(kwargs)[:200]
                    }
                    
                    exception_info = handler.handle_exception(e, context, auto_recover)
                    
                    if reraise or not exception_info.resolved:
                        raise
                    
                    # 如果异常已解决，返回None或默认值
                    return None
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    context = {
                        "function": func.__name__,
                        "args": str(args)[:200],  # 限制长度
                        "kwargs": str(kwargs)[:200]
                    }
                    
                    exception_info = handler.handle_exception(e, context, auto_recover)
                    
                    if reraise or not exception_info.resolved:
                        raise
                    
                    # 如果异常已解决，返回None或默认值
                    return None
            
            return sync_wrapper
    return decorator


# 全局异常处理器实例
_global_exception_handler: Optional[ExceptionHandler] = None
_handler_lock = threading.Lock()


def get_global_exception_handler() -> ExceptionHandler:
    """获取全局异常处理器实例"""
    global _global_exception_handler
    
    if _global_exception_handler is None:
        with _handler_lock:
            if _global_exception_handler is None:
                _global_exception_handler = ExceptionHandler(max_history=1000)
    
    return _global_exception_handler


def handle_exception(exception: Exception, 
                    context: Dict[str, Any] = None,
                    auto_recover: bool = True) -> ExceptionInfo:
    """全局异常处理函数"""
    handler = get_global_exception_handler()
    return handler.handle_exception(exception, context, auto_recover)


def safe_execute(func: Callable, 
                auto_recover: bool = True,
                default_return: Any = None,
                context: Dict[str, Any] = None) -> Any:
    """安全执行装饰器
    使用方式：
      - 作为无参装饰器：@safe_execute
      - 作为带参装饰器：@safe_execute(auto_recover=False, default_return=None, context={})
    支持同步与异步函数，确保不会在装饰时立即执行被装饰函数，从而保留self/args参数。
    """
    def decorator(f: Callable):
        if asyncio.iscoroutinefunction(f):
            @wraps(f)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await f(*args, **kwargs)
                except Exception as e:
                    exception_info = handle_exception(e, context or {}, auto_recover)
                    if exception_info.resolved:
                        return default_return
                    else:
                        raise
            return async_wrapper
        else:
            @wraps(f)
            def sync_wrapper(*args, **kwargs):
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    exception_info = handle_exception(e, context or {}, auto_recover)
                    if exception_info.resolved:
                        return default_return
                    else:
                        raise
            return sync_wrapper
    # 兼容@safe_execute和@safe_execute(...)
    if callable(func):
        return decorator(func)
    else:
        return decorator


# 全局异常处理器实例
_global_exception_handler: Optional[ExceptionHandler] = None
_handler_lock = threading.Lock()


def get_global_exception_handler() -> ExceptionHandler:
    """获取全局异常处理器实例"""
    global _global_exception_handler
    
    if _global_exception_handler is None:
        with _handler_lock:
            if _global_exception_handler is None:
                _global_exception_handler = ExceptionHandler(max_history=1000)
    
    return _global_exception_handler


def handle_exception(exception: Exception, 
                    context: Dict[str, Any] = None,
                    auto_recover: bool = True) -> ExceptionInfo:
    """全局异常处理函数"""
    handler = get_global_exception_handler()
    return handler.handle_exception(exception, context, auto_recover)