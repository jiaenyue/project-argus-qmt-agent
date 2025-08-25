# Argus MCP 服务用户指南

## 概述

Argus MCP (Model Context Protocol) 服务是一个高性能的金融数据服务平台，提供实时市场数据、历史数据查询、智能缓存和动态连接池管理等功能。

## 目录

1. [快速开始](#快速开始)
2. [核心功能](#核心功能)
3. [API 接口](#api-接口)
4. [配置管理](#配置管理)
5. [性能优化](#性能优化)
6. [故障排除](#故障排除)
7. [最佳实践](#最佳实践)

## 快速开始

### 环境要求

- Python 3.8+
- Redis (可选，用于分布式缓存)
- XtQuant 环境

### 安装和启动

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **启动服务**
```bash
# 启动主服务
python src/argus_mcp/simple_main.py

# 或启动数据代理服务
python data_agent_service/main.py
```

3. **验证服务**
```bash
curl http://localhost:8001/health
```

### 基本使用

```python
from argus_mcp.data_service_client import DataServiceClient

# 创建客户端
client = DataServiceClient("http://localhost:8001")

# 获取最新市场数据
data = await client.get_latest_market_data(["000001.SZ", "000002.SZ"])
print(data)
```

## 核心功能

### 1. 市场数据服务

#### 实时数据推送
- 支持 WebSocket 实时数据流
- 自动订阅管理
- 数据缓冲和批量处理

```python
# WebSocket 订阅示例
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"收到数据: {data}")

ws = websocket.WebSocketApp(
    "ws://localhost:8001/ws/market_data",
    on_message=on_message
)

# 订阅股票
ws.send(json.dumps({
    "action": "subscribe",
    "symbols": ["000001.SZ", "000002.SZ"]
}))
```

#### 历史数据查询
- 支持多种时间周期
- 灵活的查询条件
- 高效的数据压缩

```python
# 获取历史数据
history_data = await client.get_history_market_data(
    symbols=["000001.SZ"],
    start_date="2024-01-01",
    end_date="2024-01-31",
    period="1d"
)
```

### 2. 智能缓存系统

#### 三级缓存架构
- **L1 热数据缓存**: 最新交易数据，TTL 30秒
- **L2 温数据缓存**: 历史数据，TTL 5分钟
- **L3 冷数据缓存**: 基础信息，TTL 1小时

#### 缓存管理
```python
from argus_mcp.cache_optimizer import CacheOptimizer

# 获取缓存统计
optimizer = CacheOptimizer()
stats = await optimizer.get_cache_stats()
print(f"缓存命中率: {stats['hit_rate']:.2%}")

# 手动清理缓存
await optimizer.clear_cache("market_data")
```

### 3. 动态连接池

#### 自适应扩缩容
- 基于负载自动调整连接数
- 支持多种负载均衡策略
- 实时健康检查

```python
from argus_mcp.dynamic_connection_pool import connection_pool_manager

# 创建连接池
await connection_pool_manager.create_pool(
    name="market_data_pool",
    config=PoolConfiguration(
        min_size=5,
        max_size=50,
        auto_scale=True
    )
)

# 获取连接池指标
metrics = pool.get_metrics()
print(f"连接池利用率: {metrics['pool_utilization']:.2%}")
```

## API 接口

### 市场数据 API

#### 获取最新行情
```http
GET /api/v1/market_data/latest?symbols=000001.SZ,000002.SZ
```

响应示例:
```json
{
  "success": true,
  "data": {
    "000001.SZ": {
      "symbol": "000001.SZ",
      "price": 12.34,
      "change": 0.12,
      "change_pct": 0.98,
      "volume": 1234567,
      "timestamp": "2024-01-15T09:30:00Z"
    }
  }
}
```

#### 获取完整行情
```http
GET /api/v1/market_data/full?symbols=000001.SZ&fields=price,volume,bid,ask
```

#### 获取历史数据
```http
GET /api/v1/market_data/history?symbols=000001.SZ&start_date=2024-01-01&end_date=2024-01-31&period=1d
```

### 缓存管理 API

#### 获取缓存统计
```http
GET /api/v1/cache/stats
```

#### 清理缓存
```http
DELETE /api/v1/cache/clear?cache_type=market_data
```

#### 优化缓存
```http
POST /api/v1/cache/optimize
```

### 连接池管理 API

#### 创建连接池
```http
POST /api/v1/connection_pool/pools
Content-Type: application/json

{
  "name": "market_data_pool",
  "config": {
    "min_size": 5,
    "max_size": 50,
    "auto_scale": true,
    "load_balance_strategy": "round_robin"
  },
  "server_nodes": [
    {
      "host": "localhost",
      "port": 8001,
      "weight": 1.0,
      "max_connections": 100
    }
  ]
}
```

#### 获取连接池列表
```http
GET /api/v1/connection_pool/pools
```

#### 获取连接池详情
```http
GET /api/v1/connection_pool/pools/{pool_name}
```

#### 手动扩缩容
```http
POST /api/v1/connection_pool/pools/{pool_name}/scale
Content-Type: application/json

{
  "target_size": 30
}
```

## 配置管理

### 环境变量配置

```bash
# 服务配置
ARGUS_HOST=0.0.0.0
ARGUS_PORT=8001
ARGUS_DEBUG=false

# 缓存配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
CACHE_TTL_DEFAULT=300

# 连接池配置
POOL_MIN_SIZE=5
POOL_MAX_SIZE=50
POOL_TIMEOUT=30
POOL_AUTO_SCALE=true

# XtQuant 配置
XTQUANT_HOST=localhost
XTQUANT_PORT=58610
XTQUANT_USER_ID=your_user_id
```

### 配置文件

创建 `config/settings.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8001
  debug: false
  workers: 4

cache:
  redis:
    host: "localhost"
    port: 6379
    db: 0
  ttl:
    hot_data: 30      # 热数据 TTL (秒)
    warm_data: 300    # 温数据 TTL (秒)
    cold_data: 3600   # 冷数据 TTL (秒)

connection_pool:
  default:
    min_size: 5
    max_size: 50
    timeout: 30
    auto_scale: true
    scale_threshold: 0.8
    health_check_interval: 60

market_data:
  websocket:
    max_connections: 1000
    heartbeat_interval: 30
  batch_size: 100
  buffer_size: 10000
```

## 性能优化

### 缓存优化

1. **合理设置 TTL**
```python
# 根据数据更新频率设置 TTL
cache_config = {
    "latest_data": 30,      # 最新数据 30 秒
    "minute_data": 300,     # 分钟数据 5 分钟
    "daily_data": 3600,     # 日线数据 1 小时
    "basic_info": 86400     # 基础信息 24 小时
}
```

2. **预加载热点数据**
```python
# 预加载常用股票数据
hot_symbols = ["000001.SZ", "000002.SZ", "399001.SZ"]
await cache_optimizer.preload_data(hot_symbols)
```

3. **批量操作**
```python
# 批量获取数据，减少网络开销
data = await client.get_latest_market_data_batch(symbols, batch_size=100)
```

### 连接池优化

1. **动态调整连接数**
```python
# 根据负载自动调整
pool_config = PoolConfiguration(
    min_size=5,
    max_size=100,
    auto_scale=True,
    scale_threshold=0.8,    # 80% 利用率时扩容
    scale_factor=1.5        # 扩容 50%
)
```

2. **负载均衡策略**
```python
# 选择合适的负载均衡策略
strategies = [
    "round_robin",      # 轮询 (默认)
    "least_connections", # 最少连接
    "weighted_round_robin", # 加权轮询
    "random"            # 随机
]
```

### WebSocket 优化

1. **连接复用**
```javascript
// 复用 WebSocket 连接
const ws = new WebSocket('ws://localhost:8001/ws/market_data');
ws.onopen = () => {
    // 订阅多个股票
    ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: ['000001.SZ', '000002.SZ', '000858.SZ']
    }));
};
```

2. **数据压缩**
```python
# 启用数据压缩
websocket_config = {
    "compression": "gzip",
    "compression_level": 6,
    "max_message_size": 1024 * 1024  # 1MB
}
```

## 故障排除

### 常见问题

#### 1. 连接超时
**问题**: 客户端连接超时
**解决方案**:
```python
# 增加超时时间
client = DataServiceClient(
    base_url="http://localhost:8001",
    timeout=60  # 60 秒超时
)

# 检查网络连接
import requests
response = requests.get("http://localhost:8001/health")
print(response.status_code)
```

#### 2. 缓存命中率低
**问题**: 缓存命中率低于预期
**解决方案**:
```python
# 检查缓存统计
stats = await cache_optimizer.get_cache_stats()
print(f"命中率: {stats['hit_rate']:.2%}")
print(f"缓存大小: {stats['cache_size']}")

# 调整 TTL 设置
await cache_optimizer.update_ttl("market_data", 600)  # 增加到 10 分钟
```

#### 3. 内存使用过高
**问题**: 服务内存使用过高
**解决方案**:
```python
# 清理过期缓存
await cache_optimizer.cleanup_expired()

# 减少缓存大小
cache_config.max_size = 1000  # 限制缓存条目数

# 启用内存监控
import psutil
memory_usage = psutil.virtual_memory().percent
if memory_usage > 80:
    await cache_optimizer.emergency_cleanup()
```

#### 4. WebSocket 连接断开
**问题**: WebSocket 连接频繁断开
**解决方案**:
```javascript
// 实现自动重连
function connectWebSocket() {
    const ws = new WebSocket('ws://localhost:8001/ws/market_data');
    
    ws.onclose = () => {
        console.log('连接断开，5秒后重连...');
        setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket 错误:', error);
    };
    
    return ws;
}
```

### 日志分析

#### 启用详细日志
```python
import logging

# 设置日志级别
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 查看特定模块日志
logger = logging.getLogger('argus_mcp.cache_optimizer')
logger.setLevel(logging.DEBUG)
```

#### 日志文件位置
```
logs/
├── argus_mcp.log          # 主服务日志
├── cache_optimizer.log    # 缓存优化日志
├── connection_pool.log    # 连接池日志
└── market_data.log        # 市场数据日志
```

### 性能监控

#### 监控指标
```python
# 获取系统指标
metrics = await system_monitor.get_metrics()
print(f"CPU 使用率: {metrics['cpu_percent']:.1f}%")
print(f"内存使用率: {metrics['memory_percent']:.1f}%")
print(f"网络 I/O: {metrics['network_io']}")

# 获取服务指标
service_metrics = await service_monitor.get_metrics()
print(f"请求 QPS: {service_metrics['qps']}")
print(f"平均响应时间: {service_metrics['avg_response_time']:.2f}ms")
print(f"错误率: {service_metrics['error_rate']:.2%}")
```

## 最佳实践

### 1. 数据访问模式

```python
# 推荐：批量获取数据
symbols = ["000001.SZ", "000002.SZ", "000858.SZ"]
data = await client.get_latest_market_data_batch(symbols)

# 不推荐：逐个获取数据
for symbol in symbols:
    data = await client.get_latest_market_data([symbol])  # 效率低
```

### 2. 缓存策略

```python
# 根据数据特性设置缓存
cache_rules = {
    # 实时数据：短 TTL，高优先级
    "realtime": {"ttl": 30, "priority": "high"},
    
    # 历史数据：长 TTL，中优先级
    "historical": {"ttl": 3600, "priority": "medium"},
    
    # 基础信息：很长 TTL，低优先级
    "basic_info": {"ttl": 86400, "priority": "low"}
}
```

### 3. 错误处理

```python
import asyncio
from argus_mcp.exceptions import DataServiceError, CacheError

async def robust_data_fetch(symbols):
    """健壮的数据获取"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            return await client.get_latest_market_data(symbols)
        except DataServiceError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(retry_delay * (2 ** attempt))  # 指数退避
        except CacheError:
            # 缓存错误时直接从源获取
            return await client.get_latest_market_data(symbols, use_cache=False)
```

### 4. 资源管理

```python
# 使用上下文管理器
async with DataServiceClient("http://localhost:8001") as client:
    data = await client.get_latest_market_data(["000001.SZ"])
    # 自动清理资源

# 定期清理
async def periodic_cleanup():
    while True:
        await cache_optimizer.cleanup_expired()
        await connection_pool_manager.health_check_all()
        await asyncio.sleep(300)  # 每 5 分钟清理一次
```

### 5. 监控和告警

```python
# 设置监控阈值
thresholds = {
    "cache_hit_rate": 0.85,      # 缓存命中率 > 85%
    "response_time": 100,        # 响应时间 < 100ms
    "error_rate": 0.01,          # 错误率 < 1%
    "memory_usage": 0.80         # 内存使用 < 80%
}

# 实现告警
async def check_and_alert():
    metrics = await get_system_metrics()
    for metric, threshold in thresholds.items():
        if metrics[metric] > threshold:
            await send_alert(f"{metric} 超过阈值: {metrics[metric]}")
```

## 总结

Argus MCP 服务提供了完整的金融数据解决方案，通过合理配置和使用，可以实现高性能、高可用的数据服务。关键要点：

1. **合理配置缓存策略**，提高数据访问效率
2. **使用动态连接池**，优化资源利用
3. **实施监控和告警**，确保服务稳定
4. **遵循最佳实践**，避免常见陷阱
5. **定期性能调优**，持续改进系统

如需更多帮助，请参考 [API 文档](api_documentation.md) 或联系技术支持。