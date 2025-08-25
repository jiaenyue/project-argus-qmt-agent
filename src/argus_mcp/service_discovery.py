"""
WebSocket 实时数据系统 - 服务发现
根据 tasks.md 任务9要求实现的服务发现和注册中心
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import socket

from .load_balancer import ServerNode

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """服务状态"""
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"


class DiscoveryBackend(str, Enum):
    """服务发现后端类型"""
    CONSUL = "consul"
    ETCD = "etcd"
    REDIS = "redis"
    MEMORY = "memory"  # 内存模式，用于测试


@dataclass
class ServiceInstance:
    """服务实例信息"""
    service_id: str
    service_name: str
    host: str
    port: int
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_check_url: Optional[str] = None
    status: ServiceStatus = ServiceStatus.STARTING
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    ttl: int = 30  # 生存时间（秒）


@dataclass
class DiscoveryConfig:
    """服务发现配置"""
    backend: DiscoveryBackend = DiscoveryBackend.MEMORY
    consul_host: str = "localhost"
    consul_port: int = 8500
    etcd_host: str = "localhost"
    etcd_port: int = 2379
    redis_host: str = "localhost"
    redis_port: int = 6379
    service_name: str = "websocket-server"
    health_check_interval: int = 10
    heartbeat_interval: int = 15
    discovery_interval: int = 30


class ServiceDiscovery:
    """服务发现管理器"""
    
    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.local_instance: Optional[ServiceInstance] = None
        self.discovered_services: Dict[str, ServiceInstance] = {}
        self.service_listeners: List[Callable[[List[ServiceInstance]], None]] = []
        
        # 后台任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._discovery_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        # HTTP客户端（用于健康检查和API调用）
        self._http_session: Optional[aiohttp.ClientSession] = None
        
    async def start(self) -> None:
        """启动服务发现"""
        if self._is_running:
            return
            
        logger.info(f"Starting ServiceDiscovery with backend: {self.config.backend}")
        self._is_running = True
        
        # 创建HTTP会话
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5)
        )
        
        # 启动后台任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
    async def stop(self) -> None:
        """停止服务发现"""
        if not self._is_running:
            return
            
        logger.info("Stopping ServiceDiscovery")
        self._is_running = False
        
        # 注销本地服务
        if self.local_instance:
            await self.deregister_service(self.local_instance.service_id)
            
        # 停止后台任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._discovery_task:
            self._discovery_task.cancel()
        if self._health_check_task:
            self._health_check_task.cancel()
            
        # 关闭HTTP会话
        if self._http_session:
            await self._http_session.close()
            
    async def register_service(
        self,
        host: str,
        port: int,
        service_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        health_check_url: Optional[str] = None
    ) -> ServiceInstance:
        """注册服务实例"""
        if not service_id:
            service_id = f"{self.config.service_name}-{host}-{port}"
            
        instance = ServiceInstance(
            service_id=service_id,
            service_name=self.config.service_name,
            host=host,
            port=port,
            tags=tags or [],
            metadata=metadata or {},
            health_check_url=health_check_url
        )
        
        # 根据后端类型注册服务
        if self.config.backend == DiscoveryBackend.CONSUL:
            await self._register_consul(instance)
        elif self.config.backend == DiscoveryBackend.ETCD:
            await self._register_etcd(instance)
        elif self.config.backend == DiscoveryBackend.REDIS:
            await self._register_redis(instance)
        else:  # MEMORY
            await self._register_memory(instance)
            
        self.local_instance = instance
        instance.status = ServiceStatus.HEALTHY
        
        logger.info(f"Registered service {service_id} at {host}:{port}")
        return instance
        
    async def deregister_service(self, service_id: str) -> bool:
        """注销服务实例"""
        try:
            # 根据后端类型注销服务
            if self.config.backend == DiscoveryBackend.CONSUL:
                await self._deregister_consul(service_id)
            elif self.config.backend == DiscoveryBackend.ETCD:
                await self._deregister_etcd(service_id)
            elif self.config.backend == DiscoveryBackend.REDIS:
                await self._deregister_redis(service_id)
            else:  # MEMORY
                await self._deregister_memory(service_id)
                
            if self.local_instance and self.local_instance.service_id == service_id:
                self.local_instance.status = ServiceStatus.STOPPED
                
            logger.info(f"Deregistered service {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deregister service {service_id}: {e}")
            return False
            
    async def discover_services(
        self,
        service_name: Optional[str] = None
    ) -> List[ServiceInstance]:
        """发现服务实例"""
        target_service = service_name or self.config.service_name
        
        try:
            # 根据后端类型发现服务
            if self.config.backend == DiscoveryBackend.CONSUL:
                instances = await self._discover_consul(target_service)
            elif self.config.backend == DiscoveryBackend.ETCD:
                instances = await self._discover_etcd(target_service)
            elif self.config.backend == DiscoveryBackend.REDIS:
                instances = await self._discover_redis(target_service)
            else:  # MEMORY
                instances = await self._discover_memory(target_service)
                
            # 更新本地缓存
            for instance in instances:
                self.discovered_services[instance.service_id] = instance
                
            # 移除过期的服务
            current_ids = {instance.service_id for instance in instances}
            expired_ids = set(self.discovered_services.keys()) - current_ids
            for expired_id in expired_ids:
                del self.discovered_services[expired_id]
                
            return instances
            
        except Exception as e:
            logger.error(f"Failed to discover services: {e}")
            return list(self.discovered_services.values())
            
    def add_service_listener(
        self,
        callback: Callable[[List[ServiceInstance]], None]
    ) -> None:
        """添加服务变更监听器"""
        self.service_listeners.append(callback)
        
    def remove_service_listener(
        self,
        callback: Callable[[List[ServiceInstance]], None]
    ) -> None:
        """移除服务变更监听器"""
        if callback in self.service_listeners:
            self.service_listeners.remove(callback)
            
    async def get_healthy_instances(
        self,
        service_name: Optional[str] = None
    ) -> List[ServiceInstance]:
        """获取健康的服务实例"""
        instances = await self.discover_services(service_name)
        return [
            instance for instance in instances
            if instance.status == ServiceStatus.HEALTHY
        ]
        
    async def _register_consul(self, instance: ServiceInstance) -> None:
        """在Consul中注册服务"""
        url = f"http://{self.config.consul_host}:{self.config.consul_port}/v1/agent/service/register"
        
        payload = {
            "ID": instance.service_id,
            "Name": instance.service_name,
            "Tags": instance.tags,
            "Address": instance.host,
            "Port": instance.port,
            "Meta": instance.metadata
        }
        
        # 添加健康检查
        if instance.health_check_url:
            payload["Check"] = {
                "HTTP": instance.health_check_url,
                "Interval": f"{self.config.health_check_interval}s",
                "Timeout": "5s"
            }
        else:
            payload["Check"] = {
                "TTL": f"{instance.ttl}s"
            }
            
        async with self._http_session.put(url, json=payload) as response:
            if response.status != 200:
                raise Exception(f"Consul registration failed: {response.status}")
                
    async def _deregister_consul(self, service_id: str) -> None:
        """从Consul注销服务"""
        url = f"http://{self.config.consul_host}:{self.config.consul_port}/v1/agent/service/deregister/{service_id}"
        
        async with self._http_session.put(url) as response:
            if response.status != 200:
                raise Exception(f"Consul deregistration failed: {response.status}")
                
    async def _discover_consul(self, service_name: str) -> List[ServiceInstance]:
        """从Consul发现服务"""
        url = f"http://{self.config.consul_host}:{self.config.consul_port}/v1/health/service/{service_name}?passing=true"
        
        async with self._http_session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Consul discovery failed: {response.status}")
                
            data = await response.json()
            instances = []
            
            for item in data:
                service = item["Service"]
                instance = ServiceInstance(
                    service_id=service["ID"],
                    service_name=service["Service"],
                    host=service["Address"],
                    port=service["Port"],
                    tags=service.get("Tags", []),
                    metadata=service.get("Meta", {}),
                    status=ServiceStatus.HEALTHY
                )
                instances.append(instance)
                
            return instances
            
    async def _register_etcd(self, instance: ServiceInstance) -> None:
        """在etcd中注册服务"""
        # 简化实现，实际应使用etcd3客户端
        key = f"/services/{instance.service_name}/{instance.service_id}"
        value = json.dumps({
            "host": instance.host,
            "port": instance.port,
            "tags": instance.tags,
            "metadata": instance.metadata,
            "registered_at": instance.registered_at.isoformat()
        })
        
        url = f"http://{self.config.etcd_host}:{self.config.etcd_port}/v2/keys{key}"
        payload = {"value": value, "ttl": instance.ttl}
        
        async with self._http_session.put(url, data=payload) as response:
            if response.status not in [200, 201]:
                raise Exception(f"etcd registration failed: {response.status}")
                
    async def _deregister_etcd(self, service_id: str) -> None:
        """从etcd注销服务"""
        key = f"/services/{self.config.service_name}/{service_id}"
        url = f"http://{self.config.etcd_host}:{self.config.etcd_port}/v2/keys{key}"
        
        async with self._http_session.delete(url) as response:
            if response.status not in [200, 404]:
                raise Exception(f"etcd deregistration failed: {response.status}")
                
    async def _discover_etcd(self, service_name: str) -> List[ServiceInstance]:
        """从etcd发现服务"""
        key = f"/services/{service_name}"
        url = f"http://{self.config.etcd_host}:{self.config.etcd_port}/v2/keys{key}?recursive=true"
        
        async with self._http_session.get(url) as response:
            if response.status == 404:
                return []
            if response.status != 200:
                raise Exception(f"etcd discovery failed: {response.status}")
                
            data = await response.json()
            instances = []
            
            if "node" in data and "nodes" in data["node"]:
                for node in data["node"]["nodes"]:
                    try:
                        service_data = json.loads(node["value"])
                        service_id = node["key"].split("/")[-1]
                        
                        instance = ServiceInstance(
                            service_id=service_id,
                            service_name=service_name,
                            host=service_data["host"],
                            port=service_data["port"],
                            tags=service_data.get("tags", []),
                            metadata=service_data.get("metadata", {}),
                            status=ServiceStatus.HEALTHY
                        )
                        instances.append(instance)
                    except Exception as e:
                        logger.warning(f"Failed to parse etcd node: {e}")
                        
            return instances
            
    async def _register_redis(self, instance: ServiceInstance) -> None:
        """在Redis中注册服务"""
        # 简化实现，实际应使用Redis客户端
        logger.warning("Redis backend not fully implemented")
        
    async def _deregister_redis(self, service_id: str) -> None:
        """从Redis注销服务"""
        logger.warning("Redis backend not fully implemented")
        
    async def _discover_redis(self, service_name: str) -> List[ServiceInstance]:
        """从Redis发现服务"""
        logger.warning("Redis backend not fully implemented")
        return []
        
    async def _register_memory(self, instance: ServiceInstance) -> None:
        """在内存中注册服务（测试用）"""
        self.discovered_services[instance.service_id] = instance
        
    async def _deregister_memory(self, service_id: str) -> None:
        """从内存注销服务（测试用）"""
        if service_id in self.discovered_services:
            del self.discovered_services[service_id]
            
    async def _discover_memory(self, service_name: str) -> List[ServiceInstance]:
        """从内存发现服务（测试用）"""
        return [
            instance for instance in self.discovered_services.values()
            if instance.service_name == service_name
        ]
        
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._is_running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                if self.local_instance:
                    # 发送心跳
                    if self.config.backend == DiscoveryBackend.CONSUL:
                        await self._consul_heartbeat()
                    elif self.config.backend == DiscoveryBackend.ETCD:
                        await self._etcd_heartbeat()
                        
                    self.local_instance.last_heartbeat = datetime.now()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                
    async def _discovery_loop(self) -> None:
        """服务发现循环"""
        while self._is_running:
            try:
                await asyncio.sleep(self.config.discovery_interval)
                
                old_services = set(self.discovered_services.keys())
                instances = await self.discover_services()
                new_services = set(self.discovered_services.keys())
                
                # 如果服务列表发生变化，通知监听器
                if old_services != new_services:
                    for listener in self.service_listeners:
                        try:
                            listener(instances)
                        except Exception as e:
                            logger.error(f"Error in service listener: {e}")
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self._is_running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                # 检查发现的服务健康状态
                for instance in list(self.discovered_services.values()):
                    if instance.health_check_url:
                        is_healthy = await self._check_instance_health(instance)
                        old_status = instance.status
                        instance.status = ServiceStatus.HEALTHY if is_healthy else ServiceStatus.UNHEALTHY
                        
                        if old_status != instance.status:
                            logger.info(f"Service {instance.service_id} status changed: {old_status} -> {instance.status}")
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                
    async def _consul_heartbeat(self) -> None:
        """Consul心跳"""
        if not self.local_instance:
            return
            
        url = f"http://{self.config.consul_host}:{self.config.consul_port}/v1/agent/check/pass/service:{self.local_instance.service_id}"
        
        try:
            async with self._http_session.put(url) as response:
                if response.status != 200:
                    logger.warning(f"Consul heartbeat failed: {response.status}")
        except Exception as e:
            logger.error(f"Consul heartbeat error: {e}")
            
    async def _etcd_heartbeat(self) -> None:
        """etcd心跳（通过续租实现）"""
        if not self.local_instance:
            return
            
        # 重新注册以续租
        await self._register_etcd(self.local_instance)
        
    async def _check_instance_health(self, instance: ServiceInstance) -> bool:
        """检查实例健康状态"""
        if not instance.health_check_url:
            return True
            
        try:
            async with self._http_session.get(instance.health_check_url) as response:
                return response.status == 200
        except Exception:
            return False
            
    def get_local_ip(self) -> str:
        """获取本地IP地址"""
        try:
            # 连接到一个远程地址来获取本地IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
            
    def get_stats(self) -> Dict[str, Any]:
        """获取服务发现统计信息"""
        return {
            "backend": self.config.backend,
            "local_instance": {
                "service_id": self.local_instance.service_id,
                "status": self.local_instance.status,
                "registered_at": self.local_instance.registered_at.isoformat(),
                "last_heartbeat": self.local_instance.last_heartbeat.isoformat()
            } if self.local_instance else None,
            "discovered_services": len(self.discovered_services),
            "healthy_services": len([
                s for s in self.discovered_services.values()
                if s.status == ServiceStatus.HEALTHY
            ]),
            "service_listeners": len(self.service_listeners)
        }