from flask import Flask, request, jsonify

app = Flask(__name__)

# Mock data for demonstration purposes
mock_kline_data = {
    "600519.SH": [
        {"date": "20230101", "open": 1700.00, "high": 1720.00, "low": 1690.00, "close": 1710.00, "volume": 10000},
        {"date": "20230102", "open": 1710.00, "high": 1730.00, "low": 1700.00, "close": 1720.00, "volume": 12000},
    ],
    "000001.SZ": [
        {"date": "20230101", "open": 12.00, "high": 12.20, "low": 11.90, "close": 12.10, "volume": 200000},
        {"date": "20230102", "open": 12.10, "high": 12.30, "low": 12.00, "close": 12.20, "volume": 220000},
    ]
}

@app.route('/hist_kline', methods=['GET'])
def get_hist_kline():
    symbol = request.args.get('symbol')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    frequency = request.args.get('frequency')

    if not all([symbol, start_date, end_date, frequency]):
        return jsonify({"error": "Missing required parameters"}), 400

    # In a real application, you would fetch data from xtquant here
    # For now, we return mock data
    data = mock_kline_data.get(symbol, [])

    # Filter data by date (simplified for mock data)
    # A real implementation would handle date filtering more robustly
    filtered_data = [
        item for item in data
        if start_date <= item['date'] <= end_date
    ]

    return jsonify(filtered_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
