"""
动态连接池管理器
支持自适应连接池大小调整、负载均衡和智能路由
"""

import asyncio
import logging
import time
import statistics
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading
from contextlib import asynccontextmanager
import aiohttp
import psutil

logger = logging.getLogger(__name__)

@dataclass
class ConnectionMetrics:
    """连接指标"""
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    last_update: float = field(default_factory=time.time)

@dataclass
class PoolConfiguration:
    """连接池配置"""
    min_size: int = 5
    max_size: int = 50
    initial_size: int = 10
    timeout: float = 30.0
    max_idle_time: float = 300.0
    health_check_interval: float = 60.0
    auto_scale: bool = True
    scale_factor: float = 1.5
    scale_threshold: float = 0.8
    load_balance_strategy: str = "round_robin"  # round_robin, least_connections, weighted

@dataclass
class ServerNode:
    """服务器节点"""
    host: str
    port: int
    weight: float = 1.0
    max_connections: int = 100
    current_connections: int = 0
    health_status: bool = True
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0
    last_health_check: float = field(default_factory=time.time)

class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: str = "round_robin"):
        self.strategy = strategy
        self.current_index = 0
        self.nodes: List[ServerNode] = []
        self.lock = threading.Lock()
    
    def add_node(self, node: ServerNode):
        """添加服务器节点"""
        with self.lock:
            self.nodes.append(node)
            logger.info(f"Added server node: {node.host}:{node.port}")
    
    def remove_node(self, host: str, port: int):
        """移除服务器节点"""
        with self.lock:
            self.nodes = [n for n in self.nodes if not (n.host == host and n.port == port)]
            logger.info(f"Removed server node: {host}:{port}")
    
    def get_next_node(self) -> Optional[ServerNode]:
        """获取下一个可用节点"""
        with self.lock:
            healthy_nodes = [n for n in self.nodes if n.health_status and n.current_connections < n.max_connections]
            
            if not healthy_nodes:
                logger.warning("No healthy nodes available")
                return None
            
            if self.strategy == "round_robin":
                return self._round_robin_select(healthy_nodes)
            elif self.strategy == "least_connections":
                return self._least_connections_select(healthy_nodes)
            elif self.strategy == "weighted":
                return self._weighted_select(healthy_nodes)
            else:
                return healthy_nodes[0]
    
    def _round_robin_select(self, nodes: List[ServerNode]) -> ServerNode:
        """轮询选择"""
        node = nodes[self.current_index % len(nodes)]
        self.current_index += 1
        return node
    
    def _least_connections_select(self, nodes: List[ServerNode]) -> ServerNode:
        """最少连接选择"""
        return min(nodes, key=lambda n: n.current_connections)
    
    def _weighted_select(self, nodes: List[ServerNode]) -> ServerNode:
        """加权选择"""
        # 计算加权分数（权重 / 当前连接数）
        scores = []
        for node in nodes:
            score = node.weight / max(1, node.current_connections)
            scores.append((score, node))
        
        # 选择分数最高的节点
        return max(scores, key=lambda x: x[0])[1]
    
    def update_node_metrics(self, host: str, port: int, response_time: float, success: bool):
        """更新节点指标"""
        with self.lock:
            for node in self.nodes:
                if node.host == host and node.port == port:
                    node.response_times.append(response_time)
                    if not success:
                        node.error_count += 1
                    break

class DynamicConnectionPool:
    """动态连接池"""
    
    def __init__(self, config: PoolConfiguration):
        self.config = config
        self.connections: deque = deque()
        self.active_connections: Dict[str, Any] = {}
        self.metrics = ConnectionMetrics()
        self.load_balancer = LoadBalancer(config.load_balance_strategy)
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.running = False
        self.lock = asyncio.Lock()
        
        # 性能监控
        self.response_times = deque(maxlen=1000)
        self.error_counts = deque(maxlen=100)
        self.throughput_counter = 0
        self.last_throughput_time = time.time()
    
    async def initialize(self):
        """初始化连接池"""
        self.running = True
        
        # 创建初始连接
        for _ in range(self.config.initial_size):
            await self._create_connection()
        
        # 启动监控任务
        asyncio.create_task(self._monitor_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._auto_scale_loop())
        
        logger.info(f"Dynamic connection pool initialized with {self.config.initial_size} connections")
    
    async def shutdown(self):
        """关闭连接池"""
        self.running = False
        
        # 关闭所有连接
        async with self.lock:
            while self.connections:
                conn = self.connections.popleft()
                await self._close_connection(conn)
            
            for conn_id, conn in self.active_connections.items():
                await self._close_connection(conn)
            
            self.active_connections.clear()
        
        self.executor.shutdown(wait=True)
        logger.info("Dynamic connection pool shutdown completed")
    
    @asynccontextmanager
    async def get_connection(self):
        """获取连接（上下文管理器）"""
        connection = None
        start_time = time.time()
        
        try:
            connection = await self._acquire_connection()
            yield connection
            
            # 记录成功指标
            response_time = time.time() - start_time
            self.response_times.append(response_time)
            self.throughput_counter += 1
            
        except Exception as e:
            # 记录错误指标
            self.error_counts.append(1)
            logger.error(f"Connection error: {e}")
            raise
        
        finally:
            if connection:
                await self._release_connection(connection)
    
    async def _acquire_connection(self):
        """获取连接"""
        async with self.lock:
            # 尝试从池中获取空闲连接
            if self.connections:
                connection = self.connections.popleft()
                
                # 检查连接健康状态
                if await self._is_connection_healthy(connection):
                    conn_id = id(connection)
                    self.active_connections[conn_id] = connection
                    self.metrics.active_connections += 1
                    self.metrics.idle_connections -= 1
                    return connection
                else:
                    # 连接不健康，关闭并创建新连接
                    await self._close_connection(connection)
            
            # 如果没有可用连接，创建新连接
            if len(self.active_connections) + len(self.connections) < self.config.max_size:
                connection = await self._create_connection()
                conn_id = id(connection)
                self.active_connections[conn_id] = connection
                self.metrics.active_connections += 1
                return connection
            
            # 连接池已满，等待可用连接
            raise Exception("Connection pool exhausted")
    
    async def _release_connection(self, connection):
        """释放连接"""
        async with self.lock:
            conn_id = id(connection)
            
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]
                self.metrics.active_connections -= 1
                
                # 检查连接是否仍然健康
                if await self._is_connection_healthy(connection):
                    self.connections.append(connection)
                    self.metrics.idle_connections += 1
                else:
                    await self._close_connection(connection)
    
    async def _create_connection(self):
        """创建新连接"""
        try:
            # 获取负载均衡的服务器节点
            node = self.load_balancer.get_next_node()
            if not node:
                raise Exception("No available server nodes")
            
            # 创建HTTP连接（示例）
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30
            )
            
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
            
            # 更新节点连接数
            node.current_connections += 1
            self.metrics.total_connections += 1
            
            logger.debug(f"Created new connection to {node.host}:{node.port}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise
    
    async def _close_connection(self, connection):
        """关闭连接"""
        try:
            if hasattr(connection, 'close'):
                await connection.close()
            
            self.metrics.total_connections -= 1
            logger.debug("Connection closed")
            
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
    
    async def _is_connection_healthy(self, connection) -> bool:
        """检查连接健康状态"""
        try:
            # 简单的健康检查（可以根据具体连接类型实现）
            return not connection.closed if hasattr(connection, 'closed') else True
        except:
            return False
    
    async def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                await self._update_metrics()
                await asyncio.sleep(10)  # 每10秒更新一次指标
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(10)
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.health_check_interval)
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.config.health_check_interval)
    
    async def _auto_scale_loop(self):
        """自动扩缩容循环"""
        while self.running:
            try:
                if self.config.auto_scale:
                    await self._auto_scale()
                await asyncio.sleep(30)  # 每30秒检查一次
            except Exception as e:
                logger.error(f"Error in auto scale loop: {e}")
                await asyncio.sleep(30)
    
    async def _update_metrics(self):
        """更新指标"""
        async with self.lock:
            # 计算平均响应时间
            if self.response_times:
                self.metrics.avg_response_time = statistics.mean(self.response_times)
            
            # 计算错误率
            total_requests = len(self.response_times) + sum(self.error_counts)
            if total_requests > 0:
                self.metrics.error_rate = sum(self.error_counts) / total_requests
            
            # 计算吞吐量
            current_time = time.time()
            time_diff = current_time - self.last_throughput_time
            if time_diff > 0:
                self.metrics.throughput = self.throughput_counter / time_diff
                self.throughput_counter = 0
                self.last_throughput_time = current_time
            
            # 系统资源使用率
            self.metrics.cpu_usage = psutil.cpu_percent()
            self.metrics.memory_usage = psutil.virtual_memory().percent
            
            self.metrics.last_update = current_time
    
    async def _perform_health_checks(self):
        """执行健康检查"""
        for node in self.load_balancer.nodes:
            try:
                # 简单的健康检查（ping或HTTP请求）
                start_time = time.time()
                
                # 这里可以实现具体的健康检查逻辑
                # 例如：发送HTTP请求到健康检查端点
                
                response_time = time.time() - start_time
                node.health_status = True
                node.last_health_check = time.time()
                
                # 更新响应时间
                self.load_balancer.update_node_metrics(
                    node.host, node.port, response_time, True
                )
                
            except Exception as e:
                logger.warning(f"Health check failed for {node.host}:{node.port}: {e}")
                node.health_status = False
                self.load_balancer.update_node_metrics(
                    node.host, node.port, 0, False
                )
    
    async def _auto_scale(self):
        """自动扩缩容"""
        async with self.lock:
            current_size = len(self.connections) + len(self.active_connections)
            utilization = len(self.active_connections) / max(1, current_size)
            
            # 扩容条件
            if (utilization > self.config.scale_threshold and 
                current_size < self.config.max_size):
                
                new_connections = min(
                    int(current_size * (self.config.scale_factor - 1)),
                    self.config.max_size - current_size
                )
                
                for _ in range(new_connections):
                    try:
                        await self._create_connection()
                        logger.info(f"Auto-scaled up: added connection (total: {current_size + 1})")
                    except Exception as e:
                        logger.error(f"Failed to auto-scale up: {e}")
                        break
            
            # 缩容条件
            elif (utilization < 0.3 and 
                  current_size > self.config.min_size):
                
                connections_to_remove = min(
                    int(current_size * 0.2),
                    current_size - self.config.min_size
                )
                
                for _ in range(connections_to_remove):
                    if self.connections:
                        conn = self.connections.popleft()
                        await self._close_connection(conn)
                        self.metrics.idle_connections -= 1
                        logger.info(f"Auto-scaled down: removed connection (total: {current_size - 1})")
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取连接池指标"""
        return {
            "active_connections": self.metrics.active_connections,
            "idle_connections": self.metrics.idle_connections,
            "total_connections": self.metrics.total_connections,
            "avg_response_time": self.metrics.avg_response_time,
            "error_rate": self.metrics.error_rate,
            "throughput": self.metrics.throughput,
            "cpu_usage": self.metrics.cpu_usage,
            "memory_usage": self.metrics.memory_usage,
            "pool_utilization": self.metrics.active_connections / max(1, self.metrics.total_connections),
            "last_update": self.metrics.last_update,
            "server_nodes": [
                {
                    "host": node.host,
                    "port": node.port,
                    "weight": node.weight,
                    "current_connections": node.current_connections,
                    "health_status": node.health_status,
                    "avg_response_time": statistics.mean(node.response_times) if node.response_times else 0,
                    "error_count": node.error_count
                }
                for node in self.load_balancer.nodes
            ]
        }

class ConnectionPoolManager:
    """连接池管理器"""
    
    def __init__(self):
        self.pools: Dict[str, DynamicConnectionPool] = {}
        self.default_config = PoolConfiguration()
    
    async def create_pool(self, name: str, config: Optional[PoolConfiguration] = None) -> DynamicConnectionPool:
        """创建连接池"""
        if config is None:
            config = self.default_config
        
        pool = DynamicConnectionPool(config)
        await pool.initialize()
        
        self.pools[name] = pool
        logger.info(f"Created connection pool: {name}")
        
        return pool
    
    async def get_pool(self, name: str) -> Optional[DynamicConnectionPool]:
        """获取连接池"""
        return self.pools.get(name)
    
    async def remove_pool(self, name: str):
        """移除连接池"""
        if name in self.pools:
            await self.pools[name].shutdown()
            del self.pools[name]
            logger.info(f"Removed connection pool: {name}")
    
    async def shutdown_all(self):
        """关闭所有连接池"""
        for name, pool in self.pools.items():
            await pool.shutdown()
            logger.info(f"Shutdown connection pool: {name}")
        
        self.pools.clear()
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有连接池的指标"""
        return {
            name: pool.get_metrics()
            for name, pool in self.pools.items()
        }

# 全局连接池管理器实例
connection_pool_manager = ConnectionPoolManager()