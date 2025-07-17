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
清除缓存并运行教程

该脚本用于清除缓存文件并运行指定的教程文件。
支持以下功能：
- 清除Python缓存文件（__pycache__目录和.pyc文件）
- 清除临时文件和日志
- 运行指定的教程文件

使用方法：
    python clear_cache_and_run.py [tutorial_file] [--clean-only]

参数：
    tutorial_file: 要运行的教程文件路径（可选）
    --clean-only: 仅清除缓存，不运行教程
"""

import os
import sys
import shutil
import argparse
import subprocess
from typing import List

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


def clean_cache():
    """清除缓存文件"""
    print(f"{BOLD}清除缓存文件...{ENDC}")
    
    # 清除__pycache__目录
    pycache_dirs = []
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                pycache_dirs.append(os.path.join(root, dir_name))
    
    for pycache_dir in pycache_dirs:
        try:
            shutil.rmtree(pycache_dir)
            print(f"  {GREEN}已删除: {pycache_dir}{ENDC}")
        except Exception as e:
            print(f"  {RED}删除失败: {pycache_dir} - {str(e)}{ENDC}")
    
    # 清除.pyc文件
    pyc_files = []
    for root, dirs, files in os.walk('.'):
        for file_name in files:
            if file_name.endswith('.pyc'):
                pyc_files.append(os.path.join(root, file_name))
    
    for pyc_file in pyc_files:
        try:
            os.remove(pyc_file)
            print(f"  {GREEN}已删除: {pyc_file}{ENDC}")
        except Exception as e:
            print(f"  {RED}删除失败: {pyc_file} - {str(e)}{ENDC}")
    
    # 清除临时文件和日志
    temp_patterns = ['.log', '.tmp', '.temp']
    temp_files = []
    for root, dirs, files in os.walk('.'):
        for file_name in files:
            if any(file_name.endswith(pattern) for pattern in temp_patterns):
                temp_files.append(os.path.join(root, file_name))
    
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
            print(f"  {GREEN}已删除: {temp_file}{ENDC}")
        except Exception as e:
            print(f"  {RED}删除失败: {temp_file} - {str(e)}{ENDC}")
    
    print(f"{GREEN}缓存清理完成{ENDC}")


def run_tutorial(file_path: str):
    """运行教程文件
    
    Args:
        file_path: 教程文件路径
    """
    if not os.path.exists(file_path):
        print(f"{RED}文件不存在: {file_path}{ENDC}")
        return
    
    print(f"{BOLD}运行教程: {file_path}{ENDC}")
    
    try:
        # 使用Python解释器运行文件
        process = subprocess.Popen(
            [sys.executable, file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # 实时输出结果
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        # 获取错误输出
        stderr = process.stderr.read()
        if stderr:
            print(f"{RED}错误输出:{ENDC}")
            print(stderr)
        
        # 检查返回码
        return_code = process.poll()
        if return_code == 0:
            print(f"{GREEN}教程运行成功{ENDC}")
        else:
            print(f"{RED}教程运行失败，返回码: {return_code}{ENDC}")
    
    except Exception as e:
        print(f"{RED}运行教程时出错: {str(e)}{ENDC}")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='清除缓存并运行教程')
    parser.add_argument('tutorial_file', nargs='?', help='要运行的教程文件路径')
    parser.add_argument('--clean-only', action='store_true', help='仅清除缓存，不运行教程')
    
    args = parser.parse_args()
    
    # 清除缓存
    clean_cache()
    
    # 如果不是仅清除缓存模式，运行教程
    if not args.clean_only:
        if args.tutorial_file:
            # 运行指定的教程文件
            run_tutorial(args.tutorial_file)
        else:
            # 提示用户选择教程文件
            print(f"{BOLD}可用的教程文件:{ENDC}")
            for i, file_path in enumerate(TUTORIAL_FILES):
                print(f"  {i+1}. {file_path}")
            
            try:
                choice = input(f"\n请选择要运行的教程 (1-{len(TUTORIAL_FILES)})，或按Enter退出: ")
                if choice.strip():
                    index = int(choice) - 1
                    if 0 <= index < len(TUTORIAL_FILES):
                        run_tutorial(TUTORIAL_FILES[index])
                    else:
                        print(f"{RED}无效的选择{ENDC}")
            except ValueError:
                print(f"{RED}无效的输入{ENDC}")
            except KeyboardInterrupt:
                print(f"\n{YELLOW}操作已取消{ENDC}")


if __name__ == "__main__":
    main()