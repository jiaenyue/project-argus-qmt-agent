# Data Agent Service

This service provides an API proxy for financial data, initially focusing on `xtquant` library functionalities.

## Features

- `/instrument_detail`: Fetches real-time contract information.

## Setup and Run

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the FastAPI application:**
    ```bash
    uvicorn data_agent_service.main:app --reload
    ```

## API Usage

### Get Instrument Detail

-   **Endpoint:** `/instrument_detail`
-   **Method:** `GET`
-   **Query Parameter:**
    -   `symbol` (string, required): The stock/contract symbol (e.g., "600519.SH").
-   **Example:**
    ```python
    import requests

    response = requests.get(
        "http://localhost:8000/instrument_detail",
        params={"symbol": "600519.SH"}
    )
    print(response.json())
    ```

## 防火墙与连接测试

### 防火墙测试
运行 `firewall_test.bat` 脚本，该脚本将：
1. 临时禁用防火墙
2. 运行 `miniqmt_test.py`
3. 重新启用防火墙

### 连接测试
运行 `connection_test.py` 脚本测试xtQuant连接：
```bash
python connection_test.py
```


## 账号配置说明

在使用`miniqmt_test.py`脚本前：
1. 打开脚本文件找到以下行：
   ```python
   account = "替换为您的交易账号"  # 占位符，用户需要填写
   ```
2. 将`替换为您的交易账号`改为您的实际交易账号（例如：`"123456789"`）
3. 保存文件后运行脚本

## QMT路径配置说明

在使用`miniqmt_test.py`脚本前，请确认您的QMT安装路径：
1. 打开脚本文件，找到以下行：
   ```python
   qmt_path = "G:\\Stock\\GJ_QMT\\bin.x64"  # 使用用户提供的QMT路径
   ```
2. 如果您的QMT安装路径不同，请将路径修改为您的实际安装路径（注意：路径中使用双反斜杠`\\`）
3. 保存文件后运行脚本
