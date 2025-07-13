from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to Data Agent Service"}

@app.get("/api/v1/get_trading_dates")
async def get_trading_dates(market: str, start_date: str, end_date: str):
    return ["20250102", "20250103", "20250106"]

@app.get("/api/v1/hist_kline")
async def get_hist_kline(symbol: str, start_date: str, end_date: str, frequency: str):
    return [
        {"time": "20250630", "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.1, "volume": 1000, "amount": 10000},
        {"time": "20250701", "open": 10.1, "high": 10.3, "low": 9.9, "close": 10.2, "volume": 1200, "amount": 12000},
        {"time": "20250702", "open": 10.2, "high": 10.4, "low": 10.0, "close": 10.3, "volume": 1100, "amount": 11000},
        {"time": "20250703", "open": 10.3, "high": 10.5, "low": 10.1, "close": 10.4, "volume": 1300, "amount": 13000},
        {"time": "20250704", "open": 10.4, "high": 10.6, "low": 10.2, "close": 10.5, "volume": 1400, "amount": 14000},
    ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
