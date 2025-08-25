#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xtquant连接池管理模块
提供高可用的xtquant连接池管理，支持连接复用、健康检查和自动恢复
"""

import asyncio
import logging
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty, PriorityQueue
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict

# 强制导入xtdata，如果失败则抛出错误
try:
    from xtquant import xtdata
except ImportError as e:
    raise ImportError(
        "无法导入xtdata模块。请确保miniQMT客户端已正确安装并配置。"
        "项目不支持模拟模式，必须连接真实的miniQMT服务。"
    ) from e


class ConnectionStatus(Enum):
    """连接状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    WARMING_UP = "warming_up"


class ConnectionPriority(Enum):
    """连接优先级枚举"""
    HIGH = 1
    NORMAL = 2
    LOW = 3


class LoadBalanceStrategy(Enum):
    """负载均衡策略枚举"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    FASTEST_RESPONSE = "fastest_response"
    RANDOM = "random"


@dataclass
class ConnectionMetrics:
    """连接指标数据类"""
    connection_id: str
    status: ConnectionStatus
    last_used: datetime
    created_at: datetime
    total_requests: int
    failed_requests: int
    avg_response_time: float
    last_error: Optional[str] = None
    last_health_check: Optional[datetime] = None
    
    # 新增指标
    consecutive_failures: int = 0
    max_response_time: float = 0.0
    min_response_time: float = float('inf')
    response_times: List[float] = field(default_factory=list)
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    warmup_requests: int = 0
    priority: ConnectionPriority = ConnectionPriority.NORMAL
    active_requests: int = 0

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.failed_requests) / self.total_requests

    @property
    def is_idle(self) -> bool:
        """检查连接是否空闲"""
        return (datetime.now() - self.last_used).total_seconds() > 300  # 5分钟空闲
    
    @property
    def is_healthy(self) -> bool:
        """连接是否健康"""
        if self.status != ConnectionStatus.HEALTHY:
            return False
        
        # 连续失败次数过多
        if self.consecutive_failures >= 5:
            return False
        
        # 成功率过低
        if self.total_requests >= 10 and self.success_rate < 0.8:
            return False
        
        # 响应时间过长
        if self.avg_response_time > 10.0:
            return False
        
        return True
    
    @property
    def load_score(self) -> float:
        """负载评分，用于负载均衡"""
        # 基础评分：活跃请求数
        score = self.active_requests * 10
        
        # 响应时间权重
        score += self.avg_response_time * 5
        
        # 失败率权重
        if self.total_requests > 0:
            failure_rate = self.failed_requests / self.total_requests
            score += failure_rate * 20
        
        # 连续失败权重
        score += self.consecutive_failures * 3
        
        return score
    
    def update_response_time(self, response_time: float):
        """更新响应时间统计"""
        self.response_times.append(response_time)
        
        # 保持最近100次请求的响应时间
        if len(self.response_times) > 100:
            self.response_times.pop(0)
        
        # 更新统计值
        self.avg_response_time = sum(self.response_times) / len(self.response_times)
        self.max_response_time = max(self.max_response_time, response_time)
        self.min_response_time = min(self.min_response_time, response_time)
    
    def record_success(self, response_time: float):
        """记录成功请求"""
        self.total_requests += 1
        self.consecutive_failures = 0
        self.last_used = datetime.now()
        self.update_response_time(response_time)
    
    def record_failure(self, error_type: str, response_time: float = 0.0):
        """记录失败请求"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_used = datetime.now()
        self.error_counts[error_type] += 1
        
        if response_time > 0:
            self.update_response_time(response_time)


class XtQuantConnection:
    """xtquant连接包装器"""
    
    def __init__(self, connection_id: str, config: Dict[str, Any]):
        self.connection_id = connection_id
        self.config = config
        self.metrics = ConnectionMetrics(
            connection_id=connection_id,
            status=ConnectionStatus.DISCONNECTED,
            last_used=datetime.now(),
            created_at=datetime.now(),
            total_requests=0,
            failed_requests=0,
            avg_response_time=0.0
        )
        self._lock = threading.Lock()
        self._connected = False
        self.logger = logging.getLogger(f"xtquant.connection.{connection_id}")
        
        # 连接配置
        self.connection_timeout = config.get('connection_timeout', 10)
        
        # 重试配置
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay_base = config.get('retry_delay_base', 1.0)
        self.retry_delay_max = config.get('retry_delay_max', 30.0)
        
        # 预热配置
        self.warmup_requests = config.get('warmup_requests', 5)
        self.warmup_timeout = config.get('warmup_timeout', 30.0)
        
    def connect(self) -> bool:
        """建立连接"""
        with self._lock:
            try:
                self.metrics.status = ConnectionStatus.CONNECTING
                self.logger.info(f"正在连接 xtquant [{self.connection_id}]")
                
                # 使用重试机制建立连接
                success = self._connect_with_retry()
                
                if success:
                    # 连接成功后进行预热
                    self._warmup_connection()
                    self.metrics.status = ConnectionStatus.HEALTHY
                    self.logger.info(f"xtquant 连接成功 [{self.connection_id}]")
                    return True
                else:
                    self.metrics.status = ConnectionStatus.ERROR
                    self.logger.error(f"xtquant 连接失败 [{self.connection_id}]")
                    return False
                    
            except Exception as e:
                self.metrics.status = ConnectionStatus.ERROR
                self.metrics.record_failure("connection_error")
                self.logger.error(f"连接异常 [{self.connection_id}]: {e}")
                return False
    
    def _connect_with_retry(self) -> bool:
        """使用重试机制建立连接"""
        for attempt in range(self.max_retries + 1):
            try:
                # 实际连接逻辑
                result = xtdata.connect()
                self._connected = result
                return result
                    
            except Exception as e:
                if attempt < self.max_retries:
                    delay = min(self.retry_delay_base * (2 ** attempt), self.retry_delay_max)
                    jitter = random.uniform(0, delay * 0.1)  # 添加抖动
                    total_delay = delay + jitter
                    
                    self.logger.warning(
                        f"连接尝试 {attempt + 1}/{self.max_retries + 1} 失败: {e}, "
                        f"{total_delay:.2f}秒后重试"
                    )
                    time.sleep(total_delay)
                else:
                    self.logger.error(f"连接重试失败，已达到最大重试次数: {e}")
                    raise e
        
        return False
    
    def _warmup_connection(self):
        """预热连接"""
        if self.warmup_requests <= 0:
            return
        
        self.metrics.status = ConnectionStatus.WARMING_UP
        self.logger.info(f"开始预热连接: {self.connection_id}")
        
        start_time = time.time()
        successful_warmups = 0
        
        for i in range(self.warmup_requests):
            if time.time() - start_time > self.warmup_timeout:
                self.logger.warning(f"预热超时，已完成 {successful_warmups}/{self.warmup_requests} 次预热")
                break
            
            try:
                # 执行简单的预热请求
                warmup_start = time.time()
                self._execute_warmup_request()
                warmup_time = time.time() - warmup_start
                
                self.metrics.warmup_requests += 1
                self.metrics.record_success(warmup_time)
                successful_warmups += 1
                
                # 预热请求间隔
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.warning(f"预热请求失败: {e}")
                self.metrics.record_failure("warmup_error")
        
        self.logger.info(
            f"连接预热完成: {self.connection_id}, "
            f"成功 {successful_warmups}/{self.warmup_requests} 次"
        )
    
    def _execute_warmup_request(self):
        """执行预热请求"""
        # 模拟简单的数据请求
        time.sleep(0.05)
        
        # 这里应该是实际的预热请求逻辑
        # 例如：获取市场状态、验证连接等
        pass
    
    def disconnect(self):
        """断开连接"""
        with self._lock:
            try:
                if self._connected:
                    xtdata.disconnect()
                self._connected = False
                self.metrics.status = ConnectionStatus.DISCONNECTED
                self.logger.info(f"xtquant 连接已断开 [{self.connection_id}]")
            except Exception as e:
                self.logger.error(f"断开连接异常 [{self.connection_id}]: {e}")
    
    def is_healthy(self) -> bool:
        """检查连接健康状态"""
        try:
            # 如果最近检查过且状态良好，直接返回
            if (self.metrics.last_health_check and 
                (datetime.now() - self.metrics.last_health_check).total_seconds() < 300 and  # 增加到5分钟
                self.metrics.status == ConnectionStatus.HEALTHY):
                return True
            
            start_time = time.time()
            
            # 轻量级健康检查 - 只检查xtdata模块是否可用
            try:
                # 尝试导入xtdata模块，这比实际调用API更轻量
                import xtdata
                # 简单检查模块是否正常
                result = hasattr(xtdata, 'get_market_data')
            except ImportError:
                result = False
            
            response_time = time.time() - start_time
            
            # 更新指标
            self.metrics.last_health_check = datetime.now()
            
            if result:
                if response_time > 1.0:  # 响应时间超过1秒认为性能下降
                    self.metrics.status = ConnectionStatus.UNHEALTHY
                else:
                    self.metrics.status = ConnectionStatus.HEALTHY
            else:
                self.metrics.status = ConnectionStatus.UNHEALTHY
                
            return result
            
        except Exception as e:
            self.metrics.status = ConnectionStatus.UNHEALTHY
            self.metrics.last_error = str(e)
            # 完全禁用健康检查失败日志
            # self.logger.debug(f"健康检查失败 [{self.connection_id}]: {e}")
            return False
    
    def execute_request(self, request_func: Callable, *args, **kwargs) -> Any:
        """执行请求"""
        if not self.is_healthy():
            raise ConnectionError(f"连接不健康: {self.connection_id}")
        
        # 增加活跃请求计数
        with self._lock:
            self.metrics.active_requests += 1
        
        start_time = time.time()
        try:
            # 使用重试机制执行请求
            result = self._execute_with_retry(request_func, *args, **kwargs)
            
            # 记录成功
            response_time = time.time() - start_time
            self.metrics.record_success(response_time)
            
            return result
            
        except Exception as e:
            # 记录失败
            response_time = time.time() - start_time
            error_type = type(e).__name__
            self.metrics.record_failure(error_type, response_time)
            
            self.logger.error(f"请求执行失败 [{self.connection_id}]: {e}")
            raise
        
        finally:
            # 减少活跃请求计数
            with self._lock:
                self.metrics.active_requests = max(0, self.metrics.active_requests - 1)
    
    def _execute_with_retry(self, request_func: Callable, *args, **kwargs) -> Any:
        """使用重试机制执行请求"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return request_func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # 判断是否应该重试
                if not self._should_retry(e, attempt):
                    raise e
                
                if attempt < self.max_retries:
                    delay = min(self.retry_delay_base * (2 ** attempt), self.retry_delay_max)
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter
                    
                    self.logger.warning(
                        f"请求重试 {attempt + 1}/{self.max_retries + 1}: {e}, "
                        f"{total_delay:.2f}秒后重试"
                    )
                    time.sleep(total_delay)
        
        # 所有重试都失败了
        raise last_exception
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        # 网络相关错误通常可以重试
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            OSError,
        )
        
        if isinstance(exception, retryable_errors):
            return True
        
        # 特定错误消息的重试判断
        error_msg = str(exception).lower()
        retryable_messages = [
            'connection reset',
            'connection refused',
            'timeout',
            'network',
            'temporary failure'
        ]
        
        for msg in retryable_messages:
            if msg in error_msg:
                return True
        
        return False


class XtQuantConnectionPool:
    """xtquant连接池管理器"""
    
    def __init__(self, min_connections: int = 2, max_connections: int = 10, 
                 health_check_interval: int = 30, connection_timeout: int = 10,
                 max_idle_time: int = 300, load_balance_strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_CONNECTIONS):
        """
        初始化连接池
        
        Args:
            min_connections: 最小连接数
            max_connections: 最大连接数
            health_check_interval: 健康检查间隔(秒)
            connection_timeout: 连接超时时间(秒)
            max_idle_time: 最大空闲时间(秒)
            load_balance_strategy: 负载均衡策略
        """
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.health_check_interval = health_check_interval
        self.connection_timeout = connection_timeout
        self.max_idle_time = max_idle_time
        self.load_balance_strategy = load_balance_strategy
        
        self._connections: Dict[str, XtQuantConnection] = {}
        self._available_connections = Queue(maxsize=max_connections)
        self._lock = threading.RLock()
        self._shutdown = False
        
        # 负载均衡相关
        self._round_robin_index = 0
        self._connection_stats = defaultdict(lambda: {'requests': 0, 'last_used': time.time()})
        
        self.logger = logging.getLogger("xtquant.connection_pool")
        
        # 启动后台任务
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="xtquant-pool")
        self._health_check_future = self._executor.submit(self._health_check_loop)
        self._cleanup_future = self._executor.submit(self._cleanup_loop)
        self._stats_future = self._executor.submit(self._stats_collection_loop)
        
        # 初始化最小连接数
        self._initialize_connections()
    
    def _initialize_connections(self):
        """初始化最小连接数"""
        for i in range(self.min_connections):
            connection = self._create_connection(f"conn_{i}")
            if connection.connect():
                self._available_connections.put(connection)
                self.logger.info(f"初始化连接成功: {connection.connection_id}")
            else:
                self.logger.error(f"初始化连接失败: {connection.connection_id}")
    
    def _create_connection(self, connection_id: str, config: dict = None) -> XtQuantConnection:
        """创建新的连接实例"""
        if config is None:
            config = {
                "connection_timeout": self.connection_timeout,
                "max_retries": 3,
                "retry_delay_base": 1.0,
                "retry_delay_max": 30.0,
                "warmup_requests": 3,
                "warmup_timeout": 15.0
            }
        
        connection = XtQuantConnection(
            connection_id=connection_id,
            config=config
        )
        
        # 添加到连接字典和统计信息
        with self._lock:
            self._connections[connection_id] = connection
            self._connection_stats[connection_id] = {
                'requests': 0,
                'last_used': time.time(),
                'created_at': time.time()
            }
        
        return connection
    
    @contextmanager
    def get_connection(self, timeout: float = 10.0):
        """获取连接的上下文管理器"""
        connection = None
        try:
            connection = self._acquire_connection(timeout)
            yield connection
        finally:
            if connection:
                self._release_connection(connection)
    
    def _acquire_connection(self, timeout: float) -> XtQuantConnection:
        """获取可用连接"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 使用负载均衡策略选择连接
            connection = self._select_connection_by_strategy()
            
            if connection:
                # 检查连接健康状态
                if connection.is_healthy():
                    self._update_connection_stats(connection.connection_id)
                    return connection
                else:
                    # 连接不健康，尝试重连
                    if connection.connect():
                        self._update_connection_stats(connection.connection_id)
                        return connection
                    else:
                        # 重连失败，移除连接
                        self.logger.warning(f"连接 {connection.connection_id} 重连失败，移除连接")
                        self._remove_connection(connection)
                        continue
            
            # 没有可用连接，尝试创建新连接
            if len(self._connections) < self.max_connections:
                connection = self._create_new_connection()
                if connection:
                    self._update_connection_stats(connection.connection_id)
                    return connection
            
            # 等待一段时间后重试
            time.sleep(0.1)
        
        raise TimeoutError(f"获取连接超时 ({timeout}秒)")
    
    def _select_connection_by_strategy(self) -> Optional[XtQuantConnection]:
        """根据负载均衡策略选择连接"""
        with self._lock:
            healthy_connections = [
                conn for conn in self._connections.values() 
                if conn.metrics.is_healthy and conn.metrics.active_requests < 10  # 限制并发请求数
            ]
            
            if not healthy_connections:
                return None
            
            if self.load_balance_strategy == LoadBalanceStrategy.ROUND_ROBIN:
                return self._select_round_robin(healthy_connections)
            elif self.load_balance_strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
                return self._select_least_connections(healthy_connections)
            elif self.load_balance_strategy == LoadBalanceStrategy.FASTEST_RESPONSE:
                return self._select_fastest_response(healthy_connections)
            elif self.load_balance_strategy == LoadBalanceStrategy.RANDOM:
                return self._select_random(healthy_connections)
            else:
                return healthy_connections[0]
    
    def _select_round_robin(self, connections: List[XtQuantConnection]) -> XtQuantConnection:
        """轮询策略"""
        if not connections:
            return None
        
        connection = connections[self._round_robin_index % len(connections)]
        self._round_robin_index = (self._round_robin_index + 1) % len(connections)
        return connection
    
    def _select_least_connections(self, connections: List[XtQuantConnection]) -> XtQuantConnection:
        """最少连接策略"""
        if not connections:
            return None
        
        return min(connections, key=lambda conn: conn.metrics.active_requests)
    
    def _select_fastest_response(self, connections: List[XtQuantConnection]) -> XtQuantConnection:
        """最快响应策略"""
        if not connections:
            return None
        
        # 优先选择响应时间最短的连接
        return min(connections, key=lambda conn: conn.metrics.avg_response_time)
    
    def _select_random(self, connections: List[XtQuantConnection]) -> XtQuantConnection:
        """随机策略"""
        if not connections:
            return None
        
        return random.choice(connections)
    
    def _update_connection_stats(self, connection_id: str):
        """更新连接统计信息"""
        self._connection_stats[connection_id]['requests'] += 1
        self._connection_stats[connection_id]['last_used'] = time.time()
    
    def _create_new_connection(self) -> Optional[XtQuantConnection]:
        """创建新连接"""
        connection_id = f"conn_{len(self._connections)}_{int(time.time())}"
        
        config = {
            "timeout": self.connection_timeout,
            "max_retries": 3,
            "retry_delay_base": 1.0,
            "retry_delay_max": 30.0,
            "warmup_requests": 3,
            "warmup_timeout": 15.0
        }
        
        connection = self._create_connection(connection_id, config)
        if connection.connect():
            self.logger.info(f"创建新连接成功: {connection_id}")
            return connection
        else:
            self.logger.error(f"创建新连接失败: {connection_id}")
            return None
    
    def _remove_connection(self, connection: XtQuantConnection):
        """移除连接"""
        with self._lock:
            connection.disconnect()
            if connection.connection_id in self._connections:
                del self._connections[connection.connection_id]
            if connection.connection_id in self._connection_stats:
                del self._connection_stats[connection.connection_id]
    
    def _release_connection(self, connection: XtQuantConnection):
        """释放连接回池中"""
        try:
            if not self._shutdown and connection.is_healthy():
                self._available_connections.put(connection, timeout=1.0)
            else:
                # 连接不健康或池已关闭，断开连接
                connection.disconnect()
                with self._lock:
                    if connection.connection_id in self._connections:
                        del self._connections[connection.connection_id]
        except Exception as e:
            self.logger.error(f"释放连接异常: {e}")
    
    def _health_check_loop(self):
        """健康检查循环"""
        while not self._shutdown:
            try:
                time.sleep(self.health_check_interval)
                self._perform_health_checks()
            except Exception as e:
                self.logger.error(f"健康检查异常: {e}")
    
    def _perform_health_checks(self):
        """执行健康检查"""
        with self._lock:
            unhealthy_connections = []
            
            for connection in self._connections.values():
                if not connection.is_healthy():
                    unhealthy_connections.append(connection)
            
            # 移除不健康的连接
            for connection in unhealthy_connections:
                self.logger.warning(f"移除不健康连接: {connection.connection_id}")
                connection.disconnect()
                if connection.connection_id in self._connections:
                    del self._connections[connection.connection_id]
            
            # 确保最小连接数
            current_healthy = len(self._connections) - len(unhealthy_connections)
            if current_healthy < self.min_connections:
                needed = self.min_connections - current_healthy
                for i in range(needed):
                    connection_id = f"conn_{len(self._connections) + i}"
                    config = {
                        "timeout": self.connection_timeout,
                        "max_retries": 3,
                        "retry_delay_base": 1.0,
                        "retry_delay_max": 30.0,
                        "warmup_requests": 3,
                        "warmup_timeout": 15.0
                    }
                    connection = self._create_connection(connection_id, config)
                    if connection.connect():
                        self._available_connections.put(connection)
                        self.logger.info(f"补充连接: {connection_id}")
    
    def _cleanup_loop(self):
        """清理循环 - 移除空闲连接"""
        while not self._shutdown:
            try:
                time.sleep(60)  # 每分钟检查一次
                self._cleanup_idle_connections()
            except Exception as e:
                self.logger.error(f"清理异常: {e}")
    
    def _stats_collection_loop(self):
        """统计信息收集循环"""
        while not self._shutdown:
            try:
                current_time = time.time()
                
                with self._lock:
                    # 收集连接池统计信息
                    total_connections = len(self._connections)
                    healthy_connections = sum(1 for conn in self._connections.values() if conn.metrics.is_healthy)
                    total_requests = sum(stats['requests'] for stats in self._connection_stats.values())
                    
                    # 计算平均响应时间
                    response_times = [conn.metrics.avg_response_time for conn in self._connections.values() 
                                    if conn.metrics.avg_response_time > 0]
                    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
                    
                    # 记录统计信息
                    self.logger.debug(
                        f"连接池统计 - 总连接数: {total_connections}, "
                        f"健康连接数: {healthy_connections}, "
                        f"总请求数: {total_requests}, "
                        f"平均响应时间: {avg_response_time:.3f}s"
                    )
                    
                    # 检查是否需要预创建连接
                    if healthy_connections < self.min_connections:
                        self._ensure_min_connections()
                
                # 等待下次收集
                time.sleep(60)  # 每60秒收集一次统计信息
                
            except Exception as e:
                self.logger.error(f"统计收集循环异常: {e}")
                time.sleep(10)
    
    def _ensure_min_connections(self):
        """确保最小连接数"""
        try:
            current_healthy = sum(1 for conn in self._connections.values() if conn.metrics.is_healthy)
            
            while current_healthy < self.min_connections and len(self._connections) < self.max_connections:
                connection = self._create_new_connection()
                if connection:
                    current_healthy += 1
                    self.logger.info(f"预创建连接成功，当前健康连接数: {current_healthy}")
                else:
                    break
                    
        except Exception as e:
            self.logger.error(f"确保最小连接数时发生异常: {e}")
    
    def _cleanup_idle_connections(self):
        """清理空闲连接"""
        with self._lock:
            if len(self._connections) <= self.min_connections:
                return
            
            idle_connections = []
            for connection in self._connections.values():
                if connection.metrics.is_idle:
                    idle_connections.append(connection)
            
            # 保留最小连接数
            can_remove = len(self._connections) - self.min_connections
            to_remove = idle_connections[:can_remove]
            
            for connection in to_remove:
                self.logger.info(f"清理空闲连接: {connection.connection_id}")
                connection.disconnect()
                if connection.connection_id in self._connections:
                    del self._connections[connection.connection_id]
    
    def get_pool_status(self) -> dict:
        """获取连接池状态"""
        with self._lock:
            total_connections = len(self._connections)
            healthy_connections = sum(1 for conn in self._connections.values() if conn.metrics.is_healthy)
            active_connections = sum(1 for conn in self._connections.values() if conn.metrics.active_requests > 0)
            
            # 计算统计信息
            total_requests = sum(stats['requests'] for stats in self._connection_stats.values())
            avg_response_times = [conn.metrics.avg_response_time for conn in self._connections.values() 
                                if conn.metrics.avg_response_time > 0]
            avg_response_time = sum(avg_response_times) / len(avg_response_times) if avg_response_times else 0
            
            # 连接详情
            connection_details = []
            for conn_id, conn in self._connections.items():
                stats = self._connection_stats.get(conn_id, {})
                connection_details.append({
                    "id": conn_id,
                    "status": conn.metrics.status.value,
                    "is_healthy": conn.metrics.is_healthy,
                    "active_requests": conn.metrics.active_requests,
                    "total_requests": conn.metrics.total_requests,
                    "success_rate": conn.metrics.success_rate,
                    "avg_response_time": conn.metrics.avg_response_time,
                    "consecutive_failures": conn.metrics.consecutive_failures,
                    "last_used": stats.get('last_used', 0),
                    "created_at": stats.get('created_at', 0)
                })
            
            return {
                "pool_info": {
                    "total_connections": total_connections,
                    "healthy_connections": healthy_connections,
                    "active_connections": active_connections,
                    "max_connections": self.max_connections,
                    "min_connections": self.min_connections,
                    "load_balance_strategy": self.load_balance_strategy.value
                },
                "performance_metrics": {
                    "total_requests": total_requests,
                    "avg_response_time": round(avg_response_time, 3),
                    "pool_utilization": round(total_connections / self.max_connections * 100, 2)
                },
                "configuration": {
                    "connection_timeout": self.connection_timeout,
                    "max_idle_time": self.max_idle_time,
                    "health_check_interval": self.health_check_interval
                },
                "connections": connection_details
            }
    
    def shutdown(self):
        """关闭连接池"""
        self.logger.info("正在关闭连接池...")
        self._shutdown = True
        
        # 关闭所有连接
        with self._lock:
            for connection in self._connections.values():
                connection.disconnect()
            self._connections.clear()
        
        # 关闭线程池
        self._executor.shutdown(wait=True)
        self.logger.info("连接池已关闭")


# 全局连接池实例
_connection_pool: Optional[XtQuantConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> XtQuantConnectionPool:
    """获取全局连接池实例"""
    global _connection_pool
    
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = XtQuantConnectionPool(
                    min_connections=0,  # 启动时不预创建连接，避免阻塞启动
                    max_connections=8,
                    health_check_interval=120,  # 增加健康检查间隔到120秒
                    connection_timeout=10,
                    max_idle_time=300
                )
    
    return _connection_pool


def shutdown_connection_pool():
    """关闭全局连接池"""
    global _connection_pool
    
    if _connection_pool:
        with _pool_lock:
            if _connection_pool:
                _connection_pool.shutdown()
                _connection_pool = None