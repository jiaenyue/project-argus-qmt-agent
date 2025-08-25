"""Argus MCP Server - Cache Optimizer.

This module provides automatic cache optimization based on performance analysis.
"""

import time
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from .cache_config import cache_config, DataType, CacheRule
from .cache_analyzer import CachePerformanceAnalyzer, CacheAnalysisResult
from .cache_monitor import cache_monitor

logger = logging.getLogger(__name__)


@dataclass
class OptimizationAction:
    """Cache optimization action."""
    action_type: str
    target: str
    old_value: Any
    new_value: Any
    reason: str
    impact_estimate: str
    timestamp: float


class CacheOptimizer:
    """Automatic cache optimization based on performance analysis."""
    
    def __init__(self, cache_manager, analyzer: CachePerformanceAnalyzer):
        """Initialize cache optimizer.
        
        Args:
            cache_manager: Cache manager instance
            analyzer: Cache performance analyzer
        """
        self.cache_manager = cache_manager
        self.analyzer = analyzer
        
        # Optimization settings
        self.auto_optimize = False
        self.optimization_interval = 3600  # 1 hour
        self.min_efficiency_threshold = 70  # Trigger optimization if efficiency < 70%
        
        # Optimization history
        self._optimization_history: List[OptimizationAction] = []
        self._max_history_size = 100
        
        # Optimization constraints
        self._optimization_constraints = {
            'max_ttl_increase_factor': 2.0,
            'max_ttl_decrease_factor': 0.5,
            'max_memory_increase_mb': 500,
            'min_hit_rate_improvement': 0.05
        }
        
        # Running state
        self._optimization_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        logger.info("Cache optimizer initialized")
    
    async def start_auto_optimization(self):
        """Start automatic cache optimization."""
        if self._is_running:
            logger.warning("Auto optimization already running")
            return
        
        self.auto_optimize = True
        self._is_running = True
        self._optimization_task = asyncio.create_task(self._optimization_loop())
        
        logger.info("Auto cache optimization started")
    
    async def start_optimization_loop(self):
        """Alias for start_auto_optimization for backward compatibility."""
        await self.start_auto_optimization()
    
    async def stop_auto_optimization(self):
        """Stop automatic cache optimization."""
        self.auto_optimize = False
        self._is_running = False
        
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Auto cache optimization stopped")
    
    async def _optimization_loop(self):
        """Main optimization loop."""
        while self.auto_optimize:
            try:
                # Perform analysis
                analysis_result = await self.analyzer.analyze_performance()
                
                # Check if optimization is needed
                if analysis_result.efficiency_score < self.min_efficiency_threshold:
                    logger.info(f"Efficiency score {analysis_result.efficiency_score:.1f}% below threshold, starting optimization")
                    await self.optimize_cache(analysis_result)
                
                # Wait for next optimization cycle
                await asyncio.sleep(self.optimization_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def optimize_cache(self, analysis_result: CacheAnalysisResult) -> List[OptimizationAction]:
        """Optimize cache based on analysis result."""
        logger.info("Starting cache optimization")
        
        actions = []
        
        # Optimize TTL settings
        ttl_actions = await self._optimize_ttl_settings(analysis_result)
        actions.extend(ttl_actions)
        
        # Optimize memory allocation
        memory_actions = await self._optimize_memory_allocation(analysis_result)
        actions.extend(memory_actions)
        
        # Optimize preloading settings
        preload_actions = await self._optimize_preloading(analysis_result)
        actions.extend(preload_actions)
        
        # Optimize cache levels
        level_actions = await self._optimize_cache_levels(analysis_result)
        actions.extend(level_actions)
        
        # Apply optimizations
        for action in actions:
            await self._apply_optimization_action(action)
        
        # Store optimization history
        self._optimization_history.extend(actions)
        if len(self._optimization_history) > self._max_history_size:
            self._optimization_history = self._optimization_history[-self._max_history_size:]
        
        logger.info(f"Cache optimization completed. Applied {len(actions)} optimizations")
        return actions
    
    async def _optimize_ttl_settings(self, analysis_result: CacheAnalysisResult) -> List[OptimizationAction]:
        """Optimize TTL settings based on analysis."""
        actions = []
        
        for data_type, analysis in analysis_result.data_type_analysis.items():
            hit_rate = analysis['hit_rate']
            access_count = analysis['access_count']
            
            # Get current cache rule
            try:
                data_type_enum = DataType(data_type)
                current_rule = cache_config.get_cache_rule(data_type_enum)
                current_ttl = current_rule.ttl
            except (ValueError, AttributeError):
                continue
            
            new_ttl = current_ttl
            reason = ""
            
            # Increase TTL if hit rate is low and access count is high
            if hit_rate < 0.7 and access_count > 100:
                increase_factor = min(1.5, self._optimization_constraints['max_ttl_increase_factor'])
                new_ttl = int(current_ttl * increase_factor)
                reason = f"Low hit rate ({hit_rate:.1%}) with high access count ({access_count})"
            
            # Decrease TTL if data might be stale (very high hit rate with real-time data)
            elif hit_rate > 0.95 and data_type in ['latest_data', 'market_status']:
                decrease_factor = max(0.7, self._optimization_constraints['max_ttl_decrease_factor'])
                new_ttl = int(current_ttl * decrease_factor)
                reason = f"Very high hit rate ({hit_rate:.1%}) for real-time data"
            
            if new_ttl != current_ttl:
                action = OptimizationAction(
                    action_type='ttl_adjustment',
                    target=data_type,
                    old_value=current_ttl,
                    new_value=new_ttl,
                    reason=reason,
                    impact_estimate=f"Expected hit rate improvement: +{self._optimization_constraints['min_hit_rate_improvement']:.1%}",
                    timestamp=time.time()
                )
                actions.append(action)
        
        return actions
    
    async def _optimize_memory_allocation(self, analysis_result: CacheAnalysisResult) -> List[OptimizationAction]:
        """Optimize memory allocation based on analysis."""
        actions = []
        
        overall_perf = analysis_result.overall_performance
        memory_util = overall_perf['memory_utilization']
        hit_rate = overall_perf['hit_rate']
        
        # Increase memory if utilization is high and hit rate is low
        if memory_util > 0.9 and hit_rate < 0.8:
            current_memory = overall_perf.get('memory_usage_mb', 0)
            increase_mb = min(200, self._optimization_constraints['max_memory_increase_mb'])
            new_memory = current_memory + increase_mb
            
            action = OptimizationAction(
                action_type='memory_increase',
                target='cache_manager',
                old_value=f"{current_memory}MB",
                new_value=f"{new_memory}MB",
                reason=f"High memory utilization ({memory_util:.1%}) with low hit rate ({hit_rate:.1%})",
                impact_estimate="Expected to reduce evictions and improve hit rate",
                timestamp=time.time()
            )
            actions.append(action)
        
        return actions
    
    async def _optimize_preloading(self, analysis_result: CacheAnalysisResult) -> List[OptimizationAction]:
        """Optimize preloading settings based on analysis."""
        actions = []
        
        for data_type, analysis in analysis_result.data_type_analysis.items():
            hit_rate = analysis['hit_rate']
            access_count = analysis['access_count']
            
            # Enable preloading for frequently accessed data with low hit rate
            if hit_rate < 0.6 and access_count > 50:
                try:
                    data_type_enum = DataType(data_type)
                    current_rule = cache_config.get_cache_rule(data_type_enum)
                    
                    if not current_rule.preload:
                        action = OptimizationAction(
                            action_type='enable_preloading',
                            target=data_type,
                            old_value=False,
                            new_value=True,
                            reason=f"Low hit rate ({hit_rate:.1%}) with frequent access ({access_count} requests)",
                            impact_estimate="Expected to improve hit rate by preloading data",
                            timestamp=time.time()
                        )
                        actions.append(action)
                except (ValueError, AttributeError):
                    continue
        
        return actions
    
    async def _optimize_cache_levels(self, analysis_result: CacheAnalysisResult) -> List[OptimizationAction]:
        """Optimize cache level assignments based on analysis."""
        actions = []
        
        for data_type, analysis in analysis_result.data_type_analysis.items():
            access_time = analysis['avg_access_time']
            access_count = analysis['access_count']
            
            # Move frequently accessed slow data to higher cache level
            if access_time > 0.05 and access_count > 100:
                try:
                    data_type_enum = DataType(data_type)
                    current_rule = cache_config.get_cache_rule(data_type_enum)
                    current_level = current_rule.level
                    
                    # Promote to higher level if not already at L1
                    if current_level != 'L1':
                        new_level = 'L1' if current_level == 'L2' else 'L2'
                        
                        action = OptimizationAction(
                            action_type='cache_level_promotion',
                            target=data_type,
                            old_value=current_level,
                            new_value=new_level,
                            reason=f"Slow access time ({access_time:.3f}s) with high frequency ({access_count} requests)",
                            impact_estimate="Expected to reduce access time",
                            timestamp=time.time()
                        )
                        actions.append(action)
                except (ValueError, AttributeError):
                    continue
        
        return actions
    
    async def _apply_optimization_action(self, action: OptimizationAction):
        """Apply a single optimization action."""
        try:
            if action.action_type == 'ttl_adjustment':
                await self._apply_ttl_adjustment(action)
            elif action.action_type == 'memory_increase':
                await self._apply_memory_increase(action)
            elif action.action_type == 'enable_preloading':
                await self._apply_preloading_change(action)
            elif action.action_type == 'cache_level_promotion':
                await self._apply_cache_level_change(action)
            
            logger.info(f"Applied optimization: {action.action_type} for {action.target}")
            
        except Exception as e:
            logger.error(f"Failed to apply optimization action {action.action_type}: {e}")
    
    async def _apply_ttl_adjustment(self, action: OptimizationAction):
        """Apply TTL adjustment."""
        data_type_enum = DataType(action.target)
        current_rule = cache_config.get_cache_rule(data_type_enum)
        
        # Create new rule with updated TTL
        new_rule = CacheRule(
            level=current_rule.level,
            ttl=action.new_value,
            max_size=current_rule.max_size,
            preload=current_rule.preload,
            refresh_ahead=current_rule.refresh_ahead
        )
        
        # Update cache configuration
        cache_config._cache_rules[data_type_enum] = new_rule
    
    async def _apply_memory_increase(self, action: OptimizationAction):
        """Apply memory increase."""
        # This would typically involve reconfiguring the cache manager
        # For now, we'll log the action
        logger.info(f"Memory increase recommended: {action.old_value} -> {action.new_value}")
    
    async def _apply_preloading_change(self, action: OptimizationAction):
        """Apply preloading setting change."""
        data_type_enum = DataType(action.target)
        current_rule = cache_config.get_cache_rule(data_type_enum)
        
        # Create new rule with updated preloading
        new_rule = CacheRule(
            level=current_rule.level,
            ttl=current_rule.ttl,
            max_size=current_rule.max_size,
            preload=action.new_value,
            refresh_ahead=current_rule.refresh_ahead
        )
        
        # Update cache configuration
        cache_config._cache_rules[data_type_enum] = new_rule
    
    async def _apply_cache_level_change(self, action: OptimizationAction):
        """Apply cache level change."""
        data_type_enum = DataType(action.target)
        current_rule = cache_config.get_cache_rule(data_type_enum)
        
        # Create new rule with updated level
        new_rule = CacheRule(
            level=action.new_value,
            ttl=current_rule.ttl,
            max_size=current_rule.max_size,
            preload=current_rule.preload,
            refresh_ahead=current_rule.refresh_ahead
        )
        
        # Update cache configuration
        cache_config._cache_rules[data_type_enum] = new_rule
    
    def get_optimization_history(self, limit: int = 20) -> List[OptimizationAction]:
        """Get recent optimization history."""
        return self._optimization_history[-limit:]
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get optimization summary."""
        if not self._optimization_history:
            return {'total_optimizations': 0, 'recent_actions': []}
        
        recent_actions = self._optimization_history[-10:]
        action_types = {}
        
        for action in self._optimization_history:
            action_type = action.action_type
            action_types[action_type] = action_types.get(action_type, 0) + 1
        
        return {
            'total_optimizations': len(self._optimization_history),
            'action_type_breakdown': action_types,
            'recent_actions': [
                {
                    'type': action.action_type,
                    'target': action.target,
                    'timestamp': action.timestamp,
                    'reason': action.reason
                }
                for action in recent_actions
            ],
            'auto_optimize_enabled': self.auto_optimize,
            'optimization_interval': self.optimization_interval
        }
    
    def set_optimization_constraints(self, constraints: Dict[str, Any]):
        """Update optimization constraints."""
        self._optimization_constraints.update(constraints)
        logger.info(f"Updated optimization constraints: {constraints}")
    
    def set_optimization_interval(self, interval: int):
        """Set optimization interval in seconds."""
        self.optimization_interval = interval
        logger.info(f"Set optimization interval to {interval} seconds")
    
    def set_efficiency_threshold(self, threshold: float):
        """Set minimum efficiency threshold for triggering optimization."""
        self.min_efficiency_threshold = threshold
        logger.info(f"Set efficiency threshold to {threshold}%")


# Global cache optimizer instance
_cache_optimizer_instance = None


def get_cache_optimizer(cache_manager):
    """Get or create cache optimizer instance."""
    global _cache_optimizer_instance
    
    if _cache_optimizer_instance is None:
        from .cache_analyzer import CachePerformanceAnalyzer
        analyzer = CachePerformanceAnalyzer(cache_manager)
        _cache_optimizer_instance = CacheOptimizer(cache_manager, analyzer)
    
    return _cache_optimizer_instance