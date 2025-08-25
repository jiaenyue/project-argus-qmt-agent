import os
import json
from typing import Dict, List, Optional, Set
from pathlib import Path
import logging
from datetime import datetime, timedelta

# 配置日志
logger = logging.getLogger(__name__)

class SecurityConfig:
    """安全配置管理类"""
    
    def __init__(self, config_file: str = "security_config.json"):
        # 优先从环境变量读取配置文件路径
        env_config_path = os.environ.get('SECURITY_CONFIG_PATH')
        if env_config_path:
            self.config_file = Path(env_config_path)
        else:
            # 如果是相对路径，则相对于当前文件所在目录
            if not os.path.isabs(config_file):
                current_dir = Path(__file__).parent
                self.config_file = current_dir / config_file
            else:
                self.config_file = Path(config_file)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """加载安全配置"""
        default_config = {
            "api_keys": {
                # 示例API Key配置
                "demo_key_123": {
                    "name": "Demo API Key",
                    "permissions": ["read"],
                    "rate_limit": {
                        "requests_per_minute": 60,
                        "requests_per_hour": 1000
                    },
                    "ip_whitelist": [],
                    "enabled": True,
                    "created_at": "2025-01-16T00:00:00Z",
                    "expires_at": None
                }
            },
            "rate_limiting": {
                "default_limits": {
                    "requests_per_minute": 30,
                    "requests_per_hour": 500
                },
                "ip_limits": {
                    "requests_per_minute": 20,
                    "requests_per_hour": 300
                }
            },
            "ip_whitelist": {
                "enabled": False,
                "allowed_ips": [
                    "127.0.0.1",
                    "::1",
                    "localhost"
                ]
            },
            "authentication": {
                "require_api_key": True,
                "allow_bearer_token": True,
                "allow_query_param": True,
                "header_name": "X-API-Key",
                "query_param_name": "api_key"
            },
            "logging": {
                "log_all_requests": True,
                "log_failed_auth": True,
                "log_rate_limit_exceeded": True,
                "sensitive_headers": ["authorization", "x-api-key"]
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和加载的配置
                    default_config.update(loaded_config)
                    return default_config
            except Exception as e:
                logger.error(f"Failed to load security config: {e}")
                return default_config
        else:
            # 创建默认配置文件
            self._save_config(default_config)
            return default_config
    
    def _save_config(self, config: Dict) -> None:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save security config: {e}")
    
    def get_api_key_info(self, api_key: str) -> Optional[Dict]:
        """获取API Key信息"""
        return self.config.get("api_keys", {}).get(api_key)
    
    def is_api_key_valid(self, api_key: str) -> bool:
        """验证API Key是否有效"""
        key_info = self.get_api_key_info(api_key)
        if not key_info:
            return False
        
        # 检查是否启用
        if not key_info.get("enabled", False):
            return False
        
        # 检查是否过期
        expires_at = key_info.get("expires_at")
        if expires_at:
            try:
                expire_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if datetime.now() > expire_time:
                    return False
            except Exception as e:
                logger.error(f"Failed to parse expiry date for API key: {e}")
                return False
        
        return True
    
    def get_rate_limits(self, api_key: str = None) -> Dict:
        """获取速率限制配置"""
        if api_key:
            key_info = self.get_api_key_info(api_key)
            if key_info and "rate_limit" in key_info:
                return key_info["rate_limit"]
        
        return self.config.get("rate_limiting", {}).get("default_limits", {})
    
    def get_ip_rate_limits(self) -> Dict:
        """获取IP速率限制配置"""
        return self.config.get("rate_limiting", {}).get("ip_limits", {})
    
    def is_ip_whitelisted(self, ip: str) -> bool:
        """检查IP是否在白名单中"""
        whitelist_config = self.config.get("ip_whitelist", {})
        if not whitelist_config.get("enabled", False):
            return True  # 如果未启用白名单，则允许所有IP
        
        allowed_ips = whitelist_config.get("allowed_ips", [])
        return ip in allowed_ips
    
    def get_auth_config(self) -> Dict:
        """获取认证配置"""
        auth_config = self.config.get("authentication", {})
        
        # 支持环境变量覆盖header_name
        env_header_name = os.getenv("API_KEY_HEADER")
        if env_header_name:
            auth_config["header_name"] = env_header_name
            
        return auth_config
    
    def get_logging_config(self) -> Dict:
        """获取日志配置"""
        return self.config.get("logging", {})
    
    def add_api_key(self, api_key: str, name: str, permissions: List[str] = None, 
                   rate_limit: Dict = None, ip_whitelist: List[str] = None,
                   expires_at: str = None) -> bool:
        """添加新的API Key"""
        try:
            if permissions is None:
                permissions = ["read"]
            
            key_info = {
                "name": name,
                "permissions": permissions,
                "rate_limit": rate_limit or self.get_rate_limits(),
                "ip_whitelist": ip_whitelist or [],
                "enabled": True,
                "created_at": datetime.now().isoformat() + "Z",
                "expires_at": expires_at
            }
            
            self.config["api_keys"][api_key] = key_info
            self._save_config(self.config)
            return True
        except Exception as e:
            logger.error(f"Failed to add API key: {e}")
            return False
    
    def remove_api_key(self, api_key: str) -> bool:
        """删除API Key"""
        try:
            if api_key in self.config.get("api_keys", {}):
                del self.config["api_keys"][api_key]
                self._save_config(self.config)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove API key: {e}")
            return False
    
    def update_ip_whitelist(self, allowed_ips: List[str], enabled: bool = True) -> bool:
        """更新IP白名单"""
        try:
            self.config["ip_whitelist"] = {
                "enabled": enabled,
                "allowed_ips": allowed_ips
            }
            self._save_config(self.config)
            return True
        except Exception as e:
            logger.error(f"Failed to update IP whitelist: {e}")
            return False

# 全局安全配置实例
security_config = SecurityConfig()

# 环境变量支持
def get_env_api_keys() -> Dict[str, str]:
    """从环境变量获取API Keys"""
    api_keys = {}
    
    # 支持多个API Key的环境变量格式：API_KEY_1, API_KEY_2, etc.
    for key, value in os.environ.items():
        if key.startswith('API_KEY_'):
            api_keys[value] = {
                "name": f"Environment Key {key}",
                "permissions": ["read", "write", "read:market_data", "write:market_data", "admin:system"],
                "rate_limit": security_config.get_rate_limits(),
                "ip_whitelist": [],
                "enabled": True,
                "created_at": datetime.now().isoformat() + "Z",
                "expires_at": None
            }
    
    return api_keys

# 合并环境变量中的API Keys
env_api_keys = get_env_api_keys()
if env_api_keys:
    security_config.config["api_keys"].update(env_api_keys)