import pytest
from data_agent_service.main import app
from fastapi.testclient import TestClient
from unittest.mock import patch

client = TestClient(app)

# Mock data for successful response
MOCK_FULL_MARKET_DATA = {
    "600519.SH": {
        "open": 1700.0,
        "high": 1720.0,
        "low": 1690.0,
        "close": 1710.0,
        "volume": 100000
    }
}

def test_get_full_market_success_no_fields():
    """测试成功获取完整行情数据（不指定fields参数）"""
    with patch('data_agent_service.main.xtdata.get_full_market_data') as mock_method:
        mock_method.return_value = MOCK_FULL_MARKET_DATA
        response = client.get("/full_market?symbol=600519.SH")
        assert response.status_code == 200
        data = response.json()
        assert "open" in data
        assert "high" in data
        assert "low" in data
        assert "close" in data
        assert "volume" in data

def test_get_full_market_success_with_fields():
    """测试成功获取完整行情数据（指定fields参数）"""
    with patch('data_agent_service.main.xtdata.get_full_market_data') as mock_method:
        mock_method.return_value = {"600519.SH": {"open": 1700.0, "high": 1720.0, "low": 1690.0, "close": 1710.0}}
        response = client.get("/full_market?symbol=600519.SH&fields=open,high,low,close")
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == set(['open', 'high', 'low', 'close'])
        assert data["open"] == 1700.0
        assert data["high"] == 1720.0
        assert data["low"] == 1690.0
        assert data["close"] == 1710.0

def test_get_full_market_not_found():
    """测试股票代码无效或无数据"""
    with patch('data_agent_service.main.xtdata.get_full_market_data') as mock_method:
        mock_method.return_value = {}
        response = client.get("/full_market?symbol=000000.SH")  # 使用有效格式的股票代码
        assert response.status_code == 404
        assert "Data not found" in response.json()["detail"]

def test_get_full_market_invalid_symbol_format():
    """测试股票代码格式无效"""
    response = client.get("/full_market?symbol=INVALID")
    assert response.status_code == 400
    assert "Invalid symbol format" in response.json()["detail"]

def test_get_full_market_missing_symbol_param():
    """测试缺少必需的symbol参数"""
    response = client.get("/full_market")
    assert response.status_code == 400
    assert "symbol query parameter is required" in response.json()["detail"]

def test_get_full_market_empty_fields_param():
    """测试fields参数为空（仅包含逗号）"""
    response = client.get("/full_market?symbol=600519.SH&fields=,, ,")
    assert response.status_code == 400
    assert "Fields parameter, if provided, cannot be empty or only commas" in response.json()["detail"]

def test_get_full_market_xtdata_exception():
    """测试xtdata内部异常"""
    with patch('data_agent_service.main.xtdata.get_full_market_data') as mock_method:
        mock_method.side_effect = Exception("Mock exception")
        response = client.get("/full_market?symbol=600519.SH")
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
