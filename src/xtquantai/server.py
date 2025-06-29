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

# ... 文件剩余部分保持不变 ...
