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
    xtdata = MockXtdata()

# API 函数
def get_trading_dates(market="SH", start_date_str: Optional[str] = None, end_date_str: Optional[str] = None):
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
            # 添加历史K线端点
            if path == '/api/v1/hist_kline':
                symbol = query.get('symbol', [''])[0]
                start_date = query.get('start_date', [''])[0]
                end_date = query.get('end_date', [''])[0]
                frequency = query.get('frequency', ['1d'])[0]
                
                # 参数验证
                if not all([symbol, start_date, end_date, frequency]):
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "缺少必要参数: symbol, start_date, end_date, frequency"
                    }).encode('utf-8'))
                    return
                    
                # 模拟数据返回 (实际实现需连接量化平台API)
                simulated_data = [
                    {"date": "20230103", "open": 180.0, "high": 182.5, "low": 179.5, "close": 181.2, "volume": 100000},
                    {"date": "20230104", "open": 181.5, "high": 183.8, "low": 180.8, "close": 182.0, "volume": 120000},
                    {"date": "20230105", "open": 182.5, "high": 184.0, "low": 181.0, "close": 183.5, "volume": 95000}
                ]
                
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": simulated_data
                }).encode('utf-8'))
                return
            # 添加健康检查端点
            if path == '/api/health':
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": "服务运行正常"
                }).encode('utf-8'))
                return
            if path == '/api/v1/get_trading_dates':
                market = query.get('market', ['SH'])[0]
                start_date = query.get('start_date', [''])[0]
                end_date = query.get('end_date', [''])[0]
                
                result = get_trading_dates(market, start_date, end_date)
                self.wfile.write(json.dumps(result).encode('utf-8'))
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