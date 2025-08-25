# WebSocket 实时数据服务运维指南

## 概述

本文档提供 WebSocket 实时数据服务的完整运维指南，包括部署、监控、故障排除和性能优化等内容。

## 目录

1. [部署指南](#部署指南)
2. [配置管理](#配置管理)
3. [监控和告警](#监控和告警)
4. [性能优化](#性能优化)
5. [故障排除](#故障排除)
6. [维护操作](#维护操作)
7. [安全最佳实践](#安全最佳实践)

## 部署指南

### 系统要求

**最低要求:**
- CPU: 2 核心
- 内存: 4GB RAM
- 存储: 20GB 可用空间
- 网络: 1Gbps 带宽

**推荐配置:**
- CPU: 4+ 核心
- 内存: 8GB+ RAM
- 存储: 50GB+ SSD
- 网络: 10Gbps 带宽

### Docker 部署

#### 1. 单实例部署

```bash
# 构建镜像
docker build -t websocket-server:latest .

# 运行容器
docker run -d \
  --name websocket-server \
  -p 8765:8765 \
  -p 8080:8080 \
  -e WEBSOCKET_HOST=0.0.0.0 \
  -e WEBSOCKET_PORT=8765 \
  -e MAX_CONNECTIONS=1000 \
  -e LOG_LEVEL=INFO \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  websocket-server:latest
```

#### 2. Docker Compose 部署

```bash
# 启动完整服务栈
docker-compose -f docker-compose.websocket.yml up -d

# 查看服务状态
docker-compose -f docker-compose.websocket.yml ps

# 查看日志
docker-compose -f docker-compose.websocket.yml logs -f websocket-server-1
```

### Kubernetes 部署

#### 1. 创建命名空间

```bash
kubectl create namespace websocket-system
```

#### 2. 部署服务

```bash
# 应用配置
kubectl apply -f k8s/websocket-deployment.yaml

# 检查部署状态
kubectl get pods -n websocket-system
kubectl get services -n websocket-system
```

#### 3. 扩展服务

```bash
# 手动扩展
kubectl scale deployment websocket-server --replicas=5 -n websocket-system

# 启用自动扩展
kubectl autoscale deployment websocket-server \
  --cpu-percent=70 \
  --min=2 \
  --max=10 \
  -n websocket-system
```

## 配置管理

### 环境变量配置

| 变量名 | 描述 | 默认值 | 示例 |
|--------|------|--------|------|
| `WEBSOCKET_HOST` | WebSocket 监听地址 | `0.0.0.0` | `0.0.0.0` |
| `WEBSOCKET_PORT` | WebSocket 监听端口 | `8765` | `8765` |
| `MAX_CONNECTIONS` | 最大连接数 | `1000` | `2000` |
| `MAX_SUBSCRIPTIONS_PER_CLIENT` | 每客户端最大订阅数 | `100` | `200` |
| `LOG_LEVEL` | 日志级别 | `INFO` | `DEBUG` |
| `REDIS_HOST` | Redis 主机地址 | `localhost` | `redis.example.com` |
| `CONSUL_HOST` | Consul 主机地址 | `localhost` | `consul.example.com` |

### 配置文件管理

#### 1. 主配置文件 (`config/deployment.yaml`)

```yaml
environment: production
websocket:
  host: "0.0.0.0"
  port: 8765
  max_connections: 2000
  max_subscriptions_per_client: 200
  heartbeat_interval: 30.0

service_discovery:
  backend: consul
  consul_host: consul.example.com
  consul_port: 8500

scaling:
  min_instances: 3
  max_instances: 10
  target_cpu_utilization: 70.0
  target_memory_utilization: 80.0

monitoring:
  enabled: true
  metrics_port: 9090
  prometheus_enabled: true
```

#### 2. 配置热重载

```bash
# 发送 SIGHUP 信号重载配置
kill -HUP $(pgrep -f websocket-server)

# 或使用 API 重载
curl -X POST http://localhost:8080/admin/reload-config
```

## 监控和告警

### 关键指标

#### 1. 系统指标
- **CPU 使用率**: 应保持在 70% 以下
- **内存使用率**: 应保持在 80% 以下
- **网络 I/O**: 监控带宽使用情况
- **磁盘 I/O**: 监控日志写入性能

#### 2. 应用指标
- **活跃连接数**: 监控连接数趋势
- **消息吞吐量**: 每秒处理的消息数
- **平均延迟**: 消息处理延迟
- **错误率**: 错误请求占比

#### 3. 业务指标
- **订阅数量**: 总订阅数和每客户端订阅数
- **数据推送成功率**: 数据推送的成功率
- **客户端连接时长**: 平均连接持续时间

### Prometheus 监控配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'websocket-server'
    static_configs:
      - targets: ['websocket-server:9090']
    metrics_path: '/metrics'
    scrape_interval: 10s
```

### Grafana 仪表板

推荐监控面板:
1. **系统概览**: CPU、内存、网络使用情况
2. **连接监控**: 活跃连接数、连接建立/断开趋势
3. **消息监控**: 消息吞吐量、延迟分布
4. **错误监控**: 错误率、错误类型分布
5. **性能监控**: 响应时间、资源利用率

### 告警规则

```yaml
# alert_rules.yml
groups:
  - name: websocket-alerts
    rules:
      - alert: HighCPUUsage
        expr: cpu_usage_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "WebSocket 服务 CPU 使用率过高"
          
      - alert: HighMemoryUsage
        expr: memory_usage_mb > 6000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "WebSocket 服务内存使用率过高"
          
      - alert: TooManyConnections
        expr: active_connections > 1800
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "WebSocket 连接数过多"
          
      - alert: HighErrorRate
        expr: error_rate > 0.05
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "WebSocket 错误率过高"
```

## 性能优化

### 系统级优化

#### 1. 操作系统调优

```bash
# 增加文件描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 调整网络参数
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" >> /etc/sysctl.conf
echo "net.core.netdev_max_backlog = 5000" >> /etc/sysctl.conf

# 应用设置
sysctl -p
```

#### 2. 容器资源限制

```yaml
# Docker Compose
services:
  websocket-server:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

```yaml
# Kubernetes
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

### 应用级优化

#### 1. 连接池优化

```python
# 配置连接池
WEBSOCKET_CONFIG = {
    "max_connections": 2000,
    "connection_pool_size": 1000,
    "idle_timeout": 300.0,
    "heartbeat_interval": 30.0
}
```

#### 2. 消息批处理优化

```python
# 配置消息批处理
MESSAGE_BATCH_CONFIG = {
    "batch_size": 100,
    "batch_timeout": 0.1,
    "compression_threshold": 1024
}
```

#### 3. 内存优化

```python
# 配置内存优化
MEMORY_CONFIG = {
    "gc_threshold_mb": 300.0,
    "gc_interval": 60.0,
    "memory_threshold_mb": 400.0
}
```

### 数据库优化

#### 1. Redis 配置优化

```conf
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
tcp-keepalive 60
timeout 300
```

#### 2. 连接池配置

```python
REDIS_CONFIG = {
    "host": "redis.example.com",
    "port": 6379,
    "db": 0,
    "max_connections": 50,
    "retry_on_timeout": True,
    "socket_keepalive": True,
    "socket_keepalive_options": {}
}
```

## 故障排除

### 常见问题

#### 1. 连接建立失败

**症状**: 客户端无法建立 WebSocket 连接

**可能原因**:
- 服务器未启动或端口被占用
- 防火墙阻止连接
- 负载均衡器配置错误
- SSL 证书问题

**排查步骤**:
```bash
# 检查服务状态
systemctl status websocket-server
docker ps | grep websocket

# 检查端口监听
netstat -tlnp | grep 8765
ss -tlnp | grep 8765

# 检查防火墙
iptables -L
ufw status

# 测试连接
telnet localhost 8765
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: test" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8765/
```

#### 2. 内存泄漏

**症状**: 内存使用持续增长，最终导致 OOM

**可能原因**:
- 连接未正确清理
- 消息队列积压
- 缓存未过期清理
- 循环引用

**排查步骤**:
```bash
# 监控内存使用
top -p $(pgrep websocket-server)
ps aux | grep websocket-server

# 检查连接数
curl http://localhost:8080/stats | jq '.connections'

# 检查垃圾回收
curl http://localhost:8080/admin/gc-stats

# 生成内存转储（Python）
kill -USR1 $(pgrep websocket-server)
```

#### 3. 高延迟问题

**症状**: 消息推送延迟过高

**可能原因**:
- CPU 使用率过高
- 网络拥塞
- 消息队列积压
- 数据库查询慢

**排查步骤**:
```bash
# 检查系统负载
uptime
iostat 1 5
sar -u 1 5

# 检查网络延迟
ping target-host
traceroute target-host

# 检查消息队列
curl http://localhost:8080/stats | jq '.message_queue'

# 检查数据库性能
redis-cli --latency -h redis-host
```

#### 4. 连接频繁断开

**症状**: 客户端连接经常断开重连

**可能原因**:
- 网络不稳定
- 心跳超时
- 负载均衡器超时
- 服务器资源不足

**排查步骤**:
```bash
# 检查连接日志
tail -f logs/websocket-server.log | grep -i disconnect

# 检查心跳配置
curl http://localhost:8080/config | jq '.heartbeat'

# 检查负载均衡器配置
nginx -t
curl -I http://load-balancer/health

# 监控资源使用
vmstat 1 5
free -h
```

### 日志分析

#### 1. 日志级别

- **DEBUG**: 详细调试信息
- **INFO**: 一般信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

#### 2. 关键日志模式

```bash
# 连接建立
grep "Client.*connected" logs/websocket-server.log

# 连接断开
grep "Client.*disconnected" logs/websocket-server.log

# 错误信息
grep "ERROR\|CRITICAL" logs/websocket-server.log

# 性能警告
grep "performance\|latency\|memory" logs/websocket-server.log
```

#### 3. 日志聚合

使用 ELK Stack 或类似工具进行日志聚合:

```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /app/logs/*.log
  fields:
    service: websocket-server
    environment: production

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

## 维护操作

### 日常维护

#### 1. 日志轮转

```bash
# 配置 logrotate
cat > /etc/logrotate.d/websocket-server << EOF
/app/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 websocket websocket
    postrotate
        kill -USR1 \$(pgrep websocket-server)
    endscript
}
EOF
```

#### 2. 数据备份

```bash
# Redis 数据备份
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb

# 配置文件备份
tar -czf /backup/config-$(date +%Y%m%d).tar.gz config/
```

#### 3. 健康检查

```bash
#!/bin/bash
# health-check.sh

# 检查服务状态
if ! curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "Health check failed"
    exit 1
fi

# 检查连接数
CONNECTIONS=$(curl -s http://localhost:8080/stats | jq -r '.connections.active_connections')
if [ "$CONNECTIONS" -gt 1800 ]; then
    echo "Too many connections: $CONNECTIONS"
    exit 1
fi

echo "Health check passed"
```

### 升级操作

#### 1. 滚动升级（Kubernetes）

```bash
# 更新镜像
kubectl set image deployment/websocket-server \
  websocket-server=websocket-server:v2.0.0 \
  -n websocket-system

# 监控升级进度
kubectl rollout status deployment/websocket-server -n websocket-system

# 回滚（如需要）
kubectl rollout undo deployment/websocket-server -n websocket-system
```

#### 2. 蓝绿部署

```bash
# 部署新版本
docker-compose -f docker-compose.websocket-v2.yml up -d

# 切换流量
# 更新负载均衡器配置

# 停止旧版本
docker-compose -f docker-compose.websocket-v1.yml down
```

### 性能调优

#### 1. 连接数优化

```bash
# 监控连接数趋势
watch -n 5 'curl -s http://localhost:8080/stats | jq .connections'

# 调整最大连接数
export MAX_CONNECTIONS=2000
docker restart websocket-server
```

#### 2. 内存优化

```bash
# 监控内存使用
watch -n 5 'curl -s http://localhost:8080/stats | jq .memory'

# 强制垃圾回收
curl -X POST http://localhost:8080/admin/gc
```

## 安全最佳实践

### 网络安全

#### 1. 防火墙配置

```bash
# 只允许必要端口
ufw allow 8765/tcp  # WebSocket
ufw allow 8080/tcp  # HTTP API
ufw deny 22/tcp     # SSH (仅管理网络)
```

#### 2. SSL/TLS 配置

```yaml
# nginx.conf
server {
    listen 443 ssl http2;
    server_name websocket.example.com;
    
    ssl_certificate /etc/ssl/certs/websocket.crt;
    ssl_certificate_key /etc/ssl/private/websocket.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    location /ws {
        proxy_pass http://websocket-backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 访问控制

#### 1. 认证配置

```python
# 启用认证
SECURITY_CONFIG = {
    "enable_auth": True,
    "auth_token": "your-secret-token",
    "allowed_origins": ["https://trusted-domain.com"],
    "rate_limit_enabled": True
}
```

#### 2. 速率限制

```yaml
# nginx rate limiting
http {
    limit_req_zone $binary_remote_addr zone=websocket:10m rate=10r/s;
    
    server {
        location /ws {
            limit_req zone=websocket burst=20 nodelay;
            # ... proxy configuration
        }
    }
}
```

### 监控和审计

#### 1. 访问日志

```python
# 启用详细访问日志
LOGGING_CONFIG = {
    "access_log": True,
    "access_log_format": "%(remote_addr)s - %(user)s [%(timestamp)s] \"%(request)s\" %(status)s %(bytes)s",
    "audit_log": True
}
```

#### 2. 安全事件监控

```bash
# 监控异常连接
tail -f logs/websocket-server.log | grep -E "(FAILED|DENIED|BLOCKED)"

# 监控认证失败
grep "authentication failed" logs/websocket-server.log | tail -20
```

## 总结

本运维指南涵盖了 WebSocket 实时数据服务的完整运维流程。定期检查和维护是确保服务稳定运行的关键。建议：

1. **建立监控体系**: 实施全面的监控和告警
2. **定期性能调优**: 根据业务增长调整配置
3. **制定应急预案**: 准备故障恢复流程
4. **持续安全加固**: 定期更新安全配置
5. **文档持续更新**: 保持运维文档的时效性

如有问题，请参考故障排除章节或联系技术支持团队。