import pytest
from fastapi.testclient import TestClient
from data_agent_service.main import app

client = TestClient(app)

def test_get_instrument_detail_success():
    """
    测试成功获取已知证券的详细信息
    """
    test_cases = [
        ("600519.SH", "Guizhou Maotai", 1700.50),
        ("000001.SZ", "Ping An Bank", 13.50)
    ]

    for symbol, display_name, price in test_cases:
        response = client.get(f"/instrument_detail?symbol={symbol}")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == symbol
        assert data["displayName"] == display_name
        assert data["lastPrice"] == price

def test_get_instrument_detail_not_found():
    """
    测试检索不存在的证券
    """
    symbol = "ABCDEF.EX"  # 格式正确但不存在的symbol（6位字母）
    response = client.get(f"/instrument_detail?symbol={symbol}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Instrument not found: {symbol}"

def test_get_instrument_detail_invalid_symbol_format():
    """
    测试各种无效的证券代码格式
    """
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

    for symbol, case in invalid_cases:
        response = client.get(f"/instrument_detail?symbol={symbol}")
        assert response.status_code == 400
        assert "Invalid symbol format" in response.json()["detail"]

def test_get_instrument_detail_missing_parameter():
    """
    测试缺少必需的证券代码参数
    """
    response = client.get("/instrument_detail")
    assert response.status_code == 400
    assert "Symbol query parameter is required" in response.json()["detail"]

@pytest.mark.skip(reason="Rate limiting not implemented")
def test_rate_limiting():
    """
    测试API速率限制功能（已跳过）
    """
    pass

def test_root_endpoint():
    """
    测试根端点
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Data Agent Service"}

def test_error_handling():
    """
    测试错误响应是否格式正确
    """
    # 测试400错误 - 无效格式
    response = client.get("/instrument_detail?symbol=invalid")
    assert response.status_code == 400
    assert "detail" in response.json()
    
    # 测试404错误 - 格式正确但不存在
    response = client.get("/instrument_detail?symbol=ABCDEF.EX")  # 使用有效的6位字母symbol
    assert response.status_code == 404
    assert "detail" in response.json()
