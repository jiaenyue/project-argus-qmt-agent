
# 用户指南

## 概述

QMT教程验证和修复系统是一个自动化工具，用于确保QMT API教程的质量和可靠性。本指南将帮助您了解如何使用这个系统。

## 安装和设置

### 系统要求

- Python 3.8+
- 所需的Python包（见requirements.txt）
- QMT API访问权限

### 安装步骤

1. 克隆或下载项目代码
2. 安装依赖包:
   ```bash
   pip install -r requirements.txt
   ```
3. 确保QMT API服务可用

## 使用方法

### 基本使用

运行完整的处理流水线:

```bash
python main_tutorial_processor.py
```

这将执行以下步骤:
1. 环境检查
2. 教程扫描
3. API验证
4. 错误检测和修复
5. 内容增强
6. Notebook转换
7. 综合测试
8. 文档生成

### 单独使用组件

#### 验证教程

```python
from tutorial_validation_system import TutorialValidator
from pathlib import Path

validator = TutorialValidator()
result = validator.validate_tutorial(Path("tutorials/01_trading_dates.py"))
print(f"验证结果: {result.validation_success}")
```

#### 增强教程

```python
from tutorial_enhancer import TutorialEnhancer
from pathlib import Path

enhancer = TutorialEnhancer()
result = enhancer.enhance_tutorial(Path("tutorials/01_trading_dates.py"))
print(f"增强项: {len(result.enhancements_applied)}")
```

#### 转换为Notebook

```python
from notebook_converter import NotebookConverter
from pathlib import Path

converter = NotebookConverter()
result = converter.convert_tutorial(Path("tutorials/01_trading_dates.py"))
print(f"转换成功: {result.conversion_success}")
```

## 输出文件

### 报告文件

- `reports/validation_report.md`: 验证报告
- `reports/enhancement_report.md`: 增强报告
- `reports/conversion_report.md`: 转换报告
- `reports/final_processing_report.md`: 最终处理报告
- `reports/processing_results.json`: JSON格式的处理结果

### 生成的文档

- `output/README.md`: 项目说明文档
- `output/API_DOCS.md`: API文档
- `output/USER_GUIDE.md`: 用户指南
- `output/TROUBLESHOOTING.md`: 故障排除指南

### 转换的Notebook

- `tutorials/notebooks/*.ipynb`: 转换后的Jupyter Notebook文件

## 配置选项

### 环境变量

- `QMT_API_URL`: QMT API服务地址
- `QMT_API_TOKEN`: API访问令牌
- `LOG_LEVEL`: 日志级别（DEBUG, INFO, WARNING, ERROR）

### 配置文件

可以通过修改各个组件的初始化参数来自定义行为:

```python
# 自定义验证器
validator = TutorialValidator(
    check_syntax=True,
    check_imports=True,
    check_api_calls=True,
    fix_errors=True
)

# 自定义增强器
enhancer = TutorialEnhancer(
    add_docstrings=True,
    add_comments=True,
    add_learning_objectives=True,
    add_best_practices=True
)

# 自定义转换器
converter = NotebookConverter(
    add_visualizations=True,
    optimize_structure=True,
    add_markdown_cells=True
)
```

## 最佳实践

1. **定期运行**: 建议定期运行处理流水线，确保教程始终保持最新状态
2. **备份原文件**: 系统会自动创建备份，但建议手动备份重要文件
3. **检查报告**: 仔细阅读生成的报告，了解处理过程中的问题和改进
4. **测试结果**: 运行生成的Notebook，确保功能正常
5. **自定义配置**: 根据需要调整配置参数，优化处理效果

## 常见问题

### Q: 处理过程中出现错误怎么办？

A: 查看日志文件 `tutorial_processing.log` 和相关报告，根据错误信息进行排查。常见问题的解决方案请参考故障排除指南。

### Q: 如何自定义增强内容？

A: 可以修改 `TutorialEnhancer` 类中的模板内容，或者继承该类实现自定义的增强逻辑。

### Q: 生成的Notebook无法运行怎么办？

A: 检查依赖包是否完整安装，API服务是否可用，以及Notebook中的代码是否正确。

### Q: 如何添加新的教程文件？

A: 将新的Python教程文件放入 `tutorials/` 目录，然后重新运行处理流水线即可。

## 技术支持

如果遇到技术问题，请:

1. 查看日志文件和报告
2. 参考故障排除指南
3. 检查API服务状态
4. 联系技术支持团队
