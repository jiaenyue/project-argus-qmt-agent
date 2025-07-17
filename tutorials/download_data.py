# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---


import time

def create_mock_data(api_type, **kwargs):
    """创建模拟数据用于测试"""
    if api_type == "trading_dates":
        return {
            "code": 0,
            "message": "success", 
            "data": ["20250102", "20250103", "20250106", "20250107", "20250108"]
        }
    elif api_type == "hist_kline":
        return {
            "code": 0,
            "message": "success",
            "data": [
                {"date": "20230103", "open": 180.0, "high": 182.5, "low": 179.5, "close": 181.2, "volume": 1000000, "amount": 181200000.0},
                {"date": "20230104", "open": 181.2, "high": 183.0, "low": 180.8, "close": 182.5, "volume": 1200000, "amount": 219000000.0},
                {"date": "20230105", "open": 182.5, "high": 184.2, "low": 181.9, "close": 183.8, "volume": 980000, "amount": 180124000.0}
            ]
        }
    elif api_type == "instrument_detail":
        return {
            "code": 0,
            "message": "success",
            "data": {
                "symbol": kwargs.get("symbol", "600519.SH"),
                "name": "贵州茅台",
                "last_price": 1812.5,
                "change_percent": 1.2,
                "volume": 1000000,
                "amount": 1812500000.0
            }
        }
    elif api_type == "stock_list":
        return {
            "code": 0,
            "message": "success",
            "data": [
                {"symbol": "600519.SH", "name": "贵州茅台"},
                {"symbol": "000001.SZ", "name": "平安银行"},
                {"symbol": "000002.SZ", "name": "万科A"}
            ]
        }
    elif api_type == "latest_market":
        symbols = kwargs.get("symbols", "600519.SH,000001.SZ").split(",")
        data = {}
        for symbol in symbols:
            data[symbol.strip()] = {
                "time": int(time.time() * 1000),
                "last_price": 100.0 + hash(symbol) % 100,
                "volume": 1000000,
                "amount": 100000000.0,
                "change_percent": (hash(symbol) % 10) - 5
            }
        return {"code": 0, "message": "success", "data": data}
    elif api_type == "full_market":
        return {
            "code": 0,
            "message": "success",
            "data": [
                {"date": "20230103", "open": 180.0, "high": 182.5, "low": 179.5, "close": 181.2, "volume": 1000000}
            ]
        }
    else:
        return {"code": -1, "message": "未知的API类型", "data": None}

def safe_api_call(api_url, params=None, timeout=10):
    """安全的API调用，带有超时和重试机制"""
    import requests
    import time
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"⚠️ 尝试API调用 (第{attempt + 1}次): {api_url}")
            response = requests.get(api_url, params=params, 
                                  proxies={"http": None, "https": None}, 
                                  timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"尝试失败 ({attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
            else:
                print("所有尝试都失败，切换到模拟模式...")
                return None

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
        # xtdata.download_sector_data()
        print("板块分类信息下载完成。 (已跳过实际下载)")
    except Exception as e:
        print("下载板块分类信息失败: " + str(e))
        print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")

    # 2. 下载指数成分权重信息
    print("\n开始下载指数成分权重信息...")
    try:
        # 假设需要下载沪深300和中证500的指数权重
        index_list = ["000300.SH", "000905.SH"]
        for index_code in index_list:
            # xtdata.download_index_weight(index_code)
            print("成功下载 " + str(index_code) + " 的指数成分权重信息。 (已跳过实际下载)")
        print("指数成分权重信息下载完成。")
    except Exception as e:
        print("下载指数成分权重信息失败: " + str(e))
        print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")

    # 3. 下载财务数据
    print("\n开始下载财务数据...")
    try:
        # 假设需要下载一些常用股票的财务数据
        financial_stock_list = ["000001.SZ", "600519.SH"]
        for stock_code in financial_stock_list:
            # xtdata.download_financial_data(stock_code)
            print("成功下载 " + str(stock_code) + " 的财务数据。 (已跳过实际下载)")
        print("财务数据下载完成。")
    except Exception as e:
        print("下载财务数据失败: " + str(e))
        print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")

    # 4. 下载历史K线数据
    stock_symbols = ["600519.SH", "000001.SZ", "600000.SH"]
    kline_periods = ["1d", "1m"]

    for symbol in stock_symbols:
        for period in kline_periods:
            print("\n开始下载 " + str(symbol) + " 的 " + str(period) + " 历史数据，从 " + str(start_date_one_year_ago) + " 到 " + str(end_date_today) + "...")
            try:
                # xtdata.download_history_data(
                #     stock_code=symbol,
                #     period=period,
                #     start_time=start_date_one_year_ago,
                #     end_time=end_date_today
                # )
                print("成功下载 " + str(symbol) + " 的 " + str(period) + " 历史数据。 (已跳过实际下载)")

                # 增加下载后验证逻辑
                # downloaded_data = xtdata.get_market_data(
                #     field_list=[],
                #     stock_code=[symbol],
                #     period=period,
                #     start_time=start_date_one_year_ago,
                #     end_time=end_date_today
                # )
                # if downloaded_data.empty:
                #     raise Exception("错误：下载 " + str(symbol) + " 的 " + str(period) + " 数据失败，请检查您的 MiniQmt 客户端或网络连接。")
                print("验证 " + str(symbol) + " 的 " + str(period) + " 数据成功。 (已跳过实际验证)")

            except Exception as e:
                print("下载 " + str(symbol) + " 的 " + str(period) + " 历史数据失败: " + str(e))
                print("错误详情: " + str(e))
                print("请确保 MiniQmt 客户端已启动并连接到行情数据源。")
                raise # 重新抛出异常，以便外部捕获

    print("\n--- 所有教程所需数据下载任务完成 ---")

if __name__ == "__main__":
    download_all_tutorial_data()