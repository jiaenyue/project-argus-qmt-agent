# 增强历史K线API使用指南

本指南详细介绍如何使用增强的历史K线API，包括多周期支持、数据质量监控、缓存优化和性能调优。

## 目录

1. [功能概述](#功能概述)
2. [快速开始](#快速开始)
3. [多周期数据获取](#多周期数据获取)
4. [数据质量监控](#数据质量监控)
5. [缓存优化策略](#缓存优化策略)
6. [性能优化技巧](#性能优化技巧)
7. [错误处理机制](#错误处理机制)
8. [最佳实践](#最佳实践)
9. [示例代码](#示例代码)

## 功能概述

增强的历史K线API提供以下核心功能：

### 🚀 核心特性

- **多周期支持**: 支持8种时间周期（1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M）
- **数据质量监控**: 实时监控数据完整性、准确性和一致性
- **智能缓存**: 根据数据周期自动设置缓存TTL策略
- **标准化格式**: 统一的JSON格式和数据类型
- **异步处理**: 支持高并发异步请求
- **错误恢复**: 完善的重试机制和降级策略

### 📊 质量保证

- **OHLC逻辑验证**: 自动验证开高低收价格逻辑关系
- **异常数据检测**: 使用统计方法检测价格和成交量异常
- **数据完整性检查**: 检测缺失值和数据格式错误
- **质量评分系统**: 提供综合质量评分和改进建议

### ⚡ 性能优化

- **差异化缓存**: 不同周期数据使用不同的缓存TTL
- **批量获取**: 支持并发获取多只股票数据
- **内存优化**: 智能内存管理和垃圾回收
- **性能监控**: 实时监控响应时间和缓存命中率

## 快速开始

### 安装依赖

```bash
pip install asyncio pandas numpy
```

### 基础使用

```python
import asyncio
from src.argus_mcp.api.enhanced_historical_api import (
    EnhancedHistoricalDataAPI,
    HistoricalDataRequest
)
from src.argus_mcp.data_models.historical_data import SupportedPeriod

async def basic_example():
    # 初始化API
    api = EnhancedHistoricalDataAPI()
    
    # 创建请求
    request = HistoricalDataRequest(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-31",
        period=SupportedPeriod.DAILY,
        include_quality_metrics=True,
        use_cache=True
    )
    
    # 获取数据
    response = await api.get_historical_data(request)
    
    if response.success:
        print(f"获取到 {len(response.data)} 条数据")
        print(f"质量评分: {response.quality_report.get('overall_score', 'N/A')}")
    else:
        print(f"获取失败: {response.metadata.get('error')}")

# 运行示例
asyncio.run(basic_example())
```

## 多周期数据获取

### 支持的周期类型

| 周期 | 枚举值 | 描述 | 适用场景 |
|------|--------|------|----------|
| 1m | `SupportedPeriod.MINUTE_1` | 1分钟 | 高频交易、日内分析 |
| 5m | `SupportedPeriod.MINUTE_5` | 5分钟 | 短期技术分析 |
| 15m | `SupportedPeriod.MINUTE_15` | 15分钟 | 日内趋势分析 |
| 30m | `SupportedPeriod.MINUTE_30` | 30分钟 | 中短期分析 |
| 1h | `SupportedPeriod.HOURLY` | 1小时 | 日内长期趋势 |
| 1d | `SupportedPeriod.DAILY` | 日线 | 中长期分析 |
| 1w | `SupportedPeriod.WEEKLY` | 周线 | 长期趋势分析 |
| 1M | `SupportedPeriod.MONTHLY` | 月线 | 超长期分析 |

### 多周期并发获取示例

```python
async def multi_period_example():
    api = EnhancedHistoricalDataAPI()
    symbol = "600519.SH"
    start_date = "2024-01-01"
    end_date = "2024-01-05"
    
    # 定义多个周期
    periods = [
        SupportedPeriod.DAILY,
        SupportedPeriod.HOURLY,
        SupportedPeriod.MINUTE_15
    ]
    
    # 创建并发任务
    tasks = []
    for period in periods:
        request = HistoricalDataRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            use_cache=True
        )
        tasks.append(api.get_historical_data(request))
    
    # 并发执行
    responses = await asyncio.gather(*tasks)
    
    # 处理结果
    for period, response in zip(periods, responses):
        if response.success:
            print(f"{period.value}: {len(response.data)} 条数据")
        else:
            print(f"{period.value}: 获取失败")
```

## 数据质量监控

### 质量指标说明

增强API提供以下质量指标：

- **完整性评分** (`completeness_rate`): 数据完整程度，范围0-1
- **准确性评分** (`accuracy_score`): 数据准确程度，范围0-1
- **一致性评分** (`consistency_score`): 数据一致性程度，范围0-1
- **及时性评分** (`timeliness_score`): 数据及时性程度，范围0-1
- **异常数据数量** (`anomaly_count`): 检测到的异常数据条数

### 质量监控示例

```python
async def quality_monitoring_example():
    api = EnhancedHistoricalDataAPI()
    
    request = HistoricalDataRequest(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-31",
        period=SupportedPeriod.DAILY,
        include_quality_metrics=True,  # 启用质量监控
        normalize_data=True
    )
    
    response = await api.get_historical_data(request)
    
    if response.success and response.quality_report:
        quality = response.quality_report
        
        print("📊 数据质量报告:")
        print(f"  完整性: {quality.get('completeness_rate', 0):.2%}")
        print(f"  准确性: {quality.get('accuracy_score', 0):.2f}")
        print(f"  一致性: {quality.get('consistency_score', 0):.2f}")
        print(f"  异常数据: {quality.get('anomaly_count', 0)}条")
        
        # 计算综合质量等级
        avg_score = (
            quality.get('completeness_rate', 0) +
            quality.get('accuracy_score', 0) +
            quality.get('consistency_score', 0)
        ) / 3
        
        if avg_score >= 0.9:
            print("  质量等级: 优秀 ⭐⭐⭐")
        elif avg_score >= 0.8:
            print("  质量等级: 良好 ⭐⭐")
        else:
            print("  质量等级: 一般 ⭐")
```

## 缓存优化策略

### 缓存TTL策略

增强API根据数据周期自动设置缓存TTL：

| 数据周期 | 缓存TTL | 说明 |
|----------|---------|------|
| 1m, 5m | 1小时 | 短周期数据变化快 |
| 15m, 30m | 2-4小时 | 中短周期数据 |
| 1h | 8小时 | 小时级数据 |
| 1d | 24小时 | 日线数据 |
| 1w, 1M | 7天 | 长周期数据变化慢 |

### 缓存性能测试

```python
async def cache_performance_test():
    api = EnhancedHistoricalDataAPI()
    
    request = HistoricalDataRequest(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-05",
        period=SupportedPeriod.DAILY,
        use_cache=True
    )
    
    # 第一次请求（冷缓存）
    start_time = time.time()
    response1 = await api.get_historical_data(request)
    first_time = (time.time() - start_time) * 1000
    
    # 第二次请求（热缓存）
    start_time = time.time()
    response2 = await api.get_historical_data(request)
    second_time = (time.time() - start_time) * 1000
    
    if response1.success and response2.success:
        improvement = (first_time - second_time) / first_time * 100
        print(f"缓存性能提升: {improvement:.1f}%")
        print(f"第一次请求: {first_time:.0f}ms (缓存命中: {response1.metadata.get('cache_hit', False)})")
        print(f"第二次请求: {second_time:.0f}ms (缓存命中: {response2.metadata.get('cache_hit', False)})")
```

## 性能优化技巧

### 1. 批量并发获取

```python
async def batch_concurrent_example():
    api = EnhancedHistoricalDataAPI()
    symbols = ["600519.SH", "000001.SZ", "600036.SH"]
    
    # 创建并发任务
    tasks = []
    for symbol in symbols:
        request = HistoricalDataRequest(
            symbol=symbol,
            start_date="2024-01-01",
            end_date="2024-01-05",
            period=SupportedPeriod.DAILY,
            use_cache=True
        )
        tasks.append(api.get_historical_data(request))
    
    # 并发执行
    start_time = time.time()
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = (time.time() - start_time) * 1000
    
    print(f"批量获取{len(symbols)}只股票耗时: {total_time:.0f}ms")
    print(f"平均每股票: {total_time/len(symbols):.0f}ms")
```

### 2. 内存优化

```python
import gc

async def memory_optimization_example():
    api = EnhancedHistoricalDataAPI()
    
    # 大数据量获取
    request = HistoricalDataRequest(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-03-31",
        period=SupportedPeriod.DAILY,
        use_cache=False
    )
    
    response = await api.get_historical_data(request)
    
    if response.success:
        print(f"获取到 {len(response.data)} 条数据")
        
        # 处理数据后及时清理
        # ... 数据处理逻辑 ...
        
        # 手动垃圾回收
        del response
        gc.collect()
        print("内存清理完成")
```

### 3. 分页获取大数据

```python
async def paginated_data_example():
    api = EnhancedHistoricalDataAPI()
    symbol = "600519.SH"
    
    # 分段获取大时间范围的数据
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 1, 1)
    
    all_data = []
    current_date = start_date
    
    while current_date < end_date:
        segment_end = min(current_date + timedelta(days=30), end_date)
        
        request = HistoricalDataRequest(
            symbol=symbol,
            start_date=current_date.strftime("%Y-%m-%d"),
            end_date=segment_end.strftime("%Y-%m-%d"),
            period=SupportedPeriod.DAILY,
            use_cache=True
        )
        
        response = await api.get_historical_data(request)
        
        if response.success:
            all_data.extend(response.data)
            print(f"获取 {current_date.strftime('%Y-%m-%d')} 到 {segment_end.strftime('%Y-%m-%d')} 数据: {len(response.data)} 条")
        
        current_date = segment_end + timedelta(days=1)
    
    print(f"总共获取 {len(all_data)} 条数据")
```

## 错误处理机制

### 错误类型

增强API定义了以下错误类型：

- `DataSourceError`: 数据源连接或访问错误
- `DataValidationError`: 数据验证错误
- `CacheError`: 缓存操作错误
- `PeriodConversionError`: 周期转换错误

### 错误处理示例

```python
async def error_handling_example():
    api = EnhancedHistoricalDataAPI()
    
    # 测试无效股票代码
    request = HistoricalDataRequest(
        symbol="INVALID.XX",
        start_date="2024-01-01",
        end_date="2024-01-05",
        period=SupportedPeriod.DAILY
    )
    
    try:
        response = await api.get_historical_data(request)
        
        if response.success:
            print("意外成功")
        else:
            error_msg = response.metadata.get('error', '未知错误')
            print(f"预期失败: {error_msg}")
            
            # 检查错误详情
            if 'error_details' in response.metadata:
                details = response.metadata['error_details']
                print(f"错误类型: {details.get('error_type')}")
                print(f"重试次数: {details.get('retry_count', 0)}")
                
    except Exception as e:
        print(f"异常处理: {str(e)}")
```

## 最佳实践

### 1. 周期选择策略

```python
# 根据分析需求选择合适的周期
analysis_scenarios = {
    "高频交易": SupportedPeriod.MINUTE_1,
    "日内短线": SupportedPeriod.MINUTE_5,
    "日内中线": SupportedPeriod.MINUTE_15,
    "日内长线": SupportedPeriod.HOURLY,
    "短期分析": SupportedPeriod.DAILY,
    "中期分析": SupportedPeriod.WEEKLY,
    "长期分析": SupportedPeriod.MONTHLY
}
```

### 2. 缓存使用建议

```python
# 缓存使用决策
def should_use_cache(query_frequency: str, data_freshness_requirement: str) -> bool:
    """
    决定是否使用缓存
    
    Args:
        query_frequency: 查询频率 ("high", "medium", "low")
        data_freshness_requirement: 数据新鲜度要求 ("real_time", "near_real_time", "historical")
    
    Returns:
        bool: 是否使用缓存
    """
    if data_freshness_requirement == "real_time":
        return False
    elif query_frequency == "high":
        return True
    else:
        return data_freshness_requirement == "historical"
```

### 3. 质量监控配置

```python
# 质量监控配置
quality_thresholds = {
    "completeness_rate": 0.95,  # 完整性阈值
    "accuracy_score": 0.90,     # 准确性阈值
    "consistency_score": 0.90,  # 一致性阈值
    "max_anomaly_rate": 0.05    # 最大异常率
}

def check_data_quality(quality_report: dict) -> bool:
    """检查数据质量是否达标"""
    for metric, threshold in quality_thresholds.items():
        if metric == "max_anomaly_rate":
            anomaly_rate = quality_report.get('anomaly_count', 0) / quality_report.get('total_records', 1)
            if anomaly_rate > threshold:
                return False
        else:
            if quality_report.get(metric, 0) < threshold:
                return False
    return True
```

### 4. 性能监控

```python
import time
from collections import defaultdict

class PerformanceMonitor:
    def __init__(self):
        self.metrics = defaultdict(list)
    
    async def monitored_request(self, api, request):
        """监控API请求性能"""
        start_time = time.time()
        
        try:
            response = await api.get_historical_data(request)
            request_time = (time.time() - start_time) * 1000
            
            # 记录性能指标
            self.metrics['response_times'].append(request_time)
            self.metrics['success_count'] += 1 if response.success else 0
            self.metrics['cache_hits'] += 1 if response.metadata.get('cache_hit') else 0
            self.metrics['total_requests'] += 1
            
            return response
            
        except Exception as e:
            self.metrics['error_count'] += 1
            raise e
    
    def get_performance_report(self):
        """获取性能报告"""
        if not self.metrics['response_times']:
            return "暂无性能数据"
        
        avg_response_time = sum(self.metrics['response_times']) / len(self.metrics['response_times'])
        success_rate = self.metrics['success_count'] / self.metrics['total_requests']
        cache_hit_rate = self.metrics['cache_hits'] / self.metrics['total_requests']
        
        return {
            'avg_response_time_ms': avg_response_time,
            'success_rate': success_rate,
            'cache_hit_rate': cache_hit_rate,
            'total_requests': self.metrics['total_requests']
        }
```

## 示例代码

### 完整的生产环境示例

```python
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionHistoricalDataService:
    """生产环境历史数据服务"""
    
    def __init__(self):
        self.api = EnhancedHistoricalDataAPI()
        self.performance_monitor = PerformanceMonitor()
        self.quality_thresholds = {
            "completeness_rate": 0.95,
            "accuracy_score": 0.90,
            "consistency_score": 0.90
        }
    
    async def get_reliable_historical_data(self, 
                                         symbol: str,
                                         start_date: str,
                                         end_date: str,
                                         period: SupportedPeriod,
                                         max_retries: int = 3) -> Dict[str, Any]:
        """
        获取可靠的历史数据
        
        包含重试机制、质量检查和性能监控
        """
        
        for attempt in range(max_retries):
            try:
                request = HistoricalDataRequest(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period,
                    include_quality_metrics=True,
                    use_cache=True
                )
                
                # 监控请求性能
                response = await self.performance_monitor.monitored_request(
                    self.api, request
                )
                
                if not response.success:
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {response.metadata.get('error')}")
                    continue
                
                # 检查数据质量
                if response.quality_report:
                    quality_ok = self.check_data_quality(response.quality_report)
                    if not quality_ok:
                        logger.warning(f"数据质量不达标 (尝试 {attempt + 1}/{max_retries})")
                        continue
                
                # 成功返回
                logger.info(f"成功获取 {symbol} 数据: {len(response.data)} 条")
                return {
                    'success': True,
                    'data': response.data,
                    'quality_report': response.quality_report,
                    'metadata': response.metadata
                }
                
            except Exception as e:
                logger.error(f"请求异常 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise e
                
                # 指数退避
                await asyncio.sleep(2 ** attempt)
        
        return {
            'success': False,
            'error': f'在 {max_retries} 次尝试后仍然失败'
        }
    
    def check_data_quality(self, quality_report: Dict[str, Any]) -> bool:
        """检查数据质量"""
        for metric, threshold in self.quality_thresholds.items():
            if quality_report.get(metric, 0) < threshold:
                logger.warning(f"质量指标 {metric} 不达标: {quality_report.get(metric, 0)} < {threshold}")
                return False
        return True
    
    async def batch_get_historical_data(self, 
                                      symbols: List[str],
                                      start_date: str,
                                      end_date: str,
                                      period: SupportedPeriod,
                                      max_concurrent: int = 5) -> Dict[str, Any]:
        """
        批量获取历史数据
        
        控制并发数量，避免过载
        """
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def get_single_symbol_data(symbol: str):
            async with semaphore:
                return await self.get_reliable_historical_data(
                    symbol, start_date, end_date, period
                )
        
        # 并发获取所有股票数据
        tasks = [get_single_symbol_data(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        successful_results = {}
        failed_results = {}
        
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                failed_results[symbol] = str(result)
            elif result.get('success'):
                successful_results[symbol] = result
            else:
                failed_results[symbol] = result.get('error', '未知错误')
        
        return {
            'successful': successful_results,
            'failed': failed_results,
            'success_rate': len(successful_results) / len(symbols),
            'performance_report': self.performance_monitor.get_performance_report()
        }

# 使用示例
async def main():
    service = ProductionHistoricalDataService()
    
    # 单个股票数据获取
    result = await service.get_reliable_historical_data(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-31",
        period=SupportedPeriod.DAILY
    )
    
    if result['success']:
        print(f"成功获取数据: {len(result['data'])} 条")
    else:
        print(f"获取失败: {result['error']}")
    
    # 批量股票数据获取
    symbols = ["600519.SH", "000001.SZ", "600036.SH"]
    batch_result = await service.batch_get_historical_data(
        symbols=symbols,
        start_date="2024-01-01",
        end_date="2024-01-05",
        period=SupportedPeriod.DAILY
    )
    
    print(f"批量获取成功率: {batch_result['success_rate']:.1%}")
    print(f"成功: {len(batch_result['successful'])} 个")
    print(f"失败: {len(batch_result['failed'])} 个")

if __name__ == "__main__":
    asyncio.run(main())
```

## 总结

增强的历史K线API提供了强大的功能和灵活的配置选项，通过合理使用这些功能，可以构建高性能、高可靠性的金融数据应用。

### 关键要点

1. **选择合适的数据周期**：根据分析需求选择最适合的时间周期
2. **启用质量监控**：在生产环境中始终启用数据质量监控
3. **合理使用缓存**：根据数据新鲜度要求和查询频率决定缓存策略
4. **实现错误处理**：包含重试机制和降级方案
5. **监控性能指标**：定期监控API性能和数据质量
6. **优化并发处理**：使用异步编程和合理的并发控制

通过遵循这些最佳实践，您可以充分发挥增强API的优势，构建稳定可靠的金融数据服务。