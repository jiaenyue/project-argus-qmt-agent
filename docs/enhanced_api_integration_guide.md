# 增强API集成指南

## 概述

增强历史数据API为原有的历史K线数据接口提供了多周期支持、数据质量监控、智能缓存和标准化数据格式等功能。本指南详细介绍如何使用这些增强功能。

## 功能特性

### 1. 多周期支持
- **支持周期**: 1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M
- **自动转换**: 基础数据自动聚合为目标周期
- **时间对齐**: 确保不同周期数据的时间一致性

### 2. 数据质量监控
- **完整性检查**: 检测数据缺失和时间间隔
- **准确性验证**: OHLC逻辑关系验证
- **一致性分析**: 跨周期数据一致性检查
- **异常检测**: 识别价格和成交量异常

### 3. 智能缓存
- **分层TTL**: 不同周期设置不同缓存时间
- **热点预加载**: 自动预加载常用股票数据
- **LRU清理**: 智能缓存空间管理

### 4. 标准化格式
- **统一JSON**: 标准化的数据结构
- **精度控制**: 价格精确到4位小数，成交量为整数
- **时区处理**: ISO 8601格式时间戳

## API端点

### 1. 增强历史K线数据

```http
GET /hist_kline?enhanced=true
```

#### 参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 股票代码，格式：600519.SH |
| start_date | string | 是 | 开始日期，格式：YYYYMMDD |
| end_date | string | 是 | 结束日期，格式：YYYYMMDD |
| frequency | string | 是 | 数据周期：1m/5m/15m/30m/1h/1d/1w/1M |
| enhanced | boolean | 否 | 是否使用增强API，默认false |
| include_quality | boolean | 否 | 是否包含质量指标，默认false |
| normalize | boolean | 否 | 是否标准化数据，默认true |

#### 响应格式

```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2024-01-01T00:00:00+08:00",
      "open": 1850.0000,
      "high": 1865.0000,
      "low": 1845.0000,
      "close": 1860.0000,
      "volume": 1234567,
      "amount": 2345678900.00,
      "quality_score": 1.0
    }
  ],
  "quality_report": {
    "completeness_rate": 1.0,
    "accuracy_score": 0.98,
    "timeliness_score": 1.0,
    "consistency_score": 0.99,
    "anomaly_count": 0
  },
  "metadata": {
    "symbol": "600519.SH",
    "period": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "total_records": 21,
    "cache_hit": true,
    "response_time_ms": 45
  },
  "status": 200
}
```

### 2. 多周期历史数据

```http
GET /multi_period_data
```

#### 参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 股票代码 |
| start_date | string | 是 | 开始日期，格式：YYYYMMDD |
| end_date | string | 是 | 结束日期，格式：YYYYMMDD |
| periods | string | 是 | 周期列表，逗号分隔：1d,1w,1M |
| include_quality | boolean | 否 | 是否包含质量指标，默认true |

#### 响应格式

```json
{
  "success": true,
  "data": {
    "1d": [...],
    "1w": [...],
    "1M": [...]
  },
  "quality_reports": {
    "1d": {...},
    "1w": {...},
    "1M": {...}
  },
  "metadata": {
    "symbol": "600519.SH",
    "periods": ["1d", "1w", "1M"],
    "total_periods": 3
  },
  "status": 200
}
```

## 使用示例

### Python示例

```python
import requests

# 基础增强API调用
def get_enhanced_kline_data(symbol, start_date, end_date, frequency="1d"):
    url = "http://localhost:8000/hist_kline"
    params = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "frequency": frequency,
        "enhanced": True,
        "include_quality": True,
        "normalize": True
    }
    
    response = requests.get(url, params=params)
    return response.json()

# 多周期数据调用
def get_multi_period_data(symbol, start_date, end_date, periods):
    url = "http://localhost:8000/multi_period_data"
    params = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "periods": ",".join(periods),
        "include_quality": True
    }
    
    response = requests.get(url, params=params)
    return response.json()

# 使用示例
if __name__ == "__main__":
    # 获取贵州茅台日线数据
    result = get_enhanced_kline_data(
        symbol="600519.SH",
        start_date="20240101",
        end_date="20240131",
        frequency="1d"
    )
    
    if result["success"]:
        print(f"获取到 {len(result['data'])} 条数据")
        print(f"数据质量评分: {result['quality_report']['accuracy_score']}")
        print(f"缓存命中: {result['metadata']['cache_hit']}")
    
    # 获取多周期数据
    multi_result = get_multi_period_data(
        symbol="600519.SH",
        start_date="20240101",
        end_date="20240131",
        periods=["1d", "1w"]
    )
    
    if multi_result["success"]:
        for period, data in multi_result["data"].items():
            print(f"{period}周期: {len(data)}条数据")
```

### JavaScript示例

```javascript
// 基础增强API调用
async function getEnhancedKlineData(symbol, startDate, endDate, frequency = "1d") {
    const url = "http://localhost:8000/hist_kline";
    const params = new URLSearchParams({
        symbol: symbol,
        start_date: startDate,
        end_date: endDate,
        frequency: frequency,
        enhanced: true,
        include_quality: true,
        normalize: true
    });
    
    const response = await fetch(`${url}?${params}`);
    return await response.json();
}

// 使用示例
getEnhancedKlineData("600519.SH", "20240101", "20240131", "1d")
    .then(result => {
        if (result.success) {
            console.log(`获取到 ${result.data.length} 条数据`);
            console.log(`数据质量评分: ${result.quality_report.accuracy_score}`);
            console.log(`缓存命中: ${result.metadata.cache_hit}`);
        }
    })
    .catch(error => {
        console.error("API调用失败:", error);
    });
```

## 向后兼容性

增强API完全向后兼容原有接口：

1. **默认行为**: 不指定`enhanced=true`时使用原始API
2. **响应格式**: 原始API响应格式保持不变
3. **参数兼容**: 所有原有参数继续有效
4. **错误处理**: 增强API不可用时自动回退到原始API

## 性能优化

### 缓存策略

| 周期 | TTL | 说明 |
|------|-----|------|
| 1m, 5m | 1小时 | 短周期数据更新频繁 |
| 15m, 30m | 2-4小时 | 中等周期数据 |
| 1h | 8小时 | 小时级数据 |
| 1d | 24小时 | 日线数据 |
| 1w, 1M | 7天 | 长周期数据稳定 |

### 性能指标

- **响应时间**: 缓存命中 < 50ms，缓存未命中 < 500ms
- **缓存命中率**: 目标 > 80%
- **数据质量**: 准确性评分 > 0.95
- **并发支持**: 支持100+并发请求

## 错误处理

### 错误类型

1. **参数错误**: 400状态码，详细错误信息
2. **数据源错误**: 503状态码，自动重试机制
3. **缓存错误**: 自动回退到数据源
4. **网络错误**: 指数退避重试

### 错误响应格式

```json
{
  "success": false,
  "message": "详细错误信息",
  "error_type": "DataValidationError",
  "status": 400,
  "request_id": "req_123456789"
}
```

## 监控和日志

### 日志级别

- **INFO**: 正常API调用和响应
- **WARNING**: 数据质量问题和回退操作
- **ERROR**: API调用失败和系统错误

### 监控指标

- API调用次数和成功率
- 响应时间分布
- 缓存命中率
- 数据质量指标
- 错误类型统计

## 最佳实践

### 1. 周期选择

- **技术分析**: 使用1d, 1w, 1M进行趋势分析
- **短线交易**: 使用1m, 5m, 15m进行入场时机
- **风险控制**: 使用30m, 1h进行止损设置

### 2. 缓存利用

- **批量查询**: 使用多周期API减少请求次数
- **时间范围**: 合理设置查询范围，避免过大数据集
- **预加载**: 对常用股票启用预加载功能

### 3. 质量监控

- **定期检查**: 监控数据质量指标变化
- **异常处理**: 对质量评分低的数据进行人工检查
- **阈值设置**: 根据业务需求设置质量阈值

### 4. 错误处理

- **重试机制**: 实现指数退避重试
- **降级策略**: 增强API不可用时使用原始API
- **日志记录**: 详细记录错误信息用于问题排查

## 故障排除

### 常见问题

1. **增强API不可用**
   - 检查导入路径是否正确
   - 确认增强模块是否已安装
   - 查看服务器日志获取详细错误信息

2. **数据质量评分低**
   - 检查数据源连接状态
   - 验证股票代码和时间范围
   - 查看异常数据详情

3. **缓存命中率低**
   - 检查缓存配置是否正确
   - 确认缓存服务是否正常运行
   - 调整缓存TTL设置

4. **响应时间慢**
   - 检查数据源响应时间
   - 优化查询参数和时间范围
   - 启用缓存预加载功能

### 调试工具

- 使用`include_quality=true`获取详细质量报告
- 查看`metadata`中的性能指标
- 启用详细日志记录
- 使用监控面板查看系统状态

## 更新日志

### v1.0.0 (2024-01-15)
- 初始版本发布
- 支持多周期数据获取
- 实现数据质量监控
- 添加智能缓存机制

### v1.1.0 (2024-02-01)
- 增加多周期API端点
- 优化缓存策略
- 改进错误处理机制
- 添加性能监控指标

## 联系支持

如有问题或建议，请通过以下方式联系：

- 项目仓库: [GitHub Issues](https://github.com/your-repo/issues)
- 技术文档: [API文档](https://your-docs-site.com)
- 邮件支持: support@your-domain.com