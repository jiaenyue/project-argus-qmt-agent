"""
数据存储API端点
包含所有数据存储相关的API端点
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from ..auth_middleware import get_current_user
from ..auth_middleware import require_permissions
from ..response_formatter import unified_response
from ..exception_handler import exception_handler_decorator, get_global_exception_handler
from ..data_storage_service import get_data_storage_service
from ..data_compression_service import get_compression_service

from ..memory_optimizer import GCMode, GCConfig, GarbageCollector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["数据存储"])


@router.get("/storage/stats")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def get_storage_stats(
    current_user: dict = Depends(get_current_user)
):
    """获取数据存储统计信息"""
    try:
        storage_service = get_data_storage_service()
        stats = await storage_service.get_storage_stats()
        return {
            "success": True,
            "data": stats,
            "message": "获取存储统计信息成功"
        }
    except Exception as e:
        logger.error(f"获取存储统计信息失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取存储统计信息失败: {str(e)}"
        }


@router.get("/storage/compression/stats")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def get_compression_stats(
    current_user: dict = Depends(get_current_user)
):
    """获取数据压缩统计信息"""
    try:
        compression_service = get_compression_service()
        stats = await compression_service.get_compression_stats()
        return {
            "success": True,
            "data": stats,
            "message": "获取压缩统计信息成功"
        }
    except Exception as e:
        logger.error(f"获取压缩统计信息失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取压缩统计信息失败: {str(e)}"
        }


@router.get("/storage/backup/stats")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def get_backup_stats(
    current_user: dict = Depends(get_current_user)
):
    """获取备份统计信息"""
    try:
        storage_service = get_data_storage_service()
        stats = await storage_service.get_backup_stats()
        return {
            "success": True,
            "data": stats,
            "message": "获取备份统计信息成功"
        }
    except Exception as e:
        logger.error(f"获取备份统计信息失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取备份统计信息失败: {str(e)}"
        }


@router.post("/storage/backup/trigger")
@require_permissions(["write:storage"])
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def trigger_manual_backup(
    current_user: dict = Depends(get_current_user)
):
    """手动触发备份"""
    try:
        storage_service = get_data_storage_service()
        result = await storage_service.trigger_manual_backup()
        return {
            "success": True,
            "data": result,
            "message": "手动备份触发成功"
        }
    except Exception as e:
        logger.error(f"手动备份触发失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"手动备份触发失败: {str(e)}"
        }


@router.post("/storage/archive/trigger")
@require_permissions(["write:storage"])
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def trigger_manual_archive(
    current_user: dict = Depends(get_current_user)
):
    """手动触发归档"""
    try:
        storage_service = get_data_storage_service()
        result = await storage_service.trigger_manual_archive()
        return {
            "success": True,
            "data": result,
            "message": "手动归档触发成功"
        }
    except Exception as e:
        logger.error(f"手动归档触发失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"手动归档触发失败: {str(e)}"
        }


# 内存优化相关端点
@router.get("/memory_optimizer/status")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def get_memory_optimizer_status(
    current_user: dict = Depends(get_current_user)
):
    """获取内存优化器状态"""
    try:
        status = memory_optimizer.get_status()
        return {
            "success": True,
            "data": status,
            "message": "获取内存优化器状态成功"
        }
    except Exception as e:
        logger.error(f"获取内存优化器状态失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取内存优化器状态失败: {str(e)}"
        }


@router.post("/memory_optimizer/optimize")
@require_permissions(["write:system"])
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def optimize_memory(
    current_user: dict = Depends(get_current_user)
):
    """执行内存优化"""
    try:
        results = memory_optimizer.optimize_memory()
        return {
            "success": True,
            "data": {
                "memory_saved": results.get("memory_saved", 0),
                "objects_cleaned": results.get("objects_cleaned", 0),
                "cache_cleared": results.get("cache_cleared", False),
                "gc_collected": results.get("gc_collected", 0)
            },
            "message": f"内存优化完成，节省内存: {results['memory_saved'] / (1024**2):.2f} MB" if results["memory_saved"] else "内存优化完成"
        }
    except Exception as e:
        logger.error(f"内存优化失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"内存优化失败: {str(e)}"
        }


@router.get("/memory_optimizer/gc_stats")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def get_gc_stats(
    current_user: dict = Depends(get_current_user)
):
    """获取垃圾回收统计"""
    try:
        stats = memory_optimizer.gc_optimizer.get_gc_stats()
        return {
            "success": True,
            "data": stats,
            "message": "获取垃圾回收统计成功"
        }
    except Exception as e:
        logger.error(f"获取垃圾回收统计失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"获取垃圾回收统计失败: {str(e)}"
        }


@router.post("/memory_optimizer/force_gc")
@require_permissions(["write:system"])
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def force_garbage_collection(
    generation: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """强制垃圾回收"""
    try:
        if generation is not None:
            if generation not in [0, 1, 2]:
                return {
                    "success": False,
                    "data": None,
                    "message": "无效的代数，支持的代数: 0, 1, 2"
                }
            collected = memory_optimizer.gc_optimizer.collect_generation(generation)
            return {
                "success": True,
                "data": {
                    "generation": generation,
                    "collected_objects": collected
                },
                "message": f"第{generation}代垃圾回收完成，收集了 {collected} 个对象"
            }
        else:
            results = memory_optimizer.gc_optimizer.force_collect_all()
            total_collected = sum(results.values())
            return {
                "success": True,
                "data": {
                    "results_by_generation": results,
                    "total_collected": total_collected
                },
                "message": f"全面垃圾回收完成，总共收集了 {total_collected} 个对象"
            }
    except Exception as e:
        logger.error(f"强制垃圾回收失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"强制垃圾回收失败: {str(e)}"
        }


@router.post("/memory_optimizer/update_gc_config")
@require_permissions(["write:system"])
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def update_gc_config(
    mode: str = "balanced",
    threshold_0: int = 700,
    threshold_1: int = 10,
    threshold_2: int = 10,
    auto_collect: bool = True,
    collect_interval: float = 30.0,
    memory_threshold: float = 80.0,
    force_collect_threshold: float = 90.0,
    current_user: dict = Depends(get_current_user)
):
    """更新垃圾回收配置"""
    try:
        # 验证模式
        try:
            gc_mode = GCMode[mode.upper()]
        except KeyError:
            return {
                "success": False,
                "data": None,
                "message": f"无效的GC模式: {mode}，支持的模式: conservative, balanced, aggressive, custom"
            }
        
        # 创建新配置
        new_config = GCConfig(
            mode=gc_mode,
            thresholds=(threshold_0, threshold_1, threshold_2),
            auto_collect=auto_collect,
            collect_interval=collect_interval,
            memory_threshold=memory_threshold,
            force_collect_threshold=force_collect_threshold
        )
        
        # 停止当前GC优化器
        memory_optimizer.gc_optimizer.stop_auto_collection()
        
        # 创建新的GC优化器
        memory_optimizer.gc_optimizer = GarbageCollector(new_config)
        
        # 启动新的GC优化器
        memory_optimizer.gc_optimizer.start_auto_collection()
        
        return {
            "success": True,
            "data": {
                "mode": gc_mode.value,
                "thresholds": new_config.thresholds,
                "auto_collect": new_config.auto_collect,
                "collect_interval": new_config.collect_interval,
                "memory_threshold": new_config.memory_threshold,
                "force_collect_threshold": new_config.force_collect_threshold
            },
            "message": "垃圾回收配置已更新"
        }
    except Exception as e:
        logger.error(f"更新垃圾回收配置失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"更新垃圾回收配置失败: {str(e)}"
        }


@router.get("/memory_optimizer/optimization_report")
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
@unified_response
async def get_optimization_report(
    current_user: dict = Depends(get_current_user)
):
    """生成优化报告"""
    try:
        report = memory_optimizer.generate_optimization_report()
        return {
            "success": True,
            "data": report,
            "message": "生成优化报告成功"
        }
    except Exception as e:
        logger.error(f"生成优化报告失败: {e}")
        return {
            "success": False,
            "data": None,
            "message": f"生成优化报告失败: {str(e)}"
        }