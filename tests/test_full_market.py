import pytest
from fastapi.testclient import TestClient # TestClient 仍然需要导入以进行类型提示或直接使用
from unittest.mock import patch
# from data_agent_service.main import app # 移除模块级导入，app 通过 client fixture 提供

# 模拟数据定义
MOCK_FULL_MARKET_DATA_MAOTAI = {
    "open": 1710.00,
    "high": 1720.80,
    "low": 1690.00,
    "close": 1705.30,
    "volume": 100000,
    "askPrice1": 1700.60, # 添加一些其他可能的字段
    "bidPrice1": 1700.50
}

# client fixture 现在由 conftest.py 提供，所以这里的定义被移除

# === Tests for /full_market ===

@patch('data_agent_service.main.xtdata.get_full_market_data')
def test_get_full_market_success_no_fields(mock_get_full_method, client):
    """测试成功获取完整行情 (不带fields)"""
    # xtdata.get_full_market_data 返回的是 {symbol: data_dict}
    mock_response = {"600519.SH": MOCK_FULL_MARKET_DATA_MAOTAI}
    mock_get_full_method.return_value = mock_response

    response = client.get("/full_market?symbol=600519.SH")
    assert response.status_code == 200
    data = response.json()
    # API端点设计为直接返回该symbol的数据字典
    assert data["open"] == MOCK_FULL_MARKET_DATA_MAOTAI["open"]
    assert data["volume"] == MOCK_FULL_MARKET_DATA_MAOTAI["volume"]
    assert data["askPrice1"] == MOCK_FULL_MARKET_DATA_MAOTAI["askPrice1"]
    mock_get_full_method.assert_called_once_with(["600519.SH"]) # xtdata接收列表

@patch('data_agent_service.main.xtdata.get_full_market_data')
def test_get_full_market_success_with_fields(mock_get_full_method, client):
    """测试成功获取完整行情 (带fields)"""
    requested_fields = ["open", "close", "volume"]
    # 模拟xtdata只返回请求的字段
    mock_filtered_data = {
        k: v for k, v in MOCK_FULL_MARKET_DATA_MAOTAI.items() if k in requested_fields
    }
    mock_response = {"600519.SH": mock_filtered_data}
    mock_get_full_method.return_value = mock_response

    response = client.get(f"/full_market?symbol=600519.SH&fields={','.join(requested_fields)}")
    assert response.status_code == 200
    data = response.json()
    assert "open" in data
    assert "close" in data
    assert "volume" in data
    assert "high" not in data # high未被请求
    assert "askPrice1" not in data # askPrice1未被请求
    assert data["open"] == MOCK_FULL_MARKET_DATA_MAOTAI["open"]
    mock_get_full_method.assert_called_once_with(["600519.SH"], fields=requested_fields)

@patch('data_agent_service.main.xtdata.get_full_market_data')
def test_get_full_market_not_found(mock_get_full_method, client):
    """测试股票代码无效或无数据"""
    # 情况1: xtdata返回空字典
    mock_get_full_method.return_value = {}
    response = client.get("/full_market?symbol=NONEXIST.SH")
    assert response.status_code == 404
    assert "No full market data found for symbol: NONEXIST.SH" in response.json()["detail"]
    mock_get_full_method.assert_called_with(["NONEXIST.SH"])

    # 情况2: xtdata返回字典但不含请求的symbol的键
    mock_get_full_method.reset_mock()
    mock_get_full_method.return_value = {"SOMEOTHER.SH": {"open": 10}}
    response = client.get("/full_market?symbol=NONEXIST.SH")
    assert response.status_code == 404
    assert "No full market data found for symbol: NONEXIST.SH" in response.json()["detail"]
    mock_get_full_method.assert_called_with(["NONEXIST.SH"])

    # 情况3: xtdata返回字典，含symbol，但其值为空字典 (表示无数据)
    mock_get_full_method.reset_mock()
    mock_get_full_method.return_value = {"NONEXIST.SH": {}}
    response = client.get("/full_market?symbol=NONEXIST.SH")
    assert response.status_code == 404
    assert "No full market data found for symbol: NONEXIST.SH" in response.json()["detail"]
    mock_get_full_method.assert_called_with(["NONEXIST.SH"])

def test_get_full_market_invalid_symbol_format(client):
    """测试symbol参数格式无效"""
    response = client.get("/full_market?symbol=INVALID")
    assert response.status_code == 400
    assert "Invalid symbol format: INVALID" in response.json()["detail"]

def test_get_full_market_missing_symbol_param(client):
    """测试缺少必需的symbol参数"""
    response = client.get("/full_market")
    assert response.status_code == 400
    assert "symbol query parameter is required" in response.json()["detail"]

def test_get_full_market_empty_fields_param(client):
    """测试fields参数提供但解析后为空 (例如 ",,")"""
    response = client.get("/full_market?symbol=600519.SH&fields=,,")
    assert response.status_code == 400 # 根据main.py中的校验
    assert "Fields parameter, if provided, cannot be empty or only commas." in response.json()["detail"]

@patch('data_agent_service.main.xtdata.get_full_market_data')
def test_get_full_market_xtdata_exception(mock_get_full_method, client):
    """测试xtdata调用时发生异常"""
    mock_get_full_method.side_effect = Exception("XTData internal error")
    response = client.get("/full_market?symbol=600519.SH")
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
