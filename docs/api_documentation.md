# Argus MCP API 文档

## 概述

Argus MCP 提供 RESTful API 和 WebSocket API，用于访问金融市场数据、管理缓存和连接池。所有 API 都支持 JSON 格式的请求和响应。

## 基础信息

- **Base URL**: `http://localhost:8001`
- **API Version**: `v1`
- **Content-Type**: `application/json`
- **Authentication**: 暂不需要（开发环境）

## 通用响应格式

### 成功响应
```json
{
  "success": true,
  "data": {},
  "message": "操作成功",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 错误响应
```json
{
  "success": false,
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数无效",
    "details": "symbols 参数不能为空"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 市场数据 API

### 1. 获取最新行情数据

获取指定股票的最新行情信息。

**请求**
```http
GET /api/v1/market_data/latest
```

**参数**
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| symbols | string | 是 | 股票代码，多个用逗号分隔 | `000001.SZ,000002.SZ` |
| fields | string | 否 | 返回字段，多个用逗号分隔 | `price,volume,change` |
| use_cache | boolean | 否 | 是否使用缓存 | `true` |

**响应示例**
```json
{
  "success": true,
  "data": {
    "000001.SZ": {
      "symbol": "000001.SZ",
      "name": "平安银行",
      "price": 12.34,
      "change": 0.12,
      "change_pct": 0.98,
      "volume": 1234567,
      "turnover": 15234567.89,
      "high": 12.45,
      "low": 12.20,
      "open": 12.25,
      "prev_close": 12.22,
      "timestamp": "2024-01-15T09:30:00Z"
    },
    "000002.SZ": {
      "symbol": "000002.SZ",
      "name": "万科A",
      "price": 8.76,
      "change": -0.05,
      "change_pct": -0.57,
      "volume": 987654,
      "turnover": 8654321.12,
      "high": 8.82,
      "low": 8.70,
      "open": 8.80,
      "prev_close": 8.81,
      "timestamp": "2024-01-15T09:30:00Z"
    }
  },
  "cache_hit": true,
  "response_time_ms": 15
}
```

### 2. 获取完整行情数据

获取指定股票的完整行情信息，包括买卖盘、成交明细等。

**请求**
```http
GET /api/v1/market_data/full
```

**参数**
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| symbols | string | 是 | 股票代码，多个用逗号分隔 | `000001.SZ` |
| fields | string | 否 | 返回字段 | `all` 或 `basic,orderbook,trades` |
| depth | integer | 否 | 买卖盘深度 | `5` (默认), `10`, `20` |

**响应示例**
```json
{
  "success": true,
  "data": {
    "000001.SZ": {
      "basic": {
        "symbol": "000001.SZ",
        "name": "平安银行",
        "price": 12.34,
        "change": 0.12,
        "change_pct": 0.98,
        "volume": 1234567,
        "turnover": 15234567.89,
        "timestamp": "2024-01-15T09:30:00Z"
      },
      "orderbook": {
        "bids": [
          {"price": 12.33, "volume": 1000},
          {"price": 12.32, "volume": 2000},
          {"price": 12.31, "volume": 1500},
          {"price": 12.30, "volume": 3000},
          {"price": 12.29, "volume": 2500}
        ],
        "asks": [
          {"price": 12.34, "volume": 800},
          {"price": 12.35, "volume": 1200},
          {"price": 12.36, "volume": 1800},
          {"price": 12.37, "volume": 2200},
          {"price": 12.38, "volume": 1600}
        ]
      },
      "trades": [
        {
          "price": 12.34,
          "volume": 100,
          "direction": "buy",
          "timestamp": "2024-01-15T09:30:00.123Z"
        }
      ]
    }
  }
}
```

### 3. 获取历史行情数据

获取指定时间范围内的历史行情数据。

**请求**
```http
GET /api/v1/market_data/history
```

**参数**
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| symbols | string | 是 | 股票代码 | `000001.SZ` |
| start_date | string | 是 | 开始日期 | `2024-01-01` |
| end_date | string | 是 | 结束日期 | `2024-01-31` |
| period | string | 否 | 数据周期 | `1d`, `1h`, `30m`, `15m`, `5m`, `1m` |
| adjust | string | 否 | 复权类型 | `none`, `pre`, `post` |

**响应示例**
```json
{
  "success": true,
  "data": {
    "000001.SZ": [
      {
        "date": "2024-01-01",
        "open": 12.00,
        "high": 12.50,
        "low": 11.80,
        "close": 12.30,
        "volume": 1000000,
        "turnover": 12150000.00,
        "change": 0.30,
        "change_pct": 2.50
      },
      {
        "date": "2024-01-02",
        "open": 12.30,
        "high": 12.60,
        "low": 12.10,
        "close": 12.45,
        "volume": 1200000,
        "turnover": 14940000.00,
        "change": 0.15,
        "change_pct": 1.22
      }
    ]
  },
  "total_records": 31,
  "period": "1d"
}
```

### 4. 获取股票基本信息

获取股票的基本信息，如公司名称、行业、市值等。

**请求**
```http
GET /api/v1/market_data/instrument_detail
```

**参数**
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| symbols | string | 是 | 股票代码 | `000001.SZ` |

**响应示例**
```json
{
  "success": true,
  "data": {
    "000001.SZ": {
      "symbol": "000001.SZ",
      "name": "平安银行",
      "full_name": "平安银行股份有限公司",
      "industry": "银行",
      "sector": "金融业",
      "market": "深圳主板",
      "list_date": "1991-04-03",
      "total_shares": 19405918198,
      "float_shares": 19405918198,
      "market_cap": 239517042684.32,
      "pe_ratio": 4.85,
      "pb_ratio": 0.58,
      "dividend_yield": 3.24
    }
  }
}
```

### 5. 获取交易日历

获取指定时间范围内的交易日历。

**请求**
```http
GET /api/v1/market_data/trading_dates
```

**参数**
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| start_date | string | 是 | 开始日期 | `2024-01-01` |
| end_date | string | 是 | 结束日期 | `2024-01-31` |
| market | string | 否 | 市场代码 | `SZ`, `SH`, `ALL` |

**响应示例**
```json
{
  "success": true,
  "data": {
    "trading_dates": [
      "2024-01-02",
      "2024-01-03",
      "2024-01-04",
      "2024-01-05",
      "2024-01-08"
    ],
    "total_days": 22,
    "holidays": [
      "2024-01-01",
      "2024-01-06",
      "2024-01-07"
    ]
  }
}
```

## WebSocket API

### 连接地址
```
ws://localhost:8001/ws/market_data
```

### 消息格式

#### 订阅股票
```json
{
  "action": "subscribe",
  "symbols": ["000001.SZ", "000002.SZ"],
  "fields": ["price", "volume", "change"]
}
```

#### 取消订阅
```json
{
  "action": "unsubscribe",
  "symbols": ["000001.SZ"]
}
```

#### 获取统计信息
```json
{
  "action": "get_stats"
}
```

#### 心跳检测
```json
{
  "action": "ping"
}
```

### 推送消息格式

#### 实时行情推送
```json
{
  "type": "market_data",
  "data": {
    "symbol": "000001.SZ",
    "price": 12.34,
    "change": 0.12,
    "change_pct": 0.98,
    "volume": 1234567,
    "timestamp": "2024-01-15T09:30:00.123Z"
  }
}
```

#### 统计信息响应
```json
{
  "type": "stats",
  "data": {
    "total_connections": 150,
    "total_subscriptions": 1250,
    "messages_sent": 125000,
    "uptime_seconds": 3600
  }
}
```

#### 心跳响应
```json
{
  "type": "pong",
  "timestamp": "2024-01-15T09:30:00Z"
}
```

## 缓存管理 API

### 1. 获取缓存统计

**请求**
```http
GET /api/v1/cache/stats
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "total_keys": 1250,
    "hit_rate": 0.87,
    "miss_rate": 0.13,
    "memory_usage_mb": 245.6,
    "cache_levels": {
      "L1": {
        "keys": 450,
        "hit_rate": 0.92,
        "memory_mb": 89.2
      },
      "L2": {
        "keys": 600,
        "hit_rate": 0.85,
        "memory_mb": 123.4
      },
      "L3": {
        "keys": 200,
        "hit_rate": 0.78,
        "memory_mb": 33.0
      }
    }
  }
}
```

### 2. 清理缓存

**请求**
```http
DELETE /api/v1/cache/clear
```

**参数**
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| cache_type | string | 否 | 缓存类型 | `market_data`, `history_data`, `all` |
| level | string | 否 | 缓存级别 | `L1`, `L2`, `L3` |

**响应示例**
```json
{
  "success": true,
  "message": "缓存清理完成",
  "cleared_keys": 450,
  "freed_memory_mb": 89.2
}
```

### 3. 优化缓存

**请求**
```http
POST /api/v1/cache/optimize
```

**响应示例**
```json
{
  "success": true,
  "message": "缓存优化完成",
  "optimizations": [
    "调整了 market_data 的 TTL 从 30s 到 45s",
    "清理了 150 个过期键",
    "重新分配了 L1 缓存内存"
  ],
  "performance_improvement": {
    "hit_rate_before": 0.82,
    "hit_rate_after": 0.87,
    "memory_saved_mb": 23.4
  }
}
```

### 4. 获取缓存配置

**请求**
```http
GET /api/v1/cache/config
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "cache_rules": {
      "LATEST_DATA": {
        "ttl": 30,
        "max_size": 1000,
        "level": "L1",
        "priority": "high"
      },
      "HISTORY_DATA": {
        "ttl": 300,
        "max_size": 5000,
        "level": "L2",
        "priority": "medium"
      },
      "BASIC_INFO": {
        "ttl": 3600,
        "max_size": 2000,
        "level": "L3",
        "priority": "low"
      }
    }
  }
}
```

## 连接池管理 API

### 1. 创建连接池

**请求**
```http
POST /api/v1/connection_pool/pools
```

**请求体**
```json
{
  "name": "market_data_pool",
  "config": {
    "min_size": 5,
    "max_size": 50,
    "initial_size": 10,
    "timeout": 30.0,
    "max_idle_time": 300.0,
    "health_check_interval": 60.0,
    "auto_scale": true,
    "scale_factor": 1.5,
    "scale_threshold": 0.8,
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

**响应示例**
```json
{
  "success": true,
  "message": "Connection pool 'market_data_pool' created successfully",
  "pool_name": "market_data_pool",
  "config": {
    "min_size": 5,
    "max_size": 50,
    "auto_scale": true
  },
  "server_nodes_count": 1
}
```

### 2. 获取连接池列表

**请求**
```http
GET /api/v1/connection_pool/pools
```

**响应示例**
```json
{
  "success": true,
  "pools": [
    {
      "name": "market_data_pool",
      "active_connections": 8,
      "idle_connections": 12,
      "total_connections": 20,
      "pool_utilization": 0.4,
      "health_status": "healthy",
      "server_nodes_count": 2,
      "last_update": "2024-01-15T09:30:00Z"
    }
  ],
  "total_pools": 1
}
```

### 3. 获取连接池详情

**请求**
```http
GET /api/v1/connection_pool/pools/{pool_name}
```

**响应示例**
```json
{
  "success": true,
  "pool_name": "market_data_pool",
  "metrics": {
    "active_connections": 8,
    "idle_connections": 12,
    "total_connections": 20,
    "pool_utilization": 0.4,
    "avg_response_time": 25.6,
    "error_rate": 0.02,
    "throughput": 1250.5,
    "server_nodes": [
      {
        "host": "localhost",
        "port": 8001,
        "health_status": true,
        "current_connections": 10,
        "response_time": 23.4
      }
    ],
    "last_update": "2024-01-15T09:30:00Z"
  },
  "config": {
    "min_size": 5,
    "max_size": 50,
    "timeout": 30.0,
    "auto_scale": true,
    "load_balance_strategy": "round_robin"
  }
}
```

### 4. 手动扩缩容

**请求**
```http
POST /api/v1/connection_pool/pools/{pool_name}/scale
```

**请求体**
```json
{
  "target_size": 30
}
```

**响应示例**
```json
{
  "success": true,
  "message": "Pool 'market_data_pool' scaled from 20 to 30 connections",
  "previous_size": 20,
  "new_size": 30,
  "target_size": 30
}
```

### 5. 健康检查

**请求**
```http
POST /api/v1/connection_pool/pools/{pool_name}/health_check
```

**响应示例**
```json
{
  "success": true,
  "message": "Health check completed for pool 'market_data_pool'",
  "total_nodes": 2,
  "healthy_nodes": 2,
  "unhealthy_nodes": 0,
  "node_details": [
    {
      "host": "localhost",
      "port": 8001,
      "health_status": true,
      "current_connections": 10,
      "last_health_check": "2024-01-15T09:30:00Z"
    }
  ]
}
```

## 系统监控 API

### 1. 健康检查

**请求**
```http
GET /health
```

**响应示例**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T09:30:00Z",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "services": {
    "database": "healthy",
    "cache": "healthy",
    "xtquant": "healthy"
  }
}
```

### 2. 系统指标

**请求**
```http
GET /api/v1/metrics/system
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "cpu_percent": 25.6,
    "memory_percent": 68.2,
    "disk_usage_percent": 45.8,
    "network_io": {
      "bytes_sent": 1234567890,
      "bytes_recv": 987654321
    },
    "process_info": {
      "pid": 12345,
      "threads": 8,
      "open_files": 156
    }
  }
}
```

### 3. 服务指标

**请求**
```http
GET /api/v1/metrics/service
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "requests_total": 125000,
    "requests_per_second": 45.6,
    "avg_response_time_ms": 28.5,
    "error_rate": 0.015,
    "active_connections": 150,
    "cache_hit_rate": 0.87,
    "database_connections": 25
  }
}
```

## 错误代码

| 错误代码 | HTTP状态码 | 说明 |
|----------|------------|------|
| INVALID_PARAMETER | 400 | 参数无效 |
| MISSING_PARAMETER | 400 | 缺少必需参数 |
| UNAUTHORIZED | 401 | 未授权访问 |
| FORBIDDEN | 403 | 禁止访问 |
| NOT_FOUND | 404 | 资源不存在 |
| METHOD_NOT_ALLOWED | 405 | 方法不允许 |
| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |
| INTERNAL_ERROR | 500 | 内部服务器错误 |
| SERVICE_UNAVAILABLE | 503 | 服务不可用 |
| TIMEOUT | 504 | 请求超时 |
| CACHE_ERROR | 500 | 缓存错误 |
| DATABASE_ERROR | 500 | 数据库错误 |
| XTQUANT_ERROR | 500 | XtQuant 连接错误 |

## 限流规则

| API 类型 | 限制 | 时间窗口 |
|----------|------|----------|
| 实时数据 | 100 请求/分钟 | 1 分钟 |
| 历史数据 | 50 请求/分钟 | 1 分钟 |
| 管理接口 | 20 请求/分钟 | 1 分钟 |
| WebSocket | 1000 消息/分钟 | 1 分钟 |

## SDK 示例

### Python SDK

```python
import asyncio
from argus_mcp.client import ArgusMCPClient

async def main():
    # 创建客户端
    client = ArgusMCPClient("http://localhost:8001")
    
    try:
        # 获取最新行情
        data = await client.get_latest_market_data(["000001.SZ", "000002.SZ"])
        print(f"最新行情: {data}")
        
        # 获取历史数据
        history = await client.get_history_market_data(
            symbols=["000001.SZ"],
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        print(f"历史数据: {len(history['000001.SZ'])} 条记录")
        
        # 缓存统计
        cache_stats = await client.get_cache_stats()
        print(f"缓存命中率: {cache_stats['hit_rate']:.2%}")
        
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### JavaScript SDK

```javascript
class ArgusMCPClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }
    
    async getLatestMarketData(symbols) {
        const response = await fetch(
            `${this.baseUrl}/api/v1/market_data/latest?symbols=${symbols.join(',')}`
        );
        return await response.json();
    }
    
    async getHistoryMarketData(symbols, startDate, endDate, period = '1d') {
        const params = new URLSearchParams({
            symbols: symbols.join(','),
            start_date: startDate,
            end_date: endDate,
            period: period
        });
        
        const response = await fetch(
            `${this.baseUrl}/api/v1/market_data/history?${params}`
        );
        return await response.json();
    }
    
    connectWebSocket() {
        const ws = new WebSocket(`ws://localhost:8001/ws/market_data`);
        
        ws.onopen = () => {
            console.log('WebSocket 连接已建立');
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('收到数据:', data);
        };
        
        ws.onclose = () => {
            console.log('WebSocket 连接已关闭');
        };
        
        return ws;
    }
}

// 使用示例
const client = new ArgusMCPClient('http://localhost:8001');

// 获取数据
client.getLatestMarketData(['000001.SZ', '000002.SZ'])
    .then(data => console.log(data));

// WebSocket 连接
const ws = client.connectWebSocket();
ws.onopen = () => {
    ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: ['000001.SZ', '000002.SZ']
    }));
};
```

## 版本历史

### v1.0.0 (2024-01-15)
- 初始版本发布
- 支持基本市场数据 API
- 实现缓存管理功能
- 添加连接池管理
- 提供 WebSocket 实时推送

### 未来版本计划

#### v1.1.0
- 添加用户认证和权限管理
- 支持更多数据源
- 增强监控和告警功能
- 优化性能和稳定性

#### v1.2.0
- 支持期货和期权数据
- 添加技术指标计算
- 实现数据订阅管理
- 提供更多 SDK 语言支持

## 联系方式

- **技术支持**: support@argus-mcp.com
- **文档反馈**: docs@argus-mcp.com
- **GitHub**: https://github.com/argus-mcp/argus-mcp-server

---

*本文档最后更新时间: 2024-01-15*