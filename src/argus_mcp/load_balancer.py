"""
WebSocket 实时数据系统 - 负载均衡器
根据 tasks.md 任务9要求实现的负载均衡和扩展支持
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json

from .websocket_models import WebSocketMessage, MessageType

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(str, Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    CONSISTENT_HASH = "consistent_hash"
    RESOURCE_BASED = "resource_based"


class ClientPriority(str, Enum):
    """客户端优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CRITICAL = "critical"


@dataclass
class ServerNode:
    """服务器节点信息"""
    node_id: str
    host: str
    port: int
    weight: int = 1
    max_connections: int = 1000
    current_connections: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    last_heartbeat: datetime = field(default_factory=datetime.now)
    is_healthy: bool = True
    region: Optional[str] = None
    zone: Optional[str] = None


@dataclass
class ClientInfo:
    """客户端信息"""
    client_id: str
    priority: ClientPriority = ClientPriority.MEDIUM
    connection_count: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    rate_limit_tokens: int = 100
    rate_limit_reset: datetime = field(default_factory=datetime.now)
    assigned_node: Optional[str] = None


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    requests_per_minute: int = 60
    burst_size: int = 10
    priority_multipliers: Dict[ClientPriority, float] = field(default_factory=lambda: {
        ClientPriority.CRITICAL: 5.0,
        ClientPriority.HIGH: 2.0,
        ClientPriority.MEDIUM: 1.0,
        ClientPriority.LOW: 0.5
    })


class LoadBalancer:
    """负载均衡器 - 管理连接分发和资源调度"""
    
    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_CONNECTIONS,
        rate_limit_config: Optional[RateLimitConfig] = None
    ):
        self.strategy = strategy
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        
        # 服务器节点管理
        self.nodes: Dict[str, ServerNode] = {}
        self.healthy_nodes: List[str] = []
        self.round_robin_index = 0
        
        # 客户端管理
        self.clients: Dict[str, ClientInfo] = {}
        
        # 一致性哈希环（用于consistent_hash策略）
        self.hash_ring: Dict[int, str] = {}
        self.virtual_nodes = 150  # 每个物理节点的虚拟节点数
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "rejected_requests": 0,
            "load_balanced_requests": 0,
            "rate_limited_requests": 0,
            "start_time": datetime.now()
        }
        
        # 后台任务
        self._health_check_task: Optional[asyncio.Task] = None
        self._rate_limit_reset_task: Optional[asyncio.Task] = None
        self._is_running = False
        
    async def start(self) -> None:
        """启动负载均衡器"""
        if self._is_running:
            return
            
        logger.info("Starting LoadBalancer")
        self._is_running = True
        
        # 启动后台任务
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._rate_limit_reset_task = asyncio.create_task(self._rate_limit_reset_loop())
        
    async def stop(self) -> None:
        """停止负载均衡器"""
        if not self._is_running:
            return
            
        logger.info("Stopping LoadBalancer")
        self._is_running = False
        
        # 停止后台任务
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._rate_limit_reset_task:
            self._rate_limit_reset_task.cancel()
            
    def add_node(self, node: ServerNode) -> None:
        """添加服务器节点"""
        self.nodes[node.node_id] = node
        self._update_healthy_nodes()
        self._rebuild_hash_ring()
        logger.info(f"Added node {node.node_id} ({node.host}:{node.port})")
        
    def remove_node(self, node_id: str) -> None:
        """移除服务器节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self._update_healthy_nodes()
            self._rebuild_hash_ring()
            logger.info(f"Removed node {node_id}")
            
    def update_node_stats(
        self,
        node_id: str,
        connections: int,
        cpu_usage: float,
        memory_usage: float
    ) -> None:
        """更新节点统计信息"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.current_connections = connections
            node.cpu_usage = cpu_usage
            node.memory_usage = memory_usage
            node.last_heartbeat = datetime.now()
            node.is_healthy = self._check_node_health(node)
            
            self._update_healthy_nodes()
            
    async def get_node_for_client(self, client_id: str) -> Optional[ServerNode]:
        """为客户端选择最佳节点"""
        self.stats["total_requests"] += 1
        
        # 检查速率限制
        if not await self._check_rate_limit(client_id):
            self.stats["rate_limited_requests"] += 1
            return None
            
        # 检查是否有健康节点
        if not self.healthy_nodes:
            logger.error("No healthy nodes available")
            self.stats["rejected_requests"] += 1
            return None
            
        # 根据策略选择节点
        node_id = await self._select_node(client_id)
        if not node_id:
            self.stats["rejected_requests"] += 1
            return None
            
        node = self.nodes[node_id]
        
        # 检查节点容量
        if node.current_connections >= node.max_connections:
            logger.warning(f"Node {node_id} at capacity")
            # 尝试选择其他节点
            alternative_node_id = await self._select_alternative_node(client_id, node_id)
            if alternative_node_id:
                node = self.nodes[alternative_node_id]
            else:
                self.stats["rejected_requests"] += 1
                return None
                
        # 更新客户端信息
        if client_id not in self.clients:
            self.clients[client_id] = ClientInfo(client_id=client_id)
            
        client = self.clients[client_id]
        client.assigned_node = node.node_id
        client.connection_count += 1
        client.last_activity = datetime.now()
        
        # 更新节点连接数
        node.current_connections += 1
        
        self.stats["load_balanced_requests"] += 1
        
        logger.debug(f"Assigned client {client_id} to node {node.node_id}")
        return node
        
    async def release_client(self, client_id: str) -> None:
        """释放客户端连接"""
        if client_id not in self.clients:
            return
            
        client = self.clients[client_id]
        if client.assigned_node and client.assigned_node in self.nodes:
            node = self.nodes[client.assigned_node]
            node.current_connections = max(0, node.current_connections - 1)
            
        client.connection_count = max(0, client.connection_count - 1)
        if client.connection_count == 0:
            client.assigned_node = None
            
        logger.debug(f"Released client {client_id}")
        
    def set_client_priority(self, client_id: str, priority: ClientPriority) -> None:
        """设置客户端优先级"""
        if client_id not in self.clients:
            self.clients[client_id] = ClientInfo(client_id=client_id)
            
        self.clients[client_id].priority = priority
        logger.info(f"Set client {client_id} priority to {priority}")
        
    async def _check_rate_limit(self, client_id: str) -> bool:
        """检查客户端速率限制"""
        if client_id not in self.clients:
            self.clients[client_id] = ClientInfo(client_id=client_id)
            
        client = self.clients[client_id]
        now = datetime.now()
        
        # 重置令牌桶
        if now >= client.rate_limit_reset:
            multiplier = self.rate_limit_config.priority_multipliers.get(
                client.priority, 1.0
            )
            client.rate_limit_tokens = int(
                self.rate_limit_config.requests_per_minute * multiplier
            )
            client.rate_limit_reset = now + timedelta(minutes=1)
            
        # 检查令牌
        if client.rate_limit_tokens > 0:
            client.rate_limit_tokens -= 1
            return True
            
        return False
        
    async def _select_node(self, client_id: str) -> Optional[str]:
        """根据策略选择节点"""
        if not self.healthy_nodes:
            return None
            
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_select()
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections_select()
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select()
        elif self.strategy == LoadBalancingStrategy.CONSISTENT_HASH:
            return self._consistent_hash_select(client_id)
        elif self.strategy == LoadBalancingStrategy.RESOURCE_BASED:
            return self._resource_based_select()
        else:
            return self._round_robin_select()
            
    def _round_robin_select(self) -> str:
        """轮询选择"""
        if not self.healthy_nodes:
            return None
            
        node_id = self.healthy_nodes[self.round_robin_index]
        self.round_robin_index = (self.round_robin_index + 1) % len(self.healthy_nodes)
        return node_id
        
    def _least_connections_select(self) -> str:
        """最少连接选择"""
        if not self.healthy_nodes:
            return None
            
        min_connections = float('inf')
        selected_node = None
        
        for node_id in self.healthy_nodes:
            node = self.nodes[node_id]
            if node.current_connections < min_connections:
                min_connections = node.current_connections
                selected_node = node_id
                
        return selected_node
        
    def _weighted_round_robin_select(self) -> str:
        """加权轮询选择"""
        if not self.healthy_nodes:
            return None
            
        # 简化实现：根据权重重复节点ID
        weighted_nodes = []
        for node_id in self.healthy_nodes:
            node = self.nodes[node_id]
            weighted_nodes.extend([node_id] * node.weight)
            
        if not weighted_nodes:
            return self.healthy_nodes[0]
            
        node_id = weighted_nodes[self.round_robin_index % len(weighted_nodes)]
        self.round_robin_index += 1
        return node_id
        
    def _consistent_hash_select(self, client_id: str) -> str:
        """一致性哈希选择"""
        if not self.hash_ring:
            return self.healthy_nodes[0] if self.healthy_nodes else None
            
        # 计算客户端哈希值
        client_hash = int(hashlib.md5(client_id.encode()).hexdigest(), 16)
        
        # 在哈希环中找到第一个大于等于客户端哈希值的节点
        for ring_hash in sorted(self.hash_ring.keys()):
            if ring_hash >= client_hash:
                return self.hash_ring[ring_hash]
                
        # 如果没找到，返回环上的第一个节点
        return self.hash_ring[min(self.hash_ring.keys())]
        
    def _resource_based_select(self) -> str:
        """基于资源使用率选择"""
        if not self.healthy_nodes:
            return None
            
        best_score = float('inf')
        selected_node = None
        
        for node_id in self.healthy_nodes:
            node = self.nodes[node_id]
            
            # 计算综合得分（越低越好）
            connection_ratio = node.current_connections / node.max_connections
            cpu_weight = 0.4
            memory_weight = 0.3
            connection_weight = 0.3
            
            score = (
                node.cpu_usage * cpu_weight +
                node.memory_usage * memory_weight +
                connection_ratio * 100 * connection_weight
            )
            
            if score < best_score:
                best_score = score
                selected_node = node_id
                
        return selected_node
        
    async def _select_alternative_node(
        self,
        client_id: str,
        excluded_node_id: str
    ) -> Optional[str]:
        """选择替代节点"""
        available_nodes = [
            node_id for node_id in self.healthy_nodes
            if node_id != excluded_node_id and
            self.nodes[node_id].current_connections < self.nodes[node_id].max_connections
        ]
        
        if not available_nodes:
            return None
            
        # 使用最少连接策略选择替代节点
        min_connections = float('inf')
        selected_node = None
        
        for node_id in available_nodes:
            node = self.nodes[node_id]
            if node.current_connections < min_connections:
                min_connections = node.current_connections
                selected_node = node_id
                
        return selected_node
        
    def _update_healthy_nodes(self) -> None:
        """更新健康节点列表"""
        self.healthy_nodes = [
            node_id for node_id, node in self.nodes.items()
            if node.is_healthy
        ]
        logger.debug(f"Healthy nodes: {len(self.healthy_nodes)}/{len(self.nodes)}")
        
    def _check_node_health(self, node: ServerNode) -> bool:
        """检查节点健康状态"""
        now = datetime.now()
        
        # 检查心跳超时
        if now - node.last_heartbeat > timedelta(seconds=30):
            return False
            
        # 检查资源使用率
        if node.cpu_usage > 90 or node.memory_usage > 90:
            return False
            
        # 检查连接数
        if node.current_connections >= node.max_connections:
            return False
            
        return True
        
    def _rebuild_hash_ring(self) -> None:
        """重建一致性哈希环"""
        self.hash_ring.clear()
        
        for node_id in self.healthy_nodes:
            for i in range(self.virtual_nodes):
                virtual_key = f"{node_id}:{i}"
                hash_value = int(hashlib.md5(virtual_key.encode()).hexdigest(), 16)
                self.hash_ring[hash_value] = node_id
                
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self._is_running:
            try:
                await asyncio.sleep(10)  # 每10秒检查一次
                
                for node_id, node in self.nodes.items():
                    old_health = node.is_healthy
                    node.is_healthy = self._check_node_health(node)
                    
                    if old_health != node.is_healthy:
                        status = "healthy" if node.is_healthy else "unhealthy"
                        logger.info(f"Node {node_id} is now {status}")
                        
                self._update_healthy_nodes()
                self._rebuild_hash_ring()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                
    async def _rate_limit_reset_loop(self) -> None:
        """速率限制重置循环"""
        while self._is_running:
            try:
                await asyncio.sleep(60)  # 每分钟重置一次
                
                now = datetime.now()
                for client in self.clients.values():
                    if now >= client.rate_limit_reset:
                        multiplier = self.rate_limit_config.priority_multipliers.get(
                            client.priority, 1.0
                        )
                        client.rate_limit_tokens = int(
                            self.rate_limit_config.requests_per_minute * multiplier
                        )
                        client.rate_limit_reset = now + timedelta(minutes=1)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limit reset loop: {e}")
                
    def get_stats(self) -> Dict[str, Any]:
        """获取负载均衡器统计信息"""
        uptime = datetime.now() - self.stats["start_time"]
        
        return {
            "strategy": self.strategy,
            "total_nodes": len(self.nodes),
            "healthy_nodes": len(self.healthy_nodes),
            "total_clients": len(self.clients),
            "stats": {
                **self.stats,
                "uptime_seconds": uptime.total_seconds()
            },
            "nodes": {
                node_id: {
                    "host": node.host,
                    "port": node.port,
                    "current_connections": node.current_connections,
                    "max_connections": node.max_connections,
                    "cpu_usage": node.cpu_usage,
                    "memory_usage": node.memory_usage,
                    "is_healthy": node.is_healthy,
                    "weight": node.weight
                }
                for node_id, node in self.nodes.items()
            }
        }
        
    async def get_client_stats(self, client_id: str) -> Optional[Dict[str, Any]]:
        """获取客户端统计信息"""
        if client_id not in self.clients:
            return None
            
        client = self.clients[client_id]
        return {
            "client_id": client.client_id,
            "priority": client.priority,
            "connection_count": client.connection_count,
            "assigned_node": client.assigned_node,
            "rate_limit_tokens": client.rate_limit_tokens,
            "last_activity": client.last_activity.isoformat()
        }