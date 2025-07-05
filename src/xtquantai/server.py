import asyncio  
from typing import Optional, List, Dict, Any  
import json  
import sys  
import os  
import traceback  
import time  
import re  

from mcp.server.models import InitializationOptions  
import mcp.types as types  
from mcp.server import NotificationOptions, Server  
  
from fastapi import APIRouter, Query  
from pydantic import AnyUrl, BaseModel, Field, ValidationError  
# from xtquant import xtdata # 延迟导入或包装导入
# from xtquant import xttrader # 延迟导入或包装导入

# 尝试导入xtquant，如果失败则使用模拟对象
try:
    from xtquant import xtdata
    from xtquant import xttrader
except ImportError:
    # print("Warning: Failed to import xtquant. Using mock objects for xtdata and xttrader.")
    from unittest.mock import MagicMock
    xtdata = MagicMock()
    xttrader = MagicMock()
    # 你可以在这里为模拟的xtdata和xttrader设置一些默认行为，如果需要的话
    # 例如:
    # xtdata.get_trading_dates.return_value = []
    # xtdata.get_instrument_detail.return_value = None

def ensure_xtdc_initialized():  
    # ... 保持不变 ...  
    pass  

class XTQuantAIHandler:  
    @staticmethod  
    def get_trading_dates(market: str, start_date: str, end_date: str):  
        ensure_xtdc_initialized()  
        try:  
            # 参数验证  
            if not market:  
                return {"success": False, "message": "market is required", "status": 400}  
                
            # 处理空日期参数  
            start_date = start_date.strip() if start_date else ""
            end_date = end_date.strip() if end_date else ""
            
            # 验证日期格式（仅当日期非空时）  
            date_pattern = re.compile(r"^\d{8}$")  
            if start_date and not date_pattern.match(start_date):  
                return {"success": False, "message": "start_date must be in YYYYMMDD format", "status": 400}  
            if end_date and not date_pattern.match(end_date):  
                return {"success": False, "message": "end_date must be in YYYYMMDD format", "status": 400}  
                
            # 转换空日期为None  
            start_date = start_date if start_date else None
            end_date = end_date if end_date else None

            # 调用xtquant接口获取交易日历  
            trading_dates = xtdata.get_trading_dates(market, start_date, end_date)  
            return {  
                "success": True,  
                "data": trading_dates,  # 直接返回列表，无需tolist()  
                "status": 200  
            }  
        except Exception as e:  
            traceback.print_exc()  
            return {  
                "success": False,  
                "message": f"Failed to fetch trading dates: {str(e)}",  
                "status": 500  
            }  

    @staticmethod  
    def get_hist_kline(symbol: str = None, start_date: str = None, end_date: str = None, frequency: str = None):  
        ensure_xtdc_initialized()  
        try:  
            # 参数验证  
            if symbol is None:  
                return {"success": False, "message": "symbol is required", "status": 400}  
            if start_date is None:  
                return {"success": False, "message": "start_date is required", "status": 400}  
            if end_date is None:  
                return {"success": False, "message": "end_date is required", "status": 400}  
            if frequency is None:  
                return {"success": False, "message": "frequency is required", "status": 400}  

            # 验证日期格式  
            date_pattern = re.compile(r"^\d{8}$")  
            if not date_pattern.match(start_date):  
                return {"success": False, "message": "start_date must be in YYYYMMDD format", "status": 400}  
            if not date_pattern.match(end_date):  
                return {"success": False, "message": "end_date must be in YYYYMMDD format", "status": 400}  

            # 调用xtquant接口获取K线数据  
            print(f"调用xtquant接口: symbol={symbol}, frequency={frequency}, start_date={start_date}, end_date={end_date}")  
            df = xtdata.get_history_market_data(symbol, frequency, start_date, end_date)  
            print(f"获取K线数据成功，行数: {len(df)}")  

            # 转换为测试期望的格式  
            data = []  
            for index, row in df.iterrows():  
                data.append({  
                    "time": str(index),  
                    "open": row['open'],  
                    "high": row['high'],  
                    "low": row['low'],  
                    "close": row['close'],  
                    "volume": row['volume']  
                })  

            return {  
                "success": True,  
                "data": data,  
                "status": 200  
            }  
        except Exception as e:  
            traceback.print_exc()  
            return {  
                "success": False,  
                "message": f"Failed to fetch historical kline data: {str(e)}",  
                "status": 500  
            }  

    @staticmethod  
    def get_instrument_detail(symbol: str = None):  
        ensure_xtdc_initialized()  
        try:  
            # 参数验证  
            if symbol is None:  
                return {"success": False, "message": "symbol is required", "status": 400}  
            
            # 调用xtquant接口获取股票详情
            detail = xtdata.get_instrument_detail(symbol)
            
            if not detail:
                return {
                    "success": False,
                    "message": f"Instrument detail not found for symbol: {symbol}",
                    "status": 404
                }
                
            # 返回结构化数据
            return {  
                "success": True,  
                "data": {
                    "symbol": detail.get("symbol", ""),
                    "name": detail.get("name", ""),
                    "exchange": detail.get("exchange", ""),
                    "type": detail.get("type", ""),
                    "list_date": detail.get("list_date", ""),
                    "delist_date": detail.get("delist_date", ""),
                    # 包含其他原始字段
                    **detail
                },  
                "status": 200  
            }  
        except Exception as e:  
            traceback.print_exc()  
            return {  
                "success": False,  
                "message": f"Failed to fetch instrument detail: {str(e)}",  
                "status": 500  
            }

    @staticmethod
    def get_stock_list(sector: str = Query(..., description="板块名称")):
        ensure_xtdc_initialized()
        try:
            # 调用xtquant接口获取板块股票列表
            stock_list = xtdata.get_stock_list_in_sector(sector)
            
            # 处理空列表情况（返回空数组而非错误）
            if stock_list is None:
                stock_list = []
                
            return {
                "success": True,
                "data": {
                    "sector": sector,
                    "stocks": stock_list
                },
                "status": 200
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Failed to fetch stock list: {str(e)}",
                "status": 500
            }
    @staticmethod
    def get_latest_market(symbols: str = Query(..., description="股票代码列表，逗号分隔")):
        ensure_xtdc_initialized()
        try:
            # 参数验证
            if not symbols:
                return {"success": False, "message": "symbols is required", "status": 400}
                
            # 分割股票代码
            symbol_list = [s.strip() for s in symbols.split(',') if s.strip()]
            
            # 调用XTQuant API获取最新行情
            market_data = xtdata.get_latest_market_data(symbol_list)
            
            # 转换数据结构
            result_data = {}
            for symbol in symbol_list:
                data_item = market_data.get(symbol)
                if data_item:
                    # 提取所需字段（根据XTQuant返回的字段名）
                    result_data[symbol] = {
                        "price": data_item.get("lastPrice"),      # 最新价
                        "volume": data_item.get("volume"),        # 成交量
                        "amount": data_item.get("amount"),        # 成交额
                        "open": data_item.get("openPrice"),       # 开盘价
                        "high": data_item.get("highPrice"),       # 最高价
                        "low": data_item.get("lowPrice"),         # 最低价
                        "prevClose": data_item.get("prevClosePrice")  # 前收盘价
                    }
                else:
                    # 处理部分股票查询失败
                    result_data[symbol] = {"error": "No data available"}
            
            return {
                "success": True,
                "data": result_data,
                "status": 200
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Failed to fetch latest market data: {str(e)}",
                "status": 500
            }

    @staticmethod
    def get_full_market(
        symbol: str = Query(..., description="股票代码"),
        fields: str = Query(None, description="可选字段列表，逗号分隔")
    ):
        ensure_xtdc_initialized()
        try:
            # 参数验证
            if not symbol:
                return {"success": False, "message": "symbol is required", "status": 400}

            # 调用xtquant接口获取全市场数据
            full_market_data = xtdata.get_full_market_data(symbol)
            if full_market_data is None:
                return {"success": False, "message": f"No full market data for symbol: {symbol}", "status": 404}

            # 如果指定了fields，则过滤字段
            if fields:
                field_list = [f.strip() for f in fields.split(',') if f.strip()]
                # 创建过滤后的数据字典
                filtered_data = {}
                for field in field_list:
                    if field in full_market_data:
                        filtered_data[field] = full_market_data[field]
                return {
                    "success": True,
                    "data": filtered_data,
                    "status": 200
                }
            else:
                return {
                    "success": True,
                    "data": full_market_data,
                    "status": 200
                }
        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Failed to fetch full market data: {str(e)}",
                "status": 500
            }

# 注册API路由
router = APIRouter()
router.get("/trading_dates")(XTQuantAIHandler.get_trading_dates)
router.get("/hist_kline")(XTQuantAIHandler.get_hist_kline)
router.get("/instrument_detail")(XTQuantAIHandler.get_instrument_detail)
router.get("/stock_list")(XTQuantAIHandler.get_stock_list)
router.get("/latest_market")(XTQuantAIHandler.get_latest_market)
router.get("/full_market")(XTQuantAIHandler.get_full_market)

# (文件末尾空行)
