#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
教程代码质量检查自动化工具

该脚本自动执行代码质量检查，包括：
- 代码格式化（使用black和isort）
- 静态代码分析（使用pylint和flake8）
- 文档字符串和注释完整性检查
- 生成综合质量报告

使用方法：
    python run_code_quality_checks.py [--all] [--fix] [--report FILE]

参数：
    --all: 检查所有教程文件（默认）
    --fix: 自动修复发现的问题（格式化代码）
    --report: 输出报告文件路径（默认：tutorials_quality_report.txt）
"""

import os
import sys
import argparse
import subprocess
import json
from datetime import datetime
import time
from typing import Dict, List, Any, Optional

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

# 定义检查工具列表
QUALITY_TOOLS = [
    {
        'name': '代码格式和质量检查',
        'script': 'code_quality_check.py',
        'description': '检查代码格式、静态分析和代码质量',
        'fix_flag': '--fix'
    },
    {
        'name': '文档字符串和注释检查',
        'script': 'docstring_checker.py',
        'description': '检查文档字符串和注释的完整性',
        'fix_flag': None  # 不支持自动修复
    },
    {
        'name': '语法错误检查',
        'script': 'fix_syntax_errors.py',
        'description': '检查和修复常见语法错误',
        'fix_flag': None  # 默认支持修复，使用--dry-run禁用
    }
]

# 定义代码风格配置
CODE_STYLE_CONFIG = {
    'line_length': 100,
    'indent_size': 4,
    'docstring_style': 'google',  # Google风格文档字符串
    'import_order': ['standard_library', 'third_party', 'first_party', 'local']
}

class CodeQualityManager:
    """代码质量管理器，用于自动化执行代码质量检查和修复"""
    
    def __init__(self, fix: bool = False, report_file: str = 'tutorials_quality_report.txt'):
        """初始化代码质量管理器
        
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
                'docstring': 0,
                'syntax': 0
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
        
        # 检查Python工具
        python_tools = ['black', 'isort', 'pylint', 'flake8']
        for tool in python_tools:
            try:
                # 尝试运行工具的帮助命令
                subprocess.run(
                    [sys.executable, '-m', tool, '--help'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False
                )
                available[tool] = True
                print(f"✓ {tool} 可用")
            except Exception:
                available[tool] = False
                print(f"✗ {tool} 不可用 - 请安装该工具")
        
        # 检查本地脚本工具
        script_tools = [tool['script'] for tool in QUALITY_TOOLS]
        for script in script_tools:
            if os.path.exists(script):
                available[script] = True
                print(f"✓ {script} 可用")
            else:
                available[script] = False
                print(f"✗ {script} 不可用 - 文件不存在")
        
        return available
    
    def run_quality_checks(self):
        """运行所有质量检查工具"""
        print(f"{BOLD}开始运行代码质量检查...{ENDC}")
        
        # 检查工具脚本是否存在
        missing_tools = [script for script, available in self.available_tools.items() 
                         if not available and script in [tool['script'] for tool in QUALITY_TOOLS]]
        
        if missing_tools:
            print(f"{RED}错误: 以下工具脚本不存在:{ENDC}")
            for script in missing_tools:
                print(f"  - {script}")
            print("请确保所有工具脚本在当前目录中")
            return
        
        # 运行各个工具
        tool_results = {}
        
        for tool in QUALITY_TOOLS:
            print(f"\n{BOLD}{BLUE}运行 {tool['name']}...{ENDC}")
            print(f"  {tool['description']}")
            
            # 构建命令
            cmd = [sys.executable, tool['script'], '--all']
            
            # 添加修复标志
            if self.fix and tool['fix_flag']:
                cmd.append(tool['fix_flag'])
            elif tool['script'] == 'fix_syntax_errors.py' and not self.fix:
                cmd.append('--dry-run')
            
            # 运行工具
            try:
                start_time = time.time()
                result = subprocess.run(cmd, check=False)
                duration = time.time() - start_time
                
                tool_results[tool['name']] = {
                    'success': result.returncode == 0,
                    'return_code': result.returncode,
                    'duration': duration
                }
                
                status = f"{GREEN}成功{ENDC}" if result.returncode == 0 else f"{RED}失败{ENDC}"
                print(f"  完成: {status} (耗时: {duration:.2f}秒)")
                
            except Exception as e:
                print(f"{RED}运行 {tool['script']} 时出错: {str(e)}{ENDC}")
                tool_results[tool['name']] = {
                    'success': False,
                    'error': str(e)
                }
        
        # 运行额外的代码风格检查
        print(f"\n{BOLD}{BLUE}运行额外的代码风格检查...{ENDC}")
        style_results = self._run_style_checks()
        
        # 生成综合报告
        self._generate_combined_report(tool_results, style_results)
        
        # 显示总结
        print(f"\n{BOLD}检查完成{ENDC}")
        for tool_name, result in tool_results.items():
            status = f"{GREEN}成功{ENDC}" if result.get('success', False) else f"{RED}失败{ENDC}"
            print(f"  - {tool_name}: {status}")
        
        print(f"\n综合报告已保存至: {self.report_file}")
    
    def _run_style_checks(self) -> Dict:
        """运行额外的代码风格检查
        
        Returns:
            Dict: 检查结果
        """
        results = {
            'files_checked': 0,
            'files_with_issues': 0,
            'total_issues': 0,
            'issues_by_file': {}
        }
        
        print("检查代码风格一致性...")
        
        for file_path in TUTORIAL_FILES:
            if not os.path.exists(file_path):
                continue
                
            results['files_checked'] += 1
            file_issues = []
            
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # 检查行长度
                long_lines = []
                for i, line in enumerate(lines):
                    if len(line.rstrip()) > CODE_STYLE_CONFIG['line_length']:
                        long_lines.append(i + 1)
                
                if long_lines:
                    file_issues.append({
                        'type': 'line_length',
                        'message': f'发现 {len(long_lines)} 行超过 {CODE_STYLE_CONFIG["line_length"]} 个字符',
                        'lines': long_lines[:5]  # 只显示前5个
                    })
                
                # 检查缩进一致性
                indent_issues = self._check_indentation(lines)
                if indent_issues:
                    file_issues.append({
                        'type': 'indentation',
                        'message': '缩进不一致',
                        'details': indent_issues
                    })
                
                # 检查空行规范
                empty_line_issues = self._check_empty_lines(lines)
                if empty_line_issues:
                    file_issues.append({
                        'type': 'empty_lines',
                        'message': '空行使用不规范',
                        'details': empty_line_issues
                    })
                
                # 检查命名规范
                naming_issues = self._check_naming_conventions(content)
                if naming_issues:
                    file_issues.append({
                        'type': 'naming',
                        'message': '命名不符合规范',
                        'details': naming_issues
                    })
                
                # 更新结果
                if file_issues:
                    results['files_with_issues'] += 1
                    results['total_issues'] += len(file_issues)
                    results['issues_by_file'][file_path] = file_issues
                    
                    print(f"  {YELLOW}文件 {file_path} 有 {len(file_issues)} 个风格问题{ENDC}")
                else:
                    print(f"  {GREEN}文件 {file_path} 风格检查通过{ENDC}")
                
            except Exception as e:
                print(f"  {RED}检查 {file_path} 时出错: {str(e)}{ENDC}")
        
        return results
    
    def _check_indentation(self, lines: List[str]) -> List[Dict]:
        """检查缩进一致性
        
        Args:
            lines: 文件内容行列表
            
        Returns:
            List[Dict]: 缩进问题列表
        """
        issues = []
        indent_sizes = set()
        
        for i, line in enumerate(lines):
            if line.strip() and line.startswith(' '):
                # 计算缩进大小
                indent = len(line) - len(line.lstrip(' '))
                if indent > 0 and indent % CODE_STYLE_CONFIG['indent_size'] != 0:
                    issues.append({
                        'line': i + 1,
                        'message': f'缩进大小 ({indent}) 不是 {CODE_STYLE_CONFIG["indent_size"]} 的倍数'
                    })
        
        return issues
    
    def _check_empty_lines(self, lines: List[str]) -> List[Dict]:
        """检查空行使用规范
        
        Args:
            lines: 文件内容行列表
            
        Returns:
            List[Dict]: 空行问题列表
        """
        issues = []
        
        # 检查连续的空行
        consecutive_empty = 0
        for i, line in enumerate(lines):
            if not line.strip():
                consecutive_empty += 1
                if consecutive_empty > 2:
                    issues.append({
                        'line': i + 1,
                        'message': '连续空行超过2行'
                    })
            else:
                consecutive_empty = 0
        
        # 检查函数和类定义前后的空行
        for i, line in enumerate(lines):
            if i > 0 and i < len(lines) - 1:
                if line.strip().startswith('def ') or line.strip().startswith('class '):
                    # 检查函数/类定义前的空行
                    if lines[i-1].strip():
                        issues.append({
                            'line': i + 1,
                            'message': f'{"类" if "class" in line else "函数"}定义前应有空行'
                        })
        
        return issues
    
    def _check_naming_conventions(self, content: str) -> List[Dict]:
        """检查命名规范
        
        Args:
            content: 文件内容
            
        Returns:
            List[Dict]: 命名问题列表
        """
        import re
        issues = []
        
        # 检查变量命名（使用snake_case）
        variable_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*='
        for match in re.finditer(variable_pattern, content):
            var_name = match.group(1)
            # 跳过常量
            if var_name.isupper():
                continue
            # 检查是否使用驼峰命名
            if any(c.isupper() for c in var_name):
                issues.append({
                    'name': var_name,
                    'message': f'变量名 "{var_name}" 应使用snake_case而非驼峰命名'
                })
        
        # 检查类命名（使用PascalCase）
        class_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            if not class_name[0].isupper():
                issues.append({
                    'name': class_name,
                    'message': f'类名 "{class_name}" 应使用PascalCase（首字母大写）'
                })
        
        return issues
    
    def _generate_combined_report(self, tool_results: Dict, style_results: Dict):
        """生成综合报告
        
        Args:
            tool_results: 工具运行结果
            style_results: 代码风格检查结果
        """
        # 读取各工具生成的报告
        reports = {}
        
        # 尝试读取代码质量报告
        quality_report_file = 'tutorials_quality_report.txt'
        if os.path.exists(quality_report_file):
            with open(quality_report_file, 'r', encoding='utf-8') as f:
                reports['code_quality'] = f.read()
        
        # 尝试读取文档字符串报告
        docstring_report_file = 'docstring_report.txt'
        if os.path.exists(docstring_report_file):
            with open(docstring_report_file, 'r', encoding='utf-8') as f:
                reports['docstring'] = f.read()
        
        # 生成综合报告
        with open(self.report_file, 'w', encoding='utf-8') as f:
            f.write("教程代码质量综合报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("检查工具运行结果:\n")
            for tool_name, result in tool_results.items():
                status = "成功" if result.get('success', False) else "失败"
                duration = result.get('duration', 0)
                f.write(f"  - {tool_name}: {status} (耗时: {duration:.2f}秒)\n")
                if 'error' in result:
                    f.write(f"    错误: {result['error']}\n")
            
            f.write("\n代码风格检查结果:\n")
            f.write(f"  检查文件数: {style_results['files_checked']}\n")
            f.write(f"  有问题的文件数: {style_results['files_with_issues']}\n")
            f.write(f"  总问题数: {style_results['total_issues']}\n\n")
            
            if style_results['issues_by_file']:
                f.write("文件详细问题:\n")
                for file_path, issues in style_results['issues_by_file'].items():
                    f.write(f"  {file_path}:\n")
                    for issue in issues:
                        f.write(f"    - {issue['message']}\n")
                        if 'details' in issue and issue['details']:
                            for detail in issue['details'][:3]:  # 只显示前3个详情
                                f.write(f"      • {detail.get('message', '')}\n")
                        elif 'lines' in issue:
                            lines_str = ', '.join(str(line) for line in issue['lines'])
                            f.write(f"      • 问题行: {lines_str}\n")
                f.write("\n")
            
            f.write("\n" + "=" * 50 + "\n\n")
            
            # 添加各报告内容
            if 'code_quality' in reports:
                f.write("代码质量检查报告\n")
                f.write("-" * 50 + "\n\n")
                f.write(reports['code_quality'])
                f.write("\n\n")
            
            if 'docstring' in reports:
                f.write("文档字符串和注释检查报告\n")
                f.write("-" * 50 + "\n\n")
                f.write(reports['docstring'])
                f.write("\n\n")
            
            f.write("=" * 50 + "\n")
            f.write("总结和建议:\n\n")
            f.write("1. 代码格式和风格\n")
            f.write("   - 使用统一的代码格式和缩进风格（4空格缩进）\n")
            f.write("   - 遵循PEP 8命名约定（变量和函数使用snake_case，类使用PascalCase）\n")
            f.write("   - 保持一致的导入顺序（标准库 > 第三方库 > 本地模块）\n")
            f.write(f"   - 行长度不超过{CODE_STYLE_CONFIG['line_length']}个字符\n")
            f.write("   - 函数和类定义前后保留适当的空行\n\n")
            
            f.write("2. 文档和注释\n")
            f.write("   - 为所有模块、类和公共函数添加文档字符串\n")
            f.write(f"   - 使用{CODE_STYLE_CONFIG['docstring_style']}风格的文档字符串格式\n")
            f.write("   - 在文档字符串中包含参数和返回值的说明\n")
            f.write("   - 为复杂逻辑添加适当的注释\n")
            f.write("   - 保持注释与代码的同步更新\n\n")
            
            f.write("3. 代码质量\n")
            f.write("   - 避免重复代码，提取共用功能\n")
            f.write("   - 减少函数复杂度和长度\n")
            f.write("   - 使用统一的错误处理机制\n")
            f.write("   - 避免使用全局变量\n")
            f.write("   - 使用类型注解提高代码可读性\n\n")
            
            f.write("4. 持续改进\n")
            f.write("   - 定期运行代码质量检查\n")
            f.write("   - 在开发过程中应用代码审查\n")
            f.write("   - 持续更新和完善文档\n")
            f.write("   - 使用自动化工具保持代码质量\n")
            
            # 如果有工具不可用，添加安装建议
            missing_python_tools = [tool for tool in ['black', 'isort', 'pylint', 'flake8'] 
                                   if not self.available_tools.get(tool, False)]
            if missing_python_tools:
                f.write("\n\n缺少的工具:\n")
                f.write(f"以下工具不可用，建议安装以获得更好的代码质量检查:\n")
                for tool in missing_python_tools:
                    f.write(f"  - {tool}\n")
                f.write("\n安装命令:\n")
                f.write("  pip install black isort pylint flake8\n")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程代码质量检查自动化工具')
    parser.add_argument('--all', action='store_true', help='检查所有教程文件（默认）')
    parser.add_argument('--fix', action='store_true', help='自动修复发现的问题（格式化代码）')
    parser.add_argument('--report', default='tutorials_quality_report.txt', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建代码质量管理器实例
    manager = CodeQualityManager(fix=args.fix, report_file=args.report)
    
    # 运行质量检查
    manager.run_quality_checks()


if __name__ == "__main__":
    main()