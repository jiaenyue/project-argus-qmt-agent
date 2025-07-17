"""
通用工具库 - Project Argus QMT 数据代理服务教程

这个包提供了统一的工具函数、配置管理和API客户端，
用于改进教程代码的质量和一致性。
"""

__version__ = "1.0.0"
__author__ = "Project Argus Team"

# 导出主要组件
from .config import TutorialConfig
from .utils import PerformanceMonitor, format_response_time, print_section_header, print_api_result, validate_date_format

__all__ = [
    'TutorialConfig',
    'PerformanceMonitor', 
    'format_response_time',
    'print_section_header',
    'print_api_result',
    'validate_date_format'
]