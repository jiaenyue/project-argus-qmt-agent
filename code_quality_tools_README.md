# 教程代码质量工具

本目录包含一系列用于检查和改进教程代码质量的工具。这些工具可以帮助统一代码风格、检查代码质量、验证文档完整性，并自动修复常见问题。

## 工具概述

### 1. 代码质量检查工具 (`code_quality_check.py`)

该工具用于检查代码格式和质量，包括：
- 代码格式检查（使用 black 和 isort）
- 静态代码分析（使用 pylint 和 flake8）
- 代码质量评分和建议

### 2. 文档字符串检查工具 (`docstring_checker.py`)

该工具专门用于检查文档字符串和注释的完整性：
- 检查模块、类和函数的文档字符串
- 验证参数和返回值文档
- 检查注释密度和质量
- 生成文档覆盖率报告

### 3. 语法错误修复工具 (`fix_syntax_errors.py`)

该工具用于检查和修复常见的语法错误：
- 修复 safe_api_call 递归调用错误
- 修复字典语法错误
- 修复参数传递问题
- 修复导入语句
- 修复变量名混用问题

### 4. 综合验证工具 (`run_validation.py`)

该工具整合了上述所有工具，提供一站式的代码质量验证：
- 运行所有检查工具
- 可选择性地修复问题
- 生成综合质量报告

## 安装依赖

这些工具依赖于一些第三方库，可以通过以下命令安装：

```bash
pip install black isort pylint flake8
```

## 使用方法

### 代码质量检查

```bash
# 检查单个文件
python code_quality_check.py --file tutorials/01_trading_dates.py

# 检查所有教程文件
python code_quality_check.py --all

# 检查并自动修复格式问题
python code_quality_check.py --all --fix
```

### 文档字符串检查

```bash
# 检查单个文件
python docstring_checker.py --file tutorials/01_trading_dates.py

# 检查所有教程文件
python docstring_checker.py --all
```

### 语法错误修复

```bash
# 检查单个文件（不修改）
python fix_syntax_errors.py --file tutorials/01_trading_dates.py --dry-run

# 检查并修复所有教程文件
python fix_syntax_errors.py --all
```

### 综合验证

```bash
# 检查单个文件
python run_validation.py --file tutorials/01_trading_dates.py

# 检查所有教程文件
python run_validation.py --all

# 检查并自动修复问题
python run_validation.py --all --fix
```

## 报告输出

所有工具都会生成详细的报告文件：

- `tutorials_quality_report.txt`: 代码质量报告
- `docstring_report.txt`: 文档字符串报告
- `tutorials_validation_report.txt`: 综合验证报告

## 最佳实践

1. **定期运行检查**：建议在开发过程中定期运行这些工具，及时发现和修复问题。

2. **先检查后修复**：首先使用 `--dry-run` 或不带 `--fix` 参数运行工具，查看问题报告，然后再决定是否自动修复。

3. **代码审查**：自动工具无法捕获所有问题，建议结合人工代码审查使用。

4. **持续改进**：根据工具的建议持续改进代码质量和文档。

## 注意事项

1. 自动修复功能可能会改变代码格式和结构，请在使用前备份重要文件。

2. 某些复杂的代码质量问题和文档问题需要手动修复。

3. 工具可能需要根据项目特定需求进行配置调整。