#!/usr/bin/env python
# -*- coding: utf-8 -*-

# API版本v1 更新时间2025年6月30日
"""
xtquantai 直接服务器 - 最终稳定版
"""

import os
import sys
import json
import traceback
import time
from typing import Dict, List, Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from datetime import datetime

# 尝试导入 xtquant 相关模块
xtdata = None
UIPanel = None

try:
    from xtquant import xtdata
    print(f"成功导入xtquant模块，路径: {xtdata.__file__}")
except ImportError as e:
    print(f"警告: 无法导入xtquant模块: {str(e)}")
    # 创建模拟的xtdata模块
    class MockXtdata:
        def get_trading_dates(self, market="SH", start_date=None, end_date=None):
            return ["20250102", "20250103", "20250106"]
        def get_instrument_detail(self, symbol):
            return {"InstrumentID": symbol, "InstrumentName": "模拟股票", "PreClose": 100.0}
        def get_market_data(self, field_list, stock_list, period, count):
            # 返回模拟的market_data，确保结构与真实数据类似
            mock_data = {
                'lastPrice': {stock_list[0]: [100.5]},
                'open': {stock_list[0]: [99.0]},
                'high': {stock_list[0]: [101.0]},
                'low': {stock_list[0]: [98.5]},
                'volume': {stock_list[0]: [100000]},
                'amount': {stock_list[0]: [10000000.0]},
                'time': {stock_list[0]: [int(time.time() * 1000)]}
            }
            return mock_data
        def get_full_kline(self, field_list, stock_list, period, count):
            # get_full_kline 不支持时，也返回模拟数据，避免报错
            mock_kline = {
                'open': {stock_list[0]: [99.0]},
                'high': {stock_list[0]: [101.0]},
                'low': {stock_list[0]: [98.5]},
                'close': {stock_list[0]: [100.5]},
                'volume': {stock_list[0]: [100000]},
                'amount': {stock_list[0]: [10000000.0]},
                'time': {stock_list[0]: [int(time.time() * 1000)]}
            }
            return mock_kline
    xtdata = MockXtdata()

# API 函数
def get_trading_dates_api(market="SH", start_date_str: Optional[str] = None, end_date_str: Optional[str] = None):
    """获取交易日期（最终修复版）"""
    try:
        # 获取原始日期数据
        all_dates = xtdata.get_trading_dates(market=market)
        if all_dates is None:
            return {"success": False, "error": f"获取市场{market}交易日失败"}

        # 日期对象转字符串
        date_strs = []
        for date_obj in all_dates:
            # 处理时间戳（毫秒）
            if isinstance(date_obj, int) and date_obj > 1000000000000:
                dt = datetime.fromtimestamp(date_obj / 1000)
                date_str = dt.strftime('%Y%m%d')
            # 处理datetime对象
            elif hasattr(date_obj, 'strftime'):
                date_str = date_obj.strftime('%Y%m%d')
            # 处理字符串格式
            elif isinstance(date_obj, str):
                date_str = date_obj.replace('-', '')
            # 处理整数格式
            elif isinstance(date_obj, int):
                date_str = str(date_obj)
            else:
                date_str = str(date_obj)
                
            if len(date_str) == 8 and date_str.isdigit():
                date_strs.append(date_str)
            else:
                print(f"警告：跳过无效日期格式: {date_obj}")

        # 应用日期范围过滤
        if start_date_str:
            date_strs = [d for d in date_strs if d >= start_date_str]
        if end_date_str:
            date_strs = [d for d in date_strs if d <= end_date_str]

        return {"success": True, "data": date_strs}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}

# HTTP 请求处理器
class XTRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 解析URL和参数
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            
            # 设置响应头
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # 路由处理
            if path == '/api/v1/get_trading_dates':
                market = query.get('market', ['SH'])[0]
                start_date = query.get('start_date', [''])[0]
                end_date = query.get('end_date', [''])[0]
                result = get_trading_dates_api(market, start_date, end_date)
                self.wfile.write(json.dumps(result).encode('utf-8'))
                return
            
            elif path == '/api/v1/hist_kline':
                symbol = query.get('symbol', [''])[0]
                start_date = query.get('start_date', [''])[0]
                end_date = query.get('end_date', [''])[0]
                frequency = query.get('frequency', ['1d'])[0]
                
                if not all([symbol, start_date, end_date, frequency]):
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "缺少必要参数: symbol, start_date, end_date, frequency"
                    }).encode('utf-8'))
                    return
                    
                # 调用xtdata获取K线数据
                kline_data = xtdata.get_market_data(
                    field_list=['open', 'high', 'low', 'close', 'volume', 'amount', 'time'],
                    stock_list=[symbol.upper()],
                    period=frequency,
                    start_time=start_date,
                    end_time=end_date,
                    count=-1 # 获取所有数据
                )

                # 转换数据格式以匹配教程脚本的预期
                formatted_kline = []
                if kline_data and 'time' in kline_data and symbol.upper() in kline_data['time']:
                    times = kline_data['time'][symbol.upper()]
                    for i in range(len(times)):
                        date_str = datetime.fromtimestamp(times[i] / 1000).strftime('%Y%m%d')
                        formatted_kline.append({
                            "date": date_str,
                            "open": kline_data.get('open', {}).get(symbol.upper(), [0.0])[i],
                            "high": kline_data.get('high', {}).get(symbol.upper(), [0.0])[i],
                            "low": kline_data.get('low', {}).get(symbol.upper(), [0.0])[i],
                            "close": kline_data.get('close', {}).get(symbol.upper(), [0.0])[i],
                            "volume": kline_data.get('volume', {}).get(symbol.upper(), [0])[i],
                            "amount": kline_data.get('amount', {}).get(symbol.upper(), [0.0])[i]
                        })
                
                self.wfile.write(json.dumps({"success": True, "data": formatted_kline}).encode('utf-8'))
                return

            elif path == '/api/v1/instrument_detail':
                symbol = query.get('symbol', [''])[0]
                if not symbol:
                    self.wfile.write(json.dumps({"success": False, "error": "缺少必要参数: symbol"}).encode('utf-8'))
                    return
                
                upper_symbol = symbol.upper()
                detail = xtdata.get_instrument_detail(upper_symbol)
                
                if detail is None or detail == {}:
                    self.wfile.write(json.dumps({"success": False, "error": f"Instrument not found: {symbol}"}).encode('utf-8'))
                    return
                
                # 尝试使用 get_market_data 获取最新行情数据
                market_data = xtdata.get_market_data(
                    field_list=['lastPrice', 'open', 'high', 'low', 'volume', 'amount', 'time'],
                    stock_list=[upper_symbol],
                    period='1d', # 获取日线数据
                    count=1
                )
                
                last_price = market_data.get('lastPrice', {}).get(upper_symbol, [0.0])[0]
                open_price = market_data.get('open', {}).get(upper_symbol, [0.0])[0]
                high_price = market_data.get('high', {}).get(upper_symbol, [0.0])[0]
                low_price = market_data.get('low', {}).get(upper_symbol, [0.0])[0]
                volume = market_data.get('volume', {}).get(upper_symbol, [0])[0]
                amount = market_data.get('amount', {}).get(upper_symbol, [0.0])[0]
                timestamp = market_data.get('time', {}).get(upper_symbol, [0])[0]

                pre_close = detail.get("PreClose", 0.0)
                
                change_percent = 0.0
                if pre_close and last_price is not None:
                    if pre_close != 0:
                        change_percent = ((last_price - pre_close) / pre_close) * 100
                    else:
                        change_percent = 0.0

                response_data = {
                    "symbol": detail.get("InstrumentID", symbol),
                    "name": detail.get("InstrumentName", symbol),
                    "last_price": last_price,
                    "open_price": open_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "close_price": last_price, # 通常最新价和收盘价在日线数据中是一致的
                    "volume": volume,
                    "amount": amount,
                    "timestamp": timestamp,
                    "change_percent": change_percent
                }
                self.wfile.write(json.dumps({"success": True, "data": response_data}).encode('utf-8'))
                return

            elif path == '/api/v1/stock_list':
                sector = query.get('sector', [''])[0]
                if not sector:
                    self.wfile.write(json.dumps({"success": False, "error": "缺少必要参数: sector"}).encode('utf-8'))
                    return
                # 调用xtdata获取板块股票列表
                stock_list = xtdata.get_stock_list_in_sector(sector)
                if stock_list is None:
                    stock_list = [] # 确保返回列表
                
                # 转换为教程脚本期望的格式
                formatted_stock_list = [{"symbol": s, "name": xtdata.get_instrument_detail(s).get("InstrumentName", s)} for s in stock_list]
                self.wfile.write(json.dumps({"success": True, "data": formatted_stock_list}).encode('utf-8'))
                return

            elif path == '/api/v1/latest_market':
                symbols = query.get('symbols', [''])[0]
                if not symbols:
                    self.wfile.write(json.dumps({"success": False, "error": "缺少必要参数: symbols"}).encode('utf-8'))
                    return
                symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
                
                # 调用xtdata获取最新市场数据
                market_data = xtdata.get_market_data(
                    field_list=['lastPrice', 'open', 'high', 'low', 'volume', 'amount', 'time'],
                    stock_list=symbol_list,
                    period='tick',
                    count=1
                )
                
                result = {}
                for symbol_item in symbol_list:
                    last_price = market_data.get('lastPrice', {}).get(symbol_item, [0.0])[0]
                    open_price = market_data.get('open', {}).get(symbol_item, [0.0])[0]
                    high_price = market_data.get('high', {}).get(symbol_item, [0.0])[0]
                    low_price = market_data.get('low', {}).get(symbol_item, [0.0])[0]
                    volume = market_data.get('volume', {}).get(symbol_item, [0])[0]
                    amount = market_data.get('amount', {}).get(symbol_item, [0.0])[0]
                    timestamp = market_data.get('time', {}).get(symbol_item, [0])[0]

                    detail = xtdata.get_instrument_detail(symbol_item)
                    pre_close = detail.get("PreClose", 0.0)
                    
                    change_percent = 0.0
                    if pre_close and last_price is not None:
                        if pre_close != 0:
                            change_percent = ((last_price - pre_close) / pre_close) * 100
                        else:
                            change_percent = 0.0
                    
                    result[symbol_item] = {
                        "time": timestamp,
                        "last_price": last_price,
                        "volume": volume,
                        "amount": amount,
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "change_percent": change_percent # 添加涨跌幅
                    }
                self.wfile.write(json.dumps({"success": True, "data": result}).encode('utf-8'))
                return

            elif path == '/api/v1/full_market':
                symbol = query.get('symbol', [''])[0]
                fields = query.get('fields', [''])[0]
                if not symbol:
                    self.wfile.write(json.dumps({"success": False, "error": "缺少必要参数: symbol"}).encode('utf-8'))
                    return
                
                upper_symbol = symbol.strip().upper()
                field_list = [f.strip() for f in fields.split(',') if f.strip()] if fields else ['open', 'high', 'low', 'close', 'volume', 'amount', 'time']

                # 调用xtdata获取完整行情数据
                market_data = xtdata.get_market_data(
                    field_list=field_list,
                    stock_list=[upper_symbol],
                    period='1d', # 获取日线数据
                    count=-1 # 获取所有数据
                )
                
                formatted_data = []
                if market_data and 'time' in market_data and upper_symbol in market_data['time']:
                    times = market_data['time'][upper_symbol]
                    for i in range(len(times)):
                        entry = {"date": datetime.fromtimestamp(times[i] / 1000).strftime('%Y%m%d')}
                        for field in field_list:
                            value = market_data.get(field, {}).get(upper_symbol, [None])[i]
                            if isinstance(value, np.integer):
                                value = int(value)
                            elif isinstance(value, np.floating):
                                value = float(value)
                            entry[field] = value
                        formatted_data.append(entry)

                self.wfile.write(json.dumps({"success": True, "data": formatted_data}).encode('utf-8'))
                return
            
            elif path == '/api/health':
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": "服务运行正常"
                }).encode('utf-8'))
                return
            
            else:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": f"无效的API路径: {path}"
                }).encode('utf-8'))
                
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "error": f"服务器内部错误: {str(e)}"
            }).encode('utf-8'))
            traceback.print_exc()

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, XTRequestHandler)
    print(f"服务器启动在端口: {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="xtquantai服务器")
    parser.add_argument("--port", type=int, default=8000, help="端口号")
    args = parser.parse_args()
    
    run_server(args.port)