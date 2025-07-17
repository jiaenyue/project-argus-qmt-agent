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
修复教程文件语法错误

该脚本用于修复教程文件中的常见语法错误。
支持以下功能：
- 修复 safe_api_call 递归调用错误
- 修复字典语法错误
- 修复参数传递问题
- 修复导入语句
- 修复变量名混用问题

使用方法：
    python fix_syntax_errors.py [--file FILE] [--all] [--dry-run]

参数：
    --file: 要修复的教程文件路径
    --all: 修复所有教程文件
    --dry-run: 仅显示将要进行的修复，不实际修改文件
"""

import os
import sys
import re
import argparse
from typing import Dict, List, Tuple

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


class SyntaxFixer:
    """语法修复器类，用于修复教程文件中的语法错误"""
    
    def __init__(self, dry_run: bool = False):
        """初始化语法修复器
        
        Args:
            dry_run: 是否仅显示将要进行的修复，不实际修改文件
        """
        self.dry_run = dry_run
        self.results = {
            'files_checked': 0,
            'files_fixed': 0,
            'total_fixes': 0,
            'fixes_by_type': {
                'safe_api_call': 0,
                'dict_syntax': 0,
                'parameter_passing': 0,
                'imports': 0,
                'variable_naming': 0
            },
            'file_results': {}
        }
    
    def fix_file(self, file_path: str) -> Dict:
        """修复单个文件的语法错误
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict: 修复结果
        """
        print(f"{BOLD}检查文件: {file_path}{ENDC}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"  {RED}文件不存在{ENDC}")
            return {'success': False, 'error': '文件不存在'}
        
        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  {RED}读取文件失败: {str(e)}{ENDC}")
            return {'success': False, 'error': f'读取文件失败: {str(e)}'}
        
        # 修复语法错误
        fixed_content = content
        fixes = []
        
        # 1. 修复 safe_api_call 递归调用错误
        fixed_content, count = self._fix_safe_api_call_recursion(fixed_content)
        if count > 0:
            fixes.append(f"修复了 {count} 处 safe_api_call 递归调用")
            self.results['fixes_by_type']['safe_api_call'] += count
            self.results['total_fixes'] += count
        
        # 2. 修复字典语法错误
        fixed_content, count = self._fix_dict_syntax(fixed_content)
        if count > 0:
            fixes.append(f"修复了 {count} 处字典语法错误")
            self.results['fixes_by_type']['dict_syntax'] += count
            self.results['total_fixes'] += count
        
        # 3. 修复参数传递问题
        fixed_content, count = self._fix_parameter_passing(fixed_content)
        if count > 0:
            fixes.append(f"修复了 {count} 处参数传递问题")
            self.results['fixes_by_type']['parameter_passing'] += count
            self.results['total_fixes'] += count
        
        # 4. 修复导入语句
        fixed_content, count = self._fix_imports(fixed_content)
        if count > 0:
            fixes.append(f"修复了 {count} 处导入语句")
            self.results['fixes_by_type']['imports'] += count
            self.results['total_fixes'] += count
        
        # 5. 修复变量名混用问题
        fixed_content, count = self._fix_variable_naming(fixed_content)
        if count > 0:
            fixes.append(f"修复了 {count} 处变量名混用")
            self.results['fixes_by_type']['variable_naming'] += count
            self.results['total_fixes'] += count
        
        # 更新结果统计
        self.results['files_checked'] += 1
        
        # 如果有修复，写回文件
        if fixed_content != content:
            self.results['files_fixed'] += 1
            
            if not self.dry_run:
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
                    return {'success': False, 'error': f'写入文件失败: {str(e)}'}
            else:
                print(f"  {YELLOW}[仅显示] 文件需要修复{ENDC}")
        else:
            print(f"  {BLUE}文件无需修复{ENDC}")
        
        # 显示修复详情
        for fix in fixes:
            print(f"  - {fix}")
        
        # 记录文件结果
        file_result = {
            'success': True,
            'fixes': fixes,
            'fix_count': len(fixes)
        }
        self.results['file_results'][file_path] = file_result
        
        return file_result
    
    def fix_all_files(self) -> Dict:
        """修复所有教程文件的语法错误
        
        Returns:
            Dict: 修复结果
        """
        print(f"{BOLD}开始修复所有教程文件...{ENDC}")
        
        for file_path in TUTORIAL_FILES:
            self.fix_file(file_path)
        
        # 显示总结
        print(f"\n{BOLD}修复总结:{ENDC}")
        print(f"  检查文件数: {self.results['files_checked']}")
        print(f"  {'需要修复' if self.dry_run else '已修复'}文件数: {self.results['files_fixed']}")
        print(f"  总{'需要修复' if self.dry_run else '已修复'}问题数: {self.results['total_fixes']}")
        print(f"  修复类型:")
        print(f"    - safe_api_call 递归调用: {self.results['fixes_by_type']['safe_api_call']}")
        print(f"    - 字典语法错误: {self.results['fixes_by_type']['dict_syntax']}")
        print(f"    - 参数传递问题: {self.results['fixes_by_type']['parameter_passing']}")
        print(f"    - 导入语句: {self.results['fixes_by_type']['imports']}")
        print(f"    - 变量名混用: {self.results['fixes_by_type']['variable_naming']}")
        
        return self.results
    
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


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='修复教程文件语法错误')
    parser.add_argument('--file', help='要修复的教程文件路径')
    parser.add_argument('--all', action='store_true', help='修复所有教程文件')
    parser.add_argument('--dry-run', action='store_true', help='仅显示将要进行的修复，不实际修改文件')
    
    args = parser.parse_args()
    
    # 创建语法修复器实例
    fixer = SyntaxFixer(dry_run=args.dry_run)
    
    # 根据参数执行修复
    if args.file:
        # 修复单个文件
        fixer.fix_file(args.file)
    elif args.all:
        # 修复所有文件
        fixer.fix_all_files()
    else:
        # 提示用户选择文件
        print(f"{BOLD}可用的教程文件:{ENDC}")
        for i, file_path in enumerate(TUTORIAL_FILES):
            print(f"  {i+1}. {file_path}")
        print(f"  {len(TUTORIAL_FILES)+1}. 所有文件")
        
        try:
            choice = input(f"\n请选择要修复的文件 (1-{len(TUTORIAL_FILES)+1})，或按Enter退出: ")
            if choice.strip():
                index = int(choice) - 1
                if 0 <= index < len(TUTORIAL_FILES):
                    fixer.fix_file(TUTORIAL_FILES[index])
                elif index == len(TUTORIAL_FILES):
                    fixer.fix_all_files()
                else:
                    print(f"{RED}无效的选择{ENDC}")
        except ValueError:
            print(f"{RED}无效的输入{ENDC}")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}操作已取消{ENDC}")


if __name__ == "__main__":
    main()