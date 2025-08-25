"""
WebSocket 实时数据系统 - 服务器主入口
根据 tasks.md 任务9要求实现的容器化部署支持
"""

import asyncio
import logging
import json
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from .websocket_server import WebSocketServer
from .websocket_connection_manager import WebSocketConnectionManager
from .subscription_manager import SubscriptionManager
from .data_publisher import DataPublisher
from .websocket_monitor import WebSocketMonitor
from .load_balancer import LoadBalancer, RateLimitConfig
from .service_discovery import ServiceDiscovery, DiscoveryConfig, DiscoveryBackend
from .scaling_manager import ScalingManager, ScalingConfig
from .data_integration_service import DataIntegrationService

logger = logging.getLogger(__name__)


class WebSocketServerApp:
    """WebSocket服务器应用程序"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "/app/config/websocket_config.json"
        self.config = self._load_config()
        
        # 设置日志
        self._setup_logging()
        
        # 初始化组件
        self.service_discovery: Optional[ServiceDiscovery] = None
        self.load_balancer: Optional[LoadBalancer] = None
        self.scaling_manager: Optional[ScalingManager] = None
        self.websocket_server: Optional[WebSocketServer] = None
        
        # 运行状态
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        
    def _load_config(self) -> dict:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_path}")
                return config
            else:
                logger.warning(f"Configuration file not found: {self.config_path}")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "websocket": {
                "host": os.getenv("WEBSOCKET_HOST", "0.0.0.0"),
                "port": int(os.getenv("WEBSOCKET_PORT", "8765")),
                "max_connections": int(os.getenv("MAX_CONNECTIONS", "1000")),
                "max_subscriptions_per_client": int(os.getenv("MAX_SUBSCRIPTIONS_PER_CLIENT", "100")),
                "heartbeat_interval": 30,
                "max_message_size": 1048576
            },
            "service_discovery": {
                "backend": os.getenv("SERVICE_DISCOVERY_BACKEND", "memory"),
                "consul_host": os.getenv("CONSUL_HOST", "localhost"),
                "consul_port": int(os.getenv("CONSUL_PORT", "8500")),
                "etcd_host": os.getenv("ETCD_HOST", "localhost"),
                "etcd_port": int(os.getenv("ETCD_PORT", "2379")),
                "service_name": "websocket-server",
                "health_check_interval": 10,
                "heartbeat_interval": 15
            },
            "load_balancing": {
                "strategy": os.getenv("LOAD_BALANCING_STRATEGY", "least_connections"),
                "rate_limit": {
                    "requests_per_minute": int(os.getenv("RATE_LIMIT_RPM", "60")),
                    "burst_size": 10
                }
            },
            "scaling": {
                "min_instances": int(os.getenv("MIN_INSTANCES", "1")),
                "max_instances": int(os.getenv("MAX_INSTANCES", "10")),
                "target_cpu_utilization": float(os.getenv("TARGET_CPU_UTILIZATION", "70")),
                "target_memory_utilization": float(os.getenv("TARGET_MEMORY_UTILIZATION", "80")),
                "target_connections_per_instance": 800,
                "scale_up_cooldown": 300,
                "scale_down_cooldown": 600,
                "evaluation_interval": 60
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "/app/logs/websocket-server.log"
            }
        }
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get("logging", {})
        log_level = getattr(logging, log_config.get("level", "INFO").upper())
        log_format = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_file = log_config.get("file")
        
        # 创建日志目录
        if log_file:
            log_dir = Path(log_file).parent
            log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置根日志器
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file) if log_file else logging.NullHandler()
            ]
        )
        
        logger.info(f"Logging configured: level={log_level}, file={log_file}")
    
    async def _initialize_service_discovery(self):
        """初始化服务发现"""
        sd_config = self.config.get("service_discovery", {})
        
        # 创建服务发现配置
        backend_str = sd_config.get("backend", "memory")
        backend = DiscoveryBackend(backend_str) if backend_str in DiscoveryBackend.__members__ else DiscoveryBackend.MEMORY
        
        discovery_config = DiscoveryConfig(
            backend=backend,
            consul_host=sd_config.get("consul_host", "localhost"),
            consul_port=sd_config.get("consul_port", 8500),
            etcd_host=sd_config.get("etcd_host", "localhost"),
            etcd_port=sd_config.get("etcd_port", 2379),
            service_name=sd_config.get("service_name", "websocket-server"),
            health_check_interval=sd_config.get("health_check_interval", 10),
            heartbeat_interval=sd_config.get("heartbeat_interval", 15),
            discovery_interval=sd_config.get("discovery_interval", 30)
        )
        
        self.service_discovery = ServiceDiscovery(discovery_config)
        await self.service_discovery.start()
        
        # 注册本地服务
        ws_config = self.config.get("websocket", {})
        local_ip = self.service_discovery.get_local_ip()
        health_check_url = f"http://{local_ip}:8080/health"
        
        await self.service_discovery.register_service(
            host=local_ip,
            port=ws_config.get("port", 8765),
            tags=["websocket", "realtime-data"],
            metadata={
                "version": "1.0.0",
                "max_connections": ws_config.get("max_connections", 1000),
                "pod_name": os.getenv("POD_NAME", ""),
                "pod_namespace": os.getenv("POD_NAMESPACE", ""),
                "pod_ip": os.getenv("POD_IP", local_ip)
            },
            health_check_url=health_check_url
        )
        
        logger.info("Service discovery initialized and service registered")
    
    async def _initialize_load_balancer(self):
        """初始化负载均衡器"""
        lb_config = self.config.get("load_balancing", {})
        
        # 创建速率限制配置
        rate_limit_config = RateLimitConfig(
            requests_per_minute=lb_config.get("rate_limit", {}).get("requests_per_minute", 60),
            burst_size=lb_config.get("rate_limit", {}).get("burst_size", 10)
        )
        
        # 创建负载均衡器
        from .load_balancer import LoadBalancingStrategy
        strategy_str = lb_config.get("strategy", "least_connections")
        strategy = LoadBalancingStrategy(strategy_str) if strategy_str in LoadBalancingStrategy.__members__ else LoadBalancingStrategy.LEAST_CONNECTIONS
        
        self.load_balancer = LoadBalancer(
            strategy=strategy,
            rate_limit_config=rate_limit_config
        )
        
        await self.load_balancer.start()
        logger.info("Load balancer initialized")
    
    async def _initialize_scaling_manager(self):
        """初始化扩展管理器"""
        scaling_config_dict = self.config.get("scaling", {})
        
        scaling_config = ScalingConfig(
            min_instances=scaling_config_dict.get("min_instances", 1),
            max_instances=scaling_config_dict.get("max_instances", 10),
            target_cpu_utilization=scaling_config_dict.get("target_cpu_utilization", 70.0),
            target_memory_utilization=scaling_config_dict.get("target_memory_utilization", 80.0),
            target_connections_per_instance=scaling_config_dict.get("target_connections_per_instance", 800),
            scale_up_cooldown=scaling_config_dict.get("scale_up_cooldown", 300),
            scale_down_cooldown=scaling_config_dict.get("scale_down_cooldown", 600),
            evaluation_interval=scaling_config_dict.get("evaluation_interval", 60)
        )
        
        self.scaling_manager = ScalingManager(
            self.load_balancer,
            self.service_discovery,
            scaling_config
        )
        
        # 添加扩展回调
        self.scaling_manager.add_scale_up_callback(self._handle_scale_up)
        self.scaling_manager.add_scale_down_callback(self._handle_scale_down)
        
        await self.scaling_manager.start()
        logger.info("Scaling manager initialized")
    
    async def _initialize_websocket_server(self):
        """初始化WebSocket服务器"""
        ws_config = self.config.get("websocket", {})
        
        # 创建WebSocket组件
        connection_manager = WebSocketConnectionManager()
        subscription_manager = SubscriptionManager()
        data_publisher = DataPublisher(connection_manager, subscription_manager)
        monitor = WebSocketMonitor()
        data_integration = DataIntegrationService()
        
        # 创建WebSocket服务器
        self.websocket_server = WebSocketServer(
            host=ws_config.get("host", "0.0.0.0"),
            port=ws_config.get("port", 8765),
            connection_manager=connection_manager,
            subscription_manager=subscription_manager,
            data_publisher=data_publisher,
            monitor=monitor,
            data_integration=data_integration,
            max_connections=ws_config.get("max_connections", 1000),
            max_subscriptions_per_client=ws_config.get("max_subscriptions_per_client", 100)
        )
        
        logger.info("WebSocket server initialized")
    
    def _handle_scale_up(self, count: int):
        """处理扩容事件"""
        logger.info(f"Scale up requested: {count} instances")
        # 在实际部署中，这里会调用Kubernetes API或Docker API来创建新实例
        # 这里只是记录日志
    
    def _handle_scale_down(self, instance_ids: list):
        """处理缩容事件"""
        logger.info(f"Scale down requested: {len(instance_ids)} instances")
        # 在实际部署中，这里会优雅关闭指定的实例
        # 这里只是记录日志
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self):
        """启动应用程序"""
        if self.is_running:
            return
        
        logger.info("Starting WebSocket Server Application...")
        
        try:
            # 初始化组件
            await self._initialize_service_discovery()
            await self._initialize_load_balancer()
            await self._initialize_scaling_manager()
            await self._initialize_websocket_server()
            
            # 启动WebSocket服务器
            await self.websocket_server.start()
            
            self.is_running = True
            logger.info("WebSocket Server Application started successfully")
            
            # 等待关闭信号
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            await self.shutdown()
            raise
    
    async def shutdown(self):
        """关闭应用程序"""
        if not self.is_running:
            return
        
        logger.info("Shutting down WebSocket Server Application...")
        
        try:
            # 停止WebSocket服务器
            if self.websocket_server:
                await self.websocket_server.stop()
            
            # 停止扩展管理器
            if self.scaling_manager:
                await self.scaling_manager.stop()
            
            # 停止负载均衡器
            if self.load_balancer:
                await self.load_balancer.stop()
            
            # 停止服务发现
            if self.service_discovery:
                await self.service_discovery.stop()
            
            self.is_running = False
            self._shutdown_event.set()
            
            logger.info("WebSocket Server Application shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def health_check(self) -> dict:
        """健康检查"""
        health_status = {
            "status": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "components": {}
        }
        
        try:
            # 检查WebSocket服务器
            if self.websocket_server:
                ws_stats = await self.websocket_server.get_stats()
                health_status["components"]["websocket_server"] = {
                    "status": "healthy" if ws_stats["is_running"] else "unhealthy",
                    "connections": ws_stats["active_connections"],
                    "subscriptions": ws_stats["total_subscriptions"]
                }
            
            # 检查服务发现
            if self.service_discovery:
                sd_stats = self.service_discovery.get_stats()
                health_status["components"]["service_discovery"] = {
                    "status": "healthy" if sd_stats["local_instance"] else "unhealthy",
                    "discovered_services": sd_stats["discovered_services"],
                    "healthy_services": sd_stats["healthy_services"]
                }
            
            # 检查负载均衡器
            if self.load_balancer:
                lb_stats = self.load_balancer.get_stats()
                health_status["components"]["load_balancer"] = {
                    "status": "healthy" if lb_stats["healthy_nodes"] > 0 else "unhealthy",
                    "total_nodes": lb_stats["total_nodes"],
                    "healthy_nodes": lb_stats["healthy_nodes"]
                }
            
            # 检查扩展管理器
            if self.scaling_manager:
                sm_stats = self.scaling_manager.get_stats()
                health_status["components"]["scaling_manager"] = {
                    "status": "healthy",
                    "min_instances": sm_stats["config"]["min_instances"],
                    "max_instances": sm_stats["config"]["max_instances"]
                }
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status


async def main():
    """主函数"""
    # 创建应用程序
    app = WebSocketServerApp()
    
    # 设置信号处理器
    app._setup_signal_handlers()
    
    try:
        # 启动应用程序
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())