from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import re
from xtquant import xtdata
import logging
import traceback
import numpy as np

# 配置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

app = FastAPI()

# 统一响应格式装饰器
def unified_response(func):
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return {"success": True, "data": result}
        except HTTPException as e:
            return {"success": False, "error": e.detail, "code": e.status_code}
        except Exception as e:
            logger.error(f"API error: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e), "code": 500}
    return wrapper

@app.get("/")
@unified_response
async def read_root():
    return {"message": "Welcome to Data Agent Service"}

@app.get("/instrument_detail")
@unified_response
async def get_instrument_detail(symbol: str = Query(..., min_length=1)):
    upper_symbol = symbol.upper()
    if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', upper_symbol):
        raise HTTPException(status_code=400, detail="Invalid symbol format. Expected format like '600519.SH' or '000001.SZ'.")
    
    detail = xtdata.get_instrument_detail(upper_symbol)
    
    if detail is None or detail == {}:
        raise HTTPException(status_code=404, detail=f"Instrument not found: {symbol}")
    
    # 获取最新交易日K线数据
    # 使用 get_full_kline 获取最新日线数据，包含开盘、收盘、最高、最低、成交量、成交额
    kline_data = xtdata.get_full_kline(
        field_list=['open', 'high', 'low', 'close', 'volume', 'amount', 'time'],
        stock_list=[upper_symbol],
        period='1d', # 获取日线数据
        count=1 # 获取最新一条
    )
    
    # 从kline_data中提取数据，并提供默认值
    # kline_data 的结构是 {field: {symbol: [value]}}
    last_price = kline_data.get('close', {}).get(upper_symbol, [0.0])[0]
    open_price = kline_data.get('open', {}).get(upper_symbol, [0.0])[0]
    high_price = kline_data.get('high', {}).get(upper_symbol, [0.0])[0]
    low_price = kline_data.get('low', {}).get(upper_symbol, [0.0])[0]
    volume = kline_data.get('volume', {}).get(upper_symbol, [0])[0]
    amount = kline_data.get('amount', {}).get(upper_symbol, [0.0])[0]
    timestamp = kline_data.get('time', {}).get(upper_symbol, [0])[0]

    pre_close = detail.get("PreClose", 0.0) # 获取前收盘价
    
    change_percent = 0.0
    if pre_close and last_price is not None:
        if pre_close != 0:
            change_percent = ((last_price - pre_close) / pre_close) * 100
        else:
            change_percent = 0.0 # 如果前收盘价为0，则涨跌幅为0

    return {
        "symbol": detail.get("InstrumentID", symbol),
        "name": detail.get("InstrumentName", symbol),
        "last_price": last_price,
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "close_price": last_price, # 通常最新价和收盘价在日线数据中是一致的
        "volume": volume,
        "amount": amount,
        "timestamp": timestamp,
        "change_percent": change_percent # 添加涨跌幅
    }

@app.get("/stock_list")
@unified_response
async def get_stock_list_insector(sector: str = Query(..., min_length=1, description="Sector name, e.g., '沪深A股'")):
    stock_list = xtdata.get_stock_list_in_sector(sector)
    return stock_list or []

@app.get("/latest_market")
@unified_response
async def get_latest_market_data(symbols: str = Query(..., description="Comma-separated list of stock symbols, e.g., '600519.SH,000001.SZ'")):
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

@app.get("/full_market")
@unified_response
async def get_full_market_data_endpoint(
    symbol: str = Query(..., description="Stock symbol, e.g., '600519.SH'"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields, e.g., 'open,high,low,close,volume'")
):
    upper_symbol = symbol.strip().upper()
    if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', upper_symbol):
        raise HTTPException(status_code=400, detail=f"Invalid symbol format: {symbol}")
    
    # 处理字段参数
    field_list = []
    if fields:
        field_list = [f.strip() for f in fields.split(',') if f.strip()]
        if not field_list:
            raise HTTPException(status_code=400, detail="Fields parameter, if provided, cannot be empty or only commas")
    
    if not field_list:
        field_list = ["open", "high", "low", "close", "volume"]
    
    # 获取完整行情数据
    market_data = xtdata.get_full_market_data(field_list, [upper_symbol], period='1d')
    
    if not market_data or upper_symbol not in market_data:
        raise HTTPException(status_code=404, detail="Data not found")
    
    # 直接返回字段对象
    result = {}
    for field in field_list:
        if field in market_data[upper_symbol]:
            value = market_data[upper_symbol][field]
            if isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.floating):
                value = float(value)
            result[field] = value
    
    return result

# 新增交易日历接口
@app.get("/api/v1/get_trading_dates")
@unified_response
async def get_trading_dates(market: str, start_date: str, end_date: str):
    # 实现交易日历获取逻辑（示例）
    return ["20250102", "20250103", "20250106"]

# 新增K线数据接口
@app.get("/api/v1/hist_kline")
@unified_response
async def get_hist_kline(symbol: str, start_date: str, end_date: str, frequency: str):
    # 实现K线数据获取逻辑（示例）
    return [
        {"date": "20250102", "open": 10.2, "close": 10.5},
        {"date": "20250103", "open": 10.6, "close": 10.8}
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
