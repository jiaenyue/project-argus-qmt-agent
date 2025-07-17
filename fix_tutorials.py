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
教程修复脚本

该脚本用于修复教程文件中的常见问题。
它是 validate_and_fix_tutorials.py 的简化版本，直接以修复模式运行。

使用方法：
    python fix_tutorials.py [--api-url URL]

参数：
    --api-url: API服务URL（默认：http://localhost:8000）
"""

import sys
import argparse
from validate_and_fix_tutorials import TutorialFixer
from validate_tutorials import TutorialValidator

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='教程修复脚本')
    parser.add_argument('--api-url', default='http://localhost:8000', help='API服务URL')
    
    args = parser.parse_args()
    
    # 创建验证器实例
    validator = TutorialValidator(api_url=args.api_url)
    
    # 创建修复器实例
    fixer = TutorialFixer(validator)
    
    # 执行验证和修复（修复模式）
    fixer.validate_and_fix(fix_mode=True)

if __name__ == "__main__":
    main()