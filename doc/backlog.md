# Project Argus QMT Data Agent: 优先级待办事项看板

本文档追踪 Project Argus QMT 数据代理服务的开发待办事项。事项根据优先级进行组织 (P0: 核心功能，必须实现；P1: 重要功能，应优先考虑；P2: 未来扩展功能)。每个事项都关联到相应的用户故事，并列出其主要依赖。

## P0: 核心数据接口实现 (依赖miniQMT客户端)

### 交易日历接口 (故事1.1)
**功能描述**  
提供交易日查询API，确保交易策略在正确日期执行  
**验收标准**  
1. 支持按市场、日期范围查询  
2. API响应时间 < 500ms  
3. 数据准确率 > 99.9%  
**依赖项**  
- 数据源: 本地运行的miniQMT客户端行情采集功能

### 股票列表接口 (故事1.4)
**功能描述**  
实现按板块查询股票列表功能  
**验收标准**  
1. 支持主流板块查询（沪深A股等）  
2. 包含完整股票代码和名称  
3. 支持分页查询  
**依赖项**  
- 数据源: 本地运行的miniQMT客户端
- 说明: Project Argus 的智能融合引擎可能会进一步处理或丰富此列表

### 合约信息接口 (故事1.5)
**功能描述**  
提供股票详细信息查询接口  
**验收标准**  
1. 包含市盈率、股息率等关键指标 (通过miniQMT获取，若QMT不直接提供部分财务指标，则此部分可能依赖Project Argus从Tushare等源整合)
2. 支持实时查询  
3. 字段完整度 > 95% (针对QMT可提供字段)
**依赖项**  
- 数据源: 本地运行的miniQMT客户端
- 说明: Project Argus 可能会从 Tushare 等其他数据源获取额外的财务数据进行补充

### 历史K线接口 (故事1.2)
**功能描述**  
提供多时间粒度历史K线数据  
**验收标准**  
1. 支持1m/1d/1w等多种粒度  
2. 数据覆盖近10年历史 (取决于QMT客户端提供的历史数据范围)
3. 包含复权价格选项  
**依赖项**  
- 数据源: 本地运行的miniQMT客户端
- 说明: Project Argus 的 Delta Lake 湖仓用于长期存储和分析这些数据

---

## P1: 日志记录和错误处理机制

### 全局异常处理
**功能描述**  
实现统一异常处理中间件  
**验收标准**  
1. 错误日志包含完整上下文  
2. 支持错误分级报警  
3. 错误响应标准化  
**依赖项**  
- 无

### 请求追踪系统
**功能描述**  
实现全链路请求追踪  
**验收标准**  
1. 支持跨服务追踪  
2. 保留7天追踪日志  
3. 可视化追踪路径  
**依赖项**  
- 日志存储: Elasticsearch

### 监控告警系统
**功能描述**  
实现系统健康度监控  
**验收标准**  
1. 关键指标监控覆盖率100%  
2. 支持多通道告警（邮件/短信）  
3. 告警响应时间 < 5分钟  
**依赖项**  
- 监控工具: Prometheus

---

## P2: MCP集成基础架构

### MCP服务器部署 (故事2.1)
**功能描述**  
部署xtquantai MCP服务器  
**验收标准**  
1. 支持基础MCP协议  
2. 文档完备的部署指南  
3. 可通过AI工具执行查询  
**依赖项**  
- 安全: Vault凭证管理

### AI助手集成 (故事2.1)
**功能描述**  
实现AI助手自然语言查询  
**验收标准**  
1. 支持3种以上查询类型  
2. 自然语言解析成功率>85%  
3. 结果可视化展示  
**依赖项**  
- MCP服务器部署

### 图表生成服务 (故事2.2)
**功能描述**  
实现AI驱动的图表生成  
**验收标准**  
1. 支持MA/MACD等指标  
2. 图表生成延迟 < 3s  
3. 支持自定义模板  
**依赖项**  
- AI助手集成

---

## 用户故事追溯
此表将看板中的事项与 `doc/user_story.md` 中定义的用户故事相关联。

| 故事ID | 功能点           | 优先级 | 状态   |
|--------|------------------|--------|--------|
| 1.1    | 交易日历接口     | P0     | 待开发 |
| 1.2    | 历史K线接口      | P0     | 待开发 |
| 1.4    | 股票列表接口     | P0     | 待开发 |
| 1.5    | 股票详情接口     | P0     | 待开发 |
| 2.1    | MCP服务器部署    | P2     | 待开发 |
| 2.1    | AI助手查询       | P2     | 待开发 |
| 2.2    | 图表生成服务     | P2     | 待开发 |