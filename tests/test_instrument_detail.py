import pytest
from fastapi.testclient import TestClient # TestClient 仍然需要导入以进行类型提示或直接使用
from unittest.mock import patch
# from data_agent_service.main import app # 移除模块级导入，app 通过 client fixture 提供

# 只保留此文件需要的模拟数据
MOCK_INSTRUMENT_DETAIL_MAOTAI = {
    "symbol": "600519.SH",
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
MOCK_INSTRUMENT_DETAIL_PINGAN = {
    "symbol": "000001.SZ",
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
# MOCK_LATEST_MARKET_DATA 和 MOCK_FULL_MARKET_DATA_MAOTAI 已被移除
# MOCK_STOCK_LIST_IN_SECTOR 已被移除

# client fixture 现在由 conftest.py 提供，所以这里的定义被移除

# === Tests for /instrument_detail ===

@patch('data_agent_service.main.xtdata.get_instrument_detail')
@pytest.mark.parametrize("symbol, mock_return, expected_display_name, expected_price", [
    ("600519.SH", MOCK_INSTRUMENT_DETAIL_MAOTAI, "Guizhou Maotai", 1700.50),
    ("000001.SZ", MOCK_INSTRUMENT_DETAIL_PINGAN, "Ping An Bank", 13.50),
])
def test_get_instrument_detail_success(mock_get_detail, symbol, mock_return, expected_display_name, expected_price, client): # client fixture注入
    """测试成功获取已知证券的详细信息"""
    mock_get_detail.return_value = mock_return
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"].upper() == symbol.upper()
    assert data["displayName"] == expected_display_name
    assert data["lastPrice"] == expected_price
    mock_get_detail.assert_called_with(symbol.upper())


@patch('data_agent_service.main.xtdata.get_instrument_detail')
def test_get_instrument_detail_not_found(mock_get_detail, client):
    """测试检索不存在的证券 (xtdata返回None)"""
    symbol = "NONEXIST.SH"
    mock_get_detail.return_value = None
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Instrument not found or no data available for: {symbol}"
    mock_get_detail.assert_called_with(symbol.upper())

@patch('data_agent_service.main.xtdata.get_instrument_detail')
def test_get_instrument_detail_empty_dict(mock_get_detail, client):
    """测试检索不存在的证券 (xtdata返回空字典)"""
    symbol = "EMPTYRET.SH"
    mock_get_detail.return_value = {}
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Instrument not found or no data available for: {symbol}"
    mock_get_detail.assert_called_with(symbol.upper())


def test_get_instrument_detail_invalid_symbol_format(client):
    """测试各种无效的证券代码格式"""
    invalid_cases = [
        ("600519sh", "missing dot"),
        ("600519.", "missing exchange"),
        (".SH", "missing stock code"),
        ("600519.S", "exchange too short"),
        ("600519.123", "exchange with numbers"),
        ("1234567.SH", "code too long"),
        ("12345.SH", "code too short"),
        ("600519.SHH", "exchange too long")
    ]

    for symbol, case_desc in invalid_cases:
        response = client.get(f"/instrument_detail?symbol={symbol}")
        assert response.status_code == 400
        assert "Invalid symbol format. Expected format like '600519.SH' or '000001.SZ'." in response.json()["detail"]


def test_get_instrument_detail_missing_parameter(client):
    """测试缺少必需的证券代码参数"""
    response = client.get("/instrument_detail")
    assert response.status_code == 400
    assert "symbol query parameter is required" in response.json()["detail"]


@patch('data_agent_service.main.xtdata.get_instrument_detail')
def test_get_instrument_detail_xtdata_exception(mock_get_detail, client):
    """测试xtdata调用时发生异常"""
    mock_get_detail.side_effect = Exception("XTData internal error")
    response = client.get("/instrument_detail?symbol=600519.SH")
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]


# 移除 test_rate_limiting, test_root_endpoint, test_error_handling
# 移除所有 /latest_market, /full_market, /stock_list 的测试
