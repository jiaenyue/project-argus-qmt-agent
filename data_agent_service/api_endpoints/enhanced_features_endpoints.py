"""
增强功能API端点
提供缓存优化、市场数据处理和连接池管理的接口
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enhanced", tags=["Enhanced Features"])

# 可选增强功能模块
try:
    from ...src.argus_mcp.advanced_cache_optimizer import get_cache_optimizer
except Exception:
    get_cache_optimizer = None

try:
    from ...src.argus_mcp.intelligent_connection_pool import get_pool_manager
except Exception:
    get_pool_manager = None

try:
    from ...src.argus_mcp.enhanced_market_data_processor import get_market_data_processor
except Exception:
    get_market_data_processor = None

# 响应模型
class CacheMetricsResponse(BaseModel):
    """缓存指标响应"""
    hit_rate: float
    miss_rate: float
    total_requests: int
    cache_size: int
    memory_usage: int
    eviction_count: int

class ConnectionPoolStatsResponse(BaseModel):
    """连接池统计响应"""
    pool_name: str
    active_connections: int
    idle_connections: int
    total_connections: int
    max_connections: int
    connection_requests: int
    failed_connections: int
    average_response_time: float

class MarketDataStatsResponse(BaseModel):
    """市场数据统计响应"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    cache_hit_rate: float
    data_freshness_score: float

class OptimizationSuggestion(BaseModel):
    """优化建议"""
    category: str
    priority: str
    description: str
    impact: str
    action: str

@router.get("/cache/metrics", response_model=CacheMetricsResponse)
async def get_cache_metrics():
    """获取缓存指标"""
    if not get_cache_optimizer:
        raise HTTPException(status_code=503, detail="Advanced cache optimizer not available")
    
    try:
        cache_optimizer = get_cache_optimizer()
        metrics = await cache_optimizer.get_metrics()
        
        return CacheMetricsResponse(
            hit_rate=metrics.get('hit_rate', 0.0),
            miss_rate=metrics.get('miss_rate', 0.0),
            total_requests=metrics.get('total_requests', 0),
            cache_size=metrics.get('cache_size', 0),
            memory_usage=metrics.get('memory_usage', 0),
            eviction_count=metrics.get('eviction_count', 0)
        )
    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache metrics: {str(e)}")

@router.post("/cache/optimize")
async def optimize_cache():
    """执行缓存优化"""
    if not get_cache_optimizer:
        raise HTTPException(status_code=503, detail="Advanced cache optimizer not available")
    
    try:
        cache_optimizer = get_cache_optimizer()
        
        # 执行缓存优化
        optimization_result = await cache_optimizer.optimize_cache()
        
        return {
            "status": "success",
            "message": "Cache optimization completed",
            "optimizations_applied": optimization_result.get('optimizations', []),
            "performance_improvement": optimization_result.get('improvement', 0)
        }
    except Exception as e:
        logger.error(f"Error optimizing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to optimize cache: {str(e)}")

@router.delete("/cache/clear")
async def clear_cache(pattern: Optional[str] = Query(None, description="缓存键模式，如果不提供则清空所有缓存")):
    """清空缓存"""
    if not get_cache_optimizer:
        raise HTTPException(status_code=503, detail="Advanced cache optimizer not available")
    
    try:
        cache_optimizer = get_cache_optimizer()
        
        if pattern:
            cleared_count = await cache_optimizer.clear_pattern(pattern)
            message = f"Cleared {cleared_count} cache entries matching pattern '{pattern}'"
        else:
            await cache_optimizer.clear_all()
            message = "All cache entries cleared"
        
        return {
            "status": "success",
            "message": message
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.get("/connection-pool/stats", response_model=List[ConnectionPoolStatsResponse])
async def get_connection_pool_stats():
    """获取连接池统计信息"""
    if not get_pool_manager:
        raise HTTPException(status_code=503, detail="Intelligent connection pool manager not available")
    
    try:
        pool_manager = get_pool_manager()
        
        stats_list = []
        pool_stats = await pool_manager.get_all_pool_stats()
        
        for pool_name, stats in pool_stats.items():
            stats_list.append(ConnectionPoolStatsResponse(
                pool_name=pool_name,
                active_connections=stats.get('active_connections', 0),
                idle_connections=stats.get('idle_connections', 0),
                total_connections=stats.get('total_connections', 0),
                max_connections=stats.get('max_connections', 0),
                connection_requests=stats.get('connection_requests', 0),
                failed_connections=stats.get('failed_connections', 0),
                average_response_time=stats.get('average_response_time', 0.0)
            ))
        
        return stats_list
    except Exception as e:
        logger.error(f"Error getting connection pool stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get connection pool stats: {str(e)}")

@router.post("/connection-pool/{pool_name}/scale")
async def scale_connection_pool(pool_name: str, target_size: int = Query(..., ge=1, le=100)):
    """手动扩缩容连接池"""
    if not get_pool_manager:
        raise HTTPException(status_code=503, detail="Intelligent connection pool manager not available")
    
    try:
        pool_manager = get_pool_manager()
        
        success = await pool_manager.scale_pool(pool_name, target_size)
        
        if success:
            return {
                "status": "success",
                "message": f"Connection pool '{pool_name}' scaled to {target_size} connections"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Connection pool '{pool_name}' not found")
    except Exception as e:
        logger.error(f"Error scaling connection pool: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to scale connection pool: {str(e)}")

@router.get("/market-data/stats", response_model=MarketDataStatsResponse)
async def get_market_data_stats():
    """获取市场数据处理统计"""
    if not get_market_data_processor:
        raise HTTPException(status_code=503, detail="Enhanced market data processor not available")
    
    try:
        processor = get_market_data_processor()
        
        if processor:
            stats = await processor.get_statistics()
            
            return MarketDataStatsResponse(
                total_requests=stats.get('total_requests', 0),
                successful_requests=stats.get('successful_requests', 0),
                failed_requests=stats.get('failed_requests', 0),
                average_response_time=stats.get('average_response_time', 0.0),
                cache_hit_rate=stats.get('cache_hit_rate', 0.0),
                data_freshness_score=stats.get('data_freshness_score', 0.0)
            )
        else:
            raise HTTPException(status_code=503, detail="Market data processor not available")
    except Exception as e:
        logger.error(f"Error getting market data stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get market data stats: {str(e)}")

@router.get("/optimization/suggestions", response_model=List[OptimizationSuggestion])
async def get_optimization_suggestions():
    """获取系统优化建议"""
    try:
        suggestions = []
        
        # 获取缓存优化建议
        if get_cache_optimizer:
            try:
                cache_optimizer = get_cache_optimizer()
                cache_suggestions = await cache_optimizer.get_optimization_suggestions()
                
                for suggestion in cache_suggestions:
                    suggestions.append(OptimizationSuggestion(
                        category="Cache",
                        priority=suggestion.get('priority', 'medium'),
                        description=suggestion.get('description', ''),
                        impact=suggestion.get('impact', ''),
                        action=suggestion.get('action', '')
                    ))
            except Exception as e:
                logger.warning(f"Failed to get cache suggestions: {e}")
        
        # 获取连接池优化建议
        if get_pool_manager:
            try:
                pool_manager = get_pool_manager()
                pool_suggestions = await pool_manager.get_optimization_suggestions()
                
                for suggestion in pool_suggestions:
                    suggestions.append(OptimizationSuggestion(
                        category="Connection Pool",
                        priority=suggestion.get('priority', 'medium'),
                        description=suggestion.get('description', ''),
                        impact=suggestion.get('impact', ''),
                        action=suggestion.get('action', '')
                    ))
            except Exception as e:
                logger.warning(f"Failed to get pool suggestions: {e}")
        
        # 获取市场数据优化建议
        if get_market_data_processor:
            try:
                processor = get_market_data_processor()
                
                if processor:
                    data_suggestions = await processor.get_optimization_suggestions()
                    
                    for suggestion in data_suggestions:
                        suggestions.append(OptimizationSuggestion(
                            category="Market Data",
                            priority=suggestion.get('priority', 'medium'),
                            description=suggestion.get('description', ''),
                            impact=suggestion.get('impact', ''),
                            action=suggestion.get('action', '')
                        ))
            except Exception as e:
                logger.warning(f"Failed to get market data suggestions: {e}")
        
        return suggestions
    except Exception as e:
        logger.error(f"Error getting optimization suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get optimization suggestions: {str(e)}")

@router.get("/health")
async def enhanced_features_health():
    """增强功能健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "features": {
                "cache_optimizer": bool(get_cache_optimizer),
                "connection_pool_manager": bool(get_pool_manager),
                "market_data_processor": bool(get_market_data_processor)
            },
            "active_features": []
        }
        
        # 检查各模块状态
        if get_cache_optimizer:
            try:
                cache_optimizer = get_cache_optimizer()
                health_status["active_features"].append("cache_optimizer")
            except Exception as e:
                logger.warning(f"Cache optimizer health check failed: {e}")
        
        if get_pool_manager:
            try:
                pool_manager = get_pool_manager()
                health_status["active_features"].append("connection_pool_manager")
            except Exception as e:
                logger.warning(f"Connection pool manager health check failed: {e}")
        
        if get_market_data_processor:
            try:
                processor = get_market_data_processor()
                health_status["active_features"].append("market_data_processor")
            except Exception as e:
                logger.warning(f"Market data processor health check failed: {e}")
        
        return health_status
    except Exception as e:
        logger.error(f"Error in enhanced features health check: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")