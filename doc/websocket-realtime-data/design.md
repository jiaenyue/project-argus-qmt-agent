# Design Document

## Overview

WebSocket Real-time Data功能将为现有的金融数据服务系统添加实时数据推送能力。该系统采用事件驱动架构，集成FastAPI WebSocket支持，提供高性能、可扩展的实时行情推送服务。系统将与现有的REST API服务共享数据源、缓存和认证机制，确保数据一致性和系统集成度。

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Applications                      │
├─────────────────────────────────────────────────────────────┤
│              WebSocket Connection Layer                     │
├─────────────────────────────────────────────────────────────┤
│  Connection Manager  │  Subscription Manager │  Auth Guard │
├─────────────────────────────────────────────────────────────┤
│                  Message Processing Layer                   │
├─────────────────────────────────────────────────────────────┤
│  Message Router  │  Data Formatter  │  Compression Engine  │
├─────────────────────────────────────────────────────────────┤
│                    Event Streaming Layer                    │
├─────────────────────────────────────────────────────────────┤
│  Event Publisher │  Event Subscriber │  Event Buffer       │
├─────────────────────────────────────────────────────────────┤
│                  Data Integration Layer                     │
├─────────────────────────────────────────────────────────────┤
│  Shared Cache    │  Data Normalizer  │  Quality Monitor    │
├─────────────────────────────────────────────────────────────┤
│                    Data Source Layer                        │
├─────────────────────────────────────────────────────────────┤
│    xtquant API   │   Market Data     │   Backup Sources    │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

1. **WebSocket Connection Manager**: WebSocket连接管理器
2. **Subscription Manager**: 订阅管理器
3. **Real-time Data Publisher**: 实时数据发布器
4. **Message Router**: 消息路由器
5. **Event Buffer**: 事件缓冲器
6. **Performance Monitor**: 性能监控器

## Components and Interfaces

### 1. WebSocket Connection Manager

**职责**: 管理WebSocket连接的生命周期和状态

**接口设计**:
```python
class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocketConnection] = {}
        self.connection_stats = ConnectionStats()
    
    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        auth_token: Optional[str] = None
    ) -> ConnectionResult
    
    async def disconnect(self, client_id: str) -> None
    
    async def send_message(
        self,
        client_id: str,
        message: WebSocketMessage
    ) -> bool
    
    async def broadcast_message(
        self,
        message: WebSocketMessage,
        target_clients: Optional[List[str]] = None
    ) -> BroadcastResult
    
    async def get_connection_stats(self) -> ConnectionStats
    
    async def cleanup_inactive_connections(self) -> int
```

**连接状态管理**:
```python
@dataclass
class WebSocketConnection:
    client_id: str
    websocket: WebSocket
    connected_at: datetime
    last_ping: datetime
    subscriptions: Set[str]
    auth_info: Optional[AuthInfo]
    message_count: int
    bytes_sent: int
    bytes_received: int

class ConnectionStats:
    total_connections: int
    active_connections: int
    messages_sent: int
    messages_received: int
    average_latency_ms: float
    connection_errors: int
```

### 2. Subscription Manager

**职责**: 管理客户端的数据订阅和推送配置

**订阅模型**:
```python
@dataclass
class Subscription:
    subscription_id: str
    client_id: str
    symbol: str
    data_type: DataType  # QUOTE, KLINE, TRADE, DEPTH
    frequency: Optional[str]  # 对于K线数据
    filters: Optional[Dict[str, Any]]
    created_at: datetime
    last_update: datetime

class SubscriptionManager:
    def __init__(self):
        self.subscriptions: Dict[str, Subscription] = {}
        self.client_subscriptions: Dict[str, Set[str]] = {}
        self.symbol_subscribers: Dict[str, Set[str]] = {}
    
    async def subscribe(
        self,
        client_id: str,
        subscription_request: SubscriptionRequest
    ) -> SubscriptionResult
    
    async def unsubscribe(
        self,
        client_id: str,
        subscription_id: str
    ) -> bool
    
    async def get_subscribers(
        self,
        symbol: str,
        data_type: DataType
    ) -> List[str]
    
    async def get_client_subscriptions(
        self,
        client_id: str
    ) -> List[Subscription]
    
    async def cleanup_client_subscriptions(
        self,
        client_id: str
    ) -> int
```

### 3. Real-time Data Publisher

**职责**: 从数据源获取实时数据并发布给订阅者

**数据流处理**:
```python
class RealTimeDataPublisher:
    def __init__(
        self,
        connection_manager: WebSocketConnectionManager,
        subscription_manager: SubscriptionManager
    ):
        self.connection_manager = connection_manager
        self.subscription_manager = subscription_manager
        self.data_buffer = EventBuffer()
        self.is_running = False
    
    async def start_publishing(self) -> None
    
    async def stop_publishing(self) -> None
    
    async def publish_market_data(
        self,
        market_data: MarketData
    ) -> PublishResult
    
    async def handle_data_update(
        self,
        symbol: str,
        data_type: DataType,
        data: Any
    ) -> None
    
    async def get_publishing_stats(self) -> PublishingStats

class EventBuffer:
    """事件缓冲器，用于批量处理和优化推送性能"""
    def __init__(self, buffer_size: int = 1000, flush_interval: float = 0.1):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.events: List[Event] = []
        self.last_flush = time.time()
    
    async def add_event(self, event: Event) -> None
    
    async def flush_events(self) -> List[Event]
    
    async def should_flush(self) -> bool
```

### 4. Message Router

**职责**: 路由和格式化WebSocket消息

**消息协议**:
```python
class MessageType(Enum):
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    MARKET_DATA = "market_data"
    KLINE_DATA = "kline_data"
    TRADE_DATA = "trade_data"
    DEPTH_DATA = "depth_data"
    STATUS = "status"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

@dataclass
class WebSocketMessage:
    type: MessageType
    timestamp: datetime
    data: Any
    metadata: Optional[Dict[str, Any]] = None
    compression: bool = False

class MessageRouter:
    async def route_incoming_message(
        self,
        client_id: str,
        raw_message: str
    ) -> MessageHandleResult
    
    async def format_outgoing_message(
        self,
        message: WebSocketMessage
    ) -> str
    
    async def compress_message(
        self,
        message: str
    ) -> bytes
    
    async def validate_message(
        self,
        message: Dict[str, Any]
    ) -> ValidationResult
```

### 5. Data Integration Layer

**职责**: 与现有系统集成，共享数据和缓存

**集成接口**:
```python
class DataIntegrationService:
    def __init__(
        self,
        cache_manager: CacheManager,
        data_service: DataService
    ):
        self.cache_manager = cache_manager
        self.data_service = data_service
    
    async def get_real_time_quote(
        self,
        symbol: str
    ) -> Optional[QuoteData]
    
    async def get_latest_kline(
        self,
        symbol: str,
        period: str
    ) -> Optional[KLineData]
    
    async def subscribe_to_data_updates(
        self,
        symbols: List[str],
        callback: Callable
    ) -> None
    
    async def get_market_status(self) -> MarketStatus
```

## Data Models

### WebSocket消息模型

```python
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum

class DataType(str, Enum):
    QUOTE = "quote"
    KLINE = "kline"
    TRADE = "trade"
    DEPTH = "depth"

class SubscriptionRequest(BaseModel):
    symbol: str
    data_type: DataType
    frequency: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

class SubscriptionResponse(BaseModel):
    subscription_id: str
    status: str
    message: str
    symbol: str
    data_type: DataType

class QuoteData(BaseModel):
    symbol: str
    timestamp: datetime
    last_price: Decimal
    change: Decimal
    change_percent: Decimal
    volume: int
    amount: Decimal
    bid_price: Decimal
    ask_price: Decimal
    bid_volume: int
    ask_volume: int

class KLineData(BaseModel):
    symbol: str
    timestamp: datetime
    period: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal

class TradeData(BaseModel):
    symbol: str
    timestamp: datetime
    price: Decimal
    volume: int
    direction: str  # "buy" or "sell"
    trade_id: str

class DepthData(BaseModel):
    symbol: str
    timestamp: datetime
    bids: List[List[Decimal]]  # [[price, volume], ...]
    asks: List[List[Decimal]]  # [[price, volume], ...]

class StatusMessage(BaseModel):
    type: str
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
```

### 性能监控模型

```python
@dataclass
class PerformanceMetrics:
    connections_count: int
    messages_per_second: int
    average_latency_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    network_io_mbps: float
    error_rate_percent: float

@dataclass
class PublishingStats:
    total_messages_sent: int
    messages_per_symbol: Dict[str, int]
    average_publish_latency_ms: float
    failed_publishes: int
    buffer_utilization_percent: float
```

## Error Handling

### 错误分类和处理

```python
class WebSocketError(Exception):
    """WebSocket相关错误基类"""
    pass

class ConnectionError(WebSocketError):
    """连接相关错误"""
    pass

class SubscriptionError(WebSocketError):
    """订阅相关错误"""
    pass

class DataPublishError(WebSocketError):
    """数据发布错误"""
    pass

class AuthenticationError(WebSocketError):
    """认证错误"""
    pass

# 错误处理策略
ERROR_RECOVERY_STRATEGIES = {
    ConnectionError: {
        "action": "attempt_reconnection",
        "max_retries": 3,
        "backoff_seconds": [1, 2, 4]
    },
    SubscriptionError: {
        "action": "notify_client_and_cleanup",
        "log_level": "WARNING"
    },
    DataPublishError: {
        "action": "buffer_and_retry",
        "max_buffer_size": 10000
    },
    AuthenticationError: {
        "action": "disconnect_client",
        "log_level": "ERROR"
    }
}
```

### 监控和告警

```python
class WebSocketMonitor:
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.alert_thresholds = {
            "max_connections": 1000,
            "max_latency_ms": 100,
            "max_error_rate_percent": 5.0,
            "max_memory_usage_mb": 512
        }
    
    async def collect_metrics(self) -> PerformanceMetrics
    
    async def check_alerts(self) -> List[Alert]
    
    async def log_performance_stats(self) -> None

@dataclass
class Alert:
    type: str
    severity: str
    message: str
    timestamp: datetime
    metrics: Dict[str, Any]
```

## Testing Strategy

### 测试层次

1. **单元测试**
   - WebSocket连接管理测试
   - 订阅管理逻辑测试
   - 消息路由和格式化测试
   - 数据发布机制测试

2. **集成测试**
   - WebSocket端点集成测试
   - 与REST API的数据一致性测试
   - 缓存系统集成测试
   - 认证和权限集成测试

3. **性能测试**
   - 并发连接压力测试
   - 消息吞吐量测试
   - 内存和CPU使用测试
   - 网络延迟测试

4. **可靠性测试**
   - 连接断开和重连测试
   - 网络异常恢复测试
   - 数据源故障转移测试
   - 长时间运行稳定性测试

### 测试工具和框架

```python
class WebSocketTestClient:
    """WebSocket测试客户端"""
    async def connect(self, url: str, auth_token: str = None) -> bool
    
    async def subscribe(self, symbol: str, data_type: str) -> bool
    
    async def wait_for_message(self, timeout: float = 5.0) -> Optional[Dict]
    
    async def send_message(self, message: Dict) -> bool
    
    async def disconnect(self) -> None

class LoadTestRunner:
    """负载测试运行器"""
    async def run_concurrent_connections_test(
        self,
        connection_count: int,
        duration_seconds: int
    ) -> TestResult
    
    async def run_message_throughput_test(
        self,
        messages_per_second: int,
        duration_seconds: int
    ) -> TestResult
```

### 自动化测试流程

1. **持续集成测试**: 每次代码提交触发WebSocket功能测试
2. **性能回归测试**: 定期执行性能基准测试
3. **实时监控测试**: 监控生产环境WebSocket服务状态
4. **故障模拟测试**: 定期模拟各种故障场景测试系统恢复能力