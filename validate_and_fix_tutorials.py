#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
教程验证和修复脚本

该脚本用于验证教程文件并尝试修复常见问题。
支持以下功能：
- 验证教程文件的语法和API调用
- 修复常见的语法错误和API调用问题
- 生成验证和修复报告

使用方法：
    python validate_and_fix_tutorials.py [--fix] [--api-url URL] [--output FILE]

参数：
    --fix: 尝试修复发现的问题（默认：仅验证）
    --api-url: API服务URL（默认：http://localhost:8000）
    --output: 输出报告文件路径（默认：tutorials_validation_report.txt）
"""

import os
import sys
import re
import json
import time
import argparse
import ast
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import requests

# 导入验证模块
from validate_tutorials import TutorialValidator

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


class TutorialFixer:
    """教程修复器类，用于修复教程文件中的问题"""
    
    def __init__(self, validator: TutorialValidator):
        """初始化修复器
        
        Args:
            validator: 教程验证器实例
        """
        self.validator = validator
        self.results = {
            'fixes': {},
            'summary': {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'files_checked': len(TUTORIAL_FILES),
                'files_fixed': 0,
                'total_fixes': 0
            }
        }
    
    def validate_and_fix(self, fix_mode: bool = False) -> Dict:
        """验证并修复教程文件
        
        Args:
            fix_mode: 是否实际修复文件
            
        Returns:
            Dict: 修复结果
        """
        print(f"{BOLD}开始验证和{'修复' if fix_mode else '分析'}教程文件...{ENDC}")
        
        # 首先执行验证
        validation_results = self.validator.validate_all()
        
        # 根据验证结果尝试修复问题
        for file_path in TUTORIAL_FILES:
            file_name = os.path.basename(file_path)
            print(f"\n{BOLD}处理 {file_name}...{ENDC}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"  {RED}文件不存在，跳过{ENDC}")
                continue
            
            # 读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"  {RED}读取文件失败: {str(e)}{ENDC}")
                continue
            
            # 尝试修复问题
            fixed_content, fixes = self._fix_file_issues(file_path, content, validation_results)
            
            # 记录修复结果
            self.results['fixes'][file_path] = fixes
            
            if fixes['total_fixes'] > 0:
                self.results['summary']['files_fixed'] += 1
                self.results['summary']['total_fixes'] += fixes['total_fixes']
                
                print(f"  {GREEN}发现 {fixes['total_fixes']} 个问题可修复{ENDC}")
                
                # 如果是修复模式，写回文件
                if fix_mode and fixed_content != content:
                    try:
                        # 备份原文件
                        backup_path = f"{file_path}.bak"
                        with open(backup_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        # 写入修复后的内容
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(fixed_content)
                        
                        print(f"  {GREEN}已修复文件，原文件已备份为 {backup_path}{ENDC}")
                    except Exception as e:
                        print(f"  {RED}写入修复后的文件失败: {str(e)}{ENDC}")
                else:
                    print(f"  {YELLOW}仅分析模式，未修改文件{ENDC}")
            else:
                print(f"  {BLUE}未发现需要修复的问题{ENDC}")
        
        # 生成报告
        self._generate_report(fix_mode)
        
        return self.results
    
    def _fix_file_issues(self, file_path: str, content: str, validation_results: Dict) -> Tuple[str, Dict]:
        """修复文件中的问题
        
        Args:
            file_path: 文件路径
            content: 文件内容
            validation_results: 验证结果
            
        Returns:
            Tuple[str, Dict]: 修复后的内容和修复结果
        """
        fixes = {
            'syntax_fixes': 0,
            'api_call_fixes': 0,
            'import_fixes': 0,
            'other_fixes': 0,
            'total_fixes': 0,
            'details': []
        }
        
        fixed_content = content
        
        # 1. 修复 safe_api_call 递归调用错误
        fixed_content, count = self._fix_safe_api_call_recursion(fixed_content)
        if count > 0:
            fixes['syntax_fixes'] += count
            fixes['total_fixes'] += count
            fixes['details'].append(f"修复了 {count} 处 safe_api_call 递归调用")
        
        # 2. 修复字典语法错误
        fixed_content, count = self._fix_dict_syntax(fixed_content)
        if count > 0:
            fixes['syntax_fixes'] += count
            fixes['total_fixes'] += count
            fixes['details'].append(f"修复了 {count} 处字典语法错误")
        
        # 3. 修复参数传递问题
        fixed_content, count = self._fix_parameter_passing(fixed_content)
        if count > 0:
            fixes['api_call_fixes'] += count
            fixes['total_fixes'] += count
            fixes['details'].append(f"修复了 {count} 处参数传递问题")
        
        # 4. 修复导入语句
        fixed_content, count = self._fix_imports(fixed_content)
        if count > 0:
            fixes['import_fixes'] += count
            fixes['total_fixes'] += count
            fixes['details'].append(f"修复了 {count} 处导入语句")
        
        # 5. 修复变量名混用问题
        fixed_content, count = self._fix_variable_naming(fixed_content)
        if count > 0:
            fixes['other_fixes'] += count
            fixes['total_fixes'] += count
            fixes['details'].append(f"修复了 {count} 处变量名混用")
        
        return fixed_content, fixes
    
    def _fix_safe_api_call_recursion(self, content: str) -> Tuple[str, int]:
        """修复 safe_api_call 递归调用错误
        
        Args:
            content: 文件内容
            
        Returns:
            Tuple[str, int]: 修复后的内容和修复数量
        """
        # 查找模式: safe_api_call(api_client, safe_api_call, ...)
        pattern = r'safe_api_call\s*\(\s*api_client\s*,\s*safe_api_call\s*,'
        
        # 替换为: safe_api_call(api_client, api_client.method_name, ...)
        def replace_func(match):
            # 提取后面的参数
            text = content[match.end():]
            # 查找第一个逗号
            comma_pos = text.find(',')
            if comma_pos != -1:
                method_name = text[:comma_pos].strip()
                # 替换为正确的调用
                return f'safe_api_call(api_client, api_client.{method_name}'
            return match.group(0)
        
        # 计算匹配数量
        count = len(re.findall(pattern, content))
        
        # 执行替换
        fixed_content = re.sub(pattern, replace_func, content)
        
        return fixed_content, count
    
    def _fix_dict_syntax(self, content: str) -> Tuple[str, int]:
        """修复字典语法错误
        
        Args:
            content: 文件内容
            
        Returns:
            Tuple[str, int]: 修复后的内容和修复数量
        """
        # 查找模式: { param=value, ... }
        pattern = r'{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^,}]+)\s*,'
        
        # 替换为: { "param": value, ... }
        fixed_content = content
        count = 0
        
        for match in re.finditer(pattern, content):
            param_name = match.group(1)
            param_value = match.group(2)
            
            # 构建替换字符串
            replacement = f'{{ "{param_name}": {param_value},'
            
            # 执行替换
            fixed_content = fixed_content.replace(match.group(0), replacement)
            count += 1
        
        # 另一种模式: { param=value }
        pattern = r'{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^,}]+)\s*}'
        
        for match in re.finditer(pattern, content):
            param_name = match.group(1)
            param_value = match.group(2)
            
            # 构建替换字符串
            replacement = f'{{ "{param_name}": {param_value} }}'
            
            # 执行替换
            fixed_content = fixed_content.replace(match.group(0), replacement)
            count += 1
        
        return fixed_content, count
    
    def _fix_parameter_passing(self, content: str) -> Tuple[str, int]:
        """修复参数传递问题
        
        Args:
            content: 文件内容
            
        Returns:
            Tuple[str, int]: 修复后的内容和修复数量
        """
        # 查找模式: function_name(param=value, param2=value2)
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^,)]+)\s*\)'
        
        # 替换为: function_name(param=value)
        fixed_content = content
        count = 0
        
        # 这里我们只修复特定的函数调用，避免误修改
        target_functions = [
            'get_trading_dates', 'get_hist_kline', 'instrument_detail',
            'stock_list', 'latest_market', 'full_market'
        ]
        
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            
            # 只修复目标函数
            if func_name in target_functions or func_name.endswith(tuple(target_functions)):
                # 不修改，因为这种情况通常是正确的
                continue
            
            # 检查是否是 safe_api_call
            if func_name == 'safe_api_call':
                # 这里需要特殊处理，因为 safe_api_call 的参数格式不同
                # 暂时不修改，避免误修改
                continue
            
            # 其他情况，检查是否是错误的参数传递
            param_name = match.group(2)
            param_value = match.group(3)
            
            # 如果参数名是常见的错误模式，修复它
            if param_name in ['params', 'data', 'json'] and '=' not in param_value:
                # 构建替换字符串
                replacement = f'{func_name}({param_name}={param_value})'
                
                # 执行替换
                fixed_content = fixed_content.replace(match.group(0), replacement)
                count += 1
        
        return fixed_content, count
    
    def _fix_imports(self, content: str) -> Tuple[str, int]:
        """修复导入语句
        
        Args:
            content: 文件内容
            
        Returns:
            Tuple[str, int]: 修复后的内容和修复数量
        """
        # 查找重复的导入语句
        import_lines = []
        for line in content.split('\n'):
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(line)
        
        # 检查重复
        unique_imports = set()
        duplicate_imports = []
        
        for line in import_lines:
            if line in unique_imports:
                duplicate_imports.append(line)
            else:
                unique_imports.add(line)
        
        # 移除重复的导入
        fixed_content = content
        for dup in duplicate_imports:
            # 找到第二次及以后出现的位置
            pos = fixed_content.find(dup)
            if pos != -1:
                pos = fixed_content.find(dup, pos + 1)
                while pos != -1:
                    # 移除这一行
                    end_pos = fixed_content.find('\n', pos)
                    if end_pos == -1:
                        end_pos = len(fixed_content)
                    
                    fixed_content = fixed_content[:pos] + fixed_content[end_pos:]
                    pos = fixed_content.find(dup, pos)
        
        # 添加缺失的必要导入
        required_imports = [
            'from common.api_client import QMTAPIClient, create_api_client, safe_api_call',
            'from common.mock_data import MockDataGenerator',
            'from common.utils import print_section_header, print_subsection_header, print_api_result'
        ]
        
        count = len(duplicate_imports)
        
        for imp in required_imports:
            if imp not in fixed_content:
                # 找到导入块的结束位置
                import_block_end = 0
                for line in content.split('\n'):
                    if line.strip().startswith(('import ', 'from ')):
                        import_block_end = content.find(line) + len(line)
                
                # 在导入块后添加缺失的导入
                if import_block_end > 0:
                    fixed_content = fixed_content[:import_block_end] + '\n' + imp + fixed_content[import_block_end:]
                    count += 1
        
        return fixed_content, count
    
    def _fix_variable_naming(self, content: str) -> Tuple[str, int]:
        """修复变量名混用问题
        
        Args:
            content: 文件内容
            
        Returns:
            Tuple[str, int]: 修复后的内容和修复数量
        """
        # 常见的变量名混用模式
        variable_pairs = [
            ('api_data', 'data'),
            ('result', 'response'),
            ('symbol', 'stock_code')
        ]
        
        fixed_content = content
        count = 0
        
        for var1, var2 in variable_pairs:
            # 检查是否存在混用
            if var1 in content and var2 in content:
                # 分析哪个变量使用更多
                count1 = content.count(var1)
                count2 = content.count(var2)
                
                # 使用更频繁的变量名替换较少使用的
                if count1 > count2:
                    # 替换 var2 为 var1
                    pattern = r'\b' + var2 + r'\b'
                    fixed_content = re.sub(pattern, var1, fixed_content)
                    count += 1
                elif count2 > count1:
                    # 替换 var1 为 var2
                    pattern = r'\b' + var1 + r'\b'
                    fixed_content = re.sub(pattern, var2, fixed_content)
                    count += 1
        
        return fixed_content, count
    
    def _generate_report(self, fix_mode: bool):
        """生成修复报告
        
        Args:
            fix_mode: 是否实际修复文件
        """
        # 保存为JSON文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        mode = "fix" if fix_mode else "analyze"
        result_file = f"tutorials_{mode}_report_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        # 创建最新结果的链接
        latest_file = f"tutorials_{mode}_report.json"
        if os.path.exists(latest_file):
            os.remove(latest_file)
        
        # 在Windows上使用复制而不是符号链接
        import shutil
        shutil.copy2(result_file, latest_file)
        
        # 生成文本报告
        text_report = f"tutorials_{mode}_report.txt"
        self._generate_text_report(text_report, fix_mode)
        
        print(f"\n{BOLD}{'修复' if fix_mode else '分析'}报告已生成:{ENDC}")
        print(f"  JSON报告: {result_file}")
        print(f"  文本报告: {text_report}")
    
    def _generate_text_report(self, report_file: str, fix_mode: bool):
        """生成文本报告
        
        Args:
            report_file: 报告文件路径
            fix_mode: 是否实际修复文件
        """
        summary = self.results['summary']
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"教程{'修复' if fix_mode else '分析'}报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"时间: {summary['timestamp']}\n")
            f.write(f"模式: {'修复' if fix_mode else '仅分析'}\n\n")
            
            f.write("摘要:\n")
            f.write(f"  检查文件数: {summary['files_checked']}\n")
            f.write(f"  {'修复' if fix_mode else '可修复'}文件数: {summary['files_fixed']}\n")
            f.write(f"  总{'修复' if fix_mode else '可修复'}问题数: {summary['total_fixes']}\n\n")
            
            f.write("详细结果:\n")
            for file_path, fixes in self.results['fixes'].items():
                file_name = os.path.basename(file_path)
                
                if fixes['total_fixes'] > 0:
                    f.write(f"\n  {file_name}:\n")
                    f.write(f"    语法修复: {fixes['syntax_fixes']}\n")
                    f.write(f"    API调用修复: {fixes['api_call_fixes']}\n")
                    f.write(f"    导入修复: {fixes['import_fixes']}\n")
                    f.write(f"    其他修复: {fixes['other_fixes']}\n")
                    
                    if 'details' in fixes and fixes['details']:
                        f.write("    详细信息:\n")
                        for detail in fixes['details']:
                            f.write(f"      - {detail}\n")
                else:
                    f.write(f"\n  {file_name}: 未发现需要修复的问题\n")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程验证和修复脚本')
    parser.add_argument('--fix', action='store_true', help='尝试修复发现的问题')
    parser.add_argument('--api-url', default='http://localhost:8000', help='API服务URL')
    parser.add_argument('--output', default='tutorials_validation_report.txt', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建验证器实例
    validator = TutorialValidator(api_url=args.api_url)
    
    # 创建修复器实例
    fixer = TutorialFixer(validator)
    
    # 执行验证和修复
    fixer.validate_and_fix(fix_mode=args.fix)


if __name__ == "__main__":
    main()