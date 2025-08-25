"""响应格式化模块

提供统一的API响应格式化功能。
"""

import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from functools import wraps
from fastapi import HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

class ResponseFormatter:
    """响应格式化器"""
    
    @staticmethod
    def success_response(data: Any = None, message: str = "Success", code: int = 200) -> Dict[str, Any]:
        """成功响应格式"""
        return {
            "success": True,
            "code": code,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def error_response(message: str = "Error", code: int = 500, error_code: str = None) -> Dict[str, Any]:
        """错误响应格式"""
        return {
            "success": False,
            "code": code,
            "message": message,
            "error_code": error_code,
            "data": None,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def paginated_response(data: list, total: int, page: int = 1, page_size: int = 20, message: str = "Success") -> Dict[str, Any]:
        """分页响应格式"""
        return {
            "success": True,
            "code": 200,
            "message": message,
            "data": data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            },
            "timestamp": datetime.now().isoformat()
        }

def unified_response(func):
    """统一响应格式装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # 执行原函数
            result = await func(*args, **kwargs)
            
            # 如果结果已经是字典且包含success字段，直接返回
            if isinstance(result, dict) and 'success' in result:
                return result
            
            # 否则包装为成功响应
            return ResponseFormatter.success_response(data=result)
            
        except HTTPException as e:
            # FastAPI HTTP异常，保持原样抛出
            raise e
        except Exception as e:
            # 其他异常，记录日志并抛出HTTPException
            logger.error(f"API endpoint error: {str(e)}", exc_info=True)
            # 抛出HTTPException让FastAPI正确处理状态码
            raise HTTPException(status_code=500, detail="Internal server error")
    
    return wrapper

def format_market_data_response(data: Dict[str, Any], symbols: list) -> Dict[str, Any]:
    """格式化市场数据响应"""
    formatted_data = {}
    
    for symbol in symbols:
        if symbol in data:
            symbol_data = data[symbol]
            formatted_data[symbol] = {
                "symbol": symbol,
                "lastPrice": symbol_data.get("lastPrice"),
                "open": symbol_data.get("open"),
                "high": symbol_data.get("high"),
                "low": symbol_data.get("low"),
                "volume": symbol_data.get("volume"),
                "amount": symbol_data.get("amount"),
                "time": symbol_data.get("time"),
                "change": symbol_data.get("change"),
                "changePercent": symbol_data.get("changePercent")
            }
        else:
            formatted_data[symbol] = {
                "symbol": symbol,
                "error": "Data not available"
            }
    
    return formatted_data

def format_kline_response(data: Dict[str, Any], symbols: list) -> Dict[str, Any]:
    """格式化K线数据响应"""
    formatted_data = {}
    
    for symbol in symbols:
        if symbol in data:
            kline_data = data[symbol]
            if isinstance(kline_data, list):
                formatted_data[symbol] = {
                    "symbol": symbol,
                    "data": kline_data,
                    "count": len(kline_data)
                }
            else:
                formatted_data[symbol] = {
                    "symbol": symbol,
                    "data": [],
                    "count": 0,
                    "error": "Invalid data format"
                }
        else:
            formatted_data[symbol] = {
                "symbol": symbol,
                "data": [],
                "count": 0,
                "error": "Data not available"
            }
    
    return formatted_data

def format_trading_dates_response(data: Dict[str, Any], markets: list) -> Dict[str, Any]:
    """格式化交易日期响应"""
    formatted_data = {}
    
    for market in markets:
        if market in data:
            dates_data = data[market]
            if isinstance(dates_data, list):
                formatted_data[market] = {
                    "market": market,
                    "trading_dates": dates_data,
                    "count": len(dates_data)
                }
            else:
                formatted_data[market] = {
                    "market": market,
                    "trading_dates": [],
                    "count": 0,
                    "error": "Invalid data format"
                }
        else:
            formatted_data[market] = {
                "market": market,
                "trading_dates": [],
                "count": 0,
                "error": "Data not available"
            }
    
    return formatted_data