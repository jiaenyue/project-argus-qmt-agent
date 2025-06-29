import json
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import types
import asyncio

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import after path modification
from src.xtquantai import server

class TestServerDirectTradingDates(unittest.TestCase):
    def setUp(self):
        # Create a MagicMock for xtdata
        self.mock_xtdata = MagicMock()
        
        # Patch server.xtdata to use our mock
        self.patcher = patch('src.xtquantai.server.xtdata', self.mock_xtdata)
        self.patcher.start()
        
        # 创建模拟的 XTQuantAIHandler 类
        self.handler = types.new_class('XTQuantAIHandler')
        self.handler.get_trading_dates = server.XTQuantAIHandler.get_trading_dates

    def tearDown(self):
        self.patcher.stop()
        server.xtdata = None

    def test_get_trading_dates_sh_all(self):
        """Test GET /api/get_trading_dates for SH market."""
        self.mock_xtdata.get_trading_dates.return_value = ["20250101", "20250102", "20250103"]
        result = self.handler.get_trading_dates("SH", "", "")
        self.assertEqual(result['data'], ["20250101", "20250102", "20250103"])

    def test_get_trading_dates_filtered(self):
        """Test GET /api/get_trading_dates with date filters."""
        self.mock_xtdata.get_trading_dates.return_value = ["20250101", "20250102", "20250103"]
        result = self.handler.get_trading_dates("SZ", "20250102", "20250103")
        self.assertEqual(result['data'], ["20250102", "20250103"])

    def test_get_trading_dates_validation(self):
        """验证日期参数边界值及响应格式"""
        # 测试正常日期范围
        self.mock_xtdata.get_trading_dates.return_value = ["20250102", "20250103"]
        result = self.handler.get_trading_dates("SH", "20250101", "20250110")
        self.assertIsInstance(result, dict)
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], ["20250102", "20250103"])
        
        # 验证日期格式
        for date in result['data']:
            self.assertRegex(date, r"^\d{8}$", "日期格式应为YYYYMMDD")
        
        # 测试边界值场景
        test_cases = [
            ("20241301", "20250110", "月份"),  # 无效月份 -> 预期错误消息包含"月份"
            ("20250001", "20250110", "月份"),  # 无效日期 -> 预期错误消息包含"月份" (因为月份00无效)
            ("20250110", "20250101", "不能大于"),  # 开始日期 > 结束日期 -> 预期错误消息包含"不能大于"
        ]
        
        for start, end, error_key in test_cases:
            with self.subTest(start=start, end=end):
                result = self.handler.get_trading_dates("SH", start, end)
                self.assertIsInstance(result, dict)
                # 确保所有无效参数返回 success=False
                self.assertFalse(result.get('success', True))
                # 确保返回结果包含 data 字段
                self.assertIn("data", result)
                self.assertIn(error_key, result['data'])
    
    def test_get_trading_dates_xtdata_exception(self):
        """Test handling of exceptions."""
        self.mock_xtdata.get_trading_dates.side_effect = Exception("Connection error")
        result = self.handler.get_trading_dates("SH", "", "")
        self.assertIn("错误: Connection error", result['data'])

class TestServerHTTPTradingDates(unittest.TestCase):
    def setUp(self):
        # 创建模拟的xtdata
        self.mock_xtdata = MagicMock()
        self.mock_xtdata.get_trading_dates.return_value = ["20250101", "20250102", "20250103"]
        
        # 创建模拟的server
        self.mock_server = MagicMock()
        self.mock_server.http = MagicMock()
        
        # 应用补丁
        self.patcher = patch('src.xtquantai.server.xtdata', self.mock_xtdata)
        self.patcher.start()
        
        # 导入并实例化handler
        from src.xtquantai.server import handle_get_trading_dates
        self.handler = handle_get_trading_dates

    def tearDown(self):
        self.patcher.stop()

    def test_http_get_trading_dates_success(self):
        """测试HTTP接口 /api/get_trading_dates 成功响应"""
        # 创建模拟请求
        mock_request = MagicMock()
        mock_request.query_params = {"market": "SH"}
        
        # 调用处理函数
        response = asyncio.run(self.handler(mock_request))
        
        # 验证响应
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")
        
        # 解析响应体
        body = json.loads(response["body"])
        self.assertTrue(body["success"])
        self.assertEqual(body["data"], ["20250101", "20250102", "20250103"])

    def test_http_get_trading_dates_error(self):
        """测试HTTP接口 /api/get_trading_dates 错误处理"""
        # 模拟异常
        self.mock_xtdata.get_trading_dates.side_effect = Exception("Connection error")
        
        # 创建模拟请求
        mock_request = MagicMock()
        mock_request.query_params = {"market": "SH"}
        
        # 调用处理函数
        response = asyncio.run(self.handler(mock_request))
        
        # 验证响应状态码（已改为始终返回200）
        self.assertEqual(response["status"], 200)
        
        # 解析响应体
        body = json.loads(response["body"])
        # 修正：预期 success 应为 false
        self.assertFalse(body["success"])
        self.assertIn("错误: Connection error", body["data"])

if __name__ == '__main__':
    unittest.main()
