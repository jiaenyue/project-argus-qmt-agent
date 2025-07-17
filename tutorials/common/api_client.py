"""
统一的 API 客户端模块 - Project Argus QMT 数据代理服务教程

提供统一的QMT API客户端，包含重试机制、错误处理、超时处理和性能监控功能。
实现所有API端点的标准化调用方法。
"""

import time
import requests
import json
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin
import logging

from .config import get_config
from .utils import PerformanceMonitor, format_response_time, validate_date_format, validate_symbol_format


class APIError(Exception):
    """API调用异常类"""
    
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class ConnectionError(APIError):
    """连接错误异常类"""
    pass


class TimeoutError(APIError):
    """超时错误异常类"""
    pass


class QMTAPIClient:
    """统一的QMT API客户端
    
    提供重试机制、错误处理、超时处理和性能监控功能。
    支持所有QMT API端点的标准化调用。
    """
    
    def __init__(self, base_url: str = None, timeout: int = None, 
                 max_retries: int = None, retry_delay: float = None,
                 enable_monitoring: bool = True):
        """初始化API客户端
        
        Args:
            base_url (str, optional): API基础URL
            timeout (int, optional): 请求超时时间（秒）
            max_retries (int, optional): 最大重试次数
            retry_delay (float, optional): 重试延迟时间（秒）
            enable_monitoring (bool): 是否启用性能监控
        """
        self.config = get_config()
        
        # 使用传入参数或配置文件中的默认值
        self.base_url = base_url or self.config.api.base_url
        self.timeout = timeout or self.config.api.timeout
        self.max_retries = max_retries or self.config.api.max_retries
        self.retry_delay = retry_delay or self.config.api.retry_delay
        
        # 确保URL以/结尾
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        
        # 性能监控
        self.enable_monitoring = enable_monitoring
        self.performance_monitor = PerformanceMonitor() if enable_monitoring else None
        
        # 会话管理，复用连接
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'QMT-Tutorial-Client/1.0'
        })
        
        # 配置代理设置 - 对于本地API调用跳过代理
        if self._is_local_url(self.base_url):
            self.session.proxies = {
                'http': None,
                'https': None
            }
            # 设置环境变量以确保跳过代理
            import os
            os.environ['NO_PROXY'] = '127.0.0.1,localhost'
        
        # 日志配置
        self.logger = logging.getLogger(__name__)
    
    def _is_local_url(self, url: str) -> bool:
        """检查URL是否为本地地址
        
        Args:
            url (str): 要检查的URL
            
        Returns:
            bool: 是否为本地地址
        """
        local_hosts = ['127.0.0.1', 'localhost', '0.0.0.0']
        return any(host in url for host in local_hosts)
    
    def _build_url(self, endpoint: str) -> str:
        """构建完整的API URL
        
        Args:
            endpoint (str): API端点路径
            
        Returns:
            str: 完整的URL
        """
        # 移除端点开头的斜杠避免重复
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
        
        return urljoin(self.base_url, endpoint)
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, 
                     data: Dict = None, **kwargs) -> requests.Response:
        """执行HTTP请求
        
        Args:
            method (str): HTTP方法
            endpoint (str): API端点
            params (Dict, optional): URL参数
            data (Dict, optional): 请求体数据
            **kwargs: 其他请求参数
            
        Returns:
            requests.Response: HTTP响应对象
            
        Raises:
            ConnectionError: 连接错误
            TimeoutError: 超时错误
            APIError: 其他API错误
        """
        url = self._build_url(endpoint)
        
        # 准备请求参数
        request_kwargs = {
            'timeout': self.timeout,
            'params': params,
            **kwargs
        }
        
        # 处理请求体数据
        if data is not None:
            if method.upper() in ['POST', 'PUT', 'PATCH']:
                request_kwargs['json'] = data
            else:
                request_kwargs['params'] = {**(params or {}), **data}
        
        try:
            response = self.session.request(method, url, **request_kwargs)
            return response
            
        except requests.exceptions.ConnectTimeout:
            raise TimeoutError(f"连接超时: {url}")
        except requests.exceptions.ReadTimeout:
            raise TimeoutError(f"读取超时: {url}")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"连接错误: {url} - {str(e)}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"请求错误: {url} - {str(e)}")
    
    def call_api(self, endpoint: str, method: str = 'GET', params: Dict = None, 
                data: Dict = None, **kwargs) -> Dict[str, Any]:
        """统一的API调用方法，包含重试和错误处理
        
        Args:
            endpoint (str): API端点路径
            method (str): HTTP方法，默认GET
            params (Dict, optional): URL参数
            data (Dict, optional): 请求体数据
            **kwargs: 其他请求参数
            
        Returns:
            Dict[str, Any]: 标准化的API响应
            
        Raises:
            APIError: API调用失败
        """
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 记录重试信息
                if attempt > 0:
                    self.logger.info(f"重试API调用 {endpoint} (第{attempt}次)")
                    time.sleep(self.retry_delay)
                
                # 执行请求
                response = self._make_request(method, endpoint, params, data, **kwargs)
                duration = time.time() - start_time
                
                # 处理响应
                result = self._process_response(response, endpoint, duration)
                
                # 记录成功的调用
                if self.performance_monitor:
                    self.performance_monitor.record_api_call(
                        endpoint, duration, True
                    )
                
                return result
                
            except (ConnectionError, TimeoutError, APIError) as e:
                last_error = e
                self.logger.warning(f"API调用失败 {endpoint}: {str(e)}")
                
                # 如果是最后一次尝试，不再重试
                if attempt == self.max_retries:
                    break
                
                # 某些错误不需要重试
                if isinstance(e, APIError) and hasattr(e, 'status_code'):
                    if e.status_code in [400, 401, 403, 404]:  # 客户端错误不重试
                        break
        
        # 所有重试都失败了
        duration = time.time() - start_time
        if self.performance_monitor:
            self.performance_monitor.record_api_call(
                endpoint, duration, False, str(last_error)
            )
        
        raise last_error or APIError(f"API调用失败: {endpoint}")
    
    def _process_response(self, response: requests.Response, endpoint: str, 
                         duration: float) -> Dict[str, Any]:
        """处理API响应
        
        Args:
            response (requests.Response): HTTP响应对象
            endpoint (str): API端点
            duration (float): 请求耗时
            
        Returns:
            Dict[str, Any]: 标准化的响应数据
            
        Raises:
            APIError: 响应处理失败
        """
        # 检查HTTP状态码
        if not response.ok:
            error_msg = f"HTTP {response.status_code}: {response.reason}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
            
            raise APIError(
                error_msg, 
                status_code=response.status_code,
                response_data={'status_code': response.status_code, 'reason': response.reason}
            )
        
        # 解析JSON响应
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise APIError(f"响应JSON解析失败: {str(e)}")
        
        # 标准化响应格式
        if isinstance(data, dict) and 'code' in data:
            # 已经是标准格式
            result = data.copy()
        else:
            # 转换为标准格式
            result = {
                'code': 0,
                'message': 'success',
                'data': data
            }
        
        # 添加性能信息
        result['duration'] = duration
        result['timestamp'] = int(time.time())
        
        return result
    
    def _validate_parameters(self, **kwargs) -> None:
        """验证API参数
        
        Args:
            **kwargs: 参数字典
            
        Raises:
            APIError: 参数验证失败
        """
        for key, value in kwargs.items():
            if key in ['start_date', 'end_date'] and value:
                if not validate_date_format(value):
                    raise APIError(f"日期格式错误: {key}={value}, 应为YYYY-MM-DD格式")
            
            elif key in ['symbol', 'symbols'] and value:
                symbols = [value] if isinstance(value, str) else value
                for symbol in symbols:
                    if not validate_symbol_format(symbol):
                        raise APIError(f"股票代码格式错误: {symbol}, 应为XXXXXX.SH或XXXXXX.SZ格式")
            
            elif key == 'market' and value:
                if value not in ['SH', 'SZ']:
                    raise APIError(f"市场代码错误: {value}, 应为SH或SZ")
            
            elif key == 'frequency' and value:
                valid_frequencies = ['tick', '1m', '5m', '15m', '30m', '1h', '1d', '1w', '1M']
                if value not in valid_frequencies:
                    raise APIError(f"频率参数错误: {value}, 应为{valid_frequencies}中的一个")
            
            elif key == 'count' and value is not None:
                if not isinstance(value, int) or (value < -1 or value == 0):
                    raise APIError(f"数量参数错误: {value}, 应为正整数或-1")

    def get_trading_dates(self, market: str, start_date: str = None, 
                         end_date: str = None, count: int = -1) -> Dict[str, Any]:
        """获取交易日历
        
        Args:
            market (str): 市场代码 (SH/SZ)
            start_date (str, optional): 开始日期 YYYY-MM-DD
            end_date (str, optional): 结束日期 YYYY-MM-DD
            count (int): 返回数量，-1表示全部
            
        Returns:
            Dict[str, Any]: 交易日历数据
            
        Raises:
            APIError: 参数验证失败
        """
        # 参数验证
        self._validate_parameters(
            market=market, 
            start_date=start_date, 
            end_date=end_date, 
            count=count
        )
        
        params = {'market': market}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if count != -1:
            params['count'] = count
        
        return self.call_api('trading_dates', params=params)
    
    def get_hist_kline(self, symbol: str, start_date: str, end_date: str, 
                      frequency: str = "1d") -> Dict[str, Any]:
        """获取历史K线数据
        
        Args:
            symbol (str): 股票代码
            start_date (str): 开始日期 YYYY-MM-DD
            end_date (str): 结束日期 YYYY-MM-DD
            frequency (str): 频率，默认1d
            
        Returns:
            Dict[str, Any]: 历史K线数据
            
        Raises:
            APIError: 参数验证失败
        """
        # 参数验证
        self._validate_parameters(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency
        )
        
        params = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'frequency': frequency
        }
        
        return self.call_api('hist_kline', params=params)    

    def get_instrument_detail(self, symbols: Union[str, List[str]]) -> Dict[str, Any]:
        """获取合约详情
        
        Args:
            symbols (Union[str, List[str]]): 股票代码或代码列表
            
        Returns:
            Dict[str, Any]: 合约详情数据
            
        Raises:
            APIError: 参数验证失败
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # 参数验证
        self._validate_parameters(symbols=symbols)
        
        params = {'symbols': ','.join(symbols)}
        return self.call_api('instrument_detail', params=params)
    
    def get_stock_list(self, market: str = None, sector: str = None) -> Dict[str, Any]:
        """获取股票列表
        
        Args:
            market (str, optional): 市场代码
            sector (str, optional): 板块代码
            
        Returns:
            Dict[str, Any]: 股票列表数据
        """
        params = {}
        if market:
            params['market'] = market
        if sector:
            params['sector'] = sector
        
        return self.call_api('stock_list', params=params)
    
    def get_sector_list(self) -> Dict[str, Any]:
        """获取板块列表
        
        Returns:
            Dict[str, Any]: 板块列表数据
        """
        return self.call_api('sector_list')
    
    def get_stock_list_in_sector(self, sector_name: str, real_timetag: str = None) -> Dict[str, Any]:
        """获取指定板块的成分股列表
        
        Args:
            sector_name (str): 板块名称
            real_timetag (str, optional): 历史时间点，格式YYYYMMDD
            
        Returns:
            Dict[str, Any]: 板块成分股数据
        """
        params = {'sector_name': sector_name}
        if real_timetag:
            params['real_timetag'] = real_timetag
        
        return self.call_api('stock_list_in_sector', params=params)
    
    def download_sector_data(self) -> Dict[str, Any]:
        """下载板块数据
        
        Returns:
            Dict[str, Any]: 下载结果
        """
        return self.call_api('download_sector_data', method='POST')
    
    def get_latest_market(self, symbols: Union[str, List[str]]) -> Dict[str, Any]:
        """获取最新行情
        
        Args:
            symbols (Union[str, List[str]]): 股票代码或代码列表
            
        Returns:
            Dict[str, Any]: 最新行情数据
            
        Raises:
            APIError: 参数验证失败
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # 参数验证
        self._validate_parameters(symbols=symbols)
        
        params = {'symbols': ','.join(symbols)}
        return self.call_api('latest_market', params=params)
    
    def get_full_market(self, market: str = None, symbols: Union[str, List[str]] = None) -> Dict[str, Any]:
        """获取完整行情
        
        Args:
            market (str, optional): 市场代码
            symbols (Union[str, List[str]], optional): 股票代码或代码列表
            
        Returns:
            Dict[str, Any]: 完整行情数据
        """
        params = {}
        if market:
            # 参数验证
            self._validate_parameters(market=market)
            params['market'] = market
        if symbols:
            if isinstance(symbols, str):
                symbols = [symbols]
            # 参数验证
            self._validate_parameters(symbols=symbols)
            params['symbols'] = ','.join(symbols)
        
        return self.call_api('full_market', params=params)
    
    def get_market_data(self, stock_list: List[str], period: str, start_time: str = None, 
                       end_time: str = None, count: int = None) -> Dict[str, Any]:
        """获取市场数据（对应xtdata.get_market_data）
        
        Args:
            stock_list (List[str]): 股票代码列表
            period (str): 数据周期
            start_time (str, optional): 开始时间
            end_time (str, optional): 结束时间
            count (int, optional): 数据数量
            
        Returns:
            Dict[str, Any]: 市场数据
        """
        # 参数验证
        self._validate_parameters(symbols=stock_list, frequency=period)
        if start_time:
            self._validate_parameters(start_date=start_time)
        if end_time:
            self._validate_parameters(end_date=end_time)
        if count is not None:
            self._validate_parameters(count=count)
        
        params = {
            'stock_list': ','.join(stock_list),
            'period': period
        }
        if start_time:
            params['start_time'] = start_time
        if end_time:
            params['end_time'] = end_time
        if count is not None:
            params['count'] = count
        
        return self.call_api('market_data', params=params)
    
    def subscribe_quote(self, stock_code: str, period: str, count: int = 0) -> Dict[str, Any]:
        """订阅行情数据（对应xtdata.subscribe_quote）
        
        Args:
            stock_code (str): 股票代码
            period (str): 数据周期
            count (int): 历史数据数量，默认0
            
        Returns:
            Dict[str, Any]: 订阅结果
        """
        # 参数验证
        self._validate_parameters(symbol=stock_code, frequency=period, count=count if count > 0 else 1)
        
        params = {
            'stock_code': stock_code,
            'period': period,
            'count': count
        }
        
        return self.call_api('subscribe_quote', method='POST', params=params)
    
    def unsubscribe_quote(self, subscribe_id: int) -> Dict[str, Any]:
        """取消订阅行情数据（对应xtdata.unsubscribe_quote）
        
        Args:
            subscribe_id (int): 订阅ID
            
        Returns:
            Dict[str, Any]: 取消订阅结果
        """
        params = {'subscribe_id': subscribe_id}
        return self.call_api('unsubscribe_quote', method='POST', params=params)
    
    def subscribe_whole_quote(self, code_list: List[str]) -> Dict[str, Any]:
        """订阅全推行情（对应xtdata.subscribe_whole_quote）
        
        Args:
            code_list (List[str]): 代码列表（市场代码或股票代码）
            
        Returns:
            Dict[str, Any]: 订阅结果
        """
        params = {'code_list': ','.join(code_list)}
        return self.call_api('subscribe_whole_quote', method='POST', params=params)
    
    def get_full_tick(self, code_list: List[str]) -> Dict[str, Any]:
        """获取全推数据快照（对应xtdata.get_full_tick）
        
        Args:
            code_list (List[str]): 代码列表
            
        Returns:
            Dict[str, Any]: 全推数据
        """
        params = {'code_list': ','.join(code_list)}
        return self.call_api('full_tick', params=params)
    
    def download_history_data(self, stock_code: str, period: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """下载历史数据（对应xtdata.download_history_data）
        
        Args:
            stock_code (str): 股票代码
            period (str): 数据周期
            start_date (str): 开始日期
            end_date (str): 结束日期
            
        Returns:
            Dict[str, Any]: 下载结果
        """
        # 参数验证
        self._validate_parameters(
            symbol=stock_code,
            frequency=period,
            start_date=start_date,
            end_date=end_date
        )
        
        params = {
            'stock_code': stock_code,
            'period': period,
            'start_date': start_date,
            'end_date': end_date
        }
        
        return self.call_api('download_history_data', method='POST', params=params)
    
    def test_connection(self) -> Dict[str, Any]:
        """测试API连接
        
        Returns:
            Dict[str, Any]: 连接测试结果
        """
        try:
            return self.call_api('health', method='GET')
        except APIError:
            # 如果没有health端点，尝试获取交易日历作为连接测试
            try:
                return self.get_trading_dates('SH', count=1)
            except APIError as e:
                return {
                    'code': -1,
                    'message': f'连接测试失败: {str(e)}',
                    'data': None,
                    'duration': 0,
                    'timestamp': int(time.time())
                }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息
        
        Returns:
            Dict[str, Any]: 性能统计数据
        """
        if not self.performance_monitor:
            return {'message': '性能监控未启用'}
        
        return self.performance_monitor.export_stats()
    
    def print_performance_summary(self) -> None:
        """打印性能统计摘要"""
        if self.performance_monitor:
            self.performance_monitor.print_summary()
        else:
            print("性能监控未启用")
    
    def reset_performance_stats(self) -> None:
        """重置性能统计数据"""
        if self.performance_monitor:
            self.performance_monitor.reset()
    
    def close(self) -> None:
        """关闭客户端，清理资源"""
        if self.session:
            self.session.close()
        
        if self.performance_monitor:
            self.performance_monitor.reset()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"QMTAPIClient(base_url='{self.base_url}', timeout={self.timeout})"


def create_api_client(**kwargs) -> QMTAPIClient:
    """创建API客户端实例的便捷函数
    
    Args:
        **kwargs: 传递给QMTAPIClient的参数
        
    Returns:
        QMTAPIClient: API客户端实例
    """
    return QMTAPIClient(**kwargs)


def safe_api_call(client: QMTAPIClient, api_func, *args, **kwargs) -> Dict[str, Any]:
    """安全的API调用包装函数
    
    Args:
        client (QMTAPIClient): API客户端实例
        api_func: API调用函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        Dict[str, Any]: API调用结果，失败时返回错误信息
    """
    try:
        return api_func(*args, **kwargs)
    except APIError as e:
        return {
            'code': -1,
            'message': f'API调用失败: {str(e)}',
            'data': None,
            'duration': 0,
            'timestamp': int(time.time()),
            'error_type': 'APIError',
            'error_details': {
                'status_code': getattr(e, 'status_code', None),
                'response_data': getattr(e, 'response_data', {})
            }
        }
    except Exception as e:
        return {
            'code': -1,
            'message': f'未知错误: {str(e)}',
            'data': None,
            'duration': 0,
            'timestamp': int(time.time()),
            'error_type': type(e).__name__,
            'error_details': {}
        }


if __name__ == "__main__":
    # API客户端测试和演示
    from .utils import print_section_header, print_api_result
    
    print_section_header("QMT API客户端测试")
    
    # 创建客户端实例
    print("\n创建API客户端...")
    client = create_api_client()
    print(f"客户端配置: {client}")
    
    # 测试连接
    print("\n测试API连接...")
    connection_result = client.test_connection()
    print_api_result(connection_result, "连接测试结果")
    
    # 测试交易日历API
    print("\n测试交易日历API...")
    trading_dates_result = safe_api_call(
        client, client.get_trading_dates, 'SH', count=5
    )
    print_api_result(trading_dates_result, "交易日历")
    
    # 测试历史K线API
    print("\n测试历史K线API...")
    hist_kline_result = safe_api_call(
        client, client.get_hist_kline, '600519.SH', '2024-01-01', '2024-01-05'
    )
    print_api_result(hist_kline_result, "历史K线")
    
    # 显示性能统计
    print("\n性能统计:")
    client.print_performance_summary()
    
    # 清理资源
    client.close()
    print("\nAPI客户端测试完成")