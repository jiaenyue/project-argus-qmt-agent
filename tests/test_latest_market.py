import pytest
from fastapi.testclient import TestClient # TestClient 仍然需要导入以进行类型提示或直接使用
from unittest.mock import patch
# from data_agent_service.main import app # 移除模块级导入，app 通过 client fixture 提供

# 模拟数据定义
MOCK_LATEST_MARKET_DATA = {
    "600519.SH": {"lastPrice": 1700.50, "volume": 100000, "openPrice": 1710.00},
    "000001.SZ": {"lastPrice": 13.50, "volume": 500000, "openPrice": 13.60}
}

# client fixture 现在由 conftest.py 提供，所以这里的定义被移除

# === Tests for /latest_market ===

@patch('data_agent_service.main.xtdata.get_latest_market_data')
def test_get_latest_market_success_single_symbol(mock_get_latest_method, client):
    """测试成功获取单个股票的最新行情"""
    mock_response = {"600519.SH": MOCK_LATEST_MARKET_DATA["600519.SH"]}
    mock_get_latest_method.return_value = mock_response

    response = client.get("/latest_market?symbols=600519.SH")
    assert response.status_code == 200
    data = response.json()
    assert "600519.SH" in data
    assert data["600519.SH"]["lastPrice"] == MOCK_LATEST_MARKET_DATA["600519.SH"]["lastPrice"]
    mock_get_latest_method.assert_called_once_with(["600519.SH"])

@patch('data_agent_service.main.xtdata.get_latest_market_data')
def test_get_latest_market_success_multiple_symbols(mock_get_latest_method, client):
    """测试成功获取多个股票的最新行情"""
    mock_get_latest_method.return_value = MOCK_LATEST_MARKET_DATA
    response = client.get("/latest_market?symbols=600519.SH,000001.SZ")
    assert response.status_code == 200
    data = response.json()
    assert "600519.SH" in data
    assert "000001.SZ" in data
    assert data["000001.SZ"]["volume"] == MOCK_LATEST_MARKET_DATA["000001.SZ"]["volume"]
    mock_get_latest_method.assert_called_once_with(["600519.SH", "000001.SZ"])

@patch('data_agent_service.main.xtdata.get_latest_market_data')
def test_get_latest_market_partial_found(mock_get_latest_method, client):
    """测试部分股票代码有效，xtdata只返回有效部分的数据"""
    mock_response = {"600519.SH": MOCK_LATEST_MARKET_DATA["600519.SH"]}
    mock_get_latest_method.return_value = mock_response

    response = client.get("/latest_market?symbols=600519.SH,NONEXIST.SZ")
    # API应该仍然返回200，即使只有一个股票找到了数据
    assert response.status_code == 200
    data = response.json()
    assert "600519.SH" in data
    assert "NONEXIST.SZ" not in data # 假设xtdata不为找不到的股票返回键
    mock_get_latest_method.assert_called_once_with(["600519.SH", "NONEXIST.SZ"])

@patch('data_agent_service.main.xtdata.get_latest_market_data')
def test_get_latest_market_none_found(mock_get_latest_method, client):
    """测试所有股票代码均无效或无数据 (xtdata返回空字典)"""
    mock_get_latest_method.return_value = {} # xtdata返回空字典
    response = client.get("/latest_market?symbols=NONEXIST1.SH,NONEXIST2.SZ")
    assert response.status_code == 404 # main.py中会因为空字典抛出404
    assert "No market data found for symbols" in response.json()["detail"]
    mock_get_latest_method.assert_called_once_with(["NONEXIST1.SH", "NONEXIST2.SZ"])

def test_get_latest_market_invalid_symbol_format(client):
    """测试symbols参数中包含无效格式的股票代码"""
    response = client.get("/latest_market?symbols=600519.SH,INVALIDCODE")
    assert response.status_code == 400
    assert "Invalid symbol format: INVALIDCODE" in response.json()["detail"]

def test_get_latest_market_empty_symbols_param(client):
    """测试symbols参数为空字符串"""
    response = client.get("/latest_market?symbols=")
    # 根据main.py中的检查，空字符串解析后列表为空，会触发400
    assert response.status_code == 400
    assert "Symbols query parameter cannot be empty" in response.json()["detail"]

def test_get_latest_market_missing_symbols_param(client):
    """测试缺少必需的symbols参数"""
    response = client.get("/latest_market")
    assert response.status_code == 400
    assert "symbols query parameter is required" in response.json()["detail"]

@patch('data_agent_service.main.xtdata.get_latest_market_data')
def test_get_latest_market_xtdata_exception(mock_get_latest_method, client):
    """测试xtdata调用时发生异常"""
    mock_get_latest_method.side_effect = Exception("XTData internal error")
    response = client.get("/latest_market?symbols=600519.SH")
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
