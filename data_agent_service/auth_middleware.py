from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from typing import Optional, Dict, Any
import logging
import uuid
from datetime import datetime
from .security_config import security_config

# 配置日志
logger = logging.getLogger(__name__)

class APIKeyAuth:
    """API Key认证类"""
    
    def __init__(self):
        self.security_config = security_config
        self.auth_config = self.security_config.get_auth_config()
        
        # 初始化认证方案
        self.bearer_scheme = HTTPBearer(auto_error=False)
        self.api_key_header = APIKeyHeader(
            name=self.auth_config.get("header_name", "X-API-Key"),
            auto_error=False
        )
        self.api_key_query = APIKeyQuery(
            name=self.auth_config.get("query_param_name", "api_key"),
            auto_error=False
        )
    
    async def authenticate(self, request: Request) -> Optional[Dict[str, Any]]:
        """执行认证"""
        # 生成请求ID用于追踪
        request_id = str(uuid.uuid4())[:8]
        client_ip = self._get_client_ip(request)
        
        # 检查是否需要认证
        if not self.auth_config.get("require_api_key", True):
            return {
                "authenticated": True,
                "request_id": request_id,
                "api_key": None,
                "key_info": {
                    "name": "Anonymous",
                    "permissions": ["read", "write", "read:market_data", "write:market_data", "read:storage", "write:storage", "read:system", "write:system"],  # 给予所有权限
                    "rate_limit": self.security_config.get_rate_limits()
                },
                "client_ip": client_ip
            }
        
        # 检查IP白名单
        if not self.security_config.is_ip_whitelisted(client_ip):
            logger.warning(
                f"IP not whitelisted: {client_ip}",
                extra={"request_id": request_id, "client_ip": client_ip}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: IP not whitelisted"
            )
        
        # 尝试从不同来源获取API Key
        api_key = await self._extract_api_key(request)
        
        if not api_key:
            logger.warning(
                "No API key provided",
                extra={"request_id": request_id, "client_ip": client_ip}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 验证API Key
        if not self.security_config.is_api_key_valid(api_key):
            logger.warning(
                f"Invalid API key: {api_key[:8]}...",
                extra={"request_id": request_id, "client_ip": client_ip}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # 获取API Key信息
        key_info = self.security_config.get_api_key_info(api_key)
        
        logger.info(
            f"Authentication successful for API key: {key_info.get('name', 'Unknown')}",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "api_key_name": key_info.get('name'),
                "permissions": key_info.get('permissions', [])
            }
        )
        
        return {
            "authenticated": True,
            "request_id": request_id,
            "api_key": api_key,
            "key_info": key_info,
            "client_ip": client_ip
        }
    
    async def _extract_api_key(self, request: Request) -> Optional[str]:
        """从请求中提取API Key"""
        api_key = None
        
        # 1. 尝试从Bearer Token获取
        if self.auth_config.get("allow_bearer_token", True):
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]  # 去掉 "Bearer " 前缀
        
        # 2. 尝试从Header获取
        if not api_key:
            header_name = self.auth_config.get("header_name", "X-API-Key")
            api_key = request.headers.get(header_name)
        
        # 3. 尝试从Query参数获取
        if not api_key and self.auth_config.get("allow_query_param", True):
            query_param_name = self.auth_config.get("query_param_name", "api_key")
            api_key = request.query_params.get(query_param_name)
        
        return api_key
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 返回直接连接的IP
        return request.client.host if request.client else "unknown"

class AuthenticationMiddleware:
    """认证中间件"""
    
    def __init__(self):
        self.api_key_auth = APIKeyAuth()
        self.logging_config = security_config.get_logging_config()
    
    async def __call__(self, request: Request, call_next):
        """中间件处理函数"""
        start_time = datetime.now()
        
        # 跳过不需要认证的端点
        if self._should_skip_auth(request.url.path):
            response = await call_next(request)
            return response
        
        try:
            # 执行认证
            auth_result = await self.api_key_auth.authenticate(request)
            
            # 将认证信息添加到请求状态
            request.state.auth = auth_result
            
            # 记录认证成功的请求
            if self.logging_config.get("log_all_requests", True):
                self._log_request(request, auth_result, "success")
            
            # 继续处理请求
            response = await call_next(request)
            
            # 记录响应时间
            duration = (datetime.now() - start_time).total_seconds() * 1000
            response.headers["X-Response-Time"] = f"{duration:.2f}ms"
            
            if hasattr(request.state, 'auth') and request.state.auth.get('request_id'):
                response.headers["X-Request-ID"] = request.state.auth['request_id']
            
            return response
            
        except HTTPException as e:
            # 记录认证失败
            if self.logging_config.get("log_failed_auth", True):
                self._log_request(request, {"error": str(e.detail)}, "failed")
            raise e
        except Exception as e:
            logger.error(f"Authentication middleware error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal authentication error"
            )
    
    def _should_skip_auth(self, path: str) -> bool:
        """判断是否跳过认证"""
        # 不需要认证的端点
        skip_paths = [
            "/",
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        
        return path in skip_paths
    
    def _log_request(self, request: Request, auth_result: Dict, status: str):
        """记录请求日志"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": auth_result.get("client_ip", "unknown"),
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "auth_status": status,
            "request_id": auth_result.get("request_id", "unknown")
        }
        
        if status == "success":
            log_data["api_key_name"] = auth_result.get("key_info", {}).get("name", "unknown")
            log_data["permissions"] = auth_result.get("key_info", {}).get("permissions", [])
        else:
            log_data["error"] = auth_result.get("error", "unknown")
        
        # 过滤敏感信息
        filtered_headers = {}
        sensitive_headers = self.logging_config.get("sensitive_headers", [])
        for key, value in request.headers.items():
            if key.lower() in [h.lower() for h in sensitive_headers]:
                filtered_headers[key] = "[REDACTED]"
            else:
                filtered_headers[key] = value
        
        log_data["headers"] = filtered_headers
        
        if status == "success":
            logger.info("API request authenticated", extra=log_data)
        else:
            logger.warning("API request authentication failed", extra=log_data)

# 创建中间件实例
authentication_middleware = AuthenticationMiddleware()

# 依赖注入函数
async def get_current_user(request: Request) -> Dict[str, Any]:
    """获取当前认证用户信息的依赖"""
    if hasattr(request.state, 'auth'):
        return request.state.auth
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

# 权限检查装饰器
def require_permissions(*required_permissions):
    """权限检查装饰器
    
    支持两种调用方式：
    1. @require_permissions("read:market_data", "write:market_data")
    2. @require_permissions(["read:market_data", "write:market_data"])
    """
    def decorator(func):
        from functools import wraps
        
        @wraps(func)  # 保留原始函数的签名和元数据
        async def wrapper(*args, **kwargs):
            # 处理权限参数：如果第一个参数是列表，则使用列表；否则使用所有参数
            if len(required_permissions) == 1 and isinstance(required_permissions[0], list):
                permissions_to_check = required_permissions[0]
            else:
                permissions_to_check = list(required_permissions)
            
            # 对于FastAPI，我们需要从kwargs中获取current_user依赖
            # 如果current_user存在，说明认证已经通过
            current_user = kwargs.get('current_user')
            if current_user and current_user.get('authenticated'):
                # 检查权限
                user_permissions = current_user.get('key_info', {}).get('permissions', [])
                
                for permission in permissions_to_check:
                    if permission not in user_permissions:
                        logger.warning(
                            f"Permission denied: {permission} required",
                            extra={
                                "request_id": current_user.get('request_id'),
                                "required_permissions": permissions_to_check,
                                "user_permissions": user_permissions
                            }
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Permission required: {permission}"
                        )
                
                return await func(*args, **kwargs)
            
            # 如果没有current_user，尝试从args中获取request对象（向后兼容）
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # 如果既没有current_user也没有request，说明认证配置有问题
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # 检查认证状态
            if not hasattr(request.state, 'auth') or not request.state.auth.get('authenticated'):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # 检查权限
            user_permissions = request.state.auth.get('key_info', {}).get('permissions', [])
            
            for permission in permissions_to_check:
                if permission not in user_permissions:
                    logger.warning(
                        f"Permission denied: {permission} required",
                        extra={
                            "request_id": request.state.auth.get('request_id'),
                            "required_permissions": permissions_to_check,
                            "user_permissions": user_permissions
                        }
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission required: {permission}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator