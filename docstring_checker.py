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
教程文档字符串和注释检查工具

该脚本专门用于检查教程文件中的文档字符串和注释的完整性。
支持以下功能：
- 检查模块级文档字符串
- 检查类和函数的文档字符串
- 检查参数和返回值文档
- 检查注释密度和质量
- 生成详细的文档完整性报告

使用方法：
    python docstring_checker.py [--file FILE] [--all] [--report FILE]

参数：
    --file: 要检查的教程文件路径
    --all: 检查所有教程文件
    --report: 输出报告文件路径（默认：docstring_report.txt）
"""

import os
import sys
import ast
import re
import argparse
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


class DocstringChecker:
    """文档字符串检查器类，用于检查教程文件中的文档字符串和注释"""
    
    def __init__(self, report_file: str = 'docstring_report.txt'):
        """初始化文档字符串检查器
        
        Args:
            report_file: 报告文件路径
        """
        self.report_file = report_file
        self.results = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'files_checked': 0,
            'files_with_issues': 0,
            'total_issues': 0,
            'issues_by_type': {
                'missing_module_docstring': 0,
                'missing_class_docstring': 0,
                'missing_function_docstring': 0,
                'incomplete_docstring': 0,
                'low_comment_ratio': 0
            },
            'file_results': {}
        }
    
    def check_file(self, file_path: str) -> Dict:
        """检查单个文件的文档字符串和注释
        
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
            'issues': [],
            'stats': {
                'total_lines': 0,
                'code_lines': 0,
                'comment_lines': 0,
                'docstring_lines': 0,
                'classes': 0,
                'functions': 0,
                'documented_classes': 0,
                'documented_functions': 0
            }
        }
        
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 计算基本统计信息
            file_result['stats']['total_lines'] = len(content.split('\n'))
            
            # 解析语法树
            tree = ast.parse(content)
            
            # 检查模块级文档字符串
            module_docstring = ast.get_docstring(tree)
            if not module_docstring:
                file_result['issues'].append({
                    'type': 'missing_module_docstring',
                    'message': '缺少模块级文档字符串',
                    'line': 1,
                    'severity': 'high'
                })
                self.results['issues_by_type']['missing_module_docstring'] += 1
            else:
                file_result['stats']['docstring_lines'] += len(module_docstring.split('\n'))
            
            # 检查类和函数
            self._check_node_docstrings(tree, file_result)
            
            # 检查注释密度和质量
            self._check_comments(content, file_result)
            
            # 更新统计信息
            file_result['total_issues'] = len(file_result['issues'])
            
            # 更新总结果
            self.results['files_checked'] += 1
            if file_result['total_issues'] > 0:
                self.results['files_with_issues'] += 1
                self.results['total_issues'] += file_result['total_issues']
            
            # 显示结果摘要
            if file_result['total_issues'] > 0:
                print(f"  {YELLOW}发现 {file_result['total_issues']} 个文档问题:{ENDC}")
                
                # 按类型统计问题
                issue_types = {}
                for issue in file_result['issues']:
                    issue_type = issue['type']
                    if issue_type not in issue_types:
                        issue_types[issue_type] = 0
                    issue_types[issue_type] += 1
                
                # 显示问题类型统计
                for issue_type, count in issue_types.items():
                    print(f"    - {issue_type}: {count}")
                
                # 显示文档覆盖率
                self._print_coverage(file_result['stats'])
            else:
                print(f"  {GREEN}未发现文档问题{ENDC}")
                # 显示文档覆盖率
                self._print_coverage(file_result['stats'])
        
        except Exception as e:
            print(f"  {RED}检查文件时出错: {str(e)}{ENDC}")
            file_result['error'] = str(e)
        
        # 保存文件结果
        self.results['file_results'][file_path] = file_result
        
        return file_result
    
    def check_all_files(self) -> Dict:
        """检查所有教程文件的文档字符串和注释
        
        Returns:
            Dict: 检查结果
        """
        print(f"{BOLD}开始检查所有教程文件的文档字符串和注释...{ENDC}")
        
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
        print(f"    - 缺少模块文档字符串: {self.results['issues_by_type']['missing_module_docstring']}")
        print(f"    - 缺少类文档字符串: {self.results['issues_by_type']['missing_class_docstring']}")
        print(f"    - 缺少函数文档字符串: {self.results['issues_by_type']['missing_function_docstring']}")
        print(f"    - 不完整的文档字符串: {self.results['issues_by_type']['incomplete_docstring']}")
        print(f"    - 注释密度过低: {self.results['issues_by_type']['low_comment_ratio']}")
        
        print(f"\n详细报告已保存至: {self.report_file}")
        
        return self.results
    
    def _check_node_docstrings(self, node: ast.AST, file_result: Dict):
        """递归检查节点的文档字符串
        
        Args:
            node: AST节点
            file_result: 文件结果字典
        """
        # 检查类定义
        if isinstance(node, ast.ClassDef):
            file_result['stats']['classes'] += 1
            
            # 获取类文档字符串
            class_docstring = ast.get_docstring(node)
            if not class_docstring:
                file_result['issues'].append({
                    'type': 'missing_class_docstring',
                    'message': f'类 {node.name} 缺少文档字符串',
                    'line': node.lineno,
                    'severity': 'medium'
                })
                self.results['issues_by_type']['missing_class_docstring'] += 1
            else:
                file_result['stats']['documented_classes'] += 1
                file_result['stats']['docstring_lines'] += len(class_docstring.split('\n'))
                
                # 检查文档字符串完整性
                if not self._check_docstring_completeness(class_docstring, 'class'):
                    file_result['issues'].append({
                        'type': 'incomplete_docstring',
                        'message': f'类 {node.name} 的文档字符串不完整',
                        'line': node.lineno,
                        'severity': 'low'
                    })
                    self.results['issues_by_type']['incomplete_docstring'] += 1
        
        # 检查函数定义
        elif isinstance(node, ast.FunctionDef):
            # 跳过私有方法，但包括__init__
            if not node.name.startswith('_') or node.name == '__init__':
                file_result['stats']['functions'] += 1
                
                # 获取函数文档字符串
                func_docstring = ast.get_docstring(node)
                if not func_docstring:
                    file_result['issues'].append({
                        'type': 'missing_function_docstring',
                        'message': f'函数 {node.name} 缺少文档字符串',
                        'line': node.lineno,
                        'severity': 'medium'
                    })
                    self.results['issues_by_type']['missing_function_docstring'] += 1
                else:
                    file_result['stats']['documented_functions'] += 1
                    file_result['stats']['docstring_lines'] += len(func_docstring.split('\n'))
                    
                    # 检查文档字符串完整性
                    if not self._check_docstring_completeness(func_docstring, 'function', node):
                        file_result['issues'].append({
                            'type': 'incomplete_docstring',
                            'message': f'函数 {node.name} 的文档字符串不完整',
                            'line': node.lineno,
                            'severity': 'low'
                        })
                        self.results['issues_by_type']['incomplete_docstring'] += 1
        
        # 递归检查子节点
        for child in ast.iter_child_nodes(node):
            self._check_node_docstrings(child, file_result)
    
    def _check_docstring_completeness(self, docstring: str, node_type: str, node: Optional[ast.AST] = None) -> bool:
        """检查文档字符串的完整性
        
        Args:
            docstring: 文档字符串
            node_type: 节点类型 ('class' 或 'function')
            node: AST节点（可选，用于函数参数检查）
            
        Returns:
            bool: 文档字符串是否完整
        """
        # 基本检查：文档字符串不应该太短
        if len(docstring.strip()) < 10:
            return False
        
        # 对于函数，检查是否包含参数和返回值文档
        if node_type == 'function' and node:
            # 获取函数参数
            arg_names = [arg.arg for arg in node.args.args if arg.arg != 'self']
            
            # 检查参数文档
            if arg_names:
                # 检查是否有Args部分
                if 'Args:' not in docstring and '参数:' not in docstring:
                    return False
                
                # 检查是否记录了所有参数
                for arg_name in arg_names:
                    if arg_name not in docstring:
                        return False
            
            # 检查返回值文档（如果函数有返回语句）
            has_return = False
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value is not None:
                    has_return = True
                    break
            
            if has_return:
                if 'Returns:' not in docstring and '返回:' not in docstring and '返回值:' not in docstring:
                    return False
        
        # 对于类，检查是否包含类描述
        if node_type == 'class':
            # 类文档字符串应该包含多行
            if len(docstring.strip().split('\n')) < 2:
                return False
        
        return True
    
    def _check_comments(self, content: str, file_result: Dict):
        """检查注释密度和质量
        
        Args:
            content: 文件内容
            file_result: 文件结果字典
        """
        lines = content.split('\n')
        code_lines = 0
        comment_lines = 0
        
        # 统计代码行和注释行
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('#'):
                comment_lines += 1
            else:
                code_lines += 1
                # 检查行内注释
                if '#' in line:
                    comment_lines += 1
        
        # 更新统计信息
        file_result['stats']['code_lines'] = code_lines
        file_result['stats']['comment_lines'] = comment_lines
        
        # 计算注释密度
        if code_lines > 0:
            comment_ratio = comment_lines / code_lines
            
            # 如果注释密度过低，添加问题
            if comment_ratio < 0.1 and code_lines > 50:  # 对于较大的文件，注释应该更多
                file_result['issues'].append({
                    'type': 'low_comment_ratio',
                    'message': f'注释密度过低 ({comment_ratio:.1%})',
                    'details': f'代码行: {code_lines}, 注释行: {comment_lines}',
                    'severity': 'low'
                })
                self.results['issues_by_type']['low_comment_ratio'] += 1
    
    def _print_coverage(self, stats: Dict):
        """打印文档覆盖率
        
        Args:
            stats: 统计信息
        """
        # 计算类文档覆盖率
        class_coverage = 0
        if stats['classes'] > 0:
            class_coverage = stats['documented_classes'] / stats['classes'] * 100
        
        # 计算函数文档覆盖率
        function_coverage = 0
        if stats['functions'] > 0:
            function_coverage = stats['documented_functions'] / stats['functions'] * 100
        
        # 计算总体文档覆盖率
        total_items = stats['classes'] + stats['functions']
        documented_items = stats['documented_classes'] + stats['documented_functions']
        total_coverage = 0
        if total_items > 0:
            total_coverage = documented_items / total_items * 100
        
        # 打印覆盖率
        print(f"  {BLUE}文档覆盖率:{ENDC}")
        print(f"    - 类: {stats['documented_classes']}/{stats['classes']} ({class_coverage:.1f}%)")
        print(f"    - 函数: {stats['documented_functions']}/{stats['functions']} ({function_coverage:.1f}%)")
        print(f"    - 总体: {documented_items}/{total_items} ({total_coverage:.1f}%)")
    
    def _generate_report(self):
        """生成检查报告"""
        with open(self.report_file, 'w', encoding='utf-8') as f:
            f.write("教程文档字符串和注释检查报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"检查时间: {self.results['timestamp']}\n")
            f.write(f"检查文件数: {self.results['files_checked']}\n")
            f.write(f"有问题的文件数: {self.results['files_with_issues']}\n")
            f.write(f"总问题数: {self.results['total_issues']}\n\n")
            
            f.write("问题类型统计:\n")
            f.write(f"  - 缺少模块文档字符串: {self.results['issues_by_type']['missing_module_docstring']}\n")
            f.write(f"  - 缺少类文档字符串: {self.results['issues_by_type']['missing_class_docstring']}\n")
            f.write(f"  - 缺少函数文档字符串: {self.results['issues_by_type']['missing_function_docstring']}\n")
            f.write(f"  - 不完整的文档字符串: {self.results['issues_by_type']['incomplete_docstring']}\n")
            f.write(f"  - 注释密度过低: {self.results['issues_by_type']['low_comment_ratio']}\n\n")
            
            f.write("文件详细报告:\n")
            for file_path, result in self.results['file_results'].items():
                f.write(f"\n{'-' * 50}\n")
                f.write(f"文件: {file_path}\n")
                
                if 'error' in result:
                    f.write(f"检查错误: {result['error']}\n")
                    continue
                
                # 写入统计信息
                stats = result['stats']
                f.write(f"统计信息:\n")
                f.write(f"  - 总行数: {stats['total_lines']}\n")
                f.write(f"  - 代码行数: {stats['code_lines']}\n")
                f.write(f"  - 注释行数: {stats['comment_lines']}\n")
                f.write(f"  - 文档字符串行数: {stats['docstring_lines']}\n")
                f.write(f"  - 类数量: {stats['classes']}\n")
                f.write(f"  - 函数数量: {stats['functions']}\n")
                f.write(f"  - 有文档的类: {stats['documented_classes']}\n")
                f.write(f"  - 有文档的函数: {stats['documented_functions']}\n")
                
                # 计算覆盖率
                class_coverage = 0
                if stats['classes'] > 0:
                    class_coverage = stats['documented_classes'] / stats['classes'] * 100
                
                function_coverage = 0
                if stats['functions'] > 0:
                    function_coverage = stats['documented_functions'] / stats['functions'] * 100
                
                total_items = stats['classes'] + stats['functions']
                documented_items = stats['documented_classes'] + stats['documented_functions']
                total_coverage = 0
                if total_items > 0:
                    total_coverage = documented_items / total_items * 100
                
                f.write(f"文档覆盖率:\n")
                f.write(f"  - 类: {stats['documented_classes']}/{stats['classes']} ({class_coverage:.1f}%)\n")
                f.write(f"  - 函数: {stats['documented_functions']}/{stats['functions']} ({function_coverage:.1f}%)\n")
                f.write(f"  - 总体: {documented_items}/{total_items} ({total_coverage:.1f}%)\n\n")
                
                # 写入问题
                if result.get('issues'):
                    f.write(f"发现的问题 ({len(result['issues'])}):\n")
                    
                    # 按严重性排序
                    severity_order = {'high': 0, 'medium': 1, 'low': 2}
                    sorted_issues = sorted(
                        result['issues'],
                        key=lambda x: severity_order.get(x.get('severity', 'low'), 3)
                    )
                    
                    for issue in sorted_issues:
                        severity = issue.get('severity', 'low')
                        severity_mark = {
                            'high': '[!!!]',
                            'medium': '[!!]',
                            'low': '[!]'
                        }.get(severity, '[!]')
                        
                        f.write(f"  {severity_mark} {issue['message']}")
                        if 'line' in issue:
                            f.write(f" (行 {issue['line']})")
                        f.write("\n")
                        
                        if 'details' in issue:
                            f.write(f"    {issue['details']}\n")
                else:
                    f.write("未发现问题\n")
            
            f.write("\n" + "=" * 50 + "\n")
            f.write("建议:\n")
            f.write("1. 为所有模块、类和公共函数添加文档字符串\n")
            f.write("2. 在文档字符串中包含参数和返回值的说明\n")
            f.write("3. 增加适当的注释，特别是对于复杂的逻辑\n")
            f.write("4. 使用统一的文档字符串格式（推荐Google风格或NumPy风格）\n")
            f.write("5. 文档字符串应该清晰描述功能，而不仅仅是重复函数名\n")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程文档字符串和注释检查工具')
    parser.add_argument('--file', help='要检查的教程文件路径')
    parser.add_argument('--all', action='store_true', help='检查所有教程文件')
    parser.add_argument('--report', default='docstring_report.txt', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建文档字符串检查器实例
    checker = DocstringChecker(report_file=args.report)
    
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