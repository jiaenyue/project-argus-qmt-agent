# Data Agent Service

This service provides an API proxy for financial data, initially focusing on `xtquant` library functionalities.

## Features

- `/instrument_detail`: Fetches real-time contract information.

## Setup and Run

## 🚀 Quick Start

1. **环境准备**
   ```bash
   # 克隆项目
   git clone <repository-url>
   cd project-argus-qmt-agent
   
   # 创建虚拟环境
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate     # Windows
   
   # 安装依赖
   pip install -r requirements.txt
   ```

2. **启动服务**
   ```bash
   python main.py
   ```

3. **验证服务**
   服务启动后，访问 http://localhost:8000/docs 查看API文档并测试接口。

## 主要功能

本服务通过基于 **FastAPI** 构建的 HTTP(S) API 接口，提供 miniQMT 的核心数据查询功能，主要包括：

*   **行情数据服务:**
    *   获取交易日历 (`/trading_dates`)
    *   获取板块/股票列表 (`/stock_list`)
    *   获取单只/多只合约的详细信息 (`/instrument_detail`)
    *   获取多种周期（分钟、日、周、月）的历史K线数据 (OHLCV) (`/hist_kline`)
    *   获取最新市场行情快照 (`/latest_market`)
*   **(可选) 客户端交互:**
    *   创建图表面板 (`/create_chart_panel`) - 此功能依赖QMT客户端的UI交互能力。
*   **环境解耦:**
    *   将 Windows 平台的 miniQMT 依赖与上层数据处理系统有效隔离。
*   **易用性与运维:**
    *   提供基础但全面的日志记录功能 (记录到控制台及 `qmt_data_agent.log` 文件)。
    *   服务监听端口可通过环境变量 `QMT_DATA_AGENT_PORT`灵活配置。
    *   通过 FastAPI 自动生成 OpenAPI (Swagger) 交互式API文档 (通常位于 `/docs` 路径)。

## 架构简介

本数据代理服务在逻辑上分为以下几个核心层次：

1.  **`xtquant` 交互层**: 直接通过 `xtquant` Python 库与在本地 Windows 环境中运行的 miniQMT 客户端进行通信，负责执行数据请求和接收原始数据。
2.  **API 服务层**: 基于 **FastAPI** 构建，负责：
    *   暴露符合 OpenAPI 规范的 RESTful HTTP(S) API 接口。
    *   处理客户端的API请求，进行参数校验。
    *   调用 `xtquant` 交互层获取数据，并将其转换为标准化的JSON格式返回给调用方。
    *   实现基础的认证 (如API Key)、日志、错误处理等功能。
3.  **(未来规划) MCP 适配层**: 旨在支持 Model Context Protocol，以便与AI助手等工具集成。

这种分层设计旨在实现模块化和关注点分离，使得系统更易于维护和扩展。更详细的系统架构、组件职责、数据流和部署要求，请参阅 [项目文档中的系统设计文档 (`doc/system_design.md`)](doc/system_design.md)。

## 先决条件

> **⚠️ 重要提醒：本项目严格依赖 miniQMT 连接**
> 
> 本项目已移除所有模拟数据和回退机制。项目必须连接到真实的 miniQMT 客户端才能正常运行。
> 如果无法连接 miniQMT，系统将直接报错而不会提供任何模拟数据。
> 请确保在使用本项目前已正确安装并配置 miniQMT 客户端。

*   **Windows 操作系统**
*   **Python 3.10.18** (推荐使用Conda环境管理)
*   **miniQMT 客户端 (迅投量化交易终端):** **必须**在同一台 Windows 机器上安装并正在运行。这是项目运行的强制要求，无替代方案。
*   **`xtquant` 库:** 这是 miniQMT 客户端自带的 Python API 库。**必须**能够成功导入，否则项目无法启动。
    *   **验证:** 在您的 Python 环境中执行 `python -c "from xtquant import xtdata; print(xtdata)"`。如果未报错，则说明 `xtquant` 可用。
    *   **故障排除:** 如果导入失败，您可能需要：
        *   将 QMT 安装目录下的 `bin\Lib\site-packages` (或类似路径，具体取决于您的QMT版本和安装位置) 添加到系统的 `PYTHONPATH` 环境变量。
        *   或者，将 `xtquant` 文件夹从 QMT 的 Python 库路径复制到您当前 Python 环境的 `site-packages` 目录。
    *   **注意:** 如果无法解决 `xtquant` 导入问题，项目将无法运行，不存在任何回退选项。
*   (可选，未来AI集成) **Node.js 和 npx:** 如果希望使用 `xtquantai` 的完整MCP服务器功能。

## 安装与配置

1.  **克隆或下载本项目代码：**
    ```bash
    git clone https://github.com/jiaenyue/project-argus-qmt-agent.git
    cd project-argus-qmt-agent
    ```
2.  **详细安装与配置步骤:**
    请参阅 [安装指南 (INSTALL.md)](INSTALL.md) 和 [环境设置说明 (ENVIRONMENT_SETUP.md)](ENVIRONMENT_SETUP.md) 获取详细的设置说明，包括：
    *   设置 Python 环境 (Python 3.10.18，推荐使用Conda)。
    *   激活 Conda 环境 (`conda activate qmt_py310`)。
    *   从 `requirements.txt` 安装依赖。
    *   验证 `xtquant` 的可访问性。
    *   验证 `xtquant` 的可访问性（这是强制要求）。

## 运行代理服务

按照 [安装指南 (INSTALL.md)](INSTALL.md) 中的说明安装和配置完成后，您可以使用项目根目录下的 `main.py` 脚本来运行服务。

1.  **确保 miniQMT 客户端已登录并正常运行 (如果使用实时数据)。**
2.  **激活 Conda 环境:**
    ```bash
    conda activate qmt_py310
    # 或使用批处理脚本
    activate_env.bat
    ```
3.  **导航到项目根目录并运行：**
    ```bash
    python main.py

    ```
    这将以自动模式启动服务（首先尝试 MCP Inspector，然后回退到直接模式）。您也可以指定模式：
    *   `python main.py --mode direct` (直接模式)
    *   `python main.py --mode inspector` (MCP Inspector 模式，需要 Node.js 和 npx)

    您应该能看到服务启动的日志信息。

4.  **日志文件:**
    服务主要将日志输出到控制台。MCP 服务 (`src/xtquantai/server.py`) 会将日志记录到标准输出。有关详细的日志配置 (尤其是在 MCP 环境中)，请参阅 MCP 相关文档或服务输出信息。
    项目关于日志的详细讨论可以在 [系统设计文档中的"日志记录和监控"部分 (`doc/system_design.md#5-日志记录和监控`)](doc/system_design.md#5-日志记录和监控) 找到。

## 持久化运行 (作为 Windows 服务 - 推荐)

要将代理作为 Windows 服务持久运行，您可以使用 `NSSM`。请首先参照 [安装指南 (INSTALL.md)](INSTALL.md) 完成基本安装步骤，然后按以下方式配置 NSSM：

1.  **下载 NSSM:** 从 [NSSM 官网](https://nssm.cc/download) 下载。
2.  **安装服务 (示例):**
    *   将 `nssm.exe` 放置在一个合适的目录 (例如 `C:\NSSM\`)。
    *   以管理员身份打开命令提示符。
    *   运行 `C:\NSSM\nssm.exe install ProjectArgusQMTDataAgent`
    *   在 NSSM 图形用户界面中：
        *   **Path (路径):** 指向您虚拟环境中的 Python 解释器路径 (例如 `C:\project-argus-qmt-agent\qmt_env\Scripts\python.exe`)。
        *   **Startup directory (启动目录):** 本项目的根目录 (例如 `C:\project-argus-qmt-agent\`)。
        *   **Arguments (参数):** `main.py` (如果您希望指定特定模式，可以是 `main.py --mode direct`)。
        *   **Environment Tab (环境变量页):** 可根据需要设置其他环境变量，但不再支持 `QMT_DATA_AGENT_PORT` 等回退机制相关配置。
    *   点击 "Install service" (安装服务)。
3.  **启动服务:**
    ```bash
    C:\NSSM\nssm.exe start ProjectArgusQMTDataAgent
    ```
    或者通过 Windows 服务管理器 (`services.msc`) 启动。

## 📚 教学文档体系

本项目提供完整的教学文档体系，帮助用户快速掌握API的使用方法：

### 🎯 教学模块

| 教学模块 | Python脚本 | Jupyter Notebook | 学习内容 |
|----------|------------|------------------|----------|
| 交易日历 | [`01_trading_dates.py`](tutorials/01_trading_dates.py) | [`01_trading_dates.ipynb`](tutorials/notebooks/01_trading_dates.ipynb) | 市场交易日期查询和验证 |
| 历史K线 | [`02_hist_kline.py`](tutorials/02_hist_kline.py) | [`02_hist_kline.ipynb`](tutorials/notebooks/02_hist_kline.ipynb) | OHLCV数据获取和分析 |
| 合约详情 | [`03_instrument_detail.py`](tutorials/03_instrument_detail.py) | [`03_instrument_detail.ipynb`](tutorials/notebooks/03_instrument_detail.ipynb) | 股票信息查询和验证 |
| 股票列表 | [`04_stock_list.py`](tutorials/04_stock_list.py) | [`04_stock_list.ipynb`](tutorials/notebooks/04_stock_list.ipynb) | 板块数据和成分股分析 |
| 最新行情 | [`06_latest_market.py`](tutorials/06_latest_market.py) | [`06_latest_market.ipynb`](tutorials/notebooks/06_latest_market.ipynb) | 实时数据处理和监控 |
| 完整行情 | [`07_full_market.py`](tutorials/07_full_market.py) | [`07_full_market.ipynb`](tutorials/notebooks/07_full_market.ipynb) | 深度行情分析和统计 |

### 📖 学习资源

- **[教学索引](tutorials/TUTORIAL_INDEX.md)**: 完整的学习路径和使用指南
- **[验证报告](tutorials/VALIDATION_REPORT.md)**: 教学文档的验证状态和质量报告
- **[故障排除](tutorials/TROUBLESHOOTING.md)**: 常见问题和解决方案
- **[教程README](tutorials/README.md)**: 详细的使用说明和环境配置

### 🚀 快速开始教学

1. **Python脚本学习**：
   ```bash
   cd tutorials
   python 01_trading_dates.py
   ```

2. **Jupyter交互学习**：
   ```bash
   jupyter notebook tutorials/notebooks/01_trading_dates.ipynb
   ```

3. **查看学习路径**：
   ```bash
   # 查看完整教学计划
   cat tutorials/TUTORIAL_INDEX.md
   ```

### 💡 教学特色

- ✅ **双格式支持**: 提供Python脚本和Jupyter Notebook两种格式
- ✅ **可执行代码**: 所有示例都基于真实API调用
- ✅ **分步指导**: 详细的操作步骤和最佳实践
- ✅ **错误处理**: 完善的异常处理和故障排除
- ✅ **性能监控**: 内置性能统计和优化建议

## API 接口说明

本代理提供符合 OpenAPI (Swagger) 规范的 RESTful API。具体的API接口定义、参数及响应结构与 `doc/system_design.md` 中"接口规范"部分所述一致，并通过 FastAPI 应用在 `/docs` 路径下提供自动生成的 OpenAPI 文档。

以下为主要数据获取接口的概览 (具体参数请参考 `/docs` 或 `doc/system_design.md`):

*   **获取交易日历:** `GET /trading_dates`
    *   参数: `market`, `start_date`, `end_date`
*   **获取板块股票列表:** `GET /stock_list`
    *   参数: `sector`
*   **获取合约详细信息:** `GET /instrument_detail`
    *   参数: `symbol`
*   **获取历史K线数据:** `GET /hist_kline`
    *   参数: `symbol`, `start_date`, `end_date`, `frequency`, `dividend_type` (复权类型), `fill_data` (是否填充) 等。
*   **获取最新行情快照:** `GET /latest_market`
    *   参数: `symbols` (逗号分隔的股票代码列表)
*   **获取完整行情数据:** `GET /full_market` (较少使用，通常 `/latest_market` 或 `/hist_kline` 已足够)
    *   参数: `symbol`, `fields` (可选)
*   **(可选) 创建图表面板:** `POST /create_chart_panel` (依赖QMT客户端UI交互)
    *   参数: 具体参数待定，通常包括 `codes`, `period`, `indicator_name` 等。

**通用请求头部:**
*   `X-API-Key`: (推荐) 用于认证的API密钥。实际认证机制以最终实现为准。

**通用响应结构 (示意):**
*   成功时: HTTP状态码 `200 OK`，响应体通常为JSON格式，包含请求的数据。
    ```json
    // 例如: GET /instrument_detail?symbol=600519.SH
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "last_price": 1700.00,
      // ... 其他字段
    }
    ```
*   失败时: HTTP状态码 `4xx` (客户端错误) 或 `5xx` (服务器错误)，响应体通常包含错误信息。
    ```json
    {
      "detail": "Error message explaining what went wrong."
    }
    ```
    *注: 旧版或基于 `xtquantai/server_direct.py` 直接修改的版本可能采用 `{"success": true/false, "data": ..., "error": ...}` 结构。本文档描述的是推荐的 RESTful 风格。请以服务实际提供的 `/docs` 为准。*


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
