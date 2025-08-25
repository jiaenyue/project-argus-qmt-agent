"""
连接池管理API
提供连接池监控、配置和管理的REST API接口
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from .dynamic_connection_pool import (
    connection_pool_manager,
    PoolConfiguration,
    ServerNode,
    DynamicConnectionPool
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/connection_pool", tags=["Connection Pool"])

# Pydantic模型
class PoolConfigModel(BaseModel):
    """连接池配置模型"""
    min_size: int = Field(5, ge=1, le=100, description="最小连接数")
    max_size: int = Field(50, ge=10, le=1000, description="最大连接数")
    initial_size: int = Field(10, ge=1, le=100, description="初始连接数")
    timeout: float = Field(30.0, ge=1.0, le=300.0, description="连接超时时间（秒）")
    max_idle_time: float = Field(300.0, ge=60.0, le=3600.0, description="最大空闲时间（秒）")
    health_check_interval: float = Field(60.0, ge=10.0, le=600.0, description="健康检查间隔（秒）")
    auto_scale: bool = Field(True, description="是否启用自动扩缩容")
    scale_factor: float = Field(1.5, ge=1.1, le=3.0, description="扩容因子")
    scale_threshold: float = Field(0.8, ge=0.5, le=0.95, description="扩容阈值")
    load_balance_strategy: str = Field("round_robin", description="负载均衡策略")

class ServerNodeModel(BaseModel):
    """服务器节点模型"""
    host: str = Field(..., description="服务器主机地址")
    port: int = Field(..., ge=1, le=65535, description="服务器端口")
    weight: float = Field(1.0, ge=0.1, le=10.0, description="节点权重")
    max_connections: int = Field(100, ge=1, le=1000, description="最大连接数")

class PoolCreateRequest(BaseModel):
    """创建连接池请求"""
    name: str = Field(..., description="连接池名称")
    config: PoolConfigModel = Field(..., description="连接池配置")
    server_nodes: List[ServerNodeModel] = Field([], description="服务器节点列表")

class PoolUpdateRequest(BaseModel):
    """更新连接池请求"""
    config: Optional[PoolConfigModel] = Field(None, description="连接池配置")
    server_nodes: Optional[List[ServerNodeModel]] = Field(None, description="服务器节点列表")

@router.post("/pools", summary="创建连接池")
async def create_pool(request: PoolCreateRequest):
    """创建新的连接池"""
    try:
        # 检查连接池是否已存在
        existing_pool = await connection_pool_manager.get_pool(request.name)
        if existing_pool:
            raise HTTPException(status_code=400, detail=f"Pool '{request.name}' already exists")
        
        # 转换配置
        config = PoolConfiguration(
            min_size=request.config.min_size,
            max_size=request.config.max_size,
            initial_size=request.config.initial_size,
            timeout=request.config.timeout,
            max_idle_time=request.config.max_idle_time,
            health_check_interval=request.config.health_check_interval,
            auto_scale=request.config.auto_scale,
            scale_factor=request.config.scale_factor,
            scale_threshold=request.config.scale_threshold,
            load_balance_strategy=request.config.load_balance_strategy
        )
        
        # 创建连接池
        pool = await connection_pool_manager.create_pool(request.name, config)
        
        # 添加服务器节点
        for node_config in request.server_nodes:
            node = ServerNode(
                host=node_config.host,
                port=node_config.port,
                weight=node_config.weight,
                max_connections=node_config.max_connections
            )
            pool.load_balancer.add_node(node)
        
        return {
            "success": True,
            "message": f"Connection pool '{request.name}' created successfully",
            "pool_name": request.name,
            "config": request.config.dict(),
            "server_nodes_count": len(request.server_nodes)
        }
        
    except Exception as e:
        logger.error(f"Failed to create pool '{request.name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create pool: {str(e)}")

@router.get("/pools", summary="获取所有连接池列表")
async def list_pools():
    """获取所有连接池的列表和基本信息"""
    try:
        pools_info = []
        
        for name, pool in connection_pool_manager.pools.items():
            metrics = pool.get_metrics()
            pools_info.append({
                "name": name,
                "active_connections": metrics["active_connections"],
                "idle_connections": metrics["idle_connections"],
                "total_connections": metrics["total_connections"],
                "pool_utilization": metrics["pool_utilization"],
                "health_status": "healthy" if metrics["error_rate"] < 0.1 else "degraded",
                "server_nodes_count": len(metrics["server_nodes"]),
                "last_update": metrics["last_update"]
            })
        
        return {
            "success": True,
            "pools": pools_info,
            "total_pools": len(pools_info)
        }
        
    except Exception as e:
        logger.error(f"Failed to list pools: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list pools: {str(e)}")

@router.get("/pools/{pool_name}", summary="获取连接池详细信息")
async def get_pool_details(pool_name: str):
    """获取指定连接池的详细信息"""
    try:
        pool = await connection_pool_manager.get_pool(pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail=f"Pool '{pool_name}' not found")
        
        metrics = pool.get_metrics()
        
        return {
            "success": True,
            "pool_name": pool_name,
            "metrics": metrics,
            "config": {
                "min_size": pool.config.min_size,
                "max_size": pool.config.max_size,
                "timeout": pool.config.timeout,
                "auto_scale": pool.config.auto_scale,
                "load_balance_strategy": pool.config.load_balance_strategy
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pool details for '{pool_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pool details: {str(e)}")

@router.put("/pools/{pool_name}", summary="更新连接池配置")
async def update_pool(pool_name: str, request: PoolUpdateRequest):
    """更新连接池配置"""
    try:
        pool = await connection_pool_manager.get_pool(pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail=f"Pool '{pool_name}' not found")
        
        updated_fields = []
        
        # 更新配置
        if request.config:
            pool.config.min_size = request.config.min_size
            pool.config.max_size = request.config.max_size
            pool.config.timeout = request.config.timeout
            pool.config.auto_scale = request.config.auto_scale
            pool.config.scale_factor = request.config.scale_factor
            pool.config.scale_threshold = request.config.scale_threshold
            pool.config.load_balance_strategy = request.config.load_balance_strategy
            updated_fields.append("config")
        
        # 更新服务器节点
        if request.server_nodes is not None:
            # 清除现有节点
            pool.load_balancer.nodes.clear()
            
            # 添加新节点
            for node_config in request.server_nodes:
                node = ServerNode(
                    host=node_config.host,
                    port=node_config.port,
                    weight=node_config.weight,
                    max_connections=node_config.max_connections
                )
                pool.load_balancer.add_node(node)
            
            updated_fields.append("server_nodes")
        
        return {
            "success": True,
            "message": f"Pool '{pool_name}' updated successfully",
            "updated_fields": updated_fields
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update pool '{pool_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update pool: {str(e)}")

@router.delete("/pools/{pool_name}", summary="删除连接池")
async def delete_pool(pool_name: str):
    """删除指定的连接池"""
    try:
        pool = await connection_pool_manager.get_pool(pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail=f"Pool '{pool_name}' not found")
        
        await connection_pool_manager.remove_pool(pool_name)
        
        return {
            "success": True,
            "message": f"Pool '{pool_name}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete pool '{pool_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete pool: {str(e)}")

@router.get("/pools/{pool_name}/metrics", summary="获取连接池实时指标")
async def get_pool_metrics(pool_name: str):
    """获取连接池的实时性能指标"""
    try:
        pool = await connection_pool_manager.get_pool(pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail=f"Pool '{pool_name}' not found")
        
        metrics = pool.get_metrics()
        
        return {
            "success": True,
            "pool_name": pool_name,
            "metrics": metrics,
            "timestamp": metrics["last_update"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metrics for pool '{pool_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.post("/pools/{pool_name}/scale", summary="手动扩缩容连接池")
async def scale_pool(
    pool_name: str,
    target_size: int = Body(..., ge=1, le=1000, description="目标连接数")
):
    """手动调整连接池大小"""
    try:
        pool = await connection_pool_manager.get_pool(pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail=f"Pool '{pool_name}' not found")
        
        if target_size < pool.config.min_size or target_size > pool.config.max_size:
            raise HTTPException(
                status_code=400,
                detail=f"Target size must be between {pool.config.min_size} and {pool.config.max_size}"
            )
        
        current_size = len(pool.connections) + len(pool.active_connections)
        
        if target_size > current_size:
            # 扩容
            for _ in range(target_size - current_size):
                await pool._create_connection()
        elif target_size < current_size:
            # 缩容
            async with pool.lock:
                for _ in range(current_size - target_size):
                    if pool.connections:
                        conn = pool.connections.popleft()
                        await pool._close_connection(conn)
                        pool.metrics.idle_connections -= 1
        
        new_size = len(pool.connections) + len(pool.active_connections)
        
        return {
            "success": True,
            "message": f"Pool '{pool_name}' scaled from {current_size} to {new_size} connections",
            "previous_size": current_size,
            "new_size": new_size,
            "target_size": target_size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to scale pool '{pool_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to scale pool: {str(e)}")

@router.post("/pools/{pool_name}/health_check", summary="执行连接池健康检查")
async def perform_health_check(pool_name: str):
    """手动执行连接池健康检查"""
    try:
        pool = await connection_pool_manager.get_pool(pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail=f"Pool '{pool_name}' not found")
        
        # 执行健康检查
        await pool._perform_health_checks()
        
        # 获取健康状态
        healthy_nodes = [node for node in pool.load_balancer.nodes if node.health_status]
        unhealthy_nodes = [node for node in pool.load_balancer.nodes if not node.health_status]
        
        return {
            "success": True,
            "message": f"Health check completed for pool '{pool_name}'",
            "total_nodes": len(pool.load_balancer.nodes),
            "healthy_nodes": len(healthy_nodes),
            "unhealthy_nodes": len(unhealthy_nodes),
            "node_details": [
                {
                    "host": node.host,
                    "port": node.port,
                    "health_status": node.health_status,
                    "current_connections": node.current_connections,
                    "last_health_check": node.last_health_check
                }
                for node in pool.load_balancer.nodes
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform health check for pool '{pool_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to perform health check: {str(e)}")

@router.get("/metrics/summary", summary="获取所有连接池指标摘要")
async def get_metrics_summary():
    """获取所有连接池的指标摘要"""
    try:
        all_metrics = connection_pool_manager.get_all_metrics()
        
        summary = {
            "total_pools": len(all_metrics),
            "total_connections": 0,
            "total_active_connections": 0,
            "total_idle_connections": 0,
            "avg_utilization": 0,
            "avg_response_time": 0,
            "total_error_rate": 0,
            "pools": []
        }
        
        if all_metrics:
            utilizations = []
            response_times = []
            error_rates = []
            
            for pool_name, metrics in all_metrics.items():
                summary["total_connections"] += metrics["total_connections"]
                summary["total_active_connections"] += metrics["active_connections"]
                summary["total_idle_connections"] += metrics["idle_connections"]
                
                utilizations.append(metrics["pool_utilization"])
                response_times.append(metrics["avg_response_time"])
                error_rates.append(metrics["error_rate"])
                
                summary["pools"].append({
                    "name": pool_name,
                    "connections": metrics["total_connections"],
                    "utilization": metrics["pool_utilization"],
                    "health": "healthy" if metrics["error_rate"] < 0.1 else "degraded"
                })
            
            summary["avg_utilization"] = sum(utilizations) / len(utilizations)
            summary["avg_response_time"] = sum(response_times) / len(response_times)
            summary["total_error_rate"] = sum(error_rates) / len(error_rates)
        
        return {
            "success": True,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics summary: {str(e)}")

# 导出路由
__all__ = ["router"]