from xtquant import xtdata
import datetime

def download_all_tutorial_data():
    """
    下载所有教程所需的全部数据，包括历史K线数据、板块分类信息、
    指数成分权重信息和财务数据。
    """
    today = datetime.date.today()
    # 设置下载数据的起始日期为一年前
    start_date_one_year_ago = (today - datetime.timedelta(days=365)).strftime("%Y%m%d")
    # 设置下载数据的结束日期为今天
    end_date_today = today.strftime("%Y%m%d")

    print("--- 开始下载所有教程所需数据 ---")

    # 1. 下载板块分类信息
    print("\n开始下载板块分类信息...")
    try:
        xtdata.download_sector_data()
        print("板块分类信息下载完成。")
    except Exception as e:
        print(f"下载板块分类信息失败: {e}")
        print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")

    # 2. 下载指数成分权重信息
    print("\n开始下载指数成分权重信息...")
    try:
        # 假设需要下载沪深300和中证500的指数权重
        index_list = ["000300.SH", "000905.SH"]
        for index_code in index_list:
            xtdata.download_index_weight(index_code)
            print(f"成功下载 {index_code} 的指数成分权重信息。")
        print("指数成分权重信息下载完成。")
    except Exception as e:
        print(f"下载指数成分权重信息失败: {e}")
        print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")

    # 3. 下载财务数据
    print("\n开始下载财务数据...")
    try:
        # 假设需要下载一些常用股票的财务数据
        financial_stock_list = ["000001.SZ", "600519.SH"]
        for stock_code in financial_stock_list:
            xtdata.download_financial_data(stock_code)
            print(f"成功下载 {stock_code} 的财务数据。")
        print("财务数据下载完成。")
    except Exception as e:
        print(f"下载财务数据失败: {e}")
        print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")

    # 4. 下载历史K线数据
    stock_symbols = ["600519.SH", "000001.SZ", "600000.SH"]
    kline_periods = ["1d", "1m"]

    for symbol in stock_symbols:
        for period in kline_periods:
            print(f"\n开始下载 {symbol} 的 {period} 历史数据，从 {start_date_one_year_ago} 到 {end_date_today}...")
            try:
                xtdata.download_history_data(
                    stock_code=symbol,
                    period=period,
                    start_time=start_date_one_year_ago,
                    end_time=end_date_today
                )
                print(f"成功下载 {symbol} 的 {period} 历史数据。")

                # 增加下载后验证逻辑
                downloaded_data = xtdata.get_market_data(
                    field_list=[],
                    stock_code=[symbol],
                    period=period,
                    start_time=start_date_one_year_ago,
                    end_time=end_date_today
                )
                if downloaded_data.empty:
                    raise Exception(f"错误：下载 {symbol} 的 {period} 数据失败，请检查您的 MiniQmt 客户端或网络连接。")
                print(f"验证 {symbol} 的 {period} 数据成功。")

            except Exception as e:
                print(f"下载 {symbol} 的 {period} 历史数据失败: {e}")
                print(f"错误详情: {e}")
                print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")
                raise # 重新抛出异常，以便外部捕获

    print("\n--- 所有教程所需数据下载任务完成 ---")

if __name__ == "__main__":
    download_all_tutorial_data()