#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
运行所有教程脚本

该脚本用于运行所有教程文件并生成质量报告。
支持以下功能：
- 顺序运行所有教程文件
- 收集执行结果和错误信息
- 生成质量报告

使用方法：
    python run_all_tutorials.py [--timeout SECONDS] [--output FILE]

参数：
    --timeout: 每个教程的超时时间（默认：60秒）
    --output: 输出报告文件路径（默认：tutorials_quality_report.txt）
"""

import os
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Tuple

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


class TutorialRunner:
    """教程运行器类，用于运行教程文件并生成报告"""
    
    def __init__(self, timeout: int = 60):
        """初始化运行器
        
        Args:
            timeout: 每个教程的超时时间（秒）
        """
        self.timeout = timeout
        self.results = {
            'executions': {},
            'summary': {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_files': len(TUTORIAL_FILES),
                'successful_executions': 0,
                'failed_executions': 0,
                'timeout_executions': 0,
                'total_duration': 0
            }
        }
    
    def run_all_tutorials(self) -> Dict:
        """运行所有教程文件
        
        Returns:
            Dict: 运行结果
        """
        print(f"{BOLD}开始运行所有教程文件...{ENDC}")
        
        total_start_time = time.time()
        
        for file_path in TUTORIAL_FILES:
            file_name = os.path.basename(file_path)
            print(f"\n{BOLD}运行 {file_name}...{ENDC}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"  {RED}文件不存在，跳过{ENDC}")
                self.results['executions'][file_path] = {
                    'success': False,
                    'error': '文件不存在',
                    'duration': 0,
                    'output': '',
                    'status': 'missing'
                }
                self.results['summary']['failed_executions'] += 1
                continue
            
            # 运行教程文件
            result = self._run_tutorial(file_path)
            self.results['executions'][file_path] = result
            
            # 更新统计信息
            if result['success']:
                self.results['summary']['successful_executions'] += 1
                print(f"  {GREEN}执行成功 ({result['duration']:.2f}秒){ENDC}")
            elif result['status'] == 'timeout':
                self.results['summary']['timeout_executions'] += 1
                print(f"  {YELLOW}执行超时 (>{self.timeout}秒){ENDC}")
            else:
                self.results['summary']['failed_executions'] += 1
                print(f"  {RED}执行失败: {result['error']}{ENDC}")
        
        # 计算总耗时
        self.results['summary']['total_duration'] = time.time() - total_start_time
        
        # 生成报告
        self._generate_report()
        
        print(f"\n{BOLD}所有教程运行完成:{ENDC}")
        print(f"  成功: {self.results['summary']['successful_executions']}")
        print(f"  失败: {self.results['summary']['failed_executions']}")
        print(f"  超时: {self.results['summary']['timeout_executions']}")
        print(f"  总耗时: {self.results['summary']['total_duration']:.2f}秒")
        
        return self.results
    
    def _run_tutorial(self, file_path: str) -> Dict:
        """运行单个教程文件
        
        Args:
            file_path: 教程文件路径
            
        Returns:
            Dict: 运行结果
        """
        result = {
            'success': False,
            'error': None,
            'duration': 0,
            'output': '',
            'status': 'unknown'
        }
        
        try:
            # 使用子进程运行教程文件
            start_time = time.time()
            
            # 使用Python解释器执行文件，捕获输出
            process = subprocess.Popen(
                [sys.executable, file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            try:
                # 等待进程完成，设置超时
                stdout, stderr = process.communicate(timeout=self.timeout)
                duration = time.time() - start_time
                
                result['duration'] = duration
                result['output'] = stdout
                
                if process.returncode == 0:
                    result['success'] = True
                    result['status'] = 'success'
                else:
                    result['error'] = stderr
                    result['status'] = 'error'
            
            except subprocess.TimeoutExpired:
                # 超时，终止进程
                process.kill()
                stdout, stderr = process.communicate()
                
                result['duration'] = self.timeout
                result['error'] = f"执行超时 (>{self.timeout}秒)"
                result['status'] = 'timeout'
                result['output'] = stdout
        
        except Exception as e:
            result['error'] = str(e)
            result['status'] = 'exception'
        
        return result
    
    def _generate_report(self):
        """生成运行报告"""
        # 保存为JSON文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = f"tutorials_quality_report_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        # 创建最新结果的链接
        latest_file = "tutorials_quality_report.json"
        if os.path.exists(latest_file):
            os.remove(latest_file)
        
        # 在Windows上使用复制而不是符号链接
        import shutil
        shutil.copy2(result_file, latest_file)
        
        # 生成文本报告
        self._generate_text_report("tutorials_quality_report.txt")
    
    def _generate_text_report(self, report_file: str):
        """生成文本报告
        
        Args:
            report_file: 报告文件路径
        """
        summary = self.results['summary']
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("教程质量报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"运行时间: {summary['timestamp']}\n\n")
            
            f.write("运行摘要:\n")
            f.write(f"  总文件数: {summary['total_files']}\n")
            f.write(f"  成功执行: {summary['successful_executions']}\n")
            f.write(f"  失败执行: {summary['failed_executions']}\n")
            f.write(f"  超时执行: {summary['timeout_executions']}\n")
            f.write(f"  总耗时: {summary['total_duration']:.2f}秒\n\n")
            
            f.write("详细结果:\n")
            for file_path, result in self.results['executions'].items():
                file_name = os.path.basename(file_path)
                status = result['status']
                duration = f"{result['duration']:.2f}秒" if result['duration'] else 'N/A'
                
                if status == 'success':
                    f.write(f"\n  {file_name}: 成功 ({duration})\n")
                elif status == 'timeout':
                    f.write(f"\n  {file_name}: 超时 ({duration})\n")
                elif status == 'error':
                    f.write(f"\n  {file_name}: 失败 ({duration})\n")
                    f.write(f"    错误: {result['error']}\n")
                elif status == 'missing':
                    f.write(f"\n  {file_name}: 文件不存在\n")
                else:
                    f.write(f"\n  {file_name}: 未知状态 ({status})\n")
                    if result['error']:
                        f.write(f"    错误: {result['error']}\n")
                
                # 添加输出摘要（如果有）
                if result['output']:
                    output_lines = result['output'].split('\n')
                    if len(output_lines) > 10:
                        # 只显示前5行和后5行
                        output_summary = '\n    '.join(output_lines[:5] + ['...'] + output_lines[-5:])
                    else:
                        output_summary = '\n    '.join(output_lines)
                    
                    f.write(f"    输出摘要:\n    {output_summary}\n")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='运行所有教程脚本')
    parser.add_argument('--timeout', type=int, default=60, help='每个教程的超时时间（秒）')
    parser.add_argument('--output', default='tutorials_quality_report.txt', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建运行器实例
    runner = TutorialRunner(timeout=args.timeout)
    
    # 运行所有教程
    runner.run_all_tutorials()


if __name__ == "__main__":
    main()