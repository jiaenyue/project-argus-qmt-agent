import pytest
from data_agent_service.main import app
from fastapi.testclient import TestClient
from unittest.mock import patch

client = TestClient(app)

# 定义完整的mock返回数据
MOCK_LATEST_MARKET_DATA = {
    "600519.SH": {
        "time": "2023-01-01 15:00:00",
        "lastPrice": 1700.0,
        "volume": 100000,
        "amount": 170000000.0,
        "open": 1690.0,
        "high": 1710.0,
        "low": 1680.0
    },
    "000001.SZ": {
        "time": "2023-01-01 15:00:00",
        "lastPrice": 13.5,
        "volume": 2000000,
        "amount": 27000000.0,
        "open": 13.4,
        "high": 13.6,
        "low": 13.3
    }
}

def test_get_latest_market_success_single_symbol():
    """测试成功获取单个股票的最新行情"""
    with patch('data_agent_service.main.xtdata.get_market_data') as mock_method:
        mock_method.return_value = {
            'time': {'600519.SH': ["2023-01-01 15:00:00"]},
            'lastPrice': {'600519.SH': [1700.0]},
            'volume': {'600519.SH': [100000]},
            'amount': {'600519.SH': [170000000.0]},
            'open': {'600519.SH': [1690.0]},
            'high': {'600519.SH': [1710.0]},
            'low': {'600519.SH': [1680.0]}
        }
        response = client.get("/latest_market?symbols=600519.SH")
        assert response.status_code == 200
        data = response.json()
        assert "600519.SH" in data
        assert data["600519.SH"]["lastPrice"] == 1700.0
        assert data["600519.SH"]["volume"] == 100000
        assert data["600519.SH"]["open"] == 1690.0

def test_get_latest_market_success_multiple_symbols():
    """测试成功获取多个股票的最新行情"""
    with patch('data_agent_service.main.xtdata.get_market_data') as mock_method:
        mock_method.return_value = {
            'time': {
                '600519.SH': ["2023-01-01 15:00:00"],
                '000001.SZ': ["2023-01-01 15:00:00"]
            },
            'lastPrice': {'600519.SH': [1700.0], '000001.SZ': [13.5]},
            'volume': {'600519.SH': [100000], '000001.SZ': [2000000]},
            'amount': {'600519.SH': [170000000.0], '000001.SZ': [27000000.0]},
            'open': {'600519.SH': [1690.0], '000001.SZ': [13.4]},
            'high': {'600519.SH': [1710.0], '000001.SZ': [13.6]},
            'low': {'600519.SH': [1680.0], '000001.SZ': [13.3]}
        }
        response = client.get("/latest_market?symbols=600519.SH,000001.SZ")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "600519.SH" in data
        assert "000001.SZ" in data
        assert data["000001.SZ"]["lastPrice"] == 13.5

def test_get_latest_market_partial_found():
    """测试部分股票代码有效"""
    with patch('data_agent_service.main.xtdata.get_market_data') as mock_method:
        mock_method.return_value = {
            'time': {'600519.SH': ["2023-01-01 15:00:00"]},
            'lastPrice': {'600519.SH': [1700.0]},
            'volume': {'600519.SH': [100000]},
            'amount': {'600519.SH': [170000000.0]},
            'open': {'600519.SH': [1690.0]},
            'high': {'600519.SH': [1710.0]},
            'low': {'600519.SH': [1680.0]}
        }
        response = client.get("/latest_market?symbols=600519.SH,000000.SZ")
        assert response.status_code == 200
        data = response.json()
        assert "600519.SH" in data
        assert "000000.SZ" in data  # 现在所有请求的股票都会返回
        assert data["600519.SH"]["lastPrice"] == 1700.0
        assert data["000000.SZ"]["lastPrice"] is None  # 未找到的股票字段为空

def test_get_latest_market_none_found():
    """测试所有股票代码均无效或无数据"""
    with patch('data_agent_service.main.xtdata.get_market_data') as mock_method:
        mock_method.return_value = {}  # 返回空数据
        response = client.get("/latest_market?symbols=000000.SH,000000.SZ")
        assert response.status_code == 200
        data = response.json()
        assert "000000.SH" in data
        assert "000000.SZ" in data
        assert data["000000.SH"]["lastPrice"] is None

def test_get_latest_market_invalid_symbol_format():
    """测试无效的股票代码格式"""
    response = client.get("/latest_market?symbols=INVALID")
    assert response.status_code == 400
    assert "Invalid symbol format" in response.json()["detail"]

def test_get_latest_market_empty_symbols_param():
    """测试symbols参数为空"""
    response = client.get("/latest_market?symbols=")
    assert response.status_code == 400
    assert "symbols query parameter cannot be empty" in response.json()["detail"]  # 更新断言文本

def test_get_latest_market_missing_symbols_param():
    """测试缺少必需的symbols参数"""
    response = client.get("/latest_market")
    assert response.status_code == 400
    assert "symbols query parameter is required" in response.json()["detail"]

def test_get_latest_market_xtdata_exception():
    """测试xtdata内部异常"""
    with patch('data_agent_service.main.xtdata.get_market_data') as mock_method:
        mock_method.side_effect = Exception("Mock exception")
        response = client.get("/latest_market?symbols=600519.SH")
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
