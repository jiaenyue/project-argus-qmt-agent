"""
智能连接池管理器
提供动态连接池管理、负载均衡和自适应扩缩容功能
"""

import asyncio
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import statistics
import json
from concurrent.futures import ThreadPoolExecutor
import weakref

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """连接状态"""
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    CLOSED = "closed"
    CONNECTING = "connecting"

class PoolStrategy(Enum):
    """连接池策略"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    ADAPTIVE = "adaptive"

class ScalingPolicy(Enum):
    """扩缩容策略"""
    CONSERVATIVE = "conservative"  # 保守策略
    AGGRESSIVE = "aggressive"     # 激进策略
    ADAPTIVE = "adaptive"         # 自适应策略

@dataclass
class ConnectionMetrics:
    """连接指标"""
    connection_id: str
    created_at: float
    last_used: float
    total_requests: int = 0
    active_requests: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    state: ConnectionState = ConnectionState.IDLE
    weight: float = 1.0
    
    @property
    def age(self) -> float:
        """连接年龄（秒）"""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """空闲时间（秒）"""
        return time.time() - self.last_used
    
    @property
    def error_rate(self) -> float:
        """错误率"""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'connection_id': self.connection_id,
            'created_at': self.created_at,
            'last_used': self.last_used,
            'total_requests': self.total_requests,
            'active_requests': self.active_requests,
            'error_count': self.error_count,
            'avg_response_time': self.avg_response_time,
            'state': self.state.value,
            'weight': self.weight,
            'age': self.age,
            'idle_time': self.idle_time,
            'error_rate': self.error_rate
        }

@dataclass
class PoolConfiguration:
    """连接池配置"""
    min_connections: int = 5
    max_connections: int = 50
    max_idle_time: float = 300.0  # 5分钟
    max_connection_age: float = 3600.0  # 1小时
    health_check_interval: float = 60.0  # 1分钟
    scaling_check_interval: float = 30.0  # 30秒
    target_utilization: float = 0.7  # 目标利用率
    scale_up_threshold: float = 0.8  # 扩容阈值
    scale_down_threshold: float = 0.3  # 缩容阈值
    strategy: PoolStrategy = PoolStrategy.ADAPTIVE
    scaling_policy: ScalingPolicy = ScalingPolicy.ADAPTIVE
    enable_auto_scaling: bool = True
    enable_health_check: bool = True
    connection_timeout: float = 10.0
    request_timeout: float = 30.0

@dataclass
class PoolStatistics:
    """连接池统计信息"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    error_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    current_utilization: float = 0.0
    peak_utilization: float = 0.0
    scaling_events: int = 0
    last_scaling_time: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_connections': self.total_connections,
            'active_connections': self.active_connections,
            'idle_connections': self.idle_connections,
            'error_connections': self.error_connections,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'avg_response_time': self.avg_response_time,
            'current_utilization': self.current_utilization,
            'peak_utilization': self.peak_utilization,
            'success_rate': self.success_rate,
            'scaling_events': self.scaling_events,
            'last_scaling_time': self.last_scaling_time
        }

class Connection:
    """连接对象"""
    
    def __init__(self, connection_id: str, connection_factory: Callable):
        self.connection_id = connection_id
        self.connection_factory = connection_factory
        self.metrics = ConnectionMetrics(
            connection_id=connection_id,
            created_at=time.time(),
            last_used=time.time()
        )
        self._connection = None
        self._lock = asyncio.Lock()
        self._response_times = deque(maxlen=100)
    
    async def connect(self) -> bool:
        """建立连接"""
        try:
            self.metrics.state = ConnectionState.CONNECTING
            self._connection = await self.connection_factory()
            self.metrics.state = ConnectionState.IDLE
            return True
        except Exception as e:
            logger.error(f"Failed to create connection {self.connection_id}: {e}")
            self.metrics.state = ConnectionState.ERROR
            self.metrics.error_count += 1
            return False
    
    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """执行操作"""
        async with self._lock:
            if self.metrics.state != ConnectionState.IDLE:
                raise RuntimeError(f"Connection {self.connection_id} is not available")
            
            self.metrics.state = ConnectionState.ACTIVE
            self.metrics.active_requests += 1
            self.metrics.last_used = time.time()
            
            start_time = time.time()
            
            try:
                result = await operation(self._connection, *args, **kwargs)
                
                # 记录成功
                response_time = time.time() - start_time
                self._response_times.append(response_time)
                self.metrics.avg_response_time = statistics.mean(self._response_times)
                self.metrics.total_requests += 1
                
                return result
                
            except Exception as e:
                # 记录错误
                self.metrics.error_count += 1
                self.metrics.total_requests += 1
                logger.error(f"Operation failed on connection {self.connection_id}: {e}")
                raise
                
            finally:
                self.metrics.active_requests -= 1
                self.metrics.state = ConnectionState.IDLE
    
    async def health_check(self, health_check_func: Optional[Callable] = None) -> bool:
        """健康检查"""
        try:
            if health_check_func and self._connection:
                return await health_check_func(self._connection)
            return self.metrics.state != ConnectionState.ERROR
        except Exception as e:
            logger.error(f"Health check failed for connection {self.connection_id}: {e}")
            self.metrics.state = ConnectionState.ERROR
            return False
    
    async def close(self):
        """关闭连接"""
        try:
            if self._connection and hasattr(self._connection, 'close'):
                await self._connection.close()
        except Exception as e:
            logger.error(f"Error closing connection {self.connection_id}: {e}")
        finally:
            self.metrics.state = ConnectionState.CLOSED

class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: PoolStrategy = PoolStrategy.ADAPTIVE):
        self.strategy = strategy
        self._round_robin_index = 0
        self._connection_weights = {}
    
    def select_connection(self, connections: List[Connection]) -> Optional[Connection]:
        """选择连接"""
        available_connections = [
            conn for conn in connections 
            if conn.metrics.state == ConnectionState.IDLE
        ]
        
        if not available_connections:
            return None
        
        if self.strategy == PoolStrategy.ROUND_ROBIN:
            return self._round_robin_select(available_connections)
        elif self.strategy == PoolStrategy.LEAST_CONNECTIONS:
            return self._least_connections_select(available_connections)
        elif self.strategy == PoolStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(available_connections)
        elif self.strategy == PoolStrategy.ADAPTIVE:
            return self._adaptive_select(available_connections)
        else:
            return available_connections[0]
    
    def _round_robin_select(self, connections: List[Connection]) -> Connection:
        """轮询选择"""
        connection = connections[self._round_robin_index % len(connections)]
        self._round_robin_index += 1
        return connection
    
    def _least_connections_select(self, connections: List[Connection]) -> Connection:
        """最少连接选择"""
        return min(connections, key=lambda c: c.metrics.active_requests)
    
    def _weighted_round_robin_select(self, connections: List[Connection]) -> Connection:
        """加权轮询选择"""
        # 根据权重选择
        total_weight = sum(c.metrics.weight for c in connections)
        if total_weight == 0:
            return connections[0]
        
        import random
        target = random.uniform(0, total_weight)
        current_weight = 0
        
        for connection in connections:
            current_weight += connection.metrics.weight
            if current_weight >= target:
                return connection
        
        return connections[-1]
    
    def _adaptive_select(self, connections: List[Connection]) -> Connection:
        """自适应选择"""
        # 综合考虑响应时间、错误率和活跃连接数
        def score_connection(conn: Connection) -> float:
            # 响应时间权重（越小越好）
            response_score = 1.0 / (conn.metrics.avg_response_time + 0.1)
            
            # 错误率权重（越小越好）
            error_score = 1.0 / (conn.metrics.error_rate + 0.01)
            
            # 活跃连接数权重（越小越好）
            load_score = 1.0 / (conn.metrics.active_requests + 1)
            
            return response_score * error_score * load_score
        
        return max(connections, key=score_connection)

class AutoScaler:
    """自动扩缩容器"""
    
    def __init__(self, config: PoolConfiguration):
        self.config = config
        self.scaling_history = deque(maxlen=100)
        self.last_scale_time = 0
        self.cooldown_period = 60.0  # 1分钟冷却期
    
    def should_scale_up(self, stats: PoolStatistics) -> bool:
        """是否应该扩容"""
        if not self.config.enable_auto_scaling:
            return False
        
        if stats.total_connections >= self.config.max_connections:
            return False
        
        if time.time() - self.last_scale_time < self.cooldown_period:
            return False
        
        return stats.current_utilization > self.config.scale_up_threshold
    
    def should_scale_down(self, stats: PoolStatistics) -> bool:
        """是否应该缩容"""
        if not self.config.enable_auto_scaling:
            return False
        
        if stats.total_connections <= self.config.min_connections:
            return False
        
        if time.time() - self.last_scale_time < self.cooldown_period:
            return False
        
        return stats.current_utilization < self.config.scale_down_threshold
    
    def calculate_scale_amount(self, stats: PoolStatistics, scale_up: bool) -> int:
        """计算扩缩容数量"""
        if self.config.scaling_policy == ScalingPolicy.CONSERVATIVE:
            return 1
        elif self.config.scaling_policy == ScalingPolicy.AGGRESSIVE:
            if scale_up:
                return min(5, self.config.max_connections - stats.total_connections)
            else:
                return min(3, stats.total_connections - self.config.min_connections)
        else:  # ADAPTIVE
            utilization_diff = abs(stats.current_utilization - self.config.target_utilization)
            scale_factor = min(utilization_diff * 10, 3)
            return max(1, int(scale_factor))
    
    def record_scaling_event(self, scale_type: str, amount: int):
        """记录扩缩容事件"""
        self.scaling_history.append({
            'timestamp': time.time(),
            'type': scale_type,
            'amount': amount
        })
        self.last_scale_time = time.time()

class IntelligentConnectionPool:
    """智能连接池"""
    
    def __init__(self, 
                 connection_factory: Callable,
                 config: Optional[PoolConfiguration] = None,
                 health_check_func: Optional[Callable] = None):
        self.connection_factory = connection_factory
        self.config = config or PoolConfiguration()
        self.health_check_func = health_check_func
        
        # 连接管理
        self.connections: Dict[str, Connection] = {}
        self.load_balancer = LoadBalancer(self.config.strategy)
        self.auto_scaler = AutoScaler(self.config)
        
        # 统计信息
        self.stats = PoolStatistics()
        
        # 控制变量
        self._lock = asyncio.Lock()
        self._shutdown = False
        self._background_tasks = []
        
        # 监控数据
        self.utilization_history = deque(maxlen=1000)
        self.response_time_history = deque(maxlen=1000)
    
    async def initialize(self):
        """初始化连接池"""
        logger.info(f"Initializing connection pool with {self.config.min_connections} connections")
        
        # 创建初始连接
        for i in range(self.config.min_connections):
            await self._create_connection()
        
        # 启动后台任务
        if self.config.enable_health_check:
            task = asyncio.create_task(self._health_check_loop())
            self._background_tasks.append(task)
        
        if self.config.enable_auto_scaling:
            task = asyncio.create_task(self._scaling_loop())
            self._background_tasks.append(task)
        
        # 启动监控任务
        task = asyncio.create_task(self._monitoring_loop())
        self._background_tasks.append(task)
        
        logger.info("Connection pool initialized successfully")
    
    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """执行操作"""
        start_time = time.time()
        
        try:
            # 获取连接
            connection = await self._acquire_connection()
            if not connection:
                raise RuntimeError("No available connections")
            
            # 执行操作
            result = await connection.execute(operation, *args, **kwargs)
            
            # 记录成功
            response_time = time.time() - start_time
            self.response_time_history.append(response_time)
            self.stats.successful_requests += 1
            self.stats.total_requests += 1
            
            # 更新平均响应时间
            if len(self.response_time_history) > 0:
                self.stats.avg_response_time = statistics.mean(
                    list(self.response_time_history)[-100:]
                )
            
            return result
            
        except Exception as e:
            # 记录失败
            self.stats.failed_requests += 1
            self.stats.total_requests += 1
            logger.error(f"Operation execution failed: {e}")
            raise
    
    async def get_connection_metrics(self) -> List[Dict[str, Any]]:
        """获取连接指标"""
        async with self._lock:
            return [conn.metrics.to_dict() for conn in self.connections.values()]
    
    async def get_pool_statistics(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        await self._update_statistics()
        return self.stats.to_dict()
    
    async def scale_up(self, count: int = 1) -> int:
        """手动扩容"""
        async with self._lock:
            actual_count = 0
            max_new = self.config.max_connections - len(self.connections)
            count = min(count, max_new)
            
            for _ in range(count):
                if await self._create_connection():
                    actual_count += 1
            
            if actual_count > 0:
                self.auto_scaler.record_scaling_event("manual_scale_up", actual_count)
                self.stats.scaling_events += 1
                logger.info(f"Manually scaled up by {actual_count} connections")
            
            return actual_count
    
    async def scale_down(self, count: int = 1) -> int:
        """手动缩容"""
        async with self._lock:
            actual_count = 0
            max_remove = len(self.connections) - self.config.min_connections
            count = min(count, max_remove)
            
            # 选择要移除的连接（优先移除空闲时间最长的）
            idle_connections = [
                conn for conn in self.connections.values()
                if conn.metrics.state == ConnectionState.IDLE
            ]
            
            idle_connections.sort(key=lambda c: c.metrics.idle_time, reverse=True)
            
            for i in range(min(count, len(idle_connections))):
                conn = idle_connections[i]
                await self._remove_connection(conn.connection_id)
                actual_count += 1
            
            if actual_count > 0:
                self.auto_scaler.record_scaling_event("manual_scale_down", actual_count)
                self.stats.scaling_events += 1
                logger.info(f"Manually scaled down by {actual_count} connections")
            
            return actual_count
    
    async def health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        healthy_count = 0
        unhealthy_count = 0
        
        for connection in self.connections.values():
            is_healthy = await connection.health_check(self.health_check_func)
            if is_healthy:
                healthy_count += 1
            else:
                unhealthy_count += 1
        
        return {
            'total_connections': len(self.connections),
            'healthy_connections': healthy_count,
            'unhealthy_connections': unhealthy_count,
            'health_rate': healthy_count / len(self.connections) if self.connections else 0
        }
    
    async def shutdown(self):
        """关闭连接池"""
        logger.info("Shutting down connection pool")
        self._shutdown = True
        
        # 取消后台任务
        for task in self._background_tasks:
            task.cancel()
        
        # 等待任务完成
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # 关闭所有连接
        async with self._lock:
            for connection in self.connections.values():
                await connection.close()
            self.connections.clear()
        
        logger.info("Connection pool shutdown completed")
    
    # 私有方法
    async def _acquire_connection(self) -> Optional[Connection]:
        """获取连接"""
        async with self._lock:
            connection = self.load_balancer.select_connection(
                list(self.connections.values())
            )
            return connection
    
    async def _create_connection(self) -> bool:
        """创建新连接"""
        connection_id = f"conn_{len(self.connections)}_{int(time.time())}"
        connection = Connection(connection_id, self.connection_factory)
        
        if await connection.connect():
            self.connections[connection_id] = connection
            logger.debug(f"Created connection {connection_id}")
            return True
        else:
            logger.error(f"Failed to create connection {connection_id}")
            return False
    
    async def _remove_connection(self, connection_id: str):
        """移除连接"""
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            await connection.close()
            del self.connections[connection_id]
            logger.debug(f"Removed connection {connection_id}")
    
    async def _update_statistics(self):
        """更新统计信息"""
        total_connections = len(self.connections)
        active_connections = sum(
            1 for conn in self.connections.values()
            if conn.metrics.state == ConnectionState.ACTIVE
        )
        idle_connections = sum(
            1 for conn in self.connections.values()
            if conn.metrics.state == ConnectionState.IDLE
        )
        error_connections = sum(
            1 for conn in self.connections.values()
            if conn.metrics.state == ConnectionState.ERROR
        )
        
        self.stats.total_connections = total_connections
        self.stats.active_connections = active_connections
        self.stats.idle_connections = idle_connections
        self.stats.error_connections = error_connections
        
        # 计算利用率
        if total_connections > 0:
            self.stats.current_utilization = active_connections / total_connections
            self.stats.peak_utilization = max(
                self.stats.peak_utilization, 
                self.stats.current_utilization
            )
        
        # 记录利用率历史
        self.utilization_history.append(self.stats.current_utilization)
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                if self._shutdown:
                    break
                
                # 检查连接健康状态
                unhealthy_connections = []
                
                for connection in list(self.connections.values()):
                    # 检查连接年龄
                    if connection.metrics.age > self.config.max_connection_age:
                        unhealthy_connections.append(connection.connection_id)
                        continue
                    
                    # 检查空闲时间
                    if (connection.metrics.state == ConnectionState.IDLE and
                        connection.metrics.idle_time > self.config.max_idle_time):
                        unhealthy_connections.append(connection.connection_id)
                        continue
                    
                    # 执行健康检查
                    if not await connection.health_check(self.health_check_func):
                        unhealthy_connections.append(connection.connection_id)
                
                # 移除不健康的连接
                async with self._lock:
                    for conn_id in unhealthy_connections:
                        await self._remove_connection(conn_id)
                        logger.info(f"Removed unhealthy connection {conn_id}")
                
                # 确保最小连接数
                current_count = len(self.connections)
                if current_count < self.config.min_connections:
                    needed = self.config.min_connections - current_count
                    for _ in range(needed):
                        await self._create_connection()
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _scaling_loop(self):
        """扩缩容循环"""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.scaling_check_interval)
                
                if self._shutdown:
                    break
                
                await self._update_statistics()
                
                # 检查是否需要扩容
                if self.auto_scaler.should_scale_up(self.stats):
                    scale_amount = self.auto_scaler.calculate_scale_amount(
                        self.stats, scale_up=True
                    )
                    actual_scaled = await self.scale_up(scale_amount)
                    if actual_scaled > 0:
                        logger.info(f"Auto-scaled up by {actual_scaled} connections")
                
                # 检查是否需要缩容
                elif self.auto_scaler.should_scale_down(self.stats):
                    scale_amount = self.auto_scaler.calculate_scale_amount(
                        self.stats, scale_up=False
                    )
                    actual_scaled = await self.scale_down(scale_amount)
                    if actual_scaled > 0:
                        logger.info(f"Auto-scaled down by {actual_scaled} connections")
                
            except Exception as e:
                logger.error(f"Error in scaling loop: {e}")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while not self._shutdown:
            try:
                await asyncio.sleep(10)  # 每10秒更新一次
                
                if self._shutdown:
                    break
                
                await self._update_statistics()
                
                # 记录监控数据
                if len(self.utilization_history) % 60 == 0:  # 每10分钟记录一次详细日志
                    logger.info(
                        f"Pool stats - Total: {self.stats.total_connections}, "
                        f"Active: {self.stats.active_connections}, "
                        f"Utilization: {self.stats.current_utilization:.2%}, "
                        f"Success rate: {self.stats.success_rate:.2%}"
                    )
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

# 连接池管理器
class ConnectionPoolManager:
    """连接池管理器"""
    
    def __init__(self):
        self.pools: Dict[str, IntelligentConnectionPool] = {}
        self._lock = asyncio.Lock()
    
    async def create_pool(self, 
                         pool_name: str,
                         connection_factory: Callable,
                         config: Optional[PoolConfiguration] = None,
                         health_check_func: Optional[Callable] = None) -> IntelligentConnectionPool:
        """创建连接池"""
        async with self._lock:
            if pool_name in self.pools:
                raise ValueError(f"Pool {pool_name} already exists")
            
            pool = IntelligentConnectionPool(
                connection_factory=connection_factory,
                config=config,
                health_check_func=health_check_func
            )
            
            await pool.initialize()
            self.pools[pool_name] = pool
            
            logger.info(f"Created connection pool: {pool_name}")
            return pool
    
    async def get_pool(self, pool_name: str) -> Optional[IntelligentConnectionPool]:
        """获取连接池"""
        return self.pools.get(pool_name)
    
    async def remove_pool(self, pool_name: str) -> bool:
        """移除连接池"""
        async with self._lock:
            if pool_name not in self.pools:
                return False
            
            pool = self.pools[pool_name]
            await pool.shutdown()
            del self.pools[pool_name]
            
            logger.info(f"Removed connection pool: {pool_name}")
            return True
    
    async def get_all_pools_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有连接池统计信息"""
        stats = {}
        for pool_name, pool in self.pools.items():
            stats[pool_name] = await pool.get_pool_statistics()
        return stats
    
    async def shutdown_all(self):
        """关闭所有连接池"""
        for pool_name in list(self.pools.keys()):
            await self.remove_pool(pool_name)

# 全局连接池管理器实例
_pool_manager: Optional[ConnectionPoolManager] = None

def get_pool_manager() -> ConnectionPoolManager:
    """获取连接池管理器实例"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = ConnectionPoolManager()
    return _pool_manager

async def create_connection_pool(pool_name: str,
                               connection_factory: Callable,
                               config: Optional[PoolConfiguration] = None,
                               health_check_func: Optional[Callable] = None) -> IntelligentConnectionPool:
    """创建连接池的便捷函数"""
    manager = get_pool_manager()
    return await manager.create_pool(
        pool_name=pool_name,
        connection_factory=connection_factory,
        config=config,
        health_check_func=health_check_func
    )