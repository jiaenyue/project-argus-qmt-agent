#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库查询优化模块
专门优化xtdata API查询性能和数据访问效率
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from concurrent.futures import ThreadPoolExecutor
import threading
import hashlib
import json

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """查询类型枚举"""
    MARKET_DATA = "market_data"
    KLINE_DATA = "kline_data"
    TRADING_DATES = "trading_dates"
    INSTRUMENT_DETAIL = "instrument_detail"
    SECTOR_STOCKS = "sector_stocks"
    FULL_MARKET_DATA = "full_market_data"

class QueryPriority(Enum):
    """查询优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class QueryRequest:
    """查询请求"""
    query_id: str
    query_type: QueryType
    params: Dict[str, Any]
    priority: QueryPriority = QueryPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable] = None

@dataclass
class QueryResult:
    """查询结果"""
    query_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    cache_hit: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class QueryStats:
    """查询统计信息"""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    cache_hits: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    queries_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recent_queries: deque = field(default_factory=lambda: deque(maxlen=1000))

class QueryBatcher:
    """查询批处理器"""
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 0.1):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_queries: Dict[QueryType, List[QueryRequest]] = defaultdict(list)
        self.batch_lock = threading.Lock()
        self.batch_event = threading.Event()
        self.running = False
        self.batch_thread: Optional[threading.Thread] = None
    
    def add_query(self, query: QueryRequest) -> None:
        """添加查询到批处理队列"""
        with self.batch_lock:
            self.pending_queries[query.query_type].append(query)
            if len(self.pending_queries[query.query_type]) >= self.batch_size:
                self.batch_event.set()
    
    def start(self) -> None:
        """启动批处理器"""
        if not self.running:
            self.running = True
            self.batch_thread = threading.Thread(target=self._batch_processor, daemon=True)
            self.batch_thread.start()
            logger.info("查询批处理器已启动")
    
    def stop(self) -> None:
        """停止批处理器"""
        self.running = False
        self.batch_event.set()
        if self.batch_thread:
            self.batch_thread.join(timeout=5.0)
        logger.info("查询批处理器已停止")
    
    def _batch_processor(self) -> None:
        """批处理器主循环"""
        while self.running:
            try:
                # 等待批处理事件或超时
                self.batch_event.wait(timeout=self.batch_timeout)
                self.batch_event.clear()
                
                # 处理待处理的批次
                self._process_pending_batches()
                
            except Exception as e:
                logger.error(f"批处理器处理错误: {e}")
    
    def _process_pending_batches(self) -> None:
        """处理待处理的批次"""
        with self.batch_lock:
            for query_type, queries in list(self.pending_queries.items()):
                if queries:
                    # 按优先级排序
                    queries.sort(key=lambda q: q.priority.value, reverse=True)
                    
                    # 创建批次
                    batch = queries[:self.batch_size]
                    self.pending_queries[query_type] = queries[self.batch_size:]
                    
                    # 异步处理批次
                    if batch:
                        threading.Thread(
                            target=self._execute_batch,
                            args=(query_type, batch),
                            daemon=True
                        ).start()
    
    def _execute_batch(self, query_type: QueryType, batch: List[QueryRequest]) -> None:
        """执行批次查询"""
        try:
            logger.debug(f"执行批次查询: {query_type.value}, 数量: {len(batch)}")
            
            # 根据查询类型执行相应的批量操作
            if query_type == QueryType.MARKET_DATA:
                self._execute_market_data_batch(batch)
            elif query_type == QueryType.KLINE_DATA:
                self._execute_kline_data_batch(batch)
            elif query_type == QueryType.TRADING_DATES:
                self._execute_trading_dates_batch(batch)
            else:
                # 对于其他类型，逐个执行
                for query in batch:
                    self._execute_single_query(query)
                    
        except Exception as e:
            logger.error(f"批次执行错误: {e}")
            # 标记所有查询为失败
            for query in batch:
                if query.callback:
                    query.callback(QueryResult(
                        query_id=query.query_id,
                        success=False,
                        error=str(e)
                    ))
    
    def _execute_market_data_batch(self, batch: List[QueryRequest]) -> None:
        """执行市场数据批次查询"""
        # 合并所有股票代码
        all_symbols = set()
        for query in batch:
            symbols = query.params.get('symbols', [])
            if isinstance(symbols, str):
                symbols = [symbols]
            all_symbols.update(symbols)
        
        # 执行批量查询
        # 这里需要调用实际的xtdata API
        logger.debug(f"批量查询市场数据: {len(all_symbols)} 个股票")
        
        # 模拟批量查询结果分发
        for query in batch:
            if query.callback:
                query.callback(QueryResult(
                    query_id=query.query_id,
                    success=True,
                    data={"batch_processed": True}
                ))
    
    def _execute_kline_data_batch(self, batch: List[QueryRequest]) -> None:
        """执行K线数据批次查询"""
        # 按时间周期分组
        period_groups = defaultdict(list)
        for query in batch:
            period = query.params.get('period', '1d')
            period_groups[period].append(query)
        
        # 按周期批量查询
        for period, queries in period_groups.items():
            all_symbols = set()
            for query in queries:
                symbols = query.params.get('symbols', [])
                if isinstance(symbols, str):
                    symbols = [symbols]
                all_symbols.update(symbols)
            
            logger.debug(f"批量查询K线数据: {period}, {len(all_symbols)} 个股票")
            
            # 模拟批量查询结果分发
            for query in queries:
                if query.callback:
                    query.callback(QueryResult(
                        query_id=query.query_id,
                        success=True,
                        data={"batch_processed": True, "period": period}
                    ))
    
    def _execute_trading_dates_batch(self, batch: List[QueryRequest]) -> None:
        """执行交易日期批次查询"""
        # 交易日期查询通常可以合并
        logger.debug(f"批量查询交易日期: {len(batch)} 个请求")
        
        # 模拟批量查询结果分发
        for query in batch:
            if query.callback:
                query.callback(QueryResult(
                    query_id=query.query_id,
                    success=True,
                    data={"batch_processed": True}
                ))
    
    def _execute_single_query(self, query: QueryRequest) -> None:
        """执行单个查询"""
        logger.debug(f"执行单个查询: {query.query_type.value}")
        
        if query.callback:
            query.callback(QueryResult(
                query_id=query.query_id,
                success=True,
                data={"single_processed": True}
            ))

class QueryCache:
    """查询缓存"""
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.cache_lock = threading.RLock()
    
    def _generate_cache_key(self, query_type: QueryType, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 创建一个稳定的缓存键
        key_data = {
            'type': query_type.value,
            'params': sorted(params.items()) if params else []
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, query_type: QueryType, params: Dict[str, Any]) -> Optional[Any]:
        """获取缓存数据"""
        cache_key = self._generate_cache_key(query_type, params)
        
        with self.cache_lock:
            if cache_key in self.cache:
                data, timestamp = self.cache[cache_key]
                
                # 检查是否过期
                if datetime.now() - timestamp < timedelta(seconds=self.default_ttl):
                    self.access_times[cache_key] = datetime.now()
                    return data
                else:
                    # 删除过期数据
                    del self.cache[cache_key]
                    if cache_key in self.access_times:
                        del self.access_times[cache_key]
        
        return None
    
    def set(self, query_type: QueryType, params: Dict[str, Any], data: Any, ttl: Optional[int] = None) -> None:
        """设置缓存数据"""
        cache_key = self._generate_cache_key(query_type, params)
        
        with self.cache_lock:
            # 检查缓存大小
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            self.cache[cache_key] = (data, datetime.now())
            self.access_times[cache_key] = datetime.now()
    
    def _evict_lru(self) -> None:
        """驱逐最近最少使用的缓存项"""
        if not self.access_times:
            return
        
        # 找到最久未访问的键
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        
        # 删除缓存项
        if lru_key in self.cache:
            del self.cache[lru_key]
        del self.access_times[lru_key]
    
    def clear(self) -> None:
        """清空缓存"""
        with self.cache_lock:
            self.cache.clear()
            self.access_times.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.cache_lock:
            return {
                'cache_size': len(self.cache),
                'max_size': self.max_size,
                'hit_rate': 0.0,  # 需要在使用时计算
                'oldest_entry': min(self.access_times.values()) if self.access_times else None,
                'newest_entry': max(self.access_times.values()) if self.access_times else None
            }

class DatabaseQueryOptimizer:
    """数据库查询优化器"""
    
    def __init__(self, 
                 connection_pool=None,
                 cache_manager=None,
                 performance_optimizer=None):
        self.connection_pool = connection_pool
        self.cache_manager = cache_manager
        self.performance_optimizer = performance_optimizer
        
        # 初始化组件
        self.query_batcher = QueryBatcher()
        self.query_cache = QueryCache()
        self.stats = QueryStats()
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="query_optimizer")
        
        # 运行状态
        self.running = False
        
        logger.info("数据库查询优化器初始化完成")
    
    async def start(self) -> None:
        """启动查询优化器"""
        if not self.running:
            self.running = True
            self.query_batcher.start()
            logger.info("数据库查询优化器已启动")
    
    async def stop(self) -> None:
        """停止查询优化器"""
        if self.running:
            self.running = False
            self.query_batcher.stop()
            self.executor.shutdown(wait=True)
            logger.info("数据库查询优化器已停止")
    
    async def execute_query(self, 
                          query_type: QueryType,
                          params: Dict[str, Any],
                          priority: QueryPriority = QueryPriority.NORMAL,
                          use_cache: bool = True,
                          timeout: float = 30.0) -> QueryResult:
        """执行优化查询"""
        query_id = self._generate_query_id()
        start_time = time.time()
        
        try:
            # 检查缓存
            if use_cache:
                cached_data = self.query_cache.get(query_type, params)
                if cached_data is not None:
                    self.stats.cache_hits += 1
                    return QueryResult(
                        query_id=query_id,
                        success=True,
                        data=cached_data,
                        execution_time=time.time() - start_time,
                        cache_hit=True
                    )
            
            # 创建查询请求
            query_request = QueryRequest(
                query_id=query_id,
                query_type=query_type,
                params=params,
                priority=priority,
                timeout=timeout
            )
            
            # 创建结果Future
            result_future = asyncio.Future()
            
            def callback(result: QueryResult):
                if not result_future.done():
                    result_future.set_result(result)
            
            query_request.callback = callback
            
            # 添加到批处理器
            self.query_batcher.add_query(query_request)
            
            # 等待结果
            result = await asyncio.wait_for(result_future, timeout=timeout)
            
            # 更新统计
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            self.stats.total_queries += 1
            self.stats.total_execution_time += execution_time
            self.stats.queries_by_type[query_type.value] += 1
            
            if result.success:
                self.stats.successful_queries += 1
                # 缓存成功结果
                if use_cache and result.data is not None:
                    self.query_cache.set(query_type, params, result.data)
            else:
                self.stats.failed_queries += 1
            
            # 更新平均执行时间
            if self.stats.total_queries > 0:
                self.stats.avg_execution_time = self.stats.total_execution_time / self.stats.total_queries
            
            # 记录最近查询
            self.stats.recent_queries.append({
                'query_id': query_id,
                'query_type': query_type.value,
                'execution_time': execution_time,
                'success': result.success,
                'cache_hit': result.cache_hit,
                'timestamp': datetime.now().isoformat()
            })
            
            return result
            
        except asyncio.TimeoutError:
            self.stats.failed_queries += 1
            return QueryResult(
                query_id=query_id,
                success=False,
                error="查询超时",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"查询执行错误: {e}")
            return QueryResult(
                query_id=query_id,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _generate_query_id(self) -> str:
        """生成查询ID"""
        return f"query_{int(time.time() * 1000000)}_{id(threading.current_thread())}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取优化器统计信息"""
        cache_stats = self.query_cache.get_stats()
        
        return {
            'query_stats': {
                'total_queries': self.stats.total_queries,
                'successful_queries': self.stats.successful_queries,
                'failed_queries': self.stats.failed_queries,
                'success_rate': (self.stats.successful_queries / max(self.stats.total_queries, 1)) * 100,
                'cache_hits': self.stats.cache_hits,
                'cache_hit_rate': (self.stats.cache_hits / max(self.stats.total_queries, 1)) * 100,
                'avg_execution_time': self.stats.avg_execution_time,
                'queries_by_type': dict(self.stats.queries_by_type)
            },
            'cache_stats': cache_stats,
            'batch_stats': {
                'pending_queries': {k.value: len(v) for k, v in self.query_batcher.pending_queries.items()},
                'batch_size': self.query_batcher.batch_size,
                'batch_timeout': self.query_batcher.batch_timeout
            },
            'recent_queries': list(self.stats.recent_queries)[-10:],  # 最近10个查询
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_cache(self) -> None:
        """清空查询缓存"""
        self.query_cache.clear()
        logger.info("查询缓存已清空")
    
    def optimize_query_params(self, query_type: QueryType, params: Dict[str, Any]) -> Dict[str, Any]:
        """优化查询参数"""
        optimized_params = params.copy()
        
        # 根据查询类型优化参数
        if query_type == QueryType.MARKET_DATA:
            # 优化市场数据查询参数
            symbols = optimized_params.get('symbols', [])
            if isinstance(symbols, str):
                symbols = [symbols]
            
            # 去重并排序
            optimized_params['symbols'] = sorted(list(set(symbols)))
            
        elif query_type == QueryType.KLINE_DATA:
            # 优化K线数据查询参数
            symbols = optimized_params.get('symbols', [])
            if isinstance(symbols, str):
                symbols = [symbols]
            
            optimized_params['symbols'] = sorted(list(set(symbols)))
            
            # 标准化时间格式
            if 'start_time' in optimized_params:
                start_time = optimized_params['start_time']
                if isinstance(start_time, str) and len(start_time) == 8:
                    # YYYYMMDD格式保持不变
                    pass
            
            if 'end_time' in optimized_params:
                end_time = optimized_params['end_time']
                if isinstance(end_time, str) and len(end_time) == 8:
                    # YYYYMMDD格式保持不变
                    pass
        
        return optimized_params

# 全局查询优化器实例
_global_query_optimizer: Optional[DatabaseQueryOptimizer] = None

def get_global_query_optimizer() -> DatabaseQueryOptimizer:
    """获取全局查询优化器实例"""
    global _global_query_optimizer
    if _global_query_optimizer is None:
        _global_query_optimizer = DatabaseQueryOptimizer()
    return _global_query_optimizer

async def shutdown_global_query_optimizer() -> None:
    """关闭全局查询优化器"""
    global _global_query_optimizer
    if _global_query_optimizer is not None:
        await _global_query_optimizer.stop()
        _global_query_optimizer = None