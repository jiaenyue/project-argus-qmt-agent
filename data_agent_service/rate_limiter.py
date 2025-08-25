from fastapi import HTTPException, Request, status
from typing import Dict, Optional, Tuple
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio
from .security_config import security_config

# 配置日志
logger = logging.getLogger(__name__)

class TokenBucket:
    """令牌桶算法实现"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity  # 桶容量
        self.tokens = capacity    # 当前令牌数
        self.refill_rate = refill_rate  # 每秒补充的令牌数
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """消费令牌"""
        async with self.lock:
            now = time.time()
            # 计算需要补充的令牌数
            time_passed = now - self.last_refill
            tokens_to_add = time_passed * self.refill_rate
            
            # 补充令牌，但不超过容量
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
            
            # 检查是否有足够的令牌
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """获取需要等待的时间（秒）"""
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate

class SlidingWindowCounter:
    """滑动窗口计数器"""
    
    def __init__(self, window_size: int):
        self.window_size = window_size  # 窗口大小（秒）
        self.requests = deque()  # 请求时间戳队列
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, limit: int) -> Tuple[bool, int]:
        """检查是否允许请求"""
        async with self.lock:
            now = time.time()
            
            # 移除过期的请求记录
            while self.requests and self.requests[0] <= now - self.window_size:
                self.requests.popleft()
            
            # 检查是否超过限制
            if len(self.requests) < limit:
                self.requests.append(now)
                return True, len(self.requests)
            else:
                return False, len(self.requests)
    
    def get_reset_time(self) -> float:
        """获取重置时间"""
        if not self.requests:
            return 0.0
        return self.requests[0] + self.window_size

class RateLimiter:
    """速率限制器"""
    
    def __init__(self):
        self.security_config = security_config
        
        # IP限制器（滑动窗口）
        self.ip_limiters: Dict[str, Dict[str, SlidingWindowCounter]] = defaultdict(lambda: {
            'minute': SlidingWindowCounter(60),
            'hour': SlidingWindowCounter(3600)
        })
        
        # API Key限制器（令牌桶）
        self.api_key_limiters: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)
        
        # 清理过期记录的任务
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        async def cleanup():
            while True:
                await asyncio.sleep(300)  # 每5分钟清理一次
                self.cleanup_expired_records()
        
        try:
            # 只有在有运行的事件循环时才创建任务
            loop = asyncio.get_running_loop()
            self._cleanup_task = asyncio.create_task(cleanup())
        except RuntimeError:
            # 没有运行的事件循环，稍后再创建任务
            self._cleanup_task = None
            self._cleanup_coroutine = cleanup
    
    async def _cleanup_expired_records(self):
        """清理过期记录"""
        try:
            now = time.time()
            
            # 清理IP限制器中的过期记录
            expired_ips = []
            for ip, limiters in self.ip_limiters.items():
                # 如果所有窗口都没有请求记录，则标记为过期
                all_empty = True
                for limiter in limiters.values():
                    if limiter.requests:
                        all_empty = False
                        break
                
                if all_empty:
                    expired_ips.append(ip)
            
            for ip in expired_ips:
                del self.ip_limiters[ip]
            
            # 清理API Key限制器中的过期记录
            expired_keys = []
            for api_key, limiters in self.api_key_limiters.items():
                # 检查令牌桶是否长时间未使用
                all_full = True
                for bucket in limiters.values():
                    if bucket.tokens < bucket.capacity or (now - bucket.last_refill) < 3600:
                        all_full = False
                        break
                
                if all_full:
                    expired_keys.append(api_key)
            
            for api_key in expired_keys:
                del self.api_key_limiters[api_key]
            
            if expired_ips or expired_keys:
                logger.info(f"Cleaned up {len(expired_ips)} IP limiters and {len(expired_keys)} API key limiters")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def check_ip_rate_limit(self, ip: str) -> Tuple[bool, Dict[str, any]]:
        """检查IP速率限制"""
        ip_limits = self.security_config.get_ip_rate_limits()
        
        if not ip_limits:
            return True, {"status": "no_limits"}
        
        limiters = self.ip_limiters[ip]
        results = {}
        
        # 检查每分钟限制
        minute_limit = ip_limits.get("requests_per_minute", 0)
        if minute_limit > 0:
            allowed, count = await limiters['minute'].is_allowed(minute_limit)
            results['minute'] = {
                'allowed': allowed,
                'count': count,
                'limit': minute_limit,
                'reset_time': limiters['minute'].get_reset_time()
            }
            if not allowed:
                return False, results
        
        # 检查每小时限制
        hour_limit = ip_limits.get("requests_per_hour", 0)
        if hour_limit > 0:
            allowed, count = await limiters['hour'].is_allowed(hour_limit)
            results['hour'] = {
                'allowed': allowed,
                'count': count,
                'limit': hour_limit,
                'reset_time': limiters['hour'].get_reset_time()
            }
            if not allowed:
                return False, results
        
        return True, results
    
    async def check_api_key_rate_limit(self, api_key: str) -> Tuple[bool, Dict[str, any]]:
        """检查API Key速率限制"""
        rate_limits = self.security_config.get_rate_limits(api_key)
        
        if not rate_limits:
            return True, {"status": "no_limits"}
        
        limiters = self.api_key_limiters[api_key]
        results = {}
        
        # 检查每分钟限制
        minute_limit = rate_limits.get("requests_per_minute", 0)
        if minute_limit > 0:
            if 'minute' not in limiters:
                limiters['minute'] = TokenBucket(minute_limit, minute_limit / 60.0)
            
            bucket = limiters['minute']
            allowed = await bucket.consume(1)
            results['minute'] = {
                'allowed': allowed,
                'tokens_remaining': int(bucket.tokens),
                'limit': minute_limit,
                'wait_time': bucket.get_wait_time(1) if not allowed else 0
            }
            if not allowed:
                return False, results
        
        # 检查每小时限制
        hour_limit = rate_limits.get("requests_per_hour", 0)
        if hour_limit > 0:
            if 'hour' not in limiters:
                limiters['hour'] = TokenBucket(hour_limit, hour_limit / 3600.0)
            
            bucket = limiters['hour']
            allowed = await bucket.consume(1)
            results['hour'] = {
                'allowed': allowed,
                'tokens_remaining': int(bucket.tokens),
                'limit': hour_limit,
                'wait_time': bucket.get_wait_time(1) if not allowed else 0
            }
            if not allowed:
                return False, results
        
        return True, results
    
    async def check_rate_limits(self, request: Request) -> Tuple[bool, Dict[str, any]]:
        """检查所有速率限制"""
        client_ip = self._get_client_ip(request)
        results = {'ip': client_ip}
        
        # 检查IP限制
        ip_allowed, ip_results = await self.check_ip_rate_limit(client_ip)
        results['ip_limits'] = ip_results
        
        if not ip_allowed:
            return False, results
        
        # 检查API Key限制（如果有认证信息）
        if hasattr(request.state, 'auth') and request.state.auth.get('authenticated'):
            api_key = request.state.auth.get('api_key')
            if api_key:
                key_allowed, key_results = await self.check_api_key_rate_limit(api_key)
                results['api_key_limits'] = key_results
                
                if not key_allowed:
                    return False, results
        
        return True, results
    
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

class RateLimitMiddleware:
    """速率限制中间件"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.logging_config = security_config.get_logging_config()
    
    async def __call__(self, request: Request, call_next):
        """中间件处理函数"""
        # 如果清理任务还没有启动，现在启动它
        if self.rate_limiter._cleanup_task is None and hasattr(self.rate_limiter, '_cleanup_coroutine'):
            try:
                self.rate_limiter._cleanup_task = asyncio.create_task(self.rate_limiter._cleanup_coroutine())
            except Exception:
                pass  # 忽略启动失败
        
        # 跳过不需要限制的端点
        if self._should_skip_rate_limit(request.url.path):
            response = await call_next(request)
            return response
        
        try:
            # 检查速率限制
            allowed, limit_results = await self.rate_limiter.check_rate_limits(request)
            
            if not allowed:
                # 记录速率限制超出
                if self.logging_config.get("log_rate_limit_exceeded", True):
                    self._log_rate_limit_exceeded(request, limit_results)
                
                # 构建错误响应
                error_detail = self._build_rate_limit_error(limit_results)
                headers = self._build_rate_limit_headers(limit_results)
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_detail,
                    headers=headers
                )
            
            # 继续处理请求
            response = await call_next(request)
            
            # 添加速率限制信息到响应头
            rate_limit_headers = self._build_rate_limit_headers(limit_results)
            for key, value in rate_limit_headers.items():
                response.headers[key] = value
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit middleware error: {str(e)}", exc_info=True)
            # 发生错误时允许请求通过，避免影响服务可用性
            return await call_next(request)
    
    def _should_skip_rate_limit(self, path: str) -> bool:
        """判断是否跳过速率限制"""
        # 不需要限制的端点
        skip_paths = [
            "/health",
            "/metrics"
        ]
        
        return path in skip_paths
    
    def _build_rate_limit_error(self, limit_results: Dict) -> str:
        """构建速率限制错误信息"""
        if 'api_key_limits' in limit_results:
            # API Key限制
            for period, info in limit_results['api_key_limits'].items():
                if not info.get('allowed', True):
                    wait_time = info.get('wait_time', 0)
                    return f"API key rate limit exceeded for {period}. Wait {wait_time:.1f} seconds."
        
        if 'ip_limits' in limit_results:
            # IP限制
            for period, info in limit_results['ip_limits'].items():
                if not info.get('allowed', True):
                    reset_time = info.get('reset_time', 0)
                    wait_time = max(0, reset_time - time.time())
                    return f"IP rate limit exceeded for {period}. Reset in {wait_time:.1f} seconds."
        
        return "Rate limit exceeded"
    
    def _build_rate_limit_headers(self, limit_results: Dict) -> Dict[str, str]:
        """构建速率限制响应头"""
        headers = {}
        
        # API Key限制头
        if 'api_key_limits' in limit_results:
            for period, info in limit_results['api_key_limits'].items():
                if isinstance(info, dict) and 'limit' in info:
                    headers[f"X-RateLimit-{period.title()}-Limit"] = str(info['limit'])
                    headers[f"X-RateLimit-{period.title()}-Remaining"] = str(info.get('tokens_remaining', 0))
                    if 'wait_time' in info and info['wait_time'] > 0:
                        headers[f"X-RateLimit-{period.title()}-Reset"] = str(int(time.time() + info['wait_time']))
        
        # IP限制头
        if 'ip_limits' in limit_results:
            for period, info in limit_results['ip_limits'].items():
                if isinstance(info, dict) and 'limit' in info:
                    headers[f"X-RateLimit-IP-{period.title()}-Limit"] = str(info['limit'])
                    remaining = info['limit'] - info.get('count', 0)
                    headers[f"X-RateLimit-IP-{period.title()}-Remaining"] = str(max(0, remaining))
                    if 'reset_time' in info:
                        headers[f"X-RateLimit-IP-{period.title()}-Reset"] = str(int(info['reset_time']))
        
        return headers
    
    def _log_rate_limit_exceeded(self, request: Request, limit_results: Dict):
        """记录速率限制超出日志"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "client_ip": limit_results.get('ip', 'unknown'),
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "limit_results": limit_results
        }
        
        if hasattr(request.state, 'auth'):
            auth_info = request.state.auth
            log_data["request_id"] = auth_info.get('request_id', 'unknown')
            if auth_info.get('authenticated'):
                log_data["api_key_name"] = auth_info.get('key_info', {}).get('name', 'unknown')
        
        logger.warning("Rate limit exceeded", extra=log_data)

# 创建中间件实例
rate_limit_middleware = RateLimitMiddleware()