"""Argus MCP Server - Cache Performance Analyzer.

This module provides comprehensive cache performance analysis and optimization recommendations.
"""

import time
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import statistics

from .cache_config import cache_config, DataType
from .cache_monitor import cache_monitor

logger = logging.getLogger(__name__)


@dataclass
class CacheAnalysisResult:
    """Cache analysis result."""
    timestamp: float
    overall_performance: Dict[str, Any]
    data_type_analysis: Dict[str, Dict[str, Any]]
    optimization_recommendations: List[str]
    performance_trends: Dict[str, List[float]]
    bottlenecks: List[Dict[str, Any]]
    efficiency_score: float


class CachePerformanceAnalyzer:
    """Analyze cache performance and provide optimization recommendations."""
    
    def __init__(self, cache_manager, analysis_window: int = 3600):
        """Initialize cache performance analyzer.
        
        Args:
            cache_manager: Cache manager instance
            analysis_window: Analysis window in seconds (default: 1 hour)
        """
        self.cache_manager = cache_manager
        self.analysis_window = analysis_window
        
        # Analysis history
        self._analysis_history: List[CacheAnalysisResult] = []
        self._max_history_size = 100
        
        # Performance baselines
        self._performance_baselines = {
            'hit_rate': 0.8,  # Target 80% hit rate
            'avg_access_time': 0.01,  # Target 10ms access time
            'memory_efficiency': 0.85,  # Target 85% memory efficiency
            'eviction_rate': 0.05  # Target <5% eviction rate
        }
        
        logger.info("Cache performance analyzer initialized")
    
    async def analyze_performance(self) -> CacheAnalysisResult:
        """Perform comprehensive cache performance analysis."""
        logger.info("Starting cache performance analysis")
        
        # Get current cache statistics
        cache_stats = self.cache_manager.get_stats()
        
        # Get performance summary from monitor
        performance_summary = cache_monitor.get_performance_summary(self.analysis_window)
        
        # Analyze overall performance
        overall_performance = self._analyze_overall_performance(cache_stats, performance_summary)
        
        # Analyze per-data-type performance
        data_type_analysis = self._analyze_data_type_performance(performance_summary)
        
        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(cache_stats, performance_summary)
        
        # Generate optimization recommendations
        recommendations = self._generate_recommendations(
            overall_performance, data_type_analysis, bottlenecks
        )
        
        # Calculate efficiency score
        efficiency_score = self._calculate_efficiency_score(overall_performance)
        
        # Extract performance trends
        trends = self._extract_performance_trends(performance_summary)
        
        # Create analysis result
        result = CacheAnalysisResult(
            timestamp=time.time(),
            overall_performance=overall_performance,
            data_type_analysis=data_type_analysis,
            optimization_recommendations=recommendations,
            performance_trends=trends,
            bottlenecks=bottlenecks,
            efficiency_score=efficiency_score
        )
        
        # Store in history
        self._analysis_history.append(result)
        if len(self._analysis_history) > self._max_history_size:
            self._analysis_history.pop(0)
        
        logger.info(f"Cache analysis completed. Efficiency score: {efficiency_score:.2f}")
        return result
    
    def _analyze_overall_performance(self, cache_stats: Dict[str, Any], 
                                   performance_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall cache performance."""
        analysis = {
            'hit_rate': cache_stats.get('hit_rate', 0) / 100,
            'memory_utilization': cache_stats.get('memory_utilization', 0) / 100,
            'total_entries': cache_stats.get('total_size', 0),
            'memory_usage_mb': cache_stats.get('memory_usage_mb', 0),
            'eviction_rate': 0,
            'avg_access_time': 0
        }
        
        # Calculate eviction rate
        total_requests = cache_stats.get('hits', 0) + cache_stats.get('misses', 0)
        if total_requests > 0:
            analysis['eviction_rate'] = cache_stats.get('evictions', 0) / total_requests
        
        # Get average access time from performance summary
        if 'recent_performance' in performance_summary:
            recent_perf = performance_summary['recent_performance']
            analysis['avg_access_time'] = recent_perf.get('avg_access_time', 0)
        
        # Performance status
        analysis['status'] = self._get_performance_status(analysis)
        
        return analysis
    
    def _analyze_data_type_performance(self, performance_summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by data type."""
        data_type_analysis = {}
        
        if 'data_type_breakdown' not in performance_summary:
            return data_type_analysis
        
        for data_type, stats in performance_summary['data_type_breakdown'].items():
            analysis = {
                'hit_rate': stats.get('avg_hit_rate', 0),
                'access_count': stats.get('total_requests', 0),
                'avg_access_time': stats.get('avg_access_time', 0),
                'cache_efficiency': 0,
                'recommendations': []
            }
            
            # Calculate cache efficiency
            hit_rate = analysis['hit_rate']
            access_time = analysis['avg_access_time']
            
            # Efficiency based on hit rate and access time
            efficiency = hit_rate * (1 - min(access_time / 0.1, 1.0))
            analysis['cache_efficiency'] = efficiency
            
            # Generate data type specific recommendations
            if hit_rate < 0.6:
                analysis['recommendations'].append("Increase TTL or enable preloading")
            if access_time > 0.05:
                analysis['recommendations'].append("Consider moving to higher cache level")
            if stats.get('total_requests', 0) > 1000 and hit_rate < 0.8:
                analysis['recommendations'].append("High traffic with low hit rate - optimize caching strategy")
            
            data_type_analysis[data_type] = analysis
        
        return data_type_analysis
    
    def _identify_bottlenecks(self, cache_stats: Dict[str, Any], 
                            performance_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks."""
        bottlenecks = []
        
        # Memory bottleneck
        memory_util = cache_stats.get('memory_utilization', 0) / 100
        if memory_util > 0.9:
            bottlenecks.append({
                'type': 'memory',
                'severity': 'high',
                'description': f"High memory utilization ({memory_util:.1%})",
                'impact': 'Frequent evictions, reduced hit rate',
                'solution': 'Increase cache size or optimize data storage'
            })
        
        # Hit rate bottleneck
        hit_rate = cache_stats.get('hit_rate', 0) / 100
        if hit_rate < 0.7:
            bottlenecks.append({
                'type': 'hit_rate',
                'severity': 'medium' if hit_rate > 0.5 else 'high',
                'description': f"Low cache hit rate ({hit_rate:.1%})",
                'impact': 'Increased latency, higher backend load',
                'solution': 'Optimize TTL settings, enable preloading'
            })
        
        # Access time bottleneck
        if 'recent_performance' in performance_summary:
            avg_access_time = performance_summary['recent_performance'].get('avg_access_time', 0)
            if avg_access_time > 0.05:
                bottlenecks.append({
                    'type': 'access_time',
                    'severity': 'medium',
                    'description': f"Slow cache access time ({avg_access_time:.3f}s)",
                    'impact': 'Reduced application performance',
                    'solution': 'Optimize cache structure, reduce lock contention'
                })
        
        # Eviction rate bottleneck
        total_requests = cache_stats.get('hits', 0) + cache_stats.get('misses', 0)
        if total_requests > 0:
            eviction_rate = cache_stats.get('evictions', 0) / total_requests
            if eviction_rate > 0.1:
                bottlenecks.append({
                    'type': 'eviction_rate',
                    'severity': 'medium',
                    'description': f"High eviction rate ({eviction_rate:.1%})",
                    'impact': 'Premature data removal, reduced efficiency',
                    'solution': 'Increase cache size, optimize eviction policy'
                })
        
        return bottlenecks
    
    def _generate_recommendations(self, overall_performance: Dict[str, Any],
                                data_type_analysis: Dict[str, Dict[str, Any]],
                                bottlenecks: List[Dict[str, Any]]) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Overall performance recommendations
        hit_rate = overall_performance['hit_rate']
        memory_util = overall_performance['memory_utilization']
        
        if hit_rate < 0.8:
            recommendations.append(
                f"Improve cache hit rate from {hit_rate:.1%} to >80% by optimizing TTL settings"
            )
        
        if memory_util > 0.85:
            recommendations.append(
                f"Reduce memory utilization from {memory_util:.1%} by increasing cache size or optimizing data storage"
            )
        
        # Data type specific recommendations
        for data_type, analysis in data_type_analysis.items():
            if analysis['cache_efficiency'] < 0.6:
                recommendations.append(
                    f"Optimize caching strategy for {data_type} (efficiency: {analysis['cache_efficiency']:.1%})"
                )
        
        # Bottleneck-based recommendations
        for bottleneck in bottlenecks:
            if bottleneck['severity'] == 'high':
                recommendations.append(f"URGENT: {bottleneck['solution']}")
        
        # Configuration recommendations
        recommendations.extend(self._get_configuration_recommendations())
        
        return recommendations
    
    def _get_configuration_recommendations(self) -> List[str]:
        """Get cache configuration recommendations."""
        recommendations = []
        
        # Analyze current cache configuration
        config_summary = cache_config.get_cache_config_summary()
        
        # Check for suboptimal TTL settings
        for data_type, rule in config_summary['cache_rules'].items():
            ttl = rule['ttl']
            if ttl < 60 and data_type in ['stock_list', 'trading_dates']:
                recommendations.append(
                    f"Increase TTL for {data_type} from {ttl}s to improve cache efficiency"
                )
            elif ttl > 3600 and data_type in ['latest_data', 'market_status']:
                recommendations.append(
                    f"Decrease TTL for {data_type} from {ttl}s to ensure data freshness"
                )
        
        # Check preloading configuration
        preload_enabled = any(rule['preload'] for rule in config_summary['cache_rules'].values())
        if not preload_enabled:
            recommendations.append("Enable preloading for frequently accessed data types")
        
        return recommendations
    
    def _calculate_efficiency_score(self, overall_performance: Dict[str, Any]) -> float:
        """Calculate overall cache efficiency score (0-100)."""
        hit_rate = overall_performance['hit_rate']
        memory_util = overall_performance['memory_utilization']
        eviction_rate = overall_performance['eviction_rate']
        avg_access_time = overall_performance['avg_access_time']
        
        # Weighted scoring
        hit_rate_score = min(hit_rate / 0.9, 1.0) * 40  # 40% weight
        memory_score = (1 - abs(memory_util - 0.8) / 0.2) * 25  # 25% weight, optimal at 80%
        eviction_score = max(0, 1 - eviction_rate / 0.1) * 20  # 20% weight
        access_time_score = max(0, 1 - avg_access_time / 0.1) * 15  # 15% weight
        
        total_score = hit_rate_score + memory_score + eviction_score + access_time_score
        return min(100, max(0, total_score))
    
    def _extract_performance_trends(self, performance_summary: Dict[str, Any]) -> Dict[str, List[float]]:
        """Extract performance trends from summary."""
        trends = {
            'hit_rate': [],
            'memory_usage': [],
            'access_time': []
        }
        
        if 'recent_performance' in performance_summary:
            recent = performance_summary['recent_performance']
            trends['hit_rate'] = [recent.get('avg_hit_rate', 0)]
            trends['memory_usage'] = [recent.get('avg_memory_usage', 0)]
            trends['access_time'] = [recent.get('avg_access_time', 0)]
        
        return trends
    
    def _get_performance_status(self, analysis: Dict[str, Any]) -> str:
        """Get overall performance status."""
        hit_rate = analysis['hit_rate']
        memory_util = analysis['memory_utilization']
        
        if hit_rate >= 0.9 and memory_util < 0.8:
            return 'excellent'
        elif hit_rate >= 0.8 and memory_util < 0.9:
            return 'good'
        elif hit_rate >= 0.6 and memory_util < 0.95:
            return 'fair'
        else:
            return 'poor'
    
    def get_analysis_history(self, limit: int = 10) -> List[CacheAnalysisResult]:
        """Get recent analysis history."""
        return self._analysis_history[-limit:]
    
    def export_analysis_report(self, result: CacheAnalysisResult) -> str:
        """Export analysis result as JSON report."""
        report = {
            'timestamp': result.timestamp,
            'analysis_date': datetime.fromtimestamp(result.timestamp).isoformat(),
            'efficiency_score': result.efficiency_score,
            'overall_performance': result.overall_performance,
            'data_type_analysis': result.data_type_analysis,
            'bottlenecks': result.bottlenecks,
            'recommendations': result.optimization_recommendations,
            'performance_trends': result.performance_trends
        }
        
        return json.dumps(report, indent=2, default=str)