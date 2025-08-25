#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的API端点
集成批量处理、智能缓存和异步优化
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import Query, Depends, HTTPException
import logging

from .optimized_data_service import get_global_data_service, OptimizedDataService, DataRequest
from .auth_middleware import get_current_user, require_permissions
from .response_formatter import unified_response
from .performance_optimizer import optimize_performance
from .retry_mechanism import retry_data_fetch, MARKET_DATA_RETRY_CONFIG, DATA_FETCH_RETRY_CONFIG
from .exception_handler import exception_handler_decorator, handle_exception, get_global_exception_handler

logger = logging.getLogger(__name__)

class OptimizedAPIEndpoints:
    """优化的API端点类"""
    
    def __init__(self):
        self.data_service: OptimizedDataService = get_global_data_service()
    
    @require_permissions(["read:market_data"])
    @unified_response
    @optimize_performance(ttl=30)  # 缓存30秒
    @retry_data_fetch(MARKET_DATA_RETRY_CONFIG)
    @exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
    async def get_optimized_market_data(
        self,
        symbols: str = Query(..., description="Comma-separated list of stock symbols, e.g., '600519.SH,000001.SZ'"),
        fields: Optional[str] = Query(None, description="Comma-separated list of fields, e.g., 'lastPrice,volume,amount'"),
        current_user: dict = Depends(get_current_user)
    ):
        """优化的市场数据获取接口"""
        start_time = time.time()
        
        # 解析参数
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="symbols query parameter cannot be empty")
        
        # 验证股票代码格式
        import re
        invalid_symbols = [s for s in symbol_list if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', s)]
        if invalid_symbols:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid symbol format: {', '.join(invalid_symbols)}"
            )
        
        # 处理字段参数
        field_list = ['lastPrice', 'open', 'high', 'low', 'volume', 'amount', 'time']
        if fields:
            custom_fields = [f.strip() for f in fields.split(',') if f.strip()]
            if custom_fields:
                field_list = custom_fields
        
        # 创建数据请求
        request = DataRequest(
            request_id=str(uuid.uuid4()),
            request_type='market_data',
            symbols=symbol_list,
            fields=field_list,
            params={},
            timestamp=datetime.now(),
            priority=1
        )
        
        # 通过优化服务获取数据
        result = await self.data_service.request_data(request)
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "Failed to fetch market data")
        
        # 记录性能指标
        processing_time = time.time() - start_time
        logger.debug(f"Optimized market data request completed in {processing_time:.3f}s for {len(symbol_list)} symbols")
        
        return result.data
    
    @require_permissions(["read:market_data"])
    @unified_response
    @optimize_performance(ttl=60)  # 缓存1分钟
    @retry_data_fetch(MARKET_DATA_RETRY_CONFIG)
    @exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
    async def get_optimized_full_market_data(
        self,
        symbol: str = Query(..., description="Stock symbol, e.g., '600519.SH'"),
        fields: Optional[str] = Query(None, description="Comma-separated list of fields, e.g., 'open,high,low,close,volume'"),
        current_user: dict = Depends(get_current_user)
    ):
        """优化的完整市场数据获取接口"""
        start_time = time.time()
        
        # 验证股票代码格式
        import re
        upper_symbol = symbol.strip().upper()
        if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', upper_symbol):
            raise HTTPException(status_code=400, detail=f"Invalid symbol format: {symbol}")
        
        # 处理字段参数
        field_list = ["open", "high", "low", "close", "volume"]
        if fields:
            custom_fields = [f.strip() for f in fields.split(',') if f.strip()]
            if custom_fields:
                field_list = custom_fields
        
        # 创建数据请求
        request = DataRequest(
            request_id=str(uuid.uuid4()),
            request_type='full_market_data',
            symbols=[upper_symbol],
            fields=field_list,
            params={'period': '1d'},
            timestamp=datetime.now(),
            priority=1
        )
        
        # 通过优化服务获取数据
        result = await self.data_service.request_data(request)
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "Failed to fetch full market data")
        
        # 提取单个股票的数据
        symbol_data = result.data.get(upper_symbol, {})
        if not symbol_data:
            raise HTTPException(status_code=404, detail="Data not found")
        
        # 记录性能指标
        processing_time = time.time() - start_time
        logger.debug(f"Optimized full market data request completed in {processing_time:.3f}s for {symbol}")
        
        return symbol_data
    
    @require_permissions(["read:market_data"])
    @unified_response
    @optimize_performance(ttl=1800)  # 缓存30分钟
    @retry_data_fetch(MARKET_DATA_RETRY_CONFIG)
    @exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
    async def get_optimized_kline_data(
        self,
        symbols: str = Query(..., description="Comma-separated list of stock symbols, e.g., '600519.SH,000001.SZ'"),
        period: str = Query("1d", description="K-line period: 1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M"),
        start_time: Optional[str] = Query(None, description="Start time in YYYYMMDD format"),
        end_time: Optional[str] = Query(None, description="End time in YYYYMMDD format"),
        count: Optional[int] = Query(None, description="Number of bars to retrieve"),
        current_user: dict = Depends(get_current_user)
    ):
        """优化的K线数据获取接口（支持多股票批量获取）"""
        start_request_time = time.time()
        
        # 解析股票代码
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="symbols query parameter cannot be empty")
        
        # 验证股票代码格式
        import re
        invalid_symbols = [s for s in symbol_list if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', s)]
        if invalid_symbols:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid symbol format: {', '.join(invalid_symbols)}"
            )
        
        # 创建数据请求
        request = DataRequest(
            request_id=str(uuid.uuid4()),
            request_type='kline',
            symbols=symbol_list,
            fields=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
            params={
                'period': period,
                'start_time': start_time,
                'end_time': end_time,
                'count': count
            },
            timestamp=datetime.now(),
            priority=1
        )
        
        # 通过优化服务获取数据
        result = await self.data_service.request_data(request)
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "Failed to fetch K-line data")
        
        # 记录性能指标
        processing_time = time.time() - start_request_time
        logger.debug(f"Optimized K-line data request completed in {processing_time:.3f}s for {len(symbol_list)} symbols")
        
        return result.data
    
    @require_permissions(["read:market_data"])
    @unified_response
    @optimize_performance(ttl=3600)  # 缓存1小时
    @retry_data_fetch(DATA_FETCH_RETRY_CONFIG)
    @exception_handler_decorator(get_global_exception_handler(), auto_recover=True)
    async def get_optimized_trading_dates(
        self,
        markets: str = Query(..., description="Comma-separated list of market codes, e.g., 'SH,SZ'"),
        start_time: Optional[str] = Query(None, description="Start date in YYYYMMDD format, e.g., '20250101'. Optional."),
        end_time: Optional[str] = Query(None, description="End date in YYYYMMDD format, e.g., '20250101'. Optional."),
        count: Optional[int] = Query(-1, description="Number of recent trading dates to retrieve. -1 for all in range."),
        current_user: dict = Depends(get_current_user)
    ):
        """优化的交易日期获取接口（支持多市场批量获取）"""
        start_request_time = time.time()
        
        # 解析市场代码
        market_list = [m.strip().upper() for m in markets.split(',') if m.strip()]
        if not market_list:
            raise HTTPException(status_code=400, detail="markets query parameter cannot be empty")
        
        # 为每个市场创建请求
        requests = []
        for market in market_list:
            request = DataRequest(
                request_id=f"{uuid.uuid4()}_{market}",
                request_type='trading_dates',
                symbols=[],  # 交易日期不需要股票代码
                fields=[],
                params={
                    'market': market,
                    'start_time': start_time,
                    'end_time': end_time,
                    'count': count
                },
                timestamp=datetime.now(),
                priority=2
            )
            requests.append(request)
        
        # 并发获取所有市场的交易日期
        tasks = [self.data_service.request_data(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        market_dates = {}
        for i, result in enumerate(results):
            market = market_list[i]
            if isinstance(result, Exception):
                logger.error(f"Error fetching trading dates for market {market}: {str(result)}")
                market_dates[market] = {"error": str(result)}
            elif not result.success:
                logger.error(f"Failed to fetch trading dates for market {market}: {result.error}")
                market_dates[market] = {"error": result.error}
            else:
                market_dates[market] = result.data
        
        # 记录性能指标
        processing_time = time.time() - start_request_time
        logger.debug(f"Optimized trading dates request completed in {processing_time:.3f}s for {len(market_list)} markets")
        
        return market_dates
    
    @unified_response
    async def get_batch_performance_stats(self):
        """获取批量处理性能统计"""
        stats = self.data_service.get_stats()
        
        # 添加额外的性能指标
        stats['api_endpoints'] = {
            'optimized_market_data': 'active',
            'optimized_kline_data': 'active',
            'optimized_trading_dates': 'active',
            'batch_processing': 'enabled'
        }
        
        return stats
    
    async def warm_up_cache(self, symbols: List[str]):
        """预热缓存"""
        """为常用股票预热缓存"""
        logger.info(f"Warming up cache for {len(symbols)} symbols")
        
        # 预热市场数据缓存
        market_data_requests = []
        for i in range(0, len(symbols), 10):  # 每批10个股票
            batch_symbols = symbols[i:i+10]
            request = DataRequest(
                request_id=f"warmup_market_{i}",
                request_type='market_data',
                symbols=batch_symbols,
                fields=['lastPrice', 'volume', 'amount'],
                params={},
                timestamp=datetime.now(),
                priority=3  # 低优先级
            )
            market_data_requests.append(request)
        
        # 预热K线数据缓存（日线）
        kline_requests = []
        for i in range(0, len(symbols), 5):  # 每批5个股票
            batch_symbols = symbols[i:i+5]
            request = DataRequest(
                request_id=f"warmup_kline_{i}",
                request_type='kline',
                symbols=batch_symbols,
                fields=['time', 'open', 'high', 'low', 'close', 'volume'],
                params={'period': '1d', 'count': 30},  # 最近30天
                timestamp=datetime.now(),
                priority=3  # 低优先级
            )
            kline_requests.append(request)
        
        # 并发执行预热请求
        all_requests = market_data_requests + kline_requests
        tasks = [self.data_service.request_data(req) for req in all_requests]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception) and r.success)
            logger.info(f"Cache warm-up completed: {success_count}/{len(all_requests)} requests successful")
        except Exception as e:
            logger.error(f"Error during cache warm-up: {str(e)}")

# 创建全局优化API端点实例
optimized_endpoints = OptimizedAPIEndpoints()

# 导出优化的端点函数
get_optimized_market_data = optimized_endpoints.get_optimized_market_data
get_optimized_full_market_data = optimized_endpoints.get_optimized_full_market_data
get_optimized_kline_data = optimized_endpoints.get_optimized_kline_data
get_optimized_trading_dates = optimized_endpoints.get_optimized_trading_dates
get_batch_performance_stats = optimized_endpoints.get_batch_performance_stats
warm_up_cache = optimized_endpoints.warm_up_cache