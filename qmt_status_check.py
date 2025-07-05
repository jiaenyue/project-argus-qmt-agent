import os
import sys
import subprocess
import traceback

def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"Successfully installed {package}")
        return True
    except Exception as e:
        print(f"Failed to install {package}: {str(e)}")
        return False

def check_xtmini_process():
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            if "xtMiniQmt.exe" in proc.info['name']:
                return True
        return False
    except ImportError:
        print("psutil module not found. Attempting to install...")
        if install_package("psutil"):
            return check_xtmini_process()
        return False

def check_qmt_login():
    try:
        import xtquant
        return xtquant.xt.connected()
    except ImportError:
        print("xtquant module not found. Please ensure QMT environment is properly set up.")
        return False
    except Exception as e:
        print(f"Error checking QMT login status: {str(e)}")
        return False

def check_xtquant_init():
    try:
        import xtquant
        xtquant.xt.init()
        return True
    except ImportError:
        print("xtquant module not found. Please ensure QMT environment is properly set up.")
        return False
    except Exception as e:
        print(f"Error initializing xtQuant: {str(e)}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("QMT 状态检查")
    print("="*50)
    
    # 检查xtMiniQmt进程
    xtmini_running = check_xtmini_process()
    print(f"xtMiniQmt 进程状态: {'运行中' if xtmini_running else '未运行'}")
    
    # 检查QMT登录状态
    logged_in = check_qmt_login()
    print(f"QMT 登录状态: {'已登录' if logged_in else '未登录'}")
    
    # 检查xtQuant初始化状态
    xtquant_initialized = check_xtquant_init()
    print(f"xtQuant 初始化状态: {'已初始化' if xtquant_initialized else '初始化失败'}")
    
    print("="*50)
    input("按Enter键退出...")