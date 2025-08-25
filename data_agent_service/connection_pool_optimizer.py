#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接池优化模块
实现智能连接池管理、监控和自动调优
"""

import asyncio
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
from sqlalchemy.pool import QueuePool, StaticPool, NullPool
from sqlalchemy import event, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DisconnectionError, TimeoutError as SQLTimeoutError
import psutil
import json

from .exception_handler import safe_execute

logger = logging.getLogger(__name__)

@dataclass
class ConnectionMetrics:
    """连接指标"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    checked_out_connections: int = 0
    overflow_connections: int = 0
    invalid_connections: int = 0
    
    # 性能指标
    avg_checkout_time: float = 0.0
    max_checkout_time: float = 0.0
    total_checkouts: int = 0
    failed_checkouts: int = 0
    
    # 时间戳
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class ConnectionEvent:
    """连接事件"""
    event_type: str  # checkout, checkin, connect, disconnect, error
    timestamp: datetime
    duration: Optional[float] = None
    connection_id: Optional[str] = None
    error_message: Optional[str] = None
    pool_size: Optional[int] = None
    checked_out: Optional[int] = None

@dataclass
class PoolConfiguration:
    """连接池配置"""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    pool_reset_on_return: str = 'commit'
    
    # 自动调优参数
    auto_tune: bool = True
    min_pool_size: int = 5
    max_pool_size: int = 50
    target_utilization: float = 0.7  # 目标利用率
    adjustment_interval: int = 300  # 调整间隔（秒）

class ConnectionPoolMonitor:
    """连接池监控器"""
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.pool = engine.pool
        self.metrics_history: deque = deque(maxlen=1000)
        self.events_history: deque = deque(maxlen=5000)
        self.checkout_times: deque = deque(maxlen=1000)
        self.monitoring_enabled = True
        self._lock = threading.Lock()
        
        # 设置事件监听
        self._setup_event_listeners()
        
        logger.info("连接池监控器已初始化")
    
    def _setup_event_listeners(self):
        """设置事件监听器"""
        @event.listens_for(self.pool, "connect")
        def on_connect(dbapi_conn, connection_record):
            self._record_event("connect", connection_id=id(connection_record))
        
        @event.listens_for(self.pool, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            connection_record._checkout_start_time = time.time()
            self._record_event("checkout", connection_id=id(connection_record))
        
        @event.listens_for(self.pool, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            if hasattr(connection_record, '_checkout_start_time'):
                duration = time.time() - connection_record._checkout_start_time
                self.checkout_times.append(duration)
                delattr(connection_record, '_checkout_start_time')
                self._record_event("checkin", connection_id=id(connection_record), duration=duration)
        
        @event.listens_for(self.pool, "invalidate")
        def on_invalidate(dbapi_conn, connection_record, exception):
            error_msg = str(exception) if exception else "Unknown error"
            self._record_event("error", connection_id=id(connection_record), error_message=error_msg)
    
    def _record_event(self, event_type: str, **kwargs):
        """记录连接事件"""
        if not self.monitoring_enabled:
            return
        
        try:
            event = ConnectionEvent(
                event_type=event_type,
                timestamp=datetime.now(),
                **kwargs
            )
            
            with self._lock:
                self.events_history.append(event)
                
                # 记录当前池状态
                if hasattr(self.pool, 'size'):
                    event.pool_size = self.pool.size()
                if hasattr(self.pool, 'checkedout'):
                    event.checked_out = self.pool.checkedout()
        
        except Exception as e:
            logger.error(f"记录连接事件错误: {e}")
    
    def collect_metrics(self) -> ConnectionMetrics:
        """收集连接池指标"""
        try:
            pool = self.pool
            
            # 基础指标
            total_connections = pool.size() if hasattr(pool, 'size') else 0
            checked_out = pool.checkedout() if hasattr(pool, 'checkedout') else 0
            overflow = pool.overflow() if hasattr(pool, 'overflow') else 0
            invalid = pool.invalidated() if hasattr(pool, 'invalidated') else 0
            
            # 计算其他指标
            active_connections = checked_out
            idle_connections = max(0, total_connections - checked_out)
            
            # 性能指标
            with self._lock:
                checkout_times_list = list(self.checkout_times)
            
            avg_checkout_time = sum(checkout_times_list) / len(checkout_times_list) if checkout_times_list else 0
            max_checkout_time = max(checkout_times_list) if checkout_times_list else 0
            
            # 统计事件
            recent_events = [
                e for e in self.events_history 
                if e.timestamp > datetime.now() - timedelta(minutes=5)
            ]
            
            total_checkouts = len([e for e in recent_events if e.event_type == 'checkout'])
            failed_checkouts = len([e for e in recent_events if e.event_type == 'error'])
            
            metrics = ConnectionMetrics(
                total_connections=total_connections,
                active_connections=active_connections,
                idle_connections=idle_connections,
                checked_out_connections=checked_out,
                overflow_connections=overflow,
                invalid_connections=invalid,
                avg_checkout_time=avg_checkout_time,
                max_checkout_time=max_checkout_time,
                total_checkouts=total_checkouts,
                failed_checkouts=failed_checkouts
            )
            
            with self._lock:
                self.metrics_history.append(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"收集连接池指标错误: {e}")
            return ConnectionMetrics()
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        current_metrics = self.collect_metrics()
        
        # 计算趋势
        with self._lock:
            recent_metrics = list(self.metrics_history)[-10:] if len(self.metrics_history) >= 10 else list(self.metrics_history)
        
        trends = self._calculate_trends(recent_metrics)
        
        # 获取最近的事件
        recent_events = [
            asdict(e) for e in list(self.events_history)[-20:]
        ]
        
        return {
            'current_metrics': asdict(current_metrics),
            'trends': trends,
            'recent_events': recent_events,
            'pool_configuration': self._get_pool_config(),
            'health_status': self._assess_pool_health(current_metrics)
        }
    
    def _calculate_trends(self, metrics_list: List[ConnectionMetrics]) -> Dict[str, Any]:
        """计算趋势"""
        if len(metrics_list) < 2:
            return {}
        
        # 计算平均值变化
        first_half = metrics_list[:len(metrics_list)//2]
        second_half = metrics_list[len(metrics_list)//2:]
        
        def avg_metric(metrics, attr):
            values = [getattr(m, attr) for m in metrics]
            return sum(values) / len(values) if values else 0
        
        trends = {}
        for attr in ['active_connections', 'avg_checkout_time', 'failed_checkouts']:
            first_avg = avg_metric(first_half, attr)
            second_avg = avg_metric(second_half, attr)
            
            if first_avg > 0:
                change_percent = ((second_avg - first_avg) / first_avg) * 100
                trends[attr] = {
                    'change_percent': change_percent,
                    'direction': 'increasing' if change_percent > 5 else 'decreasing' if change_percent < -5 else 'stable'
                }
        
        return trends
    
    def _get_pool_config(self) -> Dict[str, Any]:
        """获取连接池配置"""
        pool = self.pool
        config = {}
        
        # 尝试获取各种配置参数
        for attr in ['_pool_size', '_max_overflow', '_timeout', '_recycle']:
            if hasattr(pool, attr):
                config[attr.lstrip('_')] = getattr(pool, attr)
        
        return config
    
    def _assess_pool_health(self, metrics: ConnectionMetrics) -> Dict[str, Any]:
        """评估连接池健康状况"""
        health = {
            'status': 'healthy',
            'issues': [],
            'recommendations': []
        }
        
        # 检查利用率
        if metrics.total_connections > 0:
            utilization = metrics.active_connections / metrics.total_connections
            
            if utilization > 0.9:
                health['status'] = 'warning'
                health['issues'].append('连接池利用率过高')
                health['recommendations'].append('考虑增加连接池大小')
            elif utilization < 0.1:
                health['issues'].append('连接池利用率过低')
                health['recommendations'].append('考虑减少连接池大小以节省资源')
        
        # 检查溢出连接
        if metrics.overflow_connections > 0:
            health['status'] = 'warning'
            health['issues'].append(f'存在 {metrics.overflow_connections} 个溢出连接')
            health['recommendations'].append('考虑增加基础连接池大小')
        
        # 检查失效连接
        if metrics.invalid_connections > 0:
            health['status'] = 'critical' if metrics.invalid_connections > 5 else 'warning'
            health['issues'].append(f'存在 {metrics.invalid_connections} 个失效连接')
            health['recommendations'].append('检查数据库连接稳定性')
        
        # 检查检出时间
        if metrics.avg_checkout_time > 1.0:
            health['status'] = 'warning'
            health['issues'].append(f'平均连接检出时间过长: {metrics.avg_checkout_time:.2f}s')
            health['recommendations'].append('检查连接池配置或数据库性能')
        
        # 检查失败率
        if metrics.total_checkouts > 0:
            failure_rate = metrics.failed_checkouts / metrics.total_checkouts
            if failure_rate > 0.05:  # 5%失败率
                health['status'] = 'critical'
                health['issues'].append(f'连接失败率过高: {failure_rate:.1%}')
                health['recommendations'].append('检查数据库可用性和网络连接')
        
        return health

class ConnectionPoolOptimizer:
    """连接池优化器"""
    
    def __init__(self, monitor: ConnectionPoolMonitor, config: PoolConfiguration):
        self.monitor = monitor
        self.config = config
        self.optimization_history: List[Dict[str, Any]] = []
        self.last_adjustment = datetime.now()
        self._optimization_lock = threading.Lock()
        
        logger.info("连接池优化器已初始化")
    
    @safe_execute
    async def analyze_and_optimize(self) -> Dict[str, Any]:
        """分析并优化连接池"""
        if not self.config.auto_tune:
            return {'status': 'auto_tune_disabled'}
        
        # 检查是否需要调整
        if datetime.now() - self.last_adjustment < timedelta(seconds=self.config.adjustment_interval):
            return {'status': 'too_soon_to_adjust'}
        
        with self._optimization_lock:
            analysis = await self._analyze_pool_performance()
            optimization_result = await self._apply_optimizations(analysis)
            
            # 记录优化历史
            self.optimization_history.append({
                'timestamp': datetime.now(),
                'analysis': analysis,
                'optimization': optimization_result
            })
            
            # 限制历史记录数量
            if len(self.optimization_history) > 100:
                self.optimization_history = self.optimization_history[-100:]
            
            self.last_adjustment = datetime.now()
            
            return {
                'status': 'completed',
                'analysis': analysis,
                'optimization': optimization_result
            }
    
    async def _analyze_pool_performance(self) -> Dict[str, Any]:
        """分析连接池性能"""
        # 收集最近的指标
        recent_metrics = list(self.monitor.metrics_history)[-20:] if len(self.monitor.metrics_history) >= 20 else list(self.monitor.metrics_history)
        
        if not recent_metrics:
            return {'status': 'insufficient_data'}
        
        # 计算平均指标
        avg_metrics = self._calculate_average_metrics(recent_metrics)
        
        # 分析利用率
        utilization_analysis = self._analyze_utilization(avg_metrics)
        
        # 分析性能
        performance_analysis = self._analyze_performance(avg_metrics)
        
        # 分析稳定性
        stability_analysis = self._analyze_stability(recent_metrics)
        
        # 系统资源分析
        resource_analysis = await self._analyze_system_resources()
        
        return {
            'avg_metrics': asdict(avg_metrics),
            'utilization': utilization_analysis,
            'performance': performance_analysis,
            'stability': stability_analysis,
            'resources': resource_analysis,
            'recommendations': self._generate_recommendations(
                utilization_analysis, performance_analysis, stability_analysis, resource_analysis
            )
        }
    
    def _calculate_average_metrics(self, metrics_list: List[ConnectionMetrics]) -> ConnectionMetrics:
        """计算平均指标"""
        if not metrics_list:
            return ConnectionMetrics()
        
        total_count = len(metrics_list)
        
        return ConnectionMetrics(
            total_connections=sum(m.total_connections for m in metrics_list) // total_count,
            active_connections=sum(m.active_connections for m in metrics_list) // total_count,
            idle_connections=sum(m.idle_connections for m in metrics_list) // total_count,
            checked_out_connections=sum(m.checked_out_connections for m in metrics_list) // total_count,
            overflow_connections=sum(m.overflow_connections for m in metrics_list) // total_count,
            invalid_connections=sum(m.invalid_connections for m in metrics_list) // total_count,
            avg_checkout_time=sum(m.avg_checkout_time for m in metrics_list) / total_count,
            max_checkout_time=max(m.max_checkout_time for m in metrics_list),
            total_checkouts=sum(m.total_checkouts for m in metrics_list),
            failed_checkouts=sum(m.failed_checkouts for m in metrics_list)
        )
    
    def _analyze_utilization(self, metrics: ConnectionMetrics) -> Dict[str, Any]:
        """分析利用率"""
        if metrics.total_connections == 0:
            return {'utilization': 0, 'status': 'no_connections'}
        
        utilization = metrics.active_connections / metrics.total_connections
        
        status = 'optimal'
        if utilization > 0.9:
            status = 'high'
        elif utilization < 0.1:
            status = 'low'
        elif utilization > 0.8:
            status = 'approaching_high'
        elif utilization < 0.2:
            status = 'approaching_low'
        
        return {
            'utilization': utilization,
            'status': status,
            'target_utilization': self.config.target_utilization,
            'deviation': abs(utilization - self.config.target_utilization)
        }
    
    def _analyze_performance(self, metrics: ConnectionMetrics) -> Dict[str, Any]:
        """分析性能"""
        performance = {
            'avg_checkout_time': metrics.avg_checkout_time,
            'max_checkout_time': metrics.max_checkout_time,
            'checkout_performance': 'good'
        }
        
        if metrics.avg_checkout_time > 1.0:
            performance['checkout_performance'] = 'poor'
        elif metrics.avg_checkout_time > 0.5:
            performance['checkout_performance'] = 'fair'
        
        # 失败率分析
        if metrics.total_checkouts > 0:
            failure_rate = metrics.failed_checkouts / metrics.total_checkouts
            performance['failure_rate'] = failure_rate
            performance['failure_status'] = 'good' if failure_rate < 0.01 else 'poor' if failure_rate > 0.05 else 'fair'
        else:
            performance['failure_rate'] = 0
            performance['failure_status'] = 'unknown'
        
        return performance
    
    def _analyze_stability(self, metrics_list: List[ConnectionMetrics]) -> Dict[str, Any]:
        """分析稳定性"""
        if len(metrics_list) < 5:
            return {'status': 'insufficient_data'}
        
        # 计算连接数变化的标准差
        active_connections = [m.active_connections for m in metrics_list]
        avg_active = sum(active_connections) / len(active_connections)
        variance = sum((x - avg_active) ** 2 for x in active_connections) / len(active_connections)
        std_dev = variance ** 0.5
        
        # 计算变化系数
        coefficient_of_variation = std_dev / avg_active if avg_active > 0 else 0
        
        stability_status = 'stable'
        if coefficient_of_variation > 0.5:
            stability_status = 'unstable'
        elif coefficient_of_variation > 0.3:
            stability_status = 'somewhat_unstable'
        
        return {
            'status': stability_status,
            'coefficient_of_variation': coefficient_of_variation,
            'std_deviation': std_dev,
            'avg_active_connections': avg_active
        }
    
    async def _analyze_system_resources(self) -> Dict[str, Any]:
        """分析系统资源"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            
            # 网络连接数
            connections = psutil.net_connections()
            tcp_connections = len([c for c in connections if c.type == 2])  # TCP
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'tcp_connections': tcp_connections,
                'resource_pressure': self._assess_resource_pressure(cpu_percent, memory.percent)
            }
        except Exception as e:
            logger.error(f"分析系统资源错误: {e}")
            return {'error': str(e)}
    
    def _assess_resource_pressure(self, cpu_percent: float, memory_percent: float) -> str:
        """评估资源压力"""
        if cpu_percent > 80 or memory_percent > 85:
            return 'high'
        elif cpu_percent > 60 or memory_percent > 70:
            return 'medium'
        else:
            return 'low'
    
    def _generate_recommendations(self, utilization: Dict, performance: Dict, 
                                stability: Dict, resources: Dict) -> List[Dict[str, Any]]:
        """生成优化建议"""
        recommendations = []
        
        # 利用率建议
        if utilization.get('status') == 'high':
            recommendations.append({
                'type': 'increase_pool_size',
                'priority': 'high',
                'reason': f"连接池利用率过高: {utilization['utilization']:.1%}",
                'suggested_action': f"建议将连接池大小从 {self.config.pool_size} 增加到 {min(self.config.pool_size + 5, self.config.max_pool_size)}"
            })
        elif utilization.get('status') == 'low':
            recommendations.append({
                'type': 'decrease_pool_size',
                'priority': 'medium',
                'reason': f"连接池利用率过低: {utilization['utilization']:.1%}",
                'suggested_action': f"建议将连接池大小从 {self.config.pool_size} 减少到 {max(self.config.pool_size - 3, self.config.min_pool_size)}"
            })
        
        # 性能建议
        if performance.get('checkout_performance') == 'poor':
            recommendations.append({
                'type': 'optimize_checkout_time',
                'priority': 'high',
                'reason': f"连接检出时间过长: {performance['avg_checkout_time']:.2f}s",
                'suggested_action': '检查数据库性能或增加连接池大小'
            })
        
        if performance.get('failure_status') == 'poor':
            recommendations.append({
                'type': 'fix_connection_failures',
                'priority': 'critical',
                'reason': f"连接失败率过高: {performance['failure_rate']:.1%}",
                'suggested_action': '检查数据库可用性和网络连接'
            })
        
        # 稳定性建议
        if stability.get('status') == 'unstable':
            recommendations.append({
                'type': 'improve_stability',
                'priority': 'medium',
                'reason': '连接使用模式不稳定',
                'suggested_action': '考虑调整连接池配置或应用负载均衡'
            })
        
        # 资源建议
        if resources.get('resource_pressure') == 'high':
            recommendations.append({
                'type': 'reduce_resource_usage',
                'priority': 'high',
                'reason': '系统资源压力过大',
                'suggested_action': '考虑减少连接池大小或优化应用性能'
            })
        
        return recommendations
    
    async def _apply_optimizations(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """应用优化"""
        applied_optimizations = []
        
        recommendations = analysis.get('recommendations', [])
        
        for rec in recommendations:
            if rec['priority'] in ['critical', 'high']:
                optimization_result = await self._apply_single_optimization(rec)
                if optimization_result:
                    applied_optimizations.append(optimization_result)
        
        return {
            'applied_count': len(applied_optimizations),
            'optimizations': applied_optimizations
        }
    
    async def _apply_single_optimization(self, recommendation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """应用单个优化"""
        try:
            if recommendation['type'] == 'increase_pool_size':
                new_size = min(self.config.pool_size + 5, self.config.max_pool_size)
                if new_size > self.config.pool_size:
                    old_size = self.config.pool_size
                    self.config.pool_size = new_size
                    return {
                        'type': 'pool_size_increased',
                        'old_value': old_size,
                        'new_value': new_size,
                        'reason': recommendation['reason']
                    }
            
            elif recommendation['type'] == 'decrease_pool_size':
                new_size = max(self.config.pool_size - 3, self.config.min_pool_size)
                if new_size < self.config.pool_size:
                    old_size = self.config.pool_size
                    self.config.pool_size = new_size
                    return {
                        'type': 'pool_size_decreased',
                        'old_value': old_size,
                        'new_value': new_size,
                        'reason': recommendation['reason']
                    }
        
        except Exception as e:
            logger.error(f"应用优化失败: {e}")
            return {
                'type': 'optimization_failed',
                'error': str(e),
                'recommendation': recommendation
            }
        
        return None
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """获取优化历史"""
        return self.optimization_history.copy()
    
    def reset_optimization_history(self):
        """重置优化历史"""
        self.optimization_history.clear()
        logger.info("优化历史已重置")

class ConnectionPoolManager:
    """连接池管理器"""
    
    def __init__(self, database_url: str, config: PoolConfiguration):
        self.database_url = database_url
        self.config = config
        self.engine: Optional[Engine] = None
        self.monitor: Optional[ConnectionPoolMonitor] = None
        self.optimizer: Optional[ConnectionPoolOptimizer] = None
        self._initialized = False
        
        logger.info("连接池管理器已创建")
    
    def initialize(self):
        """初始化连接池"""
        if self._initialized:
            return
        
        try:
            # 创建引擎和连接池
            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=self.config.pool_pre_ping,
                pool_reset_on_return=self.config.pool_reset_on_return,
                echo=False
            )
            
            # 创建监控器和优化器
            self.monitor = ConnectionPoolMonitor(self.engine)
            self.optimizer = ConnectionPoolOptimizer(self.monitor, self.config)
            
            self._initialized = True
            logger.info("连接池管理器已初始化")
            
        except Exception as e:
            logger.error(f"初始化连接池管理器失败: {e}")
            raise
    
    def get_engine(self) -> Engine:
        """获取数据库引擎"""
        if not self._initialized:
            self.initialize()
        return self.engine
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        if not self._initialized:
            return {'status': 'not_initialized'}
        
        return self.monitor.get_pool_status()
    
    async def optimize_pool(self) -> Dict[str, Any]:
        """优化连接池"""
        if not self._initialized:
            return {'status': 'not_initialized'}
        
        return await self.optimizer.analyze_and_optimize()
    
    def update_config(self, new_config: PoolConfiguration):
        """更新配置"""
        self.config = new_config
        if self.optimizer:
            self.optimizer.config = new_config
        
        logger.info("连接池配置已更新")
    
    def cleanup(self):
        """清理资源"""
        if self.engine:
            self.engine.dispose()
        
        self._initialized = False
        logger.info("连接池管理器已清理")

# 全局连接池管理器
_pool_manager: Optional[ConnectionPoolManager] = None

def get_connection_pool_manager(database_url: str = None, config: PoolConfiguration = None) -> ConnectionPoolManager:
    """获取全局连接池管理器"""
    global _pool_manager
    
    if _pool_manager is None and database_url:
        if config is None:
            config = PoolConfiguration()
        _pool_manager = ConnectionPoolManager(database_url, config)
    
    return _pool_manager

def cleanup_connection_pool_manager():
    """清理连接池管理器"""
    global _pool_manager
    if _pool_manager:
        _pool_manager.cleanup()
        _pool_manager = None