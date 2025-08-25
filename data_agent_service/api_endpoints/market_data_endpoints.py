"""
市场数据API端点
包含所有市场数据相关的API端点
"""

import re
import time
import logging
import pandas as pd
import numpy as np
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Path, Depends

from ..xtquant_connection_pool import get_connection_pool, ConnectionStatus
from ..auth_middleware import get_current_user
from ..auth_middleware import require_permissions
from ..response_formatter import unified_response
from ..performance_optimizer import optimize_performance
from ..retry_mechanism import retry_data_fetch, DATA_FETCH_RETRY_CONFIG, MARKET_DATA_RETRY_CONFIG
from ..exception_handler import exception_handler_decorator, get_global_exception_handler

from xtquant import xtdata
# 修复: 运行 main.py 时，api_endpoints 作为顶层包加载，使用相对导入会越界，改为绝对导入同级模块
from .. import optimized_api_endpoints

# 可选增强市场数据处理器
try:
    from ..enhanced_market_data_processor import get_market_data_processor
except Exception:
    get_market_data_processor = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["市场数据"])


@router.get("/instrument_detail/{symbol}")
@require_permissions(["read:market_data"])
@unified_response
@optimize_performance(ttl=300)  # 缓存5分钟
@retry_data_fetch(DATA_FETCH_RETRY_CONFIG)
async def get_instrument_detail(
    symbol: str = Path(..., min_length=1),
    current_user: dict = Depends(get_current_user)
):
    """获取股票详细信息"""
    try:
        connection_pool = get_connection_pool()
        with connection_pool.get_connection() as conn:
            if not conn or conn.metrics.status != ConnectionStatus.HEALTHY:
                raise HTTPException(status_code=503, detail="QMT连接不可用")
            
            upper_symbol = symbol.upper()
            if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', upper_symbol):
                raise HTTPException(status_code=400, detail="Invalid symbol format. Expected format like '600519.SH' or '000001.SZ'.")
            
            detail = xtdata.get_instrument_detail(upper_symbol)
            
            if detail is None or detail == {}:
                raise HTTPException(status_code=404, detail=f"Instrument not found: {symbol}")
            
            # 从xtdata.get_instrument_detail返回的detail中提取信息
            last_price = detail.get("PreClose", 0.0)
            pre_close = detail.get("PreClose", 0.0)
            
            change_percent = 0.0
            if pre_close and last_price is not None:
                if pre_close != 0:
                    change_percent = ((last_price - pre_close) / pre_close) * 100
                else:
                    change_percent = 0.0

            return {
                "symbol": detail.get("InstrumentID", symbol),
                "name": detail.get("InstrumentName", symbol),
                "last_price": last_price,
                "open_price": detail.get("OpenPrice", 0.0),
                "high_price": detail.get("HighPrice", 0.0),
                "low_price": detail.get("LowPrice", 0.0),
                "close_price": last_price,
                "volume": detail.get("TotalVolume", 0),
                "amount": 0.0,
                "timestamp": 0,
                "change_percent": change_percent,
                "ExchangeID": detail.get("ExchangeID"),
                "PreClose": detail.get("PreClose"),
                "TotalVolume": detail.get("TotalVolume"),
                "FloatVolume": detail.get("FloatVolume"),
                "IsTrading": detail.get("IsTrading"),
                "UniCode": detail.get("UniCode"),
                "OpenDate": detail.get("OpenDate"),
                "PriceTick": detail.get("PriceTick")
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股票详细信息失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stock_list_in_sector")
@require_permissions(["read:market_data"])
@unified_response
@optimize_performance(ttl=600)  # 缓存10分钟
@retry_data_fetch(DATA_FETCH_RETRY_CONFIG)
async def get_stock_list_in_sector(
    sector_name: str = Query(..., min_length=1, description="Sector name, e.g., '沪深A股'"),
    current_user: dict = Depends(get_current_user)
):
    """获取板块内股票列表"""
    try:
        connection_pool = get_connection_pool()
        with connection_pool.get_connection() as conn:
            if not conn or conn.metrics.status != ConnectionStatus.HEALTHY:
                raise HTTPException(status_code=503, detail="QMT连接不可用")
            
            stock_list = xtdata.get_stock_list_in_sector(sector_name)
            return stock_list or []
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取板块内股票列表失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# 为了兼容性，添加get_stock_list别名
@router.get("/get_stock_list")
@require_permissions(["read:market_data"])
@unified_response
@optimize_performance(ttl=600)  # 缓存10分钟
@retry_data_fetch(DATA_FETCH_RETRY_CONFIG)
async def get_stock_list(
    sector: str = Query(..., min_length=1, description="Sector name, e.g., '沪深A股'"),
    current_user: dict = Depends(get_current_user)
):
    """获取板块内股票列表（别名端点）"""
    try:
        connection_pool = get_connection_pool()
        with connection_pool.get_connection() as conn:
            if not conn or conn.metrics.status != ConnectionStatus.HEALTHY:
                raise HTTPException(status_code=503, detail="QMT连接不可用")
            
            stock_list = xtdata.get_stock_list_in_sector(sector)
            return stock_list or []
    except Exception as e:
        # 记录异常但返回错误响应
        logger.error(f"获取股票列表失败: {str(e)}")
        from ..response_formatter import ResponseFormatter
        return ResponseFormatter.error_response(
            message=f"获取股票列表失败: {str(e)}",
            code=500,
            error_code="STOCK_LIST_ERROR"
        )


@router.get("/latest_market_data")
@require_permissions(["read:market_data"])
@unified_response
@optimize_performance(ttl=30)  # 缓存30秒
@retry_data_fetch(MARKET_DATA_RETRY_CONFIG)
async def get_latest_market_data(
    symbols: str = Query(..., description="Comma-separated list of stock symbols, e.g., '600519.SH,000001.SZ'"),
    current_user: dict = Depends(get_current_user)
):
    """获取最新市场数据"""
    try:
        connection_pool = get_connection_pool()
        with connection_pool.get_connection() as conn:
            if not conn or conn.metrics.status != ConnectionStatus.HEALTHY:
                raise HTTPException(status_code=503, detail="QMT连接不可用")
            
            symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
            if not symbol_list:
                raise HTTPException(status_code=400, detail="symbols query parameter cannot be empty")
            
            # 验证股票代码格式
            invalid_symbols = [s for s in symbol_list if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', s)]
            if invalid_symbols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid symbol format: {', '.join(invalid_symbols)}"
                )
            
            # 获取最新市场数据
            market_data = xtdata.get_market_data(
                field_list=['lastPrice', 'open', 'high', 'low', 'volume', 'amount', 'time'],
                stock_list=symbol_list,
                period='tick',
                count=1
            )
            
            # 构建响应对象
            result = {}
            for symbol in symbol_list:
                result[symbol] = {
                    "time": market_data.get('time', {}).get(symbol, [None])[0],
                    "lastPrice": market_data.get('lastPrice', {}).get(symbol, [None])[0],
                    "volume": market_data.get('volume', {}).get(symbol, [None])[0],
                    "amount": market_data.get('amount', {}).get(symbol, [None])[0],
                    "open": market_data.get('open', {}).get(symbol, [None])[0],
                    "high": market_data.get('high', {}).get(symbol, [None])[0],
                    "low": market_data.get('low', {}).get(symbol, [None])[0]
                }
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最新市场数据失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/enhanced/latest_market_data")
@require_permissions(["read:market_data"])
@unified_response
@optimize_performance(ttl=20)  # 增强版短缓存
@retry_data_fetch(MARKET_DATA_RETRY_CONFIG)
async def enhanced_latest_market_data(
    symbols: str = Query(..., description="Comma-separated list of stock symbols, e.g., '600519.SH,000001.SZ'"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to include"),
    use_cache: bool = Query(True, description="Whether to use cache"),
    current_user: dict = Depends(get_current_user)
):
    """增强版获取最新市场数据（支持大批量与优化处理）"""
    try:
        # 标准化股票代码列表
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="symbols query parameter cannot be empty")
        
        # 验证格式
        invalid_symbols = [s for s in symbol_list if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', s)]
        if invalid_symbols:
            raise HTTPException(status_code=400, detail=f"Invalid symbol format: {', '.join(invalid_symbols)}")
        
        # 解析字段
        field_list = None
        if fields:
            field_list = [f.strip() for f in fields.split(',') if f.strip()]
        
        # 使用增强处理器（如果可用）
        if get_market_data_processor:
            processor = get_market_data_processor()
            result = await processor.get_latest_market_data(symbol_list, fields=field_list, use_cache=use_cache)
            
            return {
                "summary": {
                    "total_requested": result.total_requested,
                    "successful": result.successful,
                    "failed": result.failed,
                    "processing_time": result.processing_time
                },
                "data": result.data,
                "errors": result.errors
            }
        else:
            # 降级到基本行情获取
            market_data = xtdata.get_market_data(
                field_list=field_list or ['lastPrice', 'open', 'high', 'low', 'volume', 'amount', 'time'],
                stock_list=symbol_list,
                period='tick',
                count=1
            )
            
            return {
                "summary": {
                    "total_requested": len(symbol_list),
                    "successful": len(symbol_list),
                    "failed": 0,
                    "processing_time": 0.1
                },
                "data": market_data,
                "errors": []
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"增强版获取最新市场数据失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/optimized/warm_up_cache")
@require_permissions(["write:system"])
@unified_response
@exception_handler_decorator(get_global_exception_handler(), auto_recover=False)
async def warm_up_cache_endpoint(
    current_user: dict = Depends(get_current_user)
):
    """预热缓存"""
    return await optimized_api_endpoints.warm_up_cache()