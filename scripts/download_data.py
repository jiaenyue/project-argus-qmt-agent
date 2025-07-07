import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from xtquant import xtdata

LOG_FILE = "scripts/download_log.txt"
log_lock = threading.Lock()

def get_stock_list():
    """
    获取所有A股的股票代码列表。
    参考 tutorials/04_stock_list.ipynb
    """
    print("正在获取A股股票列表...")
    try:
        stocks = xtdata.get_stock_list_in_sector('沪深A股')
        if stocks:
            print(f"成功获取 {len(stocks)} 只股票。")
            return stocks
        else:
            print("未获取到股票列表。")
            return []
    except Exception as e:
        print(f"获取股票列表失败: {str(e)}")
        return []

def load_downloaded_stocks():
    """
    从日志文件中加载已下载的股票代码。
    """
    downloaded = set()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            for line in f:
                downloaded.add(line.strip())
    return downloaded

def record_downloaded_stock(symbol):
    """
    将成功下载的股票代码记录到日志文件。
    """
    with log_lock:
        with open(LOG_FILE, 'a') as f:
            f.write(f"{symbol}\n")

def download_stock_data(symbol, downloaded_stocks):
    """
    下载单只股票的日线历史数据，并支持断点续传。
    参考 tutorials/02_hist_kline.ipynb
    """
    if symbol in downloaded_stocks:
        print(f"已在日志中，跳过 {symbol}")
        return

    print(f"正在下载 {symbol} 的数据...")
    start_date = "20000101"  # 下载完整的历史数据，从较早日期开始
    end_date = datetime.now().strftime("%Y%m%d")
    frequency = "1d"

    try:
        xtdata.download_history_data(
            stock_code=symbol,
            period=frequency,
            start_time=start_date,
            end_time=end_date
        )
        print(f"成功为 {symbol} 补充历史数据。")
        record_downloaded_stock(symbol)
    except Exception as e:
        print(f"下载 {symbol} 数据失败: {e}")

def main():
    downloaded_stocks = load_downloaded_stocks()
    stocks = get_stock_list()
    if not stocks:
        print("未获取到股票列表，退出。")
        return

    # 使用多线程下载
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 将 downloaded_stocks 传递给每个线程任务
        futures = [executor.submit(download_stock_data, stock, downloaded_stocks) for stock in stocks]
        for future in futures:
            future.result() # 等待所有任务完成

    print("所有股票历史数据补充尝试完成。")

if __name__ == "__main__":
    main()