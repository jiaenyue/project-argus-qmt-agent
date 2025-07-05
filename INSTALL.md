# 安装指南 - xtquantai

本指南提供详细步骤，说明如何安装并运行 `xtquantai` 数据代理服务。

## 先决条件

*   **Windows 操作系统:** `xtquant` 通常依赖于 Windows 环境下的 miniQMT 客户端。
*   **Python:** 版本 3.11 或更高。您可以使用 `pyenv` 管理 Python 版本，或从 [python.org](https://www.python.org/downloads/) 下载。
*   **miniQMT 客户端 (迅投量化交易终端):** 如果您打算使用实时的 `xtquant` 数据，则必须在同一台 Windows 机器上安装并运行 miniQMT。对于不依赖实时数据的测试或开发，使用模拟的 `xtdata` 可能已足够。
*   **`xtquant` 库:**
    *   此库通常随 miniQMT 客户端提供。如果环境中未找到 `xtquant`，应用程序会尝试从 PyPI 安装它，但 PyPI上的版本可能与您的 QMT 客户端版本不完全兼容，或缺少某些功能。
    *   **验证:** 在您的 Python 环境中，尝试执行 `python -c "from xtquant import xtdata; print(xtdata)"`。如果命令无错误运行，则表示 `xtquant` 可用。
    *   **`xtquant` 访问问题排查:** 如果导入失败，您可能需要：
        1.  将 QMT 安装目录下的 Python 库路径 (例如 `miniQMT安装路径\bin\Lib\site-packages`) 添加到系统的 `PYTHONPATH` 环境变量中。
        2.  或者，将 `xtquant` 文件夹从 QMT 的 Python 库路径复制到您当前 Python 环境的 `site-packages` 目录下。
        (如果遇到 `xtquant` 相关问题，请参阅主 `README.md` 文件获取更多信息。)
*   **(可选，用于 MCP Inspector 模式)** **Node.js 和 npx:** 如果您希望通过 `main.py --mode inspector` 使用 MCP Inspector 模式运行服务器，则需要安装它们。

## 安装步骤

1.  **克隆代码仓库:**
    ```bash
    git clone https://github.com/jiaenyue/project-argus-qmt-agent.git
    cd project-argus-qmt-agent
    ```

2.  **创建 Python 虚拟环境 (推荐):**
    在项目根目录下打开终端。
    ```bash
    python -m venv qmt_env
    ```
    *   激活虚拟环境:
        *   Windows CMD: `qmt_env\\Scripts\\activate.bat`
        *   Windows PowerShell: `.\\qmt_env\\Scripts\\Activate.ps1`
        *   Linux/macOS (如适用): `source qmt_env/bin/activate`

3.  **安装依赖:**
    激活虚拟环境后，安装所需的 Python 包：
    ```bash
    pip install .
    ```
    该命令会根据 `pyproject.toml` 文件安装依赖项，包括 `mcp`, `anyio`, 并会尝试安装 `xtquant`。

4.  **验证安装:**
    安装完成后，尝试运行测试以确保环境配置正确：
    ```bash
    python tests/test_server_direct.py
    ```
    所有测试应该通过。

## 运行服务

运行服务的主要方式是使用项目根目录下的 `main.py` 脚本。此脚本支持多种运行模式。

请确保您已导航到项目根目录，并已激活虚拟环境。

*   **自动模式 (推荐):**
    此模式会优先尝试使用 MCP Inspector (如果 Node.js/npx 可用)，否则将回退到直接模式。
    ```bash
    python main.py
    ```

*   **直接模式:**
    此模式直接运行 `xtquantai` 服务器。
    ```bash
    python main.py --mode direct
    ```
    您可以指定端口 (回退的 `server_direct.py` 默认为 8000，但 `src/xtquantai/server.py` 中的 MCP 服务器通常通过 MCP 配置管理端口)：
    ```bash
    python main.py --mode direct --port 8001
    ```
    *(注意: `main.py` 中的 `--port` 参数主要用于旧版 `server_direct.py` 回退。`src/xtquantai/server.py` 中的主 MCP 服务器的 HTTP 端口通常由 MCP 框架配置或管理)。*

*   **MCP Inspector 模式 (需要 Node.js 和 npx):**
    ```bash
    python main.py --mode inspector
    ```

如果您通过 `pip install .` 将包安装到全局或虚拟环境中，您可能也可以直接使用 `xtquantai` 命令 (这取决于您系统的 PATH 配置)：
```bash
xtquantai
```

服务启动后，会在控制台打印日志信息，表明服务已启动并准备好接受请求或连接。有关 API 端点的详细信息，请参阅主 `README.md`。
