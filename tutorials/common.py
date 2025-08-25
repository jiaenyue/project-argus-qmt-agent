# Combined common module for Project Argus QMT tutorials

import os
import sys
import time
import datetime
import re
import json
import requests
import logging
import math
import random
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from urllib.parse import urljoin
from collections import defaultdict

# 导入配置文件
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from config.app_config import app_config
    DEFAULT_BASE_URL = f"http://{app_config.DATA_AGENT_SERVICE_HOST}:{app_config.DATA_AGENT_SERVICE_PORT}"
except ImportError:
    # 如果配置文件不存在，使用默认值
    DEFAULT_BASE_URL = "http://127.0.0.1:8002"

# --- Contents from api_client.py ---

class APIClient:
    """一个简单的API客户端，用于与QMT后端服务交互"""
    
    def __init__(self, base_url: str, timeout: int = 10, max_retries: int = 3, retry_delay: float = 1.0):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        # 为本地和局域网请求跳过HTTP代理
        self.session.proxies = {"http": None, "https": None}
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Project-Argus-QMT-Tutorials/1.0'
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status() 
                return response.json()
            except requests.exceptions.RequestException as e:
                logging.warning(f"API请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logging.error(f"API请求在 {self.max_retries} 次尝试后最终失败: {e}")
                    return {"code": -1, "message": f"API request failed: {e}", "data": None}

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request('GET', endpoint, params=params)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request('POST', endpoint, json=data)

    def get_trading_dates(self, market: str, start_date: Optional[str] = None, end_date: Optional[str] = None, count: Optional[int] = None) -> Dict[str, Any]:
        """获取交易日历"""
        params = {"market": market}
        if start_date:
            params["start_time"] = start_date  # API期望start_time参数
        if end_date:
            params["end_time"] = end_date      # API期望end_time参数
        if count:
            params["count"] = count
        return self.get("/api/v1/get_trading_dates", params=params)  # 使用正确的API路径

    def get_hist_kline(self, symbol: str, start_date: str, end_date: str, period: str = "1d", dividend_type: str = "none") -> Dict[str, Any]:
        """获取历史K线"""
        params = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "period": period,
            "dividend_type": dividend_type,
        }
        return self.get("/api/v1/hist_kline", params=params)

    def get_instrument_detail(self, symbol: Union[str, List[str]]) -> Dict[str, Any]:
        """获取合约详情"""
        # 注意：实际API路径需要symbol作为路径参数，这里需要特殊处理
        if isinstance(symbol, list):
            symbol = symbol[0]  # 如果是列表，取第一个
        return self.get(f"/api/v1/instrument_detail/{symbol}")

    def get_stock_list(self, market: str = "A", date: Optional[str] = None) -> Dict[str, Any]:
        """获取股票列表"""
        params = {"market": market}
        if date:
            params["date"] = date
        return self.get("/api/v1/stock_list_in_sector", params=params)

    def subscribe(self, symbols: List[str]) -> Dict[str, Any]:
        """订阅行情"""
        return self.post("/subscribe", data={"symbols": symbols})

    def get_full_tick(self, symbols: List[str]) -> Dict[str, Any]:
        """获取全推行情"""
        params = {"symbols": ",".join(symbols)}
        return self.get("/api/v1/full_market_data", params=params)
        
    def get_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取市场快照"""
        params = {"symbols": ",".join(symbols)}
        return self.get("/api/v1/latest_market_data", params=params)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_api_client() -> APIClient:
    """创建并返回一个API客户端实例"""
    config = get_config().api
    return APIClient(
        base_url=config.base_url,
        timeout=config.timeout,
        max_retries=config.max_retries,
        retry_delay=config.retry_delay
    )

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
                print("所有尝试都失败，请检查网络连接和API配置")
                print("确保数据服务可用，API密钥和访问权限正确设置")
                print("如果问题持续存在，请联系数据服务提供商")
                return None


# --- Contents from config.py ---

@dataclass
class APIConfig:
    """API配置类"""
    base_url: str = DEFAULT_BASE_URL  # 使用配置文件中的地址
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    
    def validate(self) -> bool:
        """验证API配置的有效性"""
        if not self.base_url or not isinstance(self.base_url, str):
            return False
        if self.timeout <= 0 or self.max_retries < 0:
            return False
        if self.retry_delay < 0:
            return False
        return True

@dataclass 
class DisplayConfig:
    """显示配置类"""
    max_display_items: int = 10
    enable_performance_monitoring: bool = True
    show_timestamps: bool = True
    decimal_places: int = 4
    
    def validate(self) -> bool:
        """验证显示配置的有效性"""
        if self.max_display_items <= 0:
            return False
        if self.decimal_places < 0:
            return False
        return True

class TutorialConfig:
    """教程配置管理类"""
    
    def __init__(self):
        self._api_config = None
        self._display_config = None
        self._demo_data = None
        self._load_config()
    
    def _load_config(self):
        self._api_config = APIConfig(
            base_url=os.getenv('QMT_API_BASE_URL', DEFAULT_BASE_URL),  # 使用配置文件中的地址
            timeout=int(os.getenv('QMT_API_TIMEOUT', '10')),
            max_retries=int(os.getenv('QMT_API_MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('QMT_API_RETRY_DELAY', '1.0'))
        )
        self._display_config = DisplayConfig(
            max_display_items=int(os.getenv('QMT_MAX_DISPLAY_ITEMS', '10')),
            enable_performance_monitoring=os.getenv('QMT_ENABLE_PERF_MONITORING', 'true').lower() == 'true',
            show_timestamps=os.getenv('QMT_SHOW_TIMESTAMPS', 'true').lower() == 'true',
            decimal_places=int(os.getenv('QMT_DECIMAL_PLACES', '4'))
        )
        self._demo_data = {
            'symbols': ["600519.SH", "000858.SZ", "601318.SH", "000001.SZ", "600036.SH"],
            'markets': ["SH", "SZ"],
            'frequencies': ["1m", "5m", "15m", "30m", "1h", "1d"],
            'default_date_range': 30
        }
    
    @property
    def api(self) -> APIConfig:
        return self._api_config
    
    @property
    def display(self) -> DisplayConfig:
        return self._display_config
    
    @property
    def demo_symbols(self) -> List[str]:
        return self._demo_data['symbols'].copy()
    
    @property
    def demo_markets(self) -> List[str]:
        return self._demo_data['markets'].copy()
    
    @property
    def demo_frequencies(self) -> List[str]:
        return self._demo_data['frequencies'].copy()
    
    @property
    def default_date_range(self) -> int:
        return self._demo_data['default_date_range']
    
    def is_valid(self) -> bool:
        return self._api_config.validate() and self._display_config.validate()

config_instance = TutorialConfig()

def get_config() -> TutorialConfig:
    return config_instance

# --- Contents from utils.py ---

def format_response_time(seconds: float) -> str:
    """格式化响应时间显示"""
    if seconds < 0.001:
        return f"{seconds * 1000:.2f} ms"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"

def print_subsection_header(title: str, width: int = 50, char: str = "-") -> None:
    """打印子章节标题"""
    padding = (width - len(title) - 2) // 2
    remaining = width - len(title) - 2 - padding
    print(f"{char * padding} {title} {char * remaining}")

def format_number(num: Union[int, float], precision: int = 2) -> str:
    """格式化数字，添加千位分隔符并控制小数位数"""
    if isinstance(num, (int, float)):
        return f"{num:,.{precision}f}"
    return str(num)

@dataclass
class DemoContext:
    """演示上下文，用于存储和传递演示过程中的状态"""
    api_client: Any
    performance_monitor: Any
    config: Any
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class PerformanceMonitor:
    """性能监控器，用于记录和分析API调用耗时"""
    def __init__(self):
        self.records = defaultdict(list)

    def record_api_call(self, api_name: str, duration: float, success: bool):
        self.records[api_name].append({
            'duration': duration,
            'success': success,
            'timestamp': time.time()
        })

    def print_summary(self):
        print_section_header("性能统计报告")
        if not self.records:
            print("没有记录到任何API调用。")
            return

        for api_name, calls in self.records.items():
            total_calls = len(calls)
            successful_calls = sum(1 for call in calls if call['success'])
            failed_calls = total_calls - successful_calls
            avg_duration = sum(call['duration'] for call in calls) / total_calls if total_calls > 0 else 0

            print(f"\nAPI: {api_name}")
            print(f"  - 总调用次数: {total_calls}")
            print(f"  - 成功率: {successful_calls / total_calls:.2%} ({successful_calls}/{total_calls})")
            if failed_calls > 0:
                print(f"  - 失败次数: {failed_calls}")
            print(f"  - 平均耗时: {format_response_time(avg_duration)}")

def create_demo_context() -> DemoContext:
    """创建并返回一个演示上下文实例"""
    return DemoContext(
        api_client=create_api_client(),
        performance_monitor=PerformanceMonitor(),
        config=get_config()
    )



def print_section_header(title: str, width: int = 60, char: str = "=") -> None:
    """打印章节标题"""
    padding = (width - len(title) - 2) // 2
    remaining = width - len(title) - 2 - padding
    print(f"{char * padding} {title} {char * remaining}")

def get_date_range(days_ago: int) -> tuple[str, str]:
    """获取从几天前到今天的日期范围"""
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days_ago)
    return start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def print_api_result(result: Any, title: str = None, max_items: int = 10) -> None:
    """统一的API结果显示格式"""
    if title:
        print_section_header(title)
    
    if isinstance(result, dict) and 'data' in result:
        data = result['data']
        print(f"  状态码: {result.get('code', 'N/A')}, 消息: {result.get('message', 'N/A')}")
        if isinstance(data, list):
            print(f"  数据 (前 {min(len(data), max_items)} 项):")
            for item in data[:max_items]:
                print(f"    - {item}")
            if len(data) > max_items:
                print(f"    ... (还有 {len(data) - max_items} 项)")
        else:
            print(f"  数据: {data}")
    else:
        print(f"结果: {result}")

def validate_date_format(date_str: str) -> bool:
    """验证日期格式 YYYY-MM-DD"""
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', date_str))

def validate_symbol_format(symbol: str) -> bool:
    """验证股票代码格式 600519.SH"""
    return bool(re.match(r'^\d{6}\.(SH|SZ)$', symbol))

# --- Mock data functionality removed ---
# Project no longer supports mock data mode. All API calls must connect to real miniQMT.

# --- Contents from api_client.py ---

class APIError(Exception):
    """API调用异常类"""
    pass

class ConnectionError(APIError):
    """连接错误异常类"""
    pass

class TimeoutError(APIError):
    """超时错误异常类"""
    pass

class QMTAPIClient:
    """统一的QMT API客户端"""
    def __init__(self, **kwargs):
        self.config = get_config()
        self.base_url = kwargs.get('base_url', self.config.api.base_url)
        self.timeout = kwargs.get('timeout', self.config.api.timeout)
        self.max_retries = kwargs.get('max_retries', self.config.api.max_retries)
        self.retry_delay = kwargs.get('retry_delay', self.config.api.retry_delay)
        self.performance_monitor = PerformanceMonitor() if self.config.display.enable_performance_monitoring else None
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                duration = time.time() - start_time
                if self.performance_monitor:
                    self.performance_monitor.record_api_call(endpoint, duration, True)
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    duration = time.time() - start_time
                    if self.performance_monitor:
                        self.performance_monitor.record_api_call(endpoint, duration, False)
                    raise APIError(f"API调用失败，无法连接到miniQMT服务: {e}")
                time.sleep(self.retry_delay)
        
        # This should not be reached
        raise APIError("API调用失败，请确保miniQMT服务正在运行")

    def get_trading_dates(self, market: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        params = {"market": market, "start_date": start_date, "end_date": end_date}
        return self._make_request('GET', 'get_trading_dates', params={k: v for k, v in params.items() if v})

    def get_hist_kline(self, symbol: str, period: str, start_time: str, end_time: str) -> Dict[str, Any]:
        params = {"symbol": symbol, "period": period, "start_time": start_time, "end_time": end_time}
        return self._make_request('GET', 'get_hist_kline', params=params)

# --- Exports from __init__.py ---
# These are now globally available in this module
__all__ = [
    'TutorialConfig',
    'PerformanceMonitor', 
    'format_response_time',
    'print_section_header',
    'print_api_result',
    'validate_date_format',
    'QMTAPIClient',
    'get_config'
]