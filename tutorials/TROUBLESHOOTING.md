# 故障排除指南 - Project Argus QMT 数据代理服务教程

本指南提供了使用真实数据时可能遇到的常见问题及其解决方案。

## 快速诊断

在开始故障排除之前，可以运行以下Python代码进行快速诊断：

```python
from common.utils import print_data_requirements_check, print_troubleshooting_guide

# 检查前置条件
print_data_requirements_check()

# 显示故障排除指导
print_troubleshooting_guide()
```

## 1. API连接问题

### 1.1 "连接被拒绝" 或 "无法连接到服务器"

**症状**: 教程运行时显示连接错误，无法访问API服务

**可能原因**:
- API服务未启动
- 端口被占用或防火墙阻止
- 服务地址配置错误

**解决步骤**:

1. **检查API服务状态**:
   ```powershell
   # 检查端口占用情况
   netstat -ano | findstr :8000
   
   # 测试API服务响应
   curl http://localhost:8000/api/v1/health
   ```

2. **启动API服务**:
   ```powershell
   # 启动默认端口服务
   python server_direct.py
   
   # 或指定端口
   python server_direct.py --port 8001
   ```

3. **验证服务运行**:
   - 浏览器访问: http://localhost:8000/docs
   - 应该看到API文档页面

### 1.2 "请求超时"

**症状**: API调用长时间无响应，最终超时

**可能原因**:
- 网络连接不稳定
- 服务器负载过高
- 数据源响应慢

**解决步骤**:

1. **检查网络连接**:
   ```powershell
   ping localhost
   Test-NetConnection -ComputerName localhost -Port 8000
   ```

2. **增加超时时间**:
   ```python
   # 在API调用中增加超时参数
   import requests
   response = requests.get(url, timeout=30)  # 增加到30秒
   ```

3. **检查系统资源**:
   ```powershell
   # 检查CPU和内存使用
   Get-Process -Name python
   ```

## 2. 数据获取问题

### 2.1 "无法获取数据" 或返回空结果

**症状**: API调用成功但返回空数据或错误信息

**可能原因**:
- 股票代码格式错误
- 查询日期范围无效
- 数据源暂时不可用
- 权限不足

**解决步骤**:

1. **验证股票代码格式**:
   ```python
   # 正确格式示例
   valid_symbols = [
       "600519.SH",  # 上海证券交易所
       "000001.SZ",  # 深圳证券交易所
       "399001.SZ"   # 深圳指数
   ]
   
   # 错误格式示例
   invalid_symbols = [
       "600519",     # 缺少交易所后缀
       "SH600519",   # 格式错误
       "600519.sh"   # 大小写错误
   ]
   ```

2. **检查日期范围**:
   ```python
   from datetime import datetime, timedelta
   
   # 确保日期范围合理
   end_date = datetime.now().strftime("%Y-%m-%d")
   start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
   
   print(f"查询日期范围: {start_date} 到 {end_date}")
   ```

3. **测试简单查询**:
   ```python
   # 使用已知有效的参数进行测试
   from common.api_client import create_api_client
   
   client = create_api_client()
   result = client.get_trading_dates("SH")
   
   if result and result.get("code") == 0:
       print("API基本功能正常")
   else:
       print(f"API调用失败: {result}")
   ```

### 2.2 "数据格式错误" 或解析失败

**症状**: 获取到数据但无法正确解析或格式异常

**可能原因**:
- API返回格式变更
- 数据类型不匹配
- 编码问题

**解决步骤**:

1. **检查原始响应**:
   ```python
   import requests
   import json
   
   response = requests.get("http://localhost:8000/api/v1/get_trading_dates?market=SH")
   print(f"状态码: {response.status_code}")
   print(f"响应头: {response.headers}")
   print(f"原始内容: {response.text}")
   
   try:
       data = response.json()
       print(f"JSON数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
   except json.JSONDecodeError as e:
       print(f"JSON解析失败: {e}")
   ```

2. **验证数据结构**:
   ```python
   def validate_api_response(response):
       """验证API响应格式"""
       if not isinstance(response, dict):
           return False, "响应不是字典格式"
       
       if "code" not in response:
           return False, "缺少状态码字段"
       
       if response["code"] != 0:
           return False, f"API返回错误: {response.get('message', '未知错误')}"
       
       if "data" not in response:
           return False, "缺少数据字段"
       
       return True, "响应格式正确"
   ```

## 3. xtdata集成问题

### 3.1 "xtdata模块导入失败"

**症状**: 运行教程时提示无法导入xtdata模块

**可能原因**:
- xtdata未正确安装
- Python环境路径问题
- 版本兼容性问题

**解决步骤**:

1. **验证安装**:
   ```python
   try:
       import xtquant
       print(f"xtquant版本: {xtquant.__version__}")
       
       from xtquant import xtdata
       print("xtdata导入成功")
   except ImportError as e:
       print(f"导入失败: {e}")
   ```

2. **检查安装路径**:
   ```python
   import sys
   print("Python路径:")
   for path in sys.path:
       print(f"  {path}")
   ```

3. **重新安装xtdata**:
   ```powershell
   # 卸载现有版本
   pip uninstall xtquant
   
   # 重新安装
   pip install xtquant
   ```

### 3.2 "xtdata连接失败"

**症状**: xtdata模块导入成功但无法获取数据

**可能原因**:
- xtdata客户端未运行
- 账户权限问题
- 数据订阅过期

**解决步骤**:

1. **检查xtdata客户端**:
   - 确认xtdata客户端程序已启动
   - 验证登录状态和连接状态

2. **测试基本功能**:
   ```python
   from xtquant import xtdata
   
   try:
       # 测试获取交易日历
       dates = xtdata.get_trading_dates("SH")
       print(f"获取到{len(dates)}个交易日")
       
       # 测试获取股票列表
       stocks = xtdata.get_stock_list_in_sector("银行")
       print(f"银行板块有{len(stocks)}只股票")
       
   except Exception as e:
       print(f"xtdata调用失败: {e}")
   ```

3. **检查权限和订阅**:
   - 确认账户是否有相应数据权限
   - 检查数据订阅是否有效
   - 联系数据提供商确认服务状态

## 4. 性能问题

### 4.1 响应速度慢

**症状**: API调用响应时间过长

**诊断方法**:

```python
import time
import requests

def measure_api_performance(url, params=None, iterations=5):
    """测量API性能"""
    times = []
    
    for i in range(iterations):
        start = time.time()
        try:
            response = requests.get(url, params=params, timeout=10)
            end = time.time()
            times.append(end - start)
            print(f"第{i+1}次: {end-start:.2f}秒 (状态码: {response.status_code})")
        except Exception as e:
            print(f"第{i+1}次: 失败 - {e}")
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"平均响应时间: {avg_time:.2f}秒")
        print(f"最快: {min(times):.2f}秒, 最慢: {max(times):.2f}秒")

# 使用示例
measure_api_performance("http://localhost:8000/api/v1/get_trading_dates", {"market": "SH"})
```

**优化建议**:

1. **减少数据量**:
   - 缩小日期范围
   - 减少查询的股票数量
   - 使用分页查询

2. **使用缓存**:
   ```python
   import functools
   
   @functools.lru_cache(maxsize=128)
   def cached_api_call(symbol, start_date, end_date):
       # API调用逻辑
       pass
   ```

3. **并行处理**:
   ```python
   import concurrent.futures
   import requests
   
   def fetch_data(symbol):
       # 单个股票数据获取
       pass
   
   symbols = ["600519.SH", "000001.SZ", "601318.SH"]
   
   with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
       results = list(executor.map(fetch_data, symbols))
   ```

### 4.2 内存使用过高

**症状**: 程序运行时内存占用持续增长

**监控方法**:

```python
import psutil
import os

def monitor_memory():
    """监控内存使用"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    print(f"内存使用: {memory_info.rss / 1024 / 1024:.2f} MB")
    print(f"虚拟内存: {memory_info.vms / 1024 / 1024:.2f} MB")

# 在关键位置调用
monitor_memory()
```

**优化建议**:

1. **及时释放大对象**:
   ```python
   large_data = get_large_dataset()
   process_data(large_data)
   large_data = None  # 显式释放
   
   import gc
   gc.collect()  # 强制垃圾回收
   ```

2. **使用生成器**:
   ```python
   def data_generator(symbols):
       for symbol in symbols:
           yield get_data(symbol)
   
   # 逐个处理而不是一次性加载所有数据
   for data in data_generator(symbols):
       process(data)
   ```

## 5. 环境问题

### 5.1 虚拟环境问题

**症状**: 包导入失败或版本冲突

**解决步骤**:

1. **验证虚拟环境**:
   ```powershell
   # 检查当前Python路径
   where python
   
   # 应该指向虚拟环境中的python.exe
   # 例如: .\qmt_env\Scripts\python.exe
   ```

2. **重新创建虚拟环境**:
   ```powershell
   # 删除现有环境
   Remove-Item -Recurse -Force qmt_env
   
   # 创建新环境
   python -m venv qmt_env
   
   # 激活环境
   .\qmt_env\Scripts\Activate.ps1
   
   # 安装依赖
   pip install -r requirements.txt
   ```

### 5.2 权限问题

**症状**: 无法创建文件或访问某些资源

**解决步骤**:

1. **以管理员身份运行**:
   - 右键点击PowerShell或命令提示符
   - 选择"以管理员身份运行"

2. **检查文件权限**:
   ```powershell
   # 检查当前目录权限
   Get-Acl . | Format-List
   ```

## 6. 获取帮助

如果以上解决方案都无法解决问题，请：

1. **收集错误信息**:
   - 完整的错误消息
   - 运行环境信息（Python版本、操作系统等）
   - 重现问题的步骤

2. **运行诊断工具**:
   ```python
   from common.utils import diagnose_api_connection, validate_real_data_requirements
   
   # API连接诊断
   diagnosis = diagnose_api_connection()
   print(diagnosis)
   
   # 前置条件验证
   validation = validate_real_data_requirements()
   print(validation)
   ```

3. **查看日志文件**:
   - 检查API服务日志
   - 查看Python错误堆栈

4. **联系支持**:
   - 在项目仓库中提交Issue
   - 提供详细的错误信息和环境描述
   - 包含诊断工具的输出结果

---

*本故障排除指南最后更新于: 2025年7月19日*