import pytest
from fastapi.testclient import TestClient # TestClient 仍然需要导入以进行类型提示或直接使用（尽管fixture是首选）
from unittest.mock import patch
# from data_agent_service.main import app # app 的导入由 conftest 中的 client fixture 处理

# 模拟数据定义
MOCK_STOCK_LIST_IN_SECTOR = ["600000.SH", "600001.SH"]

# client fixture 现在由 conftest.py 提供，所以这里不需要再定义

@patch('data_agent_service.main.xtdata.get_stock_list_in_sector')
def test_get_stock_list_success(mock_get_list_method, client): # client fixture由conftest自动注入
    """测试成功获取板块股票列表"""
    mock_get_list_method.return_value = MOCK_STOCK_LIST_IN_SECTOR
    response = client.get("/stock_list?sector=沪深A股")
    assert response.status_code == 200
    assert response.json() == MOCK_STOCK_LIST_IN_SECTOR
    mock_get_list_method.assert_called_once_with("沪深A股")

@patch('data_agent_service.main.xtdata.get_stock_list_in_sector')
def test_get_stock_list_empty(mock_get_list_method, client):
    """测试板块存在但无股票或板块不存在时返回空列表"""
    mock_get_list_method.return_value = []
    response = client.get("/stock_list?sector=未知板块")
    assert response.status_code == 200 # main.py 中调整了逻辑，空列表直接返回200
    assert response.json() == []
    mock_get_list_method.assert_called_once_with("未知板块")

def test_get_stock_list_missing_parameter(client):
    """测试缺少必需的 sector 参数"""
    response = client.get("/stock_list")
    assert response.status_code == 400
    assert "sector query parameter is required" in response.json()["detail"]

@patch('data_agent_service.main.xtdata.get_stock_list_in_sector')
def test_get_stock_list_xtdata_exception(mock_get_list_method, client):
    """测试xtdata调用时发生异常"""
    mock_get_list_method.side_effect = Exception("XTData internal error")
    response = client.get("/stock_list?sector=沪深A股")
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
