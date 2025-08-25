"""
健康检查模块
提供系统健康状态检查功能
"""

import time
import logging
from typing import Dict, Any

from .metrics import metrics_collector
from .xtquant_connection_pool import get_connection_pool

logger = logging.getLogger(__name__)


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.last_health_check = 0
        self.health_cache_ttl = 60  # 健康检查缓存60秒
        self.cached_health_status = None
    
    async def get_health_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """获取系统健康状态"""
        current_time = time.time()
        
        # 如果缓存有效且不强制刷新，返回缓存结果
        if (not force_refresh and 
            self.cached_health_status and 
            current_time - self.last_health_check < self.health_cache_ttl):
            return self.cached_health_status
        
        try:
            # 检查QMT连接状态
            qmt_status = await self._check_qmt_connection()
            
            # 获取系统指标
            system_metrics = self._get_system_metrics()
            
            # 构建健康状态响应
            health_status = {
                "status": "healthy" if qmt_status["connected"] else "unhealthy",
                "timestamp": current_time,
                "services": {
                    "qmt_connection": qmt_status,
                    "system_metrics": system_metrics
                },
                "uptime": current_time - getattr(self, 'start_time', current_time)
            }
            
            # 更新缓存
            self.cached_health_status = health_status
            self.last_health_check = current_time
            
            # 更新指标收集器
            metrics_collector.set_qmt_connection_status(1 if qmt_status["connected"] else 0)
            metrics_collector.set_api_health_status(1 if health_status["status"] == "healthy" else 0)
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            error_status = {
                "status": "error",
                "timestamp": current_time,
                "error": str(e),
                "services": {
                    "qmt_connection": {"connected": False, "error": str(e)},
                    "system_metrics": {"available": False, "error": str(e)}
                }
            }
            
            # 更新指标收集器
            metrics_collector.set_qmt_connection_status(0)
            metrics_collector.set_api_health_status(0)
            
            return error_status
    
    async def _check_qmt_connection(self) -> Dict[str, Any]:
        """检查QMT连接状态"""
        try:
            # 获取连接池实例
            connection_pool = get_connection_pool()
            
            # 获取连接池状态
            pool_status = connection_pool.get_pool_status()
            
            # 检查是否有健康的连接
            healthy_connections = pool_status["pool_info"]["healthy_connections"]
            total_connections = pool_status["pool_info"]["total_connections"]
            
            if healthy_connections > 0:
                return {
                    "connected": True,
                    "pool_status": pool_status,
                    "healthy_connections": healthy_connections,
                    "total_connections": total_connections,
                    "last_check": time.time()
                }
            else:
                return {
                    "connected": False,
                    "pool_status": pool_status,
                    "healthy_connections": healthy_connections,
                    "total_connections": total_connections,
                    "error": "No healthy connections available",
                    "last_check": time.time()
                }
                    
        except Exception as e:
            # 降低日志级别，避免过多错误信息
            logger.debug(f"QMT connection check failed: {str(e)}")
            return {
                "connected": False,
                "error": str(e),
                "last_check": time.time()
            }
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        try:
            import psutil
            
            # 获取CPU和内存使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            metrics = {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "available": True,
                "last_update": time.time()
            }
            
            # 更新指标收集器
            metrics_collector.set_system_metrics(cpu_percent, memory.percent)
            
            return metrics
            
        except ImportError:
            logger.warning("psutil not available, system metrics disabled")
            return {
                "available": False,
                "error": "psutil not installed"
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {str(e)}")
            return {
                "available": False,
                "error": str(e)
            }
    
    def set_start_time(self, start_time: float):
        """设置应用启动时间"""
        self.start_time = start_time


# 创建全局健康检查器实例
health_checker = HealthChecker()