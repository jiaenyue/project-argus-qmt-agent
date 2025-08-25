#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的数据获取服务
实现批量处理、异步优化、智能缓存等功能
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from collections import defaultdict, deque
import numpy as np
from fastapi import HTTPException

# 强制导入xtdata，如果失败则抛出错误
try:
    from xtquant import xtdata
except ImportError as e:
    raise ImportError(
        "无法导入xtdata模块。请确保miniQMT客户端已正确安装并配置。"
        "项目不支持模拟模式，必须连接真实的miniQMT服务。"
    ) from e

from .xtquant_connection_pool import get_connection_pool, ConnectionStatus
from .performance_optimizer import get_global_optimizer, optimize_performance
from .cache_manager import get_cache_manager
from .exception_handler import safe_execute, get_global_exception_handler
from .connection_monitor import get_connection_monitor
from .data_storage_service import get_data_storage_service

logger = logging.getLogger(__name__)

@dataclass
class DataRequest:
    """数据请求对象"""
    request_id: str
    request_type: str  # 'market_data', 'kline', 'trading_dates', etc.
    symbols: List[str]
    fields: List[str]
    params: Dict[str, Any]
    timestamp: datetime
    priority: int = 1  # 1=high, 2=medium, 3=low

@dataclass
class BatchResult:
    """批量处理结果"""
    request_id: str
    success: bool
    data: Any
    error: Optional[str] = None
    processing_time: float = 0.0

class OptimizedDataService:
    """优化的数据获取服务"""
    
    def __init__(self, max_batch_size: int = 20, batch_timeout: float = 0.05):
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        
        # 批量处理队列
        self._pending_requests: Dict[str, List[DataRequest]] = defaultdict(list)
        self._request_futures: Dict[str, asyncio.Future] = {}
        self._batch_lock = threading.Lock()
        
        # 性能优化器和缓存管理器
        self.optimizer = get_global_optimizer()
        self.cache_manager = get_cache_manager()
        
        # 连接监控器和异常处理器
        self.connection_monitor = get_connection_monitor()
        self.exception_handler = get_global_exception_handler()
        
        # 数据存储服务
        self.storage_service = get_data_storage_service()
        
        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="data_service")
        
        # 批量处理任务
        self._batch_processor_task = None
        self._running = False
        
        # 性能统计
        self._stats = {
            'total_requests': 0,
            'batch_requests': 0,
            'cache_hits': 0,
            'avg_response_time': 0.0,
            'batch_efficiency': 0.0
        }
        
    async def start(self):
        """启动服务"""
        if self._running:
            return
            
        self._running = True
        
        # 启动连接监控
        await self.connection_monitor.start()
        
        # 启动批量处理器
        self._batch_processor_task = asyncio.create_task(self._batch_processor())
        
        logger.info("OptimizedDataService started with connection monitoring")
    
    async def stop(self):
        """停止服务"""
        self._running = False
        
        # 停止连接监控
        await self.connection_monitor.stop()
        
        if self._batch_processor_task:
            self._batch_processor_task.cancel()
            try:
                await self._batch_processor_task
            except asyncio.CancelledError:
                pass
        
        self._executor.shutdown(wait=True)
        logger.info("OptimizedDataService stopped")
    
    async def _batch_processor(self):
        """批量处理器"""
        while self._running:
            try:
                await asyncio.sleep(self.batch_timeout)
                await self._process_pending_batches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processor: {str(e)}")
    
    async def _process_pending_batches(self):
        """处理待处理的批量请求"""
        with self._batch_lock:
            if not self._pending_requests:
                return
            
            # 复制并清空待处理请求
            batches_to_process = dict(self._pending_requests)
            self._pending_requests.clear()
        
        # 并发处理不同类型的批量请求
        tasks = []
        for request_type, requests in batches_to_process.items():
            if requests:
                task = asyncio.create_task(
                    self._process_batch(request_type, requests)
                )
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_batch(self, request_type: str, requests: List[DataRequest]):
        """处理单个批量请求"""
        start_time = time.time()
        
        try:
            if request_type == 'market_data':
                results = await self._batch_get_market_data(requests)
            elif request_type == 'kline':
                results = await self._batch_get_kline_data(requests)
            elif request_type == 'trading_dates':
                results = await self._batch_get_trading_dates(requests)
            else:
                # 单独处理不支持批量的请求
                results = await self._process_individual_requests(requests)
            
            # 设置结果
            for result in results:
                future = self._request_futures.get(result.request_id)
                if future and not future.done():
                    future.set_result(result)
            
            # 更新统计
            processing_time = time.time() - start_time
            self._stats['batch_requests'] += 1
            self._stats['batch_efficiency'] = len(requests) / max(processing_time, 0.001)
            
            logger.debug(f"Processed batch of {len(requests)} {request_type} requests in {processing_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Error processing batch {request_type}: {str(e)}")
            
            # 设置错误结果
            for request in requests:
                future = self._request_futures.get(request.request_id)
                if future and not future.done():
                    result = BatchResult(
                        request_id=request.request_id,
                        success=False,
                        data=None,
                        error=str(e)
                    )
                    future.set_result(result)
    
    async def _batch_get_market_data(self, requests: List[DataRequest]) -> List[BatchResult]:
        """批量获取市场数据"""
        # 合并所有请求的股票代码
        all_symbols = set()
        all_fields = set()
        
        for request in requests:
            all_symbols.update(request.symbols)
            all_fields.update(request.fields)
        
        # 检查缓存
        cache_key = f"market_data:{':'.join(sorted(all_symbols))}:{':'.join(sorted(all_fields))}"
        cached_data = await self.cache_manager.get_market_data(cache_key)
        
        if cached_data:
            self._stats['cache_hits'] += 1
            market_data = cached_data
        else:
            # 批量获取数据
            def _fetch_data():
                # 检查连接状态
                monitor_status = self.connection_monitor.get_status()
                if not monitor_status.is_healthy:
                    raise HTTPException(
                        status_code=503, 
                        detail=f"QMT连接不健康: {monitor_status.status_message}"
                    )
                
                with get_connection_pool().get_connection() as conn:
                    if not conn or conn.status != ConnectionStatus.CONNECTED:
                        raise HTTPException(status_code=503, detail="QMT连接不可用")
                    
                    return xtdata.get_market_data(
                        field_list=list(all_fields),
                        stock_list=list(all_symbols),
                        period='tick',
                        count=1
                    )
            
            # 使用异常处理器安全执行数据获取
            market_data = await safe_execute(
                asyncio.get_event_loop().run_in_executor(self._executor, _fetch_data),
                operation_name="batch_get_market_data",
                max_retries=3
            )
            
            # 缓存结果
            await self.cache_manager.set_market_data(cache_key, market_data, ttl=30)
            
            # 保存到数据库
            try:
                await self._save_market_data_to_db(market_data, list(all_symbols))
            except Exception as e:
                logger.warning(f"保存市场数据到数据库失败: {e}")
        
        # 为每个请求构建结果
        results = []
        for request in requests:
            try:
                result_data = {}
                for symbol in request.symbols:
                    symbol_data = {}
                    for field in request.fields:
                        if field in market_data and symbol in market_data[field]:
                            value = market_data[field][symbol]
                            if isinstance(value, list) and value:
                                symbol_data[field] = value[0]
                            else:
                                symbol_data[field] = value
                        else:
                            symbol_data[field] = None
                    result_data[symbol] = symbol_data
                
                results.append(BatchResult(
                    request_id=request.request_id,
                    success=True,
                    data=result_data
                ))
                
            except Exception as e:
                results.append(BatchResult(
                    request_id=request.request_id,
                    success=False,
                    data=None,
                    error=str(e)
                ))
        
        return results
    
    async def _batch_get_kline_data(self, requests: List[DataRequest]) -> List[BatchResult]:
        """批量获取K线数据"""
        # 按周期分组请求
        period_groups = defaultdict(list)
        for request in requests:
            period = request.params.get('period', '1d')
            period_groups[period].append(request)
        
        all_results = []
        
        # 按周期批量处理
        for period, period_requests in period_groups.items():
            # 合并同周期的股票代码
            all_symbols = set()
            for request in period_requests:
                all_symbols.update(request.symbols)
            
            # 获取通用参数
            start_time = period_requests[0].params.get('start_time')
            end_time = period_requests[0].params.get('end_time')
            
            # 检查缓存
            cache_key = f"kline:{period}:{':'.join(sorted(all_symbols))}:{start_time}:{end_time}"
            cached_data = await self.cache_manager.get_kline_data(cache_key)
            
            if cached_data:
                self._stats['cache_hits'] += 1
                kline_data = cached_data
            else:
                # 批量获取K线数据
                def _fetch_kline():
                    # 检查连接状态
                    monitor_status = self.connection_monitor.get_status()
                    if not monitor_status.is_healthy:
                        raise HTTPException(
                            status_code=503, 
                            detail=f"QMT连接不健康: {monitor_status.status_message}"
                        )
                    
                    with get_connection_pool().get_connection() as conn:
                        if not conn or conn.status != ConnectionStatus.CONNECTED:
                            raise HTTPException(status_code=503, detail="QMT连接不可用")
                        
                        field_list = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
                        return xtdata.get_market_data(
                            field_list=field_list,
                            stock_list=list(all_symbols),
                            period=period,
                            start_time=start_time,
                            end_time=end_time
                        )
                
                # 使用异常处理器安全执行K线数据获取
                kline_data = await safe_execute(
                    asyncio.get_event_loop().run_in_executor(self._executor, _fetch_kline),
                    operation_name="batch_get_kline_data",
                    max_retries=3
                )
                
                # 缓存结果
                await self.cache_manager.set_kline_data(cache_key, kline_data, ttl=1800)
                
                # 保存到数据库
                try:
                    await self._save_kline_data_to_db(kline_data, list(all_symbols), period)
                except Exception as e:
                    logger.warning(f"保存K线数据到数据库失败: {e}")
            
            # 为每个请求构建结果
            for request in period_requests:
                try:
                    result_data = {}
                    for symbol in request.symbols:
                        if 'time' in kline_data and symbol in kline_data['time']:
                            # 构建K线数据数组
                            times = kline_data['time'][symbol]
                            if times:
                                kline_array = []
                                for i in range(len(times)):
                                    bar = {'time': times[i]}
                                    for field in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                                        if field in kline_data and symbol in kline_data[field]:
                                            values = kline_data[field][symbol]
                                            bar[field] = values[i] if i < len(values) else None
                                        else:
                                            bar[field] = None
                                    kline_array.append(bar)
                                result_data[symbol] = kline_array
                            else:
                                result_data[symbol] = []
                        else:
                            result_data[symbol] = []
                    
                    all_results.append(BatchResult(
                        request_id=request.request_id,
                        success=True,
                        data=result_data
                    ))
                    
                except Exception as e:
                    all_results.append(BatchResult(
                        request_id=request.request_id,
                        success=False,
                        data=None,
                        error=str(e)
                    ))
        
        return all_results
    
    async def _batch_get_trading_dates(self, requests: List[DataRequest]) -> List[BatchResult]:
        """批量获取交易日期"""
        # 交易日期通常按市场分组
        market_groups = defaultdict(list)
        for request in requests:
            market = request.params.get('market', 'SH')
            market_groups[market].append(request)
        
        all_results = []
        
        for market, market_requests in market_groups.items():
            # 获取该市场的所有日期范围
            start_times = [req.params.get('start_time') for req in market_requests]
            end_times = [req.params.get('end_time') for req in market_requests]
            
            # 使用最大范围获取数据
            min_start = min(filter(None, start_times)) if any(start_times) else None
            max_end = max(filter(None, end_times)) if any(end_times) else None
            
            # 检查缓存
            cache_key = f"trading_dates:{market}:{min_start}:{max_end}"
            cached_data = await self.cache_manager.get(cache_key)
            
            if cached_data:
                self._stats['cache_hits'] += 1
                all_dates = cached_data
            else:
                # 获取交易日期
                def _fetch_dates():
                    # 检查连接状态
                    monitor_status = self.connection_monitor.get_status()
                    if not monitor_status.is_healthy:
                        raise HTTPException(
                            status_code=503, 
                            detail=f"QMT连接不健康: {monitor_status.status_message}"
                        )
                    
                    with get_connection_pool().get_connection() as conn:
                        if not conn or conn.status != ConnectionStatus.CONNECTED:
                            raise HTTPException(status_code=503, detail="QMT连接不可用")
                        
                        return xtdata.get_trading_dates(
                            market,
                            min_start or "",
                            max_end or "",
                            -1
                        )
                
                # 使用异常处理器安全执行交易日期获取
                all_dates = await safe_execute(
                    asyncio.get_event_loop().run_in_executor(self._executor, _fetch_dates),
                    operation_name="batch_get_trading_dates",
                    max_retries=3
                )
                
                # 缓存结果
                await self.cache_manager.set(cache_key, all_dates, ttl=3600)
            
            # 为每个请求过滤结果
            for request in market_requests:
                try:
                    start_time = request.params.get('start_time')
                    end_time = request.params.get('end_time')
                    count = request.params.get('count', -1)
                    
                    filtered_dates = all_dates
                    
                    # 应用过滤条件
                    if start_time:
                        filtered_dates = [d for d in filtered_dates if d >= start_time]
                    if end_time:
                        filtered_dates = [d for d in filtered_dates if d <= end_time]
                    if count > 0:
                        filtered_dates = filtered_dates[-count:]
                    
                    all_results.append(BatchResult(
                        request_id=request.request_id,
                        success=True,
                        data=filtered_dates
                    ))
                    
                except Exception as e:
                    all_results.append(BatchResult(
                        request_id=request.request_id,
                        success=False,
                        data=None,
                        error=str(e)
                    ))
        
        return all_results
    
    async def _process_individual_requests(self, requests: List[DataRequest]) -> List[BatchResult]:
        """处理单独的请求"""
        results = []
        
        # 并发处理单独请求
        tasks = []
        for request in requests:
            task = asyncio.create_task(self._process_single_request(request))
            tasks.append(task)
        
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(completed_results):
            if isinstance(result, Exception):
                results.append(BatchResult(
                    request_id=requests[i].request_id,
                    success=False,
                    data=None,
                    error=str(result)
                ))
            else:
                results.append(result)
        
        return results
    
    async def _process_single_request(self, request: DataRequest) -> BatchResult:
        """处理单个请求"""
        start_time = time.time()
        
        try:
            # 这里可以添加更多请求类型的处理逻辑
            result_data = {"message": "Request type not implemented for batch processing"}
            
            processing_time = time.time() - start_time
            return BatchResult(
                request_id=request.request_id,
                success=True,
                data=result_data,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return BatchResult(
                request_id=request.request_id,
                success=False,
                data=None,
                error=str(e),
                processing_time=processing_time
            )
    
    async def request_data(self, request: DataRequest) -> BatchResult:
        """请求数据（支持批量处理）"""
        self._stats['total_requests'] += 1
        
        # 检查连接状态
        if not self.connection_monitor.get_status().is_healthy:
            return BatchResult(
                request_id=request.request_id,
                success=False,
                data=None,
                error="QMT连接不健康，无法处理请求"
            )
        
        # 创建Future用于接收结果
        future = asyncio.Future()
        self._request_futures[request.request_id] = future
        
        # 添加到批量处理队列
        with self._batch_lock:
            self._pending_requests[request.request_type].append(request)
            
            # 如果达到批量大小，立即处理
            if len(self._pending_requests[request.request_type]) >= self.max_batch_size:
                requests_to_process = self._pending_requests[request.request_type].copy()
                self._pending_requests[request.request_type].clear()
                
                # 异步处理批量请求
                asyncio.create_task(
                    self._process_batch(request.request_type, requests_to_process)
                )
        
        # 等待结果
        try:
            result = await asyncio.wait_for(future, timeout=30.0)  # 30秒超时
            return result
        except asyncio.TimeoutError:
            return BatchResult(
                request_id=request.request_id,
                success=False,
                data=None,
                error="Request timeout"
            )
        finally:
            # 清理Future
            self._request_futures.pop(request.request_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        return {
            **self._stats,
            'pending_requests': sum(len(reqs) for reqs in self._pending_requests.values()),
            'active_futures': len(self._request_futures),
            'cache_stats': self.cache_manager.get_cache_info() if hasattr(self.cache_manager, 'get_cache_info') else {},
            'optimizer_stats': self.optimizer.get_performance_stats(),
            'connection_status': self.connection_monitor.get_status().__dict__,
            'connection_metrics': self.connection_monitor.get_metrics_history(),
            'exception_stats': self.exception_handler.get_exception_stats()
        }
    
    async def _save_market_data_to_db(self, market_data: Dict[str, Any], symbols: List[str]):
        """将市场数据保存到数据库"""
        try:
            # 转换数据格式为数据库存储格式
            data_records = []
            current_time = datetime.now()
            
            for symbol in symbols:
                record = {
                    'symbol': symbol,
                    'timestamp': current_time,
                    'data_type': 'market_data'
                }
                
                # 提取各字段数据
                for field in ['lastPrice', 'volume', 'amount', 'bid1', 'ask1', 'bidVol1', 'askVol1']:
                    if field in market_data and symbol in market_data[field]:
                        value = market_data[field][symbol]
                        if isinstance(value, list) and value:
                            record[field] = value[0]
                        else:
                            record[field] = value
                    else:
                        record[field] = None
                
                data_records.append(record)
            
            # 批量保存到数据库
            if data_records:
                await self.storage_service.batch_write_market_data(data_records)
                logger.debug(f"成功保存 {len(data_records)} 条市场数据到数据库")
                
        except Exception as e:
            logger.error(f"保存市场数据到数据库失败: {e}")
            raise
    
    async def _save_kline_data_to_db(self, kline_data: Dict[str, Any], symbols: List[str], period: str):
        """将K线数据保存到数据库"""
        try:
            # 转换数据格式为数据库存储格式
            data_records = []
            
            for symbol in symbols:
                if 'time' in kline_data and symbol in kline_data['time']:
                    times = kline_data['time'][symbol]
                    if times:
                        for i, timestamp in enumerate(times):
                            record = {
                                'symbol': symbol,
                                'timestamp': timestamp,
                                'period': period,
                                'data_type': 'kline_data'
                            }
                            
                            # 提取OHLCV数据
                            for field in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                                if field in kline_data and symbol in kline_data[field]:
                                    values = kline_data[field][symbol]
                                    record[field] = values[i] if i < len(values) else None
                                else:
                                    record[field] = None
                            
                            data_records.append(record)
            
            # 批量保存到数据库
            if data_records:
                await self.storage_service.batch_write_kline_data(data_records)
                logger.debug(f"成功保存 {len(data_records)} 条K线数据到数据库")
                
        except Exception as e:
            logger.error(f"保存K线数据到数据库失败: {e}")
            raise

# 全局优化数据服务实例
_global_data_service: Optional[OptimizedDataService] = None

def get_global_data_service() -> OptimizedDataService:
    """获取全局优化数据服务实例"""
    global _global_data_service
    if _global_data_service is None:
        _global_data_service = OptimizedDataService()
    return _global_data_service

async def init_data_service():
    """初始化数据服务"""
    service = get_global_data_service()
    await service.start()
    logger.info("Optimized data service initialized")

async def shutdown_data_service():
    """关闭数据服务"""
    global _global_data_service
    if _global_data_service:
        await _global_data_service.stop()
        _global_data_service = None
    logger.info("Optimized data service shutdown")