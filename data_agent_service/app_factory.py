"""
FastAPI应用工厂模块
负责创建和配置FastAPI应用实例
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from .https_config import security_headers_middleware
except ImportError:
    security_headers_middleware = None

try:
    from .middleware import (
        RequestTrackingMiddleware,
        WindowsMetricsMiddleware,
        RateLimitMiddlewareWrapper,
        AuthenticationMiddlewareWrapper
    )
except ImportError:
    RequestTrackingMiddleware = None
    WindowsMetricsMiddleware = None
    RateLimitMiddlewareWrapper = None
    AuthenticationMiddlewareWrapper = None

try:
    from .access_logger import AccessLogMiddleware
except ImportError:
    AccessLogMiddleware = None


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    
    # 创建FastAPI应用
    app = FastAPI(
        title="QMT Data Agent API",
        description="基于迅投QMT的金融数据代理服务API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 在生产环境中应该配置具体的域名
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # 添加安全响应头中间件
    if security_headers_middleware:
        app.add_middleware(BaseHTTPMiddleware, dispatch=security_headers_middleware)

    # 添加中间件（注意顺序很重要 - 后添加的先执行）
    if AccessLogMiddleware:
        app.add_middleware(AccessLogMiddleware)  # 访问日志（最外层）
    if RateLimitMiddlewareWrapper:
        app.add_middleware(RateLimitMiddlewareWrapper)  # 限流
    if AuthenticationMiddlewareWrapper:
        app.add_middleware(AuthenticationMiddlewareWrapper)  # 认证
    if WindowsMetricsMiddleware:
        app.add_middleware(WindowsMetricsMiddleware)  # Windows兼容指标
    if RequestTrackingMiddleware:
        app.add_middleware(RequestTrackingMiddleware)  # 请求追踪

    return app