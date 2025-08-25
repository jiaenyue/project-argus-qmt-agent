"""
基础API端点
包含健康检查、指标、连接状态等基础功能
"""

import time
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..health_check import health_checker
from ..metrics import metrics_collector
from ..xtquant_connection_pool import get_connection_pool
from ..response_formatter import unified_response

router = APIRouter()


@router.get("/")
@unified_response
async def root():
    """根端点"""
    return {"message": "Welcome to Data Agent Service"}


@router.get("/health")
@unified_response
async def health_check():
    """健康检查端点"""
    try:
        health_status = await health_checker.get_health_status()
        
        if health_status["status"] == "healthy":
            return health_status
        else:
            raise HTTPException(status_code=503, detail=health_status)
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/metrics")
@unified_response
async def get_metrics():
    """获取系统指标"""
    try:
        metrics_summary = metrics_collector.get_metrics_summary()
        return {
            "metrics": metrics_summary,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/api/v1/connection_status")
@unified_response
async def get_connection_status():
    """获取连接状态"""
    try:
        connection_pool = get_connection_pool()
        pool_status = connection_pool.get_pool_status()
        
        # 尝试获取一个连接进行测试
        test_result = {"connection_test": "failed"}
        try:
            with connection_pool.get_connection() as conn:
                if conn:
                    test_result = {"connection_test": "success"}
        except Exception as test_e:
            test_result = {"connection_test": "failed", "error": str(test_e)}
        
        return {
            "pool_status": pool_status,
            "test_result": test_result,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get connection status: {str(e)}"
        )