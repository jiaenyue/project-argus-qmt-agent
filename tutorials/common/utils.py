"""
通用工具函数模块 - Project Argus QMT 数据代理服务教程

提供格式化输出、日期验证、性能监控等工具函数，
实现统一的日志和显示格式。
"""

import time
import datetime
import re
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict
import json


def format_response_time(seconds: float) -> str:
    """格式化响应时间显示
    
    Args:
        seconds (float): 响应时间（秒）
        
    Returns:
        str: 格式化的响应时间字符串
    """
    if seconds < 0.001:
        return f"{seconds * 1000000:.0f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    else:
        return f"{seconds:.2f}s"


def print_section_header(title: str, width: int = 60, char: str = "=") -> None:
    """打印章节标题
    
    Args:
        title (str): 标题文本
        width (int): 总宽度，默认60
        char (str): 分隔符字符，默认"="
    """
    if len(title) >= width - 4:
        print(f"{char * 2} {title} {char * 2}")
    else:
        padding = (width - len(title) - 2) // 2
        remaining = width - len(title) - 2 - padding
        print(f"{char * padding} {title} {char * remaining}")


def print_subsection_header(title: str, width: int = 50, char: str = "-") -> None:
    """打印子章节标题
    
    Args:
        title (str): 标题文本
        width (int): 总宽度，默认50
        char (str): 分隔符字符，默认"-"
    """
    print(f"\n{char * 3} {title} {char * (width - len(title) - 5)}")


def print_api_result(result: Any, title: str = None, max_items: int = 10) -> None:
    """统一的API结果显示格式
    
    Args:
        result (Any): API返回结果
        title (str, optional): 结果标题
        max_items (int): 最大显示项目数，默认10
    """
    if title:
        print_subsection_header(title)
    
    if result is None:
        print("  结果: None")
        return
    
    if isinstance(result, dict):
        _print_dict_result(result, max_items)
    elif isinstance(result, list):
        _print_list_result(result, max_items)
    else:
        print(f"  结果: {result}")


def _print_dict_result(result: Dict, max_items: int) -> None:
    """打印字典类型结果"""
    if 'code' in result and 'data' in result:
        # 标准API响应格式
        print(f"  状态码: {result.get('code', 'N/A')}")
        print(f"  消息: {result.get('message', 'N/A')}")
        if 'duration' in result:
            print(f"  耗时: {format_response_time(result['duration'])}")
        
        data = result.get('data')
        if data:
            print("  数据:")
            if isinstance(data, list) and len(data) > max_items:
                print(f"    显示前{max_items}项（共{len(data)}项）:")
                for i, item in enumerate(data[:max_items]):
                    print(f"    [{i+1}] {item}")
                print(f"    ... 还有{len(data) - max_items}项")
            else:
                _print_nested_data(data, indent="    ")
    else:
        # 普通字典
        _print_nested_data(result, max_items=max_items)


def _print_list_result(result: List, max_items: int) -> None:
    """打印列表类型结果"""
    total_items = len(result)
    print(f"  总计: {total_items} 项")
    
    if total_items == 0:
        print("  无数据")
        return
    
    display_count = min(max_items, total_items)
    print(f"  显示前{display_count}项:")
    
    for i, item in enumerate(result[:display_count]):
        print(f"  [{i+1}] {item}")
    
    if total_items > max_items:
        print(f"  ... 还有{total_items - max_items}项")


def _print_nested_data(data: Any, indent: str = "  ", max_items: int = 10) -> None:
    """打印嵌套数据结构"""
    if isinstance(data, dict):
        for key, value in list(data.items())[:max_items]:
            if isinstance(value, (dict, list)) and len(str(value)) > 100:
                print(f"{indent}{key}: {type(value).__name__}({len(value)} items)")
            else:
                print(f"{indent}{key}: {value}")
        if len(data) > max_items:
            print(f"{indent}... 还有{len(data) - max_items}个字段")
    elif isinstance(data, list):
        for i, item in enumerate(data[:max_items]):
            print(f"{indent}[{i}] {item}")
        if len(data) > max_items:
            print(f"{indent}... 还有{len(data) - max_items}项")
    else:
        print(f"{indent}{data}")


def validate_date_format(date_str: str, format_pattern: str = r'^\d{4}-\d{2}-\d{2}$') -> bool:
    """验证日期格式
    
    Args:
        date_str (str): 日期字符串
        format_pattern (str): 正则表达式模式，默认YYYY-MM-DD格式
        
    Returns:
        bool: 格式是否正确
    """
    if not isinstance(date_str, str):
        return False
    
    # 正则表达式验证
    if not re.match(format_pattern, date_str):
        return False
    
    # 尝试解析日期
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_symbol_format(symbol: str) -> bool:
    """验证股票代码格式
    
    Args:
        symbol (str): 股票代码
        
    Returns:
        bool: 格式是否正确
    """
    if not isinstance(symbol, str):
        return False
    
    # 支持的格式: 600519.SH, 000001.SZ 等
    pattern = r'^\d{6}\.(SH|SZ)$'
    return bool(re.match(pattern, symbol))


def get_date_range(days: int = 30) -> tuple:
    """获取日期范围
    
    Args:
        days (int): 天数，默认30天
        
    Returns:
        tuple: (开始日期, 结束日期) 格式为 YYYY-MM-DD
    """
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


def format_number(number: Union[int, float], decimal_places: int = 2) -> str:
    """格式化数字显示
    
    Args:
        number (Union[int, float]): 数字
        decimal_places (int): 小数位数，默认2位
        
    Returns:
        str: 格式化的数字字符串
    """
    if isinstance(number, int):
        return f"{number:,}"
    elif isinstance(number, float):
        return f"{number:,.{decimal_places}f}"
    else:
        return str(number)


class PerformanceMonitor:
    """性能监控工具类
    
    用于记录和统计API调用的性能数据。
    """
    
    def __init__(self):
        """初始化性能监控器"""
        self.stats = defaultdict(list)
        self.start_time = time.time()
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
    
    def record_api_call(self, endpoint: str, duration: float, success: bool, 
                       error_msg: str = None) -> None:
        """记录API调用性能
        
        Args:
            endpoint (str): API端点名称
            duration (float): 调用耗时（秒）
            success (bool): 是否成功
            error_msg (str, optional): 错误信息
        """
        self.stats[endpoint].append({
            'duration': duration,
            'success': success,
            'timestamp': time.time(),
            'error_msg': error_msg
        })
        
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
    
    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """获取特定端点的统计信息
        
        Args:
            endpoint (str): API端点名称
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        if endpoint not in self.stats:
            return {}
        
        calls = self.stats[endpoint]
        durations = [call['duration'] for call in calls]
        successful = [call for call in calls if call['success']]
        failed = [call for call in calls if not call['success']]
        
        return {
            'total_calls': len(calls),
            'successful_calls': len(successful),
            'failed_calls': len(failed),
            'success_rate': len(successful) / len(calls) * 100 if calls else 0,
            'avg_duration': sum(durations) / len(durations) if durations else 0,
            'min_duration': min(durations) if durations else 0,
            'max_duration': max(durations) if durations else 0,
            'total_duration': sum(durations)
        }
    
    def print_summary(self) -> None:
        """打印性能统计摘要"""
        print_section_header("性能统计摘要")
        
        total_duration = time.time() - self.start_time
        print(f"总运行时间: {format_response_time(total_duration)}")
        print(f"总调用次数: {self.total_calls}")
        print(f"成功调用: {self.successful_calls}")
        print(f"失败调用: {self.failed_calls}")
        
        if self.total_calls > 0:
            success_rate = self.successful_calls / self.total_calls * 100
            print(f"成功率: {success_rate:.1f}%")
        
        if self.stats:
            print("\n各端点详细统计:")
            for endpoint, calls in self.stats.items():
                stats = self.get_endpoint_stats(endpoint)
                print(f"\n  {endpoint}:")
                print(f"    调用次数: {stats['total_calls']}")
                print(f"    成功率: {stats['success_rate']:.1f}%")
                print(f"    平均耗时: {format_response_time(stats['avg_duration'])}")
                print(f"    最短耗时: {format_response_time(stats['min_duration'])}")
                print(f"    最长耗时: {format_response_time(stats['max_duration'])}")
    
    def export_stats(self, filename: str = None) -> Dict[str, Any]:
        """导出统计数据
        
        Args:
            filename (str, optional): 导出文件名
            
        Returns:
            Dict[str, Any]: 完整的统计数据
        """
        export_data = {
            'summary': {
                'total_duration': time.time() - self.start_time,
                'total_calls': self.total_calls,
                'successful_calls': self.successful_calls,
                'failed_calls': self.failed_calls,
                'success_rate': self.successful_calls / self.total_calls * 100 if self.total_calls > 0 else 0
            },
            'endpoints': {}
        }
        
        for endpoint in self.stats:
            export_data['endpoints'][endpoint] = self.get_endpoint_stats(endpoint)
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                print(f"统计数据已导出到: {filename}")
            except Exception as e:
                print(f"导出统计数据失败: {e}")
        
        return export_data
    
    def reset(self) -> None:
        """重置统计数据"""
        self.stats.clear()
        self.start_time = time.time()
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0


def create_demo_context() -> Dict[str, Any]:
    """创建演示上下文信息
    
    Returns:
        Dict[str, Any]: 演示上下文
    """
    start_date, end_date = get_date_range(30)
    
    return {
        'timestamp': datetime.datetime.now().isoformat(),
        'date_range': {
            'start_date': start_date,
            'end_date': end_date,
            'days': 30
        },
        'performance_monitor': PerformanceMonitor()
    }


if __name__ == "__main__":
    # 工具函数测试和演示
    print_section_header("Project Argus QMT 通用工具函数演示")
    
    # 测试日期验证
    print_subsection_header("日期格式验证测试")
    test_dates = ["2024-01-01", "2024-13-01", "invalid", "2024-02-30"]
    for date_str in test_dates:
        result = validate_date_format(date_str)
        print(f"  {date_str}: {'有效' if result else '无效'}")
    
    # 测试股票代码验证
    print_subsection_header("股票代码格式验证测试")
    test_symbols = ["600519.SH", "000001.SZ", "invalid", "123456.XX"]
    for symbol in test_symbols:
        result = validate_symbol_format(symbol)
        print(f"  {symbol}: {'有效' if result else '无效'}")
    
    # 测试性能监控
    print_subsection_header("性能监控演示")
    monitor = PerformanceMonitor()
    
    # 模拟一些API调用
    import random
    for i in range(5):
        duration = random.uniform(0.1, 2.0)
        success = random.choice([True, True, True, False])  # 75%成功率
        monitor.record_api_call("test_api", duration, success)
    
    monitor.print_summary()
    
    # 测试结果显示
    print_subsection_header("API结果显示测试")
    test_result = {
        'code': 0,
        'message': 'success',
        'data': [f'item_{i}' for i in range(15)],
        'duration': 0.123
    }
    print_api_result(test_result, "测试API响应")