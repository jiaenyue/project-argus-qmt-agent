"""Argus MCP Server - Cache Performance Manager.

This module provides unified management of cache performance optimization tools.
"""

import time
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from .cache_config import cache_config, DataType
from .cache_analyzer import CachePerformanceAnalyzer, CacheAnalysisResult
from .cache_optimizer import CacheOptimizer, OptimizationAction
from .cache_performance_test import CachePerformanceTester, PerformanceTestResult
from .cache_monitor import cache_monitor

logger = logging.getLogger(__name__)


@dataclass
class PerformanceReport:
    """Comprehensive cache performance report."""
    timestamp: float
    analysis_result: CacheAnalysisResult
    test_results: List[PerformanceTestResult]
    optimization_actions: List[OptimizationAction]
    performance_summary: Dict[str, Any]
    recommendations: List[str]


class CachePerformanceManager:
    """Unified cache performance management."""
    
    def __init__(self, cache_manager):
        """Initialize cache performance manager.
        
        Args:
            cache_manager: Cache manager instance
        """
        self.cache_manager = cache_manager
        
        # Initialize performance tools
        self.analyzer = CachePerformanceAnalyzer(cache_manager)
        self.optimizer = CacheOptimizer(cache_manager, self.analyzer)
        self.performance_tester = CachePerformanceTester(cache_manager, self.analyzer)
        
        # Performance tracking
        self._performance_history: List[PerformanceReport] = []
        self._max_history_size = 50
        
        # Auto-optimization settings
        self._auto_optimize_enabled = False
        self._optimization_interval = 3600  # 1 hour
        self._performance_check_interval = 300  # 5 minutes
        
        # Running tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        logger.info("Cache performance manager initialized")
    
    async def start_performance_monitoring(self):
        """Start comprehensive performance monitoring."""
        if self._is_running:
            logger.warning("Performance monitoring already running")
            return
        
        self._is_running = True
        
        # Start cache monitor
        cache_monitor.start_monitoring()
        
        # Start auto-optimization if enabled
        if self._auto_optimize_enabled:
            await self.optimizer.start_auto_optimization()
        
        # Start performance monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Performance monitoring started")
    
    async def stop_performance_monitoring(self):
        """Stop performance monitoring."""
        self._is_running = False
        
        # Stop cache monitor
        cache_monitor.stop_monitoring()
        
        # Stop auto-optimization
        await self.optimizer.stop_auto_optimization()
        
        # Stop monitoring task
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Performance monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main performance monitoring loop."""
        while self._is_running:
            try:
                # Perform periodic performance check
                await self._perform_performance_check()
                
                # Wait for next check
                await asyncio.sleep(self._performance_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _perform_performance_check(self):
        """Perform periodic performance check."""
        try:
            # Get current cache statistics
            cache_stats = self.cache_manager.get_stats()
            
            # Check for performance issues
            issues = []
            
            # Check hit rate
            hit_rate = cache_stats.get('hit_rate', 0) / 100
            if hit_rate < 0.7:
                issues.append(f"Low hit rate: {hit_rate:.1%}")
            
            # Check memory utilization
            memory_util = cache_stats.get('memory_utilization', 0) / 100
            if memory_util > 0.9:
                issues.append(f"High memory utilization: {memory_util:.1%}")
            
            # Check eviction rate
            total_requests = cache_stats.get('hits', 0) + cache_stats.get('misses', 0)
            if total_requests > 0:
                eviction_rate = cache_stats.get('evictions', 0) / total_requests
                if eviction_rate > 0.1:
                    issues.append(f"High eviction rate: {eviction_rate:.1%}")
            
            # Log issues if found
            if issues:
                logger.warning(f"Performance issues detected: {', '.join(issues)}")
            
        except Exception as e:
            logger.error(f"Error in performance check: {e}")
    
    async def generate_comprehensive_report(self) -> PerformanceReport:
        """Generate comprehensive performance report."""
        logger.info("Generating comprehensive performance report")
        
        # Perform analysis
        analysis_result = await self.analyzer.analyze_performance()
        
        # Run performance tests
        test_results = []
        basic_test_config = {
            'name': 'comprehensive_test',
            'data_type': DataType.LATEST_DATA,
            'operation_type': 'mixed',
            'duration': 30,
            'concurrent_users': 5
        }
        
        test_result = await self.performance_tester.run_performance_test(basic_test_config)
        test_results.append(test_result)
        
        # Get recent optimization actions
        optimization_actions = self.optimizer.get_optimization_history(10)
        
        # Generate performance summary
        performance_summary = self._generate_performance_summary(
            analysis_result, test_results, optimization_actions
        )
        
        # Compile recommendations
        recommendations = self._compile_recommendations(
            analysis_result, test_results, optimization_actions
        )
        
        # Create report
        report = PerformanceReport(
            timestamp=time.time(),
            analysis_result=analysis_result,
            test_results=test_results,
            optimization_actions=optimization_actions,
            performance_summary=performance_summary,
            recommendations=recommendations
        )
        
        # Store in history
        self._performance_history.append(report)
        if len(self._performance_history) > self._max_history_size:
            self._performance_history.pop(0)
        
        logger.info(f"Comprehensive report generated. Efficiency score: {analysis_result.efficiency_score:.1f}%")
        return report
    
    def _generate_performance_summary(self, analysis_result: CacheAnalysisResult,
                                    test_results: List[PerformanceTestResult],
                                    optimization_actions: List[OptimizationAction]) -> Dict[str, Any]:
        """Generate performance summary."""
        summary = {
            'overall_efficiency': analysis_result.efficiency_score,
            'cache_performance': analysis_result.overall_performance,
            'test_performance': {},
            'optimization_summary': {},
            'trends': analysis_result.performance_trends,
            'status': 'excellent' if analysis_result.efficiency_score >= 90 else
                     'good' if analysis_result.efficiency_score >= 80 else
                     'fair' if analysis_result.efficiency_score >= 70 else 'poor'
        }
        
        # Test performance summary
        if test_results:
            latest_test = test_results[-1]
            summary['test_performance'] = {
                'operations_per_second': latest_test.operations_per_second,
                'hit_rate': latest_test.hit_rate,
                'avg_response_time': latest_test.avg_response_time,
                'success_rate': latest_test.success_rate
            }
        
        # Optimization summary
        if optimization_actions:
            action_types = {}
            for action in optimization_actions:
                action_type = action.action_type
                action_types[action_type] = action_types.get(action_type, 0) + 1
            
            summary['optimization_summary'] = {
                'total_optimizations': len(optimization_actions),
                'action_breakdown': action_types,
                'recent_optimizations': len([a for a in optimization_actions 
                                           if time.time() - a.timestamp < 3600])
            }
        
        return summary
    
    def _compile_recommendations(self, analysis_result: CacheAnalysisResult,
                               test_results: List[PerformanceTestResult],
                               optimization_actions: List[OptimizationAction]) -> List[str]:
        """Compile performance recommendations."""
        recommendations = []
        
        # Add analysis recommendations
        recommendations.extend(analysis_result.optimization_recommendations)
        
        # Add test-based recommendations
        if test_results:
            latest_test = test_results[-1]
            
            if latest_test.hit_rate < 0.8:
                recommendations.append(
                    f"Improve cache hit rate from {latest_test.hit_rate:.1%} by optimizing TTL settings"
                )
            
            if latest_test.avg_response_time > 0.05:
                recommendations.append(
                    f"Reduce average response time from {latest_test.avg_response_time:.3f}s by optimizing cache structure"
                )
            
            if latest_test.success_rate < 0.99:
                recommendations.append(
                    f"Improve success rate from {latest_test.success_rate:.1%} by addressing error conditions"
                )
        
        # Add optimization-based recommendations
        if not optimization_actions:
            recommendations.append("Consider enabling auto-optimization for continuous performance improvement")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    async def optimize_cache_performance(self) -> List[OptimizationAction]:
        """Perform cache optimization."""
        logger.info("Starting cache performance optimization")
        
        # Perform analysis
        analysis_result = await self.analyzer.analyze_performance()
        
        # Perform optimization
        optimization_actions = await self.optimizer.optimize_cache(analysis_result)
        
        logger.info(f"Cache optimization completed. Applied {len(optimization_actions)} optimizations")
        return optimization_actions
    
    async def run_performance_benchmark(self, suite_name: str = 'basic_performance') -> List[PerformanceTestResult]:
        """Run performance benchmark suite."""
        logger.info(f"Running performance benchmark: {suite_name}")
        
        results = await self.performance_tester.run_benchmark_suite(suite_name)
        
        logger.info(f"Benchmark completed: {len(results)} tests")
        return results
    
    async def validate_optimization_effectiveness(self) -> Dict[str, Any]:
        """Validate optimization effectiveness."""
        logger.info("Validating optimization effectiveness")
        
        validation_result = await self.performance_tester.run_optimization_validation(self.optimizer)
        
        logger.info("Optimization validation completed")
        return validation_result
    
    def enable_auto_optimization(self, interval: int = 3600, efficiency_threshold: float = 70):
        """Enable automatic optimization."""
        self._auto_optimize_enabled = True
        self.optimizer.set_optimization_interval(interval)
        self.optimizer.set_efficiency_threshold(efficiency_threshold)
        
        logger.info(f"Auto-optimization enabled. Interval: {interval}s, Threshold: {efficiency_threshold}%")
    
    def disable_auto_optimization(self):
        """Disable automatic optimization."""
        self._auto_optimize_enabled = False
        logger.info("Auto-optimization disabled")
    
    def get_performance_history(self, limit: int = 10) -> List[PerformanceReport]:
        """Get performance history."""
        return self._performance_history[-limit:]
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current performance status."""
        cache_stats = self.cache_manager.get_stats()
        
        return {
            'monitoring_active': self._is_running,
            'auto_optimization_enabled': self._auto_optimize_enabled,
            'cache_stats': cache_stats,
            'optimization_summary': self.optimizer.get_optimization_summary(),
            'available_test_suites': self.performance_tester.get_available_suites(),
            'last_report_time': self._performance_history[-1].timestamp if self._performance_history else None
        }
    
    def export_performance_report(self, report: PerformanceReport) -> str:
        """Export performance report as JSON."""
        export_data = {
            'report_timestamp': report.timestamp,
            'report_date': datetime.fromtimestamp(report.timestamp).isoformat(),
            'efficiency_score': report.analysis_result.efficiency_score,
            'performance_summary': report.performance_summary,
            'analysis_result': {
                'overall_performance': report.analysis_result.overall_performance,
                'data_type_analysis': report.analysis_result.data_type_analysis,
                'bottlenecks': report.analysis_result.bottlenecks
            },
            'test_results': [asdict(result) for result in report.test_results],
            'optimization_actions': [asdict(action) for action in report.optimization_actions],
            'recommendations': report.recommendations
        }
        
        return json.dumps(export_data, indent=2, default=str)
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.stop_performance_monitoring()
        logger.info("Cache performance manager cleanup completed")