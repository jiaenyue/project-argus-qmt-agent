# Project Argus QMT Data Agent

本项目是一个在 Windows 环境下运行的 Python 服务，作为 Project Argus (或其他需要访问 miniQMT 数据的系统) 与 miniQMT (迅投量化交易客户端) 之间的数据代理。它利用 `xtquant` 库与本地运行的 miniQMT 客户端进行交互，并通过 HTTP(S) API 接口暴露数据服务。

本项目基于 [xtquantai](https://github.com/dfkai/xtquantai) 项目中的 `server_direct.py` 脚本进行修改和定制，专注于提供稳定可靠的数据接口。同时，`xtquantai` 项目本身支持 MCP (Model Context Protocol)，为未来与 AI 助手集成提供了潜力。

## 主要功能

*   通过 HTTP API 接口提供 miniQMT 的核心数据查询功能：
    *   获取交易日历
    *   获取板块/股票列表
    *   获取合约详细信息
    *   获取历史K线数据 (OHLCV)
    *   (可选) 创建图表面板 (依赖QMT客户端UI交互)
*   将 Windows 平台的 miniQMT 依赖与上层数据处理系统 (如 Project Argus 的 Docker 化环境) 解耦。
*   提供基础的日志记录功能。
*   端口可通过环境变量配置。

## 先决条件

*   **Windows 操作系统**
*   **Python 3.11+**
*   **miniQMT 客户端 (迅投量化交易终端):** 必须在同一台 Windows 机器上安装并正在运行。
*   **`xtquant` 库:** 这是 miniQMT 客户端自带的 Python API 库。通常，在安装 QMT 客户端时，它会尝试将其 Python 库安装到默认的 Python 环境或提供安装说明。您需要确保运行此代理的 Python 环境能够成功导入 `xtquant`。
    *   **验证:** 在您的 Python 环境中执行 `python -c "from xtquant import xtdata; print(xtdata)"`。如果未报错，则说明 `xtquant` 可用。
    *   **故障排除:** 如果导入失败，您可能需要：
        *   将 QMT 安装目录下的 `bin\Lib\site-packages` (或类似路径，具体取决于您的QMT版本和安装位置) 添加到系统的 `PYTHONPATH` 环境变量。
        *   或者，将 `xtquant` 文件夹从 QMT 的 Python 库路径复制到您当前 Python 环境的 `site-packages` 目录。
*   (可选，未来AI集成) **Node.js 和 npx:** 如果希望使用 `xtquantai` 的完整MCP服务器功能。

## 安装与配置

1.  **克隆或下载本项目代码：**
    ```bash
    git clone https://github.com/jiaenyue/project-argus-qmt-agent.git
    cd project-argus-qmt-agent
    ```
    或者直接下载 `qmt_data_agent.py` (或其他主要脚本文件)。

2.  **Python 环境：**
    建议使用虚拟环境：
    ```bash
    python -m venv .venv
    # 激活虚拟环境
    # Windows CMD:
    # .venv\Scripts\activate.bat
    # Windows PowerShell:
    # .\.venv\Scripts\Activate.ps1
    ```

3.  **依赖安装 (如果除了标准库和`xtquant`外还有其他依赖):**
    如果本项目有 `requirements.txt` 文件：
    ```bash
    pip install -r requirements.txt
    ```
    (当前版本的 `qmt_data_agent.py` 主要依赖Python标准库和`xtquant`)

4.  **配置端口 (可选):**
    本代理服务监听的端口可以通过环境变量 `QMT_DATA_AGENT_PORT` 进行配置。如果未设置，默认为 `8000`。
    ```bash
    # Windows CMD
    set QMT_DATA_AGENT_PORT=8001
    # Windows PowerShell
    $env:QMT_DATA_AGENT_PORT="8001"
    ```

## 运行代理服务

1.  **确保 miniQMT 客户端已登录并正常运行。**
2.  **启动代理脚本：**
    打开命令行工具 (CMD 或 PowerShell)，导航到脚本所在目录，然后运行：
    ```bash
    python qmt_data_agent.py
    ```
    您应该会看到服务器启动的日志信息，包括监听的地址和端口。

3.  **日志文件:**
    代理的运行日志会输出到控制台，并同时记录在与脚本同目录下的 `qmt_data_agent.log` 文件中。

## 持久化运行 (作为 Windows 服务 - 推荐)

为了确保代理服务在系统重启后依然能够自动运行，并能在后台稳定工作，建议将其注册为 Windows 服务。可以使用 `NSSM (Non-Sucking Service Manager)` 工具。

1.  **下载 NSSM:** 从 [NSSM 官网](https://nssm.cc/download) 下载最新版本。
2.  **安装服务:**
    *   将 `nssm.exe` 放置到一个合适的目录 (例如 `C:\NSSM\`)。
    *   以管理员身份打开命令行。
    *   执行以下命令安装服务 (请根据您的实际路径修改)：
        ```bash
        C:\NSSM\nssm.exe install ProjectArgusQMTDataAgent
        ```
    *   在弹出的 NSSM 服务编辑器中：
        *   **Application Tab:**
            *   **Path:** 浏览到您的 Python 解释器路径 (例如 `C:\Python311\python.exe` 或虚拟环境中的 `\.venv\Scripts\python.exe`)。
            *   **Startup directory:** 浏览到 `qmt_data_agent.py` 脚本所在的目录 (例如 `C:\project-argus-qmt-agent\`)。
            *   **Arguments:** 填写脚本名称 `qmt_data_agent.py`。
        *   **Environment Tab (可选，如果需要设置端口):**
            *   添加环境变量：`QMT_DATA_AGENT_PORT=8001` (替换为您希望的端口)。
        *   **Details Tab:** 可以设置服务的显示名称和描述。
        *   **I/O Tab (可选):** 可以配置标准输出和错误输出的重定向，但脚本本身已包含日志文件功能。
        *   **Shutdown Tab:** 确保 "Generate control-C" 被选中，以便正常关闭Python应用。
    *   点击 "Install service"。
3.  **启动服务:**
    ```bash
    C:\NSSM\nssm.exe start ProjectArgusQMTDataAgent
    ```
    或者通过 Windows 服务管理器 (services.msc) 启动。

## API 接口说明

本代理提供符合 OpenAPI (Swagger) 规范的 RESTful API。具体的API接口定义、参数及响应结构与 `doc/system_design.md` 中“接口规范”部分所述一致，并通过 FastAPI 应用在 `/docs` 路径下提供自动生成的 OpenAPI 文档。

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

## 未来潜力: MCP (Model Context Protocol) 服务器

本项目所基于的 `xtquantai` (https://github.com/dfkai/xtquantai) 项目的核心是一个 MCP 服务器。这意味着，除了当前 Project Argus 使用的直接 HTTP API 模式外，`xtquantai` 还可以配置为 MCP 服务器模式运行。

MCP 模式允许与兼容的 AI 工具（例如 Cursor AI 编辑器或其他支持该协议的AI应用）进行集成，从而可以通过自然语言或特定协议指令与 miniQMT 进行交互，例如：

*   直接从 AI 助手中查询 QMT 数据。
*   指令 QMT 生成图表并在客户端显示。
*   未来可能扩展到更复杂的AI辅助分析或交易指令。

如果需要启用和配置 `xtquantai` 的 MCP 服务器功能，请参考其官方 GitHub 仓库的完整文档。这为 Project Argus 或其他相关系统未来的智能化扩展提供了基础。

## 贡献

欢迎提交问题 (Issues) 和拉取请求 (Pull Requests)。

## 许可证

本项目基于 `xtquantai`，其采用 MIT 许可证。本代理服务的代码同样遵循 MIT 许可证。
