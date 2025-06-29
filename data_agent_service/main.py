from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import re

class XTDataMock:
    def get_instrument_detail(self, symbol: str) -> Optional[Dict[str, Any]]:
        symbol_upper = symbol.upper()
        if symbol_upper == "600519.SH":
            return {
                "symbol": symbol,
                "displayName": "Guizhou Maotai",
                "lastPrice": 1700.50,
                "openPrice": 1710.00,
                "highPrice": 1720.80,
                "lowPrice": 1690.00,
                "closePrice": 1705.30,
                "volume": 100000,
                "amount": 170050000.00,
                "timestamp": "2023-10-27 15:00:00"
            }
        elif symbol_upper == "000001.SZ":
            return {
                "symbol": symbol,
                "displayName": "Ping An Bank",
                "lastPrice": 13.50,
                "openPrice": 13.60,
                "highPrice": 13.70,
                "lowPrice": 13.40,
                "closePrice": 13.55,
                "volume": 500000,
                "amount": 67500000.00,
                "timestamp": "2023-10-27 15:00:00"
            }
        return None

xtdata_mock = XTDataMock()

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 只处理参数验证错误（如参数缺失）
    if any(error["loc"] == ("query", "symbol") and error["type"] == "missing" for error in exc.errors()):
        return JSONResponse(
            status_code=400,
            content={"detail": "Symbol query parameter is required"},
        )
    # 其他验证错误保持默认处理
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

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
        if not re.match(r'^[A-Z0-9]{6}\.[A-Z]{2}$', symbol):
            raise HTTPException(status_code=400, detail="Invalid symbol format")
        
        detail = xtdata_mock.get_instrument_detail(symbol)
        
        if detail is None:
            raise HTTPException(status_code=404, detail=f"Instrument not found: {symbol}")
        
        return detail
    except HTTPException:
        # 直接重新抛出HTTPException，让FastAPI处理
        raise
    except Exception as e:
        # 处理其他未捕获的异常
        raise HTTPException(status_code=500, detail="Internal server error")
