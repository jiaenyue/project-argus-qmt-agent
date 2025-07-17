#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
教程回归测试脚本

该脚本用于比较当前测试结果与基准测试结果，检测性能退化和功能回归。
支持以下功能：
- 比较语法检查结果
- 比较API测试结果
- 比较性能测试结果
- 生成回归测试报告

使用方法：
    python regression_test.py [--baseline FILE] [--current FILE]

参数：
    --baseline: 基准测试结果文件路径（默认：test_results/tutorial_test_baseline.json）
    --current: 当前测试结果文件路径（默认：test_results/tutorial_test_latest.json）
"""

import os
import sys
import json
import argparse
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

# 定义颜色代码，用于控制台输出
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
ENDC = '\033[0m'
BOLD = '\033[1m'


class RegressionTester:
    """回归测试器类，用于比较测试结果"""
    
    def __init__(self, baseline_file: str, current_file: str):
        """初始化回归测试器
        
        Args:
            baseline_file: 基准测试结果文件路径
            current_file: 当前测试结果文件路径
        """
        self.baseline_file = baseline_file
        self.current_file = current_file
        self.baseline_data = None
        self.current_data = None
        self.comparison_results = {
            'syntax': {},
            'api': {},
            'performance': {},
            'summary': {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'baseline_file': baseline_file,
                'current_file': current_file,
                'syntax_regressions': 0,
                'api_regressions': 0,
                'performance_regressions': 0
            }
        }
        
        # 创建结果目录
        os.makedirs('test_results', exist_ok=True)
    
    def load_data(self) -> bool:
        """加载测试数据
        
        Returns:
            bool: 是否成功加载数据
        """
        try:
            # 加载基准数据
            if not os.path.exists(self.baseline_file):
                print(f"{RED}错误: 基准文件不存在: {self.baseline_file}{ENDC}")
                return False
            
            with open(self.baseline_file, 'r', encoding='utf-8') as f:
                self.baseline_data = json.load(f)
            
            # 加载当前数据
            if not os.path.exists(self.current_file):
                print(f"{RED}错误: 当前测试文件不存在: {self.current_file}{ENDC}")
                return False
            
            with open(self.current_file, 'r', encoding='utf-8') as f:
                self.current_data = json.load(f)
            
            return True
        
        except Exception as e:
            print(f"{RED}加载数据时出错: {str(e)}{ENDC}")
            return False
    
    def compare_results(self) -> dict:
        """比较测试结果
        
        Returns:
            dict: 比较结果
        """
        if not self.baseline_data or not self.current_data:
            if not self.load_data():
                return self.comparison_results
        
        print(f"{BOLD}开始比较测试结果...{ENDC}")
        
        # 比较语法检查结果
        self._compare_syntax_results()
        
        # 比较API测试结果
        self._compare_api_results()
        
        # 比较性能测试结果
        self._compare_performance_results()
        
        # 生成比较报告
        self._generate_report()
        
        return self.comparison_results
    
    def _compare_syntax_results(self):
        """比较语法检查结果"""
        print(f"\n{BOLD}{BLUE}1. 比较语法检查结果...{ENDC}")
        
        baseline_syntax = self.baseline_data.get('syntax', {})
        current_syntax = self.current_data.get('syntax', {})
        
        # 检查每个文件的语法结果
        for file_path in set(baseline_syntax.keys()) | set(current_syntax.keys()):
            file_name = os.path.basename(file_path)
            
            baseline_result = baseline_syntax.get(file_path, {}).get('passed', False)
            current_result = current_syntax.get(file_path, {}).get('passed', False)
            
            # 检测回归
            if baseline_result and not current_result:
                self.comparison_results['syntax'][file_path] = {
                    'status': 'regression',
                    'baseline': baseline_result,
                    'current': current_result,
                    'error': current_syntax.get(file_path, {}).get('error')
                }
                self.comparison_results['summary']['syntax_regressions'] += 1
                print(f"  {RED}回归{ENDC}: {file_name} - 基准通过但当前失败")
            
            # 检测改进
            elif not baseline_result and current_result:
                self.comparison_results['syntax'][file_path] = {
                    'status': 'improvement',
                    'baseline': baseline_result,
                    'current': current_result
                }
                print(f"  {GREEN}改进{ENDC}: {file_name} - 基准失败但当前通过")
            
            # 检测无变化
            else:
                self.comparison_results['syntax'][file_path] = {
                    'status': 'unchanged',
                    'baseline': baseline_result,
                    'current': current_result
                }
        
        print(f"语法检查比较完成: {self.comparison_results['summary']['syntax_regressions']} 个回归")
    
    def _compare_api_results(self):
        """比较API测试结果"""
        print(f"\n{BOLD}{BLUE}2. 比较API测试结果...{ENDC}")
        
        baseline_api = self.baseline_data.get('api', {})
        current_api = self.current_data.get('api', {})
        
        # 检查每个API端点的结果
        for endpoint in set(baseline_api.keys()) | set(current_api.keys()):
            if endpoint == 'mock_data':
                continue
                
            endpoint_name = endpoint.split('/')[-1] if '/' in endpoint else endpoint
            
            baseline_result = baseline_api.get(endpoint, {}).get('passed', False)
            current_result = current_api.get(endpoint, {}).get('passed', False)
            
            # 检测回归
            if baseline_result and not current_result:
                self.comparison_results['api'][endpoint] = {
                    'status': 'regression',
                    'baseline': baseline_result,
                    'current': current_result,
                    'error': current_api.get(endpoint, {}).get('error')
                }
                self.comparison_results['summary']['api_regressions'] += 1
                print(f"  {RED}回归{ENDC}: {endpoint_name} - 基准通过但当前失败")
            
            # 检测改进
            elif not baseline_result and current_result:
                self.comparison_results['api'][endpoint] = {
                    'status': 'improvement',
                    'baseline': baseline_result,
                    'current': current_result
                }
                print(f"  {GREEN}改进{ENDC}: {endpoint_name} - 基准失败但当前通过")
            
            # 检测无变化
            else:
                self.comparison_results['api'][endpoint] = {
                    'status': 'unchanged',
                    'baseline': baseline_result,
                    'current': current_result
                }
        
        print(f"API测试比较完成: {self.comparison_results['summary']['api_regressions']} 个回归")
    
    def _compare_performance_results(self):
        """比较性能测试结果"""
        print(f"\n{BOLD}{BLUE}3. 比较性能测试结果...{ENDC}")
        
        baseline_perf = self.baseline_data.get('performance', {})
        current_perf = self.current_data.get('performance', {})
        
        # 比较教程文件执行性能
        for file_path in set(k for k in baseline_perf.keys() if k.endswith('.py')) | set(k for k in current_perf.keys() if k.endswith('.py')):
            file_name = os.path.basename(file_path)
            
            baseline_time = baseline_perf.get(file_path, {}).get('execution_time')
            current_time = current_perf.get(file_path, {}).get('execution_time')
            
            if baseline_time is not None and current_time is not None:
                # 计算性能变化百分比
                if baseline_time > 0:
                    change_pct = (current_time - baseline_time) / baseline_time * 100
                    
                    # 性能退化超过10%视为回归
                    if change_pct > 10:
                        self.comparison_results['performance'][file_path] = {
                            'status': 'regression',
                            'baseline_time': baseline_time,
                            'current_time': current_time,
                            'change_pct': change_pct
                        }
                        self.comparison_results['summary']['performance_regressions'] += 1
                        print(f"  {RED}性能回归{ENDC}: {file_name} - 执行时间增加 {change_pct:.1f}%")
                    
                    # 性能提升超过10%视为改进
                    elif change_pct < -10:
                        self.comparison_results['performance'][file_path] = {
                            'status': 'improvement',
                            'baseline_time': baseline_time,
                            'current_time': current_time,
                            'change_pct': change_pct
                        }
                        print(f"  {GREEN}性能改进{ENDC}: {file_name} - 执行时间减少 {-change_pct:.1f}%")
                    
                    # 变化不大视为无变化
                    else:
                        self.comparison_results['performance'][file_path] = {
                            'status': 'unchanged',
                            'baseline_time': baseline_time,
                            'current_time': current_time,
                            'change_pct': change_pct
                        }
        
        # 比较API调用性能
        for key in set(k for k in baseline_perf.keys() if k.startswith('api_')) | set(k for k in current_perf.keys() if k.startswith('api_')):
            endpoint_name = key[4:]  # 去掉'api_'前缀
            
            baseline_time = baseline_perf.get(key, {}).get('avg_response_time')
            current_time = current_perf.get(key, {}).get('avg_response_time')
            
            if baseline_time is not None and current_time is not None:
                # 计算性能变化百分比
                if baseline_time > 0:
                    change_pct = (current_time - baseline_time) / baseline_time * 100
                    
                    # 性能退化超过20%视为回归（API调用受网络影响较大，阈值放宽）
                    if change_pct > 20:
                        self.comparison_results['performance'][key] = {
                            'status': 'regression',
                            'baseline_time': baseline_time,
                            'current_time': current_time,
                            'change_pct': change_pct
                        }
                        self.comparison_results['summary']['performance_regressions'] += 1
                        print(f"  {RED}性能回归{ENDC}: API {endpoint_name} - 响应时间增加 {change_pct:.1f}%")
                    
                    # 性能提升超过20%视为改进
                    elif change_pct < -20:
                        self.comparison_results['performance'][key] = {
                            'status': 'improvement',
                            'baseline_time': baseline_time,
                            'current_time': current_time,
                            'change_pct': change_pct
                        }
                        print(f"  {GREEN}性能改进{ENDC}: API {endpoint_name} - 响应时间减少 {-change_pct:.1f}%")
                    
                    # 变化不大视为无变化
                    else:
                        self.comparison_results['performance'][key] = {
                            'status': 'unchanged',
                            'baseline_time': baseline_time,
                            'current_time': current_time,
                            'change_pct': change_pct
                        }
        
        # 比较数据处理性能
        if 'data_processing' in baseline_perf and 'data_processing' in current_perf:
            baseline_dp = baseline_perf['data_processing']
            current_dp = current_perf['data_processing']
            
            if 'processing_rate' in baseline_dp and 'processing_rate' in current_dp:
                baseline_rate = baseline_dp['processing_rate']
                current_rate = current_dp['processing_rate']
                
                if baseline_rate > 0:
                    change_pct = (current_rate - baseline_rate) / baseline_rate * 100
                    
                    # 处理速率下降超过15%视为回归
                    if change_pct < -15:
                        self.comparison_results['performance']['data_processing'] = {
                            'status': 'regression',
                            'baseline_rate': baseline_rate,
                            'current_rate': current_rate,
                            'change_pct': change_pct
                        }
                        self.comparison_results['summary']['performance_regressions'] += 1
                        print(f"  {RED}性能回归{ENDC}: 数据处理 - 处理速率下降 {-change_pct:.1f}%")
                    
                    # 处理速率提升超过15%视为改进
                    elif change_pct > 15:
                        self.comparison_results['performance']['data_processing'] = {
                            'status': 'improvement',
                            'baseline_rate': baseline_rate,
                            'current_rate': current_rate,
                            'change_pct': change_pct
                        }
                        print(f"  {GREEN}性能改进{ENDC}: 数据处理 - 处理速率提升 {change_pct:.1f}%")
                    
                    # 变化不大视为无变化
                    else:
                        self.comparison_results['performance']['data_processing'] = {
                            'status': 'unchanged',
                            'baseline_rate': baseline_rate,
                            'current_rate': current_rate,
                            'change_pct': change_pct
                        }
        
        print(f"性能测试比较完成: {self.comparison_results['summary']['performance_regressions']} 个回归")
    
    def _generate_report(self):
        """生成比较报告"""
        # 保存比较结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = f"test_results/regression_test_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.comparison_results, f, ensure_ascii=False, indent=2)
        
        # 创建HTML报告
        report_file = "test_results/regression_test_report.html"
        self._generate_html_report(report_file)
        
        print(f"\n{BOLD}回归测试报告已生成: {report_file}{ENDC}")
    
    def _generate_html_report(self, report_file: str):
        """生成HTML报告
        
        Args:
            report_file: 报告文件路径
        """
        # 提取基准和当前测试的时间信息
        baseline_time = self.baseline_data.get('summary', {}).get('start_time', 'Unknown')
        current_time = self.current_data.get('summary', {}).get('start_time', 'Unknown')
        
        # 生成HTML内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>教程回归测试报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #333; }}
                .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .regression {{ color: red; }}
                .improvement {{ color: green; }}
                .unchanged {{ color: gray; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .chart-container {{ width: 600px; height: 400px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>教程回归测试报告</h1>
            
            <div class="summary">
                <h2>测试摘要</h2>
                <p>比较时间: {self.comparison_results['summary']['timestamp']}</p>
                <p>基准测试: {baseline_time} ({os.path.basename(self.baseline_file)})</p>
                <p>当前测试: {current_time} ({os.path.basename(self.current_file)})</p>
                <p>语法回归: <span class="{'regression' if self.comparison_results['summary']['syntax_regressions'] > 0 else 'unchanged'}">{self.comparison_results['summary']['syntax_regressions']}</span></p>
                <p>API回归: <span class="{'regression' if self.comparison_results['summary']['api_regressions'] > 0 else 'unchanged'}">{self.comparison_results['summary']['api_regressions']}</span></p>
                <p>性能回归: <span class="{'regression' if self.comparison_results['summary']['performance_regressions'] > 0 else 'unchanged'}">{self.comparison_results['summary']['performance_regressions']}</span></p>
            </div>
            
            <h2>语法检查比较</h2>
            <table>
                <tr>
                    <th>文件</th>
                    <th>状态</th>
                    <th>基准结果</th>
                    <th>当前结果</th>
                    <th>错误信息</th>
                </tr>
        """
        
        # 添加语法检查比较结果
        for file_path, result in self.comparison_results['syntax'].items():
            file_name = os.path.basename(file_path)
            status = result['status']
            baseline = "通过" if result.get('baseline', False) else "失败"
            current = "通过" if result.get('current', False) else "失败"
            error = result.get('error', '') if status == 'regression' else ''
            
            html_content += f"""
                <tr>
                    <td>{file_name}</td>
                    <td class="{status}">{status}</td>
                    <td>{baseline}</td>
                    <td>{current}</td>
                    <td>{error}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h2>API测试比较</h2>
            <table>
                <tr>
                    <th>端点</th>
                    <th>状态</th>
                    <th>基准结果</th>
                    <th>当前结果</th>
                    <th>错误信息</th>
                </tr>
        """
        
        # 添加API测试比较结果
        for endpoint, result in self.comparison_results['api'].items():
            endpoint_name = endpoint.split('/')[-1] if '/' in endpoint else endpoint
            status = result['status']
            baseline = "通过" if result.get('baseline', False) else "失败"
            current = "通过" if result.get('current', False) else "失败"
            error = result.get('error', '') if status == 'regression' else ''
            
            html_content += f"""
                <tr>
                    <td>{endpoint_name}</td>
                    <td class="{status}">{status}</td>
                    <td>{baseline}</td>
                    <td>{current}</td>
                    <td>{error}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h2>性能测试比较</h2>
            <h3>教程文件执行性能</h3>
            <table>
                <tr>
                    <th>文件</th>
                    <th>状态</th>
                    <th>基准时间</th>
                    <th>当前时间</th>
                    <th>变化</th>
                </tr>
        """
        
        # 添加教程文件执行性能比较结果
        for file_path, result in self.comparison_results['performance'].items():
            if not file_path.endswith('.py'):
                continue
                
            file_name = os.path.basename(file_path)
            status = result['status']
            baseline_time = f"{result.get('baseline_time', 0):.2f} 秒"
            current_time = f"{result.get('current_time', 0):.2f} 秒"
            change = f"{result.get('change_pct', 0):.1f}%"
            
            html_content += f"""
                <tr>
                    <td>{file_name}</td>
                    <td class="{status}">{status}</td>
                    <td>{baseline_time}</td>
                    <td>{current_time}</td>
                    <td class="{status}">{change}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h3>API调用性能</h3>
            <table>
                <tr>
                    <th>端点</th>
                    <th>状态</th>
                    <th>基准响应时间</th>
                    <th>当前响应时间</th>
                    <th>变化</th>
                </tr>
        """
        
        # 添加API调用性能比较结果
        for key, result in self.comparison_results['performance'].items():
            if not key.startswith('api_'):
                continue
                
            endpoint_name = key[4:]  # 去掉'api_'前缀
            status = result['status']
            baseline_time = f"{result.get('baseline_time', 0):.3f} 秒"
            current_time = f"{result.get('current_time', 0):.3f} 秒"
            change = f"{result.get('change_pct', 0):.1f}%"
            
            html_content += f"""
                <tr>
                    <td>{endpoint_name}</td>
                    <td class="{status}">{status}</td>
                    <td>{baseline_time}</td>
                    <td>{current_time}</td>
                    <td class="{status}">{change}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h3>数据处理性能</h3>
        """
        
        # 添加数据处理性能比较结果
        if 'data_processing' in self.comparison_results['performance']:
            dp = self.comparison_results['performance']['data_processing']
            status = dp['status']
            baseline_rate = f"{dp.get('baseline_rate', 0):.1f} 点/秒"
            current_rate = f"{dp.get('current_rate', 0):.1f} 点/秒"
            change = f"{dp.get('change_pct', 0):.1f}%"
            
            html_content += f"""
            <table>
                <tr>
                    <th>指标</th>
                    <th>状态</th>
                    <th>基准处理速率</th>
                    <th>当前处理速率</th>
                    <th>变化</th>
                </tr>
                <tr>
                    <td>数据处理速率</td>
                    <td class="{status}">{status}</td>
                    <td>{baseline_rate}</td>
                    <td>{current_rate}</td>
                    <td class="{status}">{change}</td>
                </tr>
            </table>
            """
        else:
            html_content += """
            <p>未比较数据处理性能</p>
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
    parser = argparse.ArgumentParser(description='教程回归测试脚本')
    parser.add_argument('--baseline', default='test_results/tutorial_test_baseline.json', help='基准测试结果文件路径')
    parser.add_argument('--current', default='test_results/tutorial_test_latest.json', help='当前测试结果文件路径')
    
    args = parser.parse_args()
    
    # 创建回归测试器实例
    tester = RegressionTester(baseline_file=args.baseline, current_file=args.current)
    
    # 执行比较
    tester.compare_results()


if __name__ == "__main__":
    main()