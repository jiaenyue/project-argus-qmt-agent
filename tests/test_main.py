from fastapi.testclient import TestClient
from data_agent_service.main import app # Import the FastAPI app instance

# Create a TestClient instance using the FastAPI app
client = TestClient(app)

def test_get_instrument_detail_success():
    """
    Test successful retrieval of instrument details for a known symbol.
    """
    symbol = "600519.SH"
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert data["displayName"] == "贵州茅台"
    assert "lastPrice" in data
    assert data["lastPrice"] == 1700.50

def test_get_instrument_detail_another_known_symbol():
    """
    Test successful retrieval for another known symbol.
    """
    symbol = "000001.SZ"
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert data["displayName"] == "平安银行"
    assert "lastPrice" in data
    assert data["lastPrice"] == 13.50

def test_get_instrument_detail_not_found():
    """
    Test retrieval of a non-existent symbol, expecting a 404 error.
    """
    symbol = "NONEXISTENT.EX"
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Instrument detail not found for symbol: {symbol} (tried xtdata and mock)"

def test_get_instrument_detail_unknown_symbol_mock_default():
    """
    Test retrieval of an unknown symbol that gets a default mock response.
    """
    symbol = "UNKNOWN.SYM"
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 200 # The mock provides a default, not a 404
    data = response.json()
    assert data["symbol"] == symbol
    assert data["displayName"] == "Unknown Instrument"
    assert data["lastPrice"] == 0.0

def test_get_instrument_detail_missing_symbol_parameter():
    """
    Test calling the endpoint without the required 'symbol' query parameter.
    FastAPI should handle this with a 422 Unprocessable Entity error.
    """
    response = client.get("/instrument_detail")
    assert response.status_code == 422 # FastAPI's default for missing required query parameters
    data = response.json()
    assert "detail" in data
    # Check if the detail message indicates that 'symbol' is missing
    # Example: {"detail":[{"loc":["query","symbol"],"msg":"field required","type":"value_error.missing"}]}
    assert any(err["loc"] == ["query", "symbol"] and "missing" in err["type"] for err in data["detail"])


def test_read_main_root():
    """
    Test the root endpoint if it exists (FastAPI default app doesn't have one unless added).
    Let's add a root endpoint to main.py for basic app health check.
    This test will currently fail as there is no "/" endpoint.
    We will add it in the next step for completeness.
    """
    # First, let's check if the root endpoint is actually defined in our app.
    # If not, this test is not applicable or should be for a 404.
    # For now, assuming we will add a root endpoint.
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Data Agent Service"}

# To run tests using pytest:
# 1. Make sure you are in the root directory of the project.
# 2. Ensure 'pytest' is installed (pip install pytest).
# 3. Run: pytest
#
# If you encounter import errors like "ModuleNotFoundError: No module named 'data_agent_service'",
# ensure your PYTHONPATH is set up correctly, or run pytest with:
# PYTHONPATH=. pytest tests/
# or install the package in editable mode: pip install -e . (if you have a setup.py)
# For simple projects, running `pytest` from the root directory usually works if using standard project structure.
