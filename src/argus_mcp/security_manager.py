"""
安全加固和认证授权
实现JWT认证、权限管理、数据加密和访问控制
"""

import asyncio
import logging
import secrets
import hashlib
import hmac
import jwt
import time
import json
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import base64
import os
from functools import wraps
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"
    API_USER = "api_user"


class Permission(Enum):
    """权限枚举"""
    READ_MARKET_DATA = "read:market_data"
    WRITE_TRADES = "write:trades"
    MANAGE_CONNECTIONS = "manage:connections"
    ADMIN_OPERATIONS = "admin:operations"
    ACCESS_WEBSOCKET = "access:websocket"
    VIEW_ANALYTICS = "view:analytics"


@dataclass
class User:
    """用户模型"""
    id: str
    username: str
    email: str
    role: UserRole
    permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None


@dataclass
class SecurityConfig:
    """安全配置"""
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    encryption_key: bytes
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # 秒
    max_login_attempts: int = 5
    lockout_duration: int = 300  # 秒
    require_https: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["https://localhost:3000"])


class TokenManager:
    """JWT令牌管理器"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.refresh_tokens: Dict[str, Dict[str, Any]] = {}
        self.blacklisted_tokens: Set[str] = set()
    
    def generate_access_token(self, user: User) -> str:
        """生成访问令牌"""
        payload = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "permissions": [p.value for p in user.permissions],
            "exp": datetime.now(timezone.utc) + timedelta(hours=self.config.jwt_expiry_hours),
            "iat": datetime.now(timezone.utc),
            "type": "access"
        }
        
        return jwt.encode(payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)
    
    def generate_refresh_token(self, user_id: str) -> str:
        """生成刷新令牌"""
        token_id = secrets.token_urlsafe(32)
        payload = {
            "user_id": user_id,
            "token_id": token_id,
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        }
        
        refresh_token = jwt.encode(
            payload, 
            self.config.jwt_secret_key, 
            algorithm=self.config.jwt_algorithm
        )
        
        self.refresh_tokens[token_id] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30)
        }
        
        return refresh_token
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """验证令牌"""
        try:
            if token in self.blacklisted_tokens:
                return None
            
            payload = jwt.decode(
                token, 
                self.config.jwt_secret_key, 
                algorithms=[self.config.jwt_algorithm]
            )
            
            if payload.get("type") != token_type:
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def blacklist_token(self, token: str):
        """将令牌加入黑名单"""
        self.blacklisted_tokens.add(token)
    
    def revoke_refresh_token(self, token_id: str):
        """撤销刷新令牌"""
        self.refresh_tokens.pop(token_id, None)
    
    def cleanup_expired_tokens(self):
        """清理过期令牌"""
        now = datetime.now(timezone.utc)
        expired_tokens = [
            token_id for token_id, data in self.refresh_tokens.items()
            if data["expires_at"] < now
        ]
        
        for token_id in expired_tokens:
            self.refresh_tokens.pop(token_id, None)


class EncryptionManager:
    """数据加密管理器"""
    
    def __init__(self, encryption_key: bytes):
        self.fernet = Fernet(encryption_key)
    
    def encrypt_data(self, data: str) -> str:
        """加密数据"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """解密数据"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """加密字典数据"""
        json_str = json.dumps(data)
        return self.encrypt_data(json_str)
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """解密字典数据"""
        json_str = self.decrypt_data(encrypted_data)
        return json.loads(json_str)
    
    @staticmethod
    def generate_key() -> bytes:
        """生成新的加密密钥"""
        return Fernet.generate_key()
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """从密码派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # 清理过期请求
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if now - req_time < self.window_seconds
        ]
        
        # 检查是否超过限制
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # 记录请求
        self.requests[identifier].append(now)
        return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """获取剩余请求数"""
        now = time.time()
        
        if identifier not in self.requests:
            return self.max_requests
        
        # 清理过期请求
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if now - req_time < self.window_seconds
        ]
        
        return max(0, self.max_requests - len(self.requests[identifier]))
    
    def reset_limit(self, identifier: str):
        """重置限制"""
        self.requests.pop(identifier, None)


class LoginAttemptTracker:
    """登录尝试跟踪器"""
    
    def __init__(self, max_attempts: int, lockout_duration: int):
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration
        self.attempts: Dict[str, List[datetime]] = {}
        self.locked_users: Dict[str, datetime] = {}
    
    def record_attempt(self, identifier: str):
        """记录登录尝试"""
        now = datetime.now(timezone.utc)
        
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        
        self.attempts[identifier].append(now)
        
        # 清理过期尝试
        cutoff = now - timedelta(seconds=self.lockout_duration)
        self.attempts[identifier] = [
            attempt for attempt in self.attempts[identifier]
            if attempt > cutoff
        ]
    
    def is_locked(self, identifier: str) -> bool:
        """检查用户是否被锁定"""
        if identifier in self.locked_users:
            lock_time = self.locked_users[identifier]
            if datetime.now(timezone.utc) - lock_time < timedelta(seconds=self.lockout_duration):
                return True
            else:
                # 解锁用户
                del self.locked_users[identifier]
        
        # 检查尝试次数
        if identifier in self.attempts:
            if len(self.attempts[identifier]) >= self.max_attempts:
                self.locked_users[identifier] = datetime.now(timezone.utc)
                return True
        
        return False
    
    def reset_attempts(self, identifier: str):
        """重置尝试记录"""
        self.attempts.pop(identifier, None)
        self.locked_users.pop(identifier, None)


class SecurityManager:
    """安全管理器"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.token_manager = TokenManager(config)
        self.encryption_manager = EncryptionManager(config.encryption_key)
        self.rate_limiter = RateLimiter(
            config.rate_limit_requests,
            config.rate_limit_window
        )
        self.login_tracker = LoginAttemptTracker(
            config.max_login_attempts,
            config.lockout_duration
        )
        
        # 用户存储
        self.users: Dict[str, User] = {}
        self.api_keys: Dict[str, str] = {}  # key -> user_id
        
        # 安全事件日志
        self.security_events: List[Dict[str, Any]] = []
        
        # 初始化默认管理员用户
        self._initialize_default_users()
    
    def _initialize_default_users(self):
        """初始化默认用户"""
        admin_user = User(
            id="admin_001",
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN,
            permissions={
                Permission.READ_MARKET_DATA,
                Permission.WRITE_TRADES,
                Permission.MANAGE_CONNECTIONS,
                Permission.ADMIN_OPERATIONS,
                Permission.ACCESS_WEBSOCKET,
                Permission.VIEW_ANALYTICS
            }
        )
        
        trader_user = User(
            id="trader_001",
            username="trader",
            email="trader@example.com",
            role=UserRole.TRADER,
            permissions={
                Permission.READ_MARKET_DATA,
                Permission.WRITE_TRADES,
                Permission.ACCESS_WEBSOCKET,
                Permission.VIEW_ANALYTICS
            }
        )
        
        viewer_user = User(
            id="viewer_001",
            username="viewer",
            email="viewer@example.com",
            role=UserRole.VIEWER,
            permissions={
                Permission.READ_MARKET_DATA,
                Permission.VIEW_ANALYTICS
            }
        )
        
        self.users[admin_user.id] = admin_user
        self.users[trader_user.id] = trader_user
        self.users[viewer_user.id] = viewer_user
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """记录安全事件"""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc),
            "details": details
        }
        self.security_events.append(event)
        
        # 只保留最近1000条事件
        if len(self.security_events) > 1000:
            self.security_events = self.security_events[-1000:]
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """用户认证"""
        # 检查速率限制
        if not self.rate_limiter.is_allowed(f"login_{username}"):
            self._log_security_event("rate_limit_exceeded", {"username": username})
            return None
        
        # 检查用户是否被锁定
        if self.login_tracker.is_locked(username):
            self._log_security_event("login_locked", {"username": username})
            return None
        
        # 查找用户
        user = None
        for u in self.users.values():
            if u.username == username:
                user = u
                break
        
        if not user or not user.is_active:
            self.login_tracker.record_attempt(username)
            self._log_security_event("login_failed", {"username": username, "reason": "user_not_found"})
            return None
        
        # 验证密码（这里简化处理，实际应该使用密码哈希）
        # 在生产环境中应该使用安全的密码哈希和验证
        if password != "password123":  # 简化示例
            self.login_tracker.record_attempt(username)
            self._log_security_event("login_failed", {"username": username, "reason": "invalid_password"})
            return None
        
        # 重置尝试记录
        self.login_tracker.reset_attempts(username)
        
        # 更新最后登录时间
        user.last_login = datetime.now(timezone.utc)
        
        # 生成令牌
        access_token = self.token_manager.generate_access_token(user)
        refresh_token = self.token_manager.generate_refresh_token(user.id)
        
        self._log_security_event("login_success", {"username": username, "user_id": user.id})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.config.jwt_expiry_hours * 3600
        }
    
    def verify_token(self, token: str) -> Optional[User]:
        """验证令牌并返回用户"""
        payload = self.token_manager.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        return self.users.get(user_id)
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """刷新访问令牌"""
        payload = self.token_manager.verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        user = self.users.get(user_id)
        
        if not user:
            return None
        
        return self.token_manager.generate_access_token(user)
    
    def logout_user(self, token: str):
        """用户登出"""
        payload = self.token_manager.verify_token(token)
        if payload:
            self.token_manager.blacklist_token(token)
            self._log_security_event("logout", {"user_id": payload.get("user_id")})
    
    def has_permission(self, user: User, permission: Permission) -> bool:
        """检查用户权限"""
        return permission in user.permissions
    
    def generate_api_key(self, user_id: str) -> str:
        """生成API密钥"""
        api_key = secrets.token_urlsafe(32)
        self.api_keys[api_key] = user_id
        self._log_security_event("api_key_generated", {"user_id": user_id})
        return api_key
    
    def verify_api_key(self, api_key: str) -> Optional[User]:
        """验证API密钥"""
        user_id = self.api_keys.get(api_key)
        if user_id:
            self._log_security_event("api_key_used", {"user_id": user_id})
            return self.users.get(user_id)
        return None
    
    def revoke_api_key(self, api_key: str):
        """撤销API密钥"""
        user_id = self.api_keys.pop(api_key, None)
        if user_id:
            self._log_security_event("api_key_revoked", {"user_id": user_id})
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """加密敏感数据"""
        return self.encryption_manager.encrypt_data(data)
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """解密敏感数据"""
        return self.encryption_manager.decrypt_data(encrypted_data)
    
    def get_security_report(self) -> Dict[str, Any]:
        """获取安全报告"""
        return {
            "total_users": len(self.users),
            "active_sessions": len(self.token_manager.refresh_tokens),
            "blacklisted_tokens": len(self.token_manager.blacklisted_tokens),
            "api_keys_count": len(self.api_keys),
            "security_events_count": len(self.security_events),
            "recent_events": self.security_events[-50:] if self.security_events else [],
            "rate_limiter_stats": {
                "total_requests": sum(len(reqs) for reqs in self.rate_limiter.requests.values()),
                "unique_clients": len(self.rate_limiter.requests)
            }
        }
    
    def cleanup_expired_data(self):
        """清理过期数据"""
        self.token_manager.cleanup_expired_tokens()
        self.rate_limiter.requests.clear()  # 定期清理速率限制


# FastAPI依赖项
security = HTTPBearer()


class SecurityMiddleware:
    """安全中间件"""
    
    def __init__(self, security_manager: SecurityManager):
        self.security_manager = security_manager
    
    async def __call__(self, request):
        """处理请求的安全检查"""
        # 检查HTTPS
        if self.security_manager.config.require_https:
            if request.url.scheme != "https":
                raise HTTPException(status_code=400, detail="HTTPS required")
        
        # 检查CORS
        origin = request.headers.get("origin")
        if origin and origin not in self.security_manager.config.cors_origins:
            raise HTTPException(status_code=403, detail="Origin not allowed")
        
        return request


def require_auth(permissions: Optional[List[Permission]] = None):
    """认证装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 这里应该集成FastAPI的依赖注入
            # 实际使用时会通过FastAPI的Security依赖
            return await func(*args, **kwargs)
        return wrapper
    return decorator