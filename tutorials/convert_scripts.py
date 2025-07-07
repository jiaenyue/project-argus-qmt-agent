import os
import subprocess

TUTORIALS_DIR = "tutorials" # This variable is now only for context, not path joining

PYTHON_FILES = [
    "01_trading_dates.py",
    "02_hist_kline.py",
    "03_instrument_detail.py",
    "04_stock_list.py",
    "05_instrument_detail.py",
    "06_latest_market.py",
    "07_full_market.py",
]

def convert_py_to_ipynb():
    print("Converting .py to .ipynb...")
    for py_file in PYTHON_FILES:
        # Corrected: Directly use py_file as the script is run from TUTORIALS_DIR
        py_path = py_file
        ipynb_file = py_file.replace(".py", ".ipynb")
        # Corrected: Directly use ipynb_file as the script is run from TUTORIALS_DIR
        ipynb_path = ipynb_file
        command = ["jupytext", "--to", "ipynb", "--output", ipynb_path, py_path]
        print(f"Executing: {' '.join(command)}")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Successfully converted {py_file} to {ipynb_file}")
        except subprocess.CalledProcessError as e:
            print(f"Error converting {py_file}: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")

def convert_ipynb_to_py_with_outputs():
    print("Converting .ipynb to .py (with outputs, using percent format)...")
    for py_file in PYTHON_FILES:
        ipynb_file = py_file.replace(".py", ".ipynb")
        # Corrected: Directly use ipynb_file as the script is run from TUTORIALS_DIR
        ipynb_path = ipynb_file
        # Use .percent.py extension to avoid overwriting original .py files
        output_py_file = py_file.replace(".py", ".percent.py")
        # Corrected: Directly use output_py_file as the script is run from TUTORIALS_DIR
        output_py_path = output_py_file
        # Use --set-formats to specify the output format including outputs
        command = ["jupytext", "--to", "py:percent", "--output", output_py_path, ipynb_path]
        print(f"Executing: {' '.join(command)}")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Successfully converted {ipynb_file} to {output_py_file} (with outputs)")
        except subprocess.CalledProcessError as e:
            print(f"Error converting {ipynb_file}: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")

if __name__ == "__main__":
    print("Choose an option:")
    print("1. Convert .py files to .ipynb")
    print("2. Convert .ipynb files to .py (with outputs)")
    choice = input("Enter your choice (1 or 2): ")

    if choice == '1':
        convert_py_to_ipynb()
    elif choice == '2':
        convert_ipynb_to_py_with_outputs()
    else:
        print("Invalid choice. Please enter 1 or 2.")