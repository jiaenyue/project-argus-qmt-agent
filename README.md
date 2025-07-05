# Project Argus QMT Data Agent

本项目是一个在 Windows 环境下运行的 Python 服务，作为 Project Argus (或其他需要访问 miniQMT 数据的系统) 与 miniQMT (迅投量化交易客户端) 之间的数据代理。它利用 `xtquant` 库与本地运行的 miniQMT 客户端进行交互，并通过 HTTP(S) API 接口暴露数据服务。

本项目基于 [xtquantai](https://github.com/dfkai/xtquantai) 项目中的 `server_direct.py` 脚本进行修改和定制，专注于提供稳定可靠的数据接口。同时，`xtquantai` 项目本身支持 MCP (Model Context Protocol)，为未来与 AI 助手集成提供了潜力。

## 致谢 (Acknowledgements)

本项目基于 [xtquantai](https://github.com/dfkai/xtquantai) 项目进行修改和定制，并从中获得了许多有益的启发。我们对 `xtquantai` 项目的开发者表示衷心的感谢。

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
    *   将 Windows 平台的 miniQMT 依赖与上层数据处理系统（例如 Project Argus 的 Docker化/Linux环境）有效隔离。
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
2.  **详细安装与配置步骤:**
    请参阅 [安装指南 (INSTALL.md)](INSTALL.md) 获取详细的设置说明，包括：
    *   设置 Python 环境 (Python 3.11+)。
    *   创建 Python 虚拟环境 (例如 `qmt_env`)。
    *   从 `pyproject.toml` 安装依赖 (使用 `pip install .`)。
    *   验证 `xtquant` 的可访问性。
    *   （可选）为 `server_direct.py` (旧版回退服务) 配置端口环境变量 `QMT_DATA_AGENT_PORT`。

## 运行代理服务

按照 [安装指南 (INSTALL.md)](INSTALL.md) 中的说明安装和配置完成后，您可以使用项目根目录下的 `main.py` 脚本来运行服务。

1.  **确保 miniQMT 客户端已登录并正常运行 (如果使用实时数据)。**
2.  **激活您的 Python 虚拟环境 (例如 `qmt_env`)。**
3.  **导航到项目根目录并运行：**
    ```bash
    python main.py
    ```
    这将以自动模式启动服务（首先尝试 MCP Inspector，然后回退到直接模式）。您也可以指定模式：
    *   `python main.py --mode direct` (直接模式)
    *   `python main.py --mode inspector` (MCP Inspector 模式，需要 Node.js 和 npx)

    您应该能看到服务启动的日志信息。

4.  **日志文件:**
    服务主要将日志输出到控制台。旧版的 `server_direct.py` (作为回退使用时) 可能会创建 `qmt_data_agent.log` 文件，但主要的 MCP 服务 (`src/xtquantai/server.py`) 会将日志记录到标准输出。有关详细的日志配置 (尤其是在 MCP 环境中)，请参阅 MCP 相关文档或服务输出信息。
    原始项目关于日志的讨论可以在 [系统设计文档中的“日志记录和监控”部分 (`doc/system_design.md#5-日志记录和监控`)](doc/system_design.md#5-日志记录和监控) 找到。

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
        *   **Environment Tab (环境变量页，可选):** 如果 `server_direct.py` 作为回退机制被使用，且您需要为其指定特定端口，则可设置 `QMT_DATA_AGENT_PORT`。
    *   点击 "Install service" (安装服务)。
3.  **启动服务:**
    ```bash
    C:\NSSM\nssm.exe start ProjectArgusQMTDataAgent
    ```
    或者通过 Windows 服务管理器 (`services.msc`) 启动。

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

## 重要声明与风险提示 (Important Disclaimer and Risk Warning)

本项目为个人学习和技术研究目的创建，并非专业交易软件，**严禁用于任何真实的股票交易或其他金融活动**。用户基于本项目进行的任何操作（包括但不限于模拟交易、数据分析等）所导致的任何直接或间接损失，均由用户自行承担。项目作者及贡献者不对任何因使用或依赖本项目代码及信息而产生的损失负责。

## 贡献

欢迎提交问题 (Issues) 和拉取请求 (Pull Requests)。

## 许可证

本项目基于 `xtquantai`，其采用 MIT 许可证。本代理服务的代码同样遵循 MIT 许可证。
