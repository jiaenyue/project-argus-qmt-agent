"""
WebSocket 服务部署配置管理器
管理环境变量、配置文件和部署参数
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class DeploymentEnvironment(str, Enum):
    """部署环境类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ServiceDiscoveryBackend(str, Enum):
    """服务发现后端"""
    CONSUL = "consul"
    ETCD = "etcd"
    KUBERNETES = "kubernetes"
    NONE = "none"


@dataclass
class WebSocketConfig:
    """WebSocket服务配置"""
    host: str = "0.0.0.0"
    port: int = 8765
    max_connections: int = 1000
    max_subscriptions_per_client: int = 100
    heartbeat_interval: float = 30.0
    max_message_size: int = 1048576  # 1MB
    ping_interval: float = 20.0
    ping_timeout: float = 20.0
    close_timeout: float = 10.0
    max_queue: int = 32


@dataclass
class ServiceDiscoveryConfig:
    """服务发现配置"""
    backend: ServiceDiscoveryBackend = ServiceDiscoveryBackend.NONE
    consul_host: str = "localhost"
    consul_port: int = 8500
    etcd_endpoints: List[str] = field(default_factory=lambda: ["localhost:2379"])
    service_name: str = "websocket-server"
    health_check_interval: float = 10.0
    heartbeat_interval: float = 15.0


@dataclass
class LoadBalancingConfig:
    """负载均衡配置"""
    strategy: str = "least_connections"  # round_robin, least_connections, ip_hash
    rate_limit_rpm: int = 60
    burst_size: int = 10
    sticky_sessions: bool = False


@dataclass
class ScalingConfig:
    """扩展配置"""
    min_instances: int = 1
    max_instances: int = 5
    target_cpu_utilization: float = 70.0
    target_memory_utilization: float = 80.0
    target_connections_per_instance: int = 800
    scale_up_cooldown: float = 300.0
    scale_down_cooldown: float = 600.0
    evaluation_interval: float = 60.0


@dataclass
class SecurityConfig:
    """安全配置"""
    enable_auth: bool = False
    auth_token: Optional[str] = None
    allowed_origins: List[str] = field(default_factory=lambda: ["*"])
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    rate_limit_enabled: bool = True


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    console_output: bool = True


@dataclass
class MonitoringConfig:
    """监控配置"""
    enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    health_check_path: str = "/health"
    readiness_check_path: str = "/ready"
    prometheus_enabled: bool = True
    grafana_enabled: bool = True


@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    max_size: int = 1000
    ttl: float = 300.0
    cleanup_interval: float = 60.0


@dataclass
class DatabaseConfig:
    """数据库配置"""
    enabled: bool = False
    host: str = "localhost"
    port: int = 5432
    database: str = "websocket_db"
    username: str = "websocket_user"
    password: Optional[str] = None
    pool_size: int = 10
    max_overflow: int = 20


@dataclass
class DeploymentConfig:
    """完整部署配置"""
    environment: DeploymentEnvironment = DeploymentEnvironment.DEVELOPMENT
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    service_discovery: ServiceDiscoveryConfig = field(default_factory=ServiceDiscoveryConfig)
    load_balancing: LoadBalancingConfig = field(default_factory=LoadBalancingConfig)
    scaling: ScalingConfig = field(default_factory=ScalingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)


class DeploymentConfigManager:
    """部署配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/deployment.yaml"
        self.config: Optional[DeploymentConfig] = None
        self._env_overrides: Dict[str, Any] = {}
    
    def load_config(self, config_path: Optional[str] = None) -> DeploymentConfig:
        """加载配置"""
        if config_path:
            self.config_path = config_path
        
        # 从文件加载基础配置
        base_config = self._load_from_file()
        
        # 应用环境变量覆盖
        self._apply_env_overrides(base_config)
        
        # 验证配置
        self._validate_config(base_config)
        
        self.config = base_config
        return self.config
    
    def _load_from_file(self) -> DeploymentConfig:
        """从文件加载配置"""
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            return DeploymentConfig()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif config_file.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    raise ValueError(f"不支持的配置文件格式: {config_file.suffix}")
            
            return self._dict_to_config(data)
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return DeploymentConfig()
    
    def _dict_to_config(self, data: Dict[str, Any]) -> DeploymentConfig:
        """将字典转换为配置对象"""
        config = DeploymentConfig()
        
        # 环境
        if 'environment' in data:
            config.environment = DeploymentEnvironment(data['environment'])
        
        # WebSocket配置
        if 'websocket' in data:
            ws_data = data['websocket']
            config.websocket = WebSocketConfig(**ws_data)
        
        # 服务发现配置
        if 'service_discovery' in data:
            sd_data = data['service_discovery']
            if 'backend' in sd_data:
                sd_data['backend'] = ServiceDiscoveryBackend(sd_data['backend'])
            config.service_discovery = ServiceDiscoveryConfig(**sd_data)
        
        # 负载均衡配置
        if 'load_balancing' in data:
            config.load_balancing = LoadBalancingConfig(**data['load_balancing'])
        
        # 扩展配置
        if 'scaling' in data:
            config.scaling = ScalingConfig(**data['scaling'])
        
        # 安全配置
        if 'security' in data:
            config.security = SecurityConfig(**data['security'])
        
        # 日志配置
        if 'logging' in data:
            config.logging = LoggingConfig(**data['logging'])
        
        # 监控配置
        if 'monitoring' in data:
            config.monitoring = MonitoringConfig(**data['monitoring'])
        
        # 缓存配置
        if 'cache' in data:
            config.cache = CacheConfig(**data['cache'])
        
        # 数据库配置
        if 'database' in data:
            config.database = DatabaseConfig(**data['database'])
        
        return config
    
    def _apply_env_overrides(self, config: DeploymentConfig):
        """应用环境变量覆盖"""
        env_mappings = {
            # WebSocket配置
            'WEBSOCKET_HOST': ('websocket', 'host'),
            'WEBSOCKET_PORT': ('websocket', 'port', int),
            'MAX_CONNECTIONS': ('websocket', 'max_connections', int),
            'MAX_SUBSCRIPTIONS_PER_CLIENT': ('websocket', 'max_subscriptions_per_client', int),
            'HEARTBEAT_INTERVAL': ('websocket', 'heartbeat_interval', float),
            
            # 服务发现配置
            'SERVICE_DISCOVERY_BACKEND': ('service_discovery', 'backend', ServiceDiscoveryBackend),
            'CONSUL_HOST': ('service_discovery', 'consul_host'),
            'CONSUL_PORT': ('service_discovery', 'consul_port', int),
            
            # 负载均衡配置
            'LOAD_BALANCING_STRATEGY': ('load_balancing', 'strategy'),
            'RATE_LIMIT_RPM': ('load_balancing', 'rate_limit_rpm', int),
            
            # 扩展配置
            'MIN_INSTANCES': ('scaling', 'min_instances', int),
            'MAX_INSTANCES': ('scaling', 'max_instances', int),
            'TARGET_CPU_UTILIZATION': ('scaling', 'target_cpu_utilization', float),
            'TARGET_MEMORY_UTILIZATION': ('scaling', 'target_memory_utilization', float),
            
            # 安全配置
            'ENABLE_AUTH': ('security', 'enable_auth', bool),
            'AUTH_TOKEN': ('security', 'auth_token'),
            'SSL_ENABLED': ('security', 'ssl_enabled', bool),
            'SSL_CERT_PATH': ('security', 'ssl_cert_path'),
            'SSL_KEY_PATH': ('security', 'ssl_key_path'),
            
            # 日志配置
            'LOG_LEVEL': ('logging', 'level'),
            'LOG_FILE_PATH': ('logging', 'file_path'),
            
            # 监控配置
            'MONITORING_ENABLED': ('monitoring', 'enabled', bool),
            'METRICS_PORT': ('monitoring', 'metrics_port', int),
            
            # 缓存配置
            'REDIS_HOST': ('cache', 'redis_host'),
            'REDIS_PORT': ('cache', 'redis_port', int),
            'REDIS_PASSWORD': ('cache', 'redis_password'),
            
            # 数据库配置
            'DATABASE_HOST': ('database', 'host'),
            'DATABASE_PORT': ('database', 'port', int),
            'DATABASE_NAME': ('database', 'database'),
            'DATABASE_USER': ('database', 'username'),
            'DATABASE_PASSWORD': ('database', 'password'),
        }
        
        for env_var, mapping in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                section = mapping[0]
                field_name = mapping[1]
                converter = mapping[2] if len(mapping) > 2 else str
                
                # 类型转换
                try:
                    if converter == bool:
                        converted_value = value.lower() in ('true', '1', 'yes', 'on')
                    elif converter == ServiceDiscoveryBackend:
                        converted_value = ServiceDiscoveryBackend(value)
                    else:
                        converted_value = converter(value)
                    
                    # 设置配置值
                    section_obj = getattr(config, section)
                    setattr(section_obj, field_name, converted_value)
                    
                    logger.info(f"环境变量覆盖: {env_var} -> {section}.{field_name} = {converted_value}")
                    
                except (ValueError, TypeError) as e:
                    logger.error(f"环境变量转换失败 {env_var}: {e}")
    
    def _validate_config(self, config: DeploymentConfig):
        """验证配置"""
        errors = []
        
        # WebSocket配置验证
        if config.websocket.port < 1 or config.websocket.port > 65535:
            errors.append("WebSocket端口必须在1-65535范围内")
        
        if config.websocket.max_connections < 1:
            errors.append("最大连接数必须大于0")
        
        # 扩展配置验证
        if config.scaling.min_instances > config.scaling.max_instances:
            errors.append("最小实例数不能大于最大实例数")
        
        if config.scaling.target_cpu_utilization < 1 or config.scaling.target_cpu_utilization > 100:
            errors.append("目标CPU利用率必须在1-100范围内")
        
        # SSL配置验证
        if config.security.ssl_enabled:
            if not config.security.ssl_cert_path or not config.security.ssl_key_path:
                errors.append("启用SSL时必须提供证书和密钥路径")
        
        if errors:
            raise ValueError(f"配置验证失败: {'; '.join(errors)}")
    
    def save_config(self, config_path: Optional[str] = None) -> bool:
        """保存配置到文件"""
        if not self.config:
            logger.error("没有配置可保存")
            return False
        
        save_path = config_path or self.config_path
        
        try:
            config_dict = asdict(self.config)
            
            # 转换枚举值
            config_dict['environment'] = self.config.environment.value
            config_dict['service_discovery']['backend'] = self.config.service_discovery.backend.value
            
            with open(save_path, 'w', encoding='utf-8') as f:
                if save_path.endswith('.json'):
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"配置已保存到: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def get_environment_variables(self) -> Dict[str, str]:
        """获取环境变量字典"""
        if not self.config:
            return {}
        
        env_vars = {}
        
        # WebSocket配置
        env_vars.update({
            'WEBSOCKET_HOST': self.config.websocket.host,
            'WEBSOCKET_PORT': str(self.config.websocket.port),
            'MAX_CONNECTIONS': str(self.config.websocket.max_connections),
            'MAX_SUBSCRIPTIONS_PER_CLIENT': str(self.config.websocket.max_subscriptions_per_client),
            'HEARTBEAT_INTERVAL': str(self.config.websocket.heartbeat_interval),
        })
        
        # 服务发现配置
        env_vars.update({
            'SERVICE_DISCOVERY_BACKEND': self.config.service_discovery.backend.value,
            'CONSUL_HOST': self.config.service_discovery.consul_host,
            'CONSUL_PORT': str(self.config.service_discovery.consul_port),
        })
        
        # 负载均衡配置
        env_vars.update({
            'LOAD_BALANCING_STRATEGY': self.config.load_balancing.strategy,
            'RATE_LIMIT_RPM': str(self.config.load_balancing.rate_limit_rpm),
        })
        
        # 扩展配置
        env_vars.update({
            'MIN_INSTANCES': str(self.config.scaling.min_instances),
            'MAX_INSTANCES': str(self.config.scaling.max_instances),
            'TARGET_CPU_UTILIZATION': str(self.config.scaling.target_cpu_utilization),
            'TARGET_MEMORY_UTILIZATION': str(self.config.scaling.target_memory_utilization),
        })
        
        # 安全配置
        env_vars.update({
            'ENABLE_AUTH': str(self.config.security.enable_auth).lower(),
            'SSL_ENABLED': str(self.config.security.ssl_enabled).lower(),
        })
        
        if self.config.security.auth_token:
            env_vars['AUTH_TOKEN'] = self.config.security.auth_token
        
        if self.config.security.ssl_cert_path:
            env_vars['SSL_CERT_PATH'] = self.config.security.ssl_cert_path
        
        if self.config.security.ssl_key_path:
            env_vars['SSL_KEY_PATH'] = self.config.security.ssl_key_path
        
        # 日志配置
        env_vars.update({
            'LOG_LEVEL': self.config.logging.level,
        })
        
        if self.config.logging.file_path:
            env_vars['LOG_FILE_PATH'] = self.config.logging.file_path
        
        # 监控配置
        env_vars.update({
            'MONITORING_ENABLED': str(self.config.monitoring.enabled).lower(),
            'METRICS_PORT': str(self.config.monitoring.metrics_port),
        })
        
        # 缓存配置
        env_vars.update({
            'REDIS_HOST': self.config.cache.redis_host,
            'REDIS_PORT': str(self.config.cache.redis_port),
        })
        
        if self.config.cache.redis_password:
            env_vars['REDIS_PASSWORD'] = self.config.cache.redis_password
        
        # 数据库配置
        if self.config.database.enabled:
            env_vars.update({
                'DATABASE_HOST': self.config.database.host,
                'DATABASE_PORT': str(self.config.database.port),
                'DATABASE_NAME': self.config.database.database,
                'DATABASE_USER': self.config.database.username,
            })
            
            if self.config.database.password:
                env_vars['DATABASE_PASSWORD'] = self.config.database.password
        
        return env_vars
    
    def generate_docker_env_file(self, output_path: str = ".env") -> bool:
        """生成Docker环境变量文件"""
        try:
            env_vars = self.get_environment_variables()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("# WebSocket服务环境变量配置\n")
                f.write(f"# 生成时间: {os.popen('date').read().strip()}\n\n")
                
                for key, value in sorted(env_vars.items()):
                    f.write(f"{key}={value}\n")
            
            logger.info(f"Docker环境变量文件已生成: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"生成Docker环境变量文件失败: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        if not self.config:
            return {"status": "no_config"}
        
        return {
            "environment": self.config.environment.value,
            "websocket": {
                "host": self.config.websocket.host,
                "port": self.config.websocket.port,
                "max_connections": self.config.websocket.max_connections,
            },
            "service_discovery": {
                "backend": self.config.service_discovery.backend.value,
                "enabled": self.config.service_discovery.backend != ServiceDiscoveryBackend.NONE,
            },
            "scaling": {
                "min_instances": self.config.scaling.min_instances,
                "max_instances": self.config.scaling.max_instances,
                "auto_scaling": self.config.scaling.max_instances > self.config.scaling.min_instances,
            },
            "security": {
                "auth_enabled": self.config.security.enable_auth,
                "ssl_enabled": self.config.security.ssl_enabled,
            },
            "monitoring": {
                "enabled": self.config.monitoring.enabled,
                "metrics_port": self.config.monitoring.metrics_port,
            },
            "cache": {
                "enabled": self.config.cache.enabled,
                "redis_host": self.config.cache.redis_host,
            }
        }


# 全局配置管理器实例
deployment_config_manager = DeploymentConfigManager()


def get_deployment_config() -> DeploymentConfig:
    """获取部署配置"""
    if deployment_config_manager.config is None:
        deployment_config_manager.load_config()
    return deployment_config_manager.config


def load_deployment_config(config_path: Optional[str] = None) -> DeploymentConfig:
    """加载部署配置"""
    return deployment_config_manager.load_config(config_path)