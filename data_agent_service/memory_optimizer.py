#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存优化模块

提供内存使用监控、垃圾回收优化和内存泄漏检测功能。
包括内存统计、对象追踪、垃圾回收调优等功能。
"""

import gc
import sys
import psutil
import threading
import time
import weakref
import tracemalloc
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class MemoryThresholdLevel(Enum):
    """内存阈值级别"""
    LOW = "low"          # 低使用率
    NORMAL = "normal"    # 正常使用率
    HIGH = "high"        # 高使用率
    CRITICAL = "critical" # 临界使用率

class GCMode(Enum):
    """垃圾回收模式"""
    CONSERVATIVE = "conservative"  # 保守模式
    BALANCED = "balanced"         # 平衡模式
    AGGRESSIVE = "aggressive"     # 激进模式
    CUSTOM = "custom"             # 自定义模式

@dataclass
class MemoryStats:
    """内存统计信息"""
    timestamp: datetime
    total_memory: int  # 总内存 (bytes)
    available_memory: int  # 可用内存 (bytes)
    used_memory: int  # 已用内存 (bytes)
    memory_percent: float  # 内存使用百分比
    process_memory: int  # 进程内存 (bytes)
    process_percent: float  # 进程内存百分比
    gc_collections: Dict[int, int]  # GC收集次数
    gc_collected: Dict[int, int]  # GC收集对象数
    gc_uncollectable: Dict[int, int]  # GC不可收集对象数
    object_count: int  # 对象总数
    threshold_level: MemoryThresholdLevel

@dataclass
class ObjectTracker:
    """对象追踪器"""
    object_type: str
    count: int
    size_estimate: int
    growth_rate: float
    last_update: datetime
    references: List[weakref.ref] = field(default_factory=list)

@dataclass
class MemoryLeak:
    """内存泄漏信息"""
    object_type: str
    leak_rate: float  # 泄漏速率 (objects/second)
    total_leaked: int
    first_detected: datetime
    last_detected: datetime
    severity: str  # low, medium, high, critical
    stack_trace: Optional[str] = None

@dataclass
class GCConfig:
    """垃圾回收配置"""
    mode: GCMode
    thresholds: Tuple[int, int, int]  # (gen0, gen1, gen2)
    auto_collect: bool
    collect_interval: float  # 自动收集间隔 (seconds)
    memory_threshold: float  # 内存阈值百分比
    force_collect_threshold: float  # 强制收集阈值

class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, 
                 check_interval: float = 5.0,
                 history_size: int = 1000,
                 enable_tracemalloc: bool = True):
        self.check_interval = check_interval
        self.history_size = history_size
        self.enable_tracemalloc = enable_tracemalloc
        
        # 内存统计历史
        self.memory_history: deque = deque(maxlen=history_size)
        
        # 对象追踪
        self.object_trackers: Dict[str, ObjectTracker] = {}
        self.tracked_objects: Set[weakref.ref] = set()
        
        # 内存泄漏检测
        self.potential_leaks: Dict[str, MemoryLeak] = {}
        self.leak_detection_window = timedelta(minutes=10)
        
        # 监控状态
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # 进程信息
        self.process = psutil.Process()
        
        # 启用内存追踪
        if self.enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()
    
    def start_monitoring(self):
        """启动内存监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("内存监控已启动")
    
    def stop_monitoring(self):
        """停止内存监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self._stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("内存监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while not self._stop_event.wait(self.check_interval):
            try:
                stats = self._collect_memory_stats()
                self.memory_history.append(stats)
                
                # 更新对象追踪
                self._update_object_tracking()
                
                # 检测内存泄漏
                self._detect_memory_leaks()
                
                # 检查内存阈值
                self._check_memory_thresholds(stats)
                
            except Exception as e:
                logger.error(f"内存监控循环出错: {e}")
    
    def _collect_memory_stats(self) -> MemoryStats:
        """收集内存统计信息"""
        # 系统内存信息
        memory = psutil.virtual_memory()
        
        # 进程内存信息
        process_memory = self.process.memory_info()
        
        # GC统计信息
        gc_stats = gc.get_stats()
        gc_collections = {i: stat['collections'] for i, stat in enumerate(gc_stats)}
        gc_collected = {i: stat['collected'] for i, stat in enumerate(gc_stats)}
        gc_uncollectable = {i: stat['uncollectable'] for i, stat in enumerate(gc_stats)}
        
        # 对象计数
        object_count = len(gc.get_objects())
        
        # 确定阈值级别
        threshold_level = self._determine_threshold_level(memory.percent)
        
        return MemoryStats(
            timestamp=datetime.now(),
            total_memory=memory.total,
            available_memory=memory.available,
            used_memory=memory.used,
            memory_percent=memory.percent,
            process_memory=process_memory.rss,
            process_percent=(process_memory.rss / memory.total) * 100,
            gc_collections=gc_collections,
            gc_collected=gc_collected,
            gc_uncollectable=gc_uncollectable,
            object_count=object_count,
            threshold_level=threshold_level
        )
    
    def _determine_threshold_level(self, memory_percent: float) -> MemoryThresholdLevel:
        """确定内存阈值级别"""
        if memory_percent < 50:
            return MemoryThresholdLevel.LOW
        elif memory_percent < 75:
            return MemoryThresholdLevel.NORMAL
        elif memory_percent < 90:
            return MemoryThresholdLevel.HIGH
        else:
            return MemoryThresholdLevel.CRITICAL
    
    def _update_object_tracking(self):
        """更新对象追踪"""
        current_objects = defaultdict(int)
        
        # 统计当前对象
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            current_objects[obj_type] += 1
        
        now = datetime.now()
        
        # 更新追踪器
        for obj_type, count in current_objects.items():
            if obj_type in self.object_trackers:
                tracker = self.object_trackers[obj_type]
                old_count = tracker.count
                time_diff = (now - tracker.last_update).total_seconds()
                
                if time_diff > 0:
                    growth_rate = (count - old_count) / time_diff
                    tracker.growth_rate = growth_rate
                
                tracker.count = count
                tracker.last_update = now
            else:
                self.object_trackers[obj_type] = ObjectTracker(
                    object_type=obj_type,
                    count=count,
                    size_estimate=sys.getsizeof(obj_type),
                    growth_rate=0.0,
                    last_update=now
                )
    
    def _detect_memory_leaks(self):
        """检测内存泄漏"""
        now = datetime.now()
        
        for obj_type, tracker in self.object_trackers.items():
            # 检查增长率
            if tracker.growth_rate > 10:  # 每秒增长超过10个对象
                if obj_type not in self.potential_leaks:
                    self.potential_leaks[obj_type] = MemoryLeak(
                        object_type=obj_type,
                        leak_rate=tracker.growth_rate,
                        total_leaked=0,
                        first_detected=now,
                        last_detected=now,
                        severity=self._determine_leak_severity(tracker.growth_rate)
                    )
                else:
                    leak = self.potential_leaks[obj_type]
                    leak.leak_rate = tracker.growth_rate
                    leak.last_detected = now
                    leak.total_leaked += max(0, int(tracker.growth_rate))
                    leak.severity = self._determine_leak_severity(tracker.growth_rate)
        
        # 清理过期的泄漏记录
        expired_leaks = []
        for obj_type, leak in self.potential_leaks.items():
            if now - leak.last_detected > self.leak_detection_window:
                expired_leaks.append(obj_type)
        
        for obj_type in expired_leaks:
            del self.potential_leaks[obj_type]
    
    def _determine_leak_severity(self, growth_rate: float) -> str:
        """确定泄漏严重程度"""
        if growth_rate < 10:
            return "low"
        elif growth_rate < 50:
            return "medium"
        elif growth_rate < 100:
            return "high"
        else:
            return "critical"
    
    def _check_memory_thresholds(self, stats: MemoryStats):
        """检查内存阈值"""
        if stats.threshold_level == MemoryThresholdLevel.CRITICAL:
            logger.warning(f"内存使用率达到临界水平: {stats.memory_percent:.1f}%")
        elif stats.threshold_level == MemoryThresholdLevel.HIGH:
            logger.info(f"内存使用率较高: {stats.memory_percent:.1f}%")
    
    def get_current_stats(self) -> Optional[MemoryStats]:
        """获取当前内存统计"""
        if self.memory_history:
            return self.memory_history[-1]
        return self._collect_memory_stats()
    
    def get_memory_history(self, limit: Optional[int] = None) -> List[MemoryStats]:
        """获取内存历史"""
        history = list(self.memory_history)
        if limit:
            return history[-limit:]
        return history
    
    def get_object_trackers(self) -> Dict[str, ObjectTracker]:
        """获取对象追踪器"""
        return self.object_trackers.copy()
    
    def get_potential_leaks(self) -> Dict[str, MemoryLeak]:
        """获取潜在内存泄漏"""
        return self.potential_leaks.copy()

class GarbageCollector:
    """垃圾回收优化器"""
    
    def __init__(self, config: Optional[GCConfig] = None):
        self.config = config or self._get_default_config()
        self.is_auto_collecting = False
        self.collect_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # 应用配置
        self._apply_config()
    
    def _get_default_config(self) -> GCConfig:
        """获取默认配置"""
        return GCConfig(
            mode=GCMode.BALANCED,
            thresholds=(700, 10, 10),
            auto_collect=True,
            collect_interval=30.0,
            memory_threshold=80.0,
            force_collect_threshold=90.0
        )
    
    def _apply_config(self):
        """应用配置"""
        # 设置GC阈值
        gc.set_threshold(*self.config.thresholds)
        
        # 根据模式调整
        if self.config.mode == GCMode.CONSERVATIVE:
            gc.set_threshold(1000, 15, 15)
        elif self.config.mode == GCMode.AGGRESSIVE:
            gc.set_threshold(400, 5, 5)
        elif self.config.mode == GCMode.BALANCED:
            gc.set_threshold(700, 10, 10)
    
    def start_auto_collection(self):
        """启动自动垃圾回收"""
        if not self.config.auto_collect or self.is_auto_collecting:
            return
        
        self.is_auto_collecting = True
        self._stop_event.clear()
        self.collect_thread = threading.Thread(target=self._auto_collect_loop, daemon=True)
        self.collect_thread.start()
        logger.info("自动垃圾回收已启动")
    
    def stop_auto_collection(self):
        """停止自动垃圾回收"""
        if not self.is_auto_collecting:
            return
        
        self.is_auto_collecting = False
        self._stop_event.set()
        
        if self.collect_thread and self.collect_thread.is_alive():
            self.collect_thread.join(timeout=5.0)
        
        logger.info("自动垃圾回收已停止")
    
    def _auto_collect_loop(self):
        """自动收集循环"""
        while not self._stop_event.wait(self.config.collect_interval):
            try:
                memory_percent = psutil.virtual_memory().percent
                
                if memory_percent >= self.config.force_collect_threshold:
                    # 强制全面收集
                    self.force_collect_all()
                elif memory_percent >= self.config.memory_threshold:
                    # 常规收集
                    self.collect_generation(2)
                
            except Exception as e:
                logger.error(f"自动垃圾回收出错: {e}")
    
    def collect_generation(self, generation: int) -> int:
        """收集指定代的垃圾"""
        try:
            collected = gc.collect(generation)
            logger.debug(f"GC generation {generation} 收集了 {collected} 个对象")
            return collected
        except Exception as e:
            logger.error(f"垃圾回收出错: {e}")
            return 0
    
    def force_collect_all(self) -> Dict[int, int]:
        """强制收集所有代的垃圾"""
        results = {}
        for generation in range(3):
            results[generation] = self.collect_generation(generation)
        
        logger.info(f"强制垃圾回收完成: {results}")
        return results
    
    def get_gc_stats(self) -> Dict[str, Any]:
        """获取垃圾回收统计"""
        stats = gc.get_stats()
        return {
            "thresholds": gc.get_threshold(),
            "counts": gc.get_count(),
            "stats": stats,
            "config": {
                "mode": self.config.mode.value,
                "auto_collect": self.config.auto_collect,
                "collect_interval": self.config.collect_interval
            }
        }

class MemoryOptimizer:
    """内存优化器主类"""
    
    def __init__(self, 
                 monitor_interval: float = 5.0,
                 gc_config: Optional[GCConfig] = None,
                 enable_tracemalloc: bool = True):
        self.monitor = MemoryMonitor(
            check_interval=monitor_interval,
            enable_tracemalloc=enable_tracemalloc
        )
        self.gc_optimizer = GarbageCollector(gc_config)
        
        # 优化建议
        self.optimization_suggestions: List[str] = []
        
        # 性能指标
        self.performance_metrics = {
            "memory_saved": 0,
            "gc_optimizations": 0,
            "leak_detections": 0
        }
    
    def start(self):
        """启动内存优化器"""
        self.monitor.start_monitoring()
        self.gc_optimizer.start_auto_collection()
        logger.info("内存优化器已启动")
    
    def stop(self):
        """停止内存优化器"""
        self.monitor.stop_monitoring()
        self.gc_optimizer.stop_auto_collection()
        logger.info("内存优化器已停止")
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """获取内存摘要"""
        current_stats = self.monitor.get_current_stats()
        gc_stats = self.gc_optimizer.get_gc_stats()
        potential_leaks = self.monitor.get_potential_leaks()
        
        return {
            "current_memory": {
                "total_gb": current_stats.total_memory / (1024**3) if current_stats else 0,
                "used_gb": current_stats.used_memory / (1024**3) if current_stats else 0,
                "available_gb": current_stats.available_memory / (1024**3) if current_stats else 0,
                "usage_percent": current_stats.memory_percent if current_stats else 0,
                "process_mb": current_stats.process_memory / (1024**2) if current_stats else 0,
                "threshold_level": current_stats.threshold_level.value if current_stats else "unknown"
            },
            "garbage_collection": gc_stats,
            "potential_leaks": {
                "count": len(potential_leaks),
                "details": [
                    {
                        "type": leak.object_type,
                        "rate": leak.leak_rate,
                        "severity": leak.severity
                    }
                    for leak in potential_leaks.values()
                ]
            },
            "performance_metrics": self.performance_metrics,
            "optimization_suggestions": self.optimization_suggestions
        }
    
    def optimize_memory(self) -> Dict[str, Any]:
        """执行内存优化"""
        optimization_results = {
            "actions_taken": [],
            "memory_before": 0,
            "memory_after": 0,
            "memory_saved": 0
        }
        
        # 记录优化前内存
        before_stats = self.monitor.get_current_stats()
        if before_stats:
            optimization_results["memory_before"] = before_stats.process_memory
        
        # 执行垃圾回收
        gc_results = self.gc_optimizer.force_collect_all()
        optimization_results["actions_taken"].append(f"垃圾回收: {gc_results}")
        
        # 清理弱引用
        self._cleanup_weak_references()
        optimization_results["actions_taken"].append("清理弱引用")
        
        # 记录优化后内存
        after_stats = self.monitor._collect_memory_stats()
        optimization_results["memory_after"] = after_stats.process_memory
        
        # 计算节省的内存
        if before_stats:
            memory_saved = before_stats.process_memory - after_stats.process_memory
            optimization_results["memory_saved"] = memory_saved
            self.performance_metrics["memory_saved"] += memory_saved
        
        self.performance_metrics["gc_optimizations"] += 1
        
        return optimization_results
    
    def _cleanup_weak_references(self):
        """清理弱引用"""
        # 清理监控器中的弱引用
        dead_refs = [ref for ref in self.monitor.tracked_objects if ref() is None]
        for ref in dead_refs:
            self.monitor.tracked_objects.discard(ref)
        
        # 清理对象追踪器中的弱引用
        for tracker in self.monitor.object_trackers.values():
            tracker.references = [ref for ref in tracker.references if ref() is not None]
    
    def generate_optimization_report(self) -> Dict[str, Any]:
        """生成优化报告"""
        memory_history = self.monitor.get_memory_history(limit=100)
        potential_leaks = self.monitor.get_potential_leaks()
        
        # 分析内存趋势
        memory_trend = "stable"
        if len(memory_history) >= 2:
            recent_usage = [stats.memory_percent for stats in memory_history[-10:]]
            if len(recent_usage) >= 2:
                trend_slope = (recent_usage[-1] - recent_usage[0]) / len(recent_usage)
                if trend_slope > 1:
                    memory_trend = "increasing"
                elif trend_slope < -1:
                    memory_trend = "decreasing"
        
        # 生成建议
        suggestions = self._generate_suggestions(memory_history, potential_leaks)
        
        return {
            "report_time": datetime.now().isoformat(),
            "memory_trend": memory_trend,
            "total_leaks_detected": len(potential_leaks),
            "critical_leaks": len([leak for leak in potential_leaks.values() if leak.severity == "critical"]),
            "suggestions": suggestions,
            "performance_metrics": self.performance_metrics,
            "memory_history_summary": {
                "avg_usage": sum(stats.memory_percent for stats in memory_history) / len(memory_history) if memory_history else 0,
                "max_usage": max(stats.memory_percent for stats in memory_history) if memory_history else 0,
                "min_usage": min(stats.memory_percent for stats in memory_history) if memory_history else 0
            }
        }
    
    def _generate_suggestions(self, memory_history: List[MemoryStats], potential_leaks: Dict[str, MemoryLeak]) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        # 基于内存使用率的建议
        if memory_history:
            avg_usage = sum(stats.memory_percent for stats in memory_history) / len(memory_history)
            if avg_usage > 80:
                suggestions.append("内存使用率过高，建议增加系统内存或优化应用程序")
            elif avg_usage > 60:
                suggestions.append("内存使用率较高，建议定期执行垃圾回收")
        
        # 基于内存泄漏的建议
        if potential_leaks:
            critical_leaks = [leak for leak in potential_leaks.values() if leak.severity == "critical"]
            if critical_leaks:
                suggestions.append(f"检测到 {len(critical_leaks)} 个严重内存泄漏，需要立即处理")
            
            high_leaks = [leak for leak in potential_leaks.values() if leak.severity == "high"]
            if high_leaks:
                suggestions.append(f"检测到 {len(high_leaks)} 个高风险内存泄漏，建议优先处理")
        
        # 基于GC统计的建议
        gc_stats = self.gc_optimizer.get_gc_stats()
        if gc_stats["counts"][0] > 1000:
            suggestions.append("第0代垃圾回收过于频繁，建议调整GC阈值")
        
        return suggestions

# 全局内存优化器实例
_global_memory_optimizer: Optional[MemoryOptimizer] = None
_optimizer_lock = threading.Lock()

def get_global_memory_optimizer() -> MemoryOptimizer:
    """获取全局内存优化器实例"""
    global _global_memory_optimizer
    
    if _global_memory_optimizer is None:
        with _optimizer_lock:
            if _global_memory_optimizer is None:
                _global_memory_optimizer = MemoryOptimizer()
    
    return _global_memory_optimizer

def shutdown_global_memory_optimizer():
    """关闭全局内存优化器"""
    global _global_memory_optimizer
    
    if _global_memory_optimizer is not None:
        with _optimizer_lock:
            if _global_memory_optimizer is not None:
                _global_memory_optimizer.stop()
                _global_memory_optimizer = None
                logger.info("全局内存优化器已关闭")