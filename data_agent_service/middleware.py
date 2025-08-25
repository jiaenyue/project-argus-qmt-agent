"""
中间件模块
包含所有自定义中间件的定义
"""

import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from .metrics import metrics_collector
from .rate_limiter import rate_limit_middleware
# from .auth_middleware import authentication_middleware
from . import auth_middleware as auth_module

logger = logging.getLogger(__name__)


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """请求追踪中间件 - 为每个请求生成唯一ID"""
    
    async def dispatch(self, request: Request, call_next):
        # 生成请求追踪ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # 设置到上下文变量中，供xtquant交互层使用
        try:
            import contextvars
            request_context = contextvars.ContextVar('request_context')
            request_context.set({
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'start_time': time.time()
            })
        except ImportError:
            # 如果contextvars不可用，使用线程本地存储
            import threading
            if not hasattr(threading.current_thread(), 'request_context'):
                threading.current_thread().request_context = {}
            threading.current_thread().request_context.update({
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'start_time': time.time()
            })
        
        response = await call_next(request)
        return response


class WindowsMetricsMiddleware(BaseHTTPMiddleware):
    """Windows兼容的指标收集中间件"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        try:
            response = await call_next(request)
            
            # 记录成功请求的指标
            status_code = response.status_code
            duration = time.time() - start_time
            
            metrics_collector.increment_request_count(
                method=request.method,
                endpoint=request.url.path,
                status_code=str(status_code)
            )
            metrics_collector.record_request_duration(
                method=request.method,
                endpoint=request.url.path,
                status_code=str(status_code),
                duration=duration
            )
            
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {status_code}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration": duration
                }
            )
            
            return response
            
        except Exception as e:
            # 记录异常
            status_code = 500
            duration = time.time() - start_time
            metrics_collector.increment_request_count(
                method=request.method,
                endpoint=request.url.path,
                status_code=str(status_code)
            )
            metrics_collector.record_request_duration(
                method=request.method,
                endpoint=request.url.path,
                status_code=str(status_code),
                duration=duration
            )
            
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration": duration
                },
                exc_info=True
            )
            
            raise e


class RateLimitMiddlewareWrapper(BaseHTTPMiddleware):
    """限流中间件包装器"""
    async def dispatch(self, request: Request, call_next):
        return await rate_limit_middleware(request, call_next)


class AuthenticationMiddlewareWrapper(BaseHTTPMiddleware):
    """认证中间件包装器"""
    async def dispatch(self, request: Request, call_next):
        # 动态引用 auth_module 中的实例，确保测试环境里的替换生效
        return await auth_module.authentication_middleware(request, call_next)