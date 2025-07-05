import pytest
from data_agent_service.main import app
from fastapi.testclient import TestClient
from unittest.mock import patch

client = TestClient(app)

def test_user_story_1_4():
    """验证用户故事1.4: 获取板块股票列表"""
    with patch('data_agent_service.main.xtdata.get_stock_list_in_sector') as mock_method:
        # 模拟沪深A股数据
        mock_method.return_value = ["600519.SH", "000001.SZ", "601318.SH"]
        
        response = client.get("/stock_list?sector=沪深A股")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert "600519.SH" in data
        assert "000001.SZ" in data

def test_user_story_1_5():
    """验证用户故事1.5: 获取股票详情"""
    with patch('data_agent_service.main.xtdata.get_instrument_detail') as mock_detail, \
         patch('data_agent_service.main.xtdata.get_market_data') as mock_market:
        
        # 设置模拟数据
        mock_detail.return_value = {
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
        assert data["timestamp"] == "2023-01-01 15:00:00"

def test_user_story_1_6():
    """验证用户故事1.6: 获取最新行情数据"""
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
        assert data["600519.SH"]["lastPrice"] == 1700.0
        assert data["000001.SZ"]["volume"] == 2000000
        assert data["600519.SH"]["time"] == "2023-01-01 15:00:00"

def test_user_story_1_7():
    """验证用户故事1.7: 获取完整行情数据"""
    with patch('data_agent_service.main.xtdata.get_full_market_data') as mock_method:
        mock_method.return_value = {
            "600519.SH": {
                "open": 1700.0,
                "high": 1720.0,
                "low": 1690.0,
                "close": 1710.0,
                "volume": 100000
            }
        }
        
        # 测试默认字段
        response = client.get("/full_market?symbol=600519.SH")
        assert response.status_code == 200
        data = response.json()
        assert "open" in data
        assert "high" in data
        assert "low" in data
        assert "close" in data
        assert "volume" in data
        
        # 测试字段过滤
        response = client.get("/full_market?symbol=600519.SH&fields=open,close")
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == set(["open", "close"])
        assert data["open"] == 1700.0
        assert data["close"] == 1710.0