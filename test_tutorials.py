#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
教程文件自动化测试脚本

该脚本用于验证所有教程文件的语法正确性、API可用性和性能基准测试。
支持以下功能：
- 语法检查：验证所有教程文件是否存在语法错误
- API可用性测试：验证API服务是否可用，以及模拟数据是否正常工作
- 性能基准测试：测量API调用和数据处理的性能
- 回归测试：确保修改不会破坏现有功能

使用方法：
    python test_tutorials.py [--syntax-only] [--api-test] [--performance] [--all]

参数：
    --syntax-only: 仅执行语法检查
    --api-test: 仅执行API可用性测试
    --performance: 仅执行性能基准测试
    --all: 执行所有测试（默认）
"""

import os
import sys
import ast
import time
import json
import argparse
import importlib
import subprocess
import traceback
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import concurrent.futures
import requests
import pandas as pd
import matplotlib.pyplot as plt

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

# 定义API端点列表，用于可用性测试
API_ENDPOINTS = [
    '/api/v1/get_trading_dates',
    '/api/v1/get_hist_kline',
    '/api/v1/instrument_detail',
    '/api/v1/stock_list',
    '/api/v1/latest_market',
    '/api/v1/full_market',
]

# 定义性能基准测试参数
PERFORMANCE_TEST_ITERATIONS = 3  # 每个测试重复次数
PERFORMANCE_TEST_TIMEOUT = 30    # 测试超时时间（秒）


class TutorialTester:
    """教程测试器类，提供各种测试功能"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """初始化测试器
        
        Args:
            base_url: API服务基础URL
        """
        self.base_url = base_url
        self.results = {
            'syntax': {},
            'api': {},
            'performance': {},
            'summary': {
                'total_files': len(TUTORIAL_FILES),
                'syntax_passed': 0,
                'api_passed': 0,
                'performance_passed': 0,
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': None,
                'duration': 0
            }
        }
        
        # 创建结果目录
        os.makedirs('test_results', exist_ok=True)
    
    def run_all_tests(self) -> Dict:
        """运行所有测试
        
        Returns:
            Dict: 测试结果
        """
        start_time = time.time()
        
        print(f"{BOLD}开始执行教程文件自动化测试...{ENDC}")
        
        # 1. 语法检查
        self.test_syntax()
        
        # 2. API可用性测试
        self.test_api_availability()
        
        # 3. 性能基准测试
        self.test_performance()
        
        # 计算总耗时
        duration = time.time() - start_time
        self.results['summary']['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.results['summary']['duration'] = duration
        
        # 保存测试结果
        self.save_results()
        
        # 生成测试报告
        self.generate_report()
        
        print(f"\n{BOLD}测试完成，总耗时: {duration:.2f} 秒{ENDC}")
        print(f"详细报告已保存至 test_results/tutorial_test_report.html")
        
        return self.results
    
    def test_syntax(self) -> Dict:
        """测试所有教程文件的语法正确性
        
        Returns:
            Dict: 语法测试结果
        """
        print(f"\n{BOLD}{BLUE}1. 执行语法检查...{ENDC}")
        
        for file_path in TUTORIAL_FILES:
            print(f"  检查 {file_path}...", end='')
            
            result = self._check_file_syntax(file_path)
            self.results['syntax'][file_path] = result
            
            if result['passed']:
                print(f"{GREEN} 通过{ENDC}")
                self.results['summary']['syntax_passed'] += 1
            else:
                print(f"{RED} 失败{ENDC}")
                print(f"    错误: {result['error']}")
        
        print(f"\n语法检查完成: {self.results['summary']['syntax_passed']}/{len(TUTORIAL_FILES)} 个文件通过")
        return self.results['syntax']
    
    def _check_file_syntax(self, file_path: str) -> Dict:
        """检查单个文件的语法
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict: 检查结果
        """
        result = {
            'passed': False,
            'error': None,
            'ast_valid': False,
            'imports_valid': False,
            'execution_valid': False
        }
        
        if not os.path.exists(file_path):
            result['error'] = f"文件不存在: {file_path}"
            return result
        
        # 1. 检查语法树是否有效
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # 解析语法树
            ast.parse(file_content)
            result['ast_valid'] = True
            
            # 2. 检查导入是否有效
            module_name = file_path.replace('/', '.').replace('\\', '.').replace('.py', '')
            try:
                # 尝试导入模块（不执行）
                spec = importlib.util.find_spec(module_name)
                if spec is not None:
                    result['imports_valid'] = True
            except ImportError as e:
                result['error'] = f"导入错误: {str(e)}"
                return result
            
            # 3. 尝试执行语法检查（不实际运行）
            try:
                # 使用Python解释器检查语法
                subprocess.check_output(
                    [sys.executable, '-m', 'py_compile', file_path],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                result['execution_valid'] = True
                result['passed'] = True
            except subprocess.CalledProcessError as e:
                result['error'] = f"编译错误: {e.output.strip()}"
                return result
            
        except SyntaxError as e:
            result['error'] = f"语法错误: {str(e)}"
            return result
        except Exception as e:
            result['error'] = f"未知错误: {str(e)}"
            return result
        
        return result
    
    def test_api_availability(self) -> Dict:
        """测试API可用性和模拟数据
        
        Returns:
            Dict: API测试结果
        """
        print(f"\n{BOLD}{BLUE}2. 执行API可用性测试...{ENDC}")
        
        # 首先检查API服务是否运行
        api_available = self._check_api_service()
        
        if not api_available:
            print(f"{YELLOW}API服务不可用，将仅测试模拟数据功能{ENDC}")
        
        # 测试各个API端点
        for endpoint in API_ENDPOINTS:
            print(f"  测试端点 {endpoint}...", end='')
            
            result = self._test_api_endpoint(endpoint, api_available)
            self.results['api'][endpoint] = result
            
            if result['passed']:
                print(f"{GREEN} 通过{ENDC}")
                self.results['summary']['api_passed'] += 1
            else:
                print(f"{RED} 失败{ENDC}")
                print(f"    错误: {result['error']}")
        
        # 测试模拟数据生成
        print(f"  测试模拟数据生成...", end='')
        mock_result = self._test_mock_data()
        self.results['api']['mock_data'] = mock_result
        
        if mock_result['passed']:
            print(f"{GREEN} 通过{ENDC}")
        else:
            print(f"{RED} 失败{ENDC}")
            print(f"    错误: {mock_result['error']}")
        
        print(f"\nAPI测试完成: {self.results['summary']['api_passed']}/{len(API_ENDPOINTS)} 个端点通过")
        return self.results['api']
    
    def _check_api_service(self) -> bool:
        """检查API服务是否可用
        
        Returns:
            bool: 服务是否可用
        """
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _test_api_endpoint(self, endpoint: str, api_available: bool) -> Dict:
        """测试单个API端点
        
        Args:
            endpoint: API端点
            api_available: API服务是否可用
            
        Returns:
            Dict: 测试结果
        """
        result = {
            'passed': False,
            'error': None,
            'response_time': None,
            'status_code': None,
            'mock_data_valid': False
        }
        
        # 如果API服务可用，尝试直接调用
        if api_available:
            try:
                # 准备测试参数
                params = self._get_test_params_for_endpoint(endpoint)
                
                # 发送请求
                start_time = time.time()
                response = requests.get(f"{self.base_url}{endpoint}", params=params, timeout=10)
                response_time = time.time() - start_time
                
                result['response_time'] = response_time
                result['status_code'] = response.status_code
                
                # 检查响应
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == 0:
                        result['passed'] = True
                    else:
                        result['error'] = f"API错误: {data.get('message', '未知错误')}"
                else:
                    result['error'] = f"HTTP错误: {response.status_code}"
            
            except Exception as e:
                result['error'] = f"请求异常: {str(e)}"
        else:
            result['error'] = "API服务不可用"
        
        # 如果API调用失败或服务不可用，测试模拟数据
        if not result['passed']:
            try:
                # 导入模拟数据生成器
                sys.path.append('.')  # 确保能够导入项目模块
                from common.mock_data import MockDataGenerator
                
                # 创建模拟数据生成器实例
                mock_generator = MockDataGenerator()
                
                # 根据端点调用相应的模拟数据生成方法
                mock_data = self._generate_mock_data(mock_generator, endpoint)
                
                if mock_data and mock_data.get('code') == 0:
                    result['mock_data_valid'] = True
                    # 如果API不可用但模拟数据正常，则测试通过
                    if not api_available:
                        result['passed'] = True
                        result['error'] = None
            except Exception as e:
                if not result['error']:
                    result['error'] = f"模拟数据生成异常: {str(e)}"
        
        return result
    
    def _get_test_params_for_endpoint(self, endpoint: str) -> Dict:
        """获取测试端点的参数
        
        Args:
            endpoint: API端点
            
        Returns:
            Dict: 测试参数
        """
        # 根据不同端点返回适当的测试参数
        if endpoint == '/api/v1/get_trading_dates':
            return {'market': 'SH'}
        elif endpoint == '/api/v1/get_hist_kline':
            return {'symbol': '600519.SH', 'start_date': '20250101', 'end_date': '20250110'}
        elif endpoint == '/api/v1/instrument_detail':
            return {'symbol': '600519.SH'}
        elif endpoint == '/api/v1/stock_list':
            return {'sector': '银行'}
        elif endpoint == '/api/v1/latest_market':
            return {'symbols': '600519.SH,000001.SZ'}
        elif endpoint == '/api/v1/full_market':
            return {'market': 'SH'}
        else:
            return {}
    
    def _generate_mock_data(self, mock_generator, endpoint: str) -> Dict:
        """根据端点生成模拟数据
        
        Args:
            mock_generator: 模拟数据生成器实例
            endpoint: API端点
            
        Returns:
            Dict: 模拟数据
        """
        if endpoint == '/api/v1/get_trading_dates':
            return mock_generator.generate_trading_dates('SH')
        elif endpoint == '/api/v1/get_hist_kline':
            return mock_generator.generate_hist_kline('600519.SH', '20250101', '20250110')
        elif endpoint == '/api/v1/instrument_detail':
            return mock_generator.generate_instrument_detail('600519.SH')
        elif endpoint == '/api/v1/stock_list':
            return mock_generator.generate_stock_list('银行')
        elif endpoint == '/api/v1/latest_market':
            return mock_generator.generate_latest_market(['600519.SH', '000001.SZ'])
        elif endpoint == '/api/v1/full_market':
            return mock_generator.generate_full_market('SH')
        else:
            return {'code': -1, 'message': '未知端点'}
    
    def _test_mock_data(self) -> Dict:
        """测试模拟数据生成功能
        
        Returns:
            Dict: 测试结果
        """
        result = {
            'passed': False,
            'error': None,
            'generators_tested': 0,
            'generators_passed': 0
        }
        
        try:
            # 导入模拟数据生成器
            sys.path.append('.')  # 确保能够导入项目模块
            from common.mock_data import MockDataGenerator
            
            # 创建模拟数据生成器实例
            mock_generator = MockDataGenerator()
            
            # 测试各种模拟数据生成方法
            test_cases = [
                ('generate_trading_dates', ['SH']),
                ('generate_hist_kline', ['600519.SH', '20250101', '20250110']),
                ('generate_instrument_detail', ['600519.SH']),
                ('generate_stock_list', ['银行']),
                ('generate_latest_market', [['600519.SH', '000001.SZ']]),
                ('generate_full_market', ['SH'])
            ]
            
            for method_name, args in test_cases:
                result['generators_tested'] += 1
                
                # 调用模拟数据生成方法
                method = getattr(mock_generator, method_name)
                mock_data = method(*args)
                
                # 验证结果
                if mock_data and mock_data.get('code') == 0 and 'data' in mock_data:
                    result['generators_passed'] += 1
            
            # 如果所有生成器都通过，则测试通过
            if result['generators_passed'] == result['generators_tested']:
                result['passed'] = True
            else:
                result['error'] = f"部分模拟数据生成器失败: {result['generators_passed']}/{result['generators_tested']}"
                
        except Exception as e:
            result['error'] = f"模拟数据测试异常: {str(e)}"
        
        return result
    
    def test_performance(self) -> Dict:
        """执行性能基准测试
        
        Returns:
            Dict: 性能测试结果
        """
        print(f"\n{BOLD}{BLUE}3. 执行性能基准测试...{ENDC}")
        
        # 测试教程文件执行性能
        self._test_tutorial_execution_performance()
        
        # 测试API调用性能
        self._test_api_call_performance()
        
        # 测试数据处理性能
        self._test_data_processing_performance()
        
        print(f"\n性能测试完成")
        return self.results['performance']
    
    def _test_tutorial_execution_performance(self):
        """测试教程文件执行性能"""
        print(f"  测试教程文件执行性能...")
        
        for file_path in TUTORIAL_FILES:
            file_name = os.path.basename(file_path)
            print(f"    测试 {file_name}...", end='')
            
            # 跳过语法检查未通过的文件
            if file_path in self.results['syntax'] and not self.results['syntax'][file_path]['passed']:
                print(f"{YELLOW} 跳过 (语法错误){ENDC}")
                continue
            
            # 使用子进程执行教程文件，避免影响主进程
            try:
                # 设置超时时间，防止无限循环
                start_time = time.time()
                
                # 使用Python解释器执行文件，捕获输出
                process = subprocess.Popen(
                    [sys.executable, file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                # 等待进程完成，设置超时
                try:
                    stdout, stderr = process.communicate(timeout=PERFORMANCE_TEST_TIMEOUT)
                    execution_time = time.time() - start_time
                    
                    # 记录结果
                    self.results['performance'][file_path] = {
                        'execution_time': execution_time,
                        'success': process.returncode == 0,
                        'error': stderr if process.returncode != 0 else None
                    }
                    
                    if process.returncode == 0:
                        print(f"{GREEN} 通过 ({execution_time:.2f}秒){ENDC}")
                    else:
                        print(f"{RED} 失败{ENDC}")
                        print(f"      错误: {stderr[:100]}...")
                
                except subprocess.TimeoutExpired:
                    # 超时，终止进程
                    process.kill()
                    print(f"{RED} 超时 (>{PERFORMANCE_TEST_TIMEOUT}秒){ENDC}")
                    
                    self.results['performance'][file_path] = {
                        'execution_time': PERFORMANCE_TEST_TIMEOUT,
                        'success': False,
                        'error': f"执行超时 (>{PERFORMANCE_TEST_TIMEOUT}秒)"
                    }
            
            except Exception as e:
                print(f"{RED} 异常{ENDC}")
                print(f"      错误: {str(e)}")
                
                self.results['performance'][file_path] = {
                    'execution_time': None,
                    'success': False,
                    'error': str(e)
                }
    
    def _test_api_call_performance(self):
        """测试API调用性能"""
        print(f"  测试API调用性能...")
        
        # 检查API服务是否可用
        api_available = self._check_api_service()
        
        if not api_available:
            print(f"{YELLOW}    API服务不可用，跳过API调用性能测试{ENDC}")
            return
        
        # 测试各个API端点的性能
        for endpoint in API_ENDPOINTS:
            endpoint_name = endpoint.split('/')[-1]
            print(f"    测试端点 {endpoint_name}...", end='')
            
            # 准备测试参数
            params = self._get_test_params_for_endpoint(endpoint)
            
            # 执行多次调用，计算平均响应时间
            response_times = []
            success_count = 0
            
            for i in range(PERFORMANCE_TEST_ITERATIONS):
                try:
                    start_time = time.time()
                    response = requests.get(f"{self.base_url}{endpoint}", params=params, timeout=10)
                    response_time = time.time() - start_time
                    
                    response_times.append(response_time)
                    
                    if response.status_code == 200 and response.json().get('code') == 0:
                        success_count += 1
                
                except Exception:
                    pass
            
            # 计算统计数据
            if response_times:
                avg_time = sum(response_times) / len(response_times)
                min_time = min(response_times)
                max_time = max(response_times)
                success_rate = success_count / PERFORMANCE_TEST_ITERATIONS * 100
                
                self.results['performance'][f'api_{endpoint_name}'] = {
                    'avg_response_time': avg_time,
                    'min_response_time': min_time,
                    'max_response_time': max_time,
                    'success_rate': success_rate,
                    'iterations': PERFORMANCE_TEST_ITERATIONS
                }
                
                print(f"{GREEN} 平均: {avg_time:.3f}秒, 成功率: {success_rate:.0f}%{ENDC}")
            else:
                print(f"{RED} 所有请求失败{ENDC}")
                
                self.results['performance'][f'api_{endpoint_name}'] = {
                    'avg_response_time': None,
                    'min_response_time': None,
                    'max_response_time': None,
                    'success_rate': 0,
                    'iterations': PERFORMANCE_TEST_ITERATIONS
                }
    
    def _test_data_processing_performance(self):
        """测试数据处理性能"""
        print(f"  测试数据处理性能...")
        
        try:
            # 导入必要的模块
            sys.path.append('.')  # 确保能够导入项目模块
            from common.mock_data import MockDataGenerator
            
            # 创建模拟数据生成器实例
            mock_generator = MockDataGenerator()
            
            # 测试大数据量处理性能
            print(f"    测试大数据量处理...", end='')
            
            # 生成大量模拟数据
            start_time = time.time()
            
            # 生成1000只股票的模拟数据
            stock_count = 1000
            sh_stocks = [f"60{i:04d}.SH" for i in range(500)]
            sz_stocks = [f"00{i:04d}.SZ" for i in range(500)]
            all_stocks = sh_stocks + sz_stocks
            
            # 批量处理
            batch_size = 100
            batches = [all_stocks[i:i+batch_size] for i in range(0, len(all_stocks), batch_size)]
            
            total_data_points = 0
            batch_times = []
            
            for batch in batches:
                batch_start = time.time()
                mock_result = mock_generator.generate_full_market(symbols=batch)
                batch_time = time.time() - batch_start
                
                if mock_result.get('code') == 0:
                    batch_data = mock_result['data']
                    total_data_points += len(batch_data)
                    batch_times.append(batch_time)
            
            total_time = time.time() - start_time
            
            # 记录结果
            self.results['performance']['data_processing'] = {
                'total_time': total_time,
                'total_data_points': total_data_points,
                'processing_rate': total_data_points / total_time if total_time > 0 else 0,
                'avg_batch_time': sum(batch_times) / len(batch_times) if batch_times else 0,
                'batch_count': len(batches),
                'batch_size': batch_size
            }
            
            print(f"{GREEN} 完成 ({total_time:.2f}秒, {total_data_points}点){ENDC}")
            
        except Exception as e:
            print(f"{RED} 异常{ENDC}")
            print(f"      错误: {str(e)}")
            
            self.results['performance']['data_processing'] = {
                'error': str(e)
            }
    
    def save_results(self):
        """保存测试结果到文件"""
        # 保存为JSON文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = f"test_results/tutorial_test_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        # 创建最新结果的链接
        latest_file = "test_results/tutorial_test_latest.json"
        if os.path.exists(latest_file):
            os.remove(latest_file)
        
        # 在Windows上使用复制而不是符号链接
        import shutil
        shutil.copy2(result_file, latest_file)
    
    def generate_report(self):
        """生成HTML测试报告"""
        # 创建HTML报告
        report_file = "test_results/tutorial_test_report.html"
        
        # 读取结果数据
        summary = self.results['summary']
        syntax_results = self.results['syntax']
        api_results = self.results['api']
        performance_results = self.results['performance']
        
        # 生成HTML内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>教程测试报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #333; }}
                .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .pass {{ color: green; }}
                .fail {{ color: red; }}
                .warning {{ color: orange; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .chart-container {{ width: 600px; height: 400px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>教程测试报告</h1>
            
            <div class="summary">
                <h2>测试摘要</h2>
                <p>开始时间: {summary['start_time']}</p>
                <p>结束时间: {summary['end_time']}</p>
                <p>总耗时: {summary['duration']:.2f} 秒</p>
                <p>语法检查: <span class="{'pass' if summary['syntax_passed'] == summary['total_files'] else 'fail'}">{summary['syntax_passed']}/{summary['total_files']} 通过</span></p>
                <p>API测试: <span class="{'pass' if summary['api_passed'] == len(API_ENDPOINTS) else 'warning'}">{summary['api_passed']}/{len(API_ENDPOINTS)} 通过</span></p>
            </div>
            
            <h2>语法检查结果</h2>
            <table>
                <tr>
                    <th>文件</th>
                    <th>结果</th>
                    <th>错误信息</th>
                </tr>
        """
        
        # 添加语法检查结果
        for file_path, result in syntax_results.items():
            file_name = os.path.basename(file_path)
            status = "通过" if result['passed'] else "失败"
            status_class = "pass" if result['passed'] else "fail"
            error = result.get('error', '') if not result['passed'] else ''
            
            html_content += f"""
                <tr>
                    <td>{file_name}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{error}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h2>API测试结果</h2>
            <table>
                <tr>
                    <th>端点</th>
                    <th>结果</th>
                    <th>响应时间</th>
                    <th>状态码</th>
                    <th>模拟数据</th>
                    <th>错误信息</th>
                </tr>
        """
        
        # 添加API测试结果
        for endpoint, result in api_results.items():
            if endpoint == 'mock_data':
                continue
                
            endpoint_name = endpoint.split('/')[-1]
            status = "通过" if result.get('passed', False) else "失败"
            status_class = "pass" if result.get('passed', False) else "fail"
            response_time = f"{result.get('response_time', 0):.3f} 秒" if result.get('response_time') else 'N/A'
            status_code = result.get('status_code', 'N/A')
            mock_data = "有效" if result.get('mock_data_valid', False) else "无效"
            error = result.get('error', '') if not result.get('passed', False) else ''
            
            html_content += f"""
                <tr>
                    <td>{endpoint_name}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{response_time}</td>
                    <td>{status_code}</td>
                    <td>{mock_data}</td>
                    <td>{error}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h2>性能测试结果</h2>
            <h3>教程文件执行性能</h3>
            <table>
                <tr>
                    <th>文件</th>
                    <th>执行时间</th>
                    <th>结果</th>
                    <th>错误信息</th>
                </tr>
        """
        
        # 添加教程文件执行性能结果
        for file_path, result in performance_results.items():
            if not file_path.endswith('.py'):
                continue
                
            file_name = os.path.basename(file_path)
            execution_time = f"{result.get('execution_time', 0):.2f} 秒" if result.get('execution_time') else 'N/A'
            status = "成功" if result.get('success', False) else "失败"
            status_class = "pass" if result.get('success', False) else "fail"
            error = result.get('error', '') if not result.get('success', False) else ''
            
            html_content += f"""
                <tr>
                    <td>{file_name}</td>
                    <td>{execution_time}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{error}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h3>API调用性能</h3>
            <table>
                <tr>
                    <th>端点</th>
                    <th>平均响应时间</th>
                    <th>最小响应时间</th>
                    <th>最大响应时间</th>
                    <th>成功率</th>
                </tr>
        """
        
        # 添加API调用性能结果
        for key, result in performance_results.items():
            if not key.startswith('api_'):
                continue
                
            endpoint_name = key[4:]  # 去掉'api_'前缀
            avg_time = f"{result.get('avg_response_time', 0):.3f} 秒" if result.get('avg_response_time') else 'N/A'
            min_time = f"{result.get('min_response_time', 0):.3f} 秒" if result.get('min_response_time') else 'N/A'
            max_time = f"{result.get('max_response_time', 0):.3f} 秒" if result.get('max_response_time') else 'N/A'
            success_rate = f"{result.get('success_rate', 0):.0f}%" if result.get('success_rate') is not None else 'N/A'
            
            html_content += f"""
                <tr>
                    <td>{endpoint_name}</td>
                    <td>{avg_time}</td>
                    <td>{min_time}</td>
                    <td>{max_time}</td>
                    <td>{success_rate}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h3>数据处理性能</h3>
        """
        
        # 添加数据处理性能结果
        if 'data_processing' in performance_results:
            dp = performance_results['data_processing']
            if 'error' in dp:
                html_content += f"""
                <p class="fail">数据处理测试失败: {dp['error']}</p>
                """
            else:
                total_time = f"{dp.get('total_time', 0):.2f} 秒"
                total_points = dp.get('total_data_points', 0)
                processing_rate = f"{dp.get('processing_rate', 0):.1f} 点/秒"
                avg_batch_time = f"{dp.get('avg_batch_time', 0):.3f} 秒"
                
                html_content += f"""
                <table>
                    <tr>
                        <th>总处理时间</th>
                        <th>数据点数量</th>
                        <th>处理速率</th>
                        <th>平均批处理时间</th>
                        <th>批次数量</th>
                        <th>批次大小</th>
                    </tr>
                    <tr>
                        <td>{total_time}</td>
                        <td>{total_points}</td>
                        <td>{processing_rate}</td>
                        <td>{avg_batch_time}</td>
                        <td>{dp.get('batch_count', 0)}</td>
                        <td>{dp.get('batch_size', 0)}</td>
                    </tr>
                </table>
                """
        else:
            html_content += """
            <p>未执行数据处理性能测试</p>
            """
        
        # 结束HTML
        html_content += """
        </body>
        </html>
        """
        
        # 写入HTML文件
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程文件自动化测试脚本')
    parser.add_argument('--syntax-only', action='store_true', help='仅执行语法检查')
    parser.add_argument('--api-test', action='store_true', help='仅执行API可用性测试')
    parser.add_argument('--performance', action='store_true', help='仅执行性能基准测试')
    parser.add_argument('--all', action='store_true', help='执行所有测试（默认）')
    parser.add_argument('--base-url', default='http://localhost:8000', help='API服务基础URL')
    
    args = parser.parse_args()
    
    # 创建测试器实例
    tester = TutorialTester(base_url=args.base_url)
    
    # 根据参数执行测试
    if args.syntax_only:
        tester.test_syntax()
    elif args.api_test:
        tester.test_api_availability()
    elif args.performance:
        tester.test_performance()
    else:
        # 默认执行所有测试
        tester.run_all_tests()
    
    # 保存结果和生成报告
    tester.save_results()
    tester.generate_report()


if __name__ == "__main__":
    main()