
# API文档

## TutorialValidator

教程验证器，负责检测和修复教程中的错误。

### 方法

#### `validate_tutorial(tutorial_path: Path) -> ValidationResult`

验证单个教程文件。

**参数:**
- `tutorial_path`: 教程文件路径

**返回:**
- `ValidationResult`: 验证结果对象

#### `generate_validation_report() -> str`

生成验证报告。

**返回:**
- `str`: Markdown格式的验证报告

## TutorialEnhancer

教程增强器，负责添加详细的文字指导和优化代码结构。

### 方法

#### `enhance_tutorial(tutorial_path: Path) -> EnhancementResult`

增强单个教程文件。

**参数:**
- `tutorial_path`: 教程文件路径

**返回:**
- `EnhancementResult`: 增强结果对象

#### `generate_enhancement_report() -> str`

生成增强报告。

**返回:**
- `str`: Markdown格式的增强报告

## NotebookConverter

Notebook转换器，负责将Python脚本转换为Jupyter Notebook格式。

### 方法

#### `convert_tutorial(python_file: Path) -> ConversionResult`

转换单个Python文件为Notebook。

**参数:**
- `python_file`: Python文件路径

**返回:**
- `ConversionResult`: 转换结果对象

#### `generate_conversion_report() -> str`

生成转换报告。

**返回:**
- `str`: Markdown格式的转换报告

## TutorialProcessor

主教程处理器，整合所有处理步骤。

### 方法

#### `run_complete_pipeline() -> Dict[str, Any]`

运行完整的处理流水线。

**返回:**
- `Dict[str, Any]`: 完整的处理结果

## 数据结构

### ValidationResult

```python
@dataclass
class ValidationResult:
    tutorial_name: str
    validation_success: bool
    errors: List[str]
    warnings: List[str]
    fixes_applied: List[str]
    timestamp: datetime.datetime
```

### EnhancementResult

```python
@dataclass
class EnhancementResult:
    tutorial_name: str
    enhancements_applied: List[str]
    docstrings_added: int
    comments_added: int
    learning_objectives_added: bool
    background_knowledge_added: bool
    best_practices_added: bool
    timestamp: datetime.datetime
```

### ConversionResult

```python
@dataclass
class ConversionResult:
    source_file: str
    notebook_file: str
    cell_count: int
    code_cells: int
    markdown_cells: int
    visualization_cells: int
    conversion_success: bool
    error_message: str
    timestamp: datetime.datetime
```
