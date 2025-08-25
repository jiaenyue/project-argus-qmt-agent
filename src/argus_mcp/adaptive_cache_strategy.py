"""自适应缓存策略模块

根据实时性能数据动态调整缓存参数，实现智能化的缓存管理。
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class AdaptationStrategy(Enum):
    """自适应策略类型"""
    CONSERVATIVE = "conservative"  # 保守策略，小幅调整
    AGGRESSIVE = "aggressive"     # 激进策略，大幅调整
    BALANCED = "balanced"         # 平衡策略，中等调整
    CUSTOM = "custom"             # 自定义策略

@dataclass
class AdaptationRule:
    """自适应规则定义"""
    metric_name: str
    threshold_low: float
    threshold_high: float
    adjustment_factor: float
    max_adjustment: float
    cooldown_seconds: int = 300  # 5分钟冷却期
    last_applied: float = 0.0
    
    def can_apply(self) -> bool:
        """检查是否可以应用此规则（冷却期检查）"""
        return time.time() - self.last_applied > self.cooldown_seconds
    
    def mark_applied(self):
        """标记规则已应用"""
        self.last_applied = time.time()

@dataclass
class CacheAdjustment:
    """缓存调整记录"""
    timestamp: float
    parameter: str
    old_value: Any
    new_value: Any
    reason: str
    metric_trigger: str
    effectiveness_score: Optional[float] = None

class AdaptiveCacheStrategy:
    """自适应缓存策略管理器"""
    
    def __init__(self, 
                 strategy: AdaptationStrategy = AdaptationStrategy.BALANCED,
                 monitoring_interval: int = 60,
                 max_adjustments_per_hour: int = 10):
        self.strategy = strategy
        self.monitoring_interval = monitoring_interval
        self.max_adjustments_per_hour = max_adjustments_per_hour
        
        # 自适应规则
        self.adaptation_rules: Dict[str, AdaptationRule] = {}
        self._initialize_default_rules()
        
        # 调整历史
        self.adjustment_history: deque = deque(maxlen=1000)
        self.recent_adjustments: deque = deque(maxlen=100)
        
        # 性能基线
        self.performance_baseline: Dict[str, float] = {}
        self.baseline_window_size = 20
        
        # 监控状态
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            'total_adjustments': 0,
            'successful_adjustments': 0,
            'failed_adjustments': 0,
            'performance_improvements': 0,
            'performance_degradations': 0
        }
        
        logger.info(f"Adaptive cache strategy initialized with {strategy.value} mode")
    
    def _initialize_default_rules(self):
        """初始化默认的自适应规则"""
        strategy_configs = {
            AdaptationStrategy.CONSERVATIVE: {
                'adjustment_factor': 0.05,  # 5%调整
                'max_adjustment': 0.2,      # 最大20%调整
                'cooldown': 600             # 10分钟冷却
            },
            AdaptationStrategy.BALANCED: {
                'adjustment_factor': 0.1,   # 10%调整
                'max_adjustment': 0.3,      # 最大30%调整
                'cooldown': 300             # 5分钟冷却
            },
            AdaptationStrategy.AGGRESSIVE: {
                'adjustment_factor': 0.2,   # 20%调整
                'max_adjustment': 0.5,      # 最大50%调整
                'cooldown': 180             # 3分钟冷却
            }
        }
        
        config = strategy_configs.get(self.strategy, strategy_configs[AdaptationStrategy.BALANCED])
        
        # 命中率规则
        self.adaptation_rules['hit_rate'] = AdaptationRule(
            metric_name='hit_rate',
            threshold_low=0.7,
            threshold_high=0.95,
            adjustment_factor=config['adjustment_factor'],
            max_adjustment=config['max_adjustment'],
            cooldown_seconds=config['cooldown']
        )
        
        # 内存使用规则
        self.adaptation_rules['memory_usage'] = AdaptationRule(
            metric_name='memory_usage',
            threshold_low=0.3,  # 30%内存使用率
            threshold_high=0.8, # 80%内存使用率
            adjustment_factor=config['adjustment_factor'],
            max_adjustment=config['max_adjustment'],
            cooldown_seconds=config['cooldown']
        )
        
        # 访问时间规则
        self.adaptation_rules['access_time'] = AdaptationRule(
            metric_name='access_time',
            threshold_low=0.01,  # 10ms
            threshold_high=0.1,  # 100ms
            adjustment_factor=config['adjustment_factor'],
            max_adjustment=config['max_adjustment'],
            cooldown_seconds=config['cooldown']
        )
        
        # 驱逐率规则
        self.adaptation_rules['eviction_rate'] = AdaptationRule(
            metric_name='eviction_rate',
            threshold_low=1.0,   # 1次/分钟
            threshold_high=10.0, # 10次/分钟
            adjustment_factor=config['adjustment_factor'],
            max_adjustment=config['max_adjustment'],
            cooldown_seconds=config['cooldown']
        )
    
    async def start_monitoring(self, cache_manager):
        """开始自适应监控"""
        if self.is_monitoring:
            logger.warning("Adaptive monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(cache_manager)
        )
        logger.info("Started adaptive cache monitoring")
    
    async def stop_monitoring(self):
        """停止自适应监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped adaptive cache monitoring")
    
    async def _monitoring_loop(self, cache_manager):
        """监控循环"""
        try:
            while self.is_monitoring:
                await self._analyze_and_adapt(cache_manager)
                await asyncio.sleep(self.monitoring_interval)
        except asyncio.CancelledError:
            logger.info("Adaptive monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in adaptive monitoring loop: {e}")
    
    async def _analyze_and_adapt(self, cache_manager):
        """分析性能并执行自适应调整"""
        try:
            # 获取当前性能指标
            current_metrics = await self._get_current_metrics(cache_manager)
            if not current_metrics:
                return
            
            # 更新性能基线
            self._update_performance_baseline(current_metrics)
            
            # 检查是否需要调整
            adjustments = self._evaluate_adjustments(current_metrics)
            
            # 应用调整
            for adjustment in adjustments:
                if self._can_make_adjustment():
                    await self._apply_adjustment(cache_manager, adjustment)
                    self.recent_adjustments.append(adjustment)
                    
            # 评估之前调整的效果
            await self._evaluate_adjustment_effectiveness(cache_manager)
            
        except Exception as e:
            logger.error(f"Error in adaptive analysis: {e}")
    
    async def _get_current_metrics(self, cache_manager) -> Dict[str, float]:
        """获取当前性能指标"""
        try:
            stats = cache_manager.get_stats()
            
            # 确保stats是CacheStats对象
            if hasattr(stats, 'hit_rate'):
                hit_rate = stats.hit_rate
            else:
                hit_rate = stats.get('hit_rate', 0.0) if isinstance(stats, dict) else 0.0
            
            if hasattr(stats, 'memory_usage'):
                memory_usage = stats.memory_usage
            else:
                memory_usage = stats.get('memory_usage', 0) if isinstance(stats, dict) else 0
            
            if hasattr(stats, 'evictions'):
                evictions = stats.evictions
            else:
                evictions = stats.get('evictions', 0) if isinstance(stats, dict) else 0
            
            if hasattr(stats, 'hits') and hasattr(stats, 'misses'):
                total_ops = stats.hits + stats.misses
            else:
                hits = stats.get('hits', 0) if isinstance(stats, dict) else 0
                misses = stats.get('misses', 0) if isinstance(stats, dict) else 0
                total_ops = hits + misses
            
            metrics = {
                'hit_rate': hit_rate,
                'memory_usage_ratio': memory_usage / cache_manager.max_size if cache_manager.max_size > 0 else 0,
                'avg_access_time': 0.01,  # 默认访问时间
                'eviction_rate': evictions / max(total_ops, 1)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {
                'hit_rate': 0.0,
                'memory_usage_ratio': 0.0,
                'avg_access_time': 0.01,
                'eviction_rate': 0.0
            }
    
    def _update_performance_baseline(self, metrics: Dict[str, float]):
        """更新性能基线"""
        for metric_name, value in metrics.items():
            if metric_name not in self.performance_baseline:
                self.performance_baseline[metric_name] = value
            else:
                # 使用指数移动平均更新基线
                alpha = 0.1  # 平滑因子
                self.performance_baseline[metric_name] = (
                    alpha * value + (1 - alpha) * self.performance_baseline[metric_name]
                )
    
    def _evaluate_adjustments(self, metrics: Dict[str, float]) -> List[CacheAdjustment]:
        """评估需要的调整"""
        adjustments = []
        
        for rule_name, rule in self.adaptation_rules.items():
            if not rule.can_apply():
                continue
                
            metric_value = metrics.get(rule.metric_name, 0.0)
            baseline_value = self.performance_baseline.get(rule.metric_name, metric_value)
            
            # 检查是否需要调整
            adjustment = self._check_metric_adjustment(rule, metric_value, baseline_value)
            if adjustment:
                adjustments.append(adjustment)
                rule.mark_applied()
        
        return adjustments
    
    def _check_metric_adjustment(self, rule: AdaptationRule, current_value: float, baseline_value: float) -> Optional[CacheAdjustment]:
        """检查特定指标是否需要调整"""
        if rule.metric_name == 'hit_rate':
            if current_value < rule.threshold_low:
                # 命中率过低，增加缓存大小或TTL
                return self._create_cache_size_adjustment(
                    increase=True,
                    factor=rule.adjustment_factor,
                    reason=f"Low hit rate: {current_value:.2%}",
                    metric_trigger=rule.metric_name
                )
        
        elif rule.metric_name == 'memory_usage':
            if current_value > rule.threshold_high:
                # 内存使用过高，减少缓存大小
                return self._create_cache_size_adjustment(
                    increase=False,
                    factor=rule.adjustment_factor,
                    reason=f"High memory usage: {current_value:.1f}GB",
                    metric_trigger=rule.metric_name
                )
        
        elif rule.metric_name == 'access_time':
            if current_value > rule.threshold_high:
                # 访问时间过长，优化缓存结构
                return self._create_structure_optimization_adjustment(
                    reason=f"Slow access time: {current_value*1000:.1f}ms",
                    metric_trigger=rule.metric_name
                )
        
        elif rule.metric_name == 'eviction_rate':
            if current_value > rule.threshold_high:
                # 驱逐率过高，增加缓存大小
                return self._create_cache_size_adjustment(
                    increase=True,
                    factor=rule.adjustment_factor,
                    reason=f"High eviction rate: {current_value:.1f}/min",
                    metric_trigger=rule.metric_name
                )
        
        return None
    
    def _create_cache_size_adjustment(self, increase: bool, factor: float, reason: str, metric_trigger: str) -> CacheAdjustment:
        """创建缓存大小调整"""
        adjustment_factor = factor if increase else -factor
        return CacheAdjustment(
            timestamp=time.time(),
            parameter='cache_size',
            old_value=None,  # 将在应用时填充
            new_value=None,  # 将在应用时填充
            reason=reason,
            metric_trigger=metric_trigger
        )
    
    def _create_structure_optimization_adjustment(self, reason: str, metric_trigger: str) -> CacheAdjustment:
        """创建结构优化调整"""
        return CacheAdjustment(
            timestamp=time.time(),
            parameter='structure_optimization',
            old_value=None,
            new_value=None,
            reason=reason,
            metric_trigger=metric_trigger
        )
    
    def _can_make_adjustment(self) -> bool:
        """检查是否可以进行调整（频率限制）"""
        current_time = time.time()
        recent_count = sum(
            1 for adj in self.recent_adjustments 
            if current_time - adj.timestamp < 3600  # 最近1小时
        )
        return recent_count < self.max_adjustments_per_hour
    
    async def _apply_adjustment(self, cache_manager, adjustment: CacheAdjustment):
        """应用缓存调整"""
        try:
            if adjustment.parameter == 'cache_size':
                await self._apply_cache_size_adjustment(cache_manager, adjustment)
            elif adjustment.parameter == 'structure_optimization':
                await self._apply_structure_optimization(cache_manager, adjustment)
            
            self.adjustment_history.append(adjustment)
            self.stats['total_adjustments'] += 1
            
            logger.info(f"Applied cache adjustment: {adjustment.parameter} - {adjustment.reason}")
            
        except Exception as e:
            logger.error(f"Error applying adjustment: {e}")
            self.stats['failed_adjustments'] += 1
    
    async def _apply_cache_size_adjustment(self, cache_manager, adjustment: CacheAdjustment):
        """应用缓存大小调整"""
        # 这里需要根据实际的缓存管理器接口来实现
        # 示例实现
        if hasattr(cache_manager, 'config'):
            current_size = getattr(cache_manager.config, 'max_size', 1000)
            adjustment.old_value = current_size
            
            # 根据调整原因确定新大小
            if 'Low hit rate' in adjustment.reason or 'High eviction rate' in adjustment.reason:
                new_size = int(current_size * 1.2)  # 增加20%
            elif 'High memory usage' in adjustment.reason:
                new_size = int(current_size * 0.8)  # 减少20%
            else:
                new_size = current_size
            
            adjustment.new_value = new_size
            
            # 应用新配置（需要根据实际接口调整）
            if hasattr(cache_manager.config, 'update_max_size'):
                cache_manager.config.update_max_size(new_size)
    
    async def _apply_structure_optimization(self, cache_manager, adjustment: CacheAdjustment):
        """应用结构优化"""
        # 触发缓存重组或优化
        if hasattr(cache_manager, 'optimize_structure'):
            await cache_manager.optimize_structure()
        
        adjustment.old_value = "unoptimized"
        adjustment.new_value = "optimized"
    
    async def _evaluate_adjustment_effectiveness(self, cache_manager):
        """评估调整效果"""
        if len(self.recent_adjustments) < 2:
            return
        
        # 获取最近的调整
        recent_adjustment = self.recent_adjustments[-1]
        
        # 检查调整后的性能变化
        if time.time() - recent_adjustment.timestamp > 300:  # 5分钟后评估
            current_metrics = await self._get_current_metrics(cache_manager)
            if current_metrics:
                effectiveness = self._calculate_adjustment_effectiveness(
                    recent_adjustment, current_metrics
                )
                recent_adjustment.effectiveness_score = effectiveness
                
                if effectiveness > 0:
                    self.stats['successful_adjustments'] += 1
                    self.stats['performance_improvements'] += 1
                else:
                    self.stats['performance_degradations'] += 1
    
    def _calculate_adjustment_effectiveness(self, adjustment: CacheAdjustment, current_metrics: Dict[str, float]) -> float:
        """计算调整效果评分"""
        metric_name = adjustment.metric_trigger
        current_value = current_metrics.get(metric_name, 0.0)
        baseline_value = self.performance_baseline.get(metric_name, current_value)
        
        # 根据指标类型计算改善程度
        if metric_name == 'hit_rate':
            # 命中率越高越好
            return (current_value - baseline_value) * 100
        elif metric_name in ['memory_usage', 'access_time', 'eviction_rate']:
            # 这些指标越低越好
            return (baseline_value - current_value) * 100
        
        return 0.0
    
    def get_adaptation_status(self) -> Dict[str, Any]:
        """获取自适应状态"""
        return {
            'is_monitoring': self.is_monitoring,
            'strategy': self.strategy.value,
            'monitoring_interval': self.monitoring_interval,
            'stats': self.stats.copy(),
            'recent_adjustments': [
                {
                    'timestamp': adj.timestamp,
                    'parameter': adj.parameter,
                    'reason': adj.reason,
                    'effectiveness': adj.effectiveness_score
                }
                for adj in list(self.recent_adjustments)[-5:]  # 最近5次调整
            ],
            'performance_baseline': self.performance_baseline.copy(),
            'active_rules': {
                name: {
                    'threshold_low': rule.threshold_low,
                    'threshold_high': rule.threshold_high,
                    'last_applied': rule.last_applied,
                    'can_apply': rule.can_apply()
                }
                for name, rule in self.adaptation_rules.items()
            }
        }
    
    def update_strategy(self, new_strategy: AdaptationStrategy):
        """更新自适应策略"""
        if new_strategy != self.strategy:
            self.strategy = new_strategy
            self._initialize_default_rules()
            logger.info(f"Updated adaptive strategy to {new_strategy.value}")
    
    def add_custom_rule(self, rule: AdaptationRule):
        """添加自定义规则"""
        self.adaptation_rules[rule.metric_name] = rule
        logger.info(f"Added custom adaptation rule for {rule.metric_name}")
    
    def export_adjustment_history(self, filepath: str):
        """导出调整历史"""
        import json
        
        history_data = {
            'strategy': self.strategy.value,
            'stats': self.stats,
            'adjustments': [
                {
                    'timestamp': adj.timestamp,
                    'parameter': adj.parameter,
                    'old_value': adj.old_value,
                    'new_value': adj.new_value,
                    'reason': adj.reason,
                    'metric_trigger': adj.metric_trigger,
                    'effectiveness_score': adj.effectiveness_score
                }
                for adj in self.adjustment_history
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported adjustment history to {filepath}")