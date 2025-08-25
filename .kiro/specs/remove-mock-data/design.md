# 设计文档：移除模拟数据使用

## 概述

本设计文档概述了从所有 Project Argus QMT 数据代理服务教程中移除模拟数据使用的方法。目前，当 API 调用失败或数据服务不可用时，教程使用模拟数据生成器作为回退方案。本设计详细说明了确保所有教程仅使用来自 API 或 xtdata 库的真实数据所需的更改，以及用适当的错误处理替代模拟数据回退。

## 架构

当前教程架构包括：

1. **API 客户端层**：处理与 Project Argus QMT 数据代理服务的通信
2. **模拟数据层**：在 API 调用失败时提供回退数据（将被移除）
3. **数据处理层**：将原始数据转换为用于分析的 pandas DataFrames
4. **可视化层**：创建图表和可视化，展示数据

修改后的架构将：

1. **API 客户端层**：处理与 Project Argus QMT 数据代理服务的通信，增强错误处理
2. **数据处理层**：将原始数据转换为 pandas DataFrames，适当处理空或错误结果
3. **可视化层**：创建图表和可视化，优雅处理缺失数据

## 组件和接口

### 1. API 客户端函数

需要修改 API 客户端函数以移除模拟数据回退：

```python
# 当前带有模拟数据回退的模式
def get_hist_kline_data(symbol, start_date, end_date, frequency):
    result = safe_api_call(api_client, api_client.get_hist_kline, symbol, start_date, end_date, frequency)
    
    if result.get("code") != 0:
        print("  API调用失败，使用模拟数据")
        result = mock_generator.generate_hist_kline(...)  # 这部分将被移除
```

```python
# 新的带有适当错误处理的模式
def get_hist_kline_data(symbol, start_date, end_date, frequency):
    result = safe_api_call(api_client, api_client.get_hist_kline, symbol, start_date, end_date, frequency)
    
    if result.get("code") != 0:
        print(f"  API调用失败: {result.get('message', '未知错误')}")
        print("  请检查网络连接和API配置，确保数据服务可用")
        return pd.DataFrame()  # 返回空 DataFrame 而不是模拟数据
```

### 2. xtdata 集成

xtdata 集成也需要修改以移除模拟数据回退：

```python
# 当前带有模拟数据回退的模式
try:
    # xtdata 调用
    local_kline_data_raw = xtdata.get_market_data(...)
    # 处理数据
except Exception as e:
    print(f"  xtdata调用失败: {e}")
    # 回退到模拟数据或 API 数据
```

```python
# 新的带有适当错误处理的模式
try:
    # xtdata 调用
    local_kline_data_raw = xtdata.get_market_data(...)
    # 处理数据
except Exception as e:
    print(f"  xtdata调用失败: {e}")
    print("  请确保xtdata环境已正确配置，并且数据服务可用")
    return pd.DataFrame()  # 返回空 DataFrame 而不是模拟数据
```

### 3. 数据处理函数

数据处理函数需要更新以优雅处理空或错误结果：

```python
# 当前带有模拟数据生成的模式
if df.empty:
    print("  未获取到实际数据，创建示例数据用于演示")
    # 创建模拟数据
    dates = pd.date_range(start=start_date, end=end_date, freq="B")
    data = {
        "open": [100 + i * 0.1 for i in range(len(dates))],
        # 更多模拟数据...
    }
    df = pd.DataFrame(data, index=dates)
```

```python
# 新的带有适当空数据处理的模式
if df.empty:
    print("  未获取到数据，请检查API连接和参数设置")
    return df  # 返回空 DataFrame 而不创建模拟数据
```

## 数据模型

数据模型保持不变，但将改进空或错误结果的处理：

1. **API 响应格式**：
   ```python
   {
       'code': 0,  # 状态码（0表示成功）
       'message': 'success',  # 状态消息
       'data': [...]  # 数据点
   }
   ```

2. **DataFrame 格式**：
   ```python
   pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
   ```

## 错误处理

错误处理策略将得到增强：

1. **具体错误消息**：提供解释失败原因的清晰错误消息
2. **故障排除指导**：包括解决常见问题的建议
3. **优雅降级**：处理空或错误结果而不崩溃
4. **一致模式**：在所有教程中使用一致的错误处理模式

错误消息将包括：
- API 连接问题
- 数据服务可用性
- 配置问题
- 参数验证错误
- 空结果处理

## 测试策略

移除模拟数据使用的测试策略包括：

1. **功能测试**：确保所有教程使用真实数据正确运行
2. **错误情况测试**：验证数据服务不可用时的适当错误处理
3. **空结果测试**：测试空结果的处理
4. **集成测试**：测试与 API 和 xtdata 服务的集成
5. **Jupyter 转换测试**：确保修改后的教程可以成功转换为 ipynb 格式并运行

## 实施方法

实施将遵循以下步骤：

1. **识别模拟数据使用**：定位教程中所有模拟数据生成的实例
2. **移除模拟数据回退**：用适当的错误处理替换模拟数据回退
3. **增强错误消息**：改进错误消息，提供清晰的解释和故障排除指导
4. **更新数据处理**：修改数据处理函数以优雅处理空或错误结果
5. **使用真实数据测试**：使用真实数据测试所有教程，确保它们正确工作
6. **测试错误场景**：测试错误场景以验证适当的错误处理
7. **测试 Jupyter 转换**：确保修改后的教程可以成功转换为 ipynb 格式并运行

这些更改将应用于所有教程，以确保数据检索和错误处理的一致方法。