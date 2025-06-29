from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import re
from xtquant import xtdata # 添加导入

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 处理参数验证错误
    # errors = []
    # for error in exc.errors():
    #     param_name = error["loc"][-1] # 获取参数名
    #     errors.append(f"{param_name} query parameter is required")

    # if errors:
    #     return JSONResponse(
    #         status_code=400,
    #         content={"detail": "; ".join(errors)},
    #     )
    # 返回原始的FastAPI验证错误以获取更详细的信息
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)

@app.get("/")
async def read_root():
    return {"message": "Welcome to Data Agent Service"}

class InstrumentDetailResponse(BaseModel):
    symbol: str
    displayName: str
    lastPrice: float
    openPrice: float
    highPrice: float
    lowPrice: float
    closePrice: float
    volume: int
    amount: float
    timestamp: str

@app.get("/instrument_detail")
async def get_instrument_detail(symbol: str = Query(..., min_length=1)):
    try:
        # 验证symbol格式
        if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', symbol.upper()): # 转换为大写以匹配常见格式
            raise HTTPException(status_code=400, detail="Invalid symbol format. Expected format like '600519.SH' or '000001.SZ'.")
        
        # 初始化xtdata（如果尚未初始化）
        # xtdata.init() # 实际项目中根据需要进行初始化管理

        detail = xtdata.get_instrument_detail(symbol.upper()) # 使用xtquant.xtdata
        
        if detail is None or not isinstance(detail, dict) or not detail: # xtquant可能返回None或空字典
            raise HTTPException(status_code=404, detail=f"Instrument not found or no data available for: {symbol}")
        
        # Pydantic模型验证（如果启用了response_model）会处理字段缺失/类型错误
        # 这里可以直接返回detail，FastAPI会尝试匹配InstrumentDetailResponse
        return detail
    except HTTPException:
        # 直接重新抛出HTTPException，让FastAPI处理
        raise
    except Exception as e:
        # 记录异常信息到日志会更好
        # print(f"Error in get_instrument_detail: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching instrument detail for: {symbol}")

@app.get("/stock_list", response_model=List[str])
async def get_stock_list_in_sector(sector: str = Query(..., min_length=1, description="Sector name, e.g., '沪深A股'")):
    try:
        # 初始化xtdata（如果尚未初始化）
        # xtdata.init() # 实际项目中根据需要进行初始化管理

        stock_list = xtdata.get_stock_list_in_sector(sector)
        if not stock_list: # xtquant在找不到板块或板块内无股票时返回空列表
            # 返回空列表符合预期，表示该板块下没有股票，不应视为404错误
            # 如果确实需要区分“板块不存在”和“板块内无股票”，xtquant本身可能不直接提供此区分
            # 此处我们遵循xtquant的行为，返回空列表
            pass # 继续执行并返回空列表
        return stock_list
    except HTTPException:
        raise
    except Exception as e:
        # 记录异常信息到日志会更好
        # print(f"Error in get_stock_list_in_sector: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching stock list for sector: {sector}")

# 故事 1.6: 获取最新行情数据
# API调用示例: requests.get("http://data-agent-service/latest_market", params={"symbols": "600519.SH,000001.SZ"})
# 对应 xtquant.xtdata.get_latest_market_data 功能
@app.get("/latest_market") # Pydantic模型可以稍后根据xtquant返回的具体结构定义
async def get_latest_market_data(symbols: str = Query(..., description="Comma-separated list of stock symbols, e.g., '600519.SH,000001.SZ'")):
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="Symbols query parameter cannot be empty.")

        # 验证每个symbol的格式
        for symbol in symbol_list:
            if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', symbol):
                raise HTTPException(status_code=400, detail=f"Invalid symbol format: {symbol}. Expected format like '600519.SH'.")

        # 初始化xtdata（如果尚未初始化）
        # xtdata.init() # 实际项目中根据需要进行初始化管理

        market_data = xtdata.get_latest_market_data(symbol_list)

        # xtquant.get_latest_market_data 返回一个字典，键是股票代码，值是行情数据
        # 如果某个股票代码无效或无数据，它可能不在返回的字典中，或者对应的值是特殊标记（需查阅xtquant文档）
        # 这里我们假设如果xtquant调用成功，就返回其结果，客户端负责处理可能存在的缺失数据
        if not market_data: # 如果返回空字典
             raise HTTPException(status_code=404, detail=f"No market data found for symbols: {symbols}")

        return market_data
    except HTTPException:
        raise
    except Exception as e:
        # print(f"Error in get_latest_market_data: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching latest market data for symbols: {symbols}")

# 故事 1.7: 获取完整行情数据
# API调用示例: requests.get("http://data-agent-service/full_market", params={"symbol": "600519.SH", "fields": "open,high,low,close,volume"})
# 对应 xtquant.xtdata.get_full_market_data 功能
@app.get("/full_market") # Pydantic模型可以稍后根据xtquant返回的具体结构定义
async def get_full_market_data_endpoint(
    symbol: str = Query(..., description="Stock symbol, e.g., '600519.SH'"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields, e.g., 'open,high,low,close,volume'")
):
    try:
        upper_symbol = symbol.strip().upper()
        if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', upper_symbol):
            raise HTTPException(status_code=400, detail=f"Invalid symbol format: {symbol}. Expected format like '600519.SH'.")

        field_list = []
        if fields:
            field_list = [f.strip() for f in fields.split(',') if f.strip()]
            if not field_list and fields.strip() != "": # 用户提供了fields参数但解析后为空列表 (例如 ",, ,")
                 raise HTTPException(status_code=400, detail="Fields parameter, if provided, cannot be empty or only commas.")


        # 初始化xtdata（如果尚未初始化）
        # xtdata.init() # 实际项目中根据需要进行初始化管理

        # xtquant.xtdata.get_full_market_data 需要一个股票代码列表作为第一个参数
        # 即使我们只查询单个股票，也要传递列表
        if field_list:
            market_data = xtdata.get_full_market_data([upper_symbol], fields=field_list)
        else:
            market_data = xtdata.get_full_market_data([upper_symbol]) # 获取所有可用字段

        # get_full_market_data 返回一个字典，键是股票代码，值是包含字段和其值的字典
        # 如果股票代码无效或无数据，它可能不在返回的字典中，或其值可能表示无数据
        if not market_data or upper_symbol not in market_data or not market_data[upper_symbol]:
            raise HTTPException(status_code=404, detail=f"No full market data found for symbol: {symbol} with specified fields.")

        # API 返回单个股票的数据，所以直接返回该股票对应的数据字典
        return market_data[upper_symbol]
    except HTTPException:
        raise
    except Exception as e:
        # print(f"Error in get_full_market_data_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error while fetching full market data for symbol: {symbol}")
