# -*- coding: utf-8 -*-
"""
主应用入口，统一注册路由与中间件
"""
import os
import sys
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api_endpoints.basic_endpoints import router as basic_router
from .api_endpoints.market_data_endpoints import router as market_data_router
from .api_endpoints.data_storage_endpoints import router as storage_router

# 引入自定义中间件包装器
from .middleware import (
    RequestTrackingMiddleware,
    AuthenticationMiddlewareWrapper,
    RateLimitMiddlewareWrapper,
    WindowsMetricsMiddleware,
)

# 可选增强路由模块（若存在则加载）
try:
    from .api_endpoints.websocket_endpoints import router as websocket_router
except Exception:
    websocket_router = None

try:
    from .api_endpoints.connection_pool_api import router as connection_pool_router
except Exception:
    connection_pool_router = None

# 可选增强功能模块（从src.argus_mcp包）
try:
    from ..src.argus_mcp.enhanced_market_data_processor import get_market_data_processor
except Exception:
    get_market_data_processor = None

try:
    from ..src.argus_mcp.intelligent_connection_pool import get_dynamic_connection_pool
except Exception:
    get_dynamic_connection_pool = None

try:
    from ..src.argus_mcp.advanced_cache_optimizer import get_advanced_cache
except Exception:
    get_advanced_cache = None

logger = logging.getLogger(__name__)

app = FastAPI(title="Argus Data Agent Service", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安装自定义中间件（顺序很重要）
# 1) 请求追踪 -> 2) 认证 -> 3) 限流 -> 4) 指标收集
app.add_middleware(RequestTrackingMiddleware)
app.add_middleware(AuthenticationMiddlewareWrapper)
app.add_middleware(RateLimitMiddlewareWrapper)
app.add_middleware(WindowsMetricsMiddleware)

# 注册基础路由 - basic_router has no prefix, market_data_router has /api/v1 prefix
app.include_router(basic_router)  # includes / and /health
app.include_router(market_data_router)  # includes /api/v1/* endpoints
app.include_router(storage_router)  # includes /api/v1/storage/* endpoints

# 注册可选增强路由（存在时）
if websocket_router is not None:
    app.include_router(websocket_router, prefix="/ws")
if connection_pool_router is not None:
    app.include_router(connection_pool_router, prefix="/api/pool")

# 使用 lifespan 取代已弃用的 on_event 钩子
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("服务启动中...")
    if get_market_data_processor:
        try:
            processor = get_market_data_processor()
            logger.info("增强行情处理器已加载")
        except Exception as e:
            logger.warning(f"加载增强行情处理器失败: {e}")
    if get_dynamic_connection_pool:
        try:
            pool = await get_dynamic_connection_pool()
            logger.info("智能连接池已初始化")
        except Exception as e:
            logger.warning(f"初始化智能连接池失败: {e}")
    if get_advanced_cache:
        try:
            cache = await get_advanced_cache()
            logger.info("高级缓存已初始化")
        except Exception as e:
            logger.warning(f"初始化高级缓存失败: {e}")
    try:
        yield
    finally:
        logger.info("服务关闭中...")

# 将 lifespan 绑定到应用
app.router.lifespan_context = lifespan

# 移除 on_event（使用 lifespan 处理）
# @app.on_event("startup")
# async def on_startup():
#     ...
#
# @app.on_event("shutdown")
# async def on_shutdown():
#     ...

# 根路由 - note: basic_router already defines "/" so this may conflict
# Remove this to avoid conflicts since basic_router handles "/"
# @app.get("/")
# async def root():
#     return {"message": "Argus Data Agent Service is running"}
