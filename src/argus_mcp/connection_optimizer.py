"""Argus MCP Server - Connection Pool Optimizer.

This module provides intelligent connection pool optimization with dynamic
scaling, load balancing, and health monitoring capabilities.
"""

import asyncio
import time
import logging
import statistics
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    CLOSING = "closing"
    CLOSED = "closed"


class LoadBalanceStrategy(Enum):
    """Load balancing strategy enumeration."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RESPONSE_TIME = "response_time"
    ADAPTIVE = "adaptive"


@dataclass
class ConnectionMetrics:
    """Connection performance metrics."""
    connection_id: str
    created_at: float
    last_used: float
    total_requests: int = 0
    active_requests: int = 0
    total_response_time: float = 0.0
    error_count: int = 0
    state: ConnectionState = ConnectionState.IDLE
    weight: float = 1.0
    health_score: float = 1.0
    
    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests
    
    @property
    def utilization(self) -> float:
        """Calculate connection utilization."""
        if self.total_requests == 0:
            return 0.0
        
        uptime = time.time() - self.created_at
        if uptime == 0:
            return 0.0
        
        return self.total_response_time / uptime


@dataclass
class PoolConfiguration:
    """Connection pool configuration."""
    min_connections: int = 2
    max_connections: int = 20
    target_utilization: float = 0.7
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.3
    health_check_interval: int = 30
    connection_timeout: int = 10
    idle_timeout: int = 300
    max_retries: int = 3
    retry_delay: float = 1.0
    load_balance_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ADAPTIVE
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: float = 0.5
    circuit_breaker_timeout: int = 60


class CircuitBreaker:
    """Circuit breaker for connection pool."""
    
    def __init__(self, failure_threshold: float = 0.5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
    
    def record_success(self):
        """Record a successful operation."""
        self.success_count += 1
        if self.state == "half-open":
            self.state = "closed"
            self.failure_count = 0
    
    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        total_requests = self.failure_count + self.success_count
        if total_requests > 0:
            failure_rate = self.failure_count / total_requests
            if failure_rate >= self.failure_threshold:
                self.state = "open"
    
    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "half-open"
                return True
            return False
        
        # half-open state
        return True
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        total_requests = self.failure_count + self.success_count
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_rate": self.failure_count / max(total_requests, 1),
            "last_failure_time": self.last_failure_time
        }


class ConnectionPoolOptimizer:
    """Intelligent connection pool optimizer with dynamic scaling and load balancing."""
    
    def __init__(self, connection_pool, config: Optional[PoolConfiguration] = None):
        """Initialize connection pool optimizer.
        
        Args:
            connection_pool: Connection pool instance to optimize
            config: Pool configuration
        """
        self.connection_pool = connection_pool
        self.config = config or PoolConfiguration()
        
        # Connection metrics tracking
        self._connection_metrics: Dict[str, ConnectionMetrics] = {}
        
        # Load balancing
        self._round_robin_index = 0
        self._load_balance_weights: Dict[str, float] = {}
        
        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            self.config.circuit_breaker_threshold,
            self.config.circuit_breaker_timeout
        ) if self.config.enable_circuit_breaker else None
        
        # Optimization tasks
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._scaling_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self._performance_history: List[Dict[str, Any]] = []
        self._optimization_stats = {
            'scale_up_events': 0,
            'scale_down_events': 0,
            'health_check_failures': 0,
            'circuit_breaker_trips': 0,
            'total_optimizations': 0,
            'start_time': time.time()
        }
        
        logger.info("Connection pool optimizer initialized")
    
    async def start(self):
        """Start the connection pool optimizer."""
        if self._running:
            logger.warning("Connection pool optimizer is already running")
            return
        
        self._running = True
        
        # Start optimization tasks
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._scaling_task = asyncio.create_task(self._scaling_loop())
        self._metrics_task = asyncio.create_task(self._metrics_collection_loop())
        
        logger.info("Connection pool optimizer started")
    
    async def stop(self):
        """Stop the connection pool optimizer."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel tasks
        for task in [self._health_check_task, self._scaling_task, self._metrics_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("Connection pool optimizer stopped")
    
    async def get_optimal_connection(self) -> Optional[Any]:
        """Get the optimal connection based on load balancing strategy."""
        if self._circuit_breaker and not self._circuit_breaker.can_execute():
            logger.warning("Circuit breaker is open, rejecting connection request")
            return None
        
        available_connections = await self._get_available_connections()
        
        if not available_connections:
            # Try to scale up if possible
            if await self._can_scale_up():
                await self._scale_up(1)
                available_connections = await self._get_available_connections()
        
        if not available_connections:
            return None
        
        # Select connection based on strategy
        connection = await self._select_connection(available_connections)
        
        if connection:
            # Update metrics
            conn_id = self._get_connection_id(connection)
            if conn_id in self._connection_metrics:
                metrics = self._connection_metrics[conn_id]
                metrics.active_requests += 1
                metrics.last_used = time.time()
                metrics.state = ConnectionState.ACTIVE
        
        return connection
    
    async def release_connection(self, connection: Any, success: bool = True, 
                               response_time: float = 0.0):
        """Release a connection and update metrics.
        
        Args:
            connection: Connection to release
            success: Whether the operation was successful
            response_time: Response time for the operation
        """
        conn_id = self._get_connection_id(connection)
        
        if conn_id in self._connection_metrics:
            metrics = self._connection_metrics[conn_id]
            metrics.active_requests = max(0, metrics.active_requests - 1)
            metrics.total_requests += 1
            metrics.total_response_time += response_time
            metrics.state = ConnectionState.IDLE
            
            if not success:
                metrics.error_count += 1
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()
            else:
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()
            
            # Update health score
            metrics.health_score = self._calculate_health_score(metrics)
        
        # Release connection back to pool
        if hasattr(self.connection_pool, 'release'):
            await self.connection_pool.release(connection)
    
    async def _get_available_connections(self) -> List[Any]:
        """Get list of available connections."""
        # This would depend on your connection pool implementation
        # For now, return a mock list
        if hasattr(self.connection_pool, 'get_available_connections'):
            return await self.connection_pool.get_available_connections()
        return []
    
    async def _select_connection(self, connections: List[Any]) -> Optional[Any]:
        """Select the best connection based on load balancing strategy."""
        if not connections:
            return None
        
        strategy = self.config.load_balance_strategy
        
        if strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._round_robin_selection(connections)
        elif strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return self._least_connections_selection(connections)
        elif strategy == LoadBalanceStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_selection(connections)
        elif strategy == LoadBalanceStrategy.RESPONSE_TIME:
            return self._response_time_selection(connections)
        elif strategy == LoadBalanceStrategy.ADAPTIVE:
            return self._adaptive_selection(connections)
        else:
            return connections[0]  # Default to first available
    
    def _round_robin_selection(self, connections: List[Any]) -> Any:
        """Round-robin connection selection."""
        if not connections:
            return None
        
        connection = connections[self._round_robin_index % len(connections)]
        self._round_robin_index += 1
        return connection
    
    def _least_connections_selection(self, connections: List[Any]) -> Any:
        """Select connection with least active connections."""
        best_connection = None
        min_active = float('inf')
        
        for conn in connections:
            conn_id = self._get_connection_id(conn)
            if conn_id in self._connection_metrics:
                active = self._connection_metrics[conn_id].active_requests
                if active < min_active:
                    min_active = active
                    best_connection = conn
            else:
                # New connection, prefer it
                return conn
        
        return best_connection or connections[0]
    
    def _weighted_round_robin_selection(self, connections: List[Any]) -> Any:
        """Weighted round-robin selection based on connection performance."""
        if not connections:
            return None
        
        # Calculate weights based on performance metrics
        weighted_connections = []
        for conn in connections:
            conn_id = self._get_connection_id(conn)
            if conn_id in self._connection_metrics:
                weight = self._connection_metrics[conn_id].health_score
            else:
                weight = 1.0
            
            weighted_connections.extend([conn] * max(1, int(weight * 10)))
        
        if weighted_connections:
            index = self._round_robin_index % len(weighted_connections)
            self._round_robin_index += 1
            return weighted_connections[index]
        
        return connections[0]
    
    def _response_time_selection(self, connections: List[Any]) -> Any:
        """Select connection with best response time."""
        best_connection = None
        best_response_time = float('inf')
        
        for conn in connections:
            conn_id = self._get_connection_id(conn)
            if conn_id in self._connection_metrics:
                response_time = self._connection_metrics[conn_id].avg_response_time
                if response_time < best_response_time:
                    best_response_time = response_time
                    best_connection = conn
            else:
                # New connection, prefer it
                return conn
        
        return best_connection or connections[0]
    
    def _adaptive_selection(self, connections: List[Any]) -> Any:
        """Adaptive selection combining multiple factors."""
        if not connections:
            return None
        
        best_connection = None
        best_score = -1
        
        for conn in connections:
            conn_id = self._get_connection_id(conn)
            if conn_id in self._connection_metrics:
                metrics = self._connection_metrics[conn_id]
                
                # Calculate composite score
                health_score = metrics.health_score
                utilization_score = 1.0 - min(metrics.utilization, 1.0)
                response_time_score = 1.0 / (1.0 + metrics.avg_response_time)
                
                composite_score = (
                    health_score * 0.4 +
                    utilization_score * 0.3 +
                    response_time_score * 0.3
                )
                
                if composite_score > best_score:
                    best_score = composite_score
                    best_connection = conn
            else:
                # New connection gets high score
                return conn
        
        return best_connection or connections[0]
    
    def _calculate_health_score(self, metrics: ConnectionMetrics) -> float:
        """Calculate health score for a connection."""
        if metrics.total_requests == 0:
            return 1.0
        
        # Factors: error rate, response time, utilization
        error_factor = 1.0 - min(metrics.error_rate, 1.0)
        
        # Normalize response time (assume 1 second is baseline)
        response_time_factor = 1.0 / (1.0 + metrics.avg_response_time)
        
        # Utilization factor (prefer moderate utilization)
        utilization = metrics.utilization
        if utilization < 0.3:
            utilization_factor = utilization / 0.3  # Underutilized
        elif utilization > 0.8:
            utilization_factor = (1.0 - utilization) / 0.2  # Overutilized
        else:
            utilization_factor = 1.0  # Optimal range
        
        health_score = (
            error_factor * 0.5 +
            response_time_factor * 0.3 +
            utilization_factor * 0.2
        )
        
        return max(0.0, min(1.0, health_score))
    
    async def _health_check_loop(self):
        """Background health check loop."""
        while self._running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.config.health_check_interval)
    
    async def _scaling_loop(self):
        """Background scaling loop."""
        while self._running:
            try:
                await self._check_scaling_needs()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scaling loop: {e}")
                await asyncio.sleep(30)
    
    async def _metrics_collection_loop(self):
        """Background metrics collection loop."""
        while self._running:
            try:
                await self._collect_performance_metrics()
                await asyncio.sleep(60)  # Collect every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(60)
    
    async def _perform_health_checks(self):
        """Perform health checks on all connections."""
        for conn_id, metrics in self._connection_metrics.items():
            try:
                # Perform health check (implementation depends on connection type)
                is_healthy = await self._check_connection_health(conn_id)
                
                if not is_healthy:
                    metrics.state = ConnectionState.ERROR
                    metrics.error_count += 1
                    self._optimization_stats['health_check_failures'] += 1
                    logger.warning(f"Health check failed for connection {conn_id}")
                else:
                    if metrics.state == ConnectionState.ERROR:
                        metrics.state = ConnectionState.IDLE
                        logger.info(f"Connection {conn_id} recovered")
                
            except Exception as e:
                logger.error(f"Error checking health of connection {conn_id}: {e}")
                metrics.state = ConnectionState.ERROR
    
    async def _check_connection_health(self, conn_id: str) -> bool:
        """Check health of a specific connection."""
        # This would depend on your connection implementation
        # For now, return True (healthy)
        return True
    
    async def _check_scaling_needs(self):
        """Check if pool needs to be scaled up or down."""
        current_size = len(self._connection_metrics)
        
        if current_size == 0:
            return
        
        # Calculate average utilization
        total_utilization = sum(
            metrics.utilization for metrics in self._connection_metrics.values()
        )
        avg_utilization = total_utilization / current_size
        
        # Check for scale up
        if (avg_utilization > self.config.scale_up_threshold and 
            await self._can_scale_up()):
            scale_amount = max(1, int(current_size * 0.2))  # Scale by 20%
            await self._scale_up(scale_amount)
        
        # Check for scale down
        elif (avg_utilization < self.config.scale_down_threshold and 
              await self._can_scale_down()):
            scale_amount = max(1, int(current_size * 0.1))  # Scale down by 10%
            await self._scale_down(scale_amount)
    
    async def _can_scale_up(self) -> bool:
        """Check if pool can be scaled up."""
        current_size = len(self._connection_metrics)
        return current_size < self.config.max_connections
    
    async def _can_scale_down(self) -> bool:
        """Check if pool can be scaled down."""
        current_size = len(self._connection_metrics)
        return current_size > self.config.min_connections
    
    async def _scale_up(self, amount: int):
        """Scale up the connection pool."""
        logger.info(f"Scaling up connection pool by {amount} connections")
        
        # This would depend on your connection pool implementation
        if hasattr(self.connection_pool, 'scale_up'):
            await self.connection_pool.scale_up(amount)
        
        self._optimization_stats['scale_up_events'] += 1
        self._optimization_stats['total_optimizations'] += 1
    
    async def _scale_down(self, amount: int):
        """Scale down the connection pool."""
        logger.info(f"Scaling down connection pool by {amount} connections")
        
        # This would depend on your connection pool implementation
        if hasattr(self.connection_pool, 'scale_down'):
            await self.connection_pool.scale_down(amount)
        
        self._optimization_stats['scale_down_events'] += 1
        self._optimization_stats['total_optimizations'] += 1
    
    async def _collect_performance_metrics(self):
        """Collect and store performance metrics."""
        current_time = time.time()
        
        # Calculate pool-wide metrics
        total_connections = len(self._connection_metrics)
        active_connections = sum(
            1 for metrics in self._connection_metrics.values()
            if metrics.active_requests > 0
        )
        
        avg_response_time = 0.0
        total_error_rate = 0.0
        avg_utilization = 0.0
        
        if total_connections > 0:
            avg_response_time = statistics.mean([
                metrics.avg_response_time for metrics in self._connection_metrics.values()
                if metrics.total_requests > 0
            ] or [0.0])
            
            total_error_rate = statistics.mean([
                metrics.error_rate for metrics in self._connection_metrics.values()
            ])
            
            avg_utilization = statistics.mean([
                metrics.utilization for metrics in self._connection_metrics.values()
            ])
        
        metrics_snapshot = {
            'timestamp': current_time,
            'total_connections': total_connections,
            'active_connections': active_connections,
            'avg_response_time': avg_response_time,
            'total_error_rate': total_error_rate,
            'avg_utilization': avg_utilization,
            'circuit_breaker_state': (
                self._circuit_breaker.get_state() if self._circuit_breaker else None
            )
        }
        
        self._performance_history.append(metrics_snapshot)
        
        # Keep only last hour of metrics
        cutoff_time = current_time - 3600
        self._performance_history = [
            m for m in self._performance_history if m['timestamp'] >= cutoff_time
        ]
    
    def _get_connection_id(self, connection: Any) -> str:
        """Get unique identifier for a connection."""
        # This would depend on your connection implementation
        return str(id(connection))
    
    def register_connection(self, connection: Any):
        """Register a new connection for tracking."""
        conn_id = self._get_connection_id(connection)
        if conn_id not in self._connection_metrics:
            self._connection_metrics[conn_id] = ConnectionMetrics(
                connection_id=conn_id,
                created_at=time.time(),
                last_used=time.time()
            )
            logger.debug(f"Registered connection: {conn_id}")
    
    def unregister_connection(self, connection: Any):
        """Unregister a connection from tracking."""
        conn_id = self._get_connection_id(connection)
        if conn_id in self._connection_metrics:
            del self._connection_metrics[conn_id]
            logger.debug(f"Unregistered connection: {conn_id}")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        current_time = time.time()
        uptime = current_time - self._optimization_stats['start_time']
        
        stats = {
            'uptime_hours': uptime / 3600,
            'total_connections': len(self._connection_metrics),
            'active_connections': sum(
                1 for metrics in self._connection_metrics.values()
                if metrics.active_requests > 0
            ),
            'optimization_events': {
                'scale_up': self._optimization_stats['scale_up_events'],
                'scale_down': self._optimization_stats['scale_down_events'],
                'health_failures': self._optimization_stats['health_check_failures'],
                'circuit_breaker_trips': self._optimization_stats['circuit_breaker_trips'],
                'total': self._optimization_stats['total_optimizations']
            },
            'performance_summary': self._get_performance_summary(),
            'circuit_breaker': (
                self._circuit_breaker.get_state() if self._circuit_breaker else None
            ),
            'configuration': {
                'min_connections': self.config.min_connections,
                'max_connections': self.config.max_connections,
                'target_utilization': self.config.target_utilization,
                'load_balance_strategy': self.config.load_balance_strategy.value
            }
        }
        
        return stats
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary from recent metrics."""
        if not self._performance_history:
            return {}
        
        recent_metrics = self._performance_history[-10:]  # Last 10 data points
        
        return {
            'avg_response_time': statistics.mean([
                m['avg_response_time'] for m in recent_metrics
            ]),
            'avg_error_rate': statistics.mean([
                m['total_error_rate'] for m in recent_metrics
            ]),
            'avg_utilization': statistics.mean([
                m['avg_utilization'] for m in recent_metrics
            ]),
            'connection_stability': statistics.stdev([
                m['total_connections'] for m in recent_metrics
            ]) if len(recent_metrics) > 1 else 0.0
        }
    
    async def force_optimization(self):
        """Force immediate optimization check."""
        logger.info("Forcing connection pool optimization")
        
        await self._perform_health_checks()
        await self._check_scaling_needs()
        await self._collect_performance_metrics()
        
        self._optimization_stats['total_optimizations'] += 1