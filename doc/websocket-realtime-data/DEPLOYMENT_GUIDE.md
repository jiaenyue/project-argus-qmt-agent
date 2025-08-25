# 部署配置和运维指南

## 概述

本文档提供了Argus MCP系统的完整部署配置和运维指南，包括容器化部署、Kubernetes编排、健康检查、监控集成和自动化运维流程。

## 目录

1. [快速开始](#快速开始)
2. [Docker部署](#docker部署)
3. [Kubernetes部署](#kubernetes部署)
4. [健康检查](#健康检查)
5. [监控和告警](#监控和告警)
6. [自动化部署](#自动化部署)
7. [故障排除](#故障排除)
8. [最佳实践](#最佳实践)

## 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- Kubernetes 1.20+ (可选)
- kubectl (可选)
- 4GB+ RAM
- 2核+ CPU

### 一键部署

```bash
# 克隆项目
git clone <repository-url>
cd project-argus-qmt-agent

# 运行部署脚本
chmod +x scripts/deploy.sh
./scripts/deploy.sh -e development
```

## Docker部署

### 使用Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f argus-mcp

# 停止服务
docker-compose down
```

### 手动构建和运行

```bash
# 构建镜像
docker build -t argus-mcp:latest .

# 运行容器
docker run -d \
  --name argus-mcp \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e REDIS_URL=redis://redis:6379 \
  -e POSTGRES_URL=postgresql://user:pass@postgres:5432/argus \
  argus-mcp:latest
```

### 环境变量配置

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| ENVIRONMENT | 运行环境 | development |
| PORT | 服务端口 | 8000 |
| LOG_LEVEL | 日志级别 | INFO |
| REDIS_URL | Redis连接URL | redis://localhost:6379 |
| POSTGRES_URL | PostgreSQL连接URL | postgresql://user:pass@localhost:5432/argus |
| ENABLE_METRICS | 启用指标收集 | true |
| ENABLE_HEALTH_CHECK | 启用健康检查 | true |

## Kubernetes部署

### 前提条件

```bash
# 确保kubectl已配置
kubectl cluster-info

# 创建命名空间
kubectl create namespace argus-mcp
```

### 部署步骤

```bash
# 使用部署脚本
chmod +x scripts/k8s-deploy.sh
./scripts/k8s-deploy.sh -e production -n argus-mcp

# 或者手动部署
kubectl apply -f k8s/ -n argus-mcp
```

### 配置说明

#### 部署配置 (k8s/deployment.yaml)

- **副本数**: 3个实例，确保高可用
- **资源限制**: 每个Pod限制2GB内存，1核CPU
- **健康检查**: 包含liveness和readiness探针
- **自动扩缩容**: HPA根据CPU和内存使用率自动调整副本数

#### 服务配置 (k8s/service.yaml)

- **类型**: LoadBalancer，提供外部访问
- **端口**: 80端口映射到容器的8000端口

#### 配置管理 (k8s/configmap.yaml)

- 使用ConfigMap管理应用配置
- 支持环境变量注入

### 扩缩容配置

```bash
# 手动调整副本数
kubectl scale deployment argus-mcp --replicas=5 -n argus-mcp

# 自动扩缩容
kubectl autoscale deployment argus-mcp --min=2 --max=10 --cpu-percent=70 -n argus-mcp
```

## 健康检查

### 健康检查端点

- **应用健康**: `GET /health`
- **详细健康**: `GET /health/detailed`
- **就绪检查**: `GET /ready`

### 健康检查配置

#### Docker健康检查

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

#### Kubernetes健康检查

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### 自定义健康检查

```python
from src.argus_mcp.deployment_manager import HealthChecker

health_checker = HealthChecker()

# 注册自定义检查
async def check_database():
    # 数据库连接检查
    return await database.is_connected()

health_checker.register_check("database", check_database)

# 运行所有检查
results = await health_checker.run_all_checks()
```

## 监控和告警

### Prometheus监控

#### 指标收集

- **应用指标**: WebSocket连接数、消息处理延迟、错误率
- **系统指标**: CPU、内存、磁盘、网络使用率
- **业务指标**: 交易量、用户活跃度、系统吞吐量

#### 配置文件

- **Prometheus配置**: `config/prometheus.yml`
- **告警规则**: `config/alert_rules.yml`

#### 访问监控面板

- **Prometheus**: http://localhost:9091
- **Grafana**: http://localhost:3000 (admin/admin123)

### 关键指标

| 指标名称 | 描述 | 告警阈值 |
|----------|------|----------|
| websocket_active_connections | WebSocket活跃连接数 | > 800 |
| websocket_message_processing_duration_seconds | 消息处理延迟 | > 1s |
| process_cpu_seconds_total | CPU使用率 | > 80% |
| process_resident_memory_bytes | 内存使用率 | > 90% |
| redis_up | Redis连接状态 | = 0 |
| pg_up | PostgreSQL连接状态 | = 0 |

### 告警配置

#### 告警规则

```yaml
# 服务不可用告警
- alert: ServiceDown
  expr: up{job="argus-mcp"} == 0
  for: 30s
  labels:
    severity: critical
```

#### 通知配置

支持多种通知方式：
- 邮件通知
- Slack通知
- 钉钉通知
- Webhook通知

## 自动化部署

### 部署脚本

#### Docker部署脚本

```bash
# 部署到开发环境
./scripts/deploy.sh -e development

# 部署到生产环境
./scripts/deploy.sh -e production -v 1.0.0

# 构建并推送镜像
./scripts/deploy.sh -b -p -v 1.0.0
```

#### Kubernetes部署脚本

```bash
# 部署到Kubernetes
./scripts/k8s-deploy.sh -e production -n argus-mcp -v 1.0.0
```

### CI/CD集成

#### GitHub Actions示例

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build and Push
        run: |
          docker build -t argus-mcp:${{ github.ref_name }} .
          docker push registry.com/argus-mcp:${{ github.ref_name }}
      
      - name: Deploy to K8s
        run: |
          ./scripts/k8s-deploy.sh -e production -v ${{ github.ref_name }}
```

## 故障排除

### 常见问题

#### 1. 容器启动失败

**症状**: 容器启动后立即退出

**解决方案**:
```bash
# 查看容器日志
docker logs argus-mcp

# 检查环境变量
docker inspect argus-mcp | grep -A 10 Env

# 进入容器调试
docker run -it --rm argus-mcp:latest /bin/bash
```

#### 2. WebSocket连接失败

**症状**: 客户端无法建立WebSocket连接

**解决方案**:
```bash
# 检查服务状态
curl http://localhost:8000/health

# 检查端口监听
netstat -tlnp | grep 8000

# 检查防火墙设置
sudo ufw status
```

#### 3. 数据库连接问题

**症状**: 应用无法连接到数据库

**解决方案**:
```bash
# 检查数据库容器
docker ps | grep postgres

# 测试数据库连接
docker exec -it postgres psql -U argus -d argus_db -c "SELECT 1"

# 检查网络连接
docker network ls
docker network inspect argus-network
```

### 调试工具

#### 日志分析

```bash
# 实时查看应用日志
docker logs -f argus-mcp

# 查看特定时间段的日志
docker logs --since 1h argus-mcp

# 搜索错误日志
docker logs argus-mcp | grep ERROR
```

#### 性能监控

```bash
# 容器资源使用
docker stats

# 进程监控
docker top argus-mcp

# 网络监控
docker exec argus-mcp netstat -tlnp
```

## 最佳实践

### 安全配置

1. **镜像安全**
   - 使用官方基础镜像
   - 定期更新镜像
   - 扫描镜像漏洞

2. **网络安全**
   - 使用TLS/SSL
   - 配置防火墙规则
   - 限制容器权限

3. **数据安全**
   - 加密敏感数据
   - 定期备份数据
   - 使用密钥管理服务

### 性能优化

1. **资源限制**
   - 设置合理的内存和CPU限制
   - 使用资源请求和限制
   - 监控资源使用情况

2. **缓存策略**
   - 使用Redis缓存
   - 配置CDN加速
   - 优化数据库查询

3. **连接池管理**
   - 合理配置连接池大小
   - 设置连接超时时间
   - 监控连接使用情况

### 维护策略

1. **定期维护**
   - 每周检查系统健康状态
   - 每月更新依赖版本
   - 每季度进行安全审计

2. **备份策略**
   - 数据库每日备份
   - 配置文件版本控制
   - 容器镜像备份

3. **灾难恢复**
   - 制定恢复计划
   - 定期演练恢复流程
   - 建立异地备份

## 监控仪表板

### Grafana仪表板

我们提供了预配置的Grafana仪表板，包含以下视图：

1. **系统概览**: CPU、内存、网络、磁盘使用率
2. **应用性能**: WebSocket连接、消息处理、错误率
3. **业务指标**: 交易量、用户活跃度、响应时间
4. **告警状态**: 当前告警、历史告警、告警统计

### 访问地址

- **应用服务**: http://localhost:8000
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9091
- **健康检查**: http://localhost:8000/health

## 联系支持

如有部署或运维问题，请联系：
- 技术支持: support@argus.com
- 文档更新: https://github.com/argus-mcp/docs
- 问题反馈: https://github.com/argus-mcp/issues