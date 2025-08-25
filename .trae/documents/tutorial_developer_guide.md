# Project Argus QMT 教学文档系统开发者指南

## 1. 开发环境设置

### 1.1 环境要求

**基础环境:**
- Python 3.8+
- Git 2.20+
- Node.js 16+ (用于某些工具)
- Visual Studio Code (推荐)

**Python依赖:**
```bash
# 核心依赖
pip install requests>=2.28.0
pip install jupyter>=1.0.0
pip install jupytext>=1.14.0
pip install pytest>=7.0.0

# 开发工具
pip install black>=22.0.0
pip install flake8>=5.0.0
pip install mypy>=0.991
pip install isort>=5.10.0
pip install pre-commit>=2.20.0

# 文档工具
pip install sphinx>=5.0.0
pip install mkdocs>=1.4.0
pip install mkdocs-material>=8.5.0
```

### 1.2 开发工具配置

**VS Code配置 (.vscode/settings.json):**
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length=88"],
    "python.sortImports.args": ["--profile", "black"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "files.associations": {
        "*.py": "python"
    },
    "jupyter.askForKernelRestart": false
}
```

**Pre-commit配置 (.pre-commit-config.yaml):**
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 22.10.0
    hooks:
      - id: black
        language_version: python3
        args: [--line-length=88]
  
  - repo: https://github.com/pycqa/isort
    rev: 5.10.1
    hooks:
      - id: isort
        args: ["--profile", "black"]
  
  - repo: https://github.com/pycqa/flake8
    rev: 5.0.4
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v0.991
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

### 1.3 项目结构

```
project-argus-qmt-agent/
├── tutorials/                    # 教学文档根目录
│   ├── common.py                # 通用工具库
│   ├── 01_trading_dates.py      # 交易日历教学
│   ├── 02_hist_kline.py         # 历史K线教学
│   ├── 03_instrument_detail.py  # 合约详情教学
│   ├── 04_stock_list.py         # 股票列表教学
│   ├── 06_latest_market.py      # 最新行情教学
│   ├── 07_full_market.py        # 全推行情教学
│   ├── notebooks/               # Jupyter Notebook目录
│   │   ├── 01_trading_dates.ipynb
│   │   ├── 02_hist_kline.ipynb
│   │   └── ...
│   ├── scripts/                 # 自动化脚本
│   │   ├── convert_to_notebooks.py
│   │   ├── validate_tutorials.py
│   │   └── run_all_tutorials.py
│   ├── tests/                   # 测试文件
│   │   ├── test_common.py
│   │   ├── test_tutorials.py
│   │   └── conftest.py
│   ├── README.md               # 教学系统说明
│   └── TROUBLESHOOTING.md      # 故障排除指南
├── .trae/documents/            # 系统文档
│   ├── tutorial_system_design.md
│   ├── tutorial_implementation_plan.md
│   ├── tutorial_technical_architecture.md
│   ├── tutorial_user_guide.md
│   └── tutorial_developer_guide.md
├── docs/                       # 项目文档
├── src/                        # 源代码
├── requirements.txt            # 依赖列表
├── setup.py                    # 安装配置
└── README.md                   # 项目说明
```

## 2. 教学文档开发规范

### 2.1 Python教学文件规范

**文件头部模板:**
```python
# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.5
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

"""
# Project Argus QMT 教学文档 - [主题名称]

## 学习目标
- 目标1: 具体的学习目标描述
- 目标2: 具体的学习目标描述
- 目标3: 具体的学习目标描述

## 背景知识
[相关背景知识和概念解释]

## 操作步骤
1. 步骤1: 详细操作说明
2. 步骤2: 详细操作说明
3. 步骤3: 详细操作说明

## 注意事项
- 注意事项1
- 注意事项2
- 注意事项3
"""

# 导入必要的库
import sys
import time
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

# 导入项目通用工具
from common import (
    create_api_client,
    print_section_header,
    print_subsection_header,
    print_api_result,
    get_date_range,
    safe_api_call
)
```

**函数命名规范:**
```python
# 演示函数命名模式
def demo_basic_functionality():          # 基础功能演示
    """演示基础功能的使用方法"""
    pass

def demo_advanced_features():            # 高级功能演示
    """演示高级功能和参数使用"""
    pass

def demo_error_handling():               # 错误处理演示
    """演示错误处理和异常情况"""
    pass

def demo_practical_application():        # 实际应用演示
    """演示实际应用场景和最佳实践"""
    pass

def demo_performance_optimization():     # 性能优化演示
    """演示性能优化技巧"""
    pass

def print_usage_guide():                 # 使用指南
    """打印详细的使用指南和参数说明"""
    pass

def main():                              # 主函数
    """执行所有演示函数"""
    print_section_header("[主题名称] 教学演示")
    
    demo_basic_functionality()
    demo_advanced_features()
    demo_error_handling()
    demo_practical_application()
    demo_performance_optimization()
    print_usage_guide()
    
    print("\n✅ 教学演示完成！")

if __name__ == "__main__":
    main()
```

**代码注释规范:**
```python
def demo_api_usage():
    """API使用演示
    
    这个函数演示了如何正确使用API，包括:
    1. 参数准备和验证
    2. API调用和响应处理
    3. 错误处理和降级策略
    4. 结果展示和分析
    """
    print_subsection_header("API使用演示")
    
    # 步骤1: 创建API客户端
    # 使用通用工具创建客户端，自动处理配置
    client = create_api_client()
    
    # 步骤2: 准备请求参数
    # 设置查询参数，注意参数格式和有效性
    params = {
        "market": "SH",      # 市场代码: SH=上海, SZ=深圳
        "count": 10,         # 返回记录数: 1-100
        "offset": 0          # 偏移量: 用于分页查询
    }
    
    try:
        # 步骤3: 执行API调用
        # 使用安全调用函数，自动处理超时和重试
        print("📡 正在调用API...")
        result = client.get_trading_dates(**params)
        
        # 步骤4: 处理API响应
        if result.get("code") == 0:
            # 成功响应处理
            data = result.get("data", [])
            print(f"✅ 获取成功: {len(data)} 条记录")
            
            # 展示部分数据
            for i, item in enumerate(data[:3]):
                print(f"  {i+1}. {item}")
            
            if len(data) > 3:
                print(f"  ... 还有 {len(data)-3} 条记录")
                
        else:
            # 错误响应处理
            error_msg = result.get("message", "未知错误")
            print(f"❌ API调用失败: {error_msg}")
            print("💡 请检查参数设置和网络连接")
            
    except Exception as e:
        # 异常处理
        print(f"⚠️ 执行异常: {e}")
        print("💡 建议检查:")
        print("   - API服务是否正常运行")
        print("   - 网络连接是否稳定")
        print("   - 参数格式是否正确")
    
    print()  # 添加空行分隔
```

### 2.2 Jupyter Notebook规范

**Notebook结构:**
```markdown
# Cell 1: 标题和说明
# Project Argus QMT 教学文档 - [主题名称]

本教学文档将带您学习...

## 学习目标
- 目标1
- 目标2
- 目标3

# Cell 2: 环境检查
# 检查环境和依赖
import sys
print(f"Python版本: {sys.version}")

try:
    from common import create_api_client
    print("✅ 通用工具库导入成功")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在tutorials目录下运行")

# Cell 3: API连接测试
# 测试API连接
client = create_api_client()
print("🔗 正在测试API连接...")

# 简单的连接测试
try:
    result = client.get_trading_dates(market="SH", count=1)
    if result.get("code") == 0:
        print("✅ API连接正常")
    else:
        print(f"❌ API响应异常: {result.get('message')}")
except Exception as e:
    print(f"❌ 连接失败: {e}")

# Cell 4-N: 功能演示
# 每个功能一个或多个Cell
```

**Cell类型规范:**
- **Markdown Cell**: 用于说明、标题、总结
- **Code Cell**: 用于代码演示和执行
- **Raw Cell**: 用于配置信息（很少使用）

### 2.3 通用工具库开发

**APIClient类扩展:**
```python
class APIClient:
    """QMT API客户端
    
    提供统一的API调用接口，包含错误处理、重试机制、
    性能监控等功能。
    """
    
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """配置HTTP会话"""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Project-Argus-Tutorial/1.0'
        })
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """执行HTTP请求
        
        Args:
            endpoint: API端点
            params: 请求参数
            
        Returns:
            API响应数据
            
        Raises:
            requests.RequestException: 网络请求异常
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(
                url, 
                params=params, 
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            raise requests.RequestException(f"请求超时 ({self.timeout}秒)")
        except requests.exceptions.ConnectionError:
            raise requests.RequestException("连接失败，请检查网络和服务状态")
        except requests.exceptions.HTTPError as e:
            raise requests.RequestException(f"HTTP错误: {e}")
        except json.JSONDecodeError:
            raise requests.RequestException("响应格式错误，非有效JSON")
    
    def get_trading_dates(self, market: str = "SH", 
                         count: int = 10, 
                         offset: int = 0) -> Dict:
        """获取交易日历
        
        Args:
            market: 市场代码 (SH/SZ)
            count: 返回记录数 (1-100)
            offset: 偏移量
            
        Returns:
            交易日历数据
        """
        params = {
            "market": market,
            "count": count,
            "offset": offset
        }
        return self._make_request("/api/trading_dates", params)
    
    # 其他API方法...
```

**工具函数扩展:**
```python
def print_section_header(title: str, width: int = 60):
    """打印章节标题
    
    Args:
        title: 标题文本
        width: 标题宽度
    """
    border = "=" * width
    padding = (width - len(title) - 2) // 2
    formatted_title = f"{' ' * padding}{title}{' ' * padding}"
    
    print(f"\n{border}")
    print(f"|{formatted_title}|")
    print(f"{border}\n")

def print_api_result(result: Dict, title: str = "API结果"):
    """格式化打印API结果
    
    Args:
        result: API响应数据
        title: 结果标题
    """
    print(f"📊 {title}:")
    
    if result.get("code") == 0:
        data = result.get("data", [])
        print(f"   状态: ✅ 成功")
        print(f"   记录数: {len(data) if isinstance(data, list) else 1}")
        
        # 显示数据样例
        if isinstance(data, list) and data:
            print(f"   样例数据: {data[0]}")
        elif data:
            print(f"   数据: {data}")
    else:
        print(f"   状态: ❌ 失败")
        print(f"   错误: {result.get('message', '未知错误')}")
    
    print()

def safe_api_call(func, *args, max_retries: int = 3, **kwargs):
    """安全的API调用，带重试机制
    
    Args:
        func: API调用函数
        max_retries: 最大重试次数
        *args, **kwargs: 函数参数
        
    Returns:
        API调用结果或None
    """
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            if result.get("code") == 0:
                return result
            else:
                print(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): "
                      f"{result.get('message')}")
        except Exception as e:
            print(f"调用异常 (尝试 {attempt + 1}/{max_retries}): {e}")
            
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 指数退避
            print(f"等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
    
    print("所有重试都失败")
    return None
```

## 3. 自动化工具开发

### 3.1 转换脚本 (convert_to_notebooks.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python教学文件到Jupyter Notebook转换脚本

功能:
1. 批量转换.py文件为.ipynb格式
2. 保持代码结构和注释
3. 自动生成Markdown说明单元
4. 验证转换结果
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

import jupytext

class NotebookConverter:
    """Notebook转换器"""
    
    def __init__(self, source_dir: str, target_dir: str):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.target_dir.mkdir(parents=True, exist_ok=True)
    
    def find_python_files(self) -> List[Path]:
        """查找所有Python教学文件"""
        python_files = []
        
        for file_path in self.source_dir.glob("*.py"):
            # 排除通用工具文件和测试文件
            if file_path.name in ["common.py", "conftest.py"]:
                continue
            if file_path.name.startswith("test_"):
                continue
                
            python_files.append(file_path)
        
        return sorted(python_files)
    
    def convert_file(self, py_file: Path) -> Optional[Path]:
        """转换单个Python文件
        
        Args:
            py_file: Python文件路径
            
        Returns:
            生成的notebook文件路径
        """
        try:
            print(f"🔄 转换文件: {py_file.name}")
            
            # 读取Python文件
            notebook = jupytext.read(py_file)
            
            # 设置notebook元数据
            notebook.metadata = {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": "3.8.0"
                }
            }
            
            # 生成输出文件路径
            output_file = self.target_dir / f"{py_file.stem}.ipynb"
            
            # 写入notebook文件
            jupytext.write(notebook, output_file)
            
            print(f"✅ 转换成功: {output_file.name}")
            return output_file
            
        except Exception as e:
            print(f"❌ 转换失败 {py_file.name}: {e}")
            return None
    
    def validate_notebook(self, notebook_file: Path) -> bool:
        """验证notebook文件
        
        Args:
            notebook_file: notebook文件路径
            
        Returns:
            验证是否成功
        """
        try:
            # 检查文件是否存在
            if not notebook_file.exists():
                print(f"❌ 文件不存在: {notebook_file}")
                return False
            
            # 检查JSON格式
            with open(notebook_file, 'r', encoding='utf-8') as f:
                notebook_data = json.load(f)
            
            # 检查必要字段
            required_fields = ['cells', 'metadata', 'nbformat']
            for field in required_fields:
                if field not in notebook_data:
                    print(f"❌ 缺少必要字段 {field}: {notebook_file}")
                    return False
            
            # 检查是否有代码单元
            code_cells = [cell for cell in notebook_data['cells'] 
                         if cell.get('cell_type') == 'code']
            if not code_cells:
                print(f"⚠️ 没有代码单元: {notebook_file}")
            
            print(f"✅ 验证通过: {notebook_file.name}")
            return True
            
        except Exception as e:
            print(f"❌ 验证失败 {notebook_file}: {e}")
            return False
    
    def convert_all(self) -> Dict[str, int]:
        """批量转换所有文件
        
        Returns:
            转换统计信息
        """
        python_files = self.find_python_files()
        
        stats = {
            'total': len(python_files),
            'success': 0,
            'failed': 0,
            'validated': 0
        }
        
        print(f"📁 找到 {stats['total']} 个Python教学文件")
        print(f"📂 输出目录: {self.target_dir}")
        print()
        
        for py_file in python_files:
            # 转换文件
            notebook_file = self.convert_file(py_file)
            
            if notebook_file:
                stats['success'] += 1
                
                # 验证转换结果
                if self.validate_notebook(notebook_file):
                    stats['validated'] += 1
            else:
                stats['failed'] += 1
            
            print()  # 添加空行分隔
        
        return stats
    
    def print_summary(self, stats: Dict[str, int]):
        """打印转换摘要"""
        print("=" * 50)
        print("📊 转换摘要")
        print("=" * 50)
        print(f"总文件数: {stats['total']}")
        print(f"转换成功: {stats['success']}")
        print(f"转换失败: {stats['failed']}")
        print(f"验证通过: {stats['validated']}")
        
        if stats['success'] == stats['total']:
            print("\n🎉 所有文件转换成功！")
        elif stats['success'] > 0:
            print(f"\n⚠️ 部分文件转换成功 ({stats['success']}/{stats['total']})")
        else:
            print("\n❌ 没有文件转换成功")

def main():
    """主函数"""
    # 设置路径
    current_dir = Path(__file__).parent
    source_dir = current_dir.parent  # tutorials目录
    target_dir = source_dir / "notebooks"
    
    print("🚀 启动Python到Notebook转换工具")
    print(f"📁 源目录: {source_dir}")
    print(f"📂 目标目录: {target_dir}")
    print()
    
    # 创建转换器
    converter = NotebookConverter(source_dir, target_dir)
    
    # 执行转换
    stats = converter.convert_all()
    
    # 打印摘要
    converter.print_summary(stats)

if __name__ == "__main__":
    main()
```

### 3.2 验证脚本 (validate_tutorials.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
教学文档验证脚本

功能:
1. 验证Python文件语法正确性
2. 检查API调用是否正常
3. 验证Notebook文件格式
4. 生成验证报告
"""

import os
import sys
import ast
import json
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """验证结果"""
    file_path: Path
    file_type: str  # 'python' or 'notebook'
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    execution_time: float = 0.0

class TutorialValidator:
    """教学文档验证器"""
    
    def __init__(self, tutorials_dir: str):
        self.tutorials_dir = Path(tutorials_dir)
        self.results: List[ValidationResult] = []
    
    def validate_python_syntax(self, py_file: Path) -> ValidationResult:
        """验证Python文件语法
        
        Args:
            py_file: Python文件路径
            
        Returns:
            验证结果
        """
        result = ValidationResult(
            file_path=py_file,
            file_type='python',
            is_valid=True,
            errors=[],
            warnings=[]
        )
        
        try:
            # 读取文件内容
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 语法检查
            ast.parse(content)
            
            # 检查编码声明
            if '# -*- coding: utf-8 -*-' not in content:
                result.warnings.append("缺少编码声明")
            
            # 检查文档字符串
            if '"""' not in content:
                result.warnings.append("缺少文档字符串")
            
            # 检查主函数
            if 'def main():' not in content:
                result.warnings.append("缺少main函数")
            
            # 检查执行入口
            if 'if __name__ == "__main__":' not in content:
                result.warnings.append("缺少执行入口")
                
        except SyntaxError as e:
            result.is_valid = False
            result.errors.append(f"语法错误: {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"验证异常: {e}")
        
        return result
    
    def validate_python_execution(self, py_file: Path) -> ValidationResult:
        """验证Python文件执行
        
        Args:
            py_file: Python文件路径
            
        Returns:
            验证结果
        """
        result = ValidationResult(
            file_path=py_file,
            file_type='python',
            is_valid=True,
            errors=[],
            warnings=[]
        )
        
        try:
            start_time = time.time()
            
            # 执行Python文件
            process = subprocess.run(
                [sys.executable, str(py_file)],
                cwd=self.tutorials_dir,
                capture_output=True,
                text=True,
                timeout=60  # 60秒超时
            )
            
            result.execution_time = time.time() - start_time
            
            if process.returncode != 0:
                result.is_valid = False
                result.errors.append(f"执行失败 (退出码: {process.returncode})")
                if process.stderr:
                    result.errors.append(f"错误输出: {process.stderr}")
            
            # 检查输出内容
            if process.stdout:
                output = process.stdout
                if "❌" in output:
                    result.warnings.append("输出中包含错误标记")
                if "API连接失败" in output:
                    result.warnings.append("API连接失败")
                    
        except subprocess.TimeoutExpired:
            result.is_valid = False
            result.errors.append("执行超时 (60秒)")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"执行异常: {e}")
        
        return result
    
    def validate_notebook_format(self, notebook_file: Path) -> ValidationResult:
        """验证Notebook文件格式
        
        Args:
            notebook_file: Notebook文件路径
            
        Returns:
            验证结果
        """
        result = ValidationResult(
            file_path=notebook_file,
            file_type='notebook',
            is_valid=True,
            errors=[],
            warnings=[]
        )
        
        try:
            # 检查文件是否存在
            if not notebook_file.exists():
                result.is_valid = False
                result.errors.append("文件不存在")
                return result
            
            # 读取JSON内容
            with open(notebook_file, 'r', encoding='utf-8') as f:
                notebook_data = json.load(f)
            
            # 检查必要字段
            required_fields = ['cells', 'metadata', 'nbformat', 'nbformat_minor']
            for field in required_fields:
                if field not in notebook_data:
                    result.errors.append(f"缺少必要字段: {field}")
                    result.is_valid = False
            
            if not result.is_valid:
                return result
            
            # 检查单元格
            cells = notebook_data.get('cells', [])
            if not cells:
                result.warnings.append("没有单元格")
            
            # 统计单元格类型
            cell_types = {}
            for cell in cells:
                cell_type = cell.get('cell_type', 'unknown')
                cell_types[cell_type] = cell_types.get(cell_type, 0) + 1
            
            # 检查是否有代码单元
            if cell_types.get('code', 0) == 0:
                result.warnings.append("没有代码单元")
            
            # 检查是否有Markdown单元
            if cell_types.get('markdown', 0) == 0:
                result.warnings.append("没有Markdown单元")
            
            # 检查内核信息
            kernelspec = notebook_data.get('metadata', {}).get('kernelspec', {})
            if kernelspec.get('name') != 'python3':
                result.warnings.append("内核不是Python3")
                
        except json.JSONDecodeError as e:
            result.is_valid = False
            result.errors.append(f"JSON格式错误: {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"验证异常: {e}")
        
        return result
    
    def find_files(self) -> Tuple[List[Path], List[Path]]:
        """查找所有教学文件
        
        Returns:
            (Python文件列表, Notebook文件列表)
        """
        python_files = []
        notebook_files = []
        
        # 查找Python文件
        for py_file in self.tutorials_dir.glob("*.py"):
            if py_file.name not in ["common.py", "conftest.py"]:
                if not py_file.name.startswith("test_"):
                    python_files.append(py_file)
        
        # 查找Notebook文件
        notebooks_dir = self.tutorials_dir / "notebooks"
        if notebooks_dir.exists():
            for nb_file in notebooks_dir.glob("*.ipynb"):
                notebook_files.append(nb_file)
        
        return sorted(python_files), sorted(notebook_files)
    
    def validate_all(self, check_execution: bool = True) -> Dict[str, int]:
        """验证所有文件
        
        Args:
            check_execution: 是否检查执行
            
        Returns:
            验证统计信息
        """
        python_files, notebook_files = self.find_files()
        
        stats = {
            'total_files': len(python_files) + len(notebook_files),
            'python_files': len(python_files),
            'notebook_files': len(notebook_files),
            'valid_files': 0,
            'invalid_files': 0,
            'warnings': 0
        }
        
        print(f"📁 找到 {stats['python_files']} 个Python文件")
        print(f"📓 找到 {stats['notebook_files']} 个Notebook文件")
        print()
        
        # 验证Python文件
        for py_file in python_files:
            print(f"🔍 验证Python文件: {py_file.name}")
            
            # 语法检查
            syntax_result = self.validate_python_syntax(py_file)
            self.results.append(syntax_result)
            
            if syntax_result.is_valid and check_execution:
                # 执行检查
                exec_result = self.validate_python_execution(py_file)
                self.results.append(exec_result)
            
            print()
        
        # 验证Notebook文件
        for nb_file in notebook_files:
            print(f"🔍 验证Notebook文件: {nb_file.name}")
            
            nb_result = self.validate_notebook_format(nb_file)
            self.results.append(nb_result)
            
            print()
        
        # 统计结果
        for result in self.results:
            if result.is_valid:
                stats['valid_files'] += 1
            else:
                stats['invalid_files'] += 1
            
            stats['warnings'] += len(result.warnings)
        
        return stats
    
    def print_detailed_results(self):
        """打印详细验证结果"""
        print("=" * 60)
        print("📋 详细验证结果")
        print("=" * 60)
        
        for result in self.results:
            status = "✅ 通过" if result.is_valid else "❌ 失败"
            print(f"{status} {result.file_path.name} ({result.file_type})")
            
            if result.execution_time > 0:
                print(f"   执行时间: {result.execution_time:.2f}秒")
            
            if result.errors:
                print("   错误:")
                for error in result.errors:
                    print(f"     - {error}")
            
            if result.warnings:
                print("   警告:")
                for warning in result.warnings:
                    print(f"     - {warning}")
            
            print()
    
    def print_summary(self, stats: Dict[str, int]):
        """打印验证摘要"""
        print("=" * 50)
        print("📊 验证摘要")
        print("=" * 50)
        print(f"总文件数: {stats['total_files']}")
        print(f"  Python文件: {stats['python_files']}")
        print(f"  Notebook文件: {stats['notebook_files']}")
        print(f"验证通过: {stats['valid_files']}")
        print(f"验证失败: {stats['invalid_files']}")
        print(f"警告数量: {stats['warnings']}")
        
        if stats['invalid_files'] == 0:
            print("\n🎉 所有文件验证通过！")
        else:
            print(f"\n⚠️ {stats['invalid_files']} 个文件验证失败")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="教学文档验证工具")
    parser.add_argument(
        "--no-execution", 
        action="store_true", 
        help="跳过执行检查"
    )
    parser.add_argument(
        "--detailed", 
        action="store_true", 
        help="显示详细结果"
    )
    
    args = parser.parse_args()
    
    # 设置路径
    current_dir = Path(__file__).parent
    tutorials_dir = current_dir.parent  # tutorials目录
    
    print("🔍 启动教学文档验证工具")
    print(f"📁 验证目录: {tutorials_dir}")
    print()
    
    # 创建验证器
    validator = TutorialValidator(tutorials_dir)
    
    # 执行验证
    check_execution = not args.no_execution
    stats = validator.validate_all(check_execution)
    
    # 打印结果
    if args.detailed:
        validator.print_detailed_results()
    
    validator.print_summary(stats)
    
    # 设置退出码
    sys.exit(0 if stats['invalid_files'] == 0 else 1)

if __name__ == "__main__":
    main()
```

### 3.3 批量执行脚本 (run_all_tutorials.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量执行教学文档脚本

功能:
1. 按顺序执行所有教学文件
2. 记录执行时间和结果
3. 生成执行报告
4. 支持并行执行
"""

import os
import sys
import time
import subprocess
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ExecutionResult:
    """执行结果"""
    file_path: Path
    success: bool
    execution_time: float
    output: str
    error: str
    start_time: datetime
    end_time: datetime

class TutorialRunner:
    """教学文档执行器"""
    
    def __init__(self, tutorials_dir: str):
        self.tutorials_dir = Path(tutorials_dir)
        self.results: List[ExecutionResult] = []
    
    def find_tutorial_files(self) -> List[Path]:
        """查找所有教学文件
        
        Returns:
            按编号排序的教学文件列表
        """
        tutorial_files = []
        
        for py_file in self.tutorials_dir.glob("*.py"):
            # 排除通用文件和测试文件
            if py_file.name in ["common.py", "conftest.py"]:
                continue
            if py_file.name.startswith("test_"):
                continue
            
            tutorial_files.append(py_file)
        
        # 按文件名排序（数字优先）
        def sort_key(file_path):
            name = file_path.name
            if name[0].isdigit():
                return (0, int(name.split('_')[0]), name)
            else:
                return (1, 0, name)
        
        return sorted(tutorial_files, key=sort_key)
    
    def execute_tutorial(self, py_file: Path, timeout: int = 120) -> ExecutionResult:
        """执行单个教学文件
        
        Args:
            py_file: Python文件路径
            timeout: 超时时间（秒）
            
        Returns:
            执行结果
        """
        start_time = datetime.now()
        
        try:
            print(f"🚀 执行: {py_file.name}")
            
            # 执行Python文件
            process = subprocess.run(
                [sys.executable, str(py_file)],
                cwd=self.tutorials_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            success = process.returncode == 0
            status = "✅ 成功" if success else "❌ 失败"
            
            print(f"   {status} (耗时: {execution_time:.2f}秒)")
            
            if not success and process.stderr:
                print(f"   错误: {process.stderr[:100]}...")
            
            return ExecutionResult(
                file_path=py_file,
                success=success,
                execution_time=execution_time,
                output=process.stdout,
                error=process.stderr,
                start_time=start_time,
                end_time=end_time
            )
            
        except subprocess.TimeoutExpired:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            print(f"   ⏰ 超时 (耗时: {execution_time:.2f}秒)")
            
            return ExecutionResult(
                file_path=py_file,
                success=False,
                execution_time=execution_time,
                output="",
                error=f"执行超时 ({timeout}秒)",
                start_time=start_time,
                end_time=end_time
            )
            
        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            print(f"   💥 异常: {e}")
            
            return ExecutionResult(
                file_path=py_file,
                success=False,
                execution_time=execution_time,
                output="",
                error=str(e),
                start_time=start_time,
                end_time=end_time
            )
    
    def execute_all_sequential(self, timeout: int = 120) -> Dict[str, int]:
        """顺序执行所有教学文件
        
        Args:
            timeout: 单个文件超时时间
            
        Returns:
            执行统计信息
        """
        tutorial_files = self.find_tutorial_files()
        
        stats = {
            'total': len(tutorial_files),
            'success': 0,
            'failed': 0,
            'timeout': 0,
            'total_time': 0.0
        }
        
        print(f"📁 找到 {stats['total']} 个教学文件")
        print(f"⏱️ 单个文件超时: {timeout} 秒")
        print()
        
        start_time = time.time()
        
        for py_file in tutorial_files:
            result = self.execute_tutorial(py_file, timeout)
            self.results.append(result)
            
            if result.success:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                if "超时" in result.error:
                    stats['timeout'] += 1
            
            stats['total_time'] += result.execution_time
            print()  # 添加空行分隔
        
        stats['total_time'] = time.time() - start_time
        return stats
    
    def execute_all_parallel(self, max_workers: int = 3, timeout: int = 120) -> Dict[str, int]:
        """并行执行所有教学文件
        
        Args:
            max_workers: 最大并行数
            timeout: 单个文件超时时间
            
        Returns:
            执行统计信息
        """
        tutorial_files = self.find_tutorial_files()
        
        stats = {
            'total': len(tutorial_files),
            'success': 0,
            'failed': 0,
            'timeout': 0,
            'total_time': 0.0
        }
        
        print(f"📁 找到 {stats['total']} 个教学文件")
        print(f"🔄 并行执行 (最大 {max_workers} 个进程)")
        print(f"⏱️ 单个文件超时: {timeout} 秒")
        print()
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_file = {
                executor.submit(self.execute_tutorial, py_file, timeout): py_file
                for py_file in tutorial_files
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_file):
                result = future.result()
                self.results.append(result)
                
                if result.success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    if "超时" in result.error:
                        stats['timeout'] += 1
        
        stats['total_time'] = time.time() - start_time
        
        # 按文件名排序结果
        self.results.sort(key=lambda r: r.file_path.name)
        
        return stats
    
    def print_detailed_results(self):
        """打印详细执行结果"""
        print("=" * 70)
        print("📋 详细执行结果")
        print("=" * 70)
        
        for result in self.results:
            status = "✅ 成功" if result.success else "❌ 失败"
            print(f"{status} {result.file_path.name}")
            print(f"   开始时间: {result.start_time.strftime('%H:%M:%S')}")
            print(f"   结束时间: {result.end_time.strftime('%H:%M:%S')}")
            print(f"   执行时间: {result.execution_time:.2f}秒")
            
            if not result.success:
                print(f"   错误信息: {result.error}")
            
            # 显示输出摘要
            if result.output:
                lines = result.output.split('\n')
                success_lines = [line for line in lines if '✅' in line]
                error_lines = [line for line in lines if '❌' in line]
                
                if success_lines:
                    print(f"   成功操作: {len(success_lines)} 个")
                if error_lines:
                    print(f"   失败操作: {len(error_lines)} 个")
            
            print()
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """生成执行报告
        
        Args:
            output_file: 输出文件路径
            
        Returns:
            报告内容
        """
        report_lines = [
            "# Project Argus QMT 教学文档执行报告",
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 执行摘要",
            "",
            f"- 总文件数: {len(self.results)}",
            f"- 成功执行: {sum(1 for r in self.results if r.success)}",
            f"- 执行失败: {sum(1 for r in self.results if not r.success)}",
            f"- 总执行时间: {sum(r.execution_time for r in self.results):.2f}秒",
            "",
            "## 详细结果",
            ""
        ]
        
        for result in self.results:
            status = "✅ 成功" if result.success else "❌ 失败"
            report_lines.extend([
                f"### {result.file_path.name}",
                "",
                f"- 状态: {status}",
                f"- 执行时间: {result.execution_time:.2f}秒",
                f"- 开始时间: {result.start_time.strftime('%H:%M:%S')}",
                f"- 结束时间: {result.end_time.strftime('%H:%M:%S')}",
                ""
            ])
            
            if not result.success:
                report_lines.extend([
                    "**错误信息:**",
                    "",
                    f"```",
                    result.error,
                    f"```",
                    ""
                ])
            
            if result.output:
                # 提取关键信息
                lines = result.output.split('\n')
                success_count = len([line for line in lines if '✅' in line])
                error_count = len([line for line in lines if '❌' in line])
                
                if success_count > 0 or error_count > 0:
                    report_lines.extend([
                        "**执行统计:**",
                        "",
                        f"- 成功操作: {success_count}",
                        f"- 失败操作: {error_count}",
                        ""
                    ])
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"📄 报告已保存到: {output_file}")
        
        return report_content
    
    def print_summary(self, stats: Dict[str, int]):
        """打印执行摘要"""
        print("=" * 50)
        print("📊 执行摘要")
        print("=" * 50)
        print(f"总文件数: {stats['total']}")
        print(f"执行成功: {stats['success']}")
        print(f"执行失败: {stats['failed']}")
        if stats.get('timeout', 0) > 0:
            print(f"执行超时: {stats['timeout']}")
        print(f"总耗时: {stats['total_time']:.2f}秒")
        
        if stats['failed'] == 0:
            print("\n🎉 所有教学文件执行成功！")
        else:
            print(f"\n⚠️ {stats['failed']} 个文件执行失败")
            
        # 性能统计
        if self.results:
            avg_time = sum(r.execution_time for r in self.results) / len(self.results)
            max_time = max(r.execution_time for r in self.results)
            min_time = min(r.execution_time for r in self.results)
            
            print("\n📈 性能统计:")
            print(f"   平均执行时间: {avg_time:.2f}秒")
            print(f"   最长执行时间: {max_time:.2f}秒")
            print(f"   最短执行时间: {min_time:.2f}秒")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="批量执行教学文档")
    parser.add_argument(
        "--parallel", 
        action="store_true", 
        help="并行执行"
    )
    parser.add_argument(
        "--workers", 
        type=int, 
        default=3, 
        help="并行执行的最大进程数"
    )
    parser.add_argument(
        "--timeout", 
        type=int, 
        default=120, 
        help="单个文件超时时间（秒）"
    )
    parser.add_argument(
        "--detailed", 
        action="store_true", 
        help="显示详细结果"
    )
    parser.add_argument(
        "--report", 
        type=str, 
        help="生成报告文件路径"
    )
    
    args = parser.parse_args()
    
    # 设置路径
    current_dir = Path(__file__).parent
    tutorials_dir = current_dir.parent  # tutorials目录
    
    print("🚀 启动教学文档批量执行工具")
    print(f"📁 执行目录: {tutorials_dir}")
    print()
    
    # 创建执行器
    runner = TutorialRunner(tutorials_dir)
    
    # 执行教学文件
    if args.parallel:
        stats = runner.execute_all_parallel(args.workers, args.timeout)
    else:
        stats = runner.execute_all_sequential(args.timeout)
    
    # 打印结果
    if args.detailed:
        runner.print_detailed_results()
    
    runner.print_summary(stats)
    
    # 生成报告
    if args.report:
        runner.generate_report(args.report)
    
    # 设置退出码
    sys.exit(0 if stats['failed'] == 0 else 1)

if __name__ == "__main__":
    main()
```

## 4. 测试和质量保证

### 4.1 单元测试

**测试配置 (conftest.py):**
```python