# Project Argus QMT Data Agent - 文档索引

## 1. 文档概览

本项目提供完整的文档体系，涵盖产品需求、技术架构、教学指南和项目管理等各个方面。

## 2. 核心文档

### 2.1 产品与架构文档

| 文档名称 | 文件路径 | 描述 |
|----------|----------|------|
| 产品需求文档 | `.trae/documents/product_requirements.md` | 项目整体功能需求和设计规范 |
| 技术架构文档 | `.trae/documents/technical_architecture.md` | 系统架构设计和技术选型 |
| 项目总结 | `.trae/documents/project_summary.md` | 项目概览和功能介绍 |
| 项目进度报告 | `.trae/documents/project_progress_report.md` | 详细的项目进度和完成状态 |

### 2.2 教学文档体系

| 文档名称 | 文件路径 | 描述 |
|----------|----------|------|
| 教学体系需求文档 | `.trae/documents/tutorial_system_requirements.md` | 教学文档体系的功能需求 |
| 教学体系架构文档 | `.trae/documents/tutorial_system_architecture.md` | 教学文档的技术架构设计 |
| 教学索引 | `tutorials/TUTORIAL_INDEX.md` | 教学模块导航和学习路径 |
| 验证报告 | `tutorials/VALIDATION_REPORT.md` | 教学文档质量验证结果 |

## 3. 技术文档

### 3.1 架构设计
- [技术架构文档](technical_architecture_document.md) - 系统整体技术架构设计
- [教学体系架构文档](tutorial_system_architecture.md) - 教学文档体系的技术架构

### 3.2 安全策略
- [内部系统安全策略](internal_system_security_policy.md) - 内部系统安全策略和认证决策

### 3.3 开发指南
- [部署运维指南](deployment_operations_guide.md) - 系统部署和运维操作指南

## 4. 教学模块详情

### 3.1 Python 脚本教程

位置：`tutorials/` 目录

| 模块 | 文件名 | 功能描述 |
|------|--------|----------|
| 交易日历 | `01_trading_dates.py` | 获取交易日历数据的完整教程 |
| 历史K线 | `02_hist_kline.py` | 历史K线数据查询和处理 |
| 合约详情 | `03_instrument_detail.py` | 股票合约信息查询 |
| 股票列表 | `04_stock_list.py` | 板块股票列表获取 |
| 最新行情 | `06_latest_market.py` | 实时行情数据获取 |
| 完整行情 | `07_full_market.py` | 完整市场数据查询 |

### 3.2 Jupyter Notebook 教程

位置：`tutorials/notebooks/` 目录

| 模块 | 文件名 | 功能描述 |
|------|--------|----------|
| 交易日历 | `01_trading_dates.ipynb` | 交互式交易日历教程 |
| 历史K线 | `02_hist_kline.ipynb` | 交互式K线数据分析 |
| 合约详情 | `03_instrument_detail.ipynb` | 交互式合约信息查询 |
| 股票列表 | `04_stock_list.ipynb` | 交互式股票列表操作 |
| 最新行情 | `06_latest_market.ipynb` | 交互式实时行情分析 |
| 完整行情 | `07_full_market.ipynb` | 交互式完整行情数据处理 |

### 3.3 支持文档

| 文档名称 | 文件路径 | 描述 |
|----------|----------|------|
| 通用工具库 | `tutorials/common.py` | 教学中使用的通用函数和工具 |
| 教程说明 | `tutorials/README.md` | 教学体系使用指南 |
| 故障排查 | `tutorials/TROUBLESHOOTING.md` | 常见问题和解决方案 |

## 4. 文档使用指南

### 4.1 新用户入门

1. **开始学习**：阅读 `tutorials/TUTORIAL_INDEX.md` 了解学习路径
2. **环境准备**：参考 `tutorials/README.md` 配置开发环境
3. **选择格式**：
   - 偏好代码编辑器：使用 `.py` 文件
   - 偏好交互式学习：使用 `.ipynb` 文件
4. **按序学习**：从 `01_trading_dates` 开始，逐步学习各个模块

### 4.2 开发者参考

1. **技术架构**：查看 `.trae/documents/technical_architecture.md`
2. **API设计**：参考 `.trae/documents/product_requirements.md`
3. **项目状态**：查看 `.trae/documents/project_progress_report.md`
4. **代码示例**：使用 `tutorials/` 目录下的教学代码

### 4.3 项目管理

1. **项目概览**：查看 `.trae/documents/project_summary.md`
2. **进度跟踪**：参考 `.trae/documents/project_progress_report.md`
3. **需求管理**：使用 `.trae/documents/product_requirements.md`
4. **质量保证**：参考 `tutorials/VALIDATION_REPORT.md`

## 5. 文档维护

### 5.1 更新频率

- **教学文档**：功能更新时同步更新
- **技术文档**：架构变更时更新
- **项目文档**：每周更新进度报告
- **索引文档**：新增文档时更新

### 5.2 质量标准

- **准确性**：所有代码示例必须可执行
- **完整性**：覆盖所有核心功能
- **一致性**：文档格式和风格统一
- **时效性**：与代码实现保持同步

### 5.3 反馈机制

- **问题报告**：通过 `tutorials/TROUBLESHOOTING.md` 收集
- **改进建议**：在项目进度报告中跟踪
- **用户反馈**：通过教学验证报告评估

## 6. 技术支持

### 6.1 常见问题

参考 `tutorials/TROUBLESHOOTING.md` 获取：
- 环境配置问题
- API连接问题
- 数据格式问题
- 性能优化建议

### 6.2 学习资源

- **教学索引**：`tutorials/TUTORIAL_INDEX.md`
- **验证报告**：`tutorials/VALIDATION_REPORT.md`
- **最佳实践**：各教学模块中的实践指导

### 6.3 开发支持

- **架构设计**：`.trae/documents/technical_architecture.md`
- **需求规范**：`.trae/documents/product_requirements.md`
- **项目状态**：`.trae/documents/project_progress_report.md`

---

**文档版本**: v1.0  
**最后更新**: 2025年1月  
**维护团队**: Project Argus 开发团队