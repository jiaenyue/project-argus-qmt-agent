# 环境设置说明

## Python 环境
- **Python 版本**: 3.10.18
- **环境管理**: Conda
- **环境名称**: qmt_py310

## 激活环境

### 方法1: 使用批处理脚本
```bash
activate_env.bat
```

### 方法2: 手动激活
```bash
conda activate qmt_py310
```

## 验证环境
激活环境后，运行以下命令验证：
```bash
python --version  # 应该显示 Python 3.10.18
python -c "import xtquant; print('xtquant OK')"
```

## 已安装的主要依赖
- fastapi - Web框架
- uvicorn - ASGI服务器
- httpx - HTTP客户端
- xtquant - 量化交易库
- tushare - 金融数据API
- rqdatac - 米筐量化数据API
- python-dotenv - 环境变量管理
- jupyter/notebook - 数据分析环境
- pandas, numpy - 数据处理

## 启动服务
```bash
# 启动FastAPI服务
uvicorn data_agent_service.main:app --reload

# 启动Jupyter Notebook
jupyter notebook
```

## 验证系统运行
启动服务并验证运行状态：

```bash
# 启动主服务
python main.py

# 或使用数据代理服务
cd data_agent_service
python main.py
```

服务启动后，可以通过浏览器访问 http://localhost:8000/docs 查看API文档并测试接口。

## 注意事项
- 旧的venv环境(qmt_env)已被弃用，请使用新的conda环境
- 确保每次工作前都激活正确的conda环境
- Tushare需要在.env文件中配置TUSHARE_TOKEN
- xtquant需要QMT客户端运行