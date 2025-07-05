import pytest
from data_agent_service.main import app
from fastapi.testclient import TestClient
from unittest.mock import patch

client = TestClient(app)

def test_get_stock_list_success():
    """测试成功获取股票列表"""
    with patch('data_agent_service.main.xtdata.get_stock_list_in_sector') as mock_method:
        mock_method.return_value = ["600519.SH", "000001.SZ", "000002.SZ"]
        response = client.get("/stock_list?sector=沪深A股")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert "600519.SH" in data

def test_get_stock_list_empty():
    """测试获取空股票列表（板块内无股票）"""
    with patch('data_agent_service.main.xtdata.get_stock_list_in_sector') as mock_method:
        mock_method.return_value = []
        response = client.get("/stock_list?sector=空板块")
        assert response.status_code == 200
        data = response.json()
        assert data == []

def test_get_stock_list_missing_parameter():
    """测试缺少必需的 sector 参数"""
    response = client.get("/stock_list")
    assert response.status_code == 400
    assert "sector query parameter is required" in response.json()["detail"]

def test_get_stock_list_xtdata_exception():
    """测试xtdata内部异常"""
    with patch('data_agent_service.main.xtdata.get_stock_list_in_sector') as mock_method:
        mock_method.side_effect = Exception("Mock exception")
        response = client.get("/stock_list?sector=沪深A股")
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
