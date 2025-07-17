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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
生成综合质量报告

该脚本用于生成教程文件的综合质量报告。
它整合了语法检查、API测试、性能测试和执行结果。

使用方法：
    python generate_report.py [--syntax FILE] [--api FILE] [--performance FILE] [--execution FILE] [--output FILE]

参数：
    --syntax: 语法检查结果文件（默认：test_results/tutorial_test_latest.json）
    --api: API测试结果文件（默认：tutorials_validation_report.json）
    --performance: 性能测试结果文件（默认：test_results/tutorial_test_latest.json）
    --execution: 执行结果文件（默认：tutorials_quality_report.json）
    --output: 输出报告文件路径（默认：tutorials_comprehensive_report.html）
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# 定义教程文件列表
TUTORIAL_FILES = [
    'tutorials/01_trading_dates.py',
    'tutorials/02_hist_kline.py',
    'tutorials/03_instrument_detail.py',
    'tutorials/04_stock_list.py',
    'tutorials/06_latest_market.py',
    'tutorials/07_full_market.py',
]


class ReportGenerator:
    """报告生成器类，用于生成综合质量报告"""
    
    def __init__(self, syntax_file: str, api_file: str, performance_file: str, execution_file: str):
        """初始化报告生成器
        
        Args:
            syntax_file: 语法检查结果文件
            api_file: API测试结果文件
            performance_file: 性能测试结果文件
            execution_file: 执行结果文件
        """
        self.syntax_file = syntax_file
        self.api_file = api_file
        self.performance_file = performance_file
        self.execution_file = execution_file
        
        self.syntax_data = None
        self.api_data = None
        self.performance_data = None
        self.execution_data = None
        
        self.report_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'files': {},
            'api_endpoints': {},
            'summary': {
                'total_files': len(TUTORIAL_FILES),
                'syntax_passed': 0,
                'api_passed': 0,
                'execution_passed': 0,
                'overall_quality': 0
            }
        }
    
    def generate_report(self, output_file: str) -> Dict:
        """生成综合质量报告
        
        Args:
            output_file: 输出报告文件路径
            
        Returns:
            Dict: 报告数据
        """
        print(f"开始生成综合质量报告...")
        
        # 加载数据
        self._load_data()
        
        # 整合数据
        self._integrate_data()
        
        # 计算质量分数
        self._calculate_quality_scores()
        
        # 生成HTML报告
        self._generate_html_report(output_file)
        
        print(f"综合质量报告已生成: {output_file}")
        
        return self.report_data
    
    def _load_data(self):
        """加载数据文件"""
        # 加载语法检查结果
        if os.path.exists(self.syntax_file):
            try:
                with open(self.syntax_file, 'r', encoding='utf-8') as f:
                    self.syntax_data = json.load(f)
                print(f"已加载语法检查结果: {self.syntax_file}")
            except Exception as e:
                print(f"加载语法检查结果失败: {str(e)}")
        else:
            print(f"语法检查结果文件不存在: {self.syntax_file}")
        
        # 加载API测试结果
        if os.path.exists(self.api_file):
            try:
                with open(self.api_file, 'r', encoding='utf-8') as f:
                    self.api_data = json.load(f)
                print(f"已加载API测试结果: {self.api_file}")
            except Exception as e:
                print(f"加载API测试结果失败: {str(e)}")
        else:
            print(f"API测试结果文件不存在: {self.api_file}")
        
        # 加载性能测试结果
        if os.path.exists(self.performance_file):
            try:
                with open(self.performance_file, 'r', encoding='utf-8') as f:
                    self.performance_data = json.load(f)
                print(f"已加载性能测试结果: {self.performance_file}")
            except Exception as e:
                print(f"加载性能测试结果失败: {str(e)}")
        else:
            print(f"性能测试结果文件不存在: {self.performance_file}")
        
        # 加载执行结果
        if os.path.exists(self.execution_file):
            try:
                with open(self.execution_file, 'r', encoding='utf-8') as f:
                    self.execution_data = json.load(f)
                print(f"已加载执行结果: {self.execution_file}")
            except Exception as e:
                print(f"加载执行结果失败: {str(e)}")
        else:
            print(f"执行结果文件不存在: {self.execution_file}")
    
    def _integrate_data(self):
        """整合数据"""
        # 整合文件数据
        for file_path in TUTORIAL_FILES:
            file_name = os.path.basename(file_path)
            
            file_data = {
                'name': file_name,
                'path': file_path,
                'syntax': {
                    'passed': False,
                    'error': None
                },
                'api_calls': {
                    'valid': False,
                    'total': 0,
                    'valid_count': 0
                },
                'performance': {
                    'execution_time': None,
                    'success': False
                },
                'execution': {
                    'success': False,
                    'duration': None,
                    'error': None
                },
                'quality_score': 0
            }
            
            # 添加语法检查结果
            if self.syntax_data and 'syntax' in self.syntax_data:
                if file_path in self.syntax_data['syntax']:
                    syntax_result = self.syntax_data['syntax'][file_path]
                    file_data['syntax']['passed'] = syntax_result.get('passed', False)
                    file_data['syntax']['error'] = syntax_result.get('error')
            
            # 添加API调用验证结果
            if self.api_data and 'tutorial_validation' in self.api_data:
                if file_path in self.api_data['tutorial_validation']:
                    api_result = self.api_data['tutorial_validation'][file_path]
                    file_data['api_calls']['valid'] = api_result.get('valid', False)
                    file_data['api_calls']['total'] = api_result.get('api_calls_total', 0)
                    file_data['api_calls']['valid_count'] = api_result.get('api_calls_valid', 0)
            
            # 添加性能测试结果
            if self.performance_data and 'performance' in self.performance_data:
                if file_path in self.performance_data['performance']:
                    perf_result = self.performance_data['performance'][file_path]
                    file_data['performance']['execution_time'] = perf_result.get('execution_time')
                    file_data['performance']['success'] = perf_result.get('success', False)
            
            # 添加执行结果
            if self.execution_data and 'executions' in self.execution_data:
                if file_path in self.execution_data['executions']:
                    exec_result = self.execution_data['executions'][file_path]
                    file_data['execution']['success'] = exec_result.get('success', False)
                    file_data['execution']['duration'] = exec_result.get('duration')
                    file_data['execution']['error'] = exec_result.get('error')
            
            # 添加到报告数据
            self.report_data['files'][file_path] = file_data
        
        # 整合API端点数据
        if self.api_data and 'api_validation' in self.api_data:
            for endpoint, result in self.api_data['api_validation'].items():
                self.report_data['api_endpoints'][endpoint] = {
                    'valid': result.get('valid', False),
                    'response_time': result.get('response_time'),
                    'status_code': result.get('status_code'),
                    'error': result.get('error')
                }
    
    def _calculate_quality_scores(self):
        """计算质量分数"""
        # 计算每个文件的质量分数
        for file_path, file_data in self.report_data['files'].items():
            score = 0
            
            # 语法检查（30分）
            if file_data['syntax']['passed']:
                score += 30
                self.report_data['summary']['syntax_passed'] += 1
            
            # API调用验证（30分）
            if file_data['api_calls']['valid']:
                score += 30
                self.report_data['summary']['api_passed'] += 1
            elif file_data['api_calls']['total'] > 0:
                # 部分有效
                valid_ratio = file_data['api_calls']['valid_count'] / file_data['api_calls']['total']
                score += int(30 * valid_ratio)
            
            # 执行成功（40分）
            if file_data['execution']['success']:
                score += 40
                self.report_data['summary']['execution_passed'] += 1
            
            # 更新文件质量分数
            file_data['quality_score'] = score
        
        # 计算总体质量分数
        if self.report_data['summary']['total_files'] > 0:
            total_score = sum(f['quality_score'] for f in self.report_data['files'].values())
            self.report_data['summary']['overall_quality'] = int(total_score / self.report_data['summary']['total_files'])
    
    def _generate_html_report(self, output_file: str):
        """生成HTML报告
        
        Args:
            output_file: 输出报告文件路径
        """
        # 准备HTML内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>教程综合质量报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #333; }}
                .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .good {{ color: green; }}
                .warning {{ color: orange; }}
                .bad {{ color: red; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .progress-bar {{ 
                    width: 100%; 
                    background-color: #e0e0e0; 
                    border-radius: 5px; 
                    margin-bottom: 10px;
                }}
                .progress {{ 
                    height: 20px; 
                    border-radius: 5px; 
                    text-align: center; 
                    line-height: 20px; 
                    color: white; 
                }}
                .quality-score {{ font-size: 24px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>教程综合质量报告</h1>
            
            <div class="summary">
                <h2>质量摘要</h2>
                <p>生成时间: {self.report_data['timestamp']}</p>
                <p>总体质量分数: <span class="quality-score {self._get_score_class(self.report_data['summary']['overall_quality'])}">{self.report_data['summary']['overall_quality']}/100</span></p>
                
                <div class="progress-bar">
                    <div class="progress" style="width: {self.report_data['summary']['overall_quality']}%; background-color: {self._get_score_color(self.report_data['summary']['overall_quality'])}">
                        {self.report_data['summary']['overall_quality']}%
                    </div>
                </div>
                
                <p>语法检查通过: {self.report_data['summary']['syntax_passed']}/{self.report_data['summary']['total_files']}</p>
                <p>API调用验证通过: {self.report_data['summary']['api_passed']}/{self.report_data['summary']['total_files']}</p>
                <p>执行成功: {self.report_data['summary']['execution_passed']}/{self.report_data['summary']['total_files']}</p>
            </div>
            
            <h2>文件质量详情</h2>
            <table>
                <tr>
                    <th>文件</th>
                    <th>质量分数</th>
                    <th>语法检查</th>
                    <th>API调用</th>
                    <th>执行结果</th>
                    <th>执行时间</th>
                </tr>
        """
        
        # 添加文件质量详情
        for file_path, file_data in sorted(self.report_data['files'].items()):
            file_name = file_data['name']
            quality_score = file_data['quality_score']
            syntax_status = "通过" if file_data['syntax']['passed'] else "失败"
            syntax_class = "good" if file_data['syntax']['passed'] else "bad"
            
            api_status = f"{file_data['api_calls']['valid_count']}/{file_data['api_calls']['total']}"
            api_class = "good" if file_data['api_calls']['valid'] else ("warning" if file_data['api_calls']['valid_count'] > 0 else "bad")
            
            exec_status = "成功" if file_data['execution']['success'] else "失败"
            exec_class = "good" if file_data['execution']['success'] else "bad"
            
            exec_time = f"{file_data['execution']['duration']:.2f}秒" if file_data['execution']['duration'] else "N/A"
            
            html_content += f"""
                <tr>
                    <td>{file_name}</td>
                    <td class="{self._get_score_class(quality_score)}">{quality_score}/100</td>
                    <td class="{syntax_class}">{syntax_status}</td>
                    <td class="{api_class}">{api_status}</td>
                    <td class="{exec_class}">{exec_status}</td>
                    <td>{exec_time}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h2>API端点状态</h2>
            <table>
                <tr>
                    <th>端点</th>
                    <th>状态</th>
                    <th>响应时间</th>
                    <th>状态码</th>
                    <th>错误信息</th>
                </tr>
        """
        
        # 添加API端点状态
        for endpoint, data in sorted(self.report_data['api_endpoints'].items()):
            status = "有效" if data['valid'] else "无效"
            status_class = "good" if data['valid'] else "bad"
            response_time = f"{data['response_time']:.3f}秒" if data['response_time'] else "N/A"
            status_code = data['status_code'] if data['status_code'] else "N/A"
            error = data['error'] if data['error'] else ""
            
            html_content += f"""
                <tr>
                    <td>{endpoint}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{response_time}</td>
                    <td>{status_code}</td>
                    <td>{error}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h2>详细错误信息</h2>
            <table>
                <tr>
                    <th>文件</th>
                    <th>错误类型</th>
                    <th>错误信息</th>
                </tr>
        """
        
        # 添加详细错误信息
        for file_path, file_data in sorted(self.report_data['files'].items()):
            file_name = file_data['name']
            
            # 语法错误
            if not file_data['syntax']['passed'] and file_data['syntax']['error']:
                html_content += f"""
                    <tr>
                        <td>{file_name}</td>
                        <td>语法错误</td>
                        <td>{file_data['syntax']['error']}</td>
                    </tr>
                """
            
            # 执行错误
            if not file_data['execution']['success'] and file_data['execution']['error']:
                html_content += f"""
                    <tr>
                        <td>{file_name}</td>
                        <td>执行错误</td>
                        <td>{file_data['execution']['error']}</td>
                    </tr>
                """
        
        # 结束HTML
        html_content += """
            </table>
            
            <h2>改进建议</h2>
            <ul>
        """
        
        # 添加改进建议
        suggestions = self._generate_suggestions()
        for suggestion in suggestions:
            html_content += f"""
                <li>{suggestion}</li>
            """
        
        html_content += """
            </ul>
        </body>
        </html>
        """
        
        # 写入HTML文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _get_score_class(self, score: int) -> str:
        """获取分数对应的CSS类
        
        Args:
            score: 分数
            
        Returns:
            str: CSS类名
        """
        if score >= 80:
            return "good"
        elif score >= 60:
            return "warning"
        else:
            return "bad"
    
    def _get_score_color(self, score: int) -> str:
        """获取分数对应的颜色
        
        Args:
            score: 分数
            
        Returns:
            str: 颜色代码
        """
        if score >= 80:
            return "#4CAF50"  # 绿色
        elif score >= 60:
            return "#FF9800"  # 橙色
        else:
            return "#F44336"  # 红色
    
    def _generate_suggestions(self) -> List[str]:
        """生成改进建议
        
        Returns:
            List[str]: 建议列表
        """
        suggestions = []
        
        # 语法错误建议
        syntax_failed = len(self.report_data['files']) - self.report_data['summary']['syntax_passed']
        if syntax_failed > 0:
            suggestions.append(f"修复 {syntax_failed} 个文件中的语法错误，特别是 safe_api_call 递归调用和字典语法问题。")
        
        # API调用建议
        api_failed = len(self.report_data['files']) - self.report_data['summary']['api_passed']
        if api_failed > 0:
            suggestions.append(f"改进 {api_failed} 个文件中的API调用，确保参数传递正确。")
        
        # 执行失败建议
        exec_failed = len(self.report_data['files']) - self.report_data['summary']['execution_passed']
        if exec_failed > 0:
            suggestions.append(f"解决 {exec_failed} 个文件的执行错误，确保它们可以正常运行。")
        
        # API端点建议
        invalid_endpoints = sum(1 for data in self.report_data['api_endpoints'].values() if not data['valid'])
        if invalid_endpoints > 0:
            suggestions.append(f"检查 {invalid_endpoints} 个无效的API端点，确保服务正常运行。")
        
        # 性能建议
        slow_files = sum(1 for data in self.report_data['files'].values() 
                         if data['execution']['duration'] and data['execution']['duration'] > 10)
        if slow_files > 0:
            suggestions.append(f"优化 {slow_files} 个执行时间较长的文件，提高性能。")
        
        # 通用建议
        suggestions.append("使用统一的API客户端和错误处理机制，减少代码重复。")
        suggestions.append("添加更详细的注释和文档字符串，提高代码可读性。")
        suggestions.append("实现更健壮的错误处理和降级机制，提高代码稳定性。")
        
        return suggestions


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='生成综合质量报告')
    parser.add_argument('--syntax', default='test_results/tutorial_test_latest.json', help='语法检查结果文件')
    parser.add_argument('--api', default='tutorials_validation_report.json', help='API测试结果文件')
    parser.add_argument('--performance', default='test_results/tutorial_test_latest.json', help='性能测试结果文件')
    parser.add_argument('--execution', default='tutorials_quality_report.json', help='执行结果文件')
    parser.add_argument('--output', default='tutorials_comprehensive_report.html', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建报告生成器实例
    generator = ReportGenerator(
        syntax_file=args.syntax,
        api_file=args.api,
        performance_file=args.performance,
        execution_file=args.execution
    )
    
    # 生成报告
    generator.generate_report(args.output)


if __name__ == "__main__":
    main()