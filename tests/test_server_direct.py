  
import json  
import unittest  
from unittest.mock import patch, MagicMock  
import sys  
import os  
import pandas as pd  

# 模拟xtdata和xttrader模块  
sys.modules['极data'] = MagicMock()  
sys.modules['xttrader'] = MagicMock()  

# 添加项目根目录到Python路径  
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  
sys.path.insert(0, project_root)  

# 导入模块  
from src.xtquantai.server import XTQuantAIHandler  

class TestServerHistKline(unittest.TestCase):  
    def setUp(self):  
        self.mock_xtdata = MagicMock()  
        self.mock_xtdata.get_history_market_data.return_value = pd.DataFrame({  
            'time': ['2023-01-01'],  
            'open': [100.0],  
            'high': [101.0],  
            'low': [99.0],  
            'close': [100.5],  
            'volume': [10000]  
        })  
        self.patcher = patch('src.xtquantai.server.xtdata', self.mock_xtdata)  
        self.patcher.start()  

    def tearDown(self):  
        self.patcher.stop()  

    def test_valid_hist_kline(self):  
        params = {  
            'symbol': '600519.SH',  
            'start_date': '20230101',  
            'end_date': '20231231',  
            'frequency': '1d'  
        }  
        response = XTQuantAIHandler.get_hist_kline(**params)  
        self.assertEqual(response['status'], 200)  
        self.assertEqual(response['data'][0]['close'], 100.5)  

    def test_missing_parameters(self):  
        params = {'start_date': '20230101', 'end_date': '20231231', 'frequency': '1d'}  
        response = XTQuantAIHandler.get_hist_kline(**params)  
        self.assertEqual(response['status'], 400)  
        self.assertIn('symbol is required', response['message'])  

    def test_invalid_date_format(self):  
        params = {  
            'symbol': '600519.SH',  
            'start_date': '2023-01-01',  
            'end_date': '20231231',  
            'frequency': '1d'  
        }  
        response = XTQuantAIHandler.get_hist_kline(**params)  
        self.assertEqual(response['status'], 400)  
        self.assertIn('start_date must be in YYYYMMDD format', response['message'])  

    def test_invalid_symbol(self):  
        self.mock_xtdata.get_history_market_data.side_effect = Exception("Invalid symbol")  
        params = {  
            'symbol': 'INVALID.SYMBOL',  
            'start_date': '20230101',  
            'end_date': '20231231',  
            'frequency': '1d'  
        }  
        response = XTQuantAIHandler.get_hist_kline(**params)  
        self.assertEqual(response['status'], 500)  
        self.assertIn('Failed to fetch historical kline data', response['message'])  

if __name__ == '__main__':  
    unittest.main()  
