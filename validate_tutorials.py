#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
教程验证脚本

该脚本用于验证教程文件的API可用性和模拟数据生成。
支持以下功能：
- 验证API服务可用性
- 验证模拟数据生成
- 验证教程文件中的API调用
- 生成验证报告

使用方法：
    python validate_tutorials.py [--api-url URL] [--output FILE]

参数：
    --api-url: API服务URL（默认：http://localhost:8000）
    --output: 输出报告文件路径（默认：tutorials_validation_report.json）
"""

import os
import sys
import json
import time
import argparse
import importlib.util
import ast
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import requests
import concurrent.futures

# 定义颜色代码，用于控制台输出
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
ENDC = '\033[0m'
BOLD = '\033[1m'

# 定义教程文件列表
TUTORIAL_FILES = [
    'tutorials/01_trading_dates.py',
    'tutorials/02_hist_kline.py',
    'tutorials/03_instrument_detail.py',
    'tutorials/04_stock_list.py',
    'tutorials/06_latest_market.py',
    'tutorials/07_full_market.py',
]

# 定义API端点列表
API_ENDPOINTS = [
    '/trading_dates',
    '/hist_kline',
    '/instrument_detail',
    '/stock_list',
    '/latest_market',
    '/full_market',
]


class TutorialValidator:
    """教程验证器类，用于验证教程文件"""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """初始化验证器
        
        Args:
            api_url: API服务URL
        """
        self.api_url = api_url
        self.results = {
            'api_validation': {},
            'mock_validation': {},
            'tutorial_validation': {},
            'summary': {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'api_url': api_url,
                'api_available': False,
                'api_endpoints_total': len(API_ENDPOINTS),
                'api_endpoints_valid': 0,
                'mock_generators_total': len(API_ENDPOINTS),
                'mock_generators_valid': 0,
                'tutorials_total': len(TUTORIAL_FILES),
                'tutorials_valid': 0
            }
        }
    
    def validate_all(self) -> Dict:
        """执行所有验证
        
        Returns:
            Dict: 验证结果
        """
        print(f"{BOLD}开始验证教程文件...{ENDC}")
        
        # 1. 验证API服务可用性
        self.validate_api_availability()
        
        # 2. 验证模拟数据生成
        self.validate_mock_data()
        
        # 3. 验证教程文件中的API调用
        self.validate_tutorials()
        
        # 生成验证报告
        self._generate_report()
        
        return self.results
    
    def validate_api_availability(self) -> Dict:
        """验证API服务可用性
        
        Returns:
            Dict: API验证结果
        """
        print(f"\n{BOLD}{BLUE}1. 验证API服务可用性...{ENDC}")
        
        # 检查API服务是否运行
        api_available = self._check_api_service()
        self.results['summary']['api_available'] = api_available
        
        if not api_available:
            print(f"{YELLOW}API服务不可用，将仅验证模拟数据功能{ENDC}")
        
        # 验证各个API端点
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._validate_api_endpoint, endpoint): endpoint for endpoint in API_ENDPOINTS}
            
            for future in concurrent.futures.as_completed(futures):
                endpoint = futures[future]
                try:
                    result = future.result()
                    self.results['api_validation'][endpoint] = result
                    
                    if result['valid']:
                        self.results['summary']['api_endpoints_valid'] += 1
                        print(f"  {GREEN}✓{ENDC} {endpoint} - 有效")
                    else:
                        print(f"  {RED}✗{ENDC} {endpoint} - 无效: {result['error']}")
                except Exception as e:
                    print(f"  {RED}✗{ENDC} {endpoint} - 异常: {str(e)}")
                    self.results['api_validation'][endpoint] = {
                        'valid': False,
                        'error': str(e)
                    }
        
        print(f"\nAPI验证完成: {self.results['summary']['api_endpoints_valid']}/{self.results['summary']['api_endpoints_total']} 个端点有效")
        return self.results['api_validation']
    
    def _check_api_service(self) -> bool:
        """检查API服务是否可用
        
        Returns:
            bool: 服务是否可用
        """
        try:
            response = requests.get(f"{self.api_url}/api/v1/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _validate_api_endpoint(self, endpoint: str) -> Dict:
        """验证单个API端点
        
        Args:
            endpoint: API端点
            
        Returns:
            Dict: 验证结果
        """
        result = {
            'valid': False,
            'error': None,
            'response_time': None,
            'status_code': None,
            'response_format_valid': False
        }
        
        try:
            # 准备测试参数
            params = self._get_test_params_for_endpoint(endpoint)
            
            # 发送请求
            start_time = time.time()
            # 禁用代理，直接连接本地服务
            response = requests.get(
                f"{self.api_url}{endpoint}", 
                params=params, 
                timeout=10,
                proxies={'http': None, 'https': None}  # 跳过代理服务器
            )
            response_time = time.time() - start_time
            
            result['response_time'] = response_time
            result['status_code'] = response.status_code
            
            # 检查响应
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0 and 'data' in data:
                    result['valid'] = True
                    result['response_format_valid'] = True
                else:
                    result['error'] = f"API错误: {data.get('message', '未知错误')}"
            else:
                result['error'] = f"HTTP错误: {response.status_code}"
        
        except Exception as e:
            result['error'] = f"请求异常: {str(e)}"
        
        return result
    
    def _get_test_params_for_endpoint(self, endpoint: str) -> Dict:
        """获取测试端点的参数
        
        Args:
            endpoint: API端点
            
        Returns:
            Dict: 测试参数
        """
        # 根据不同端点返回适当的测试参数
        if endpoint == '/trading_dates':
            return {'market': 'SH'}
        elif endpoint == '/hist_kline':
            return {'symbol': '600519.SH', 'start_date': '20250101', 'end_date': '20250110'}
        elif endpoint == '/instrument_detail':
            return {'symbol': '600519.SH'}
        elif endpoint == '/stock_list':
            return {'sector': '银行'}
        elif endpoint == '/latest_market':
            return {'symbols': '600519.SH,000001.SZ'}
        elif endpoint == '/full_market':
            return {'market': 'SH'}
        else:
            return {}
    
    def validate_mock_data(self) -> Dict:
        """验证模拟数据生成
        
        Returns:
            Dict: 模拟数据验证结果
        """
        print(f"\n{BOLD}{BLUE}2. 验证模拟数据生成...{ENDC}")
        
        try:
            # 导入模拟数据生成器
            sys.path.append('.')  # 确保能够导入项目模块
            sys.path.append('tutorials')  # 添加tutorials目录到路径
            from tutorials.common.mock_data import MockDataGenerator
            
            # 创建模拟数据生成器实例
            mock_generator = MockDataGenerator()
            
            # 验证各种模拟数据生成方法
            test_cases = [
                ('generate_trading_dates', ['SH'], '/api/v1/get_trading_dates'),
                ('generate_hist_kline', ['600519.SH', '20250101', '20250110'], '/api/v1/get_hist_kline'),
                ('generate_instrument_detail', ['600519.SH'], '/api/v1/instrument_detail'),
                ('generate_stock_list', ['银行'], '/api/v1/stock_list'),
                ('generate_latest_market', [['600519.SH', '000001.SZ']], '/api/v1/latest_market'),
                ('generate_full_market', ['SH'], '/api/v1/full_market')
            ]
            
            for method_name, args, endpoint in test_cases:
                print(f"  验证 {method_name}...", end='')
                
                try:
                    # 调用模拟数据生成方法
                    method = getattr(mock_generator, method_name)
                    mock_data = method(*args)
                    
                    # 验证结果
                    result = {
                        'valid': False,
                        'error': None,
                        'data_structure_valid': False,
                        'data_content_valid': False
                    }
                    
                    if mock_data and isinstance(mock_data, dict):
                        result['data_structure_valid'] = 'code' in mock_data and 'data' in mock_data
                        
                        if result['data_structure_valid']:
                            # 验证数据内容
                            data_content = mock_data['data']
                            result['data_content_valid'] = self._validate_mock_data_content(endpoint, data_content)
                            result['valid'] = result['data_content_valid']
                    
                    if not result['valid']:
                        result['error'] = "模拟数据格式或内容无效"
                    
                    self.results['mock_validation'][endpoint] = result
                    
                    if result['valid']:
                        self.results['summary']['mock_generators_valid'] += 1
                        print(f"{GREEN} 有效{ENDC}")
                    else:
                        print(f"{RED} 无效{ENDC}")
                        if result['error']:
                            print(f"    错误: {result['error']}")
                
                except Exception as e:
                    print(f"{RED} 异常{ENDC}")
                    print(f"    错误: {str(e)}")
                    
                    self.results['mock_validation'][endpoint] = {
                        'valid': False,
                        'error': str(e)
                    }
            
        except Exception as e:
            print(f"{RED}模拟数据验证失败: {str(e)}{ENDC}")
        
        print(f"\n模拟数据验证完成: {self.results['summary']['mock_generators_valid']}/{self.results['summary']['mock_generators_total']} 个生成器有效")
        return self.results['mock_validation']
    
    def _validate_mock_data_content(self, endpoint: str, data_content: Any) -> bool:
        """验证模拟数据内容
        
        Args:
            endpoint: API端点
            data_content: 数据内容
            
        Returns:
            bool: 数据内容是否有效
        """
        if endpoint == '/api/v1/get_trading_dates':
            # 应该是日期字符串列表
            return isinstance(data_content, list) and all(isinstance(d, str) for d in data_content)
        
        elif endpoint == '/api/v1/get_hist_kline':
            # 应该是K线数据列表
            return (isinstance(data_content, list) and 
                    all(isinstance(k, dict) and 'date' in k and 'close' in k for k in data_content))
        
        elif endpoint == '/api/v1/instrument_detail':
            # 应该是合约详情字典
            return isinstance(data_content, dict) and 'symbol' in data_content
        
        elif endpoint == '/api/v1/stock_list':
            # 应该是股票列表
            return isinstance(data_content, list) and all(isinstance(s, str) for s in data_content)
        
        elif endpoint == '/api/v1/latest_market':
            # 应该是最新行情字典
            return isinstance(data_content, dict) and all(isinstance(v, dict) for v in data_content.values())
        
        elif endpoint == '/api/v1/full_market':
            # 应该是完整行情列表或字典
            return (isinstance(data_content, list) or isinstance(data_content, dict))
        
        return False
    
    def validate_tutorials(self) -> Dict:
        """验证教程文件中的API调用
        
        Returns:
            Dict: 教程验证结果
        """
        print(f"\n{BOLD}{BLUE}3. 验证教程文件中的API调用...{ENDC}")
        
        for file_path in TUTORIAL_FILES:
            file_name = os.path.basename(file_path)
            print(f"  验证 {file_name}...", end='')
            
            try:
                # 解析教程文件，提取API调用
                api_calls = self._extract_api_calls(file_path)
                
                # 验证API调用
                valid_calls = 0
                invalid_calls = 0
                errors = []
                
                for call in api_calls:
                    if self._validate_api_call(call):
                        valid_calls += 1
                    else:
                        invalid_calls += 1
                        errors.append(f"无效的API调用: {call}")
                
                # 记录结果
                result = {
                    'valid': invalid_calls == 0 and valid_calls > 0,
                    'api_calls_total': len(api_calls),
                    'api_calls_valid': valid_calls,
                    'api_calls_invalid': invalid_calls,
                    'errors': errors
                }
                
                self.results['tutorial_validation'][file_path] = result
                
                if result['valid']:
                    self.results['summary']['tutorials_valid'] += 1
                    print(f"{GREEN} 有效 ({valid_calls}/{len(api_calls)} 个API调用){ENDC}")
                else:
                    print(f"{RED} 无效 ({valid_calls}/{len(api_calls)} 个API调用){ENDC}")
                    for error in errors[:3]:  # 只显示前3个错误
                        print(f"    {error}")
                    if len(errors) > 3:
                        print(f"    ... 还有 {len(errors) - 3} 个错误")
            
            except Exception as e:
                print(f"{RED} 异常{ENDC}")
                print(f"    错误: {str(e)}")
                
                self.results['tutorial_validation'][file_path] = {
                    'valid': False,
                    'error': str(e)
                }
        
        print(f"\n教程验证完成: {self.results['summary']['tutorials_valid']}/{self.results['summary']['tutorials_total']} 个教程有效")
        return self.results['tutorial_validation']
    
    def _extract_api_calls(self, file_path: str) -> List[Dict]:
        """从教程文件中提取API调用
        
        Args:
            file_path: 教程文件路径
            
        Returns:
            List[Dict]: API调用列表
        """
        api_calls = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # 解析语法树
            tree = ast.parse(file_content)
            
            # 遍历语法树，查找API调用
            for node in ast.walk(tree):
                # 查找函数调用
                if isinstance(node, ast.Call):
                    # 检查是否是API客户端调用
                    if self._is_api_client_call(node):
                        api_call = self._extract_api_call_info(node)
                        if api_call:
                            api_calls.append(api_call)
        
        except Exception as e:
            print(f"提取API调用时出错: {str(e)}")
        
        return api_calls
    
    def _is_api_client_call(self, node: ast.Call) -> bool:
        """检查节点是否是API客户端调用
        
        Args:
            node: AST调用节点
            
        Returns:
            bool: 是否是API客户端调用
        """
        # 检查直接调用，如 api_client.get_trading_dates(...)
        if isinstance(node.func, ast.Attribute):
            if hasattr(node.func, 'attr') and node.func.attr in [
                'get_trading_dates', 'get_hist_kline', 'instrument_detail',
                'stock_list', 'latest_market', 'full_market',
                'call_api'
            ]:
                return True
        
        # 检查safe_api_call调用，如 safe_api_call(api_client, api_client.get_trading_dates, ...)
        if isinstance(node.func, ast.Name) and node.func.id == 'safe_api_call':
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Attribute):
                return True
        
        return False
    
    def _extract_api_call_info(self, node: ast.Call) -> Optional[Dict]:
        """提取API调用信息
        
        Args:
            node: AST调用节点
            
        Returns:
            Optional[Dict]: API调用信息
        """
        try:
            if isinstance(node.func, ast.Attribute):
                # 直接调用
                method_name = node.func.attr
                endpoint = self._method_to_endpoint(method_name)
                
                return {
                    'method': method_name,
                    'endpoint': endpoint,
                    'args_count': len(node.args),
                    'kwargs_count': len(node.keywords)
                }
            
            elif isinstance(node.func, ast.Name) and node.func.id == 'safe_api_call':
                # safe_api_call调用
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Attribute):
                    method_name = node.args[1].attr
                    endpoint = self._method_to_endpoint(method_name)
                    
                    return {
                        'method': method_name,
                        'endpoint': endpoint,
                        'args_count': len(node.args) - 2,  # 减去api_client和方法参数
                        'kwargs_count': len(node.keywords)
                    }
        
        except Exception:
            pass
        
        return None
    
    def _method_to_endpoint(self, method_name: str) -> str:
        """将方法名转换为API端点
        
        Args:
            method_name: 方法名
            
        Returns:
            str: API端点
        """
        method_to_endpoint = {
            'get_trading_dates': '/api/v1/get_trading_dates',
            'get_hist_kline': '/api/v1/get_hist_kline',
            'get_instrument_detail': '/api/v1/instrument_detail',
            'instrument_detail': '/api/v1/instrument_detail',
            'get_stock_list': '/api/v1/stock_list',
            'stock_list': '/api/v1/stock_list',
            'get_stock_list_in_sector': '/api/v1/stock_list',
            'download_sector_data': '/api/v1/stock_list',
            'get_sector_list': '/api/v1/stock_list',
            'get_latest_market': '/api/v1/latest_market',
            'latest_market': '/api/v1/latest_market',
            'subscribe_quote': '/api/v1/latest_market',
            'unsubscribe_quote': '/api/v1/latest_market',
            'get_full_market': '/api/v1/full_market',
            'full_market': '/api/v1/full_market',
            'subscribe_whole_quote': '/api/v1/full_market',
            'get_full_tick': '/api/v1/full_market'
        }
        
        return method_to_endpoint.get(method_name, 'unknown')
    
    def _validate_api_call(self, api_call: Dict) -> bool:
        """验证API调用
        
        Args:
            api_call: API调用信息
            
        Returns:
            bool: API调用是否有效
        """
        # 检查端点是否有效
        if api_call['endpoint'] == 'unknown':
            return False
        
        # 检查参数数量是否合理
        if api_call['endpoint'] == '/api/v1/get_trading_dates':
            # 至少需要一个参数（market）
            return api_call['args_count'] + api_call['kwargs_count'] >= 1
        
        elif api_call['endpoint'] == '/api/v1/get_hist_kline':
            # 至少需要三个参数（symbol, start_date, end_date）
            return api_call['args_count'] + api_call['kwargs_count'] >= 3
        
        elif api_call['endpoint'] == '/api/v1/instrument_detail':
            # 至少需要一个参数（symbol）
            return api_call['args_count'] + api_call['kwargs_count'] >= 1
        
        elif api_call['endpoint'] == '/api/v1/stock_list':
            # 至少需要一个参数（sector）
            return api_call['args_count'] + api_call['kwargs_count'] >= 1
        
        elif api_call['endpoint'] == '/api/v1/latest_market':
            # 至少需要一个参数（symbols）
            return api_call['args_count'] + api_call['kwargs_count'] >= 1
        
        elif api_call['endpoint'] == '/api/v1/full_market':
            # 至少需要一个参数（market或symbols）
            return api_call['args_count'] + api_call['kwargs_count'] >= 1
        
        return True
    
    def _generate_report(self):
        """生成验证报告"""
        # 保存为JSON文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = f"tutorials_validation_report_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        # 创建最新结果的链接
        latest_file = "tutorials_validation_report.json"
        if os.path.exists(latest_file):
            os.remove(latest_file)
        
        # 在Windows上使用复制而不是符号链接
        import shutil
        shutil.copy2(result_file, latest_file)
        
        # 生成文本报告
        self._generate_text_report("tutorials_validation_report.txt")
        
        print(f"\n{BOLD}验证报告已生成:{ENDC}")
        print(f"  JSON报告: {result_file}")
        print(f"  文本报告: tutorials_validation_report.txt")
    
    def _generate_text_report(self, report_file: str):
        """生成文本报告
        
        Args:
            report_file: 报告文件路径
        """
        summary = self.results['summary']
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("教程验证报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"验证时间: {summary['timestamp']}\n")
            f.write(f"API服务: {summary['api_url']}\n")
            f.write(f"API服务状态: {'可用' if summary['api_available'] else '不可用'}\n\n")
            
            f.write("验证摘要:\n")
            f.write(f"  API端点: {summary['api_endpoints_valid']}/{summary['api_endpoints_total']} 个有效\n")
            f.write(f"  模拟数据生成器: {summary['mock_generators_valid']}/{summary['mock_generators_total']} 个有效\n")
            f.write(f"  教程文件: {summary['tutorials_valid']}/{summary['tutorials_total']} 个有效\n\n")
            
            f.write("API端点验证结果:\n")
            for endpoint, result in self.results['api_validation'].items():
                status = "有效" if result.get('valid', False) else "无效"
                error = f" - {result.get('error', '')}" if not result.get('valid', False) else ""
                f.write(f"  {endpoint}: {status}{error}\n")
            
            f.write("\n模拟数据验证结果:\n")
            for endpoint, result in self.results['mock_validation'].items():
                status = "有效" if result.get('valid', False) else "无效"
                error = f" - {result.get('error', '')}" if not result.get('valid', False) else ""
                f.write(f"  {endpoint}: {status}{error}\n")
            
            f.write("\n教程文件验证结果:\n")
            for file_path, result in self.results['tutorial_validation'].items():
                file_name = os.path.basename(file_path)
                if 'api_calls_total' in result:
                    status = "有效" if result.get('valid', False) else "无效"
                    api_calls = f"{result.get('api_calls_valid', 0)}/{result.get('api_calls_total', 0)} 个API调用有效"
                    f.write(f"  {file_name}: {status} ({api_calls})\n")
                    
                    if not result.get('valid', False) and 'errors' in result:
                        for error in result['errors'][:3]:  # 只显示前3个错误
                            f.write(f"    - {error}\n")
                        if len(result['errors']) > 3:
                            f.write(f"    - ... 还有 {len(result['errors']) - 3} 个错误\n")
                else:
                    status = "验证失败"
                    error = f" - {result.get('error', '')}" if 'error' in result else ""
                    f.write(f"  {file_name}: {status}{error}\n")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程验证脚本')
    parser.add_argument('--api-url', default='http://localhost:8000', help='API服务URL')
    parser.add_argument('--output', default='tutorials_validation_report.json', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建验证器实例
    validator = TutorialValidator(api_url=args.api_url)
    
    # 执行验证
    validator.validate_all()


if __name__ == "__main__":
    main()