"""
WebSocket 实时数据系统 - 扩展管理器
根据 tasks.md 任务9要求实现的水平扩展和自动伸缩支持
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json

from .load_balancer import LoadBalancer, ServerNode, ClientPriority
from .service_discovery import ServiceDiscovery, ServiceInstance, ServiceStatus

logger = logging.getLogger(__name__)


class ScalingAction(str, Enum):
    """扩展动作"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


class ScalingTrigger(str, Enum):
    """扩展触发器"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    CONNECTION_COUNT = "connection_count"
    RESPONSE_TIME = "response_time"
    QUEUE_LENGTH = "queue_length"
    CUSTOM_METRIC = "custom_metric"


@dataclass
class ScalingRule:
    """扩展规则"""
    name: str
    trigger: ScalingTrigger
    metric_name: str
    scale_up_threshold: float
    scale_down_threshold: float
    scale_up_adjustment: int = 1
    scale_down_adjustment: int = 1
    cooldown_period: int = 300  # 冷却期（秒）
    evaluation_periods: int = 2  # 评估周期数
    enabled: bool = True


@dataclass
class ScalingConfig:
    """扩展配置"""
    min_instances: int = 1
    max_instances: int = 10
    target_cpu_utilization: float = 70.0
    target_memory_utilization: float = 80.0
    target_connections_per_instance: int = 800
    scale_up_cooldown: int = 300
    scale_down_cooldown: int = 600
    evaluation_interval: int = 60
    metrics_window: int = 300  # 指标窗口（秒）


@dataclass
class MetricData:
    """指标数据"""
    timestamp: datetime
    value: float
    source: str


@dataclass
class ScalingEvent:
    """扩展事件"""
    timestamp: datetime
    action: ScalingAction
    trigger: str
    reason: str
    old_count: int
    new_count: int
    success: bool
    error: Optional[str] = None


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, window_size: int = 300):
        self.window_size = window_size
        self.metrics: Dict[str, List[MetricData]] = {}
        
    def add_metric(self, name: str, value: float, source: str = "default") -> None:
        """添加指标数据"""
        if name not in self.metrics:
            self.metrics[name] = []
            
        metric = MetricData(
            timestamp=datetime.now(),
            value=value,
            source=source
        )
        
        self.metrics[name].append(metric)
        
        # 清理过期数据
        cutoff_time = datetime.now() - timedelta(seconds=self.window_size)
        self.metrics[name] = [
            m for m in self.metrics[name]
            if m.timestamp > cutoff_time
        ]
        
    def get_metric_average(self, name: str, period: int = 60) -> Optional[float]:
        """获取指标平均值"""
        if name not in self.metrics or not self.metrics[name]:
            return None
            
        cutoff_time = datetime.now() - timedelta(seconds=period)
        recent_metrics = [
            m for m in self.metrics[name]
            if m.timestamp > cutoff_time
        ]
        
        if not recent_metrics:
            return None
            
        return sum(m.value for m in recent_metrics) / len(recent_metrics)
        
    def get_metric_max(self, name: str, period: int = 60) -> Optional[float]:
        """获取指标最大值"""
        if name not in self.metrics or not self.metrics[name]:
            return None
            
        cutoff_time = datetime.now() - timedelta(seconds=period)
        recent_metrics = [
            m for m in self.metrics[name]
            if m.timestamp > cutoff_time
        ]
        
        if not recent_metrics:
            return None
            
        return max(m.value for m in recent_metrics)
        
    def get_all_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有指标数据"""
        result = {}
        for name, metrics in self.metrics.items():
            result[name] = [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "value": m.value,
                    "source": m.source
                }
                for m in metrics
            ]
        return result


class ScalingManager:
    """扩展管理器 - 管理自动伸缩和水平扩展"""
    
    def __init__(
        self,
        load_balancer: LoadBalancer,
        service_discovery: ServiceDiscovery,
        config: ScalingConfig
    ):
        self.load_balancer = load_balancer
        self.service_discovery = service_discovery
        self.config = config
        
        # 指标收集器
        self.metrics_collector = MetricsCollector(config.metrics_window)
        
        # 扩展规则
        self.scaling_rules: List[ScalingRule] = []
        self._setup_default_rules()
        
        # 扩展历史
        self.scaling_events: List[ScalingEvent] = []
        self.last_scale_up: Optional[datetime] = None
        self.last_scale_down: Optional[datetime] = None
        
        # 后台任务
        self._evaluation_task: Optional[asyncio.Task] = None
        self._metrics_collection_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        # 扩展回调
        self.scale_up_callbacks: List[Callable[[int], None]] = []
        self.scale_down_callbacks: List[Callable[[List[str]], None]] = []
        
    def _setup_default_rules(self) -> None:
        """设置默认扩展规则"""
        self.scaling_rules = [
            ScalingRule(
                name="cpu_based_scaling",
                trigger=ScalingTrigger.CPU_USAGE,
                metric_name="cpu_usage",
                scale_up_threshold=self.config.target_cpu_utilization,
                scale_down_threshold=self.config.target_cpu_utilization * 0.5,
                cooldown_period=self.config.scale_up_cooldown
            ),
            ScalingRule(
                name="memory_based_scaling",
                trigger=ScalingTrigger.MEMORY_USAGE,
                metric_name="memory_usage",
                scale_up_threshold=self.config.target_memory_utilization,
                scale_down_threshold=self.config.target_memory_utilization * 0.5,
                cooldown_period=self.config.scale_up_cooldown
            ),
            ScalingRule(
                name="connection_based_scaling",
                trigger=ScalingTrigger.CONNECTION_COUNT,
                metric_name="connections_per_instance",
                scale_up_threshold=self.config.target_connections_per_instance,
                scale_down_threshold=self.config.target_connections_per_instance * 0.3,
                cooldown_period=self.config.scale_up_cooldown
            )
        ]
        
    async def start(self) -> None:
        """启动扩展管理器"""
        if self._is_running:
            return
            
        logger.info("Starting ScalingManager")
        self._is_running = True
        
        # 启动后台任务
        self._evaluation_task = asyncio.create_task(self._evaluation_loop())
        self._metrics_collection_task = asyncio.create_task(self._metrics_collection_loop())
        
    async def stop(self) -> None:
        """停止扩展管理器"""
        if not self._is_running:
            return
            
        logger.info("Stopping ScalingManager")
        self._is_running = False
        
        # 停止后台任务
        if self._evaluation_task:
            self._evaluation_task.cancel()
        if self._metrics_collection_task:
            self._metrics_collection_task.cancel()
            
    def add_scaling_rule(self, rule: ScalingRule) -> None:
        """添加扩展规则"""
        self.scaling_rules.append(rule)
        logger.info(f"Added scaling rule: {rule.name}")
        
    def remove_scaling_rule(self, rule_name: str) -> bool:
        """移除扩展规则"""
        for i, rule in enumerate(self.scaling_rules):
            if rule.name == rule_name:
                del self.scaling_rules[i]
                logger.info(f"Removed scaling rule: {rule_name}")
                return True
        return False
        
    def add_scale_up_callback(self, callback: Callable[[int], None]) -> None:
        """添加扩容回调"""
        self.scale_up_callbacks.append(callback)
        
    def add_scale_down_callback(self, callback: Callable[[List[str]], None]) -> None:
        """添加缩容回调"""
        self.scale_down_callbacks.append(callback)
        
    async def evaluate_scaling(self) -> Optional[ScalingAction]:
        """评估是否需要扩展"""
        try:
            # 获取当前实例数
            instances = await self.service_discovery.get_healthy_instances()
            current_count = len(instances)
            
            if current_count == 0:
                logger.warning("No healthy instances found")
                return ScalingAction.NO_ACTION
                
            # 收集当前指标
            await self._collect_current_metrics(instances)
            
            # 评估每个规则
            scale_up_votes = 0
            scale_down_votes = 0
            
            for rule in self.scaling_rules:
                if not rule.enabled:
                    continue
                    
                action = await self._evaluate_rule(rule, current_count)
                if action == ScalingAction.SCALE_UP:
                    scale_up_votes += 1
                elif action == ScalingAction.SCALE_DOWN:
                    scale_down_votes += 1
                    
            # 决定扩展动作
            if scale_up_votes > 0 and current_count < self.config.max_instances:
                if self._can_scale_up():
                    return ScalingAction.SCALE_UP
            elif scale_down_votes > scale_up_votes and current_count > self.config.min_instances:
                if self._can_scale_down():
                    return ScalingAction.SCALE_DOWN
                    
            return ScalingAction.NO_ACTION
            
        except Exception as e:
            logger.error(f"Error evaluating scaling: {e}")
            return ScalingAction.NO_ACTION
            
    async def _evaluate_rule(self, rule: ScalingRule, current_count: int) -> ScalingAction:
        """评估单个规则"""
        try:
            # 获取指标值
            if rule.trigger == ScalingTrigger.CONNECTION_COUNT:
                metric_value = await self._get_connections_per_instance()
            else:
                metric_value = self.metrics_collector.get_metric_average(
                    rule.metric_name, 
                    self.config.evaluation_interval
                )
                
            if metric_value is None:
                return ScalingAction.NO_ACTION
                
            # 检查阈值
            if metric_value > rule.scale_up_threshold:
                logger.info(f"Rule {rule.name}: {metric_value} > {rule.scale_up_threshold} (scale up)")
                return ScalingAction.SCALE_UP
            elif metric_value < rule.scale_down_threshold:
                logger.info(f"Rule {rule.name}: {metric_value} < {rule.scale_down_threshold} (scale down)")
                return ScalingAction.SCALE_DOWN
                
            return ScalingAction.NO_ACTION
            
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.name}: {e}")
            return ScalingAction.NO_ACTION
            
    async def _get_connections_per_instance(self) -> Optional[float]:
        """获取每个实例的平均连接数"""
        try:
            instances = await self.service_discovery.get_healthy_instances()
            if not instances:
                return None
                
            total_connections = 0
            for instance in instances:
                node_id = f"{instance.host}:{instance.port}"
                if node_id in self.load_balancer.nodes:
                    node = self.load_balancer.nodes[node_id]
                    total_connections += node.current_connections
                    
            return total_connections / len(instances) if instances else 0
            
        except Exception as e:
            logger.error(f"Error getting connections per instance: {e}")
            return None
            
    def _can_scale_up(self) -> bool:
        """检查是否可以扩容"""
        if self.last_scale_up is None:
            return True
            
        elapsed = (datetime.now() - self.last_scale_up).total_seconds()
        return elapsed >= self.config.scale_up_cooldown
        
    def _can_scale_down(self) -> bool:
        """检查是否可以缩容"""
        if self.last_scale_down is None:
            return True
            
        elapsed = (datetime.now() - self.last_scale_down).total_seconds()
        return elapsed >= self.config.scale_down_cooldown
        
    async def scale_up(self, count: int = 1) -> bool:
        """扩容"""
        try:
            logger.info(f"Scaling up by {count} instances")
            
            # 获取当前实例数
            instances = await self.service_discovery.get_healthy_instances()
            old_count = len(instances)
            new_count = old_count + count
            
            # 检查最大实例数限制
            if new_count > self.config.max_instances:
                count = self.config.max_instances - old_count
                new_count = self.config.max_instances
                
            if count <= 0:
                logger.warning("Cannot scale up: already at maximum instances")
                return False
                
            # 调用扩容回调
            success = True
            for callback in self.scale_up_callbacks:
                try:
                    callback(count)
                except Exception as e:
                    logger.error(f"Scale up callback error: {e}")
                    success = False
                    
            # 记录扩展事件
            event = ScalingEvent(
                timestamp=datetime.now(),
                action=ScalingAction.SCALE_UP,
                trigger="auto_scaling",
                reason=f"Scaled up by {count} instances",
                old_count=old_count,
                new_count=new_count,
                success=success
            )
            self.scaling_events.append(event)
            
            if success:
                self.last_scale_up = datetime.now()
                logger.info(f"Successfully scaled up from {old_count} to {new_count} instances")
            else:
                logger.error("Scale up failed")
                
            return success
            
        except Exception as e:
            logger.error(f"Error scaling up: {e}")
            return False
            
    async def scale_down(self, count: int = 1) -> bool:
        """缩容"""
        try:
            logger.info(f"Scaling down by {count} instances")
            
            # 获取当前实例
            instances = await self.service_discovery.get_healthy_instances()
            old_count = len(instances)
            new_count = max(self.config.min_instances, old_count - count)
            actual_count = old_count - new_count
            
            if actual_count <= 0:
                logger.warning("Cannot scale down: already at minimum instances")
                return False
                
            # 选择要移除的实例（选择连接数最少的）
            instances_to_remove = await self._select_instances_to_remove(instances, actual_count)
            
            # 调用缩容回调
            success = True
            for callback in self.scale_down_callbacks:
                try:
                    callback([i.service_id for i in instances_to_remove])
                except Exception as e:
                    logger.error(f"Scale down callback error: {e}")
                    success = False
                    
            # 记录扩展事件
            event = ScalingEvent(
                timestamp=datetime.now(),
                action=ScalingAction.SCALE_DOWN,
                trigger="auto_scaling",
                reason=f"Scaled down by {actual_count} instances",
                old_count=old_count,
                new_count=new_count,
                success=success
            )
            self.scaling_events.append(event)
            
            if success:
                self.last_scale_down = datetime.now()
                logger.info(f"Successfully scaled down from {old_count} to {new_count} instances")
            else:
                logger.error("Scale down failed")
                
            return success
            
        except Exception as e:
            logger.error(f"Error scaling down: {e}")
            return False
            
    async def _select_instances_to_remove(
        self,
        instances: List[ServiceInstance],
        count: int
    ) -> List[ServiceInstance]:
        """选择要移除的实例"""
        # 按连接数排序，选择连接数最少的实例
        instance_loads = []
        
        for instance in instances:
            node_id = f"{instance.host}:{instance.port}"
            connections = 0
            
            if node_id in self.load_balancer.nodes:
                connections = self.load_balancer.nodes[node_id].current_connections
                
            instance_loads.append((instance, connections))
            
        # 按连接数排序
        instance_loads.sort(key=lambda x: x[1])
        
        # 选择前count个实例
        return [instance for instance, _ in instance_loads[:count]]
        
    async def _collect_current_metrics(self, instances: List[ServiceInstance]) -> None:
        """收集当前指标"""
        try:
            total_cpu = 0
            total_memory = 0
            total_connections = 0
            
            for instance in instances:
                node_id = f"{instance.host}:{instance.port}"
                if node_id in self.load_balancer.nodes:
                    node = self.load_balancer.nodes[node_id]
                    total_cpu += node.cpu_usage
                    total_memory += node.memory_usage
                    total_connections += node.current_connections
                    
            if instances:
                avg_cpu = total_cpu / len(instances)
                avg_memory = total_memory / len(instances)
                avg_connections = total_connections / len(instances)
                
                self.metrics_collector.add_metric("cpu_usage", avg_cpu)
                self.metrics_collector.add_metric("memory_usage", avg_memory)
                self.metrics_collector.add_metric("connections_per_instance", avg_connections)
                
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            
    async def _evaluation_loop(self) -> None:
        """扩展评估循环"""
        while self._is_running:
            try:
                await asyncio.sleep(self.config.evaluation_interval)
                
                action = await self.evaluate_scaling()
                
                if action == ScalingAction.SCALE_UP:
                    await self.scale_up()
                elif action == ScalingAction.SCALE_DOWN:
                    await self.scale_down()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in evaluation loop: {e}")
                
    async def _metrics_collection_loop(self) -> None:
        """指标收集循环"""
        while self._is_running:
            try:
                await asyncio.sleep(30)  # 每30秒收集一次指标
                
                instances = await self.service_discovery.get_healthy_instances()
                if instances:
                    await self._collect_current_metrics(instances)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                
    def get_stats(self) -> Dict[str, Any]:
        """获取扩展管理器统计信息"""
        recent_events = [
            {
                "timestamp": event.timestamp.isoformat(),
                "action": event.action,
                "trigger": event.trigger,
                "reason": event.reason,
                "old_count": event.old_count,
                "new_count": event.new_count,
                "success": event.success,
                "error": event.error
            }
            for event in self.scaling_events[-10:]  # 最近10个事件
        ]
        
        return {
            "config": {
                "min_instances": self.config.min_instances,
                "max_instances": self.config.max_instances,
                "target_cpu_utilization": self.config.target_cpu_utilization,
                "target_memory_utilization": self.config.target_memory_utilization,
                "target_connections_per_instance": self.config.target_connections_per_instance
            },
            "scaling_rules": [
                {
                    "name": rule.name,
                    "trigger": rule.trigger,
                    "scale_up_threshold": rule.scale_up_threshold,
                    "scale_down_threshold": rule.scale_down_threshold,
                    "enabled": rule.enabled
                }
                for rule in self.scaling_rules
            ],
            "recent_events": recent_events,
            "last_scale_up": self.last_scale_up.isoformat() if self.last_scale_up else None,
            "last_scale_down": self.last_scale_down.isoformat() if self.last_scale_down else None,
            "metrics": self.metrics_collector.get_all_metrics()
        }