# Project Argus QMT Data Agent: 用户故事

本文档定义了 Project Argus QMT 数据代理服务的用户故事。用户故事从不同项目角色的视角出发，描述了他们期望通过本服务实现的功能和价值。这些故事驱动着服务的设计和开发，确保其满足实际用户需求。用户故事被组织成不同的史诗 (Epics)，代表了主要的功能领域或开发阶段。

## 项目角色 (Personas)

*   **量化分析师 (Quantitative Analyst):** 数据的最终用户，追求数据的准确性、完整性、多维度和易用性，以构建可靠的交易策略。
*   **数据工程师 (Data Engineer):** 数据管道的建设者，关注数据流的效率、代码的健壮性和数据模型的正确性。
*   **DevOps工程师 / 运维工程师 (DevOps Engineer):** 系统的运维者，负责部署、自动化、监控和容灾，保障系统稳定运行。

---

### Epic 1: 数据代理服务核心场景
**目标:** 通过标准化API提供核心数据服务，支持交易系统、分析工具和监控系统的高效运作。
**可交付成果:** 稳定可靠的数据代理服务API，满足三类核心场景的数据需求。

*   **故事 1.1: 交易系统获取交易日历**
    *   **作为** 交易系统开发者，
    *   **我想要** 通过数据代理服务API获取准确的交易日历数据，
    *   **以便** 确保交易策略在正确的交易日执行。
    *   **API调用示例:**
        ```python
        # 调用交易日历API (对应 xtquant.xtdata.get_trading_dates 功能)
        import requests
        response = requests.get(
            "http://data-agent-service/trading_dates",
            params={"market": "SH", "start_date": "20250101", "end_date": "20251231"}
        )
        print(response.json())
        ```

*   **故事 1.2: 分析工具获取历史K线数据**
    *   **作为** 量化分析师，
    *   **我想要** 通过数据代理服务API获取历史K线数据，
    *   **以便** 进行策略回测和数据分析。
    *   **API调用示例:**
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

*   **故事 1.3: 监控系统获取实时合约信息**
    *   **作为** 运维工程师，
    *   **我想要** 通过数据代理服务API获取实时合约信息，
    *   **以便** 监控市场状态和系统健康状况。
    *   **API调用示例:**
        ```python
        # 调用实时合约API (对应 xtquant.xtdata.get_instrument_detail 功能)
        import requests
        response = requests.get(
            "http://data-agent-service/instrument_detail",
            params={"symbol": "600519.SH"}
        )
        print(response.json())
        ```

*   **故事 1.4: 获取板块股票列表**
    *   **作为** 策略研究员，
    *   **我想要** 通过数据代理服务API获取特定板块的股票列表，
    *   **以便** 快速构建投资组合和进行板块分析。
    *   **API调用示例:**
        ```python
        # 调用板块股票API (对应 xtquant.xtdata.get_stock_list_in_sector 功能)
        import requests
        response = requests.get(
            "http://data-agent-service/stock_list",
            params={"sector": "沪深A股"}
        )
        print(response.json())
        ```

*   **故事 1.5: 获取股票详情**
    *   **作为** 投资经理，
    *   **我想要** 通过数据代理服务API获取股票的详细信息，
    *   **以便** 深入了解标的资产的基本面情况。
    *   **API调用示例:**
        ```python
        # 调用股票详情API (对应 xtquant.xtdata.get_instrument_detail 功能)
        import requests
        response = requests.get(
            "http://data-agent-service/instrument_detail",
            params={"symbol": "600519.SH"}
        )
        print(response.json())
        ```

*   **故事 1.6: 获取最新行情数据**
    *   **作为** 交易员，
    *   **我想要** 通过数据代理服务API获取股票的最新行情数据，
    *   **以便** 实时监控市场动态和交易机会。
    *   **API调用示例:**
        ```python
        # 调用最新行情API (对应 xtquant.xtdata.get_latest_market_data 功能)
        import requests
        response = requests.get(
            "http://data-agent-service/latest_market",
            params={"symbols": "600519.SH,000001.SZ"}
        )
        print(response.json())
        ```

*   **故事 1.7: 获取完整行情数据**
    *   **作为** 量化开发工程师，
    *   **我想要** 通过数据代理服务API获取股票的完整行情数据，
    *   **以便** 进行深度市场分析和策略开发。
    *   **API调用示例:**
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

### Epic 2: (未来规划) AI集成与智能化扩展
**目标:** 探索并利用 `xtquantai` 项目的 Model Context Protocol (MCP) 特性，实现与AI工具的集成，提升数据分析与操作的智能化水平。此举旨在降低数据获取和初步分析的门槛，使得分析师可以将更多精力聚焦于策略研发本身，并可能催生新的数据交互和分析范式。

*   **故事 2.1: 通过AI助手查询QMT数据**
    *   **作为** 一名高级量化分析师，
    *   **我想要** 通过AI助手（如Cursor或自定义AI应用）使用自然语言或特定指令，直接查询`Windows QMT Data Agent`（运行在MCP模式下）获取miniQMT中的数据，
    *   **以便** 更快速、更便捷地进行探索性数据分析和策略思路验证，而无需编写复杂的查询脚本。
    *   **验收标准:**
        1.  `Windows QMT Data Agent`能够以MCP服务器模式成功启动并运行。
        2.  AI助手能够通过MCP协议连接到该Agent。
        3.  可以通过AI助手成功执行至少三种不同类型的QMT数据查询（例如：获取某股票的最新行情、查询某日期区间的历史K线、获取某板块的成分股）。
        4.  查询结果在AI助手中正确展示。
        5.  相关操作和交互过程有清晰的文档记录。

*   **故事 2.2: AI辅助的图表生成**
    *   **作为** 一名策略研究员，
    *   **我想要** AI助手能够调用`Windows QMT Data Agent`（MCP模式）的图表生成功能，
    *   **以便** 快速可视化特定股票的技术指标（如MA, MACD），辅助我进行技术分析。
    *   **验收标准:**
        1.  AI助手可以成功调用Agent的`create_chart_panel`或类似功能。
        2.  QMT客户端能够根据指令正确显示生成的图表。
        3.  支持至少两种常用技术指标的图表生成。

---
### Epic 3: (相关系统规划) 交易执行服务核心场景
**注意:** 此 Epic 描述的是一个独立的交易执行代理服务 (Trade Agent Service)，它与本 QMT 数据代理服务 (QMT Data Agent) 是分离但相关的组件。QMT 数据代理专注于数据查询，而交易执行服务专注于处理交易指令。两者可能共同作为 Project Argus 的组成部分。

**目标:** 提供稳定可靠的交易执行功能，支持策略交易和资产管理。
**可交付成果:** 高性能的交易执行服务API (例如，通过 `http://trade-agent-service` 访问)。

*   **故事 3.1: 异步下单**
    *   **作为** 交易员，
    *   **我想要** 通过交易执行服务API异步下单，
    *   **以便** 在收到下单结果前可以继续执行其他操作。
    *   **API调用示例:**
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

*   **故事 3.2: 异步撤单**
    *   **作为** 交易员，
    *   **我想要** 通过交易执行服务API异步撤单，
    *   **以便** 在收到撤单结果前可以继续执行其他操作。
    *   **API调用示例:**
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

*   **故事 3.3: 资产查询**
    *   **作为** 资产管理员，
    *   **我想要** 通过交易执行服务API查询实时资产，
    *   **以便** 监控账户资金情况。
    *   **API调用示例:**
        ```python
        # 查询资产API
        import requests
        response = requests.get(
            "http://trade-agent-service/asset",
            params={"account_id": "1000000365"}
        )
        print(response.json())
        ```

*   **故事 3.4: 持仓查询**
    *   **作为** 风险控制员，
    *   **我想要** 通过交易执行服务API查询实时持仓，
    *   **以便** 监控账户风险敞口。
    *   **API调用示例:**
        ```python
        # 查询持仓API
        import requests
        response = requests.get(
            "http://trade-agent-service/positions",
            params={"account_id": "1000000365"}
        )
        print(response.json())
        ```

*   **故事 3.5: 委托查询**
    *   **作为** 交易监控员，
    *   **我想要** 通过交易执行服务API查询当日委托，
    *   **以便** 跟踪订单执行状态。
    *   **API调用示例:**
        ```python
        # 查询委托API
        import requests
        response = requests.get(
            "http://trade-agent-service/orders",
            params={"account_id": "1000000365"}
        )
        print(response.json())
        ```

*   **故事 3.6: 成交查询**
    *   **作为** 结算专员，
    *   **我想要** 通过交易执行服务API查询当日成交，
    *   **以便** 进行每日交易结算。
    *   **API调用示例:**
        ```python
        # 查询成交API
        import requests
        response = requests.get(
            "http://trade-agent-service/trades",
            params={"account_id": "1000000365"}
        )
        print(response.json())
        ```