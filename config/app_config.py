"""
应用配置文件
统一管理所有服务的端口、地址和其他配置信息
"""

import os
from typing import Dict, Any

class AppConfig:
    """应用配置类"""
    
    # 服务端口配置
    DATA_AGENT_SERVICE_PORT = int(os.getenv("DATA_AGENT_SERVICE_PORT", "8001"))
    DATA_AGENT_SERVICE_HOST = os.getenv("DATA_AGENT_SERVICE_HOST", "127.0.0.1")
    
    # MCP服务端口配置
    MCP_SERVICE_PORT = int(os.getenv("MCP_SERVICE_PORT", "8001"))
    MCP_SERVICE_HOST = os.getenv("MCP_SERVICE_HOST", "127.0.0.1")
    
    # API基础URL配置
    @classmethod
    def get_data_agent_base_url(cls) -> str:
        """获取数据代理服务的基础URL"""
        return f"http://{cls.DATA_AGENT_SERVICE_HOST}:{cls.DATA_AGENT_SERVICE_PORT}"
    
    @classmethod
    def get_mcp_base_url(cls) -> str:
        """获取MCP服务的基础URL"""
        return f"http://{cls.MCP_SERVICE_HOST}:{cls.MCP_SERVICE_PORT}"
    
    # 数据库配置
    DATABASE_CONFIG = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "argus_qmt"),
        "username": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
    
    # QMT配置
    QMT_CONFIG = {
        "mini_qmt_path": os.getenv("MINI_QMT_PATH", "G:\\Stock\\GJ_QMT\\bin.x64"),
        "data_dir": os.getenv("QMT_DATA_DIR", "G:\\Stock\\GJ_QMT\\bin.x64\\..\\userdata_mini\\datadir"),
        "connection_timeout": int(os.getenv("QMT_CONNECTION_TIMEOUT", "30")),
        "retry_attempts": int(os.getenv("QMT_RETRY_ATTEMPTS", "3")),
    }
    
    # 缓存配置
    CACHE_CONFIG = {
        "redis_host": os.getenv("REDIS_HOST", "localhost"),
        "redis_port": int(os.getenv("REDIS_PORT", "6379")),
        "redis_db": int(os.getenv("REDIS_DB", "0")),
        "default_ttl": int(os.getenv("CACHE_DEFAULT_TTL", "3600")),
        "max_memory": os.getenv("CACHE_MAX_MEMORY", "256mb"),
    }
    
    # 日志配置
    LOGGING_CONFIG = {
        "level": os.getenv("LOG_LEVEL", "INFO"),
        "format": os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        "file_path": os.getenv("LOG_FILE_PATH", "logs/app.log"),
        "max_file_size": int(os.getenv("LOG_MAX_FILE_SIZE", "10485760")),  # 10MB
        "backup_count": int(os.getenv("LOG_BACKUP_COUNT", "5")),
    }
    
    # 安全配置
    SECURITY_CONFIG = {
        "secret_key": os.getenv("SECRET_KEY", "your-secret-key-here"),
        "algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
        "access_token_expire_minutes": int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        "rate_limit_per_minute": int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    }
    
    # 性能配置
    PERFORMANCE_CONFIG = {
        "max_workers": int(os.getenv("MAX_WORKERS", "4")),
        "connection_pool_size": int(os.getenv("CONNECTION_POOL_SIZE", "10")),
        "query_timeout": int(os.getenv("QUERY_TIMEOUT", "30")),
        "batch_size": int(os.getenv("BATCH_SIZE", "1000")),
    }
    
    # 开发/测试配置
    DEVELOPMENT_CONFIG = {
        "debug": os.getenv("DEBUG", "False").lower() == "true",
        "reload": os.getenv("RELOAD", "False").lower() == "true",
        "test_mode": os.getenv("TEST_MODE", "False").lower() == "true",
    }
    
    @classmethod
    def get_all_config(cls) -> Dict[str, Any]:
        """获取所有配置信息"""
        return {
            "service": {
                "data_agent_port": cls.DATA_AGENT_SERVICE_PORT,
                "data_agent_host": cls.DATA_AGENT_SERVICE_HOST,
                "mcp_port": cls.MCP_SERVICE_PORT,
                "mcp_host": cls.MCP_SERVICE_HOST,
                "data_agent_base_url": cls.get_data_agent_base_url(),
                "mcp_base_url": cls.get_mcp_base_url(),
            },
            "database": cls.DATABASE_CONFIG,
            "qmt": cls.QMT_CONFIG,
            "cache": cls.CACHE_CONFIG,
            "logging": cls.LOGGING_CONFIG,
            "security": cls.SECURITY_CONFIG,
            "performance": cls.PERFORMANCE_CONFIG,
            "development": cls.DEVELOPMENT_CONFIG,
        }
    
    @classmethod
    def print_config_summary(cls):
        """打印配置摘要"""
        print("=" * 50)
        print("应用配置摘要")
        print("=" * 50)
        print(f"数据代理服务: {cls.get_data_agent_base_url()}")
        print(f"MCP服务: {cls.get_mcp_base_url()}")
        print(f"调试模式: {cls.DEVELOPMENT_CONFIG['debug']}")
        print(f"测试模式: {cls.DEVELOPMENT_CONFIG['test_mode']}")
        print("=" * 50)


# 创建全局配置实例
app_config = AppConfig()

# 导出常用配置
DATA_AGENT_BASE_URL = app_config.get_data_agent_base_url()
MCP_BASE_URL = app_config.get_mcp_base_url()
DATA_AGENT_PORT = app_config.DATA_AGENT_SERVICE_PORT
DATA_AGENT_HOST = app_config.DATA_AGENT_SERVICE_HOST

if __name__ == "__main__":
    app_config.print_config_summary()