# Requirements Document

## Introduction

本规格说明书旨在验证并修复教程目录下的所有Python教程，确保它们能够正确运行，从API返回真实的市场数据，并且能够与xtdata进行有效对比。同时需要为每个教程添加详细的文字指导，并将Python文件转换为Jupyter Notebook格式，为用户提供完整的学习体验。

**重要原则：**
- 必须使用真实的市场数据，严禁使用任何模拟数据
- 遇到错误必须修复根本原因，不能通过模拟数据绕过问题
- 所有API调用都必须成功返回真实数据
- 确保与xtdata的对比使用的是真实数据源
- 每个教程都需要详细的文字说明和步骤指导
- 最终的ipynb文件必须能够完整运行，为用户提供最佳学习体验

## Requirements

### Requirement 1

**User Story:** 作为开发者，我希望所有教程都能正确运行并获取真实数据，这样我就能学习如何使用API获取真实的市场数据。

#### Acceptance Criteria

1. WHEN 运行任何教程文件 THEN 系统 SHALL 成功执行而不出现语法错误或运行时异常
2. WHEN 教程调用API THEN 系统 SHALL 返回真实的市场数据，不允许使用任何模拟数据
3. WHEN API调用失败 THEN 系统 SHALL 修复错误原因而不是回退到模拟数据
4. WHEN 教程执行完成 THEN 系统 SHALL 显示清晰的真实数据结果输出和数据摘要

### Requirement 2

**User Story:** 作为开发者，我希望教程能够从API获取真实正确的数据，这样我就能验证真实数据的准确性和完整性。

#### Acceptance Criteria

1. WHEN 教程调用get_trading_dates API THEN 系统 SHALL 返回真实的交易日期列表，不允许生成模拟日期
2. WHEN 教程调用get_hist_kline API THEN 系统 SHALL 返回真实市场的OHLCV数据，不允许使用模拟K线数据
3. WHEN 教程调用get_instrument_detail API THEN 系统 SHALL 返回真实股票的详细基础信息，不允许使用虚假信息
4. WHEN 教程调用get_stock_list API THEN 系统 SHALL 返回真实市场的股票列表，不允许生成模拟股票代码
5. WHEN 教程调用get_latest_market API THEN 系统 SHALL 返回真实的最新行情数据，不允许使用模拟价格
6. WHEN 教程调用get_full_market API THEN 系统 SHALL 返回真实的完整市场行情数据，不允许使用任何模拟数据

### Requirement 3

**User Story:** 作为开发者，我希望教程能够与xtdata进行真实数据对比，这样我就能验证不同真实数据源的一致性。

#### Acceptance Criteria

1. WHEN 教程同时调用API和xtdata THEN 系统 SHALL 成功获取两个数据源的真实数据
2. WHEN 进行数据对比 THEN 系统 SHALL 标准化两个真实数据源的格式以便比较
3. WHEN 显示对比结果 THEN 系统 SHALL 展示真实数据的差异统计和详细对比信息
4. WHEN xtdata不可用 THEN 系统 SHALL 修复xtdata连接问题而不是使用模拟数据替代
5. WHEN 数据对比发现差异 THEN 系统 SHALL 分析真实数据差异的原因而不是忽略差异

### Requirement 4

**User Story:** 作为开发者，我希望教程具有强大的错误修复机制，这样遇到问题时能够自动修复并继续获取真实数据。

#### Acceptance Criteria

1. WHEN API调用失败 THEN 系统 SHALL 诊断并修复API连接问题，确保能获取真实数据
2. WHEN 网络连接问题 THEN 系统 SHALL 实施重试机制和连接修复，不允许使用离线模拟数据
3. WHEN 数据格式异常 THEN 系统 SHALL 修复数据解析逻辑以正确处理真实数据格式
4. WHEN 参数错误 THEN 系统 SHALL 自动修正参数格式并重新调用API获取真实数据
5. WHEN 遇到任何错误 THEN 系统 SHALL 优先修复问题而不是回退到模拟数据

### Requirement 5

**User Story:** 作为开发者，我希望教程能够提供性能监控和统计信息，这样我就能了解API调用的效率和成功率。

#### Acceptance Criteria

1. WHEN 教程执行 THEN 系统 SHALL 记录每个API调用的响应时间
2. WHEN 教程完成 THEN 系统 SHALL 显示性能统计报告包括成功率和平均响应时间
3. WHEN 发现性能问题 THEN 系统 SHALL 提供优化建议
4. WHEN 数据量较大 THEN 系统 SHALL 实施批量处理和缓存策略

### Requirement 6

**User Story:** 作为开发者，我希望教程能够自动验证数据的完整性和准确性，这样我就能确信获取的数据是可靠的。

#### Acceptance Criteria

1. WHEN 获取K线数据 THEN 系统 SHALL 验证OHLCV字段的完整性和数值合理性
2. WHEN 获取交易日期 THEN 系统 SHALL 验证日期格式和时间顺序的正确性
3. WHEN 获取股票信息 THEN 系统 SHALL 验证必要字段的存在和数据类型
4. WHEN 发现数据异常 THEN 系统 SHALL 记录异常并提供数据质量报告
### Requirement 7

**User Story:** 作为开发者，我希望教程能够彻底移除所有模拟数据相关代码，这样我就能确保只使用真实的市场数据。

#### Acceptance Criteria

1. WHEN 检查教程代码 THEN 系统 SHALL 识别并移除所有模拟数据生成函数
2. WHEN 发现mock数据导入 THEN 系统 SHALL 删除所有mock数据相关的import语句
3. WHEN 发现fallback到模拟数据的逻辑 THEN 系统 SHALL 替换为错误修复逻辑
4. WHEN 清理完成 THEN 系统 SHALL 确保教程只能获取和使用真实数据

### Requirement 8

**User Story:** 作为学习者，我希望每个教程都有详细的文字说明和步骤指导，这样我就能一步一步地学习如何使用API。

#### Acceptance Criteria

1. WHEN 查看教程 THEN 系统 SHALL 提供清晰的章节结构和学习目标
2. WHEN 执行每个步骤 THEN 系统 SHALL 提供详细的解释说明每个操作的目的和原理
3. WHEN 遇到重要概念 THEN 系统 SHALL 提供背景知识和最佳实践建议
4. WHEN 显示结果 THEN 系统 SHALL 解释数据的含义和如何解读结果
5. WHEN 教程结束 THEN 系统 SHALL 提供总结和进一步学习的建议

### Requirement 9

**User Story:** 作为学习者，我希望能够使用Jupyter Notebook格式的教程，这样我就能交互式地学习和实验。

#### Acceptance Criteria

1. WHEN 转换Python文件 THEN 系统 SHALL 使用jupytext将.py文件转换为.ipynb格式
2. WHEN 生成notebook THEN 系统 SHALL 确保所有代码单元格能够正确执行
3. WHEN 添加markdown单元格 THEN 系统 SHALL 包含详细的文字说明和指导
4. WHEN 用户运行notebook THEN 系统 SHALL 确保能够完整运行并获取真实数据
5. WHEN notebook完成 THEN 系统 SHALL 提供清晰的输出结果和数据可视化