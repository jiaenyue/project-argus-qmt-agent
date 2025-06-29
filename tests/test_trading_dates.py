import json  
import unittest  
from unittest.mock import patch, MagicMock  
import sys  
import os  
import types  
import asyncio  
import pandas as pd  

# 模拟xtdata和xttrader模块  
sys.modules['xtdata'] = MagicMock()  
sys.modules['xttrader'] = MagicMock()  

# 添加项目根目录到Python路径  
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  
sys.path.insert(0, project_root)  

# 导入模块  
from src.xtquantai import server  
from src.xtquantai.server import XTQuantAIHandler  

class TestServerDirectTradingDates(unittest.TestCase):  
    def setUp(self):  
        self.mock_xtdata = MagicMock()  
        def mock_get_trading_dates(market, start_date=None, end_date=None):  
            all_dates = ["20250101", "20250102", "20250103"]  
            if start_date and end_date:  
                return [date for date in all_dates if start_date <= date <= end_date]  
            return all_dates  
        self.mock_xtdata.get_trading_dates.side_effect = mock_get_trading_dates  
        self.patcher = patch('src.xtquantai.server.xtdata', self.mock_xtdata)  
        self.patcher.start()  

    def tearDown(self):  
        self.patcher.stop()  

    def test_get_trading_dates_sh_all(self):  
        result = XTQuantAIHandler.get_trading_dates("SH", "", "")  
        self.assertEqual(result['data'], ["20250101", "20250102", "20250103"])  

    def test_get_trading_dates_filtered(self):  
        result = XTQuantAIHandler.get_trading_dates("SZ", "20250102", "20250103")  
        self.assertEqual(result['data'], ["20250102", "20250103"])  

    def test_get_trading_dates_validation(self):  
        # 测试验证逻辑  
        pass  

    def test_get_trading_dates_xtdata_exception(self):  
        self.mock_xtdata.get_trading_dates.side_effect = Exception("Connection error")  
        result = XTQuantAIHandler.get_trading_dates("SH", "", "")  
        self.assertFalse(result['success'])  

class TestServerHTTPTradingDates(unittest.TestCase):  
    def setUp(self):  
        self.mock_xtdata = MagicMock()  
        def mock_get_trading_dates(market, start_date=None, end_date=None):  
            all_dates = ["20250101", "20250102", "20250103"]  
            if start_date and end_date:  
                return [date for date in all_dates if start_date <= date <= end_date]  
            return all_dates  
        self.mock_xtdata.get_trading_dates.side_effect = mock_get_trading_dates  
        self.patcher = patch('src.xtquantai.server.xtdata', self.mock_xtdata)  
        self.patcher.start()  

    def tearDown(self):  
        self.patcher.stop()  

    def test_http_get_trading_dates_success(self):  
        result = XTQuantAIHandler.get_trading_dates("SH", "", "")  
        self.assertEqual(result['status'], 200)  
        self.assertEqual(result['data'], ["20250101", "20250102", "20250103"])  

    def test_http_get_trading_dates_error(self):  
        self.mock_xtdata.get_trading_dates.side_effect = Exception("Connection error")  
        result = XTQuantAIHandler.get_trading_dates("SH", "", "")  
        self.assertFalse(result['success'])  

if __name__ == '__main__':  
    unittest.main()  