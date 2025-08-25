#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库性能优化模块
实现智能索引策略、查询性能监控和自动优化
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from sqlalchemy import text, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import sqltypes
import threading
import json
from pathlib import Path

from .database_config import get_database_manager
from .database_models import SystemMetrics
from .exception_handler import safe_execute

logger = logging.getLogger(__name__)

@dataclass
class QueryPerformanceMetrics:
    """查询性能指标"""
    query_hash: str
    sql_text: str
    execution_count: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    last_executed: Optional[datetime] = None
    error_count: int = 0
    
    def update(self, duration: float, error: bool = False):
        """更新性能指标"""
        self.execution_count += 1
        self.last_executed = datetime.now()
        
        if error:
            self.error_count += 1
            return
        
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.execution_count
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)

@dataclass
class IndexRecommendation:
    """索引推荐"""
    table_name: str
    columns: List[str]
    index_type: str  # btree, hash, gin, gist
    reason: str
    estimated_benefit: float  # 0-100
    creation_sql: str
    priority: str  # high, medium, low

@dataclass
class SlowQuery:
    """慢查询记录"""
    query_hash: str
    sql_text: str
    duration: float
    timestamp: datetime
    parameters: Optional[Dict[str, Any]] = None
    execution_plan: Optional[str] = None

class QueryAnalyzer:
    """查询分析器"""
    
    def __init__(self):
        self.query_patterns = {
            'select_with_where': r'SELECT.*FROM\s+(\w+).*WHERE\s+([\w\s=<>!]+)',
            'select_with_join': r'SELECT.*FROM\s+(\w+).*JOIN\s+(\w+)',
            'select_with_order': r'SELECT.*FROM\s+(\w+).*ORDER\s+BY\s+([\w,\s]+)',
            'select_with_group': r'SELECT.*FROM\s+(\w+).*GROUP\s+BY\s+([\w,\s]+)',
        }
    
    def analyze_query(self, sql: str) -> Dict[str, Any]:
        """分析查询语句"""
        analysis = {
            'tables': self._extract_tables(sql),
            'columns': self._extract_columns(sql),
            'operations': self._extract_operations(sql),
            'complexity': self._calculate_complexity(sql),
            'optimization_hints': self._get_optimization_hints(sql)
        }
        return analysis
    
    def _extract_tables(self, sql: str) -> List[str]:
        """提取表名"""
        import re
        # 简化的表名提取
        pattern = r'FROM\s+(\w+)|JOIN\s+(\w+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        tables = []
        for match in matches:
            tables.extend([t for t in match if t])
        return list(set(tables))
    
    def _extract_columns(self, sql: str) -> List[str]:
        """提取列名"""
        import re
        # 简化的列名提取
        pattern = r'WHERE\s+([\w.]+)\s*[=<>!]|ORDER\s+BY\s+([\w.,\s]+)|GROUP\s+BY\s+([\w.,\s]+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        columns = []
        for match in matches:
            for col_group in match:
                if col_group:
                    columns.extend([c.strip() for c in col_group.split(',')])
        return list(set(columns))
    
    def _extract_operations(self, sql: str) -> List[str]:
        """提取操作类型"""
        operations = []
        sql_upper = sql.upper()
        
        if 'SELECT' in sql_upper:
            operations.append('SELECT')
        if 'INSERT' in sql_upper:
            operations.append('INSERT')
        if 'UPDATE' in sql_upper:
            operations.append('UPDATE')
        if 'DELETE' in sql_upper:
            operations.append('DELETE')
        if 'JOIN' in sql_upper:
            operations.append('JOIN')
        if 'ORDER BY' in sql_upper:
            operations.append('ORDER_BY')
        if 'GROUP BY' in sql_upper:
            operations.append('GROUP_BY')
        if 'HAVING' in sql_upper:
            operations.append('HAVING')
        
        return operations
    
    def _calculate_complexity(self, sql: str) -> int:
        """计算查询复杂度"""
        complexity = 0
        sql_upper = sql.upper()
        
        # 基础复杂度
        complexity += 1
        
        # JOIN增加复杂度
        complexity += sql_upper.count('JOIN') * 2
        
        # 子查询增加复杂度
        complexity += sql_upper.count('SELECT') - 1
        
        # 聚合函数增加复杂度
        complexity += sql_upper.count('GROUP BY')
        complexity += sql_upper.count('HAVING')
        
        # 排序增加复杂度
        complexity += sql_upper.count('ORDER BY')
        
        return complexity
    
    def _get_optimization_hints(self, sql: str) -> List[str]:
        """获取优化建议"""
        hints = []
        sql_upper = sql.upper()
        
        if 'SELECT *' in sql_upper:
            hints.append('避免使用SELECT *，明确指定需要的列')
        
        if sql_upper.count('JOIN') > 3:
            hints.append('考虑减少JOIN的数量或优化JOIN条件')
        
        if 'ORDER BY' in sql_upper and 'LIMIT' not in sql_upper:
            hints.append('对大结果集排序时考虑添加LIMIT')
        
        if 'WHERE' not in sql_upper and 'SELECT' in sql_upper:
            hints.append('考虑添加WHERE条件以减少扫描的数据量')
        
        return hints

class IndexOptimizer:
    """索引优化器"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.query_analyzer = QueryAnalyzer()
    
    def analyze_missing_indexes(self, query_metrics: Dict[str, QueryPerformanceMetrics]) -> List[IndexRecommendation]:
        """分析缺失的索引"""
        recommendations = []
        
        # 分析慢查询
        slow_queries = [
            metrics for metrics in query_metrics.values()
            if metrics.avg_duration > 1.0  # 超过1秒的查询
        ]
        
        for query_metrics in slow_queries:
            analysis = self.query_analyzer.analyze_query(query_metrics.sql_text)
            
            for table in analysis['tables']:
                # 为WHERE条件推荐索引
                where_columns = self._extract_where_columns(query_metrics.sql_text, table)
                if where_columns:
                    recommendation = IndexRecommendation(
                        table_name=table,
                        columns=where_columns,
                        index_type='btree',
                        reason=f'WHERE条件优化，平均执行时间: {query_metrics.avg_duration:.2f}s',
                        estimated_benefit=min(90, query_metrics.avg_duration * 20),
                        creation_sql=self._generate_index_sql(table, where_columns, 'btree'),
                        priority='high' if query_metrics.avg_duration > 5.0 else 'medium'
                    )
                    recommendations.append(recommendation)
                
                # 为ORDER BY推荐索引
                order_columns = self._extract_order_columns(query_metrics.sql_text, table)
                if order_columns:
                    recommendation = IndexRecommendation(
                        table_name=table,
                        columns=order_columns,
                        index_type='btree',
                        reason=f'ORDER BY优化，平均执行时间: {query_metrics.avg_duration:.2f}s',
                        estimated_benefit=min(80, query_metrics.avg_duration * 15),
                        creation_sql=self._generate_index_sql(table, order_columns, 'btree'),
                        priority='medium'
                    )
                    recommendations.append(recommendation)
        
        # 去重和排序
        unique_recommendations = self._deduplicate_recommendations(recommendations)
        return sorted(unique_recommendations, key=lambda x: x.estimated_benefit, reverse=True)
    
    def _extract_where_columns(self, sql: str, table: str) -> List[str]:
        """提取WHERE条件中的列"""
        import re
        # 简化的WHERE列提取
        pattern = rf'WHERE\s+.*?({table}\.)?([\w]+)\s*[=<>!]'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return [match[1] for match in matches if match[1]]
    
    def _extract_order_columns(self, sql: str, table: str) -> List[str]:
        """提取ORDER BY中的列"""
        import re
        pattern = rf'ORDER\s+BY\s+.*?({table}\.)?([\w]+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return [match[1] for match in matches if match[1]]
    
    def _generate_index_sql(self, table: str, columns: List[str], index_type: str) -> str:
        """生成创建索引的SQL"""
        index_name = f"idx_{table}_{'_'.join(columns)}"
        columns_str = ', '.join(columns)
        
        if index_type == 'btree':
            return f"CREATE INDEX CONCURRENTLY {index_name} ON {table} ({columns_str});"
        elif index_type == 'hash':
            return f"CREATE INDEX CONCURRENTLY {index_name} ON {table} USING HASH ({columns_str});"
        else:
            return f"CREATE INDEX CONCURRENTLY {index_name} ON {table} USING {index_type} ({columns_str});"
    
    def _deduplicate_recommendations(self, recommendations: List[IndexRecommendation]) -> List[IndexRecommendation]:
        """去重索引推荐"""
        seen = set()
        unique_recommendations = []
        
        for rec in recommendations:
            key = (rec.table_name, tuple(sorted(rec.columns)), rec.index_type)
            if key not in seen:
                seen.add(key)
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    def get_existing_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """获取现有索引信息"""
        try:
            with self.db_manager.get_session() as session:
                sql = """
                SELECT 
                    indexname,
                    indexdef,
                    schemaname,
                    tablename
                FROM pg_indexes 
                WHERE tablename = :table_name
                """
                result = session.execute(text(sql), {'table_name': table_name})
                return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"获取索引信息失败: {e}")
            return []
    
    def create_recommended_indexes(self, recommendations: List[IndexRecommendation], 
                                 max_indexes: int = 5) -> Dict[str, Any]:
        """创建推荐的索引"""
        results = {
            'created': [],
            'failed': [],
            'skipped': []
        }
        
        # 按优先级和收益排序
        sorted_recommendations = sorted(
            recommendations[:max_indexes],
            key=lambda x: (x.priority == 'high', x.estimated_benefit),
            reverse=True
        )
        
        for rec in sorted_recommendations:
            try:
                # 检查索引是否已存在
                existing_indexes = self.get_existing_indexes(rec.table_name)
                index_exists = any(
                    all(col in idx['indexdef'].lower() for col in rec.columns)
                    for idx in existing_indexes
                )
                
                if index_exists:
                    results['skipped'].append({
                        'recommendation': asdict(rec),
                        'reason': '索引已存在'
                    })
                    continue
                
                # 创建索引
                with self.db_manager.get_session() as session:
                    session.execute(text(rec.creation_sql))
                    session.commit()
                
                results['created'].append(asdict(rec))
                logger.info(f"成功创建索引: {rec.table_name} - {rec.columns}")
                
            except Exception as e:
                results['failed'].append({
                    'recommendation': asdict(rec),
                    'error': str(e)
                })
                logger.error(f"创建索引失败: {e}")
        
        return results

class DatabasePerformanceOptimizer:
    """数据库性能优化器"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.index_optimizer = IndexOptimizer(self.db_manager)
        self.query_metrics: Dict[str, QueryPerformanceMetrics] = {}
        self.slow_queries: deque = deque(maxlen=1000)
        self.monitoring_enabled = True
        self.slow_query_threshold = 1.0  # 秒
        self._lock = threading.Lock()
        
        # 设置查询监控
        self._setup_query_monitoring()
        
        logger.info("数据库性能优化器已初始化")
    
    def _setup_query_monitoring(self):
        """设置查询监控"""
        @event.listens_for(self.db_manager.engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if self.monitoring_enabled:
                context._query_start_time = time.time()
                context._query_statement = statement
                context._query_parameters = parameters
        
        @event.listens_for(self.db_manager.engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if self.monitoring_enabled and hasattr(context, '_query_start_time'):
                duration = time.time() - context._query_start_time
                self._record_query_performance(statement, duration, parameters)
    
    def _record_query_performance(self, sql: str, duration: float, parameters: Any = None):
        """记录查询性能"""
        try:
            # 生成查询哈希
            query_hash = self._generate_query_hash(sql)
            
            with self._lock:
                if query_hash not in self.query_metrics:
                    self.query_metrics[query_hash] = QueryPerformanceMetrics(
                        query_hash=query_hash,
                        sql_text=sql[:500]  # 限制SQL长度
                    )
                
                self.query_metrics[query_hash].update(duration)
                
                # 记录慢查询
                if duration > self.slow_query_threshold:
                    slow_query = SlowQuery(
                        query_hash=query_hash,
                        sql_text=sql[:500],
                        duration=duration,
                        timestamp=datetime.now(),
                        parameters=str(parameters)[:200] if parameters else None
                    )
                    self.slow_queries.append(slow_query)
                    
                    logger.warning(f"慢查询检测: {duration:.2f}s - {sql[:100]}...")
        
        except Exception as e:
            logger.error(f"记录查询性能错误: {e}")
    
    def _generate_query_hash(self, sql: str) -> str:
        """生成查询哈希"""
        import hashlib
        # 标准化SQL（移除参数值）
        normalized_sql = self._normalize_sql(sql)
        return hashlib.md5(normalized_sql.encode()).hexdigest()[:16]
    
    def _normalize_sql(self, sql: str) -> str:
        """标准化SQL语句"""
        import re
        # 移除多余空格
        sql = re.sub(r'\s+', ' ', sql.strip())
        # 移除参数值（简化处理）
        sql = re.sub(r"'[^']*'", "'?'", sql)
        sql = re.sub(r'\b\d+\b', '?', sql)
        return sql.upper()
    
    @safe_execute
    async def analyze_performance(self) -> Dict[str, Any]:
        """分析数据库性能"""
        analysis = {
            'query_statistics': self._get_query_statistics(),
            'slow_queries': self._get_slow_query_analysis(),
            'index_recommendations': self._get_index_recommendations(),
            'connection_pool_stats': self.db_manager.get_connection_info(),
            'database_stats': await self._get_database_statistics()
        }
        return analysis
    
    def _get_query_statistics(self) -> Dict[str, Any]:
        """获取查询统计信息"""
        with self._lock:
            total_queries = sum(m.execution_count for m in self.query_metrics.values())
            total_duration = sum(m.total_duration for m in self.query_metrics.values())
            
            # 最慢的查询
            slowest_queries = sorted(
                self.query_metrics.values(),
                key=lambda x: x.avg_duration,
                reverse=True
            )[:10]
            
            # 最频繁的查询
            most_frequent_queries = sorted(
                self.query_metrics.values(),
                key=lambda x: x.execution_count,
                reverse=True
            )[:10]
            
            return {
                'total_queries': total_queries,
                'total_duration': total_duration,
                'avg_query_duration': total_duration / total_queries if total_queries > 0 else 0,
                'unique_queries': len(self.query_metrics),
                'slowest_queries': [asdict(q) for q in slowest_queries],
                'most_frequent_queries': [asdict(q) for q in most_frequent_queries]
            }
    
    def _get_slow_query_analysis(self) -> Dict[str, Any]:
        """获取慢查询分析"""
        with self._lock:
            slow_queries_list = list(self.slow_queries)
        
        if not slow_queries_list:
            return {'count': 0, 'queries': []}
        
        # 按持续时间排序
        sorted_slow_queries = sorted(
            slow_queries_list,
            key=lambda x: x.duration,
            reverse=True
        )[:20]
        
        return {
            'count': len(slow_queries_list),
            'threshold': self.slow_query_threshold,
            'queries': [asdict(q) for q in sorted_slow_queries]
        }
    
    def _get_index_recommendations(self) -> List[Dict[str, Any]]:
        """获取索引推荐"""
        recommendations = self.index_optimizer.analyze_missing_indexes(self.query_metrics)
        return [asdict(rec) for rec in recommendations[:10]]
    
    async def _get_database_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            with self.db_manager.get_session() as session:
                # 数据库大小
                db_size_sql = """
                SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                       pg_database_size(current_database()) as size_bytes
                """
                db_size_result = session.execute(text(db_size_sql)).first()
                
                # 表统计
                table_stats_sql = """
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
                LIMIT 10
                """
                table_stats_result = session.execute(text(table_stats_sql)).fetchall()
                
                # 索引统计
                index_stats_sql = """
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read,
                    idx_tup_fetch,
                    idx_scan
                FROM pg_stat_user_indexes
                ORDER BY idx_scan DESC
                LIMIT 10
                """
                index_stats_result = session.execute(text(index_stats_sql)).fetchall()
                
                return {
                    'database_size': {
                        'size': db_size_result[0] if db_size_result else 'Unknown',
                        'size_bytes': db_size_result[1] if db_size_result else 0
                    },
                    'table_statistics': [dict(row) for row in table_stats_result],
                    'index_statistics': [dict(row) for row in index_stats_result]
                }
                
        except Exception as e:
            logger.error(f"获取数据库统计信息错误: {e}")
            return {}
    
    @safe_execute
    async def optimize_database(self, auto_create_indexes: bool = False) -> Dict[str, Any]:
        """优化数据库"""
        optimization_results = {
            'analysis': await self.analyze_performance(),
            'optimizations_applied': [],
            'recommendations': []
        }
        
        # 获取索引推荐
        index_recommendations = self.index_optimizer.analyze_missing_indexes(self.query_metrics)
        
        if auto_create_indexes and index_recommendations:
            # 自动创建高优先级索引
            high_priority_recs = [
                rec for rec in index_recommendations 
                if rec.priority == 'high' and rec.estimated_benefit > 70
            ]
            
            if high_priority_recs:
                index_results = self.index_optimizer.create_recommended_indexes(
                    high_priority_recs, max_indexes=3
                )
                optimization_results['optimizations_applied'].append({
                    'type': 'index_creation',
                    'results': index_results
                })
        
        # 添加其他推荐
        optimization_results['recommendations'] = [
            asdict(rec) for rec in index_recommendations[:10]
        ]
        
        # 数据库维护建议
        maintenance_recommendations = await self._get_maintenance_recommendations()
        optimization_results['recommendations'].extend(maintenance_recommendations)
        
        return optimization_results
    
    async def _get_maintenance_recommendations(self) -> List[Dict[str, Any]]:
        """获取数据库维护建议"""
        recommendations = []
        
        try:
            with self.db_manager.get_session() as session:
                # 检查需要VACUUM的表
                vacuum_sql = """
                SELECT tablename, n_dead_tup, n_live_tup,
                       CASE WHEN n_live_tup > 0 
                            THEN (n_dead_tup::float / n_live_tup::float) * 100 
                            ELSE 0 END as dead_tuple_ratio
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                ORDER BY dead_tuple_ratio DESC
                """
                vacuum_result = session.execute(text(vacuum_sql)).fetchall()
                
                for row in vacuum_result:
                    if row[3] > 20:  # 死元组比例超过20%
                        recommendations.append({
                            'type': 'vacuum',
                            'table': row[0],
                            'reason': f'死元组比例过高: {row[3]:.1f}%',
                            'command': f'VACUUM ANALYZE {row[0]};',
                            'priority': 'high' if row[3] > 50 else 'medium'
                        })
                
                # 检查需要ANALYZE的表
                analyze_sql = """
                SELECT tablename, last_analyze, last_autoanalyze
                FROM pg_stat_user_tables
                WHERE (last_analyze IS NULL OR last_analyze < NOW() - INTERVAL '7 days')
                  AND (last_autoanalyze IS NULL OR last_autoanalyze < NOW() - INTERVAL '7 days')
                """
                analyze_result = session.execute(text(analyze_sql)).fetchall()
                
                for row in analyze_result:
                    recommendations.append({
                        'type': 'analyze',
                        'table': row[0],
                        'reason': '统计信息过期',
                        'command': f'ANALYZE {row[0]};',
                        'priority': 'medium'
                    })
        
        except Exception as e:
            logger.error(f"获取维护建议错误: {e}")
        
        return recommendations
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        with self._lock:
            report = {
                'monitoring_status': {
                    'enabled': self.monitoring_enabled,
                    'slow_query_threshold': self.slow_query_threshold,
                    'queries_monitored': len(self.query_metrics),
                    'slow_queries_detected': len(self.slow_queries)
                },
                'top_issues': self._identify_top_issues(),
                'performance_trends': self._calculate_performance_trends(),
                'recommendations_summary': self._get_recommendations_summary()
            }
        return report
    
    def _identify_top_issues(self) -> List[Dict[str, Any]]:
        """识别主要性能问题"""
        issues = []
        
        # 检查慢查询
        slow_query_count = len(self.slow_queries)
        if slow_query_count > 10:
            issues.append({
                'type': 'slow_queries',
                'severity': 'high' if slow_query_count > 50 else 'medium',
                'description': f'检测到 {slow_query_count} 个慢查询',
                'recommendation': '优化慢查询或添加索引'
            })
        
        # 检查频繁查询
        frequent_queries = [
            m for m in self.query_metrics.values() 
            if m.execution_count > 100 and m.avg_duration > 0.5
        ]
        if frequent_queries:
            issues.append({
                'type': 'frequent_slow_queries',
                'severity': 'high',
                'description': f'{len(frequent_queries)} 个频繁执行的慢查询',
                'recommendation': '优先优化这些查询以获得最大收益'
            })
        
        return issues
    
    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """计算性能趋势"""
        # 简化的趋势计算
        recent_queries = [q for q in self.slow_queries if q.timestamp > datetime.now() - timedelta(hours=1)]
        
        return {
            'recent_slow_queries': len(recent_queries),
            'avg_recent_duration': sum(q.duration for q in recent_queries) / len(recent_queries) if recent_queries else 0,
            'trend': 'improving' if len(recent_queries) < len(self.slow_queries) * 0.1 else 'stable'
        }
    
    def _get_recommendations_summary(self) -> Dict[str, Any]:
        """获取推荐摘要"""
        index_recommendations = self.index_optimizer.analyze_missing_indexes(self.query_metrics)
        
        return {
            'total_index_recommendations': len(index_recommendations),
            'high_priority_indexes': len([r for r in index_recommendations if r.priority == 'high']),
            'estimated_total_benefit': sum(r.estimated_benefit for r in index_recommendations)
        }
    
    def set_monitoring_config(self, enabled: bool = True, slow_query_threshold: float = 1.0):
        """设置监控配置"""
        self.monitoring_enabled = enabled
        self.slow_query_threshold = slow_query_threshold
        logger.info(f"性能监控配置已更新: enabled={enabled}, threshold={slow_query_threshold}s")
    
    def clear_metrics(self):
        """清空性能指标"""
        with self._lock:
            self.query_metrics.clear()
            self.slow_queries.clear()
        logger.info("性能指标已清空")

# 全局性能优化器实例
_performance_optimizer: Optional[DatabasePerformanceOptimizer] = None

def get_database_performance_optimizer() -> DatabasePerformanceOptimizer:
    """获取全局数据库性能优化器实例"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = DatabasePerformanceOptimizer()
    return _performance_optimizer

def cleanup_performance_optimizer():
    """清理性能优化器资源"""
    global _performance_optimizer
    if _performance_optimizer:
        _performance_optimizer.clear_metrics()
        _performance_optimizer = None