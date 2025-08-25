# WebSocket客户端SDK API文档

## 概述

WebSocket客户端SDK提供了简单易用的API来连接和使用WebSocket实时数据服务。支持连接管理、数据订阅、错误处理和自动重连等功能。

## 快速开始

### 安装依赖

```bash
pip install websockets
```

### 基础使用示例

```python
import asyncio
from src.argus_mcp.websocket_client import QuickStartClient

async def main():
    # 创建客户端
    client = await QuickStartClient.create("ws://localhost:8000/ws")
    
    # 连接服务器
    if await client.connect():
        print("连接成功")
        
        # 定义数据处理器
        def on_price_update(data):
            print(f"价格更新: {data}")
        
        # 订阅股票数据
        sub_id = await QuickStartClient.subscribe_stocks(
            client, ["AAPL", "GOOGL", "MSFT"], on_price_update
        )
        
        # 保持连接运行
        try:
            await asyncio.sleep(60)  # 运行60秒
        finally:
            await client.disconnect()

# 运行示例
if __name__ == "__main__":
    asyncio.run(main())
```

## API参考

### WebSocketClient类

#### 构造函数

```python
from src.argus_mcp.websocket_client import WebSocketClient, ConnectionConfig

config = ConnectionConfig(
    url="ws://localhost:8000/ws",
    api_key="your_api_key",  # 可选
    max_reconnect_attempts=5,
    reconnect_delay=1.0,
    heartbeat_interval=30,
    timeout=10,
    max_subscriptions=100
)

client = WebSocketClient(config)
```

#### 方法

##### connect()
连接到WebSocket服务器。

```python
success = await client.connect()
if success:
    print("连接成功")
```

##### disconnect()
断开与服务器的连接。

```python
await client.disconnect()
```

##### subscribe(subscription_id, config)
订阅实时数据。

```python
from src.argus_mcp.websocket_client import SubscriptionConfig

config = SubscriptionConfig(
    symbols=["AAPL", "GOOGL"],
    data_types=["price", "volume", "orderbook"],
    update_frequency="realtime",  # "realtime", "1s", "5s", "1m"
    filters={
        "min_price": 100,
        "max_price": 1000
    }
)

await client.subscribe("my_subscription", config)
```

##### unsubscribe(subscription_id)
取消订阅。

```python
await client.unsubscribe("my_subscription")
```

##### add_message_handler(data_type, handler)
添加消息处理器。

```python
def handle_price_update(data):
    symbol = data["symbol"]
    price = data["price"]
    timestamp = data["timestamp"]
    print(f"{symbol}: ${price} @ {timestamp}")

client.add_message_handler("price", handle_price_update)
```

##### get_stats()
获取连接统计信息。

```python
stats = await client.get_stats()
print(stats)
# 输出示例:
# {
#     "messages_received": 1250,
#     "messages_sent": 5,
#     "reconnect_count": 2,
#     "errors": 0,
#     "state": "connected",
#     "connection_id": "550e8400-e29b-41d4-a716-446655440000",
#     "subscriptions_count": 3,
#     "uptime": "0:05:23.123456"
# }
```

### 数据类型

#### ConnectionConfig
连接配置类。

```python
@dataclass
class ConnectionConfig:
    url: str                           # WebSocket服务器URL
    api_key: Optional[str] = None      # API密钥（可选）
    max_reconnect_attempts: int = 5    # 最大重连次数
    reconnect_delay: float = 1.0       # 重连延迟（秒）
    heartbeat_interval: int = 30       # 心跳间隔（秒）
    timeout: int = 10                  # 超时时间（秒）
    max_subscriptions: int = 100       # 最大订阅数量
```

#### SubscriptionConfig
订阅配置类。

```python
@dataclass
class SubscriptionConfig:
    symbols: List[str]                 # 股票代码列表
    data_types: List[str]              # 数据类型列表
    update_frequency: str = "realtime" # 更新频率
    filters: Dict[str, Any] = None     # 过滤条件
```

#### ConnectionState
连接状态枚举。

```python
class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
```

### WebSocketClientManager类

管理多个客户端实例。

```python
from src.argus_mcp.websocket_client import WebSocketClientManager

manager = WebSocketClientManager()

# 创建客户端
client1 = manager.create_client("client1", config1)
client2 = manager.create_client("client2", config2)

# 获取所有客户端统计
stats = await manager.get_all_stats()

# 关闭所有客户端
await manager.close_all()
```

### QuickStartClient类

快速开始工具类。

```python
from src.argus_mcp.websocket_client import QuickStartClient

# 创建客户端
client = await QuickStartClient.create("ws://localhost:8000/ws", "api_key")

# 快速订阅股票
def handle_stock_data(data):
    print(f"股票数据: {data}")

sub_id = await QuickStartClient.subscribe_stocks(
    client, 
    ["AAPL", "GOOGL", "MSFT"], 
    handle_stock_data
)
```

## 高级用法

### 自定义消息处理器

```python
import asyncio
from src.argus_mcp.websocket_client import WebSocketClient, ConnectionConfig, SubscriptionConfig

class DataProcessor:
    def __init__(self):
        self.price_cache = {}
        self.volume_cache = {}
    
    async def handle_price(self, data):
        symbol = data["symbol"]
        price = data["price"]
        self.price_cache[symbol] = price
        
        if self.should_alert(symbol, price):
            await self.send_alert(symbol, price)
    
    async def handle_volume(self, data):
        symbol = data["symbol"]
        volume = data["volume"]
        self.volume_cache[symbol] = volume
    
    def should_alert(self, symbol, price):
        # 实现自定义告警逻辑
        return price > 200
    
    async def send_alert(self, symbol, price):
        print(f"🚨 价格告警: {symbol} 达到 ${price}")

async def main():
    processor = DataProcessor()
    
    config = ConnectionConfig(url="ws://localhost:8000/ws")
    client = WebSocketClient(config)
    
    # 添加自定义处理器
    client.add_message_handler("price", processor.handle_price)
    client.add_message_handler("volume", processor.handle_volume)
    
    if await client.connect():
        # 订阅数据
        sub_config = SubscriptionConfig(
            symbols=["AAPL", "GOOGL", "TSLA"],
            data_types=["price", "volume"]
        )
        await client.subscribe("main_subscription", sub_config)
        
        # 运行事件循环
        try:
            await asyncio.sleep(300)  # 运行5分钟
        finally:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### 错误处理和重连

```python
import asyncio
from src.argus_mcp.websocket_client import WebSocketClient, ConnectionConfig

class RobustClient:
    def __init__(self, url, api_key=None):
        self.config = ConnectionConfig(
            url=url,
            api_key=api_key,
            max_reconnect_attempts=10,
            reconnect_delay=2.0,
            heartbeat_interval=15
        )
        self.client = WebSocketClient(self.config)
    
    async def start(self):
        while True:
            try:
                if await self.client.connect():
                    # 设置消息处理器
                    self.setup_handlers()
                    
                    # 重新订阅
                    await self.resubscribe()
                    
                    # 等待连接
                    await self.client.wait_for_connection()
                    
                    # 获取统计信息
                    stats = await self.client.get_stats()
                    print(f"连接成功: {stats}")
                    
                    # 运行直到断开
                    while self.client.state.value == "connected":
                        await asyncio.sleep(1)
                        
                else:
                    print("连接失败，重试中...")
                    await asyncio.sleep(5)
                    
            except Exception as e:
                print(f"错误: {e}")
                await asyncio.sleep(5)
    
    def setup_handlers(self):
        def handle_data(data):
            print(f"收到数据: {data}")
        
        self.client.add_message_handler("price", handle_data)
        self.client.add_message_handler("volume", handle_data)
    
    async def resubscribe(self):
        # 重新订阅之前的订阅
        config = SubscriptionConfig(
            symbols=["AAPL", "GOOGL"],
            data_types=["price"]
        )
        await self.client.subscribe("main", config)

async def main():
    robust_client = RobustClient("ws://localhost:8000/ws", "api_key")
    await robust_client.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### 多客户端管理

```python
import asyncio
from src.argus_mcp.websocket_client import WebSocketClientManager, ConnectionConfig

class MultiClientApp:
    def __init__(self):
        self.manager = WebSocketClientManager()
    
    async def setup_clients(self):
        # 创建不同配置的客户端
        configs = [
            ConnectionConfig("ws://server1.com/ws", "key1"),
            ConnectionConfig("ws://server2.com/ws", "key2"),
            ConnectionConfig("ws://server3.com/ws", "key3")
        ]
        
        for i, config in enumerate(configs):
            client = self.manager.create_client(f"client_{i}", config)
            
            # 设置处理器
            client.add_message_handler("price", self.handle_price)
            
            # 连接
            await client.connect()
            
            # 订阅
            from src.argus_mcp.websocket_client import SubscriptionConfig
            sub_config = SubscriptionConfig(
                symbols=["AAPL"],
                data_types=["price"]
            )
            await client.subscribe(f"sub_{i}", sub_config)
    
    def handle_price(self, data):
        print(f"价格更新: {data}")
    
    async def monitor_stats(self):
        while True:
            stats = await self.manager.get_all_stats()
            print("=== 客户端统计 ===")
            for client_id, stat in stats.items():
                print(f"{client_id}: {stat}")
            
            await asyncio.sleep(30)
    
    async def run(self):
        await self.setup_clients()
        await self.monitor_stats()

async def main():
    app = MultiClientApp()
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## 配置示例

### 生产环境配置

```python
config = ConnectionConfig(
    url="wss://api.example.com/ws/v1",
    api_key="your_production_api_key",
    max_reconnect_attempts=10,
    reconnect_delay=2.0,
    heartbeat_interval=20,
    timeout=15,
    max_subscriptions=1000
)
```

### 开发环境配置

```python
config = ConnectionConfig(
    url="ws://localhost:8000/ws",
    max_reconnect_attempts=3,
    reconnect_delay=1.0,
    heartbeat_interval=30,
    timeout=10,
    max_subscriptions=50
)
```

### 高频交易配置

```python
config = ConnectionConfig(
    url="wss://api.trading.com/ws",
    api_key="trading_api_key",
    max_reconnect_attempts=20,
    reconnect_delay=0.5,
    heartbeat_interval=10,
    timeout=5,
    max_subscriptions=5000
)
```

## 最佳实践

1. **错误处理**: 始终实现适当的错误处理和重连机制
2. **资源管理**: 使用客户端管理器来管理多个客户端实例
3. **性能优化**: 合理设置心跳间隔和重连参数
4. **监控**: 定期检查连接统计和性能指标
5. **清理**: 确保在程序退出时正确关闭所有连接

## 故障排查

### 常见问题

1. **连接失败**: 检查URL和API密钥是否正确
2. **订阅失败**: 确认股票代码和数据类型是否有效
3. **消息丢失**: 检查网络连接和心跳设置
4. **内存泄漏**: 确保正确移除消息处理器

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 启用详细日志
client = WebSocketClient(config)
client.add_message_handler("debug", lambda x: print(f"DEBUG: {x}"))
```