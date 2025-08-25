"""
缓存管理端点
提供缓存状态查询、清理和优化功能
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth_middleware import get_current_user
from ..response_formatter import unified_response
from ..exception_handler import exception_handler_decorator, get_global_exception_handler
from ..cache_warmup_service import get_cache_warmup_service

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/cache", tags=["缓存管理"]) 


class CacheConfig(BaseModel):
    """缓存配置模型"""
    ttl: Optional[int] = None
    max_size: Optional[int] = None
    cleanup_interval: Optional[int] = None


@router.get("/stats")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def get_cache_stats(
    current_user: dict = Depends(get_current_user)
):
    """获取缓存统计信息"""
    try:
        cache_service = get_cache_warmup_service()
        stats = await cache_service.get_cache_stats()
        
        return {
            "success": True,
            "data": stats,
            "message": "缓存统计信息获取成功"
        }
    except Exception as e:
        logger.error(f"获取缓存统计信息失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取缓存统计信息失败: {str(e)}"
        }


@router.post("/clear")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def clear_cache(
    pattern: Optional[str] = Query(None, description="缓存键模式，为空则清理所有缓存"),
    current_user: dict = Depends(get_current_user)
):
    """清理缓存"""
    try:
        cache_service = get_cache_warmup_service()
        
        if pattern:
            cleared_count = await cache_service.clear_cache_by_pattern(pattern)
            message = f"已清理匹配模式 '{pattern}' 的 {cleared_count} 个缓存项"
        else:
            cleared_count = await cache_service.clear_all_cache()
            message = f"已清理所有 {cleared_count} 个缓存项"
        
        return {
            "success": True,
            "data": {"cleared_count": cleared_count},
            "message": message
        }
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"清理缓存失败: {str(e)}"
        }


@router.post("/optimize")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def optimize_cache(
    current_user: dict = Depends(get_current_user)
):
    """优化缓存"""
    try:
        cache_service = get_cache_warmup_service()
        optimization_result = await cache_service.optimize_cache()
        
        return {
            "success": True,
            "data": optimization_result,
            "message": "缓存优化完成"
        }
    except Exception as e:
        logger.error(f"缓存优化失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"缓存优化失败: {str(e)}"
        }


@router.get("/config")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def get_cache_config(
    current_user: dict = Depends(get_current_user)
):
    """获取缓存配置"""
    try:
        cache_service = get_cache_warmup_service()
        config = await cache_service.get_cache_config()
        
        return {
            "success": True,
            "data": config,
            "message": "缓存配置获取成功"
        }
    except Exception as e:
        logger.error(f"获取缓存配置失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取缓存配置失败: {str(e)}"
        }


@router.put("/config")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def update_cache_config(
    config: CacheConfig,
    current_user: dict = Depends(get_current_user)
):
    """更新缓存配置"""
    try:
        cache_service = get_cache_warmup_service()
        
        config_dict = config.dict(exclude_unset=True)
        updated_config = await cache_service.update_cache_config(config_dict)
        
        return {
            "success": True,
            "data": updated_config,
            "message": "缓存配置更新成功"
        }
    except Exception as e:
        logger.error(f"更新缓存配置失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"更新缓存配置失败: {str(e)}"
        }


@router.get("/keys")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def get_cache_keys(
    pattern: Optional[str] = Query(None, description="缓存键模式"),
    limit: int = Query(100, description="返回数量限制"),
    current_user: dict = Depends(get_current_user)
):
    """获取缓存键列表"""
    try:
        cache_service = get_cache_warmup_service()
        keys = await cache_service.get_cache_keys(pattern=pattern, limit=limit)
        
        return {
            "success": True,
            "data": {
                "keys": keys,
                "count": len(keys),
                "pattern": pattern,
                "limit": limit
            },
            "message": "缓存键列表获取成功"
        }
    except Exception as e:
        logger.error(f"获取缓存键列表失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取缓存键列表失败: {str(e)}"
        }


@router.get("/warmup/status")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def get_warmup_status(
    current_user: dict = Depends(get_current_user)
):
    """获取缓存预热状态"""
    try:
        cache_service = get_cache_warmup_service()
        status = await cache_service.get_warmup_status()
        
        return {
            "success": True,
            "data": status,
            "message": "缓存预热状态获取成功"
        }
    except Exception as e:
        logger.error(f"获取缓存预热状态失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取缓存预热状态失败: {str(e)}"
        }


@router.post("/warmup/start")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def start_cache_warmup(
    current_user: dict = Depends(get_current_user)
):
    """启动缓存预热"""
    try:
        cache_service = get_cache_warmup_service()
        result = await cache_service.start_cache_warmup()
        
        return {
            "success": True,
            "data": result,
            "message": "缓存预热已启动"
        }
    except Exception as e:
        logger.error(f"启动缓存预热失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"启动缓存预热失败: {str(e)}"
        }


# 兼容测试所需的直接函数别名/端点
@router.post("/warmup/manual")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def manual_warmup(
    task_names: Optional[List[str]] = None,
    current_user: dict = Depends(get_current_user)
):
    """手动执行指定的缓存预热任务"""
    try:
        cache_service = get_cache_warmup_service()
        result = await cache_service.manual_warmup(task_names)
        return {
            "success": True,
            "data": result,
            "message": "手动缓存预热已执行"
        }
    except Exception as e:
        logger.error(f"手动缓存预热失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"手动缓存预热失败: {str(e)}"
        }


@router.post("/clear/by-pattern")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def clear_cache_by_pattern(
    pattern: str = Query(..., description="要清理的缓存键模式"),
    current_user: dict = Depends(get_current_user)
):
    """按模式清理缓存"""
    try:
        cache_service = get_cache_warmup_service()
        cleared_count = await cache_service.clear_cache_by_pattern(pattern)
        return {
            "success": True,
            "data": {"cleared_count": cleared_count, "pattern": pattern},
            "message": f"已清理匹配模式 '{pattern}' 的 {cleared_count} 个缓存项"
        }
    except Exception as e:
        logger.error(f"按模式清理缓存失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"按模式清理缓存失败: {str(e)}"
        }


@router.post("/clear/all")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
@unified_response
async def clear_all_cache(
    current_user: dict = Depends(get_current_user)
):
    """清理所有缓存"""
    try:
        cache_service = get_cache_warmup_service()
        cleared_count = await cache_service.clear_all_cache()
        return {
            "success": True,
            "data": {"cleared_count": cleared_count},
            "message": f"已清理所有 {cleared_count} 个缓存项"
        }
    except Exception as e:
        logger.error(f"清理所有缓存失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"清理所有缓存失败: {str(e)}"
        }