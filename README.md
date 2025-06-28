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

本代理主要提供以下 HTTP API 端点 (基于 `xtquantai/server_direct.py`):

*   `GET /api/list_tools`: 列出所有可用的工具/API端点。
*   `GET/POST /api/get_trading_dates?market=SH`: 获取指定市场的交易日期。
*   `GET/POST /api/get_stock_list?sector=沪深A股`: 获取指定板块的股票列表。
*   `GET/POST /api/get_instrument_detail?code=000001.SZ&iscomplete=false`: 获取股票详情。
*   `GET/POST /api/get_history_market_data?stock_list=000001.SZ&fields=time,open,close&period=1d&start_time=20230101&end_time=20231231`: 获取历史行情数据。
    *   `stock_list`: 股票代码，或多个代码以逗号分隔。
    *   `fields`: 需要的字段，以逗号分隔。
    *   `period`: 周期 (e.g., `1m`, `5m`, `1d`, `1wk`, `1mon`)。
    *   `start_time`, `end_time`: 开始/结束时间 (格式 `YYYYMMDD` 或 `YYYYMMDDHHMMSS`)。
    *   `count`: 数据点数量 (与 `start_time`/`end_time` 配合使用)。
    *   `dividend_type`: 复权类型 (`none`, `front`, `back`)。
    *   `fill_data`: 是否填充停牌期间数据。
*   `GET/POST /api/create_chart_panel?codes=000001.SZ&period=1d&indicator_name=MA...`: (QMT UI交互) 创建图表面板。
*   `GET/POST /api/create_custom_layout?codes=000001.SZ...`: (QMT UI交互) 创建自定义布局。

所有API成功时返回 `{"success": true, "data": ...}`，失败时返回 `{"success": false, "error": "...", "debug_info": "..."}`。

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
