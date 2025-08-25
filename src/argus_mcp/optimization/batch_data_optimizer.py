"""
批量数据获取优化器

提供批量数据获取的并发控制和性能优化功能
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from collections import defaultdict
import heapq

from src.argus_mcp.monitoring.historical_performance_monitor import get_historical_performance_monitor
from src.argus_mcp.cache.intelligent_cache_strategy import get_intelligent_cache_strategy
from src.argus_mcp.exceptions.historical_data_exceptions import HistoricalDataException, ErrorCategory

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """批量请求项"""
    symbol: str
    period: str
    start_date: str
    end_date: str
    priority: int = 1  # 优先级，数字越大优先级越高
    callback: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        return self.priority > other.priority  # 优先级队列，高优先级先执行


@dataclass
class BatchResult:
    """批量请求结果"""
    request: BatchRequest
    success: bool
    data: Any = None
    error: Optional[str] = None
    response_time: float = 0.0
    cache_hit: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BatchOptimizationConfig:
    """批量优化配置"""
    max_concurrent_requests: int = 10
    max_batch_size: int = 100
    request_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    enable_request_grouping: bool = True
    enable_priority_queue: bool = True
    enable_adaptive_concurrency: bool = True
    min_concurrency: int = 2
    max_concurrency: int = 20
    performance_window_size: int = 100


class BatchDataOptimizer:
    """批量数据优化器"""
    
    def __init__(self, config: Optional[BatchOptimizationConfig] = None):
        self.config = config or BatchOptimizationConfig()
        self.monitor = get_historical_performance_monitor()
        self.cache_strategy = get_intelligent_cache_strategy()
        
        # 请求队列
        self.request_queue = asyncio.PriorityQueue()
        self.processing_requests: Dict[str, BatchRequest] = {}
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        self.current_concurrency = self.config.max_concurrent_requests
        
        # 性能统计
        self.performance_history = []
        self.last_performance_check = time.time()
        
        # 请求分组
        self.request_groups: Dict[str, List[BatchRequest]] = defaultdict(list)
        
        # 状态跟踪
        self.is_processing = False
        self.total_processed = 0
        self.total_successful = 0
        self.total_failed = 0
        
        logger.info("Batch data optimizer initialized")
    
    async def add_batch_request(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        priority: int = 1,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """添加批量请求"""
        request = BatchRequest(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            priority=priority,
            callback=callback,
            metadata=metadata or {}
        )
        
        request_id = f"{symbol}_{period}_{start_date}_{end_date}_{int(time.time())}"
        request.metadata['request_id'] = request_id
        
        await self.request_queue.put((priority, time.time(), request))
        
        logger.debug(f"Added batch request: {request_id}")
        return request_id
    
    async def add_batch_requests(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[str]:
        """批量添加请求"""
        request_ids = []
        
        for req_data in requests:
            request_id = await self.add_batch_request(
                symbol=req_data['symbol'],
                period=req_data['period'],
                start_date=req_data['start_date'],
                end_date=req_data['end_date'],
                priority=req_data.get('priority', 1),
                callback=req_data.get('callback'),
                metadata=req_data.get('metadata')
            )
            request_ids.append(request_id)
        
        return request_ids
    
    async def process_batch_requests(
        self,
        max_requests: Optional[int] = None
    ) -> List[BatchResult]:
        """处理批量请求"""
        if self.is_processing:
            logger.warning("Batch processing already in progress")
            return []
        
        self.is_processing = True
        results = []
        
        try:
            processed_count = 0
            max_to_process = max_requests or self.config.max_batch_size
            
            # 收集请求
            requests_to_process = []
            while (not self.request_queue.empty() and 
                   len(requests_to_process) < max_to_process):
                
                try:
                    _, _, request = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=0.1
                    )
                    requests_to_process.append(request)
                except asyncio.TimeoutError:
                    break
            
            if not requests_to_process:
                return results
            
            logger.info(f"Processing {len(requests_to_process)} batch requests")
            
            # 请求分组优化
            if self.config.enable_request_grouping:
                requests_to_process = self._optimize_request_order(requests_to_process)
            
            # 自适应并发控制
            if self.config.enable_adaptive_concurrency:
                await self._adjust_concurrency()
            
            # 并发处理请求
            tasks = []
            for request in requests_to_process:
                task = self._process_single_request(request)
                tasks.append(task)
            
            # 限制并发数
            semaphore = asyncio.Semaphore(self.current_concurrency)
            
            async def limited_task(task):
                async with semaphore:
                    return await task
            
            # 执行所有任务
            batch_results = await asyncio.gather(
                *[limited_task(task) for task in tasks],
                return_exceptions=True
            )
            
            # 处理结果
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch request failed: {result}")
                    self.total_failed += 1
                else:
                    results.append(result)
                    if result.success:
                        self.total_successful += 1
                    else:
                        self.total_failed += 1
                    
                    # 执行回调
                    if result.request.callback:
                        try:
                            await result.request.callback(result)
                        except Exception as e:
                            logger.error(f"Callback execution failed: {e}")
                
                self.total_processed += 1
            
            # 更新性能统计
            self._update_performance_stats(results)
            
            logger.info(f"Batch processing completed: {len(results)} results")
            
        finally:
            self.is_processing = False
        
        return results
    
    async def _process_single_request(self, request: BatchRequest) -> BatchResult:
        """处理单个请求"""
        start_time = time.time()
        request_id = request.metadata.get('request_id', 'unknown')
        
        try:
            # 记录正在处理的请求
            self.processing_requests[request_id] = request
            
            # 检查缓存
            cache_hit = False
            data = None
            
            # 从API获取数据
            from src.argus_mcp.api.enhanced_historical_api import EnhancedHistoricalDataAPI
            api = EnhancedHistoricalDataAPI()
            
            # 重试机制
            last_error = None
            for attempt in range(self.config.retry_attempts):
                try:
                    data = await asyncio.wait_for(
                        api.get_historical_data(
                            symbol=request.symbol,
                            start_date=request.start_date,
                            end_date=request.end_date,
                            period=request.period
                        ),
                        timeout=self.config.request_timeout
                    )
                    
                    # 检查是否来自缓存
                    if hasattr(data, 'metadata') and data.metadata.cache_hit:
                        cache_hit = True
                    
                    break
                    
                except Exception as e:
                    last_error = e
                    if attempt < self.config.retry_attempts - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                        logger.warning(f"Request {request_id} attempt {attempt + 1} failed, retrying: {e}")
                    else:
                        logger.error(f"Request {request_id} failed after {self.config.retry_attempts} attempts: {e}")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # 记录访问模式
            self.cache_strategy.record_access(request.symbol, request.period, cache_hit)
            
            if data is not None:
                return BatchResult(
                    request=request,
                    success=True,
                    data=data,
                    response_time=response_time,
                    cache_hit=cache_hit
                )
            else:
                return BatchResult(
                    request=request,
                    success=False,
                    error=str(last_error) if last_error else "Unknown error",
                    response_time=response_time
                )
        
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            
            return BatchResult(
                request=request,
                success=False,
                error=str(e),
                response_time=response_time
            )
        
        finally:
            # 清理处理中的请求
            if request_id in self.processing_requests:
                del self.processing_requests[request_id]
    
    def _optimize_request_order(self, requests: List[BatchRequest]) -> List[BatchRequest]:
        """优化请求顺序"""
        # 按优先级和相似性排序
        def request_key(req):
            # 优先级权重
            priority_weight = req.priority * 1000
            
            # 相同股票和周期的请求应该连续处理（缓存友好）
            symbol_hash = hash(req.symbol) % 100
            period_hash = hash(req.period) % 10
            
            return priority_weight + symbol_hash + period_hash
        
        return sorted(requests, key=request_key, reverse=True)
    
    async def _adjust_concurrency(self) -> None:
        """自适应调整并发数"""
        if not self.performance_history:
            return
        
        # 分析最近的性能数据
        recent_performance = self.performance_history[-self.config.performance_window_size:]
        
        if len(recent_performance) < 10:
            return
        
        # 计算平均响应时间和成功率
        avg_response_time = sum(p['avg_response_time'] for p in recent_performance) / len(recent_performance)
        avg_success_rate = sum(p['success_rate'] for p in recent_performance) / len(recent_performance)
        
        # 调整策略
        if avg_response_time > 5.0 or avg_success_rate < 0.9:
            # 性能下降，减少并发
            new_concurrency = max(
                self.config.min_concurrency,
                int(self.current_concurrency * 0.8)
            )
        elif avg_response_time < 1.0 and avg_success_rate > 0.95:
            # 性能良好，增加并发
            new_concurrency = min(
                self.config.max_concurrency,
                int(self.current_concurrency * 1.2)
            )
        else:
            return  # 保持当前并发数
        
        if new_concurrency != self.current_concurrency:
            logger.info(f"Adjusting concurrency from {self.current_concurrency} to {new_concurrency}")
            self.current_concurrency = new_concurrency
            self.semaphore = asyncio.Semaphore(new_concurrency)
    
    def _update_performance_stats(self, results: List[BatchResult]) -> None:
        """更新性能统计"""
        if not results:
            return
        
        successful_results = [r for r in results if r.success]
        
        performance_data = {
            'timestamp': time.time(),
            'total_requests': len(results),
            'successful_requests': len(successful_results),
            'success_rate': len(successful_results) / len(results),
            'avg_response_time': sum(r.response_time for r in results) / len(results),
            'cache_hit_rate': sum(1 for r in results if r.cache_hit) / len(results),
            'concurrency': self.current_concurrency
        }
        
        self.performance_history.append(performance_data)
        
        # 限制历史数据大小
        if len(self.performance_history) > self.config.performance_window_size * 2:
            self.performance_history = self.performance_history[-self.config.performance_window_size:]
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            'queue_size': self.request_queue.qsize(),
            'processing_requests': len(self.processing_requests),
            'is_processing': self.is_processing,
            'current_concurrency': self.current_concurrency,
            'total_processed': self.total_processed,
            'total_successful': self.total_successful,
            'total_failed': self.total_failed,
            'success_rate': self.total_successful / max(1, self.total_processed),
            'performance_history_size': len(self.performance_history)
        }
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.performance_history:
            return {'error': 'No performance data available'}
        
        recent_data = self.performance_history[-50:]  # 最近50次的数据
        
        return {
            'avg_response_time': sum(p['avg_response_time'] for p in recent_data) / len(recent_data),
            'avg_success_rate': sum(p['success_rate'] for p in recent_data) / len(recent_data),
            'avg_cache_hit_rate': sum(p['cache_hit_rate'] for p in recent_data) / len(recent_data),
            'current_concurrency': self.current_concurrency,
            'optimal_concurrency_range': [self.config.min_concurrency, self.config.max_concurrency],
            'performance_trend': self._calculate_performance_trend(recent_data)
        }
    
    def _calculate_performance_trend(self, data: List[Dict[str, Any]]) -> str:
        """计算性能趋势"""
        if len(data) < 10:
            return 'insufficient_data'
        
        # 比较前半部分和后半部分的性能
        mid_point = len(data) // 2
        first_half = data[:mid_point]
        second_half = data[mid_point:]
        
        first_avg_time = sum(p['avg_response_time'] for p in first_half) / len(first_half)
        second_avg_time = sum(p['avg_response_time'] for p in second_half) / len(second_half)
        
        first_success_rate = sum(p['success_rate'] for p in first_half) / len(first_half)
        second_success_rate = sum(p['success_rate'] for p in second_half) / len(second_half)
        
        # 判断趋势
        time_improvement = (first_avg_time - second_avg_time) / first_avg_time
        success_improvement = second_success_rate - first_success_rate
        
        if time_improvement > 0.1 and success_improvement > 0.05:
            return 'improving'
        elif time_improvement < -0.1 or success_improvement < -0.05:
            return 'degrading'
        else:
            return 'stable'
    
    async def optimize_batch_performance(self) -> Dict[str, Any]:
        """优化批量处理性能"""
        logger.info("Starting batch performance optimization")
        
        optimization_results = {
            'timestamp': datetime.now().isoformat(),
            'actions_taken': [],
            'performance_before': await self.get_performance_summary(),
            'performance_after': None
        }
        
        # 1. 调整并发数
        try:
            old_concurrency = self.current_concurrency
            await self._adjust_concurrency()
            if self.current_concurrency != old_concurrency:
                optimization_results['actions_taken'].append(
                    f'adjusted_concurrency_{old_concurrency}_to_{self.current_concurrency}'
                )
        except Exception as e:
            logger.error(f"Failed to adjust concurrency: {e}")
        
        # 2. 清理性能历史数据
        try:
            if len(self.performance_history) > self.config.performance_window_size:
                old_size = len(self.performance_history)
                self.performance_history = self.performance_history[-self.config.performance_window_size:]
                optimization_results['actions_taken'].append(
                    f'cleaned_performance_history_{old_size}_to_{len(self.performance_history)}'
                )
        except Exception as e:
            logger.error(f"Failed to clean performance history: {e}")
        
        # 3. 优化缓存策略
        try:
            cache_optimization = await self.cache_strategy.optimize_cache_performance()
            optimization_results['actions_taken'].extend(cache_optimization.get('actions_taken', []))
        except Exception as e:
            logger.error(f"Failed to optimize cache: {e}")
        
        # 获取优化后的性能指标
        try:
            optimization_results['performance_after'] = await self.get_performance_summary()
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
        
        logger.info(f"Batch optimization completed: {len(optimization_results['actions_taken'])} actions taken")
        return optimization_results


# 全局批量优化器实例
_global_batch_optimizer: Optional[BatchDataOptimizer] = None

def get_batch_data_optimizer() -> BatchDataOptimizer:
    """获取全局批量数据优化器"""
    global _global_batch_optimizer
    if _global_batch_optimizer is None:
        _global_batch_optimizer = BatchDataOptimizer()
    return _global_batch_optimizer


# 便捷函数
async def process_batch_data_requests(
    requests: List[Dict[str, Any]],
    max_concurrent: Optional[int] = None
) -> List[BatchResult]:
    """处理批量数据请求"""
    optimizer = get_batch_data_optimizer()
    
    if max_concurrent:
        optimizer.current_concurrency = max_concurrent
        optimizer.semaphore = asyncio.Semaphore(max_concurrent)
    
    # 添加请求
    await optimizer.add_batch_requests(requests)
    
    # 处理请求
    return await optimizer.process_batch_requests()


async def optimize_batch_performance_now() -> Dict[str, Any]:
    """立即优化批量处理性能"""
    optimizer = get_batch_data_optimizer()
    return await optimizer.optimize_batch_performance()