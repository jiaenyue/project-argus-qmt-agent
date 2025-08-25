"""
WebSocket 实时数据系统 - 配置文件
定义所有配置参数和设置
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os
from pathlib import Path


@dataclass
class ServerConfig:
    """服务器配置"""
    host: str = "localhost"
    port: int = 8765
    max_connections: int = 1000
    max_subscriptions_per_client: int = 100
    
    # WebSocket 设置
    ping_interval: float = 20.0
    ping_timeout: float = 20.0
    close_timeout: float = 10.0
    max_size: int = 2**20  # 1MB
    max_queue: int = 32


@dataclass
class DataSourceConfig:
    """数据源配置"""
    source_type: str = "mock"  # "mock", "qmt", "tdx", "yahoo"
    update_interval: float = 1.0
    batch_size: int = 100
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    # QMT 配置
    qmt_host: str = "localhost"
    qmt_port: int = 8000
    qmt_account: str = ""
    qmt_password: str = ""
    
    # TDX 配置
    tdx_server: str = "119.147.212.81"
    tdx_port: int = 7709
    
    # Yahoo Finance 配置
    yahoo_timeout: float = 10.0
    yahoo_retry_delay: float = 5.0


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class SecurityConfig:
    """安全配置"""
    enable_auth: bool = False
    auth_token: str = ""
    allowed_origins: list = field(default_factory=lambda: ["*"])
    rate_limit: int = 100
    rate_limit_window: float = 1.0
    
    # SSL 配置
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None


@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    max_size: int = 1000
    ttl: float = 300.0
    cleanup_interval: float = 60.0


@dataclass
class MonitoringConfig:
    """监控配置"""
    enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    health_check_path: str = "/health"
    
    # 告警配置
    alert_webhook: Optional[str] = None
    alert_threshold: Dict[str, Any] = field(default_factory=lambda: {
        "connection_count": 800,
        "error_rate": 0.05,
        "latency_p99": 1000
    })


@dataclass
class Config:
    """主配置类"""
    server: ServerConfig = field(default_factory=ServerConfig)
    datasource: DataSourceConfig = field(default_factory=DataSourceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Data service URL for API integration
    data_service_url: str = "http://localhost:8000"
    
    @classmethod
    def load_from_env(cls) -> "Config":
        """从环境变量加载配置"""
        config = cls()
        
        # 服务器配置
        config.server.host = os.getenv("WEBSOCKET_HOST", config.server.host)
        config.server.port = int(os.getenv("WEBSOCKET_PORT", str(config.server.port)))
        config.server.max_connections = int(os.getenv("MAX_CONNECTIONS", str(config.server.max_connections)))
        config.server.max_subscriptions_per_client = int(os.getenv("MAX_SUBSCRIPTIONS_PER_CLIENT", 
                                                                   str(config.server.max_subscriptions_per_client)))
        
        # 数据源配置
        config.datasource.source_type = os.getenv("DATASOURCE_TYPE", config.datasource.source_type)
        config.datasource.update_interval = float(os.getenv("UPDATE_INTERVAL", str(config.datasource.update_interval)))
        
        # QMT 配置
        config.datasource.qmt_host = os.getenv("QMT_HOST", config.datasource.qmt_host)
        config.datasource.qmt_port = int(os.getenv("QMT_PORT", str(config.datasource.qmt_port)))
        config.datasource.qmt_account = os.getenv("QMT_ACCOUNT", config.datasource.qmt_account)
        config.datasource.qmt_password = os.getenv("QMT_PASSWORD", config.datasource.qmt_password)
        
        # 日志配置
        config.logging.level = os.getenv("LOG_LEVEL", config.logging.level)
        config.logging.file_path = os.getenv("LOG_FILE_PATH", config.logging.file_path)
        
        # 安全配置
        config.security.enable_auth = os.getenv("ENABLE_AUTH", "false").lower() == "true"
        config.security.auth_token = os.getenv("AUTH_TOKEN", config.security.auth_token)
        
        # SSL 配置
        config.security.ssl_enabled = os.getenv("SSL_ENABLED", "false").lower() == "true"
        config.security.ssl_cert_path = os.getenv("SSL_CERT_PATH", config.security.ssl_cert_path)
        config.security.ssl_key_path = os.getenv("SSL_KEY_PATH", config.security.ssl_key_path)
        
        # Data service URL
        config.data_service_url = os.getenv("DATA_SERVICE_URL", config.data_service_url)
        
        return config


# 创建默认配置
def create_default_config():
    """创建默认配置"""
    config = Config()
    config.server.host = "0.0.0.0"
    config.server.port = 8765
    config.server.max_connections = 1000
    config.datasource.source_type = "mock"
    return config


# 全局配置实例
config = Config.load_from_env()