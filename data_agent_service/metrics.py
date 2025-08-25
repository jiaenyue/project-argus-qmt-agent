"""
指标收集器模块
Windows兼容的指标收集和管理
"""

import time
from collections import defaultdict, deque
from threading import Lock


class WindowsMetricsCollector:
    """Windows兼容的指标收集器"""
    
    def __init__(self):
        self._lock = Lock()
        self.request_counts = defaultdict(int)
        self.request_durations = defaultdict(list)
        self.qmt_connection_status = 0
        self.api_health_status = 1
        self.system_cpu_usage = 0.0
        self.system_memory_usage = 0.0
        self.last_update = time.time()
        
        # 保持最近1000个请求的持续时间用于统计
        self.max_duration_samples = 1000
    
    def increment_request_count(self, method: str, endpoint: str, status_code: str):
        """增加请求计数"""
        with self._lock:
            key = f"{method}_{endpoint}_{status_code}"
            self.request_counts[key] += 1
    
    def record_request_duration(self, method: str, endpoint: str, status_code: str, duration: float):
        """记录请求持续时间"""
        with self._lock:
            key = f"{method}_{endpoint}_{status_code}"
            if key not in self.request_durations:
                self.request_durations[key] = deque(maxlen=self.max_duration_samples)
            self.request_durations[key].append(duration)
    
    def set_qmt_connection_status(self, status: int):
        """设置QMT连接状态"""
        with self._lock:
            self.qmt_connection_status = status
    
    def set_api_health_status(self, status: int):
        """设置API健康状态"""
        with self._lock:
            self.api_health_status = status
    
    def set_system_metrics(self, cpu_usage: float, memory_usage: float):
        """设置系统指标"""
        with self._lock:
            self.system_cpu_usage = cpu_usage
            self.system_memory_usage = memory_usage
            self.last_update = time.time()
    
    def get_metrics_summary(self) -> dict:
        """获取指标摘要"""
        with self._lock:
            # 计算请求持续时间统计
            duration_stats = {}
            for key, durations in self.request_durations.items():
                if durations:
                    duration_list = list(durations)
                    duration_stats[key] = {
                        "count": len(duration_list),
                        "avg": sum(duration_list) / len(duration_list),
                        "min": min(duration_list),
                        "max": max(duration_list)
                    }
            
            return {
                "request_counts": dict(self.request_counts),
                "duration_stats": duration_stats,
                "qmt_connection_status": self.qmt_connection_status,
                "api_health_status": self.api_health_status,
                "system_cpu_usage": self.system_cpu_usage,
                "system_memory_usage": self.system_memory_usage,
                "last_update": self.last_update
            }


# 创建全局指标收集器实例
metrics_collector = WindowsMetricsCollector()