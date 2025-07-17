# Project Argus QMT 数据代理服务教程

本目录包含 Project Argus QMT 数据代理服务的完整教程集合，旨在帮助开发者快速掌握如何使用该服务获取和处理金融市场数据。教程采用统一的代码风格和错误处理机制，提供了从基础到高级的功能演示。

## 1. 环境配置

### 1.1 系统要求

- **操作系统**: Windows 10/11
- **Python 版本**: 3.11.9 或更高版本（推荐使用 pyenv 管理版本）
- **内存要求**: 至少 8GB RAM
- **存储空间**: 至少 10GB 可用空间（用于数据缓存）

### 1.2 依赖安装

#### 方法一：使用虚拟环境（推荐）

```powershell
# 创建虚拟环境
python -m venv qmt_env

# 激活虚拟环境 (PowerShell)
.\qmt_env\Scripts\Activate.ps1

# 激活虚拟环境 (CMD)
qmt_env\Scripts\activate

# 验证环境完整性
Test-Path qmt_env\Scripts\python.exe

# 安装依赖包
pip install -r requirements.txt

# 退出虚拟环境
deactivate
```

#### 方法二：直接安装

```powershell
# 安装依赖包
pip install -r requirements.txt
```

### 1.3 配置验证

执行以下命令验证环境配置是否正确：

```powershell
# 检查 Python 版本
python --version

# 验证依赖包安装
python -c "import fastapi, uvicorn, httpx, pandas, numpy, matplotlib; print('依赖包安装正确')"

# 验证 QMT 数据代理服务连接
python qmt_status_check.py
```

## 2. 服务启动

### 2.1 启动 API 服务

```powershell
# 默认端口 8000
python server_direct.py --port 8000

# 或指定备用端口
python server_direct.py --port 8001
```

### 2.2 验证服务状态

服务启动后，可以通过以下方式验证服务状态：

1. 浏览器访问 API 文档：http://localhost:8000/docs
2. 执行状态检查脚本：`python qmt_status_check.py`
3. 使用 curl 测试基础 API：
   ```powershell
   curl "http://localhost:8000/api/v1/get_trading_dates?market=SH"
   ```

## 3. 教程目录

按照学习顺序排列的教程文件：

| 教程文件 | 功能描述 | 核心参数 | 难度 |
|----------|----------|----------|------|
| `01_trading_dates.py` | 交易日历查询 | market, start_date, end_date | ★☆☆ |
| `02_hist_kline.py` | 历史 K 线数据 | symbol, start_date, end_date, frequency | ★★☆ |
| `03_instrument_detail.py` | 合约详情查询 | symbol | ★☆☆ |
| `04_stock_list.py` | 板块股票列表 | sector | ★★☆ |
| `06_latest_market.py` | 最新行情数据 | symbols | ★★★ |
| `07_full_market.py` | 完整行情数据 | symbol, fields | ★★★ |

## 4. 学习路径建议

### 4.1 初学者路径

1. 首先学习 `01_trading_dates.py`，了解基本的 API 调用方式和错误处理
2. 然后学习 `03_instrument_detail.py`，掌握单一合约信息的获取
3. 接着学习 `04_stock_list.py`，了解如何获取板块成分股
4. 最后学习 `02_hist_kline.py`，掌握历史数据获取和处理

### 4.2 进阶学习路径

1. 学习 `06_latest_market.py`，掌握实时行情数据获取和处理
2. 学习 `07_full_market.py`，掌握深度行情分析和大数据处理
3. 探索 `common` 目录下的工具库，了解代码复用和模块化设计

## 5. 常见问题解答

### 5.1 连接问题

**Q: 为什么脚本运行时报连接错误？**  
A: 确认 API 服务已启动（端口 8000/8001），检查防火墙设置。可以通过以下命令检查端口是否被占用：
```powershell
netstat -ano | findstr :8000
```

**Q: 如何修改 API 服务端口？**  
A: 启动时添加 `--port` 参数，如 `python server_direct.py --port 8001`。同时需要在环境变量或配置文件中更新服务地址。

**Q: 如何设置 API 服务地址？**  
A: 可以通过环境变量设置：
```powershell
$env:DATA_AGENT_SERVICE_URL = "http://localhost:8001"  # PowerShell
set DATA_AGENT_SERVICE_URL=http://localhost:8001       # CMD
```
或者在 `common/config.py` 中修改默认配置。

### 5.2 数据问题

**Q: 模拟数据与实际数据差异大怎么办？**  
A: 模拟数据仅用于连通性测试，请确保 API 服务正常连接 xtquant 数据源。如果需要更真实的模拟数据，可以修改 `common/mock_data.py` 中的生成逻辑。

**Q: 如何处理大量数据的性能问题？**  
A: 参考 `07_full_market.py` 中的大数据处理优化部分，采用批处理、并行处理和数据缓存等技术。

**Q: 如何验证数据的准确性？**  
A: 可以将 API 返回的数据与 xtquant 直接调用的结果进行对比，确保数据一致性。

### 5.3 环境问题

**Q: 虚拟环境激活失败怎么办？**  
A: 确保使用正确的激活命令：
   - PowerShell: `.\qmt_env\Scripts\Activate.ps1`
   - CMD: `qmt_env\Scripts\activate`
   
   如果遇到执行策略限制，请以管理员身份运行：`Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Q: 如何验证虚拟环境是否正常工作？**  
A: 运行以下命令验证：
```powershell
# 检查 Python 路径
where python
# 应显示虚拟环境中的 python.exe 路径

# 检查已安装包
pip list
# 应包含 xtquant 等包
```

## 6. 性能优化建议

### 6.1 API 调用优化

- 使用连接池减少连接建立开销
- 批量获取数据而非频繁单次调用
- 合理设置超时时间和重试策略
- 使用异步调用提高并发性能

### 6.2 数据处理优化

- 使用 NumPy 和 Pandas 进行高效数据处理
- 对频繁访问的数据实现本地缓存
- 采用增量更新策略减少数据传输量
- 使用多线程处理大量数据

### 6.3 内存管理

- 及时释放不再使用的大型数据对象
- 使用生成器处理大型数据集
- 避免不必要的数据复制
- 定期监控内存使用情况

## 7. 扩展和自定义

### 7.1 添加新的 API 调用

可以通过扩展 `common/api_client.py` 中的 `QMTAPIClient` 类来添加新的 API 调用方法：

```python
def get_new_data(self, param1, param2):
    """获取新数据
    
    Args:
        param1: 参数1说明
        param2: 参数2说明
        
    Returns:
        Dict: 返回数据
    """
    endpoint = "/api/v1/get_new_data"
    params = {"param1": param1, "param2": param2}
    
    return self.call_api(endpoint, params)
```

### 7.2 自定义模拟数据

可以通过扩展 `common/mock_data.py` 中的 `MockDataGenerator` 类来添加新的模拟数据生成方法：

```python
def generate_new_data(self, param1, param2):
    """生成新的模拟数据
    
    Args:
        param1: 参数1说明
        param2: 参数2说明
        
    Returns:
        Dict: 模拟数据
    """
    # 生成模拟数据的逻辑
    mock_data = {
        "field1": "value1",
        "field2": 123,
        # ...
    }
    
    return {
        "code": 0,
        "message": "success",
        "data": mock_data
    }
```

### 7.3 添加新的工具函数

可以通过扩展 `common/utils.py` 来添加新的工具函数：

```python
def new_utility_function(param):
    """新的工具函数
    
    Args:
        param: 参数说明
        
    Returns:
        返回值说明
    """
    # 函数实现
    result = process(param)
    
    return result
```

## 8. 联系与支持

如有问题或需要支持，请通过以下方式联系我们：

- **项目仓库**: [GitHub 仓库地址]
- **问题报告**: 请在 GitHub Issues 中提交问题
- **文档网站**: [文档网站地址]

---

*本文档最后更新于: 2025年7月17日*
## 
9. 使用指南和最佳实践

### 9.1 教程使用最佳实践

#### 9.1.1 准备工作

在开始学习教程之前，建议完成以下准备工作：

1. **完整阅读本 README 文件**，了解整体结构和学习路径
2. **确保环境配置正确**，包括 Python 版本和依赖包安装
3. **启动 API 服务**，并验证服务状态
4. **准备好编辑器**，推荐使用 VS Code 或 PyCharm 等支持 Python 的 IDE

#### 9.1.2 学习方法

1. **按顺序学习**：教程设计遵循由简到难的原则，建议按照推荐的学习路径顺序学习
2. **边学边练**：每学习一个教程，尝试修改参数和代码，观察结果变化
3. **理解核心概念**：重点理解 API 调用模式、错误处理机制和数据处理流程
4. **查看源代码**：深入研究 `common` 目录下的工具库，了解实现细节

#### 9.1.3 实践建议

1. **创建自己的测试脚本**：基于教程示例，创建自己的测试脚本
2. **记录学习笔记**：记录重要概念、API 用法和常见问题
3. **参与讨论**：在项目仓库中提问或分享经验
4. **定期更新**：关注项目更新，及时获取最新功能和修复

### 9.2 性能优化详解

#### 9.2.1 API 调用性能优化

1. **使用连接池**

   ```python
   # 创建连接池
   from httpx import Client
   
   client = Client(
       base_url="http://localhost:8000",
       timeout=10.0,
       limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
   )
   
   # 使用连接池进行请求
   response = client.get("/api/v1/get_trading_dates", params={"market": "SH"})
   ```

2. **批量请求**

   ```python
   # 不推荐：多次单独请求
   for symbol in symbols:
       response = requests.get(f"http://localhost:8000/api/v1/instrument_detail?symbol={symbol}")
   
   # 推荐：批量请求
   response = requests.get(
       "http://localhost:8000/api/v1/latest_market",
       params={"symbols": ",".join(symbols)}
   )
   ```

3. **异步请求**

   ```python
   import asyncio
   import httpx
   
   async def fetch_data(symbols):
       async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
           tasks = []
           for symbol in symbols:
               tasks.append(client.get(f"/api/v1/instrument_detail?symbol={symbol}"))
           
           return await asyncio.gather(*tasks)
   
   # 使用异步请求
   results = asyncio.run(fetch_data(symbols))
   ```

#### 9.2.2 数据处理优化

1. **使用 NumPy 向量化操作**

   ```python
   # 不推荐：循环处理
   result = []
   for price in prices:
       result.append(price * 1.1)
   
   # 推荐：向量化操作
   import numpy as np
   result = np.array(prices) * 1.1
   ```

2. **Pandas 高效操作**

   ```python
   # 不推荐：逐行处理
   for i, row in df.iterrows():
       df.at[i, 'ma5'] = calculate_ma(row, 5)
   
   # 推荐：使用 rolling 函数
   df['ma5'] = df['close'].rolling(window=5).mean()
   ```

3. **数据缓存**

   ```python
   import functools
   
   @functools.lru_cache(maxsize=128)
   def get_trading_dates(market, start_date, end_date):
       # API 调用逻辑
       return dates
   
   # 使用缓存函数
   dates = get_trading_dates("SH", "20250101", "20250131")
   ```

#### 9.2.3 内存管理优化

1. **使用生成器处理大数据**

   ```python
   # 不推荐：一次性加载所有数据
   all_data = load_all_data(symbols)
   
   # 推荐：使用生成器逐步处理
   def data_generator(symbols):
       for symbol in symbols:
           yield load_data(symbol)
   
   for data in data_generator(symbols):
       process_data(data)
   ```

2. **及时释放大型对象**

   ```python
   # 处理大型数据后及时释放
   large_data = load_large_dataset()
   result = process_data(large_data)
   large_data = None  # 释放引用
   import gc
   gc.collect()  # 强制垃圾回收
   ```

### 9.3 故障排除进阶指南

#### 9.3.1 API 连接问题

1. **检查网络连接**

   ```powershell
   # 测试网络连接
   Test-NetConnection -ComputerName localhost -Port 8000
   
   # 检查 API 服务是否响应
   Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health"
   ```

2. **检查服务日志**

   ```powershell
   # 查看最近的服务日志
   Get-Content -Path ".\logs\server.log" -Tail 50
   ```

3. **重启服务**

   ```powershell
   # 停止当前服务进程
   $process = Get-Process -Name python | Where-Object { $_.CommandLine -like "*server_direct.py*" }
   Stop-Process -Id $process.Id
   
   # 重新启动服务
   Start-Process -FilePath "python" -ArgumentList "server_direct.py --port 8000"
   ```

#### 9.3.2 数据问题排查

1. **验证数据一致性**

   ```python
   # 比较 API 数据和直接调用数据
   api_data = requests.get("http://localhost:8000/api/v1/get_trading_dates", 
                          params={"market": "SH"}).json()["data"]
   
   # 如果可用，直接调用 xtdata 进行比较
   try:
       from xtquant import xtdata
       direct_data = xtdata.get_trading_dates(market="SH")
       print("数据一致性检查:", set(api_data) == set(direct_data))
   except ImportError:
       print("xtdata 不可用，无法直接比较")
   ```

2. **检查数据格式**

   ```python
   # 检查数据格式是否符合预期
   def validate_data_format(data, expected_fields):
       if not isinstance(data, dict):
           return False, "数据不是字典格式"
       
       missing_fields = [field for field in expected_fields if field not in data]
       if missing_fields:
           return False, f"缺少字段: {missing_fields}"
       
       return True, "数据格式正确"
   
   # 使用示例
   result, message = validate_data_format(
       api_response["data"], 
       ["open", "high", "low", "close", "volume"]
   )
   print(message)
   ```

#### 9.3.3 性能问题排查

1. **API 响应时间分析**

   ```python
   import time
   
   def measure_api_performance(url, params, iterations=10):
       total_time = 0
       for _ in range(iterations):
           start_time = time.time()
           response = requests.get(url, params=params)
           end_time = time.time()
           total_time += (end_time - start_time)
       
       avg_time = total_time / iterations
       print(f"平均响应时间: {avg_time:.4f} 秒")
   
   # 使用示例
   measure_api_performance(
       "http://localhost:8000/api/v1/get_trading_dates",
       {"market": "SH"}
   )
   ```

2. **内存使用监控**

   ```python
   import psutil
   import os
   
   def monitor_memory_usage():
       process = psutil.Process(os.getpid())
       memory_info = process.memory_info()
       print(f"内存使用: {memory_info.rss / 1024 / 1024:.2f} MB")
   
   # 在处理大数据前后监控内存
   monitor_memory_usage()
   process_large_data()
   monitor_memory_usage()
   ```

### 9.4 扩展开发示例

#### 9.4.1 创建自定义数据分析工具

```python
# 文件: my_analysis_tool.py
from common.api_client import create_api_client
from common.utils import print_section_header
import pandas as pd
import matplotlib.pyplot as plt

class MarketAnalyzer:
    """市场分析工具
    
    提供基于 QMT 数据的市场分析功能
    """
    
    def __init__(self):
        self.api_client = create_api_client()
    
    def analyze_sector_performance(self, sector, days=30):
        """分析板块表现
        
        Args:
            sector: 板块名称
            days: 分析天数
            
        Returns:
            DataFrame: 分析结果
        """
        print_section_header(f"分析 {sector} 板块表现")
        
        # 获取板块成分股
        stocks = self.api_client.get_stock_list(sector)
        
        # 获取每只股票的表现
        performance = []
        for stock in stocks[:10]:  # 取前10只股票示例
            data = self.api_client.get_hist_kline(
                stock, 
                start_date="20250101", 
                end_date="20250131"
            )
            
            if data:
                # 计算收益率
                first_price = data[0]["close"]
                last_price = data[-1]["close"]
                return_rate = (last_price - first_price) / first_price * 100
                
                performance.append({
                    "symbol": stock,
                    "name": data[0].get("name", ""),
                    "return_rate": return_rate,
                    "start_price": first_price,
                    "end_price": last_price
                })
        
        # 转换为 DataFrame
        df = pd.DataFrame(performance)
        
        # 可视化
        self._plot_performance(df, sector)
        
        return df
    
    def _plot_performance(self, df, sector):
        """绘制表现图表
        
        Args:
            df: 数据 DataFrame
            sector: 板块名称
        """
        plt.figure(figsize=(12, 6))
        plt.bar(df["symbol"], df["return_rate"])
        plt.title(f"{sector} 板块股票收益率")
        plt.xlabel("股票代码")
        plt.ylabel("收益率 (%)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

# 使用示例
if __name__ == "__main__":
    analyzer = MarketAnalyzer()
    result = analyzer.analyze_sector_performance("银行")
    print(result)
```

#### 9.4.2 创建自定义回测框架

```python
# 文件: simple_backtest.py
from common.api_client import create_api_client
from common.utils import print_section_header
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

class SimpleBacktester:
    """简单回测框架
    
    基于 QMT 数据的简单策略回测框架
    """
    
    def __init__(self):
        self.api_client = create_api_client()
        self.portfolio = {}
        self.cash = 100000.0
        self.trades = []
        self.nav = []
    
    def backtest(self, symbols, start_date, end_date, strategy_func):
        """执行回测
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            strategy_func: 策略函数，接收价格数据，返回交易信号
            
        Returns:
            Dict: 回测结果
        """
        print_section_header(f"执行回测 {start_date} 至 {end_date}")
        
        # 获取交易日历
        trading_dates = self.api_client.get_trading_dates("SH", start_date, end_date)
        
        # 获取历史数据
        historical_data = {}
        for symbol in symbols:
            data = self.api_client.get_hist_kline(symbol, start_date, end_date)
            if data:
                historical_data[symbol] = data
        
        # 执行回测
        for date in trading_dates:
            # 准备当日数据
            daily_data = {}
            for symbol, data in historical_data.items():
                for bar in data:
                    if bar["date"] == date:
                        daily_data[symbol] = bar
                        break
            
            # 执行策略
            signals = strategy_func(daily_data, self.portfolio)
            
            # 处理交易信号
            self._process_signals(signals, daily_data, date)
            
            # 计算当日净值
            nav = self._calculate_nav(daily_data, date)
            self.nav.append(nav)
        
        # 计算回测结果
        result = self._calculate_results()
        
        # 可视化结果
        self._plot_results()
        
        return result
    
    def _process_signals(self, signals, daily_data, date):
        """处理交易信号
        
        Args:
            signals: 交易信号字典 {symbol: action}，action 可以是 "buy", "sell", "hold"
            daily_data: 当日价格数据
            date: 交易日期
        """
        for symbol, action in signals.items():
            if symbol not in daily_data:
                continue
                
            price = daily_data[symbol]["close"]
            
            if action == "buy" and self.cash >= price * 100:
                # 买入 100 股
                shares = 100
                cost = price * shares
                
                if symbol in self.portfolio:
                    self.portfolio[symbol] += shares
                else:
                    self.portfolio[symbol] = shares
                
                self.cash -= cost
                
                self.trades.append({
                    "date": date,
                    "symbol": symbol,
                    "action": "buy",
                    "shares": shares,
                    "price": price,
                    "cost": cost
                })
                
            elif action == "sell" and symbol in self.portfolio and self.portfolio[symbol] > 0:
                # 卖出全部持仓
                shares = self.portfolio[symbol]
                income = price * shares
                
                self.portfolio[symbol] = 0
                self.cash += income
                
                self.trades.append({
                    "date": date,
                    "symbol": symbol,
                    "action": "sell",
                    "shares": shares,
                    "price": price,
                    "income": income
                })
    
    def _calculate_nav(self, daily_data, date):
        """计算当日净值
        
        Args:
            daily_data: 当日价格数据
            date: 交易日期
            
        Returns:
            Dict: 净值信息
        """
        equity = self.cash
        
        for symbol, shares in self.portfolio.items():
            if symbol in daily_data and shares > 0:
                equity += daily_data[symbol]["close"] * shares
        
        return {
            "date": date,
            "cash": self.cash,
            "equity": equity
        }
    
    def _calculate_results(self):
        """计算回测结果
        
        Returns:
            Dict: 回测结果统计
        """
        if not self.nav:
            return {"error": "没有回测数据"}
        
        initial_equity = self.nav[0]["equity"]
        final_equity = self.nav[-1]["equity"]
        
        return_rate = (final_equity - initial_equity) / initial_equity * 100
        
        return {
            "initial_equity": initial_equity,
            "final_equity": final_equity,
            "return_rate": return_rate,
            "trade_count": len(self.trades)
        }
    
    def _plot_results(self):
        """绘制回测结果图表"""
        if not self.nav:
            return
        
        # 提取数据
        dates = [nav["date"] for nav in self.nav]
        equity = [nav["equity"] for nav in self.nav]
        
        # 绘制净值曲线
        plt.figure(figsize=(12, 6))
        plt.plot(dates, equity)
        plt.title("回测净值曲线")
        plt.xlabel("日期")
        plt.ylabel("净值")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

# 策略示例
def simple_ma_strategy(daily_data, portfolio):
    """简单均线策略
    
    当价格上穿5日均线时买入，下穿时卖出
    
    Args:
        daily_data: 当日价格数据
        portfolio: 当前持仓
        
    Returns:
        Dict: 交易信号
    """
    signals = {}
    
    for symbol, data in daily_data.items():
        # 这里假设 data 中已经包含了 MA5
        # 实际使用时需要自行计算或从 API 获取
        price = data["close"]
        ma5 = data.get("ma5", price)  # 假设值
        
        if price > ma5 * 1.01:  # 上穿均线 1%
            signals[symbol] = "buy"
        elif price < ma5 * 0.99:  # 下穿均线 1%
            signals[symbol] = "sell"
        else:
            signals[symbol] = "hold"
    
    return signals

# 使用示例
if __name__ == "__main__":
    backtest = SimpleBacktester()
    result = backtest.backtest(
        symbols=["600519.SH", "000001.SZ"],
        start_date="20250101",
        end_date="20250331",
        strategy_func=simple_ma_strategy
    )
    print("回测结果:", result)
```

### 9.5 高级应用场景

#### 9.5.1 实时市场监控系统

```python
# 文件: market_monitor.py
from common.api_client import create_api_client
import time
import threading
import pandas as pd
from datetime import datetime

class MarketMonitor:
    """实时市场监控系统
    
    监控股票价格和交易量，触发预警
    """
    
    def __init__(self, symbols, check_interval=60):
        """初始化监控系统
        
        Args:
            symbols: 监控的股票列表
            check_interval: 检查间隔（秒）
        """
        self.api_client = create_api_client()
        self.symbols = symbols
        self.check_interval = check_interval
        self.alerts = []
        self.is_running = False
        self.monitor_thread = None
        
        # 初始化基准数据
        self.baseline_data = self._get_baseline_data()
    
    def _get_baseline_data(self):
        """获取基准数据
        
        Returns:
            Dict: 基准数据
        """
        baseline = {}
        
        # 获取最新行情作为基准
        result = self.api_client.get_latest_market(self.symbols)
        
        if result and "data" in result:
            for symbol, data in result["data"].items():
                baseline[symbol] = {
                    "last_price": data.get("current_price", 0),
                    "last_volume": data.get("volume", 0),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
        
        return baseline
    
    def start_monitoring(self):
        """启动监控"""
        if self.is_running:
            print("监控已在运行中")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        print(f"开始监控 {len(self.symbols)} 只股票，检查间隔 {self.check_interval} 秒")
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        print("监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                self._check_market_data()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"监控过程中出错: {e}")
                time.sleep(self.check_interval)
    
    def _check_market_data(self):
        """检查市场数据"""
        # 获取最新行情
        result = self.api_client.get_latest_market(self.symbols)
        
        if not result or "data" not in result:
            print("获取市场数据失败")
            return
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] 检查市场数据...")
        
        # 检查每只股票
        for symbol, data in result["data"].items():
            if symbol not in self.baseline_data:
                self.baseline_data[symbol] = {
                    "last_price": data.get("current_price", 0),
                    "last_volume": data.get("volume", 0),
                    "timestamp": current_time
                }
                continue
            
            # 获取当前数据
            current_price = data.get("current_price", 0)
            current_volume = data.get("volume", 0)
            
            # 获取基准数据
            baseline = self.baseline_data[symbol]
            baseline_price = baseline["last_price"]
            baseline_volume = baseline["last_volume"]
            
            # 计算变化
            price_change_pct = (current_price - baseline_price) / baseline_price * 100 if baseline_price else 0
            volume_change_pct = (current_volume - baseline_volume) / baseline_volume * 100 if baseline_volume else 0
            
            # 检查预警条件
            self._check_alerts(symbol, data, price_change_pct, volume_change_pct)
            
            # 更新基准数据
            self.baseline_data[symbol] = {
                "last_price": current_price,
                "last_volume": current_volume,
                "timestamp": current_time
            }
    
    def _check_alerts(self, symbol, data, price_change_pct, volume_change_pct):
        """检查预警条件
        
        Args:
            symbol: 股票代码
            data: 当前数据
            price_change_pct: 价格变化百分比
            volume_change_pct: 成交量变化百分比
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 价格大幅变化预警
        if abs(price_change_pct) >= 2:
            alert = {
                "timestamp": current_time,
                "symbol": symbol,
                "type": "price_alert",
                "message": f"{symbol} 价格变化 {price_change_pct:.2f}%",
                "data": {
                    "current_price": data.get("current_price", 0),
                    "price_change_pct": price_change_pct
                }
            }
            
            self.alerts.append(alert)
            print(f"🚨 价格预警: {alert['message']}")
        
        # 成交量大幅变化预警
        if volume_change_pct >= 50:
            alert = {
                "timestamp": current_time,
                "symbol": symbol,
                "type": "volume_alert",
                "message": f"{symbol} 成交量增加 {volume_change_pct:.2f}%",
                "data": {
                    "current_volume": data.get("volume", 0),
                    "volume_change_pct": volume_change_pct
                }
            }
            
            self.alerts.append(alert)
            print(f"🚨 成交量预警: {alert['message']}")
    
    def get_alerts(self, alert_type=None, limit=10):
        """获取预警记录
        
        Args:
            alert_type: 预警类型，None 表示所有类型
            limit: 返回记录数量限制
            
        Returns:
            List: 预警记录
        """
        if alert_type:
            filtered_alerts = [a for a in self.alerts if a["type"] == alert_type]
        else:
            filtered_alerts = self.alerts
        
        return filtered_alerts[-limit:]

# 使用示例
if __name__ == "__main__":
    # 监控主要指数和热门股票
    symbols = ["000001.SH", "399001.SZ", "600519.SH", "000858.SZ", "601318.SH"]
    
    monitor = MarketMonitor(symbols, check_interval=30)
    
    try:
        monitor.start_monitoring()
        
        # 运行一段时间
        time.sleep(300)  # 5分钟
        
        # 获取预警记录
        alerts = monitor.get_alerts()
        print(f"\n共有 {len(alerts)} 条预警记录:")
        for alert in alerts:
            print(f"[{alert['timestamp']}] {alert['message']}")
        
    except KeyboardInterrupt:
        print("\n用户中断监控")
    finally:
        monitor.stop_monitoring()
```

#### 9.5.2 数据导出工具

```python
# 文件: data_exporter.py
from common.api_client import create_api_client
import pandas as pd
import os
from datetime import datetime

class DataExporter:
    """数据导出工具
    
    将 QMT 数据导出为 CSV、Excel 或 JSON 格式
    """
    
    def __init__(self, output_dir="./exported_data"):
        """初始化导出工具
        
        Args:
            output_dir: 输出目录
        """
        self.api_client = create_api_client()
        self.output_dir = output_dir
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
    
    def export_hist_kline(self, symbol, start_date, end_date, frequency="1d", format="csv"):
        """导出历史K线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率
            format: 导出格式 (csv, excel, json)
            
        Returns:
            str: 输出文件路径
        """
        print(f"导出 {symbol} 从 {start_date} 到 {end_date} 的历史K线数据...")
        
        # 获取数据
        result = self.api_client.get_hist_kline(symbol, start_date, end_date, frequency)
        
        if not result or "data" not in result:
            print("获取数据失败")
            return None
        
        # 转换为 DataFrame
        df = pd.DataFrame(result["data"])
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol}_{start_date}_{end_date}_{frequency}_{timestamp}"
        
        # 导出数据
        output_path = self._export_dataframe(df, filename, format)
        
        print(f"数据已导出至: {output_path}")
        return output_path
    
    def export_stock_list(self, sector, format="csv"):
        """导出板块股票列表
        
        Args:
            sector: 板块名称
            format: 导出格式 (csv, excel, json)
            
        Returns:
            str: 输出文件路径
        """
        print(f"导出 {sector} 板块股票列表...")
        
        # 获取数据
        result = self.api_client.get_stock_list(sector)
        
        if not result or "data" not in result:
            print("获取数据失败")
            return None
        
        # 转换为 DataFrame
        df = pd.DataFrame(result["data"])
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stock_list_{sector}_{timestamp}"
        
        # 导出数据
        output_path = self._export_dataframe(df, filename, format)
        
        print(f"数据已导出至: {output_path}")
        return output_path
    
    def export_market_data(self, symbols, format="csv"):
        """导出市场数据
        
        Args:
            symbols: 股票代码列表
            format: 导出格式 (csv, excel, json)
            
        Returns:
            str: 输出文件路径
        """
        print(f"导出 {len(symbols)} 只股票的市场数据...")
        
        # 获取数据
        result = self.api_client.get_latest_market(symbols)
        
        if not result or "data" not in result:
            print("获取数据失败")
            return None
        
        # 转换为 DataFrame
        data_list = []
        for symbol, data in result["data"].items():
            data["symbol"] = symbol
            data_list.append(data)
        
        df = pd.DataFrame(data_list)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"market_data_{timestamp}"
        
        # 导出数据
        output_path = self._export_dataframe(df, filename, format)
        
        print(f"数据已导出至: {output_path}")
        return output_path
    
    def _export_dataframe(self, df, filename, format):
        """导出 DataFrame
        
        Args:
            df: DataFrame 对象
            filename: 文件名（不含扩展名）
            format: 导出格式 (csv, excel, json)
            
        Returns:
            str: 输出文件路径
        """
        if format.lower() == "csv":
            output_path = os.path.join(self.output_dir, f"{filename}.csv")
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
        elif format.lower() == "excel":
            output_path = os.path.join(self.output_dir, f"{filename}.xlsx")
            df.to_excel(output_path, index=False)
        elif format.lower() == "json":
            output_path = os.path.join(self.output_dir, f"{filename}.json")
            df.to_json(output_path, orient="records", force_ascii=False, indent=4)
        else:
            raise ValueError(f"不支持的导出格式: {format}")
        
        return output_path

# 使用示例
if __name__ == "__main__":
    exporter = DataExporter()
    
    # 导出历史K线数据
    exporter.export_hist_kline(
        symbol="600519.SH",
        start_date="20250101",
        end_date="20250131",
        format="csv"
    )
    
    # 导出板块股票列表
    exporter.export_stock_list(
        sector="银行",
        format="excel"
    )
    
    # 导出市场数据
    exporter.export_market_data(
        symbols=["600519.SH", "000001.SZ", "601318.SH"],
        format="json"
    )
```

这些高级应用示例展示了如何基于 QMT 数据代理服务构建更复杂的应用，包括市场分析工具、回测框架、实时监控系统和数据导出工具。您可以根据自己的需求进行修改和扩展。