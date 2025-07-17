# Project Argus QMT Data Agent: 用户故事

本文档定义了 Project Argus QMT 数据代理服务的用户故事。用户故事从不同项目角色的视角出发，描述了他们期望通过本服务实现的功能和价值。这些故事驱动着服务的设计和开发，确保其满足实际用户需求。用户故事被组织成不同的史诗 (Epics)，代表了主要的功能领域或开发阶段。

## 项目角色 (Personas)

- **量化分析师 (Quantitative Analyst):** 数据的最终用户，追求数据的准确性、完整性、多维度和易用性，以构建可靠的交易策略。
- **数据工程师 (Data Engineer):** 数据管道的建设者，关注数据流的效率、代码的健壮性和数据模型的正确性。
- **DevOps 工程师 / 运维工程师 (DevOps Engineer):** 系统的运维者，负责部署、自动化、监控和容灾，保障系统稳定运行。

---

### Epic 1: 数据代理服务核心场景

**目标:** 通过标准化 API 提供核心数据服务，支持交易系统、分析工具和监控系统的高效运作。
**可交付成果:** 稳定可靠的数据代理服务 API，满足三类核心场景的数据需求。
**进度状态:** 🟢 **85% 完成** - 核心 API 已实现，部分功能需要优化

- **故事 1.1: 交易系统获取交易日历** ✅ **已完成**

  - **作为** 交易系统开发者，
  - **我想要** 通过数据代理服务 API 获取准确的交易日历数据，
  - **以便** 确保交易策略在正确的交易日执行。
  - **API 调用示例:**
    支持 MCP 工具调用和 HTTP REST API 两种方式

    ### 调用方式一：HTTP REST API

    ```python
    import requests
    response = requests.get(
        "http://localhost:8000/api/get_trading_dates",
        params={"market": "SH", "start_date": "20250101", "end_date": "20250107"}
    )
    print(response.json())
    ```

    ### 调用方式二：MCP 工具调用

    ```python
    # 通过MCP协议调用
    result = await mcp_client.call("get_trading_dates", market="SH", start_date="20250101", end_date="20250107")
    print(result)
    ```

    # Expected response example:

    # {

    # "success": true,

    # "data": ["20250101", "20250102", "20250103", "20250106", "20250107"]

    # }

- **故事 1.2: 分析工具获取历史 K 线数据** ✅ **已完成**

  - **作为** 量化分析师，
  - **我想要** 通过数据代理服务 API 获取历史 K 线数据，
  - **以便** 进行策略回测和数据分析。
  - **API 调用示例:**
    ```python
    # 调用历史K线API (对应 xtquant.xtdata.get_history_market_data 功能)
    import requests
    params = {
        "symbol": "600519.SH",
        "start_date": "20230101",
        "end_date": "20231231",
        "frequency": "1d"
    }
    response = requests.get("http://data-agent-service/hist_kline", params=params)
    print(response.json())
    ```

- **故事 1.3: 监控系统获取实时合约信息** ✅ **已完成**

  - **作为** 运维工程师，
  - **我想要** 通过数据代理服务 API 获取实时合约信息，
  - **以便** 监控市场状态和系统健康状况。
  - **API 调用示例:**
    ```python
    # 调用实时合约API (对应 xtquant.xtdata.get_instrument_detail 功能)
    import requests
    response = requests.get(
        "http://data-agent-service/instrument_detail",
        params={"symbol": "600519.SH"}
    )
    print(response.json())
    ```

- **故事 1.4: 获取板块股票列表** ✅ **已完成**

  - **作为** 策略研究员，
  - **我想要** 通过数据代理服务 API 获取特定板块的股票列表，
  - **以便** 快速构建投资组合和进行板块分析。
  - **API 调用示例:**
    ```python
    # 调用板块股票API (对应 xtquant.xtdata.get_stock_list_in_sector 功能)
    import requests
    response = requests.get(
        "http://data-agent-service/stock_list",
        params={"sector": "沪深A股"}
    )
    print(response.json())
    ```

- **故事 1.5: 获取股票详情** ✅ **已完成**

  - **作为** 投资经理，
  - **我想要** 通过数据代理服务 API 获取股票的详细信息，
  - **以便** 深入了解标的资产的基本面情况。
  - **API 调用示例:**
    ```python
    # 调用股票详情API (对应 xtquant.xtdata.get_instrument_detail 功能)
    import requests
    response = requests.get(
        "http://data-agent-service/instrument_detail",
        params={"symbol": "600519.SH"}
    )
    print(response.json())
    ```

- **故事 1.6: 获取最新行情数据** ✅ **已完成**

  - **作为** 交易员，
  - **我想要** 通过数据代理服务 API 获取股票的最新行情数据，
  - **以便** 实时监控市场动态和交易机会。
  - **API 调用示例:**
    ```python
    # 调用最新行情API (对应 xtquant.xtdata.get_latest_market_data 功能)
    import requests
    response = requests.get(
        "http://data-agent-service/latest_market",
        params={"symbols": "600519.SH,000001.SZ"}
    )
    print(response.json())
    ```

- **故事 1.7: 获取完整行情数据** ✅ **已完成**
  - **作为** 量化开发工程师，
  - **我想要** 通过数据代理服务 API 获取股票的完整行情数据，
  - **以便** 进行深度市场分析和策略开发。
  - **API 调用示例:**
    ```python
    # 调用完整行情API (对应 xtquant.xtdata.get_full_market_data 功能)
    import requests
    response = requests.get(
        "http://data-agent-service/full_market",
        params={"symbol": "600519.SH", "fields": "open,high,low,close,volume"}
    )
    print(response.json())
    ```

---

### Epic 2: (未来规划) AI 集成与智能化扩展

**目标:** 探索并利用 `xtquantai` 项目的 Model Context Protocol (MCP) 特性，实现与 AI 工具的集成，提升数据分析与操作的智能化水平。此举旨在降低数据获取和初步分析的门槛，使得分析师可以将更多精力聚焦于策略研发本身，并可能催生新的数据交互和分析范式。

- **故事 2.1: 通过 AI 助手查询 QMT 数据**

  - **作为** 一名高级量化分析师，
  - **我想要** 通过 AI 助手（如 Cursor 或自定义 AI 应用）使用自然语言或特定指令，直接查询`Windows QMT Data Agent`（运行在 MCP 模式下）获取 miniQMT 中的数据，
  - **以便** 更快速、更便捷地进行探索性数据分析和策略思路验证，而无需编写复杂的查询脚本。
  - **验收标准:**
    1.  `Windows QMT Data Agent`能够以 MCP 服务器模式成功启动并运行。
    2.  AI 助手能够通过 MCP 协议连接到该 Agent。
    3.  可以通过 AI 助手成功执行至少三种不同类型的 QMT 数据查询（例如：获取某股票的最新行情、查询某日期区间的历史 K 线、获取某板块的成分股）。
    4.  查询结果在 AI 助手中正确展示。
    5.  相关操作和交互过程有清晰的文档记录。

- **故事 2.2: AI 辅助的图表生成**
  - **作为** 一名策略研究员，
  - **我想要** AI 助手能够调用`Windows QMT Data Agent`（MCP 模式）的图表生成功能，
  - **以便** 快速可视化特定股票的技术指标（如 MA, MACD），辅助我进行技术分析。
  - **验收标准:**
    1.  AI 助手可以成功调用 Agent 的`create_chart_panel`或类似功能。
    2.  QMT 客户端能够根据指令正确显示生成的图表。
    3.  支持至少两种常用技术指标的图表生成。

---

### Epic 4: 开发者教程与文档支持

**目标:** 为开发者提供完整的 API 使用教程和最佳实践指导，降低集成门槛，提升开发效率。
**可交付成果:** 完整的教程文档体系，涵盖所有核心 API 的使用方法和实际应用场景。
**进度状态:** 🟢 **90% 完成** - 主要教程已完成，需要完善错误处理和最佳实践

- **故事 4.1: 交易日历 API 使用教程** ✅ **已完成**

  - **作为** 一名新手开发者，
  - **我想要** 有详细的交易日历 API 使用教程，包含参数说明、调用示例和错误处理，
  - **以便** 快速掌握如何在我的应用中集成交易日历功能。
  - **教程文件:** `tutorials/01_trading_dates.py`
  - **涵盖内容:**
    - API 参数详细说明
    - HTTP REST API 调用方式
    - xtdata 本地库调用方式
    - 实际应用场景（回测系统日期验证）
    - 错误处理与注意事项

- **故事 4.2: 历史 K 线 API 使用教程** ✅ **已完成**

  - **作为** 一名量化开发者，
  - **我想要** 有完整的历史 K 线数据获取教程，包含数据格式转换和性能优化建议，
  - **以便** 高效地获取和处理历史行情数据用于策略回测。
  - **教程文件:** `tutorials/02_hist_kline.py`
  - **涵盖内容:**
    - 多时间粒度 K 线数据获取
    - Pandas DataFrame 数据处理
    - 性能优化建议
    - 常见问题 FAQ

- **故事 4.3: 合约详情 API 使用教程** ✅ **已完成**

  - **作为** 一名投资分析师，
  - **我想要** 学习如何获取股票的详细信息，包括基本面数据和实时行情，
  - **以便** 进行全面的投资分析和风险评估。
  - **教程文件:** `tutorials/03_instrument_detail.py`
  - **涵盖内容:**
    - 合约基本信息获取
    - 实时行情数据解析
    - 数据字段说明

- **故事 4.4: 板块股票列表 API 使用教程** ✅ **已完成**

  - **作为** 一名策略研究员，
  - **我想要** 了解如何获取不同板块的股票列表，
  - **以便** 构建行业轮动策略和板块分析模型。
  - **教程文件:** `tutorials/04_stock_list.py`
  - **涵盖内容:**
    - 板块分类和代码
    - 股票列表获取方法
    - 数据格式和字段说明

- **故事 4.5: 最新行情 API 使用教程** ✅ **已完成**

  - **作为** 一名实时交易开发者，
  - **我想要** 掌握如何获取多只股票的最新行情数据，
  - **以便** 构建实时监控和预警系统。
  - **教程文件:** `tutorials/06_latest_market.py`
  - **涵盖内容:**
    - 批量行情数据获取
    - 实时数据处理
    - 监控系统集成示例

- **故事 4.6: 完整行情 API 使用教程** ✅ **已完成**

  - **作为** 一名高级量化开发者，
  - **我想要** 学习如何获取股票的完整行情数据，包括自定义字段选择，
  - **以便** 进行深度市场分析和复杂策略开发。
  - **教程文件:** `tutorials/07_full_market.py`
  - **涵盖内容:**
    - 完整行情数据获取
    - 字段自定义选择
    - 高级数据分析应用

- **故事 4.7: 系统运维指南** ✅ **已完成**

  - **作为** 一名运维工程师，
  - **我想要** 有详细的系统部署和运维指南，
  - **以便** 确保 QMT 数据代理服务的稳定运行和故障快速恢复。
  - **教程文件:** `tutorials/运维指南.md`
  - **涵盖内容:**
    - 部署最佳实践
    - 监控和告警配置
    - 故障排查指南
    - 性能调优建议

- **故事 4.8: 数据下载工具使用指南** ✅ **已完成**
  - **作为** 一名数据分析师，
  - **我想要** 有便捷的数据批量下载工具和使用说明，
  - **以便** 快速获取历史数据进行离线分析。
  - **教程文件:** `tutorials/download_data.py`
  - **涵盖内容:**
    - 批量数据下载
    - 数据存储格式
    - 下载进度监控

---

### Epic 3: (相关系统规划) 交易执行服务核心场景

**注意:** 此 Epic 描述的是一个独立的交易执行代理服务 (Trade Agent Service)，它与本 QMT 数据代理服务 (QMT Data Agent) 是分离但相关的组件。QMT 数据代理专注于数据查询，而交易执行服务专注于处理交易指令。两者可能共同作为 Project Argus 的组成部分。

**目标:** 提供稳定可靠的交易执行功能，支持策略交易和资产管理。
**可交付成果:** 高性能的交易执行服务 API (例如，通过 `http://trade-agent-service` 访问)。

- **故事 3.1: 异步下单**

  - **作为** 交易员，
  - **我想要** 通过交易执行服务 API 异步下单，
  - **以便** 在收到下单结果前可以继续执行其他操作。
  - **API 调用示例:**
    ```python
    # 异步下单API
    import requests
    data = {
        "account_id": "1000000365",
        "stock_code": "600519.SH",
        "order_type": "STOCK_BUY",
        "order_volume": 100,
        "price_type": "FIX_PRICE",
        "price": 180.0
    }
    response = requests.post("http://trade-agent-service/order_async", json=data)
    print(response.json())
    ```

- **故事 3.2: 异步撤单**

  - **作为** 交易员，
  - **我想要** 通过交易执行服务 API 异步撤单，
  - **以便** 在收到撤单结果前可以继续执行其他操作。
  - **API 调用示例:**
    ```python
    # 异步撤单API
    import requests
    data = {
        "account_id": "1000000365",
        "order_id": 123456
    }
    response = requests.post("http://trade-agent-service/cancel_order_async", json=data)
    print(response.json())
    ```

- **故事 3.3: 资产查询**

  - **作为** 资产管理员，
  - **我想要** 通过交易执行服务 API 查询实时资产，
  - **以便** 监控账户资金情况。
  - **API 调用示例:**
    ```python
    # 查询资产API
    import requests
    response = requests.get(
        "http://trade-agent-service/asset",
        params={"account_id": "1000000365"}
    )
    print(response.json())
    ```

- **故事 3.4: 持仓查询**

  - **作为** 风险控制员，
  - **我想要** 通过交易执行服务 API 查询实时持仓，
  - **以便** 监控账户风险敞口。
  - **API 调用示例:**
    ```python
    # 查询持仓API
    import requests
    response = requests.get(
        "http://trade-agent-service/positions",
        params={"account_id": "1000000365"}
    )
    print(response.json())
    ```

- **故事 3.5: 委托查询**

  - **作为** 交易监控员，
  - **我想要** 通过交易执行服务 API 查询当日委托，
  - **以便** 跟踪订单执行状态。
  - **API 调用示例:**
    ```python
    # 查询委托API
    import requests
    response = requests.get(
        "http://trade-agent-service/orders",
        params={"account_id": "1000000365"}
    )
    print(response.json())
    ```

- **故事 3.6: 成交查询**
  - **作为** 结算专员，
  - **我想要** 通过交易执行服务 API 查询当日成交，
  - **以便** 进行每日交易结算。
  - **API 调用示例:**
    ```python
    # 查询成交API
    import requests
    response = requests.get(
        "http://trade-agent-service/trades",
        params={"account_id": "1000000365"}
    )
    print(response.json())
    ```
