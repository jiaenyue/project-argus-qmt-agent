import unittest
import json
from data_agent_service import app

class TestDataAgentService(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_get_hist_kline_success(self):
        params = {
            "symbol": "600519.SH",
            "start_date": "20230101",
            "end_date": "20230102",  # Adjusted to match mock data range
            "frequency": "1d"
        }
        response = self.app.get('/hist_kline', query_string=params)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode())
        self.assertEqual(len(data), 2) # Expecting two data points for this symbol and date range
        self.assertEqual(data[0]['date'], "20230101")
        self.assertEqual(data[1]['date'], "20230102")

    def test_get_hist_kline_missing_params(self):
        params = {
            "symbol": "600519.SH",
            "start_date": "20230101"
            # end_date and frequency are missing
        }
        response = self.app.get('/hist_kline', query_string=params)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode())
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Missing required parameters")

    def test_get_hist_kline_symbol_not_found(self):
        params = {
            "symbol": "NONEXISTENT.SZ",
            "start_date": "20230101",
            "end_date": "20230102",
            "frequency": "1d"
        }
        response = self.app.get('/hist_kline', query_string=params)
        self.assertEqual(response.status_code, 200) # Endpoint currently returns empty list for unknown symbols
        data = json.loads(response.data.decode())
        self.assertEqual(len(data), 0)

    def test_get_hist_kline_date_range_no_data(self):
        params = {
            "symbol": "600519.SH",
            "start_date": "20240101", # Date range with no mock data
            "end_date": "20240102",
            "frequency": "1d"
        }
        response = self.app.get('/hist_kline', query_string=params)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode())
        self.assertEqual(len(data), 0)

if __name__ == '__main__':
    unittest.main()
