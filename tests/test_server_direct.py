import json
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the Python path to allow importing server_direct
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import after path modification
import server_direct

# Keep a reference to the original MockXtdata for restoration if needed
OriginalMockXtdata = server_direct.MockXtdata

class TestServerDirectTradingDates(unittest.TestCase):

    def setUp(self):
        # Ensure each test uses a fresh instance of MockXtdata or a specific mock
        # This helps in isolating tests
        self.mock_xtdata_instance = server_direct.MockXtdata()

        # Patch server_direct.xtdata to use our controlled mock instance for all tests in this class
        self.patcher = patch('server_direct.xtdata', self.mock_xtdata_instance)
        self.mock_xtdata_global = self.patcher.start()

        # Mock the HTTP server part for testing handler logic
        # We will call the handler methods directly, not through an actual HTTP server
        self.handler = server_direct.XTQuantAIHandler
        # Mock request and wfile for the handler
        self.handler.rfile = MagicMock()
        self.handler.wfile = MagicMock()
        self.handler.headers = {}


    def tearDown(self):
        self.patcher.stop()
        server_direct.xtdata = None # Reset to allow re-initialization if ensure_xtdc_initialized is called

    def _simulate_get_request(self, path_query: str):
        """Simulates a GET request by directly calling the handler's method."""
        request_mock = MagicMock()
        request_mock.makefile = MagicMock(return_value=self.handler.rfile) # For BaseHTTPRequestHandler internals

        # Create a new handler instance for each simulated request
        handler_instance = self.handler(request_mock, ('localhost', 8000), MagicMock())
        handler_instance.path = path_query
        handler_instance.wfile = MagicMock() # Ensure wfile is a fresh mock for capturing output

        handler_instance.do_GET()

        # Capture what was written to wfile
        written_data = handler_instance.wfile.write.call_args[0][0]
        return json.loads(written_data.decode('utf-8'))

    def _simulate_post_request(self, path: str, post_body: dict):
        """Simulates a POST request by directly calling the handler's method."""
        request_mock = MagicMock()
        request_mock.makefile = MagicMock(return_value=self.handler.rfile)

        handler_instance = self.handler(request_mock, ('localhost', 8000), MagicMock())
        handler_instance.path = path
        handler_instance.headers = {'Content-Length': str(len(json.dumps(post_body)))}
        handler_instance.rfile.read = MagicMock(return_value=json.dumps(post_body).encode('utf-8'))
        handler_instance.wfile = MagicMock()

        handler_instance.do_POST()

        written_data = handler_instance.wfile.write.call_args[0][0]
        return json.loads(written_data.decode('utf-8'))

    def test_get_trading_dates_sh_all(self):
        """Test GET /api/get_trading_dates for SH market, all dates."""
        # Update mock_xtdata_instance to return specific data for this test
        self.mock_xtdata_instance.get_trading_dates = MagicMock(
            return_value=["20250101", "20250102", "20250103", "20250106", "20250107"]
        )
        server_direct.xtdata = self.mock_xtdata_instance # Ensure the global xtdata is our instance

        response = self._simulate_get_request("/api/get_trading_dates?market=SH")
        self.assertTrue(response["success"])
        self.assertIsInstance(response["data"], list)
        self.assertEqual(response["data"], ["20250101", "20250102", "20250103", "20250106", "20250107"])
        self.mock_xtdata_instance.get_trading_dates.assert_called_once_with(market="SH", start_date=None, end_date=None)

    def test_get_trading_dates_sz_filtered(self):
        """Test GET /api/get_trading_dates for SZ market with start and end dates."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(
            # Mocking the behavior of the actual get_trading_dates in server_direct.py
            # which itself calls the (mocked) xtdata.get_trading_dates
            # So, this mock should return what the *inner* call returns.
            # The filtering is done in server_direct.get_trading_dates function.
            # Let's provide a list that would be filtered.
            return_value=["20250101", "20250102", "20250103", "20250106", "20250107"]
        )
        server_direct.xtdata = self.mock_xtdata_instance

        response = self._simulate_get_request("/api/get_trading_dates?market=SZ&start_date=20250102&end_date=20250106")
        self.assertTrue(response["success"])
        # The filtering is done in server_direct.get_trading_dates based on the return value from the mock
        # So the expected data is what the server_direct.get_trading_dates would produce after filtering.
        expected_data = ["20250102", "20250103", "20250106"]
        self.assertEqual(response["data"], expected_data)
        # The call to the *mocked* xtdata.get_trading_dates (which is self.mock_xtdata_instance.get_trading_dates)
        # inside server_direct.get_trading_dates should receive these parameters.
        self.mock_xtdata_instance.get_trading_dates.assert_called_once_with(market="SZ", start_date="20250102", end_date="20250106")


    def test_get_trading_dates_post_filtered(self):
        """Test POST /api/get_trading_dates with start and end dates."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(
            return_value=["20240101", "20240102", "20240103", "20240104"]
        )
        server_direct.xtdata = self.mock_xtdata_instance

        payload = {"market": "SH", "start_date": "20240102", "end_date": "20240103"}
        response = self._simulate_post_request("/api/get_trading_dates", payload)
        self.assertTrue(response["success"])
        self.assertEqual(response["data"], ["20240102", "20240103"])
        self.mock_xtdata_instance.get_trading_dates.assert_called_once_with(market="SH", start_date="20240102", end_date="20240103")

    def test_get_trading_dates_only_start_date(self):
        """Test GET /api/get_trading_dates with only start_date."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(
            return_value=["20250101", "20250102", "20250103", "20250106", "20250107"]
        )
        server_direct.xtdata = self.mock_xtdata_instance

        response = self._simulate_get_request("/api/get_trading_dates?market=SH&start_date=20250106")
        self.assertTrue(response["success"])
        self.assertEqual(response["data"], ["20250106", "20250107"])
        self.mock_xtdata_instance.get_trading_dates.assert_called_once_with(market="SH", start_date="20250106", end_date=None)

    def test_get_trading_dates_only_end_date(self):
        """Test GET /api/get_trading_dates with only end_date."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(
            return_value=["20250101", "20250102", "20250103", "20250106", "20250107"]
        )
        server_direct.xtdata = self.mock_xtdata_instance
        response = self._simulate_get_request("/api/get_trading_dates?market=SH&end_date=20250102")
        self.assertTrue(response["success"])
        self.assertEqual(response["data"], ["20250101", "20250102"])
        self.mock_xtdata_instance.get_trading_dates.assert_called_once_with(market="SH", start_date=None, end_date="20250102")

    def test_get_trading_dates_malformed_date_in_data(self):
        """Test handling of malformed date data from xtdata, ensuring YYYYMMDD format."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(
            return_value=["20230101", "2023-01-02", 20230103, "invalid-date", "202301040"] # Mix of formats and invalid
        )
        server_direct.xtdata = self.mock_xtdata_instance
        response = self._simulate_get_request("/api/get_trading_dates?market=SH")
        self.assertTrue(response["success"])
        # The server_direct.get_trading_dates function should correctly format and filter
        self.assertEqual(response["data"], ["20230101", "20230102", "20230103"])

    def test_get_trading_dates_no_dates_found(self):
        """Test GET /api/get_trading_dates when no dates are returned by xtdata."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(return_value=[])
        server_direct.xtdata = self.mock_xtdata_instance
        response = self._simulate_get_request("/api/get_trading_dates?market=SH")
        self.assertTrue(response["success"]) # Success is true, but data is empty
        self.assertEqual(response["data"], [])

    def test_get_trading_dates_xtdata_returns_none(self):
        """Test GET /api/get_trading_dates when xtdata.get_trading_dates returns None."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(return_value=None)
        server_direct.xtdata = self.mock_xtdata_instance
        response = self._simulate_get_request("/api/get_trading_dates?market=SH")
        self.assertFalse(response["success"])
        self.assertIn("Failed to fetch trading dates", response.get("error", ""))

    def test_get_trading_dates_xtdata_exception(self):
        """Test GET /api/get_trading_dates when xtdata call raises an exception."""
        self.mock_xtdata_instance.get_trading_dates = MagicMock(side_effect=Exception("XTData connection error"))
        server_direct.xtdata = self.mock_xtdata_instance
        response = self._simulate_get_request("/api/get_trading_dates?market=SH")
        self.assertFalse(response["success"])
        self.assertEqual(response.get("error"), "XTData connection error")

    def test_get_trading_dates_invalid_date_format_param(self):
        """Test GET /api/get_trading_dates with invalid date format in parameters (though current server doesn't validate this strictly)."""
        # This test is more about ensuring it doesn't crash. The current filtering logic
        # relies on string comparison, so "invalid" dates might lead to unexpected filtering
        # but not necessarily a crash.
        self.mock_xtdata_instance.get_trading_dates = MagicMock(
            return_value=["20250101", "20250102", "20250103"]
        )
        server_direct.xtdata = self.mock_xtdata_instance
        response = self._simulate_get_request("/api/get_trading_dates?market=SH&start_date=bad-date")
        self.assertTrue(response["success"])
        # Because "bad-date" > "20250103" is false, all dates will be returned if it's a start_date
        # If it was an end_date, "20250101" < "bad-date" would be true, so it would return all.
        # String comparison behavior:
        # "20250101" < "bad-date" -> True
        # "bad-date" < "20250101" -> True
        # This means with start_date="bad-date", no dates are filtered out before "bad-date"
        # With end_date="bad-date", all dates are filtered out after "bad-date"
        # For start_date="bad-date", since "20250101" is not < "bad-date" (it's actually the opposite by string comparison)
        # it will filter out dates. For end_date, it will also filter.
        # Let's check the actual string comparison: '20250101' < 'bad-date' is True.
        # So if start_date is 'bad-date', condition `formatted_date < start_date_str` (`'20250101' < 'bad-date'`) is True, so it continues.
        # This means all dates will be skipped.
        self.assertEqual(response["data"], [])


if __name__ == '__main__':
    unittest.main()
