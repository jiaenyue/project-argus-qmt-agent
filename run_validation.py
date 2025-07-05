import os
import subprocess
import sys
import datetime

def run_command(command, description, shell=True, capture_output=True):
    print(f"Running: {description}")
    try:
        # Set PYTHONIOENCODING to utf-8 for subprocesses to handle Unicode characters
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(command, shell=shell, capture_output=capture_output, text=True, encoding='utf-8', errors='ignore', env=env)
        if capture_output:
            print(f"Stdout:\n{result.stdout}")
            print(f"Stderr:\n{result.stderr}")
        return result
    except Exception as e:
        print(f"Error running command: {e}")
        return None

def main():
    report_content = []
    report_content.append("====== 教程文件验证报告 ======")
    report_content.append(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")

    # Activate virtual environment (Windows specific)
    activate_script = os.path.join("qmt_env", "Scripts", "activate.bat")
    if os.path.exists(activate_script):
        # This only activates for the current process, so subsequent commands need to be run in the same shell
        # For subprocess, we need to ensure the python executable from the venv is used directly
        python_executable = os.path.join("qmt_env", "Scripts", "python.exe")
    else:
        python_executable = sys.executable # Fallback to system python if venv not found

    # Install dependencies
    result = run_command(f"{python_executable} -m pip install -r requirements.txt", "Installing dependencies")
    if result and result.returncode != 0:
        report_content.append("[警告] 依赖安装失败")
        report_content.append(f"错误信息:\n{result.stderr}")
    else:
        report_content.append("[成功] 依赖安装成功")
    report_content.append("")

    # Install jupyter and nest_asyncio
    result = run_command(f"{python_executable} -m pip install jupyter nest_asyncio", "Installing jupyter and nest_asyncio")
    if result and result.returncode != 0:
        report_content.append("[警告] jupyter或nest_asyncio安装失败")
        report_content.append(f"错误信息:\n{result.stderr}")
    else:
        report_content.append("[成功] jupyter和nest_asyncio安装成功")
    report_content.append("")

    # API connection test
    report_content.append("正在测试API连接...")
    api_test_command = f'{python_executable} -c "import os; os.environ[\'NO_PROXY\'] = \'localhost,127.0.0.1\'; import requests; r = None; try: r=requests.get(\'http://localhost:8000/api/v1/status\', timeout=3) except requests.exceptions.RequestException as e: print(\'API连接错误: {{}}\'.format(e)) else: print(\'API状态: {{}}.{{}}\'.format(r.status_code, r.text))"'
    result = run_command(api_test_command, "API connection test")
    if result and result.returncode == 0 and "200" in result.stdout:
        report_content.append("[成功] API连接正常")
    else:
        report_content.append("[警告] API连接失败")
        if result:
            report_content.append(f"错误信息:\n{result.stdout}\n{result.stderr}")
    report_content.append("")

    # Validate Python scripts
    report_content.append("正在验证Python脚本...")
    tutorials_dir = "tutorials"
    for root, _, files in os.walk(tutorials_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                report_content.append(f"正在执行: {file_path}")
                result = run_command(f"{python_executable} \"{file_path}\"", f"Executing {file_path}")
                
                status = "[成功]"
                error_info = ""
                if result and result.returncode != 0:
                    status = "[失败]"
                    error_info = f"错误信息:\n{result.stdout}\n{result.stderr}"
                elif result and ("error" in result.stdout.lower() or "fail" in result.stdout.lower() or "warning" in result.stdout.lower()):
                    status = "[失败]"
                    error_info = f"输出包含错误/警告:\n{result.stdout}"

                report_content.append(f"[文件] {file_path}")
                report_content.append(status)
                if error_info:
                    report_content.append(error_info)
                report_content.append("")

    # Validate Jupyter Notebooks (commented out as per user request)
    # report_content.append("正在验证Jupyter Notebooks...")
    # for root, _, files in os.walk(tutorials_dir):
    #     for file in files:
    #         if file.endswith(".ipynb"):
    #             file_path = os.path.join(root, file)
    #             report_content.append(f"正在执行: {file_path}")
    #             # Use --ExecutePreprocessor.extra_arguments to pass --nest-asyncio
    #             command = f"{python_executable} -m jupyter nbconvert --execute --to notebook --inplace \"{file_path}\" --ExecutePreprocessor.kernel_name=python3 --ExecutePreprocessor.extra_arguments=\"--ZMQTerminalIPKernel.extra_arguments=--nest-asyncio\""
    #             result = run_command(command, f"Executing {file_path}")

    #             status = "[成功]"
    #             error_info = ""
    #             if result and result.returncode != 0:
    #                 status = "[失败]"
    #                 error_info = f"错误信息:\n{result.stdout}\n{result.stderr}"
    #             elif result and ("error" in result.stdout.lower() or "fail" in result.stdout.lower() or "warning" in result.stdout.lower()):
    #                 status = "[失败]"
    #                 error_info = f"输出包含错误/警告:\n{result.stdout}"

    #             report_content.append(f"[文件] {file_path}")
    #             report_content.append(status)
    #             if error_info:
    #                 report_content.append(error_info)
    #             report_content.append("")

    with open("tutorials_validation_report.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(report_content))

    print("验证完成! 结果已保存到: tutorials_validation_report.txt")
    run_command(f"{python_executable} generate_report.py", "Generating final report")

if __name__ == "__main__":
    main()
