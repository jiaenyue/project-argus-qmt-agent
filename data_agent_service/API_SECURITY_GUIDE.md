# QMT Data Agent API 安全认证指南

## 概述

QMT Data Agent API 实现了多层安全机制，包括API密钥认证、速率限制、IP白名单、访问日志记录和HTTPS支持。本文档详细说明了如何使用这些安全功能。

## 认证机制

### API密钥认证

API使用API密钥进行身份验证。支持两种认证方式：

#### 1. Bearer Token（推荐）

在HTTP请求头中添加Authorization字段：

```http
GET /api/v1/latest_market_data HTTP/1.1
Host: localhost:8000
Authorization: Bearer your_api_key_here
Content-Type: application/json
```

#### 2. API Key Header

在HTTP请求头中添加X-API-Key字段：

```http
GET /api/v1/latest_market_data HTTP/1.1
Host: localhost:8000
X-API-Key: your_api_key_here
Content-Type: application/json
```

#### 3. 查询参数（不推荐用于生产环境）

在URL查询参数中添加api_key：

```http
GET /api/v1/latest_market_data?api_key=your_api_key_here HTTP/1.1
Host: localhost:8000
Content-Type: application/json
```

### 默认API密钥

开发环境提供了两个默认API密钥：

1. **演示密钥**: `demo_key_12345`
   - 权限: `read:market_data`
   - 速率限制: 100请求/小时
   - 用途: 基本数据查询

2. **管理员密钥**: `admin_key_67890`
   - 权限: `read:market_data`, `write:market_data`, `admin:system`
   - 速率限制: 1000请求/小时
   - 用途: 完整API访问

## 权限系统

### 权限类型

- `read:market_data`: 读取市场数据
- `write:market_data`: 写入市场数据
- `admin:system`: 系统管理权限

### API端点权限要求

| 端点 | 权限要求 |
|------|----------|
| `/api/v1/instrument_detail/{symbol}` | `read:market_data` |
| `/api/v1/stock_list_in_sector` | `read:market_data` |
| `/api/v1/latest_market_data` | `read:market_data` |
| `/api/v1/full_market_data` | `read:market_data` |
| `/api/v1/get_trading_dates` | `read:market_data` |
| `/api/v1/hist_kline` | `read:market_data` |
| `/health` | 无需认证 |
| `/metrics` | 无需认证 |

## 速率限制

### 限制类型

1. **全局限制**: 1000请求/小时
2. **IP限制**: 100请求/小时
3. **API密钥限制**: 根据密钥配置

### 速率限制响应头

当请求受到速率限制时，响应会包含以下头信息：

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
Retry-After: 3600
```

### 速率限制错误响应

当超过速率限制时，API返回429状态码：

```json
{
  "error": "Rate limit exceeded",
  "message": "API key rate limit exceeded: 100 requests per 3600 seconds",
  "retry_after": 3600,
  "limit": 100,
  "window": 3600
}
```

## IP白名单

### 配置IP白名单

在`security_config.json`中配置：

```json
{
  "ip_whitelist": {
    "enabled": true,
    "ips": [
      "127.0.0.1",
      "192.168.1.0/24",
      "10.0.0.100"
    ]
  }
}
```

### 支持的IP格式

- 单个IP地址: `192.168.1.100`
- CIDR网段: `192.168.1.0/24`
- IPv6地址: `::1`

## HTTPS配置

### 环境变量配置

```bash
# 启用HTTPS
HTTPS_ONLY=true

# SSL证书文件路径
SSL_CERT_FILE=/path/to/server.crt
SSL_KEY_FILE=/path/to/server.key
SSL_CA_FILE=/path/to/ca.crt  # 可选

# 客户端证书验证（可选）
SSL_CLIENT_CERT_REQUIRED=false
```

### 生成自签名证书（开发环境）

```python
from https_config import https_config

# 生成自签名证书
https_config.generate_self_signed_cert("./certs")
```

### 安全响应头

启用HTTPS后，API会自动添加以下安全响应头：

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'
```

## 访问日志

### 日志格式

访问日志采用结构化JSON格式：

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "access",
  "request_id": "abc12345",
  "event_type": "request_start",
  "method": "GET",
  "path": "/api/v1/latest_market_data",
  "client_ip": "192.168.1.100",
  "user_agent": "curl/7.68.0",
  "api_key": "demo_key_12345",
  "user_name": "demo_user"
}
```

### 日志类型

1. **请求日志**: 记录所有HTTP请求
2. **认证日志**: 记录认证成功/失败事件
3. **安全日志**: 记录安全相关事件
4. **性能日志**: 记录请求处理时间
5. **错误日志**: 记录错误和异常

### 日志文件位置

- 访问日志: `./logs/access.log`
- 安全日志: `./logs/security.log`
- 性能日志: `./logs/performance.log`

## 错误响应

### 认证失败 (401)

```json
{
  "error": "Authentication failed",
  "message": "Invalid API key",
  "request_id": "abc12345"
}
```

### 权限不足 (403)

```json
{
  "error": "Permission denied",
  "message": "Insufficient permissions for this operation",
  "required_permissions": ["read:market_data"],
  "user_permissions": [],
  "request_id": "abc12345"
}
```

### IP被拒绝 (403)

```json
{
  "error": "Access denied",
  "message": "IP address not in whitelist",
  "client_ip": "10.0.0.1",
  "request_id": "abc12345"
}
```

## 配置管理

### 安全配置文件

主要配置文件: `security_config.json`

```json
{
  "api_keys": {
    "your_api_key": {
      "name": "用户名",
      "permissions": ["read:market_data"],
      "rate_limit": {
        "requests": 100,
        "window": 3600
      },
      "enabled": true
    }
  },
  "ip_whitelist": {
    "enabled": false,
    "ips": []
  },
  "rate_limiting": {
    "global": {
      "requests": 1000,
      "window": 3600
    },
    "per_ip": {
      "requests": 100,
      "window": 3600
    }
  },
  "authentication": {
    "require_api_key": true,
    "allow_bearer_token": true,
    "allow_query_param": true
  }
}
```

### 环境变量

参考`.env.example`文件配置环境变量。

## 最佳实践

### 1. API密钥管理

- 使用强随机密钥（至少32字符）
- 定期轮换API密钥
- 为不同用途创建不同的密钥
- 在生产环境中使用环境变量存储密钥

### 2. 网络安全

- 在生产环境中启用HTTPS
- 配置适当的IP白名单
- 使用反向代理（如Windows IIS）进行额外保护

### 3. 监控和告警

- 监控认证失败率
- 设置速率限制告警
- 定期审查访问日志
- 监控异常IP访问模式

### 4. 性能优化

- 合理设置速率限制
- 使用本地内存进行速率限制
- 启用请求缓存
- 优化日志写入性能

## 故障排除

### 常见问题

1. **认证失败**
   - 检查API密钥是否正确
   - 确认密钥是否已启用
   - 验证请求头格式

2. **速率限制**
   - 检查当前限制配置
   - 等待重置时间
   - 考虑申请更高限制

3. **IP访问被拒绝**
   - 确认IP白名单配置
   - 检查客户端真实IP
   - 考虑代理和负载均衡器影响

4. **HTTPS问题**
   - 验证证书文件路径
   - 检查证书有效期
   - 确认私钥文件权限

### 调试模式

设置环境变量启用调试模式：

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

## 联系支持

如有问题或需要技术支持，请联系开发团队或查看项目文档。