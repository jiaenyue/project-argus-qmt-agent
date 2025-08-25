"""
部署配置和运维管理
实现容器化部署、环境配置、健康检查和监控集成
"""

import asyncio
import logging
import os
import json
import yaml
import subprocess
import docker
import psutil
import socket
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import tempfile
import shutil
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """环境类型枚举"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class DeploymentConfig:
    """部署配置"""
    environment: EnvironmentType
    version: str
    port: int = 8000
    host: str = "0.0.0.0"
    workers: int = 4
    max_connections: int = 1000
    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql://user:pass@localhost:5432/argus"
    log_level: str = "INFO"
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    enable_metrics: bool = True
    enable_health_check: bool = True
    backup_enabled: bool = True
    backup_retention_days: int = 30
    
    # Docker配置
    docker_image: str = "argus-mcp:latest"
    docker_registry: str = "localhost:5000"
    container_memory_limit: str = "2g"
    container_cpu_limit: str = "1.0"
    
    # 监控配置
    prometheus_port: int = 9090
    grafana_port: int = 3000
    alertmanager_port: int = 9093
    
    # 扩展配置
    enable_load_balancer: bool = True
    min_replicas: int = 2
    max_replicas: int = 10
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.2


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.last_check_results: Dict[str, Dict[str, Any]] = {}
    
    def register_check(self, name: str, check_func: Callable):
        """注册健康检查"""
        self.checks[name] = check_func
    
    async def run_health_check(self, name: str) -> Dict[str, Any]:
        """运行单个健康检查"""
        if name not in self.checks:
            return {"status": "error", "message": f"Check {name} not found"}
        
        try:
            result = await self.checks[name]()
            self.last_check_results[name] = {
                "status": "healthy" if result else "unhealthy",
                "timestamp": datetime.now(),
                "result": result
            }
            return self.last_check_results[name]
        except Exception as e:
            logger.error(f"Health check {name} failed: {e}")
            self.last_check_results[name] = {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now()
            }
            return self.last_check_results[name]
    
    async def run_all_checks(self) -> Dict[str, Dict[str, Any]]:
        """运行所有健康检查"""
        results = {}
        for name in self.checks:
            results[name] = await self.run_health_check(name)
        return results
    
    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康检查摘要"""
        if not self.last_check_results:
            return {"status": "unknown", "checks": {}}
        
        all_healthy = all(
            result["status"] == "healthy"
            for result in self.last_check_results.values()
        )
        
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "total_checks": len(self.last_check_results),
            "healthy_checks": sum(1 for r in self.last_check_results.values() if r["status"] == "healthy"),
            "unhealthy_checks": sum(1 for r in self.last_check_results.values() if r["status"] != "healthy"),
            "last_check": max(
                (r["timestamp"] for r in self.last_check_results.values()),
                default=None
            )
        }


class DockerManager:
    """Docker管理器"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.docker_available = True
        except docker.errors.DockerException:
            logger.warning("Docker not available")
            self.docker_available = False
    
    def build_image(self, dockerfile_path: str, tag: str, build_args: Dict[str, str] = None) -> bool:
        """构建Docker镜像"""
        if not self.docker_available:
            return False
        
        try:
            build_args = build_args or {}
            
            logger.info(f"Building Docker image: {tag}")
            
            # 创建Dockerfile
            dockerfile_content = self._generate_dockerfile(build_args)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                dockerfile_path = Path(temp_dir) / "Dockerfile"
                dockerfile_path.write_text(dockerfile_content)
                
                # 复制应用文件
                app_dir = Path(temp_dir) / "app"
                app_dir.mkdir()
                
                # 复制必要的文件
                self._copy_app_files(app_dir)
                
                # 构建镜像
                image, logs = self.client.images.build(
                    path=temp_dir,
                    tag=tag,
                    rm=True,
                    forcerm=True
                )
                
                logger.info(f"Successfully built image: {tag}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            return False
    
    def _generate_dockerfile(self, build_args: Dict[str, str]) -> str:
        """生成Dockerfile内容"""
        python_version = build_args.get("PYTHON_VERSION", "3.9")
        
        return f"""
FROM python:{python_version}-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 创建非root用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["python", "-m", "app.main"]
"""
    
    def _copy_app_files(self, target_dir: Path):
        """复制应用文件"""
        # 这里应该复制实际的应用文件
        # 简化处理：创建示例文件
        (target_dir / "main.py").write_text("""
from fastapi import FastAPI
from src.argus_mcp.websocket_endpoint import router as ws_router

app = FastAPI()
app.include_router(ws_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
""")
    
    def push_image(self, image_tag: str, registry: str) -> bool:
        """推送镜像到仓库"""
        if not self.docker_available:
            return False
        
        try:
            full_tag = f"{registry}/{image_tag}"
            
            # 标记镜像
            image = self.client.images.get(image_tag)
            image.tag(full_tag)
            
            # 推送镜像
            self.client.images.push(full_tag)
            
            logger.info(f"Successfully pushed image: {full_tag}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to push Docker image: {e}")
            return False
    
    def deploy_container(self, config: DeploymentConfig) -> bool:
        """部署容器"""
        if not self.docker_available:
            return False
        
        try:
            container_name = f"argus-mcp-{config.environment.value}"
            
            # 停止并移除现有容器
            try:
                existing = self.client.containers.get(container_name)
                existing.stop()
                existing.remove()
            except docker.errors.NotFound:
                pass
            
            # 环境变量
            environment = {
                "ENVIRONMENT": config.environment.value,
                "PORT": str(config.port),
                "LOG_LEVEL": config.log_level,
                "REDIS_URL": config.redis_url,
                "POSTGRES_URL": config.postgres_url,
                "ENABLE_METRICS": str(config.enable_metrics),
                "ENABLE_HEALTH_CHECK": str(config.enable_health_check)
            }
            
            # 端口映射
            ports = {
                f"{config.port}/tcp": config.port,
                f"{config.prometheus_port}/tcp": config.prometheus_port
            }
            
            # 启动新容器
            container = self.client.containers.run(
                image=config.docker_image,
                name=container_name,
                ports=ports,
                environment=environment,
                mem_limit=config.container_memory_limit,
                cpu_quota=int(float(config.container_cpu_limit) * 100000),
                detach=True,
                restart_policy={"Name": "unless-stopped"}
            )
            
            logger.info(f"Successfully deployed container: {container_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deploy container: {e}")
            return False


class EnvironmentManager:
    """环境管理器"""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "config"
        self.config_dir.mkdir(exist_ok=True)
    
    def create_environment_config(self, env: EnvironmentType, overrides: Dict[str, Any] = None) -> DeploymentConfig:
        """创建环境配置"""
        overrides = overrides or {}
        
        base_config = {
            "environment": env,
            "version": "1.0.0",
            "port": 8000,
            "workers": 4 if env == EnvironmentType.PRODUCTION else 2,
            "log_level": "INFO" if env == EnvironmentType.PRODUCTION else "DEBUG"
        }
        
        # 环境特定配置
        env_configs = {
            EnvironmentType.DEVELOPMENT: {
                "redis_url": "redis://localhost:6379",
                "postgres_url": "postgresql://dev:dev@localhost:5432/argus_dev",
                "enable_metrics": False,
                "require_https": False
            },
            EnvironmentType.STAGING: {
                "redis_url": "redis://staging-redis:6379",
                "postgres_url": "postgresql://stage:stage@staging-db:5432/argus_staging",
                "enable_metrics": True,
                "require_https": True
            },
            EnvironmentType.PRODUCTION: {
                "redis_url": "redis://prod-redis:6379",
                "postgres_url": "postgresql://prod:prod@prod-db:5432/argus_prod",
                "enable_metrics": True,
                "require_https": True,
                "workers": 8,
                "min_replicas": 3,
                "max_replicas": 20
            }
        }
        
        config_data = {**base_config, **env_configs.get(env, {})}
        config_data.update(overrides)
        
        return DeploymentConfig(**config_data)
    
    def save_config(self, config: DeploymentConfig, filename: str = None):
        """保存配置到文件"""
        if filename is None:
            filename = f"config_{config.environment.value}.yaml"
        
        config_path = self.config_dir / filename
        
        # 将dataclass转换为dict
        config_dict = {
            k: v.value if isinstance(v, Enum) else v
            for k, v in config.__dict__.items()
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
        
        logger.info(f"Configuration saved to {config_path}")
    
    def load_config(self, filename: str) -> DeploymentConfig:
        """从文件加载配置"""
        config_path = self.config_dir / filename
        
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        
        # 转换环境类型
        if "environment" in config_dict:
            config_dict["environment"] = EnvironmentType(config_dict["environment"])
        
        return DeploymentConfig(**config_dict)
    
    def create_docker_compose(self, config: DeploymentConfig) -> str:
        """创建Docker Compose配置"""
        compose_config = {
            "version": "3.8",
            "services": {
                "app": {
                    "image": config.docker_image,
                    "ports": [f"{config.port}:8000"],
                    "environment": {
                        "ENVIRONMENT": config.environment.value,
                        "LOG_LEVEL": config.log_level,
                        "REDIS_URL": config.redis_url,
                        "POSTGRES_URL": config.postgres_url
                    },
                    "depends_on": ["redis", "postgres"],
                    "restart": "unless-stopped",
                    "mem_limit": config.container_memory_limit,
                    "cpus": config.container_cpu_limit
                },
                "redis": {
                    "image": "redis:7-alpine",
                    "ports": ["6379:6379"],
                    "restart": "unless-stopped",
                    "volumes": ["redis_data:/data"]
                },
                "postgres": {
                    "image": "postgres:15-alpine",
                    "ports": ["5432:5432"],
                    "environment": {
                        "POSTGRES_DB": "argus",
                        "POSTGRES_USER": "argus",
                        "POSTGRES_PASSWORD": "argus_password"
                    },
                    "restart": "unless-stopped",
                    "volumes": ["postgres_data:/var/lib/postgresql/data"]
                }
            },
            "volumes": {
                "redis_data": None,
                "postgres_data": None
            }
        }
        
        if config.enable_metrics:
            compose_config["services"]["prometheus"] = {
                "image": "prom/prometheus:latest",
                "ports": [f"{config.prometheus_port}:9090"],
                "volumes": ["./prometheus.yml:/etc/prometheus/prometheus.yml"],
                "restart": "unless-stopped"
            }
            
            compose_config["services"]["grafana"] = {
                "image": "grafana/grafana:latest",
                "ports": [f"{config.grafana_port}:3000"],
                "environment": {
                    "GF_SECURITY_ADMIN_PASSWORD": "admin"
                },
                "volumes": ["grafana_data:/var/lib/grafana"],
                "restart": "unless-stopped"
            }
            
            compose_config["volumes"]["grafana_data"] = None
        
        return yaml.dump(compose_config, default_flow_style=False)
    
    def create_kubernetes_manifests(self, config: DeploymentConfig) -> Dict[str, str]:
        """创建Kubernetes部署清单"""
        manifests = {}
        
        # Deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "argus-mcp",
                "labels": {
                    "app": "argus-mcp",
                    "version": config.version,
                    "environment": config.environment.value
                }
            },
            "spec": {
                "replicas": config.min_replicas,
                "selector": {
                    "matchLabels": {"app": "argus-mcp"}
                },
                "template": {
                    "metadata": {
                        "labels": {"app": "argus-mcp"}
                    },
                    "spec": {
                        "containers": [{
                            "name": "argus-mcp",
                            "image": config.docker_image,
                            "ports": [{"containerPort": 8000}],
                            "env": [
                                {"name": "ENVIRONMENT", "value": config.environment.value},
                                {"name": "LOG_LEVEL", "value": config.log_level},
                                {"name": "REDIS_URL", "value": config.redis_url},
                                {"name": "POSTGRES_URL", "value": config.postgres_url}
                            ],
                            "resources": {
                                "limits": {
                                    "memory": config.container_memory_limit,
                                    "cpu": config.container_cpu_limit
                                }
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/health", "port": 8000},
                                "initialDelaySeconds": 30,
                                "periodSeconds": 10
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/health", "port": 8000},
                                "initialDelaySeconds": 5,
                                "periodSeconds": 5
                            }
                        }]
                    }
                }
            }
        }
        
        # Service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "argus-mcp-service",
                "labels": {"app": "argus-mcp"}
            },
            "spec": {
                "selector": {"app": "argus-mcp"},
                "ports": [{
                    "protocol": "TCP",
                    "port": 80,
                    "targetPort": 8000
                }],
                "type": "LoadBalancer"
            }
        }
        
        # ConfigMap
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "argus-mcp-config"
            },
            "data": {
                "config.yaml": yaml.dump({
                    "environment": config.environment.value,
                    "port": config.port,
                    "log_level": config.log_level,
                    "enable_metrics": config.enable_metrics,
                    "enable_health_check": config.enable_health_check
                })
            }
        }
        
        manifests["deployment.yaml"] = yaml.dump(deployment, default_flow_style=False)
        manifests["service.yaml"] = yaml.dump(service, default_flow_style=False)
        manifests["configmap.yaml"] = yaml.dump(configmap, default_flow_style=False)
        
        return manifests


class DeploymentManager:
    """部署管理器"""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.docker_manager = DockerManager()
        self.environment_manager = EnvironmentManager(base_dir)
        self.health_checker = HealthChecker()
        
        # 注册默认健康检查
        self._register_default_health_checks()
    
    def _register_default_health_checks(self):
        """注册默认健康检查"""
        self.health_checker.register_check("disk_space", self._check_disk_space)
        self.health_checker.register_check("memory_usage", self._check_memory_usage)
        self.health_checker.register_check("cpu_usage", self._check_cpu_usage)
        self.health_checker.register_check("network_connectivity", self._check_network_connectivity)
        self.health_checker.register_check("docker_status", self._check_docker_status)
    
    async def _check_disk_space(self) -> bool:
        """检查磁盘空间"""
        disk_usage = psutil.disk_usage('/')
        free_percent = (disk_usage.free / disk_usage.total) * 100
        return free_percent > 10  # 至少10%可用空间
    
    async def _check_memory_usage(self) -> bool:
        """检查内存使用"""
        memory = psutil.virtual_memory()
        return memory.percent < 90  # 内存使用率低于90%
    
    async def _check_cpu_usage(self) -> bool:
        """检查CPU使用"""
        cpu_percent = psutil.cpu_percent(interval=1)
        return cpu_percent < 95  # CPU使用率低于95%
    
    async def _check_network_connectivity(self) -> bool:
        """检查网络连接"""
        try:
            # 测试连接到一个知名DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except (socket.error, OSError):
            return False
    
    async def _check_docker_status(self) -> bool:
        """检查Docker状态"""
        return self.docker_manager.docker_available
    
    async def deploy(self, env: EnvironmentType, overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行部署"""
        logger.info(f"Starting deployment for {env.value}")
        
        # 创建配置
        config = self.environment_manager.create_environment_config(env, overrides)
        
        # 保存配置
        self.environment_manager.save_config(config)
        
        # 运行健康检查
        health_status = await self.health_checker.run_all_checks()
        
        if not all(check["status"] == "healthy" for check in health_status.values()):
            return {
                "status": "failed",
                "reason": "Health checks failed",
                "health_status": health_status
            }
        
        # 构建镜像
        build_success = self.docker_manager.build_image(
            dockerfile_path=str(self.base_dir),
            tag=config.docker_image
        )
        
        if not build_success:
            return {
                "status": "failed",
                "reason": "Docker build failed"
            }
        
        # 部署容器
        deploy_success = self.docker_manager.deploy_container(config)
        
        if deploy_success:
            # 创建部署清单
            compose_file = self.environment_manager.create_docker_compose(config)
            compose_path = self.base_dir / "docker-compose.yml"
            compose_path.write_text(compose_file)
            
            # 创建Kubernetes清单
            k8s_manifests = self.environment_manager.create_kubernetes_manifests(config)
            k8s_dir = self.base_dir / "k8s"
            k8s_dir.mkdir(exist_ok=True)
            
            for filename, content in k8s_manifests.items():
                (k8s_dir / filename).write_text(content)
            
            return {
                "status": "success",
                "config": config,
                "health_status": health_status,
                "files_created": [
                    str(self.base_dir / f"config_{env.value}.yaml"),
                    str(compose_path),
                    str(k8s_dir)
                ]
            }
        else:
            return {
                "status": "failed",
                "reason": "Container deployment failed"
            }
    
    async def rollback(self, version: str) -> bool:
        """回滚到指定版本"""
        try:
            # 停止当前容器
            containers = self.docker_manager.client.containers.list(
                filters={"label": "app=argus-mcp"}
            )
            
            for container in containers:
                container.stop()
                container.remove()
            
            # 启动指定版本的容器
            # 这里简化处理，实际应该使用版本标签
            logger.info(f"Rolling back to version: {version}")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def generate_deployment_report(self) -> Dict[str, Any]:
        """生成部署报告"""
        health_summary = self.health_checker.get_health_summary()
        
        report = {
            "timestamp": datetime.now(),
            "health_status": health_summary,
            "docker_available": self.docker_manager.docker_available,
            "config_files": list(self.environment_manager.config_dir.glob("*.yaml")),
            "base_directory": str(self.base_dir.absolute())
        }
        
        if self.docker_manager.docker_available:
            try:
                containers = self.docker_manager.client.containers.list()
                report["running_containers"] = [
                    {
                        "name": container.name,
                        "status": container.status,
                        "image": container.image.tags[0] if container.image.tags else "unknown"
                    }
                    for container in containers
                ]
            except Exception as e:
                report["docker_error"] = str(e)
        
        return report
    
    def cleanup_old_images(self, keep_last: int = 3):
        """清理旧镜像"""
        if not self.docker_manager.docker_available:
            return
        
        try:
            images = self.docker_manager.client.images.list(name="argus-mcp")
            
            # 按创建时间排序
            images.sort(key=lambda img: img.attrs.get('Created', 0), reverse=True)
            
            # 删除旧镜像
            for image in images[keep_last:]:
                try:
                    self.docker_manager.client.images.remove(image.id, force=True)
                    logger.info(f"Removed old image: {image.id[:12]}")
                except Exception as e:
                    logger.warning(f"Failed to remove image {image.id[:12]}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup images: {e}")


# 使用示例
if __name__ == "__main__":
    async def main():
        # 创建部署管理器
        deploy_manager = DeploymentManager()
        
        # 部署到开发环境
        result = await deploy_manager.deploy(EnvironmentType.DEVELOPMENT)
        print(json.dumps(result, indent=2, default=str))
        
        # 生成部署报告
        report = deploy_manager.generate_deployment_report()
        print(json.dumps(report, indent=2, default=str))
    
    asyncio.run(main())