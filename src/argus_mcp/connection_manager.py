"""Argus MCP Server - Connection Management.

This module provides connection management capabilities including
connection pooling, health monitoring, and resource management.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

# Setup logging
logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection status enumeration."""
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class ConnectionInfo:
    """Information about a connection."""
    connection_id: str
    status: ConnectionStatus = ConnectionStatus.IDLE
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionPool:
    """Connection pool for managing multiple connections."""
    
    def __init__(self, max_connections: int = 10, max_idle_time: int = 300):
        """Initialize connection pool.
        
        Args:
            max_connections: Maximum number of connections
            max_idle_time: Maximum idle time before connection cleanup (seconds)
        """
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.connections: Dict[str, ConnectionInfo] = {}
        self.active_connections: Set[str] = set()
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_created": 0,
            "total_closed": 0,
            "total_errors": 0,
            "peak_connections": 0
        }
    
    async def start(self):
        """Start the connection pool."""
        logger.info("Starting connection pool")
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """Stop the connection pool and cleanup resources."""
        logger.info("Stopping connection pool")
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        async with self._lock:
            for conn_id in list(self.connections.keys()):
                await self._close_connection(conn_id)
    
    async def acquire_connection(self, connection_id: str) -> ConnectionInfo:
        """Acquire a connection from the pool."""
        async with self._lock:
            # Check if connection exists
            if connection_id in self.connections:
                conn_info = self.connections[connection_id]
                conn_info.status = ConnectionStatus.ACTIVE
                conn_info.last_used = time.time()
                conn_info.use_count += 1
                self.active_connections.add(connection_id)
                return conn_info
            
            # Check pool limits
            if len(self.connections) >= self.max_connections:
                # Try to cleanup idle connections
                await self._cleanup_idle_connections()
                
                if len(self.connections) >= self.max_connections:
                    raise RuntimeError(f"Connection pool limit reached: {self.max_connections}")
            
            # Create new connection
            conn_info = ConnectionInfo(
                connection_id=connection_id,
                status=ConnectionStatus.ACTIVE
            )
            
            self.connections[connection_id] = conn_info
            self.active_connections.add(connection_id)
            self._stats["total_created"] += 1
            self._stats["peak_connections"] = max(
                self._stats["peak_connections"],
                len(self.connections)
            )
            
            logger.info(f"Created new connection: {connection_id}")
            return conn_info
    
    async def release_connection(self, connection_id: str):
        """Release a connection back to the pool."""
        async with self._lock:
            if connection_id in self.connections:
                conn_info = self.connections[connection_id]
                conn_info.status = ConnectionStatus.IDLE
                conn_info.last_used = time.time()
                self.active_connections.discard(connection_id)
                logger.debug(f"Released connection: {connection_id}")
    
    async def mark_connection_error(self, connection_id: str, error: Exception):
        """Mark a connection as having an error."""
        async with self._lock:
            if connection_id in self.connections:
                conn_info = self.connections[connection_id]
                conn_info.status = ConnectionStatus.ERROR
                conn_info.error_count += 1
                conn_info.metadata["last_error"] = str(error)
                conn_info.metadata["last_error_time"] = time.time()
                self.active_connections.discard(connection_id)
                self._stats["total_errors"] += 1
                logger.warning(f"Connection error for {connection_id}: {error}")
    
    async def close_connection(self, connection_id: str):
        """Close a specific connection."""
        async with self._lock:
            await self._close_connection(connection_id)
    
    async def _close_connection(self, connection_id: str):
        """Internal method to close a connection."""
        if connection_id in self.connections:
            conn_info = self.connections[connection_id]
            conn_info.status = ConnectionStatus.CLOSED
            del self.connections[connection_id]
            self.active_connections.discard(connection_id)
            self._stats["total_closed"] += 1
            logger.info(f"Closed connection: {connection_id}")
    
    async def _cleanup_idle_connections(self):
        """Cleanup idle connections that have exceeded max idle time."""
        current_time = time.time()
        to_close = []
        
        for conn_id, conn_info in self.connections.items():
            if (conn_info.status == ConnectionStatus.IDLE and
                current_time - conn_info.last_used > self.max_idle_time):
                to_close.append(conn_id)
        
        for conn_id in to_close:
            await self._close_connection(conn_id)
            logger.info(f"Cleaned up idle connection: {conn_id}")
    
    async def _cleanup_loop(self):
        """Background task for periodic cleanup."""
        while True:
            try:
                await asyncio.sleep(60)  # Run cleanup every minute
                async with self._lock:
                    await self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return {
            **self._stats,
            "current_connections": len(self.connections),
            "active_connections": len(self.active_connections),
            "idle_connections": len(self.connections) - len(self.active_connections)
        }
    
    def get_connection_info(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get information about a specific connection."""
        return self.connections.get(connection_id)
    
    def list_connections(self) -> List[ConnectionInfo]:
        """List all connections."""
        return list(self.connections.values())


class ConnectionManager:
    """Main connection manager for the MCP server."""
    
    def __init__(self, max_connections: int = 10, max_idle_time: int = 300):
        """Initialize connection manager."""
        self.pool = ConnectionPool(max_connections, max_idle_time)
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30  # seconds
        self._unhealthy_connections: Set[str] = set()
    
    async def start(self):
        """Start the connection manager."""
        logger.info("Starting connection manager")
        await self.pool.start()
        self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop(self):
        """Stop the connection manager."""
        logger.info("Stopping connection manager")
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        await self.pool.stop()
    
    async def shutdown(self):
        """Alias for stop for backward compatibility."""
        await self.stop()
    
    async def get_connection(self, connection_id: str) -> ConnectionInfo:
        """Get a connection for use."""
        return await self.pool.acquire_connection(connection_id)
    
    async def release_connection(self, connection_id: str):
        """Release a connection after use."""
        await self.pool.release_connection(connection_id)
    
    async def handle_connection_error(self, connection_id: str, error: Exception):
        """Handle connection error."""
        await self.pool.mark_connection_error(connection_id, error)
        self._unhealthy_connections.add(connection_id)
    
    async def _health_check_loop(self):
        """Background task for connection health checks."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks on connections."""
        current_time = time.time()
        
        for conn_info in self.pool.list_connections():
            # Check for connections with too many errors
            if conn_info.error_count > 5:
                logger.warning(f"Connection {conn_info.connection_id} has too many errors, closing")
                await self.pool.close_connection(conn_info.connection_id)
                self._unhealthy_connections.discard(conn_info.connection_id)
                continue
            
            # Check for stale connections
            if (conn_info.status == ConnectionStatus.ACTIVE and
                current_time - conn_info.last_used > 600):  # 10 minutes
                logger.warning(f"Connection {conn_info.connection_id} appears stale, marking as idle")
                await self.pool.release_connection(conn_info.connection_id)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        stats = self.pool.get_stats()
        return {
            "status": "healthy" if len(self._unhealthy_connections) == 0 else "degraded",
            "pool_stats": stats,
            "unhealthy_connections": len(self._unhealthy_connections),
            "health_check_interval": self._health_check_interval
        }
    
    def is_connection_healthy(self, connection_id: str) -> bool:
        """Check if a specific connection is healthy."""
        return connection_id not in self._unhealthy_connections
    
    async def force_cleanup(self):
        """Force cleanup of all idle connections."""
        logger.info("Forcing connection cleanup")
        async with self.pool._lock:
            await self.pool._cleanup_idle_connections()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics."""
        pool_stats = self.pool.get_stats()
        return {
            **pool_stats,
            "unhealthy_connections": len(self._unhealthy_connections),
            "health_check_interval": self._health_check_interval,
            "status": "healthy" if len(self._unhealthy_connections) == 0 else "degraded"
        }