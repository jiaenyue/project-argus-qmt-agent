import asyncio
from typing import Optional, List, Dict, Any
import json
import sys
import os
import traceback
import time
import re  # 添加正则表达式模块用于日期格式验证

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl, BaseModel
import mcp.server.stdio

# 添加可能的xtquant模块路径
possible_paths = [
    os.path.expanduser("~/.local/lib/python3.11/site-packages"),
    os.path.expanduser("~/AppData/Local/Programs/Python/Python311/Lib/site-packages"),
    os.path.expanduser("~/App极长内容省略...详见原始文件"),
    # ... 其他路径 ...
]

# 导入xtquant相关模块
xtdata = None
UIPanel = None

try:
    from xtquant import xtdata
    print(f"成功导入xtquant模块，路径: {xtdata.__file__ if hasattr(xtdata, '__file__') else '未知'}")
    
    # 尝试导入UIPanel
    try:
        from xtquant.xtdata import UIPanel
        print("成功导入UIPanel类")
    except ImportError:
        # 创建模拟的UIPanel类
        class UIPanel:
            def __init__(self, stock, period, figures=None):
                self.stock = stock
                self.period = period
                self.figures = figures or []
            
            def __str__(self):
                return f"UIPanel(stock={self.stock}, period={self.period}, figures={self.figures})"
except ImportError:
    # 创建模拟的xtdata模块
    class MockXtdata:
        def get_trading_dates(self, market="SH"):
            return ["2023-01-01", "2023-01-02", "2023-01-03"]
        
        def get_stock_list_in_sector(self, sector="沪深A股"):
            return ["000001.SZ", "600519.SH", "300059.SZ"]
        
        def get_instrument_detail(self, code, iscomplete=False):
            return {"code": code, "name": "模拟股票", "price": 100.0}
        
        def apply_ui_panel_control(self, panels):
            return True
        
        def get_market_data(self, fields, stock_list, period="1d", start_time="", end_time="", count=-1, dividend_type="none", fill_data=True):
            # 创建模拟数据
            result = {}
            for stock in stock_list:
                stock_data = {}
                for field in fields:
                    if field == "close":
                        stock_data[field] = [100.0, 101.0, 102.0]
                    elif field == "open":
                        stock_data[field] = [99.0, 100.0, 101.0]
                    elif field == "high":
                        stock_data[field] = [102.0, 103.0, 104.0]
                    elif field == "low":
                        stock_data[field] = [98.0, 99.0, 100.0]
                    elif field == "volume":
                        stock_data[field] = [10000, 12000, 15000]
                    else:
                        stock_data[field] = [0.0, 0.0, 0.0]
                result[stock] = stock_data
            return result
    
    xtdata = MockXtdata()
    
    # 创建模拟的UIPanel类
    class UIPanel:
        def __init__(self, stock, period, figures=None):
            self.stock = stock
            self.period = period
            self.figures = figures or []
        
        def __str__(self):
            return f"UIPanel(stock={self.stock}, period={self.period}, figures={self.figures})"

# Initialize XTQuant data service
xtdc_initialized = False

# 自定义Server类添加HTTP路由支持
class CustomServer(Server):
    def __init__(self, name: str):
        super().__init__(name)
        self.http_routes = {}
    
    def http_route(self, path: str, methods: list):
        def decorator(handler):
            self.http_routes[path] = {"handler": handler, "methods": methods}
            return handler
        return decorator

server = CustomServer("xtquantai")

def ensure_xtdc_initialized():
    global xtdc_initialized
    if not xtdc_initialized:
        try:
            if hasattr(xtdata, 'start_xtdata'):
                xtdata.start_xtdata()
            xtdc_initialized = True
        except Exception as e:
            print(f"初始化失败: {str(e)}")
            traceback.print_exc()

# 定义工具输入模型
class GetTradingDatesInput(BaseModel):
    market: str = "SH"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class XTQuantAIHandler:
    def __init__(self):
        self.wfile = None
        self.path = ""
        
    def send_response(self, code):
        pass
        
    def send_header(self, key, value):
        pass
        
    def end_headers(self):
        pass
        
    @staticmethod
    def get_trading_dates(market, start_date, end_date):
        ensure_xtdc_initialized()
        try:
            # 参数验证
            date_pattern = re.compile(r"^\d{8}$")
            
            # 增强日期验证逻辑
            def validate_date(date_str, field_name):
                if date_str is None or date_str == "":  # None 或空字符串都应被忽略
                    return None
                if not date_str:
                    return f"{field_name}格式错误，应为YYYYMMDD"
                if not date_pattern.match(date_str):
                    return f"{field_name}格式错误，应为YYYYMMDD"
                try:
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    if month < 1 or month > 12:
                        return f"{field_name}月份无效"
                    if day < 1 or day > 31:
                        return f"{field_name}日期无效"
                except Exception:
                    return f"{field_name}包含无效数字"
                return None
            
            start_error = validate_date(start_date, "start_date")
            if start_error:
                return {"success": False, "data": start_error}
                
            end_error = validate_date(end_date, "end_date")
            if end_error:
                return {"success": False, "data": end_error}
                
            if start_date and end_date and start_date > end_date:
                return {"success": False, "data": "start_date不能大于end_date"}
            
            dates = xtdata.get_trading_dates(market)
            dates = [d.replace("-", "") for d in dates] if dates else []
            if start_date:
                dates = [d for d in dates if d >= start_date]
            if end_date:
                dates = [d for d in dates if d <= end_date]
            return {"success": True, "data": dates}
        except Exception as e:
            print(f"获取交易日失败: {str(e)}")
            traceback.print_exc()
            return {"success": False, "data": f"错误: {str(e)}"}

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools = [
        types.Tool(
            name="get_trading_dates",
            description="获取交易日期",
            inputSchema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "default": "SH"
                    },
                    "start_date": {
                        "type": "string",
                        "nullable": True
                    },
                    "end_date": {
                        "type": "string",
                        "nullable": True
                    }
                }
            }
        )
    ]
    return tools

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name == "get_trading_dates":
        # 解析请求参数
        market = arguments.get("market", "SH") if arguments else "SH"
        start_date = arguments.get("start_date") if arguments else None
        end_date = arguments.get("end_date") if arguments else None
        
        # 获取交易日历数据
        dates = XTQuantAIHandler.get_trading_dates(market, start_date, end_date)
        
        # 包装为标准响应格式
        response_data = {"success": True, "data": dates}
        return [types.TextContent(text=json.dumps(response_data))]
    else:
        raise ValueError(f"不支持的工具: {name}")

# 添加交易日历HTTP路由
@server.http_route("/api/get_trading_dates", methods=["GET"])
async def handle_get_trading_dates(request):
    params = request.query_params
    result = XTQuantAIHandler.get_trading_dates(
        market=params.get("market"),
        start_date=params.get("start_date"),
        end_date=params.get("end_date")
    )
    
    # 总是返回200状态码，错误信息在响应体中
    status_code = 200
    
    return {
        "status": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result, ensure_ascii=False)
    }

if __name__ == "__main__":
    asyncio.run(server.start())