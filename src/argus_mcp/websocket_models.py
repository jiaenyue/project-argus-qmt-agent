"""
WebSocket 实时数据系统 - 核心数据模型
根据 tasks.md 任务1要求实现的核心数据结构和模型
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class MessageType(str, Enum):
    """WebSocket消息类型枚举"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIPTION_RESPONSE = "subscription_response"
    UNSUBSCRIBE_RESPONSE = "unsubscribe_response"
    SUBSCRIPTION_LIST = "subscription_list"
    MARKET_DATA = "market_data"
    KLINE_DATA = "kline_data"
    TRADE_DATA = "trade_data"
    DEPTH_DATA = "depth_data"
    STATUS = "status"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    HEARTBEAT = "heartbeat"
    WELCOME = "welcome"
    GET_SUBSCRIPTIONS = "get_subscriptions"
    GET_STATS = "get_stats"
    STATS = "stats"


class DataType(str, Enum):
    """数据类型枚举"""
    QUOTE = "quote"
    KLINE = "kline"
    TRADE = "trade"
    DEPTH = "depth"


class SubscriptionStatus(str, Enum):
    """订阅状态枚举"""
    ACTIVE = "active"
    PENDING = "pending"
    CANCELLED = "cancelled"
    ERROR = "error"


class ConnectionStatus(str, Enum):
    """连接状态枚举"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class WebSocketMessage(BaseModel):
    """WebSocket消息基础模型"""
    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Any = None
    metadata: Optional[Dict[str, Any]] = None
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    compression: bool = False


class SubscriptionRequest(BaseModel):
    """订阅请求模型"""
    symbol: str = Field(..., description="股票代码")
    data_type: DataType = Field(..., description="数据类型")
    frequency: Optional[str] = Field(None, description="K线周期，如1m, 5m, 1h等")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    client_id: Optional[str] = Field(None, description="客户端ID")


class SubscriptionResponse(BaseModel):
    """订阅响应模型"""
    subscription_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: SubscriptionStatus
    message: str
    symbol: str
    data_type: DataType
    client_id: str
    created_at: datetime = Field(default_factory=datetime.now)


class QuoteData(BaseModel):
    """实时行情数据模型"""
    symbol: str
    timestamp: datetime
    last_price: Decimal = Field(..., decimal_places=4)
    change: Decimal = Field(..., decimal_places=4)
    change_percent: Decimal = Field(..., decimal_places=4)
    volume: int
    amount: Decimal = Field(..., decimal_places=2)
    bid_price: Decimal = Field(..., decimal_places=4)
    ask_price: Decimal = Field(..., decimal_places=4)
    bid_volume: int
    ask_volume: int
    open: Decimal = Field(..., decimal_places=4)
    high: Decimal = Field(..., decimal_places=4)
    low: Decimal = Field(..., decimal_places=4)
    close: Decimal = Field(..., decimal_places=4)
    prev_close: Decimal = Field(..., decimal_places=4)


class KLineData(BaseModel):
    """K线数据模型"""
    symbol: str
    timestamp: datetime
    period: str = Field(..., description="K线周期")
    open: Decimal = Field(..., decimal_places=4)
    high: Decimal = Field(..., decimal_places=4)
    low: Decimal = Field(..., decimal_places=4)
    close: Decimal = Field(..., decimal_places=4)
    volume: int
    amount: Decimal = Field(..., decimal_places=2)
    open_interest: Optional[int] = None


class TradeData(BaseModel):
    """成交明细数据模型"""
    symbol: str
    timestamp: datetime
    price: Decimal = Field(..., decimal_places=4)
    volume: int
    direction: str = Field(..., pattern="^(buy|sell)$")
    trade_id: str
    amount: Decimal = Field(..., decimal_places=2)


class DepthData(BaseModel):
    """深度行情数据模型"""
    symbol: str
    timestamp: datetime
    bids: List[List[Decimal]] = Field(..., description="买盘 [[价格, 数量], ...]")
    asks: List[List[Decimal]] = Field(..., description="卖盘 [[价格, 数量], ...]")
    max_bid: Decimal = Field(..., decimal_places=4)
    min_ask: Decimal = Field(..., decimal_places=4)
    bid_volume_total: int
    ask_volume_total: int


class TickData(BaseModel):
    """Tick数据模型"""
    symbol: str
    timestamp: datetime
    price: Decimal = Field(..., decimal_places=4)
    volume: int
    direction: str = Field(..., pattern="^(buy|sell|neutral)$")
    tick_id: str


class OrderBookData(BaseModel):
    """订单簿数据模型"""
    symbol: str
    timestamp: datetime
    bids: List[List[Decimal]] = Field(..., description="买盘 [[价格, 数量], ...]")
    asks: List[List[Decimal]] = Field(..., description="卖盘 [[价格, 数量], ...]")
    sequence: int


class Subscription(BaseModel):
    """订阅信息模型"""
    subscription_id: str
    client_id: str
    symbol: str
    data_type: DataType
    frequency: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_update: datetime = Field(default_factory=datetime.now)
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    message_count: int = 0
    last_message_at: Optional[datetime] = None


class WebSocketConnection(BaseModel):
    """WebSocket连接信息模型"""
    client_id: str
    connected_at: datetime = Field(default_factory=datetime.now)
    last_ping: datetime = Field(default_factory=datetime.now)
    subscriptions: List[str] = Field(default_factory=list)
    auth_info: Optional[Dict[str, Any]] = None
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    status: ConnectionStatus = ConnectionStatus.CONNECTED
    remote_address: Optional[str] = None
    user_agent: Optional[str] = None


class PerformanceMetrics(BaseModel):
    """性能监控指标模型"""
    timestamp: datetime = Field(default_factory=datetime.now)
    connections_count: int
    active_subscriptions: int
    messages_per_second: int
    average_latency_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    network_io_mbps: float
    error_rate_percent: float
    buffer_utilization_percent: float
    uptime_seconds: float


class ConnectionStats(BaseModel):
    """连接统计模型"""
    total_connections: int = 0
    active_connections: int = 0
    peak_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    average_latency_ms: float = 0.0
    connection_errors: int = 0
    subscription_errors: int = 0
    uptime_start: datetime = Field(default_factory=datetime.now)


class PublishingStats(BaseModel):
    """发布统计模型"""
    total_messages_sent: int = 0
    messages_per_symbol: Dict[str, int] = Field(default_factory=dict)
    messages_per_data_type: Dict[str, int] = Field(default_factory=dict)
    average_publish_latency_ms: float = 0.0
    failed_publishes: int = 0
    buffer_utilization_percent: float = 0.0
    last_publish_at: Optional[datetime] = None


class StatusMessage(BaseModel):
    """状态消息模型"""
    type: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[Dict[str, Any]] = None
    severity: str = Field(default="info", pattern="^(info|warning|error|critical)$")


class ErrorMessage(BaseModel):
    """错误消息模型"""
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[Dict[str, Any]] = None
    client_id: Optional[str] = None
    subscription_id: Optional[str] = None
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class HeartbeatMessage(BaseModel):
    """心跳消息模型"""
    type: str = "heartbeat"
    timestamp: datetime = Field(default_factory=datetime.now)
    client_id: str
    server_time: datetime = Field(default_factory=datetime.now)
    connection_uptime: float


class Alert(BaseModel):
    """告警消息模型"""
    type: str
    severity: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    threshold_value: Optional[float] = None
    current_value: Optional[float] = None
    client_id: Optional[str] = None


# 配置模型
class WebSocketConfig(BaseModel):
    """WebSocket配置模型"""
    max_connections: int = Field(default=1000, description="最大连接数")
    heartbeat_interval: float = Field(default=30.0, description="心跳间隔秒")
    connection_timeout: float = Field(default=60.0, description="连接超时秒")
    message_timeout: int = Field(default=10, description="消息超时秒")
    max_subscriptions_per_client: int = Field(default=100, description="每客户端最大订阅数")
    buffer_size: int = Field(default=1000, description="缓冲区大小")
    flush_interval: float = Field(default=0.1, description="刷新间隔秒")
    compression_threshold: int = Field(default=1024, description="压缩阈值字节")
    max_message_size: int = Field(default=1024*1024, description="最大消息大小字节")
    enable_compression: bool = Field(default=True, description="启用压缩")
    enable_batching: bool = Field(default=True, description="启用批量推送")


class ValidationResult(BaseModel):
    """验证结果模型"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


class MessageHandleResult(BaseModel):
    """消息处理结果模型"""
    success: bool
    message: str
    message_id: str
    response_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BroadcastResult(BaseModel):
    """广播结果模型"""
    total_clients: int
    success_count: int
    failure_count: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    elapsed_ms: float


class ConnectionResult(BaseModel):
    """连接结果模型"""
    success: bool
    client_id: str
    message: str
    connection_info: Optional[WebSocketConnection] = None
    error: Optional[str] = None