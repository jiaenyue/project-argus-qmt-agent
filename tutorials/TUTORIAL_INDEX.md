# Project Argus QMT 数据代理服务 - 教学文档索引

## 📚 教学体系概览

本教学体系基于 Project Argus QMT 数据代理服务，提供完整的 Python 和 Jupyter Notebook 教学文档。每个教学模块都包含可执行的代码示例和详细的步骤说明。

## 🗂️ 目录结构

```
tutorials/
├── *.py                    # Python 教学文件（可直接执行）
├── notebooks/              # Jupyter Notebook 文件
│   └── *.ipynb            # 对应的 Notebook 版本
├── common.py              # 通用工具和配置
├── README.md              # 详细使用说明
├── TUTORIAL_INDEX.md      # 本索引文件
└── TROUBLESHOOTING.md     # 故障排除指南
```

## 📖 教学模块列表

### 1. 交易日历 API (01_trading_dates)
- **Python 文件**: `01_trading_dates.py`
- **Notebook 文件**: `notebooks/01_trading_dates.ipynb`
- **学习目标**: 掌握交易日历 API 的使用方法
- **核心功能**: 
  - 获取交易日历数据
  - 多市场交易日历对比
  - xtdata 本地库调用
  - 错误处理和降级机制
- **难度等级**: ⭐⭐☆☆☆ (初级)
- **预计学习时间**: 30-45 分钟

### 2. 历史K线数据 (02_hist_kline)
- **Python 文件**: `02_hist_kline.py`
- **Notebook 文件**: `notebooks/02_hist_kline.ipynb`
- **学习目标**: 学习历史K线数据的获取和处理
- **核心功能**:
  - 获取股票历史K线数据
  - 数据格式化和可视化
  - 性能监控和优化
  - 批量数据处理
- **难度等级**: ⭐⭐⭐☆☆ (中级)
- **预计学习时间**: 45-60 分钟

### 3. 合约详情信息 (03_instrument_detail)
- **Python 文件**: `03_instrument_detail.py`
- **Notebook 文件**: `notebooks/03_instrument_detail.ipynb`
- **学习目标**: 掌握股票合约详情信息的获取
- **核心功能**:
  - 获取单个股票详细信息
  - 批量获取股票信息
  - 股票代码格式验证
  - 错误处理机制
- **难度等级**: ⭐⭐☆☆☆ (初级)
- **预计学习时间**: 30-40 分钟

### 4. 股票列表和板块信息 (04_stock_list)
- **Python 文件**: `04_stock_list.py`
- **Notebook 文件**: `notebooks/04_stock_list.ipynb`
- **学习目标**: 学习板块分类和股票列表的获取
- **核心功能**:
  - 下载板块数据
  - 获取板块列表
  - 获取板块成分股
  - 板块表现分析
- **难度等级**: ⭐⭐⭐☆☆ (中级)
- **预计学习时间**: 50-70 分钟

### 5. 最新行情数据 (06_latest_market)
- **Python 文件**: `06_latest_market.py`
- **Notebook 文件**: `notebooks/06_latest_market.ipynb`
- **学习目标**: 掌握实时行情数据的获取和处理
- **核心功能**:
  - 获取最新行情数据
  - 实时数据处理
  - 预警规则设置
  - 数据监控和分析
- **难度等级**: ⭐⭐⭐⭐☆ (高级)
- **预计学习时间**: 60-80 分钟

### 6. 完整行情数据 (07_full_market)
- **Python 文件**: `07_full_market.py`
- **Notebook 文件**: `notebooks/07_full_market.ipynb`
- **学习目标**: 学习完整行情数据的获取和深度分析
- **核心功能**:
  - 获取完整行情数据
  - 深度行情分析
  - 市场统计功能
  - 板块统计分析
- **难度等级**: ⭐⭐⭐⭐⭐ (专家级)
- **预计学习时间**: 80-100 分钟

## 🚀 学习路径建议

### 初学者路径
1. **环境准备**: 阅读 `README.md`，配置开发环境
2. **基础入门**: 从 `01_trading_dates` 开始，掌握基本 API 调用
3. **数据获取**: 学习 `03_instrument_detail`，了解股票信息获取
4. **历史数据**: 进入 `02_hist_kline`，学习历史数据处理
5. **板块分析**: 学习 `04_stock_list`，掌握板块数据分析

### 进阶学习路径
1. **实时数据**: 学习 `06_latest_market`，掌握实时数据处理
2. **深度分析**: 进入 `07_full_market`，学习完整行情分析
3. **综合应用**: 结合多个模块，构建完整的数据分析系统

## 💻 使用方式

### Python 文件执行
```bash
# 直接运行 Python 教学文件
python tutorials/01_trading_dates.py
```

### Jupyter Notebook 使用
```bash
# 启动 Jupyter Notebook
jupyter notebook tutorials/notebooks/

# 或使用 JupyterLab
jupyter lab tutorials/notebooks/
```

### 文件转换（开发者）
```bash
# 将 Python 文件转换为 Notebook
jupytext --to ipynb tutorials/01_trading_dates.py --output tutorials/notebooks/01_trading_dates.ipynb

# 将 Notebook 转换为 Python 文件
jupytext --to py tutorials/notebooks/01_trading_dates.ipynb --output tutorials/01_trading_dates.py
```

## 🔧 环境要求

### 系统要求
- Python 3.8+
- Windows 10/11 (推荐)
- 8GB+ RAM
- 稳定的网络连接

### 依赖包
```bash
pip install requests pandas numpy matplotlib jupytext jupyter
```

### 服务要求
- QMT 数据代理服务运行在 `http://localhost:8000`
- 有效的数据源连接（迅投QMT或模拟数据）

## 📋 学习检查清单

### 基础技能
- [ ] 能够成功启动 API 服务
- [ ] 理解 API 调用的基本流程
- [ ] 掌握错误处理机制
- [ ] 能够读取和解析返回数据

### 进阶技能
- [ ] 能够处理大量历史数据
- [ ] 掌握实时数据流处理
- [ ] 理解性能优化技巧
- [ ] 能够构建数据分析流程

### 专家技能
- [ ] 能够设计复杂的数据处理系统
- [ ] 掌握多数据源整合技术
- [ ] 理解高频数据处理优化
- [ ] 能够构建生产级应用

## 🆘 获取帮助

- **故障排除**: 查看 `TROUBLESHOOTING.md`
- **详细文档**: 查看 `README.md`
- **API 文档**: 访问 `http://localhost:8000/docs`
- **社区支持**: 提交 Issue 或联系技术支持

## 📝 贡献指南

如果您发现教学内容有误或希望改进，欢迎：
1. 提交 Issue 报告问题
2. 提交 Pull Request 改进内容
3. 分享您的学习心得和最佳实践

---

**最后更新**: 2024年1月
**版本**: v1.0.0
**维护者**: Project Argus 开发团队