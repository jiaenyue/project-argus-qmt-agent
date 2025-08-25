"""Windows兼容监控配置模块

提供统一的监控配置和日志格式设置，使用Windows Performance Counters和事件日志
"""

import logging
import sys
from datetime import datetime
from typing import Dict, Any
import json

# 监控配置
MONITORING_CONFIG = {
    # 健康检查配置
    "health_check": {
        "cache_duration_seconds": 30,
        "response_timeout_ms": 100,
        "qmt_connection_timeout_seconds": 5
    },
    
    # Windows性能监控配置
    "windows_monitoring": {
        "metrics_path": "/metrics",
        "collect_system_metrics": True,
        "collect_request_metrics": True,
        "performance_counters_enabled": True,
        "event_log_enabled": True,
        "metrics_collection_interval": 30,  # 秒
        "request_duration_buckets": [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
    },
    
    # 系统指标配置
    "system_metrics": {
        "cpu_collection_interval": 0.1,
        "memory_warning_threshold_percent": 80,
        "cpu_warning_threshold_percent": 80
    },
    
    # 日志配置
    "logging": {
        "level": "INFO",
        "format": "structured",  # structured 或 standard
        "include_request_id": True,
        "include_timestamp": True,
        "include_service_info": True,
        "console_output": True,
        "file_output": True,
        "log_requests": True,
        "log_auth_events": True,
        "log_rate_limit_exceeded": True,
        "log_performance": True,
        "log_response_headers": False,
        "log_all_performance": False,
        # 日志轮转配置
        "rotation": {
            "max_bytes": 50 * 1024 * 1024,  # 50MB
            "backup_count": 10,
            "log_directory": "logs",
            "access_log_file": "access.log",
            "security_log_file": "security.log",
            "performance_log_file": "performance.log",
            "application_log_file": "application.log",
            "error_log_file": "error.log"
        }
    }
}

class StructuredFormatter(logging.Formatter):
    """统一的结构化日志格式器"""
    
    def format(self, record):
        """格式化日志记录为JSON结构"""
        # 基础日志信息
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "data-agent-service",
            "version": "1.0.0",
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # 添加堆栈信息
        if record.stack_info:
            log_entry["stack_info"] = record.stack_info
        
        # 添加自定义字段（排除标准字段）
        excluded_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
            'filename', 'module', 'lineno', 'funcName', 'created', 
            'msecs', 'relativeCreated', 'thread', 'threadName', 
            'processName', 'process', 'getMessage', 'exc_info', 
            'exc_text', 'stack_info', 'taskName'
        }
        
        for key, value in record.__dict__.items():
            if key not in excluded_fields and not key.startswith('_'):
                # 处理特殊类型的值
                try:
                    json.dumps(value)  # 测试是否可序列化
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)

def setup_logging(config: Dict[str, Any] = None, logger_name: str = "data_agent_service") -> logging.Logger:
    """设置统一的日志配置
    
    Args:
        config: 日志配置字典，如果为None则使用默认配置
        logger_name: logger名称
    
    Returns:
        配置好的logger实例
    """
    if config is None:
        config = MONITORING_CONFIG["logging"]
    
    # 创建logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, config.get("level", "INFO")))
    
    # 清除现有的handlers
    logger.handlers.clear()
    
    # 设置格式器
    if config.get("format") == "structured":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # 控制台处理器
    if config.get("console_output", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器
    if config.get("file_output", False):
        try:
            import os
            from logging.handlers import RotatingFileHandler
            
            rotation_config = config.get("rotation", {})
            log_dir = rotation_config.get("log_directory", "logs")
            
            # 创建日志目录
            os.makedirs(log_dir, exist_ok=True)
            
            # 根据logger名称选择日志文件
            log_file_map = {
                "data_agent_service": rotation_config.get("application_log_file", "application.log"),
                "api_access": rotation_config.get("access_log_file", "access.log"),
                "api_security": rotation_config.get("security_log_file", "security.log"),
                "api_performance": rotation_config.get("performance_log_file", "performance.log"),
                "error": rotation_config.get("error_log_file", "error.log")
            }
            
            log_file = log_file_map.get(logger_name, "application.log")
            log_path = os.path.join(log_dir, log_file)
            
            # 创建轮转文件处理器
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=rotation_config.get("max_bytes", 50 * 1024 * 1024),  # 50MB
                backupCount=rotation_config.get("backup_count", 10),
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
        except Exception as e:
            # 如果文件日志设置失败，记录到控制台
            print(f"Failed to setup file logging for {logger_name}: {e}")
    
    # 防止日志重复
    logger.propagate = False
    
    return logger

def get_monitoring_config() -> Dict[str, Any]:
    """获取监控配置"""
    return MONITORING_CONFIG.copy()

def update_monitoring_config(updates: Dict[str, Any]) -> None:
    """更新监控配置
    
    Args:
        updates: 要更新的配置项
    """
    def deep_update(base_dict, update_dict):
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    deep_update(MONITORING_CONFIG, updates)

# 创建默认的logger实例
default_logger = setup_logging()