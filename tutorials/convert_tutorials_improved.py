#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import json
from pathlib import Path

def install_jupytext():
    """安装jupytext如果未安装"""
    try:
        import jupytext
        return True
    except ImportError:
        print("正在安装jupytext...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "jupytext"])
            import jupytext
            return True
        except Exception as e:
            print(f"安装jupytext失败: {e}")
            return False

def validate_notebook(nb_path):
    """验证notebook是否可以正常运行"""
    try:
        # 使用jupyter nbconvert验证notebook
        result = subprocess.run([
            "jupyter", "nbconvert", "--to", "notebook", "--execute", 
            "--output", f"{nb_path.stem}_test.ipynb", str(nb_path)
        ], capture_output=True, text=True, timeout=120)
        
        # 清理测试文件
        test_file = nb_path.parent / f"{nb_path.stem}_test.ipynb"
        if test_file.exists():
            test_file.unlink()
            
        return result.returncode == 0
    except Exception as e:
        print(f"验证notebook失败: {e}")
        return False

def convert_py_to_ipynb(directory="tutorials"):
    """将目录中的所有.py文件转换为.ipynb格式"""
    if not install_jupytext():
        return False
        
    import jupytext
    
    success_count = 0
    total_count = 0
    
    for filename in os.listdir(directory):
        if filename.endswith(".py") and not filename.startswith("convert_"):
            total_count += 1
            py_path = Path(directory) / filename
            ipynb_path = py_path.with_suffix(".ipynb")
            
            try:
                print(f"转换 {filename}...")
                
                # 读取.py文件内容
                with open(py_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 确保文件有正确的jupytext头部
                if "# ---" not in content[:500]:
                    # 添加jupytext头部
                    header = '''# -*- coding: utf-8 -*-
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

'''
                    content = header + content
                    with open(py_path, "w", encoding="utf-8") as f:
                        f.write(content)
                
                # 转换为notebook
                with open(py_path, "r", encoding="utf-8") as f:
                    notebook = jupytext.read(f, fmt="py:light")
                
                # 写入.ipynb文件
                jupytext.write(notebook, ipynb_path, fmt="ipynb")
                
                print(f"✅ 转换成功: {py_path} -> {ipynb_path}")
                
                # 验证notebook
                if validate_notebook(ipynb_path):
                    print(f"✅ Notebook验证成功: {ipynb_path}")
                    success_count += 1
                else:
                    print(f"⚠️ Notebook验证失败: {ipynb_path}")
                    
            except Exception as e:
                print(f"❌ 转换失败: {py_path}")
                print(f"错误详情: {str(e)}")
                
                # 打印问题文件的前10行帮助调试
                try:
                    with open(py_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()[:10]
                        print("文件头部内容:")
                        for i, line in enumerate(lines, 1):
                            print(f"{i}: {line.strip()}")
                except:
                    pass
    
    print(f"\n📊 转换完成: {success_count}/{total_count} 成功")
    return success_count == total_count

def convert_ipynb_to_py(directory="tutorials"):
    """将目录中的所有.ipynb文件转换为.py格式"""
    if not install_jupytext():
        return False
        
    import jupytext
    
    success_count = 0
    total_count = 0
    
    for filename in os.listdir(directory):
        if filename.endswith(".ipynb"):
            total_count += 1
            ipynb_path = Path(directory) / filename
            py_path = ipynb_path.with_suffix(".py")
            
            try:
                # 读取.ipynb文件内容
                notebook = jupytext.read(ipynb_path)
                
                # 写入.py文件（light格式）
                jupytext.write(notebook, py_path, fmt="py:light")
                print(f"✅ 转换成功: {ipynb_path} -> {py_path}")
                success_count += 1
                
            except Exception as e:
                print(f"❌ 转换失败: {ipynb_path}")
                print(f"错误详情: {str(e)}")
    
    print(f"\n📊 转换完成: {success_count}/{total_count} 成功")
    return success_count == total_count

def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="教程文件转换工具")
    parser.add_argument("--direction", choices=["py2nb", "nb2py"], default="py2nb",
                        help="转换方向: py2nb=Python到Notebook, nb2py=Notebook到Python")
    parser.add_argument("--directory", default=".", help="目标目录")
    
    args = parser.parse_args()
    
    if args.direction == "py2nb":
        convert_py_to_ipynb(args.directory)
    else:
        convert_ipynb_to_py(args.directory)

if __name__ == "__main__":
    main()