import os
import argparse
import jupytext

def convert_py_to_ipynb(directory="tutorials"):
    """将目录中的所有.py文件转换为.ipynb格式"""
    for filename in os.listdir(directory):
        if filename.endswith(".py"):
            py_path = os.path.join(directory, filename)
            ipynb_path = os.path.join(directory, filename.replace(".py", ".ipynb"))
            
            try:
                # 读取.py文件内容（显式指定格式避免自动检测问题）
                with open(py_path, "r", encoding="utf-8") as f:
                    notebook = jupytext.read(f, fmt="py:light")
                
                # 写入.ipynb文件
                jupytext.write(notebook, ipynb_path, fmt="ipynb")
                print(f"转换成功: {py_path} -> {ipynb_path}")
            except Exception as e:
                print(f"转换失败: {py_path}")
                print(f"错误详情: {str(e)}")
                # 打印问题文件的前10行帮助调试
                with open(py_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[:10]
                    print("文件头部内容:")
                    for i, line in enumerate(lines, 1):
                        print(f"{i}: {line.strip()}")

def convert_ipynb_to_py(directory="tutorials"):
    """将目录中的所有.ipynb文件转换为.py格式"""
    for filename in os.listdir(directory):
        if filename.endswith(".ipynb"):
            ipynb_path = os.path.join(directory, filename)
            py_path = os.path.join(directory, filename.replace(".ipynb", ".py"))
            
            # 读取.ipynb文件内容
            notebook = jupytext.read(ipynb_path)
            
            # 写入.py文件（light格式）
            jupytext.write(notebook, py_path, fmt="py:light")
            print(f"转换成功: {ipynb_path} -> {py_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="教程文件格式转换工具")
    parser.add_argument("--to", choices=["ipynb", "py"], required=True,
                        help="转换方向: 'ipynb'将.py转为.ipynb, 'py'将.ipynb转为.py")
    parser.add_argument("--dir", default="tutorials",
                        help="要转换的目录路径 (默认: tutorials)")
    
    args = parser.parse_args()
    
    if args.to == "ipynb":
        convert_py_to_ipynb(args.dir)
    elif args.to == "py":
        convert_ipynb_to_py(args.dir)
    
    print("\n转换完成！")
