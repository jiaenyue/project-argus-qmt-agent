import logging
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import Request, Response
import asyncio
from .security_config import security_config
from .monitoring_config import setup_logging, get_monitoring_config

# 使用统一的结构化格式器，从monitoring_config导入

class AccessLogger:
    """API访问日志记录器"""
    
    def __init__(self):
        self.security_config = security_config
        self.monitoring_config = get_monitoring_config()
        self.logging_config = self.monitoring_config["logging"]
        
        # 使用统一的日志配置设置各个logger
        self.access_logger = setup_logging(self.logging_config, "api_access")
        self.security_logger = setup_logging(self.logging_config, "api_security")
        self.performance_logger = setup_logging(self.logging_config, "api_performance")
        
        # 设置日志级别
        self.access_logger.setLevel(logging.INFO)
        self.security_logger.setLevel(logging.WARNING)
        self.performance_logger.setLevel(logging.INFO)
    
    # 移除_setup_handlers方法，因为现在使用统一的setup_logging函数
    
    def generate_request_id(self) -> str:
        """生成请求ID"""
        return str(uuid.uuid4())
    
    def get_client_info(self, request: Request) -> Dict[str, Any]:
        """获取客户端信息"""
        # 获取客户端IP
        client_ip = "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.headers.get("X-Real-IP"):
            client_ip = request.headers.get("X-Real-IP")
        elif request.client:
            client_ip = request.client.host
        
        return {
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "referer": request.headers.get("Referer", ""),
            "accept_language": request.headers.get("Accept-Language", ""),
            "content_type": request.headers.get("Content-Type", ""),
            "content_length": request.headers.get("Content-Length", "0")
        }
    
    def get_auth_info(self, request: Request) -> Dict[str, Any]:
        """获取认证信息"""
        auth_info = {
            "authenticated": False,
            "auth_method": "none",
            "api_key_name": None,
            "permissions": []
        }
        
        if hasattr(request.state, 'auth'):
            state_auth = request.state.auth
            auth_info.update({
                "authenticated": state_auth.get('authenticated', False),
                "auth_method": state_auth.get('auth_method', 'none'),
                "api_key_name": state_auth.get('key_info', {}).get('name'),
                "permissions": state_auth.get('key_info', {}).get('permissions', [])
            })
        
        return auth_info
    
    def log_request_start(self, request: Request, request_id: str) -> Dict[str, Any]:
        """记录请求开始"""
        if not self.logging_config.get("log_requests", True):
            return {}
        
        client_info = self.get_client_info(request)
        auth_info = self.get_auth_info(request)
        
        log_data = {
            "request_id": request_id,
            "event_type": "request_start",
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "start_time": time.time(),
            **client_info,
            **auth_info
        }
        
        # 记录请求体大小（不记录内容）
        if request.headers.get("Content-Length"):
            try:
                log_data["request_size"] = int(request.headers.get("Content-Length"))
            except ValueError:
                pass
        
        self.access_logger.info("Request started", extra=log_data)
        return log_data
    
    def log_request_end(self, request: Request, response: Response, 
                       request_data: Dict[str, Any], duration: float):
        """记录请求结束"""
        if not self.logging_config.get("log_requests", True):
            return
        
        log_data = {
            **request_data,
            "event_type": "request_end",
            "status_code": response.status_code,
            "response_size": len(response.body) if hasattr(response, 'body') else 0,
            "duration_ms": round(duration * 1000, 2),
            "end_time": time.time()
        }
        
        # 添加响应头信息
        if self.logging_config.get("log_response_headers", False):
            log_data["response_headers"] = dict(response.headers)
        
        # 根据状态码选择日志级别
        if response.status_code >= 500:
            self.access_logger.error("Request completed with server error", extra=log_data)
        elif response.status_code >= 400:
            self.access_logger.warning("Request completed with client error", extra=log_data)
        else:
            self.access_logger.info("Request completed successfully", extra=log_data)
    
    def log_authentication_event(self, request: Request, event_type: str, 
                                details: Dict[str, Any]):
        """记录认证事件"""
        if not self.logging_config.get("log_auth_events", True):
            return
        
        client_info = self.get_client_info(request)
        
        log_data = {
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "event_type": event_type,
            "method": request.method,
            "path": request.url.path,
            **client_info,
            **details
        }
        
        if event_type in ["auth_failed", "invalid_api_key", "ip_blocked"]:
            self.security_logger.warning(f"Security event: {event_type}", extra=log_data)
        else:
            self.security_logger.info(f"Auth event: {event_type}", extra=log_data)
    
    def log_rate_limit_event(self, request: Request, limit_info: Dict[str, Any]):
        """记录速率限制事件"""
        if not self.logging_config.get("log_rate_limit_exceeded", True):
            return
        
        client_info = self.get_client_info(request)
        auth_info = self.get_auth_info(request)
        
        log_data = {
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "event_type": "rate_limit_exceeded",
            "method": request.method,
            "path": request.url.path,
            "limit_info": limit_info,
            **client_info,
            **auth_info
        }
        
        self.security_logger.warning("Rate limit exceeded", extra=log_data)
    
    def log_performance_metrics(self, request: Request, metrics: Dict[str, Any]):
        """记录性能指标"""
        if not self.logging_config.get("log_performance", True):
            return
        
        log_data = {
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "event_type": "performance_metrics",
            "method": request.method,
            "path": request.url.path,
            **metrics
        }
        
        # 根据性能阈值选择日志级别
        duration = metrics.get('duration_ms', 0)
        if duration > 5000:  # 超过5秒
            self.performance_logger.warning("Slow request detected", extra=log_data)
        elif duration > 1000:  # 超过1秒
            self.performance_logger.info("Request performance metrics", extra=log_data)
        else:
            # 正常性能，只在调试模式下记录
            if self.logging_config.get("log_all_performance", False):
                self.performance_logger.info("Request performance metrics", extra=log_data)
    
    def log_error(self, request: Request, error: Exception, context: Dict[str, Any] = None):
        """记录错误"""
        client_info = self.get_client_info(request)
        auth_info = self.get_auth_info(request)
        
        log_data = {
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "event_type": "error",
            "method": request.method,
            "path": request.url.path,
            "error_type": type(error).__name__,
            "error_message": str(error),
            **client_info,
            **auth_info
        }
        
        if context:
            log_data["context"] = context
        
        self.access_logger.error("Request error", extra=log_data, exc_info=True)

class AccessLogMiddleware:
    """访问日志中间件"""
    
    def __init__(self, app):
        self.app = app
        self.access_logger = AccessLogger()
    
    async def __call__(self, scope, receive, send):
        """ASGI中间件接口"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        from fastapi import Request
        request = Request(scope, receive)
        
        # 生成请求ID
        request_id = self.access_logger.generate_request_id()
        request.state.request_id = request_id
        
        # 记录请求开始
        start_time = time.time()
        request_data = self.access_logger.log_request_start(request, request_id)
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # 添加请求ID到响应头
                headers = list(message.get("headers", []))
                headers.append([b"x-request-id", request_id.encode()])
                message["headers"] = headers
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
            
            # 计算处理时间
            duration = time.time() - start_time
            
            # 记录性能指标
            if duration > 0.1:  # 只记录超过100ms的请求
                metrics = {
                    "duration_ms": round(duration * 1000, 2)
                }
                self.access_logger.log_performance_metrics(request, metrics)
            
        except Exception as e:
            # 记录错误
            duration = time.time() - start_time
            self.access_logger.log_error(request, e, {
                "duration_ms": round(duration * 1000, 2)
            })
            raise

# 中间件将在main.py中初始化