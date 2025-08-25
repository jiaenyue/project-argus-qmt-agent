"""
FastAPI WebSocket 集成模块
将增强的 WebSocket 端点集成到 FastAPI 应用中
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .enhanced_websocket_endpoints import (
    get_enhanced_websocket_endpoints,
    get_router,
    start_websocket_service,
    stop_websocket_service
)
from .websocket_models import WebSocketConfig
from .websocket_heartbeat import WebSocketHeartbeatManager, WebSocketReconnectManager, HeartbeatConfig

logger = logging.getLogger(__name__)


class WebSocketFastAPIIntegration:
    """WebSocket FastAPI 集成类"""
    
    def __init__(
        self,
        app: Optional[FastAPI] = None,
        websocket_config: Optional[WebSocketConfig] = None,
        heartbeat_config: Optional[HeartbeatConfig] = None
    ):
        self.app = app
        self.websocket_config = websocket_config or WebSocketConfig()
        self.heartbeat_config = heartbeat_config or HeartbeatConfig()
        self._is_integrated = False
        
        # 心跳和重连管理器
        self.heartbeat_manager = WebSocketHeartbeatManager(self.heartbeat_config)
        self.reconnect_manager = WebSocketReconnectManager(self.heartbeat_config)
        
        # 优雅关闭支持
        self._shutdown_event = asyncio.Event()
        self._active_connections: Dict[str, Any] = {}
        self._shutdown_timeout = 30.0  # 30秒关闭超时
    
    def integrate_with_app(self, app: FastAPI) -> FastAPI:
        """将 WebSocket 功能集成到 FastAPI 应用中"""
        if self._is_integrated:
            logger.warning("WebSocket already integrated with FastAPI app")
            return app
        
        self.app = app
        
        # 添加 WebSocket 路由
        websocket_router = get_router()
        app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])
        
        # 添加 WebSocket 中间件
        self._add_websocket_middleware(app)
        
        # 添加生命周期事件
        self._setup_lifespan_events(app)
        
        # 添加异常处理器
        self._add_exception_handlers(app)
        
        self._is_integrated = True
        logger.info("WebSocket functionality integrated with FastAPI app")
        
        return app
    
    def _add_websocket_middleware(self, app: FastAPI):
        """添加 WebSocket 中间件"""
        
        @app.middleware("http")
        async def websocket_cors_middleware(request: Request, call_next):
            """WebSocket CORS 中间件"""
            response = await call_next(request)
            
            # 为 WebSocket 端点添加 CORS 头
            if request.url.path.startswith("/api/v1/ws/"):
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "*"
            
            return response
        
        logger.info("WebSocket middleware added")
    
    def _setup_lifespan_events(self, app: FastAPI):
        """设置生命周期事件"""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """应用生命周期管理"""
            # 启动时
            logger.info("Starting WebSocket service with heartbeat and reconnect support...")
            startup_success = False
            
            try:
                # 启动核心服务
                await start_websocket_service()
                
                # 启动心跳和重连管理器
                await self.heartbeat_manager.start()
                await self.reconnect_manager.start()
                
                # 设置心跳回调
                self._setup_heartbeat_callbacks()
                
                # 启动后台监控任务
                self._start_background_tasks()
                
                startup_success = True
                logger.info("WebSocket service started successfully with enhanced features")
                
            except Exception as e:
                logger.error(f"Failed to start WebSocket service: {e}")
                if not startup_success:
                    # 如果启动失败，尝试清理已启动的组件
                    await self._cleanup_failed_startup()
                raise
            
            try:
                yield
            finally:
                # 优雅关闭
                logger.info("Initiating graceful shutdown of WebSocket service...")
                try:
                    await self._graceful_shutdown()
                    logger.info("WebSocket service stopped gracefully")
                except Exception as e:
                    logger.error(f"Error during graceful shutdown: {e}")
                    # 强制关闭
                    await self._force_shutdown()
        
        # 设置生命周期
        app.router.lifespan_context = lifespan
        logger.info("WebSocket lifespan events configured with graceful shutdown")
    
    def _add_exception_handlers(self, app: FastAPI):
        """添加异常处理器"""
        
        @app.exception_handler(Exception)
        async def websocket_exception_handler(request: Request, exc: Exception):
            """WebSocket 异常处理器"""
            if request.url.path.startswith("/api/v1/ws/"):
                logger.error(f"WebSocket endpoint error: {exc}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "WebSocket service error",
                        "message": str(exc),
                        "path": request.url.path
                    }
                )
            
            # 对于非 WebSocket 端点，重新抛出异常
            raise exc
        
        logger.info("WebSocket exception handlers added")
    
    def _setup_heartbeat_callbacks(self):
        """设置心跳回调函数"""
        
        async def on_connection_lost(client_id: str):
            """连接丢失回调"""
            logger.warning(f"Connection lost for client {client_id}")
            
            # 从活跃连接中移除
            if client_id in self._active_connections:
                del self._active_connections[client_id]
            
            # 安排重连（如果需要）
            endpoints = get_enhanced_websocket_endpoints()
            if endpoints._is_running:
                await self.reconnect_manager.schedule_reconnect(
                    client_id,
                    lambda: self._attempt_reconnect(client_id)
                )
        
        async def on_connection_restored(client_id: str):
            """连接恢复回调"""
            logger.info(f"Connection restored for client {client_id}")
            
            # 取消重连任务
            await self.reconnect_manager.cancel_reconnect(client_id)
        
        async def on_heartbeat_timeout(client_id: str):
            """心跳超时回调"""
            logger.error(f"Heartbeat timeout for client {client_id}")
            
            # 可以在这里添加额外的超时处理逻辑
            # 比如发送警告消息、记录统计等
        
        # 设置回调
        self.heartbeat_manager.on_connection_lost = on_connection_lost
        self.heartbeat_manager.on_connection_restored = on_connection_restored
        self.heartbeat_manager.on_heartbeat_timeout = on_heartbeat_timeout
        
        logger.info("Heartbeat callbacks configured")
    
    async def _attempt_reconnect(self, client_id: str) -> bool:
        """尝试重连"""
        try:
            # 这里可以实现具体的重连逻辑
            # 对于服务端来说，主要是清理资源和准备接受新连接
            logger.info(f"Preparing for reconnection of client {client_id}")
            
            # 清理旧的连接状态
            endpoints = get_enhanced_websocket_endpoints()
            await endpoints.connection_manager.disconnect(client_id)
            await endpoints.subscription_manager.unsubscribe_all(client_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Reconnect attempt failed for {client_id}: {e}")
            return False
    
    async def _graceful_shutdown(self):
        """优雅关闭"""
        try:
            logger.info("Starting graceful shutdown process...")
            
            # 设置关闭事件
            self._shutdown_event.set()
            
            # 通知所有客户端即将关闭
            await self._notify_clients_shutdown()
            
            # 等待一段时间让客户端处理关闭通知
            await asyncio.sleep(2.0)
            
            # 停止心跳和重连管理器
            await self.heartbeat_manager.stop()
            await self.reconnect_manager.stop()
            
            # 停止WebSocket服务
            await stop_websocket_service()
            
            # 等待所有连接关闭
            await self._wait_for_connections_close()
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            # 强制关闭
            await self._force_shutdown()
    
    async def _notify_clients_shutdown(self):
        """通知客户端即将关闭"""
        try:
            shutdown_message = {
                "type": "server_shutdown",
                "message": "Server is shutting down gracefully",
                "timestamp": datetime.now().isoformat(),
                "reconnect_after": 5  # 建议5秒后重连
            }
            
            # 广播关闭消息
            endpoints = get_enhanced_websocket_endpoints()
            await endpoints._broadcast_message(shutdown_message)
            
            logger.info("Shutdown notification sent to all clients")
            
        except Exception as e:
            logger.error(f"Error notifying clients of shutdown: {e}")
    
    async def _wait_for_connections_close(self):
        """等待连接关闭"""
        try:
            timeout = self._shutdown_timeout
            start_time = asyncio.get_event_loop().time()
            
            while self._active_connections and (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(0.1)
            
            if self._active_connections:
                logger.warning(f"Timeout waiting for {len(self._active_connections)} connections to close")
            else:
                logger.info("All connections closed gracefully")
                
        except Exception as e:
            logger.error(f"Error waiting for connections to close: {e}")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        try:
            # 启动连接健康检查任务
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            # 启动统计收集任务
            self._stats_collection_task = asyncio.create_task(self._stats_collection_loop())
            
            logger.info("Background tasks started")
            
        except Exception as e:
            logger.error(f"Error starting background tasks: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(60)  # 每分钟检查一次
                
                try:
                    # 检查服务健康状态
                    unhealthy_connections = self.heartbeat_manager.get_unhealthy_connections()
                    
                    if unhealthy_connections:
                        logger.warning(f"Found {len(unhealthy_connections)} unhealthy connections")
                        
                        # 清理不健康的连接
                        endpoints = get_enhanced_websocket_endpoints()
                        for client_id in unhealthy_connections:
                            try:
                                await endpoints.connection_manager.disconnect(client_id)
                                await endpoints.subscription_manager.unsubscribe_all(client_id)
                            except Exception as e:
                                logger.error(f"Error cleaning up unhealthy connection {client_id}: {e}")
                    
                except Exception as e:
                    logger.error(f"Error in health check loop: {e}")
                    
        except asyncio.CancelledError:
            logger.info("Health check loop cancelled")
        except Exception as e:
            logger.error(f"Health check loop error: {e}")
    
    async def _stats_collection_loop(self):
        """统计收集循环"""
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(300)  # 每5分钟收集一次
                
                try:
                    # 收集统计信息
                    stats = await self.get_websocket_status()
                    
                    # 记录关键指标
                    logger.info(f"WebSocket Stats - Connections: {stats.get('active_connections', 0)}, "
                              f"Healthy: {stats.get('heartbeat', {}).get('healthy_connections', 0)}, "
                              f"Subscriptions: {stats.get('subscriptions', {}).get('total_subscriptions', 0)}")
                    
                except Exception as e:
                    logger.error(f"Error in stats collection loop: {e}")
                    
        except asyncio.CancelledError:
            logger.info("Stats collection loop cancelled")
        except Exception as e:
            logger.error(f"Stats collection loop error: {e}")
    
    async def _cleanup_failed_startup(self):
        """清理失败的启动"""
        try:
            logger.info("Cleaning up failed startup...")
            
            # 停止心跳和重连管理器
            try:
                await self.heartbeat_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping heartbeat manager: {e}")
            
            try:
                await self.reconnect_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping reconnect manager: {e}")
            
            # 停止WebSocket服务
            try:
                await stop_websocket_service()
            except Exception as e:
                logger.error(f"Error stopping WebSocket service: {e}")
            
            logger.info("Failed startup cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during failed startup cleanup: {e}")
    
    async def _force_shutdown(self):
        """强制关闭"""
        try:
            logger.warning("Forcing shutdown...")
            
            # 取消后台任务
            if hasattr(self, '_health_check_task') and self._health_check_task:
                self._health_check_task.cancel()
            
            if hasattr(self, '_stats_collection_task') and self._stats_collection_task:
                self._stats_collection_task.cancel()
            
            # 强制关闭所有连接
            endpoints = get_enhanced_websocket_endpoints()
            for client_id in list(self._active_connections.keys()):
                try:
                    await endpoints.connection_manager.disconnect(client_id)
                except Exception as e:
                    logger.error(f"Error force closing connection {client_id}: {e}")
            
            # 清理状态
            self._active_connections.clear()
            
            # 强制停止所有服务
            try:
                await self.heartbeat_manager.stop()
            except Exception as e:
                logger.error(f"Error force stopping heartbeat manager: {e}")
            
            try:
                await self.reconnect_manager.stop()
            except Exception as e:
                logger.error(f"Error force stopping reconnect manager: {e}")
            
            try:
                await stop_websocket_service()
            except Exception as e:
                logger.error(f"Error force stopping WebSocket service: {e}")
            
            logger.info("Force shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during force shutdown: {e}")
    
    def register_active_connection(self, client_id: str, websocket):
        """注册活跃连接"""
        self._active_connections[client_id] = websocket
        logger.debug(f"Registered active connection: {client_id}")
    
    def unregister_active_connection(self, client_id: str):
        """取消注册活跃连接"""
        if client_id in self._active_connections:
            del self._active_connections[client_id]
            logger.debug(f"Unregistered active connection: {client_id}")
    
    async def enable_heartbeat_for_connection(self, client_id: str, websocket):
        """为连接启用心跳"""
        try:
            await self.heartbeat_manager.register_connection(client_id, websocket)
            self.register_active_connection(client_id, websocket)
            logger.info(f"Heartbeat enabled for connection: {client_id}")
            
        except Exception as e:
            logger.error(f"Error enabling heartbeat for {client_id}: {e}")
    
    async def disable_heartbeat_for_connection(self, client_id: str):
        """为连接禁用心跳"""
        try:
            await self.heartbeat_manager.unregister_connection(client_id)
            self.unregister_active_connection(client_id)
            logger.info(f"Heartbeat disabled for connection: {client_id}")
            
        except Exception as e:
            logger.error(f"Error disabling heartbeat for {client_id}: {e}")
    
    async def get_websocket_status(self) -> dict:
        """获取 WebSocket 服务状态"""
        try:
            if not self._is_integrated:
                return {"status": "not_integrated"}
            
            # 获取服务状态
            endpoints = get_enhanced_websocket_endpoints()
            connection_stats = endpoints.connection_manager.get_stats()
            subscription_stats = await endpoints.subscription_manager.get_subscription_stats()
            heartbeat_stats = self.heartbeat_manager.get_heartbeat_stats()
            
            return {
                "status": "running" if endpoints._is_running else "stopped",
                "integrated": self._is_integrated,
                "connections": connection_stats,
                "subscriptions": subscription_stats,
                "heartbeat": heartbeat_stats,
                "active_connections": len(self._active_connections),
                "shutdown_initiated": self._shutdown_event.is_set(),
                "config": {
                    "max_connections": self.websocket_config.max_connections,
                    "max_subscriptions_per_client": self.websocket_config.max_subscriptions_per_client,
                    "heartbeat_interval": self.websocket_config.heartbeat_interval,
                    "connection_timeout": self.websocket_config.connection_timeout,
                    "heartbeat_config": {
                        "interval": self.heartbeat_config.interval,
                        "timeout": self.heartbeat_config.timeout,
                        "max_missed_heartbeats": self.heartbeat_config.max_missed_heartbeats,
                        "reconnect_interval": self.heartbeat_config.reconnect_interval,
                        "max_reconnect_attempts": self.heartbeat_config.max_reconnect_attempts
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting WebSocket status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def restart_websocket_service(self):
        """重启 WebSocket 服务"""
        try:
            logger.info("Restarting WebSocket service...")
            await stop_websocket_service()
            await asyncio.sleep(1)  # 等待完全停止
            await start_websocket_service()
            logger.info("WebSocket service restarted successfully")
            return {"success": True, "message": "WebSocket service restarted"}
            
        except Exception as e:
            logger.error(f"Error restarting WebSocket service: {e}")
            return {"success": False, "error": str(e)}


def create_websocket_app(
    title: str = "WebSocket Real-time Data Service",
    version: str = "2.0.0",
    websocket_config: Optional[WebSocketConfig] = None
) -> FastAPI:
    """创建集成了 WebSocket 功能的 FastAPI 应用"""
    
    # 创建 FastAPI 应用
    app = FastAPI(
        title=title,
        version=version,
        description="Real-time financial data WebSocket service with FastAPI integration"
    )
    
    # 添加 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 创建集成实例
    integration = WebSocketFastAPIIntegration(websocket_config=websocket_config)
    
    # 集成 WebSocket 功能
    app = integration.integrate_with_app(app)
    
    # 添加健康检查端点
    @app.get("/health")
    async def health_check():
        """健康检查端点"""
        websocket_status = await integration.get_websocket_status()
        return {
            "status": "healthy",
            "service": "WebSocket Real-time Data Service",
            "version": version,
            "websocket": websocket_status
        }
    
    # 添加 WebSocket 管理端点
    @app.get("/api/v1/ws/admin/status")
    async def websocket_admin_status():
        """WebSocket 管理状态"""
        return await integration.get_websocket_status()
    
    @app.post("/api/v1/ws/admin/restart")
    async def websocket_admin_restart():
        """重启 WebSocket 服务"""
        return await integration.restart_websocket_service()
    
    # 存储集成实例到应用状态
    app.state.websocket_integration = integration
    
    logger.info(f"WebSocket FastAPI application created: {title} v{version}")
    
    return app


def integrate_websocket_with_existing_app(
    app: FastAPI,
    websocket_config: Optional[WebSocketConfig] = None
) -> WebSocketFastAPIIntegration:
    """将 WebSocket 功能集成到现有的 FastAPI 应用中"""
    
    integration = WebSocketFastAPIIntegration(websocket_config=websocket_config)
    integration.integrate_with_app(app)
    
    # 添加管理端点
    @app.get("/api/v1/ws/admin/status")
    async def websocket_admin_status():
        """WebSocket 管理状态"""
        return await integration.get_websocket_status()
    
    @app.post("/api/v1/ws/admin/restart")
    async def websocket_admin_restart():
        """重启 WebSocket 服务"""
        return await integration.restart_websocket_service()
    
    # 存储集成实例到应用状态
    app.state.websocket_integration = integration
    
    return integration


# 导出主要组件
__all__ = [
    "WebSocketFastAPIIntegration",
    "create_websocket_app",
    "integrate_websocket_with_existing_app"
]