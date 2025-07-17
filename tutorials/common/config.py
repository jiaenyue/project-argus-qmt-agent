"""
配置管理模块 - Project Argus QMT 数据代理服务教程

提供统一的配置管理，包括API端点、超时时间、重试次数等配置常量，
以及配置验证和默认值处理功能。
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class APIConfig:
    """API配置类"""
    base_url: str = "http://127.0.0.1:8000"
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    
    def validate(self) -> bool:
        """验证API配置的有效性"""
        if not self.base_url or not isinstance(self.base_url, str):
            return False
        if self.timeout <= 0 or self.max_retries < 0:
            return False
        if self.retry_delay < 0:
            return False
        return True


@dataclass 
class DisplayConfig:
    """显示配置类"""
    max_display_items: int = 10
    enable_performance_monitoring: bool = True
    show_timestamps: bool = True
    decimal_places: int = 4
    
    def validate(self) -> bool:
        """验证显示配置的有效性"""
        if self.max_display_items <= 0:
            return False
        if self.decimal_places < 0:
            return False
        return True


class TutorialConfig:
    """教程配置管理类
    
    提供统一的配置管理，支持环境变量覆盖和配置验证。
    """
    
    def __init__(self):
        """初始化配置管理器"""
        self._api_config = None
        self._display_config = None
        self._demo_data = None
        self._load_config()
    
    def _load_config(self):
        """加载配置，支持环境变量覆盖"""
        # API配置
        self._api_config = APIConfig(
            base_url=os.getenv('QMT_API_BASE_URL', 'http://127.0.0.1:8000'),
            timeout=int(os.getenv('QMT_API_TIMEOUT', '10')),
            max_retries=int(os.getenv('QMT_API_MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('QMT_API_RETRY_DELAY', '1.0'))
        )
        
        # 显示配置
        self._display_config = DisplayConfig(
            max_display_items=int(os.getenv('QMT_MAX_DISPLAY_ITEMS', '10')),
            enable_performance_monitoring=os.getenv('QMT_ENABLE_PERF_MONITORING', 'true').lower() == 'true',
            show_timestamps=os.getenv('QMT_SHOW_TIMESTAMPS', 'true').lower() == 'true',
            decimal_places=int(os.getenv('QMT_DECIMAL_PLACES', '4'))
        )
        
        # 演示数据配置
        self._demo_data = {
            'symbols': [
                "600519.SH",  # 贵州茅台
                "000858.SZ",  # 五粮液
                "601318.SH",  # 中国平安
                "000001.SZ",  # 平安银行
                "600036.SH"   # 招商银行
            ],
            'markets': ["SH", "SZ"],
            'frequencies': ["1m", "5m", "15m", "30m", "1h", "1d"],
            'default_date_range': 30  # 默认30天
        }
    
    @property
    def api(self) -> APIConfig:
        """获取API配置"""
        return self._api_config
    
    @property
    def display(self) -> DisplayConfig:
        """获取显示配置"""
        return self._display_config
    
    @property
    def demo_symbols(self) -> List[str]:
        """获取演示用股票代码列表"""
        return self._demo_data['symbols'].copy()
    
    @property
    def demo_markets(self) -> List[str]:
        """获取演示用市场列表"""
        return self._demo_data['markets'].copy()
    
    @property
    def demo_frequencies(self) -> List[str]:
        """获取演示用频率列表"""
        return self._demo_data['frequencies'].copy()
    
    @property
    def default_date_range(self) -> int:
        """获取默认日期范围（天数）"""
        return self._demo_data['default_date_range']
    
    def validate_all(self) -> Dict[str, bool]:
        """验证所有配置的有效性
        
        Returns:
            Dict[str, bool]: 各配置模块的验证结果
        """
        return {
            'api_config': self._api_config.validate(),
            'display_config': self._display_config.validate()
        }
    
    def is_valid(self) -> bool:
        """检查所有配置是否有效
        
        Returns:
            bool: 所有配置都有效时返回True
        """
        validation_results = self.validate_all()
        return all(validation_results.values())
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息
        
        Returns:
            Dict[str, Any]: 配置摘要
        """
        return {
            'api': {
                'base_url': self._api_config.base_url,
                'timeout': self._api_config.timeout,
                'max_retries': self._api_config.max_retries,
                'retry_delay': self._api_config.retry_delay
            },
            'display': {
                'max_display_items': self._display_config.max_display_items,
                'enable_performance_monitoring': self._display_config.enable_performance_monitoring,
                'show_timestamps': self._display_config.show_timestamps,
                'decimal_places': self._display_config.decimal_places
            },
            'demo_data': {
                'symbols_count': len(self._demo_data['symbols']),
                'markets_count': len(self._demo_data['markets']),
                'frequencies_count': len(self._demo_data['frequencies']),
                'default_date_range': self._demo_data['default_date_range']
            },
            'validation': self.validate_all()
        }
    
    def update_api_config(self, **kwargs):
        """更新API配置
        
        Args:
            **kwargs: API配置参数
        """
        for key, value in kwargs.items():
            if hasattr(self._api_config, key):
                setattr(self._api_config, key, value)
    
    def update_display_config(self, **kwargs):
        """更新显示配置
        
        Args:
            **kwargs: 显示配置参数
        """
        for key, value in kwargs.items():
            if hasattr(self._display_config, key):
                setattr(self._display_config, key, value)


# 全局配置实例
config = TutorialConfig()


def get_config() -> TutorialConfig:
    """获取全局配置实例
    
    Returns:
        TutorialConfig: 配置管理器实例
    """
    return config


def reset_config():
    """重置配置为默认值"""
    global config
    config = TutorialConfig()


if __name__ == "__main__":
    # 配置测试和演示
    print("=== Project Argus QMT 教程配置管理 ===")
    
    # 显示当前配置
    config_summary = config.get_config_summary()
    print(f"\n当前配置摘要:")
    for section, details in config_summary.items():
        print(f"  {section}: {details}")
    
    # 验证配置
    print(f"\n配置验证结果: {'通过' if config.is_valid() else '失败'}")
    
    # 演示配置更新
    print(f"\n演示用股票代码: {config.demo_symbols[:3]}...")
    print(f"支持的市场: {config.demo_markets}")
    print(f"支持的频率: {config.demo_frequencies}")