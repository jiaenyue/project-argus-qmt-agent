
# QMT教程验证和修复系统

本项目提供了一套完整的QMT教程验证、修复和增强系统，确保所有教程都能正确运行并使用真实的市场数据。

## 功能特性

- ✅ 教程代码验证和错误检测
- 🔧 自动错误修复和代码优化
- 📚 教程内容增强和文档化
- 📓 Python到Jupyter Notebook转换
- 🧪 综合测试和质量保证
- 📊 详细的处理报告和统计

## 快速开始

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 运行处理流水线:
```bash
python main_tutorial_processor.py
```

3. 查看生成的报告和文档在 `reports/` 和 `output/` 目录中。

## 目录结构

```
├── tutorials/              # 原始教程文件
├── tutorials/notebooks/     # 转换后的Jupyter Notebook
├── reports/                # 处理报告
├── output/                 # 生成的文档
├── tutorial_validation_system.py  # 验证系统
├── tutorial_enhancer.py    # 增强器
├── notebook_converter.py   # Notebook转换器
└── main_tutorial_processor.py     # 主处理器
```

## 使用说明

详细的使用说明请参考 [用户指南](USER_GUIDE.md)。

## API文档

API文档请参考 [API文档](API_DOCS.md)。

## 故障排除

如果遇到问题，请参考 [故障排除指南](TROUBLESHOOTING.md)。

## 许可证

本项目采用MIT许可证。
