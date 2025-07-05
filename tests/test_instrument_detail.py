import pytest
from data_agent_service.main import app
from fastapi.testclient import TestClient
from unittest.mock import patch

client = TestClient(app)

def test_get_instrument_detail_success():
    """测试成功获取证券详情"""
    with patch('data_agent_service.main.xtdata.get_instrument_detail') as mock_get_detail, \
         patch('data_agent_service.main.xtdata.get_market_data') as mock_market:
        
        # 设置mock数据
        mock_get_detail.return_value = {
            "InstrumentID": "600519.SH",
            "InstrumentName": "贵州茅台"
        }
        mock_market.return_value = {
            'lastPrice': {'600519.SH': [1700.0]},
            'open': {'600519.SH': [1690.0]},
            'high': {'600519.SH': [1710.0]},
            'low': {'600519.SH': [1680.0]},
            'volume': {'600519.SH': [100000]},
            'amount': {'600519.SH': [170000000.0]},
            'time': {'600519.SH': ["2023-01-01 15:00:00"]}
        }
        
        response = client.get("/instrument_detail?symbol=600519.SH")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "600519.SH"
        assert data["displayName"] == "贵州茅台"
        assert data["lastPrice"] == 1700.0
        assert data["openPrice"] == 1690.0
        assert data["highPrice"] == 1710.0
        assert data["lowPrice"] == 1680.0
        assert data["volume"] == 100000
        assert data["amount"] == 170000000.0
        assert data["timestamp"] == "2023-01-01 15:00:00"

def test_get_instrument_detail_not_found():
    """测试检索不存在的证券 (xtdata返回None)"""
    with patch('data_agent_service.main.xtdata.get_instrument_detail') as mock_get_detail:
        symbol = "000000.SH"  # 使用有效格式的股票代码
        mock_get_detail.return_value = None
        response = client.get(f"/instrument_detail?symbol={symbol}")
        assert response.status_code == 404
        assert "Instrument not found" in response.json()["detail"]

def test_get_instrument_detail_market_data_fail():
    """测试行情数据获取失败"""
    with patch('data_agent_service.main.xtdata.get_instrument_detail') as mock_get_detail, \
         patch('data_agent_service.main.xtdata.get_market_data') as mock_market:
        
        mock_get_detail.return_value = {"InstrumentID": "600519.SH"}
        mock_market.return_value = {}  # 返回空行情数据
        
        response = client.get("/instrument_detail?symbol=600519.SH")
        assert response.status_code == 200  # 基础信息仍应返回
        assert response.json()["lastPrice"] is None  # 行情字段应为空

def test_get_instrument_detail_invalid_symbol_format():
    """测试无效的证券代码格式"""
    response = client.get("/instrument_detail?symbol=INVALID")
    assert response.status_code == 400
    assert "Invalid symbol format" in response.json()["detail"]  # 修正缩进

def test_get_instrument_detail_missing_parameter():
    """测试缺少必需的证券代码参数"""
    response = client.get("/instrument_detail")
    assert response.status_code == 400
    assert "symbol query parameter is required" in response.json()["detail"]

def test_get_instrument_detail_xtdata_exception():
    """测试xtdata内部异常"""
    with patch('data_agent_service.main.xtdata.get_instrument_detail') as mock_get_detail:
        symbol = "600519.SH"
        mock_get_detail.side_effect = Exception("Mock exception")
        response = client.get(f"/instrument_detail?symbol={symbol}")
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
