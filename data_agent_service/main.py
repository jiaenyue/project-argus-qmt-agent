from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Initialize xtquant (this might need to be done differently based on xtquant's requirements)
# For now, we will mock its behavior.
try:
    from xtquant import xtdata
    print("[xtquant] xtdata imported successfully.")
except ImportError as e:
    print(f"[xtquant] Failed to import xtdata: {e}. Will rely on mock.")
    xtdata = None # Ensure xtdata exists as a variable, even if None

app = FastAPI(
    title="Data Agent Service",
    description="API proxy for financial data, initially for xtquant functionalities.",
    version="0.1.0",
)

@app.get("/", summary="Root", description="A simple health check endpoint.")
async def read_root():
    return {"message": "Welcome to Data Agent Service"}

# --- Mock xtquant.xtdata ---
class XTDataMock:
    def get_instrument_detail(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Mocked version of xtquant.xtdata.get_instrument_detail.
        Returns detailed information for a given instrument symbol.
        """
        print(f"[Mock xtdata] get_instrument_detail called for symbol: {symbol}")
        if symbol == "600519.SH":
            return {
                "symbol": symbol,
                "displayName": "贵州茅台",
                "lastPrice": 1700.50,
                "openPrice": 1710.00,
                "highPrice": 1720.80,
                "lowPrice": 1690.00,
                "closePrice": 1705.30, # Previous day's close
                "volume": 100000,
                "amount": 170050000.00,
                "timestamp": "2023-10-27 15:00:00" # Example timestamp
            }
        elif symbol == "000001.SZ":
            return {
                "symbol": symbol,
                "displayName": "平安银行",
                "lastPrice": 13.50,
                "openPrice": 13.60,
                "highPrice": 13.70,
                "lowPrice": 13.40,
                "closePrice": 13.55,
                "volume": 500000,
                "amount": 67500000.00,
                "timestamp": "2023-10-27 15:00:00"
            }
        elif symbol == "NONEXISTENT.EX": # For testing not found cases
            return None
        else:
            # Default mock response for other symbols
            return {
                "symbol": symbol,
                "displayName": "Unknown Instrument",
                "lastPrice": 0.0,
                "openPrice": 0.0,
                "highPrice": 0.0,
                "lowPrice": 0.0,
                "closePrice": 0.0,
                "volume": 0,
                "amount": 0.0,
                "timestamp": "N/A"
            }

xtdata_mock = XTDataMock()
# --- End Mock xtquant.xtdata ---


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

@app.get(
    "/instrument_detail",
    response_model=Optional[InstrumentDetailResponse],
    summary="Get Instrument Detail",
    description="Fetches real-time detailed information for a given instrument symbol, similar to `xtquant.xtdata.get_instrument_detail`."
)
async def get_instrument_detail(symbol: str):
    """
    Retrieves detailed information for a specific instrument.

    - **symbol**: The instrument symbol (e.g., "600519.SH").
    """
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol query parameter is required.")

    # In a real scenario, you would call the actual xtquant function:
    detail = None
    if xtdata: # Check if xtdata was imported successfully
        try:
            # Attempt to use the actual xtquant function
            detail_xt = xtdata.get_instrument_detail(symbol)
            print(f"[xtdata] Successfully called get_instrument_detail for symbol: {symbol}")

            if detail_xt is None or (isinstance(detail_xt, dict) and not detail_xt): # Check for None or empty dict
                print(f"[xtdata] get_instrument_detail for {symbol} returned None or empty.")
                # If xtdata returns no data, it's a 404 for that specific symbol from xtdata's perspective
                raise HTTPException(status_code=404, detail=f"Instrument detail not found for symbol: {symbol} (xtdata returned no data)")
            detail = detail_xt

        except HTTPException: # Re-raise HTTPException (like the 404 above)
            raise
        except Exception as e:
            print(f"[xtdata] Error calling xtdata.get_instrument_detail for symbol {symbol}: {e}")
            print("[xtdata] Falling back to mock due to xtdata error.")
            # Fallback to mock if xtdata call fails with an unexpected error
            detail = xtdata_mock.get_instrument_detail(symbol)
    else:
        # xtdata was not imported, rely solely on mock
        print("[xtdata] xtdata module not available. Using mock.")
        detail = xtdata_mock.get_instrument_detail(symbol)

    if detail is None: # This can happen if mock also returns None
        raise HTTPException(status_code=404, detail=f"Instrument detail not found for symbol: {symbol} (tried xtdata and mock)")

    # Ensure the response matches the Pydantic model if possible,
    # or that the Pydantic model is flexible enough.
    # If xtdata.get_instrument_detail returns a dict with different keys,
    # a transformation step would be needed here before returning.
    # For now, we assume the structure is compatible or the mock is used.

    return detail

# Example to run the app with uvicorn (for development):
# uvicorn data_agent_service.main:app --reload
# Or from the project root:
# python -m uvicorn data_agent_service.main:app --reload
#
# Access the API at http://localhost:8000/instrument_detail?symbol=600519.SH
# Access the auto-generated docs at http://localhost:8000/docs
# or http://localhost:8000/redoc
