#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
教程代码质量验证工具

该脚本整合了多个代码质量检查工具，提供一站式的代码质量验证。
支持以下功能：
- 代码格式检查和修复
- 静态代码分析
- 文档字符串和注释检查
- 语法错误检查和修复
- 生成综合质量报告

使用方法：
    python run_validation.py [--file FILE] [--all] [--fix] [--report FILE]

参数：
    --file: 要检查的教程文件路径
    --all: 检查所有教程文件
    --fix: 自动修复发现的问题
    --report: 输出报告文件路径（默认：tutorials_quality_report.txt）
"""

import os
import sys
import argparse
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Any

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
VALIDATION_TOOLS = [
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


def run_validation(file_path: str = None, check_all: bool = False, fix: bool = False, report_file: str = 'tutorials_quality_report.txt'):
    """运行所有验证工具
    
    Args:
        file_path: 要检查的文件路径
        check_all: 是否检查所有文件
        fix: 是否自动修复问题
        report_file: 报告文件路径
    """
    print(f"{BOLD}开始运行代码质量验证...{ENDC}")
    
    # 检查工具脚本是否存在
    missing_tools = []
    for tool in VALIDATION_TOOLS:
        if not os.path.exists(tool['script']):
            missing_tools.append(tool['script'])
    
    if missing_tools:
        print(f"{RED}错误: 以下工具脚本不存在:{ENDC}")
        for script in missing_tools:
            print(f"  - {script}")
        print("请确保所有工具脚本在当前目录中")
        return
    
    # 准备命令行参数
    results = {}
    
    for tool in VALIDATION_TOOLS:
        print(f"\n{BOLD}{BLUE}运行 {tool['name']}...{ENDC}")
        print(f"  {tool['description']}")
        
        # 构建命令
        cmd = [sys.executable, tool['script']]
        
        if file_path:
            cmd.extend(['--file', file_path])
        elif check_all:
            cmd.append('--all')
        
        # 添加修复标志
        if fix and tool['fix_flag']:
            cmd.append(tool['fix_flag'])
        elif tool['script'] == 'fix_syntax_errors.py' and not fix:
            cmd.append('--dry-run')
        
        # 添加报告文件参数
        if 'report' in tool:
            cmd.extend(['--report', report_file])
        
        # 运行工具
        try:
            result = subprocess.run(cmd, check=False)
            results[tool['name']] = {
                'success': result.returncode == 0,
                'return_code': result.returncode
            }
        except Exception as e:
            print(f"{RED}运行 {tool['script']} 时出错: {str(e)}{ENDC}")
            results[tool['name']] = {
                'success': False,
                'error': str(e)
            }
    
    # 生成综合报告
    generate_combined_report(results, report_file)
    
    # 显示总结
    print(f"\n{BOLD}验证完成{ENDC}")
    for tool_name, result in results.items():
        status = f"{GREEN}成功{ENDC}" if result.get('success', False) else f"{RED}失败{ENDC}"
        print(f"  - {tool_name}: {status}")
    
    print(f"\n综合报告已保存至: {report_file}")


def generate_combined_report(results: Dict, report_file: str):
    """生成综合报告
    
    Args:
        results: 各工具的运行结果
        report_file: 报告文件路径
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
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("教程代码质量综合报告\n")
        f.write("=" * 50 + "\n\n")
        
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("验证工具运行结果:\n")
        for tool_name, result in results.items():
            status = "成功" if result.get('success', False) else "失败"
            f.write(f"  - {tool_name}: {status}\n")
            if 'error' in result:
                f.write(f"    错误: {result['error']}\n")
        
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
        f.write("   - 使用统一的代码格式和缩进风格\n")
        f.write("   - 遵循PEP 8命名约定\n")
        f.write("   - 保持一致的导入顺序\n\n")
        
        f.write("2. 文档和注释\n")
        f.write("   - 为所有模块、类和公共函数添加文档字符串\n")
        f.write("   - 在文档字符串中包含参数和返回值的说明\n")
        f.write("   - 为复杂逻辑添加适当的注释\n\n")
        
        f.write("3. 代码质量\n")
        f.write("   - 避免重复代码，提取共用功能\n")
        f.write("   - 减少函数复杂度和长度\n")
        f.write("   - 使用统一的错误处理机制\n\n")
        
        f.write("4. 持续改进\n")
        f.write("   - 定期运行代码质量检查\n")
        f.write("   - 在开发过程中应用代码审查\n")
        f.write("   - 持续更新和完善文档\n")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程代码质量验证工具')
    parser.add_argument('--file', help='要检查的教程文件路径')
    parser.add_argument('--all', action='store_true', help='检查所有教程文件')
    parser.add_argument('--fix', action='store_true', help='自动修复发现的问题')
    parser.add_argument('--report', default='tutorials_quality_report.txt', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 运行验证
    if args.file or args.all:
        run_validation(args.file, args.all, args.fix, args.report)
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
                    run_validation(TUTORIAL_FILES[index], False, args.fix, args.report)
                elif index == len(TUTORIAL_FILES):
                    run_validation(None, True, args.fix, args.report)
                else:
                    print(f"{RED}无效的选择{ENDC}")
        except ValueError:
            print(f"{RED}无效的输入{ENDC}")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}操作已取消{ENDC}")


if __name__ == "__main__":
    main()