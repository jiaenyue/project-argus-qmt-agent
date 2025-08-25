#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询性能分析器
分析查询性能瓶颈并提供优化建议
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Set
import statistics
import threading
import json

logger = logging.getLogger(__name__)

class PerformanceIssueType(Enum):
    """性能问题类型"""
    SLOW_QUERY = "slow_query"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    FREQUENT_CACHE_MISS = "frequent_cache_miss"
    CONNECTION_TIMEOUT = "connection_timeout"
    BATCH_INEFFICIENCY = "batch_inefficiency"
    RESOURCE_CONTENTION = "resource_contention"

class SeverityLevel(Enum):
    """严重程度"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class PerformanceMetric:
    """性能指标"""
    metric_name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None

@dataclass
class QueryPerformanceData:
    """查询性能数据"""
    query_id: str
    query_type: str
    execution_time: float
    memory_usage: float
    cache_hit: bool
    connection_time: float
    data_size: int
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceIssue:
    """性能问题"""
    issue_id: str
    issue_type: PerformanceIssueType
    severity: SeverityLevel
    description: str
    affected_queries: List[str]
    metrics: List[PerformanceMetric]
    recommendations: List[str]
    first_detected: datetime = field(default_factory=datetime.now)
    last_detected: datetime = field(default_factory=datetime.now)
    occurrence_count: int = 1
    resolved: bool = False

@dataclass
class PerformanceReport:
    """性能报告"""
    report_id: str
    start_time: datetime
    end_time: datetime
    total_queries: int
    avg_execution_time: float
    cache_hit_rate: float
    issues: List[PerformanceIssue]
    recommendations: List[str]
    performance_score: float
    trends: Dict[str, Any]

class QueryPatternAnalyzer:
    """查询模式分析器"""
    
    def __init__(self):
        self.query_patterns: Dict[str, List[QueryPerformanceData]] = defaultdict(list)
        self.pattern_stats: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
    
    def add_query_data(self, data: QueryPerformanceData) -> None:
        """添加查询数据"""
        pattern_key = self._generate_pattern_key(data)
        
        with self.lock:
            self.query_patterns[pattern_key].append(data)
            
            # 保持最近1000个查询记录
            if len(self.query_patterns[pattern_key]) > 1000:
                self.query_patterns[pattern_key] = self.query_patterns[pattern_key][-1000:]
            
            # 更新模式统计
            self._update_pattern_stats(pattern_key)
    
    def _generate_pattern_key(self, data: QueryPerformanceData) -> str:
        """生成查询模式键"""
        # 基于查询类型和主要参数生成模式键
        key_parts = [data.query_type]
        
        # 添加关键参数
        if 'symbols' in data.params:
            symbols = data.params['symbols']
            if isinstance(symbols, list):
                key_parts.append(f"symbols_count_{len(symbols)}")
            else:
                key_parts.append("symbols_single")
        
        if 'period' in data.params:
            key_parts.append(f"period_{data.params['period']}")
        
        if 'start_time' in data.params and 'end_time' in data.params:
            # 计算时间范围
            try:
                start = data.params['start_time']
                end = data.params['end_time']
                if isinstance(start, str) and isinstance(end, str) and len(start) == 8 and len(end) == 8:
                    start_date = datetime.strptime(start, '%Y%m%d')
                    end_date = datetime.strptime(end, '%Y%m%d')
                    days = (end_date - start_date).days
                    if days <= 7:
                        key_parts.append("range_week")
                    elif days <= 30:
                        key_parts.append("range_month")
                    elif days <= 365:
                        key_parts.append("range_year")
                    else:
                        key_parts.append("range_long")
            except:
                key_parts.append("range_unknown")
        
        return "_".join(key_parts)
    
    def _update_pattern_stats(self, pattern_key: str) -> None:
        """更新模式统计"""
        queries = self.query_patterns[pattern_key]
        if not queries:
            return
        
        # 计算统计信息
        execution_times = [q.execution_time for q in queries if q.execution_time > 0]
        memory_usages = [q.memory_usage for q in queries if q.memory_usage > 0]
        cache_hits = [q.cache_hit for q in queries]
        connection_times = [q.connection_time for q in queries if q.connection_time > 0]
        data_sizes = [q.data_size for q in queries if q.data_size > 0]
        
        stats = {
            'total_queries': len(queries),
            'avg_execution_time': statistics.mean(execution_times) if execution_times else 0,
            'median_execution_time': statistics.median(execution_times) if execution_times else 0,
            'max_execution_time': max(execution_times) if execution_times else 0,
            'min_execution_time': min(execution_times) if execution_times else 0,
            'avg_memory_usage': statistics.mean(memory_usages) if memory_usages else 0,
            'cache_hit_rate': sum(cache_hits) / len(cache_hits) if cache_hits else 0,
            'avg_connection_time': statistics.mean(connection_times) if connection_times else 0,
            'avg_data_size': statistics.mean(data_sizes) if data_sizes else 0,
            'error_rate': sum(1 for q in queries if q.error) / len(queries),
            'last_updated': datetime.now()
        }
        
        # 计算趋势
        if len(execution_times) >= 10:
            recent_times = execution_times[-10:]
            older_times = execution_times[-20:-10] if len(execution_times) >= 20 else execution_times[:-10]
            
            if older_times:
                recent_avg = statistics.mean(recent_times)
                older_avg = statistics.mean(older_times)
                trend = (recent_avg - older_avg) / older_avg * 100
                stats['performance_trend'] = trend
        
        self.pattern_stats[pattern_key] = stats
    
    def get_pattern_stats(self, pattern_key: str = None) -> Dict[str, Any]:
        """获取模式统计"""
        with self.lock:
            if pattern_key:
                return self.pattern_stats.get(pattern_key, {})
            return dict(self.pattern_stats)
    
    def get_slow_patterns(self, threshold: float = 5.0) -> List[Tuple[str, Dict[str, Any]]]:
        """获取慢查询模式"""
        with self.lock:
            slow_patterns = []
            for pattern_key, stats in self.pattern_stats.items():
                if stats.get('avg_execution_time', 0) > threshold:
                    slow_patterns.append((pattern_key, stats))
            
            # 按平均执行时间排序
            slow_patterns.sort(key=lambda x: x[1].get('avg_execution_time', 0), reverse=True)
            return slow_patterns

class PerformanceThresholdManager:
    """性能阈值管理器"""
    
    def __init__(self):
        self.thresholds = {
            'execution_time_warning': 3.0,  # 秒
            'execution_time_critical': 10.0,  # 秒
            'memory_usage_warning': 100.0,  # MB
            'memory_usage_critical': 500.0,  # MB
            'cache_hit_rate_warning': 0.7,  # 70%
            'cache_hit_rate_critical': 0.5,  # 50%
            'connection_time_warning': 1.0,  # 秒
            'connection_time_critical': 5.0,  # 秒
            'error_rate_warning': 0.05,  # 5%
            'error_rate_critical': 0.1,  # 10%
        }
    
    def check_thresholds(self, metric_name: str, value: float) -> Optional[SeverityLevel]:
        """检查阈值"""
        warning_key = f"{metric_name}_warning"
        critical_key = f"{metric_name}_critical"
        
        if critical_key in self.thresholds and value >= self.thresholds[critical_key]:
            return SeverityLevel.CRITICAL
        elif warning_key in self.thresholds and value >= self.thresholds[warning_key]:
            return SeverityLevel.HIGH
        
        return None
    
    def update_threshold(self, metric_name: str, level: str, value: float) -> None:
        """更新阈值"""
        key = f"{metric_name}_{level}"
        if key in self.thresholds:
            self.thresholds[key] = value
    
    def get_thresholds(self) -> Dict[str, float]:
        """获取所有阈值"""
        return dict(self.thresholds)

class QueryPerformanceAnalyzer:
    """查询性能分析器"""
    
    def __init__(self):
        self.pattern_analyzer = QueryPatternAnalyzer()
        self.threshold_manager = PerformanceThresholdManager()
        self.performance_data: deque = deque(maxlen=10000)
        self.issues: Dict[str, PerformanceIssue] = {}
        self.reports: List[PerformanceReport] = []
        self.lock = threading.RLock()
        
        # 统计信息
        self.total_queries = 0
        self.total_execution_time = 0.0
        self.cache_hits = 0
        self.errors = 0
        
        logger.info("查询性能分析器初始化完成")
    
    def record_query_performance(self, 
                               query_id: str,
                               query_type: str,
                               execution_time: float,
                               memory_usage: float = 0.0,
                               cache_hit: bool = False,
                               connection_time: float = 0.0,
                               data_size: int = 0,
                               error: Optional[str] = None,
                               params: Dict[str, Any] = None) -> None:
        """记录查询性能数据"""
        
        data = QueryPerformanceData(
            query_id=query_id,
            query_type=query_type,
            execution_time=execution_time,
            memory_usage=memory_usage,
            cache_hit=cache_hit,
            connection_time=connection_time,
            data_size=data_size,
            error=error,
            params=params or {}
        )
        
        with self.lock:
            self.performance_data.append(data)
            self.pattern_analyzer.add_query_data(data)
            
            # 更新统计
            self.total_queries += 1
            self.total_execution_time += execution_time
            if cache_hit:
                self.cache_hits += 1
            if error:
                self.errors += 1
            
            # 检查性能问题
            self._check_performance_issues(data)
    
    def _check_performance_issues(self, data: QueryPerformanceData) -> None:
        """检查性能问题"""
        issues_found = []
        
        # 检查执行时间
        severity = self.threshold_manager.check_thresholds('execution_time', data.execution_time)
        if severity:
            issues_found.append({
                'type': PerformanceIssueType.SLOW_QUERY,
                'severity': severity,
                'description': f"查询执行时间过长: {data.execution_time:.2f}秒",
                'metrics': [PerformanceMetric('execution_time', data.execution_time, 'seconds')]
            })
        
        # 检查内存使用
        if data.memory_usage > 0:
            severity = self.threshold_manager.check_thresholds('memory_usage', data.memory_usage)
            if severity:
                issues_found.append({
                    'type': PerformanceIssueType.HIGH_MEMORY_USAGE,
                    'severity': severity,
                    'description': f"内存使用过高: {data.memory_usage:.2f}MB",
                    'metrics': [PerformanceMetric('memory_usage', data.memory_usage, 'MB')]
                })
        
        # 检查连接时间
        if data.connection_time > 0:
            severity = self.threshold_manager.check_thresholds('connection_time', data.connection_time)
            if severity:
                issues_found.append({
                    'type': PerformanceIssueType.CONNECTION_TIMEOUT,
                    'severity': severity,
                    'description': f"连接时间过长: {data.connection_time:.2f}秒",
                    'metrics': [PerformanceMetric('connection_time', data.connection_time, 'seconds')]
                })
        
        # 创建或更新问题记录
        for issue_data in issues_found:
            self._create_or_update_issue(data, issue_data)
    
    def _create_or_update_issue(self, data: QueryPerformanceData, issue_data: Dict[str, Any]) -> None:
        """创建或更新问题记录"""
        issue_key = f"{issue_data['type'].value}_{data.query_type}"
        
        if issue_key in self.issues:
            # 更新现有问题
            issue = self.issues[issue_key]
            issue.last_detected = datetime.now()
            issue.occurrence_count += 1
            issue.affected_queries.append(data.query_id)
            issue.metrics.extend(issue_data['metrics'])
            
            # 保持最近100个受影响的查询
            if len(issue.affected_queries) > 100:
                issue.affected_queries = issue.affected_queries[-100:]
            
            # 保持最近100个指标
            if len(issue.metrics) > 100:
                issue.metrics = issue.metrics[-100:]
        else:
            # 创建新问题
            issue = PerformanceIssue(
                issue_id=f"issue_{int(time.time() * 1000000)}",
                issue_type=issue_data['type'],
                severity=issue_data['severity'],
                description=issue_data['description'],
                affected_queries=[data.query_id],
                metrics=issue_data['metrics'],
                recommendations=self._generate_recommendations(issue_data['type'], data)
            )
            self.issues[issue_key] = issue
    
    def _generate_recommendations(self, issue_type: PerformanceIssueType, data: QueryPerformanceData) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if issue_type == PerformanceIssueType.SLOW_QUERY:
            recommendations.extend([
                "考虑使用缓存减少重复查询",
                "优化查询参数，减少数据量",
                "使用批量查询合并多个请求",
                "检查网络连接质量"
            ])
            
            # 基于查询类型的具体建议
            if data.query_type == "kline_data":
                recommendations.extend([
                    "减少K线数据的时间范围",
                    "使用较大的时间周期（如日线而非分钟线）",
                    "分批获取历史数据"
                ])
            elif data.query_type == "market_data":
                recommendations.extend([
                    "减少同时查询的股票数量",
                    "使用股票分组查询",
                    "优先查询活跃股票"
                ])
        
        elif issue_type == PerformanceIssueType.HIGH_MEMORY_USAGE:
            recommendations.extend([
                "减少单次查询的数据量",
                "使用数据流处理而非一次性加载",
                "及时释放不需要的数据",
                "考虑数据压缩"
            ])
        
        elif issue_type == PerformanceIssueType.CONNECTION_TIMEOUT:
            recommendations.extend([
                "检查网络连接稳定性",
                "增加连接超时时间",
                "使用连接池管理连接",
                "实现连接重试机制"
            ])
        
        elif issue_type == PerformanceIssueType.FREQUENT_CACHE_MISS:
            recommendations.extend([
                "优化缓存策略",
                "增加缓存容量",
                "调整缓存过期时间",
                "预热常用数据"
            ])
        
        return recommendations
    
    def generate_performance_report(self, 
                                  start_time: Optional[datetime] = None,
                                  end_time: Optional[datetime] = None) -> PerformanceReport:
        """生成性能报告"""
        if not start_time:
            start_time = datetime.now() - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now()
        
        with self.lock:
            # 过滤时间范围内的数据
            filtered_data = [
                data for data in self.performance_data
                if start_time <= data.timestamp <= end_time
            ]
            
            if not filtered_data:
                return PerformanceReport(
                    report_id=f"report_{int(time.time() * 1000000)}",
                    start_time=start_time,
                    end_time=end_time,
                    total_queries=0,
                    avg_execution_time=0.0,
                    cache_hit_rate=0.0,
                    issues=[],
                    recommendations=[],
                    performance_score=100.0,
                    trends={}
                )
            
            # 计算统计信息
            total_queries = len(filtered_data)
            execution_times = [d.execution_time for d in filtered_data]
            avg_execution_time = statistics.mean(execution_times)
            cache_hits = sum(1 for d in filtered_data if d.cache_hit)
            cache_hit_rate = cache_hits / total_queries
            errors = sum(1 for d in filtered_data if d.error)
            error_rate = errors / total_queries
            
            # 获取相关问题
            relevant_issues = [
                issue for issue in self.issues.values()
                if start_time <= issue.last_detected <= end_time
            ]
            
            # 计算性能分数
            performance_score = self._calculate_performance_score(
                avg_execution_time, cache_hit_rate, error_rate, len(relevant_issues)
            )
            
            # 生成总体建议
            recommendations = self._generate_overall_recommendations(
                avg_execution_time, cache_hit_rate, error_rate, relevant_issues
            )
            
            # 计算趋势
            trends = self._calculate_trends(filtered_data)
            
            report = PerformanceReport(
                report_id=f"report_{int(time.time() * 1000000)}",
                start_time=start_time,
                end_time=end_time,
                total_queries=total_queries,
                avg_execution_time=avg_execution_time,
                cache_hit_rate=cache_hit_rate,
                issues=relevant_issues,
                recommendations=recommendations,
                performance_score=performance_score,
                trends=trends
            )
            
            self.reports.append(report)
            
            # 保持最近50个报告
            if len(self.reports) > 50:
                self.reports = self.reports[-50:]
            
            return report
    
    def _calculate_performance_score(self, 
                                   avg_execution_time: float,
                                   cache_hit_rate: float,
                                   error_rate: float,
                                   issue_count: int) -> float:
        """计算性能分数（0-100）"""
        score = 100.0
        
        # 执行时间影响（最多扣30分）
        if avg_execution_time > 10:
            score -= 30
        elif avg_execution_time > 5:
            score -= 20
        elif avg_execution_time > 3:
            score -= 10
        elif avg_execution_time > 1:
            score -= 5
        
        # 缓存命中率影响（最多扣25分）
        if cache_hit_rate < 0.3:
            score -= 25
        elif cache_hit_rate < 0.5:
            score -= 15
        elif cache_hit_rate < 0.7:
            score -= 10
        elif cache_hit_rate < 0.8:
            score -= 5
        
        # 错误率影响（最多扣25分）
        if error_rate > 0.1:
            score -= 25
        elif error_rate > 0.05:
            score -= 15
        elif error_rate > 0.02:
            score -= 10
        elif error_rate > 0.01:
            score -= 5
        
        # 问题数量影响（最多扣20分）
        if issue_count > 10:
            score -= 20
        elif issue_count > 5:
            score -= 15
        elif issue_count > 2:
            score -= 10
        elif issue_count > 0:
            score -= 5
        
        return max(0.0, score)
    
    def _generate_overall_recommendations(self, 
                                        avg_execution_time: float,
                                        cache_hit_rate: float,
                                        error_rate: float,
                                        issues: List[PerformanceIssue]) -> List[str]:
        """生成总体优化建议"""
        recommendations = []
        
        if avg_execution_time > 5:
            recommendations.append("整体查询性能较差，建议优化查询策略")
        
        if cache_hit_rate < 0.7:
            recommendations.append("缓存命中率偏低，建议优化缓存策略")
        
        if error_rate > 0.05:
            recommendations.append("错误率较高，建议检查连接稳定性和错误处理")
        
        # 基于问题类型的建议
        issue_types = set(issue.issue_type for issue in issues)
        
        if PerformanceIssueType.SLOW_QUERY in issue_types:
            recommendations.append("存在慢查询问题，建议优化查询参数和使用缓存")
        
        if PerformanceIssueType.HIGH_MEMORY_USAGE in issue_types:
            recommendations.append("内存使用过高，建议优化数据处理方式")
        
        if PerformanceIssueType.CONNECTION_TIMEOUT in issue_types:
            recommendations.append("连接超时问题，建议检查网络和连接配置")
        
        return recommendations
    
    def _calculate_trends(self, data: List[QueryPerformanceData]) -> Dict[str, Any]:
        """计算性能趋势"""
        if len(data) < 10:
            return {}
        
        # 按时间排序
        sorted_data = sorted(data, key=lambda x: x.timestamp)
        
        # 计算时间段
        total_time = (sorted_data[-1].timestamp - sorted_data[0].timestamp).total_seconds()
        if total_time <= 0:
            return {}
        
        # 分成两半计算趋势
        mid_point = len(sorted_data) // 2
        first_half = sorted_data[:mid_point]
        second_half = sorted_data[mid_point:]
        
        # 计算执行时间趋势
        first_avg_time = statistics.mean(d.execution_time for d in first_half)
        second_avg_time = statistics.mean(d.execution_time for d in second_half)
        time_trend = (second_avg_time - first_avg_time) / first_avg_time * 100 if first_avg_time > 0 else 0
        
        # 计算缓存命中率趋势
        first_cache_rate = sum(1 for d in first_half if d.cache_hit) / len(first_half)
        second_cache_rate = sum(1 for d in second_half if d.cache_hit) / len(second_half)
        cache_trend = (second_cache_rate - first_cache_rate) * 100
        
        # 计算错误率趋势
        first_error_rate = sum(1 for d in first_half if d.error) / len(first_half)
        second_error_rate = sum(1 for d in second_half if d.error) / len(second_half)
        error_trend = (second_error_rate - first_error_rate) * 100
        
        return {
            'execution_time_trend': time_trend,
            'cache_hit_rate_trend': cache_trend,
            'error_rate_trend': error_trend,
            'trend_period_seconds': total_time
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取分析器统计信息"""
        with self.lock:
            avg_execution_time = self.total_execution_time / max(self.total_queries, 1)
            cache_hit_rate = self.cache_hits / max(self.total_queries, 1)
            error_rate = self.errors / max(self.total_queries, 1)
            
            return {
                'total_queries': self.total_queries,
                'avg_execution_time': avg_execution_time,
                'cache_hit_rate': cache_hit_rate,
                'error_rate': error_rate,
                'active_issues': len([i for i in self.issues.values() if not i.resolved]),
                'resolved_issues': len([i for i in self.issues.values() if i.resolved]),
                'pattern_count': len(self.pattern_analyzer.pattern_stats),
                'recent_reports': len(self.reports),
                'thresholds': self.threshold_manager.get_thresholds()
            }
    
    def get_issues(self, resolved: Optional[bool] = None) -> List[PerformanceIssue]:
        """获取性能问题列表"""
        with self.lock:
            issues = list(self.issues.values())
            
            if resolved is not None:
                issues = [i for i in issues if i.resolved == resolved]
            
            # 按严重程度和最后检测时间排序
            issues.sort(key=lambda x: (x.severity.value, x.last_detected), reverse=True)
            
            return issues
    
    def resolve_issue(self, issue_id: str) -> bool:
        """解决性能问题"""
        with self.lock:
            for issue in self.issues.values():
                if issue.issue_id == issue_id:
                    issue.resolved = True
                    return True
            return False
    
    def get_slow_query_patterns(self, threshold: float = 5.0) -> List[Tuple[str, Dict[str, Any]]]:
        """获取慢查询模式"""
        return self.pattern_analyzer.get_slow_patterns(threshold)
    
    def clear_data(self, older_than: Optional[datetime] = None) -> None:
        """清理旧数据"""
        if not older_than:
            older_than = datetime.now() - timedelta(days=7)
        
        with self.lock:
            # 清理性能数据
            self.performance_data = deque(
                (data for data in self.performance_data if data.timestamp > older_than),
                maxlen=10000
            )
            
            # 清理已解决的旧问题
            issues_to_remove = []
            for key, issue in self.issues.items():
                if issue.resolved and issue.last_detected < older_than:
                    issues_to_remove.append(key)
            
            for key in issues_to_remove:
                del self.issues[key]
            
            # 清理旧报告
            self.reports = [r for r in self.reports if r.end_time > older_than]
            
            logger.info(f"清理了 {older_than} 之前的性能数据")

# 全局性能分析器实例
_global_performance_analyzer: Optional[QueryPerformanceAnalyzer] = None

def get_global_performance_analyzer() -> QueryPerformanceAnalyzer:
    """获取全局性能分析器实例"""
    global _global_performance_analyzer
    if _global_performance_analyzer is None:
        _global_performance_analyzer = QueryPerformanceAnalyzer()
    return _global_performance_analyzer

def shutdown_global_performance_analyzer() -> None:
    """关闭全局性能分析器"""
    global _global_performance_analyzer
    if _global_performance_analyzer is not None:
        _global_performance_analyzer.clear_data()
        _global_performance_analyzer = None