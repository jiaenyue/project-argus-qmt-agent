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
教程代码质量检查工具

该脚本用于检查教程文件的代码质量，包括：
- 代码格式化（使用black和isort）
- 静态代码分析（使用pylint和flake8）
- 文档字符串和注释完整性检查

使用方法：
    python code_quality_check.py [--file FILE] [--all] [--fix] [--report FILE]

参数：
    --file: 要检查的教程文件路径
    --all: 检查所有教程文件
    --fix: 自动修复发现的问题（格式化代码）
    --report: 输出报告文件路径（默认：tutorials_quality_report.txt）
"""

import os
import sys
import re
import ast
import argparse
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

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

# 定义工具命令
TOOLS = {
    'black': ['black', '--line-length=100'],
    'isort': ['isort', '--profile=black'],
    'pylint': ['pylint', '--disable=C0111,C0103,C0303,W0621,R0914,R0915,R0912,R0913,R0801'],
    'flake8': ['flake8', '--max-line-length=100', '--ignore=E203,W503,E501']
}


class CodeQualityChecker:
    """代码质量检查器类，用于检查教程文件的代码质量"""
    
    def __init__(self, fix: bool = False, report_file: str = 'tutorials_quality_report.txt'):
        """初始化代码质量检查器
        
        Args:
            fix: 是否自动修复发现的问题
            report_file: 报告文件路径
        """
        self.fix = fix
        self.report_file = report_file
        self.results = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'files_checked': 0,
            'files_with_issues': 0,
            'total_issues': 0,
            'issues_by_type': {
                'formatting': 0,
                'linting': 0,
                'docstring': 0
            },
            'file_results': {}
        }
        
        # 检查工具是否可用
        self.available_tools = self._check_tools()
    
    def _check_tools(self) -> Dict[str, bool]:
        """检查各种工具是否可用
        
        Returns:
            Dict[str, bool]: 工具可用性字典
        """
        available = {}
        
        for tool, command in TOOLS.items():
            try:
                # 尝试运行工具的帮助命令
                subprocess.run(
                    [command[0], '--help'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False
                )
                available[tool] = True
                print(f"✓ {tool} 可用")
            except FileNotFoundError:
                available[tool] = False
                print(f"✗ {tool} 不可用 - 请安装该工具")
        
        return available
    
    def check_file(self, file_path: str) -> Dict:
        """检查单个文件的代码质量
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict: 检查结果
        """
        print(f"{BOLD}检查文件: {file_path}{ENDC}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"  {RED}文件不存在{ENDC}")
            return {'success': False, 'error': '文件不存在'}
        
        # 初始化文件结果
        file_result = {
            'path': file_path,
            'formatting_issues': [],
            'linting_issues': [],
            'docstring_issues': [],
            'total_issues': 0
        }
        
        # 1. 检查代码格式
        formatting_issues = self._check_formatting(file_path)
        file_result['formatting_issues'] = formatting_issues
        
        # 2. 进行静态代码分析
        linting_issues = self._check_linting(file_path)
        file_result['linting_issues'] = linting_issues
        
        # 3. 检查文档字符串和注释
        docstring_issues = self._check_docstrings(file_path)
        file_result['docstring_issues'] = docstring_issues
        
        # 统计问题数量
        file_result['total_issues'] = (
            len(formatting_issues) + 
            len(linting_issues) + 
            len(docstring_issues)
        )
        
        # 更新总结果
        self.results['files_checked'] += 1
        if file_result['total_issues'] > 0:
            self.results['files_with_issues'] += 1
            self.results['total_issues'] += file_result['total_issues']
            self.results['issues_by_type']['formatting'] += len(formatting_issues)
            self.results['issues_by_type']['linting'] += len(linting_issues)
            self.results['issues_by_type']['docstring'] += len(docstring_issues)
        
        # 显示结果摘要
        if file_result['total_issues'] > 0:
            print(f"  {YELLOW}发现 {file_result['total_issues']} 个问题:{ENDC}")
            print(f"    - 格式问题: {len(formatting_issues)}")
            print(f"    - 代码质量问题: {len(linting_issues)}")
            print(f"    - 文档问题: {len(docstring_issues)}")
            
            # 如果需要修复，执行修复
            if self.fix:
                self._fix_issues(file_path)
        else:
            print(f"  {GREEN}未发现问题{ENDC}")
        
        # 保存文件结果
        self.results['file_results'][file_path] = file_result
        
        return file_result
    
    def check_all_files(self) -> Dict:
        """检查所有教程文件的代码质量
        
        Returns:
            Dict: 检查结果
        """
        print(f"{BOLD}开始检查所有教程文件...{ENDC}")
        
        for file_path in TUTORIAL_FILES:
            self.check_file(file_path)
        
        # 生成报告
        self._generate_report()
        
        # 显示总结
        print(f"\n{BOLD}检查总结:{ENDC}")
        print(f"  检查文件数: {self.results['files_checked']}")
        print(f"  有问题的文件数: {self.results['files_with_issues']}")
        print(f"  总问题数: {self.results['total_issues']}")
        print(f"  问题类型:")
        print(f"    - 格式问题: {self.results['issues_by_type']['formatting']}")
        print(f"    - 代码质量问题: {self.results['issues_by_type']['linting']}")
        print(f"    - 文档问题: {self.results['issues_by_type']['docstring']}")
        
        if self.fix:
            print(f"\n{GREEN}已尝试自动修复格式问题{ENDC}")
        
        print(f"\n详细报告已保存至: {self.report_file}")
        
        return self.results
    
    def _check_formatting(self, file_path: str) -> List[Dict]:
        """检查代码格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[Dict]: 格式问题列表
        """
        issues = []
        
        # 使用 black 检查格式
        if self.available_tools.get('black', False):
            try:
                # 使用 black 的检查模式
                cmd = TOOLS['black'] + ['--check', file_path]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # 如果返回码不是0，说明有格式问题
                if result.returncode != 0:
                    # 解析输出，提取问题
                    output = result.stdout + result.stderr
                    issues.append({
                        'tool': 'black',
                        'message': '代码格式不符合 black 标准',
                        'details': output.strip()
                    })
            except Exception as e:
                issues.append({
                    'tool': 'black',
                    'message': f'运行 black 时出错: {str(e)}',
                    'details': ''
                })
        
        # 使用 isort 检查导入顺序
        if self.available_tools.get('isort', False):
            try:
                # 使用 isort 的检查模式
                cmd = TOOLS['isort'] + ['--check-only', file_path]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # 如果返回码不是0，说明有导入顺序问题
                if result.returncode != 0:
                    # 解析输出，提取问题
                    output = result.stdout + result.stderr
                    issues.append({
                        'tool': 'isort',
                        'message': '导入顺序不符合标准',
                        'details': output.strip()
                    })
            except Exception as e:
                issues.append({
                    'tool': 'isort',
                    'message': f'运行 isort 时出错: {str(e)}',
                    'details': ''
                })
        
        return issues
    
    def _check_linting(self, file_path: str) -> List[Dict]:
        """进行静态代码分析
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[Dict]: 代码质量问题列表
        """
        issues = []
        
        # 使用 pylint 进行静态分析
        if self.available_tools.get('pylint', False):
            try:
                cmd = TOOLS['pylint'] + [file_path]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # pylint 输出解析
                output = result.stdout
                if output and 'Your code has been rated at' in output:
                    # 提取评分
                    match = re.search(r'Your code has been rated at ([\d\.]+)/10', output)
                    if match:
                        score = float(match.group(1))
                        if score < 7.0:  # 低于7分视为有问题
                            # 提取具体问题
                            problems = []
                            for line in output.split('\n'):
                                if re.match(r'^[A-Z]:\d+', line):
                                    problems.append(line)
                            
                            issues.append({
                                'tool': 'pylint',
                                'message': f'代码质量评分: {score}/10',
                                'details': '\n'.join(problems[:10])  # 只显示前10个问题
                            })
            except Exception as e:
                issues.append({
                    'tool': 'pylint',
                    'message': f'运行 pylint 时出错: {str(e)}',
                    'details': ''
                })
        
        # 使用 flake8 进行代码风格检查
        if self.available_tools.get('flake8', False):
            try:
                cmd = TOOLS['flake8'] + [file_path]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # flake8 输出解析
                output = result.stdout
                if output:
                    # 计算问题数量
                    problems = output.strip().split('\n')
                    if problems and problems[0]:  # 确保有实际问题
                        issues.append({
                            'tool': 'flake8',
                            'message': f'发现 {len(problems)} 个代码风格问题',
                            'details': '\n'.join(problems[:10])  # 只显示前10个问题
                        })
            except Exception as e:
                issues.append({
                    'tool': 'flake8',
                    'message': f'运行 flake8 时出错: {str(e)}',
                    'details': ''
                })
        
        # 如果外部工具都不可用，使用内置的简单检查
        if not self.available_tools.get('pylint', False) and not self.available_tools.get('flake8', False):
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 简单的代码质量检查
                problems = []
                
                # 检查行长度
                for i, line in enumerate(content.split('\n')):
                    if len(line) > 100:
                        problems.append(f"行 {i+1}: 行长度超过100个字符 ({len(line)})")
                
                # 检查空行
                if '\n\n\n' in content:
                    problems.append("存在连续多个空行")
                
                # 检查缩进一致性
                indent_sizes = set()
                for line in content.split('\n'):
                    if line.strip() and line.startswith(' '):
                        indent = len(line) - len(line.lstrip(' '))
                        if indent > 0:
                            indent_sizes.add(indent)
                
                if len(indent_sizes) > 1 and 2 in indent_sizes and 4 in indent_sizes:
                    problems.append("缩进不一致，同时存在2空格和4空格缩进")
                
                if problems:
                    issues.append({
                        'tool': 'internal',
                        'message': f'发现 {len(problems)} 个代码质量问题',
                        'details': '\n'.join(problems[:10])  # 只显示前10个问题
                    })
            except Exception as e:
                issues.append({
                    'tool': 'internal',
                    'message': f'进行内部代码质量检查时出错: {str(e)}',
                    'details': ''
                })
        
        return issues
    
    def _check_docstrings(self, file_path: str) -> List[Dict]:
        """检查文档字符串和注释
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[Dict]: 文档问题列表
        """
        issues = []
        
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析语法树
            tree = ast.parse(content)
            
            # 检查模块级文档字符串
            if not ast.get_docstring(tree):
                issues.append({
                    'type': 'missing_module_docstring',
                    'message': '缺少模块级文档字符串',
                    'line': 1
                })
            
            # 检查类和函数的文档字符串
            missing_docstrings = []
            
            for node in ast.walk(tree):
                # 检查类定义
                if isinstance(node, ast.ClassDef):
                    if not ast.get_docstring(node):
                        missing_docstrings.append({
                            'type': 'missing_class_docstring',
                            'message': f'类 {node.name} 缺少文档字符串',
                            'line': node.lineno
                        })
                
                # 检查函数定义
                elif isinstance(node, ast.FunctionDef):
                    # 跳过私有方法和特殊方法
                    if not node.name.startswith('_') or node.name == '__init__':
                        if not ast.get_docstring(node):
                            missing_docstrings.append({
                                'type': 'missing_function_docstring',
                                'message': f'函数 {node.name} 缺少文档字符串',
                                'line': node.lineno
                            })
            
            # 添加缺失的文档字符串问题
            if missing_docstrings:
                issues.append({
                    'type': 'missing_docstrings',
                    'message': f'发现 {len(missing_docstrings)} 个缺少文档字符串的定义',
                    'details': missing_docstrings[:10]  # 只显示前10个问题
                })
            
            # 检查注释密度
            code_lines = 0
            comment_lines = 0
            
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    code_lines += 1
                    if '#' in line:
                        comment_lines += 1
                elif line.startswith('#'):
                    comment_lines += 1
            
            if code_lines > 0:
                comment_ratio = comment_lines / code_lines
                if comment_ratio < 0.1:  # 注释少于10%
                    issues.append({
                        'type': 'low_comment_ratio',
                        'message': f'注释密度过低 ({comment_ratio:.1%})',
                        'details': f'代码行: {code_lines}, 注释行: {comment_lines}'
                    })
        
        except Exception as e:
            issues.append({
                'type': 'error',
                'message': f'检查文档字符串时出错: {str(e)}',
                'details': ''
            })
        
        return issues
    
    def _fix_issues(self, file_path: str) -> bool:
        """修复发现的问题
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功修复
        """
        success = True
        
        print(f"  {BLUE}尝试修复格式问题...{ENDC}")
        
        # 使用 isort 修复导入顺序
        if self.available_tools.get('isort', False):
            try:
                cmd = TOOLS['isort'] + [file_path]
                subprocess.run(cmd, check=False)
                print(f"    {GREEN}✓ isort 格式化完成{ENDC}")
            except Exception as e:
                print(f"    {RED}✗ isort 格式化失败: {str(e)}{ENDC}")
                success = False
        
        # 使用 black 修复代码格式
        if self.available_tools.get('black', False):
            try:
                cmd = TOOLS['black'] + [file_path]
                subprocess.run(cmd, check=False)
                print(f"    {GREEN}✓ black 格式化完成{ENDC}")
            except Exception as e:
                print(f"    {RED}✗ black 格式化失败: {str(e)}{ENDC}")
                success = False
        
        # 注意：我们不会自动修复文档字符串和代码质量问题，因为这需要人工干预
        if not self.available_tools.get('isort', False) and not self.available_tools.get('black', False):
            print(f"    {YELLOW}⚠ 没有可用的格式化工具{ENDC}")
            success = False
        
        return success
    
    def _generate_report(self):
        """生成检查报告"""
        with open(self.report_file, 'w', encoding='utf-8') as f:
            f.write("教程代码质量检查报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"检查时间: {self.results['timestamp']}\n")
            f.write(f"检查文件数: {self.results['files_checked']}\n")
            f.write(f"有问题的文件数: {self.results['files_with_issues']}\n")
            f.write(f"总问题数: {self.results['total_issues']}\n\n")
            
            f.write("问题类型统计:\n")
            f.write(f"  - 格式问题: {self.results['issues_by_type']['formatting']}\n")
            f.write(f"  - 代码质量问题: {self.results['issues_by_type']['linting']}\n")
            f.write(f"  - 文档问题: {self.results['issues_by_type']['docstring']}\n\n")
            
            f.write("文件详细报告:\n")
            for file_path, result in self.results['file_results'].items():
                f.write(f"\n{'-' * 50}\n")
                f.write(f"文件: {file_path}\n")
                f.write(f"总问题数: {result['total_issues']}\n\n")
                
                if result['formatting_issues']:
                    f.write("格式问题:\n")
                    for issue in result['formatting_issues']:
                        f.write(f"  - [{issue['tool']}] {issue['message']}\n")
                        if issue['details']:
                            for line in issue['details'].split('\n')[:5]:  # 只显示前5行详情
                                f.write(f"    {line}\n")
                    f.write("\n")
                
                if result['linting_issues']:
                    f.write("代码质量问题:\n")
                    for issue in result['linting_issues']:
                        f.write(f"  - [{issue['tool']}] {issue['message']}\n")
                        if issue.get('details'):
                            for line in str(issue['details']).split('\n')[:5]:  # 只显示前5行详情
                                f.write(f"    {line}\n")
                    f.write("\n")
                
                if result['docstring_issues']:
                    f.write("文档问题:\n")
                    for issue in result['docstring_issues']:
                        f.write(f"  - {issue['message']}\n")
                        if issue.get('details'):
                            if isinstance(issue['details'], list):
                                for detail in issue['details'][:5]:  # 只显示前5个详情
                                    f.write(f"    - {detail['message']} (行 {detail['line']})\n")
                            else:
                                f.write(f"    {issue['details']}\n")
                    f.write("\n")
            
            f.write("\n" + "=" * 50 + "\n")
            f.write("建议:\n")
            f.write("1. 使用 'black' 和 'isort' 工具格式化代码\n")
            f.write("2. 为所有类和公共函数添加文档字符串\n")
            f.write("3. 增加适当的注释，特别是对于复杂的逻辑\n")
            f.write("4. 使用 'pylint' 和 'flake8' 工具检查代码质量\n")
            
            # 如果有工具不可用，添加安装建议
            missing_tools = [tool for tool, available in self.available_tools.items() if not available]
            if missing_tools:
                f.write("\n缺少的工具:\n")
                f.write(f"以下工具不可用，建议安装以获得更好的代码质量检查:\n")
                for tool in missing_tools:
                    f.write(f"  - {tool}\n")
                f.write("\n安装命令:\n")
                f.write("  pip install black isort pylint flake8\n")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程代码质量检查工具')
    parser.add_argument('--file', help='要检查的教程文件路径')
    parser.add_argument('--all', action='store_true', help='检查所有教程文件')
    parser.add_argument('--fix', action='store_true', help='自动修复发现的问题（格式化代码）')
    parser.add_argument('--report', default='tutorials_quality_report.txt', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建代码质量检查器实例
    checker = CodeQualityChecker(fix=args.fix, report_file=args.report)
    
    # 根据参数执行检查
    if args.file:
        # 检查单个文件
        checker.check_file(args.file)
    elif args.all:
        # 检查所有文件
        checker.check_all_files()
    else:
        # 提示用户选择文件
        print(f"{BOLD}可用的教程文件:{ENDC}")
        for i, file_path in enumerate(TUTORIAL_FILES):
            print(f"  {i+1}. {file_path}")
        print(f"  {len(TUTORIAL_FILES)+1}. 所有文件")
        
        try:
            choice = input(f"\n请选择要检查的文件 (1-{len(TUTORIAL_FILES)+1})，或按Enter退出: ")
            if choice.strip():
                index = int(choice) - 1
                if 0 <= index < len(TUTORIAL_FILES):
                    checker.check_file(TUTORIAL_FILES[index])
                elif index == len(TUTORIAL_FILES):
                    checker.check_all_files()
                else:
                    print(f"{RED}无效的选择{ENDC}")
        except ValueError:
            print(f"{RED}无效的输入{ENDC}")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}操作已取消{ENDC}")


if __name__ == "__main__":
    main()