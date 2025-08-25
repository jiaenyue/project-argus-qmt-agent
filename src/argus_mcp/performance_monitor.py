"""Argus MCP Server - Performance Monitoring.

This module provides performance monitoring and metrics collection
for the MCP server operations.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from functools import wraps
import statistics
import threading

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data."""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationStats:
    """Statistics for a specific operation."""
    name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def avg_time(self) -> float:
        """Calculate average execution time."""
        return self.total_time / self.total_calls if self.total_calls > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        return (self.success_count / self.total_calls * 100) if self.total_calls > 0 else 0.0
    
    @property
    def recent_avg_time(self) -> float:
        """Calculate recent average execution time."""
        return statistics.mean(self.recent_times) if self.recent_times else 0.0
    
    def add_execution(self, duration: float, success: bool = True):
        """Add execution data."""
        self.total_calls += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.recent_times.append(duration)
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1


class PerformanceMonitor:
    """Performance monitoring system."""
    
    def __init__(self, max_metrics: int = 10000, retention_hours: int = 24):
        """Initialize performance monitor.
        
        Args:
            max_metrics: Maximum number of metrics to retain
            retention_hours: How long to retain metrics (hours)
        """
        self.max_metrics = max_metrics
        self.retention_seconds = retention_hours * 3600
        
        self._metrics: List[PerformanceMetric] = []
        self._operation_stats: Dict[str, OperationStats] = defaultdict(lambda: OperationStats(""))
        self._lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 300  # 5 minutes
        
        # System metrics
        self._system_metrics = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "active_connections": 0,
            "cache_hit_rate": 0.0,
            "requests_per_second": 0.0
        }
    
    async def start(self):
        """Start the performance monitor."""
        logger.info("Starting performance monitor")
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """Stop the performance monitor."""
        logger.info("Stopping performance monitor")
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    def record_metric(self, name: str, value: float, metadata: Optional[Dict[str, Any]] = None):
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._metrics.append(metric)
            
            # Trim metrics if needed
            if len(self._metrics) > self.max_metrics:
                self._metrics = self._metrics[-self.max_metrics:]
    
    def record_operation(self, operation_name: str, duration: float, success: bool = True):
        """Record operation execution data."""
        with self._lock:
            if operation_name not in self._operation_stats:
                self._operation_stats[operation_name] = OperationStats(operation_name)
            
            self._operation_stats[operation_name].add_execution(duration, success)
    
    def get_operation_stats(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """Get operation statistics."""
        with self._lock:
            if operation_name:
                stats = self._operation_stats.get(operation_name)
                if stats:
                    return {
                        "name": stats.name,
                        "total_calls": stats.total_calls,
                        "avg_time": stats.avg_time,
                        "min_time": stats.min_time,
                        "max_time": stats.max_time,
                        "recent_avg_time": stats.recent_avg_time,
                        "success_rate": stats.success_rate,
                        "error_count": stats.error_count
                    }
                return {}
            
            # Return all operation stats
            result = {}
            for name, stats in self._operation_stats.items():
                result[name] = {
                    "total_calls": stats.total_calls,
                    "avg_time": stats.avg_time,
                    "min_time": stats.min_time,
                    "max_time": stats.max_time,
                    "recent_avg_time": stats.recent_avg_time,
                    "success_rate": stats.success_rate,
                    "error_count": stats.error_count
                }
            return result
    
    def get_metrics(self, name: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get performance metrics."""
        with self._lock:
            metrics = self._metrics
            
            if name:
                metrics = [m for m in metrics if m.name == name]
            
            # Return most recent metrics
            recent_metrics = metrics[-limit:] if len(metrics) > limit else metrics
            
            return [
                {
                    "name": m.name,
                    "value": m.value,
                    "timestamp": m.timestamp,
                    "metadata": m.metadata
                }
                for m in recent_metrics
            ]
    
    def update_system_metric(self, name: str, value: float):
        """Update system metric."""
        with self._lock:
            self._system_metrics[name] = value
    
    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics."""
        with self._lock:
            return self._system_metrics.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        with self._lock:
            total_operations = sum(stats.total_calls for stats in self._operation_stats.values())
            total_errors = sum(stats.error_count for stats in self._operation_stats.values())
            
            return {
                "total_metrics": len(self._metrics),
                "total_operations": total_operations,
                "total_errors": total_errors,
                "error_rate": (total_errors / total_operations * 100) if total_operations > 0 else 0.0,
                "system_metrics": self._system_metrics.copy(),
                "top_operations": self._get_top_operations(5)
            }
    
    def _get_top_operations(self, limit: int) -> List[Dict[str, Any]]:
        """Get top operations by call count."""
        sorted_ops = sorted(
            self._operation_stats.values(),
            key=lambda x: x.total_calls,
            reverse=True
        )
        
        return [
            {
                "name": op.name,
                "total_calls": op.total_calls,
                "avg_time": op.avg_time,
                "success_rate": op.success_rate
            }
            for op in sorted_ops[:limit]
        ]
    
    async def _cleanup_loop(self):
        """Background task for cleaning up old metrics."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_old_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in performance monitor cleanup: {e}")
    
    async def _cleanup_old_metrics(self):
        """Remove old metrics beyond retention period."""
        current_time = time.time()
        cutoff_time = current_time - self.retention_seconds
        
        with self._lock:
            original_count = len(self._metrics)
            self._metrics = [m for m in self._metrics if m.timestamp > cutoff_time]
            
            removed_count = original_count - len(self._metrics)
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old performance metrics")


def monitor_performance(operation_name: Optional[str] = None):
    """Decorator for monitoring function performance."""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
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
                    # Record to global monitor if available
                    monitor = get_global_monitor()
                    if monitor:
                        monitor.record_operation(op_name, duration, success)
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
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
                    # Record to global monitor if available
                    monitor = get_global_monitor()
                    if monitor:
                        monitor.record_operation(op_name, duration, success)
            
            return sync_wrapper
    
    return decorator


# Global performance monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_global_monitor() -> Optional[PerformanceMonitor]:
    """Get the global performance monitor instance."""
    return _global_monitor


def set_global_monitor(monitor: PerformanceMonitor):
    """Set the global performance monitor instance."""
    global _global_monitor
    _global_monitor = monitor


# Create default performance monitor instance
performance_monitor = PerformanceMonitor()
set_global_monitor(performance_monitor)