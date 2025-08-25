"""
WebSocket 实时数据系统 - 负载均衡器主入口
根据 tasks.md 任务9要求实现的独立负载均衡器服务
"""

import asyncio
import logging
import json
import os
import signal
import sys
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from .load_balancer import LoadBalancer, RateLimitConfig, LoadBalancingStrategy
from .service_discovery import ServiceDiscovery, DiscoveryConfig, DiscoveryBackend
from .scaling_manager import ScalingManager, ScalingConfig

logger = logging.getLogger(__name__)


class LoadBalancerApp:
    """独立负载均衡器应用程序"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "/app/config/websocket_config.json"
        self.config = self._load_config()
        
        # 设置日志
        self._setup_logging()
        
        # 初始化组件
        self.service_discovery: Optional[ServiceDiscovery] = None
        self.load_balancer: Optional[LoadBalancer] = None
        self.scaling_manager: Optional[ScalingManager] = None
        
        # FastAPI应用
        self.app = FastAPI(
            title="WebSocket Load Balancer",
            description="负载均衡器管理API",
            version="1.0.0"
        )
        self._setup_routes()
        
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
            "service_discovery": {
                "backend": os.getenv("SERVICE_DISCOVERY_BACKEND", "memory"),
                "consul_host": os.getenv("CONSUL_HOST", "localhost"),
                "consul_port": int(os.getenv("CONSUL_PORT", "8500")),
                "service_name": "websocket-server",
                "health_check_interval": 10,
                "heartbeat_interval": 15,
                "discovery_interval": 30
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
            "api": {
                "host": "0.0.0.0",
                "port": 8090
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "/app/logs/load-balancer.log"
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
    
    def _setup_routes(self):
        """设置API路由"""
        
        @self.app.get("/health")
        async def health_check():
            """健康检查"""
            try:
                health_status = await self.health_check()
                return JSONResponse(content=health_status)
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/stats")
        async def get_stats():
            """获取统计信息"""
            try:
                stats = {}
                
                if self.load_balancer:
                    stats["load_balancer"] = self.load_balancer.get_stats()
                
                if self.service_discovery:
                    stats["service_discovery"] = self.service_discovery.get_stats()
                
                if self.scaling_manager:
                    stats["scaling_manager"] = self.scaling_manager.get_stats()
                
                return JSONResponse(content=stats)
            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/nodes")
        async def get_nodes():
            """获取节点信息"""
            try:
                if not self.load_balancer:
                    raise HTTPException(status_code=503, detail="Load balancer not available")
                
                stats = self.load_balancer.get_stats()
                return JSONResponse(content=stats.get("nodes", {}))
            except Exception as e:
                logger.error(f"Failed to get nodes: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/services")
        async def get_services():
            """获取服务实例"""
            try:
                if not self.service_discovery:
                    raise HTTPException(status_code=503, detail="Service discovery not available")
                
                instances = await self.service_discovery.discover_services()
                return JSONResponse(content=[
                    {
                        "service_id": instance.service_id,
                        "service_name": instance.service_name,
                        "host": instance.host,
                        "port": instance.port,
                        "status": instance.status,
                        "tags": instance.tags,
                        "metadata": instance.metadata
                    }
                    for instance in instances
                ])
            except Exception as e:
                logger.error(f"Failed to get services: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/scale/up")
        async def scale_up(count: int = 1):
            """手动扩容"""
            try:
                if not self.scaling_manager:
                    raise HTTPException(status_code=503, detail="Scaling manager not available")
                
                success = await self.scaling_manager.scale_up(count)
                return JSONResponse(content={"success": success, "count": count})
            except Exception as e:
                logger.error(f"Failed to scale up: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/scale/down")
        async def scale_down(count: int = 1):
            """手动缩容"""
            try:
                if not self.scaling_manager:
                    raise HTTPException(status_code=503, detail="Scaling manager not available")
                
                success = await self.scaling_manager.scale_down(count)
                return JSONResponse(content={"success": success, "count": count})
            except Exception as e:
                logger.error(f"Failed to scale down: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/scaling/evaluate")
        async def evaluate_scaling():
            """评估扩展需求"""
            try:
                if not self.scaling_manager:
                    raise HTTPException(status_code=503, detail="Scaling manager not available")
                
                action = await self.scaling_manager.evaluate_scaling()
                return JSONResponse(content={"recommended_action": action})
            except Exception as e:
                logger.error(f"Failed to evaluate scaling: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/client/{client_id}")
        async def get_client_stats(client_id: str):
            """获取客户端统计信息"""
            try:
                if not self.load_balancer:
                    raise HTTPException(status_code=503, detail="Load balancer not available")
                
                stats = await self.load_balancer.get_client_stats(client_id)
                if stats is None:
                    raise HTTPException(status_code=404, detail="Client not found")
                
                return JSONResponse(content=stats)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get client stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
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
        
        # 添加服务变更监听器
        self.service_discovery.add_service_listener(self._on_services_changed)
        
        logger.info("Service discovery initialized")
    
    async def _initialize_load_balancer(self):
        """初始化负载均衡器"""
        lb_config = self.config.get("load_balancing", {})
        
        # 创建速率限制配置
        rate_limit_config = RateLimitConfig(
            requests_per_minute=lb_config.get("rate_limit", {}).get("requests_per_minute", 60),
            burst_size=lb_config.get("rate_limit", {}).get("burst_size", 10)
        )
        
        # 创建负载均衡器
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
    
    def _on_services_changed(self, instances):
        """服务变更回调"""
        logger.info(f"Services changed: {len(instances)} instances discovered")
        
        # 更新负载均衡器节点
        if self.load_balancer:
            # 清除现有节点
            current_nodes = list(self.load_balancer.nodes.keys())
            for node_id in current_nodes:
                self.load_balancer.remove_node(node_id)
            
            # 添加新节点
            from .load_balancer import ServerNode
            for instance in instances:
                if instance.status.value == "healthy":
                    node = ServerNode(
                        node_id=f"{instance.host}:{instance.port}",
                        host=instance.host,
                        port=instance.port,
                        max_connections=instance.metadata.get("max_connections", 1000)
                    )
                    self.load_balancer.add_node(node)
    
    def _handle_scale_up(self, count: int):
        """处理扩容事件"""
        logger.info(f"Scale up requested: {count} instances")
        # 在实际部署中，这里会调用Kubernetes API或Docker API来创建新实例
    
    def _handle_scale_down(self, instance_ids: list):
        """处理缩容事件"""
        logger.info(f"Scale down requested: {len(instance_ids)} instances")
        # 在实际部署中，这里会优雅关闭指定的实例
    
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
        
        logger.info("Starting Load Balancer Application...")
        
        try:
            # 初始化组件
            await self._initialize_service_discovery()
            await self._initialize_load_balancer()
            await self._initialize_scaling_manager()
            
            self.is_running = True
            logger.info("Load Balancer Application started successfully")
            
            # 启动API服务器
            api_config = self.config.get("api", {})
            config = uvicorn.Config(
                self.app,
                host=api_config.get("host", "0.0.0.0"),
                port=api_config.get("port", 8090),
                log_level="info"
            )
            server = uvicorn.Server(config)
            
            # 在后台运行API服务器
            api_task = asyncio.create_task(server.serve())
            
            # 等待关闭信号
            await self._shutdown_event.wait()
            
            # 停止API服务器
            server.should_exit = True
            await api_task
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            await self.shutdown()
            raise
    
    async def shutdown(self):
        """关闭应用程序"""
        if not self.is_running:
            return
        
        logger.info("Shutting down Load Balancer Application...")
        
        try:
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
            
            logger.info("Load Balancer Application shut down successfully")
            
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
            # 检查服务发现
            if self.service_discovery:
                sd_stats = self.service_discovery.get_stats()
                health_status["components"]["service_discovery"] = {
                    "status": "healthy",
                    "discovered_services": sd_stats["discovered_services"],
                    "healthy_services": sd_stats["healthy_services"]
                }
            
            # 检查负载均衡器
            if self.load_balancer:
                lb_stats = self.load_balancer.get_stats()
                health_status["components"]["load_balancer"] = {
                    "status": "healthy" if lb_stats["healthy_nodes"] > 0 else "degraded",
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
    app = LoadBalancerApp()
    
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