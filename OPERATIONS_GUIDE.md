# Argus MCP 运维指南

## 目录
1. [快速开始](#快速开始)
2. [环境配置](#环境配置)
3. [部署指南](#部署指南)
4. [监控和告警](#监控和告警)
5. [故障排除](#故障排除)
6. [性能优化](#性能优化)
7. [备份和恢复](#备份和恢复)
8. [安全维护](#安全维护)

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd project-argus-qmt-agent

# 运行设置脚本
chmod +x scripts/setup.sh
./scripts/setup.sh

# 或者手动设置
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 开发环境
python src/argus_mcp/main.py

# Docker部署
docker-compose up -d

# Kubernetes部署
kubectl apply -f k8s/
```

## 环境配置

### 开发环境

```bash
# 设置环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动开发服务器
python src/argus_mcp/main.py --debug
```

### 生产环境

```bash
# 生产环境变量配置
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=<your-production-secret>
DATABASE_URL=<production-database-url>
```

## 部署指南

### Docker部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f argus-mcp
```

### Kubernetes部署

```bash
# 构建并推送镜像
./scripts/k8s-deploy.sh production

# 部署到集群
kubectl apply -f k8s/

# 检查部署状态
kubectl get pods -l app=argus-mcp
kubectl get svc argus-mcp-service
```

### 传统部署

```bash
# 1. 环境准备
sudo apt update && sudo apt install -y python3-pip redis-server postgresql

# 2. 创建用户和数据库
sudo -u postgres createuser argus
sudo -u postgres createdb argus_db -O argus

# 3. 部署应用
git clone <repository>
cd project-argus-qmt-agent
pip install -r requirements.txt

# 4. 启动服务
python src/argus_mcp/main.py --host 0.0.0.0 --port 8000
```

## 监控和告警

### 监控指标

| 指标名称 | 描述 | 正常范围 |
|---------|------|----------|
| CPU使用率 | 系统CPU占用 | < 80% |
| 内存使用率 | 系统内存占用 | < 80% |
| 磁盘使用率 | 磁盘空间占用 | < 85% |
| 响应时间 | API响应时间 | < 1s |
| 错误率 | HTTP错误率 | < 1% |
| WebSocket连接数 | 当前连接数 | < 1000 |
| 消息处理延迟 | 消息处理时间 | < 100ms |

### 查看监控

```bash
# 访问Prometheus
http://localhost:9090

# 访问Grafana
http://localhost:3000
# 用户名: admin
# 密码: admin

# 健康检查
./scripts/health-check.sh
```

### 告警规则

系统配置了以下告警规则：
- 服务不可用
- CPU使用率过高
- 内存使用率过高
- WebSocket连接异常
- 消息处理延迟过高
- 数据库连接失败

## 故障排除

### 常见问题

#### 1. 服务启动失败

```bash
# 检查日志
docker-compose logs argus-mcp

# 检查端口占用
netstat -tulnp | grep :8000

# 检查配置文件
python -c "from src.argus_mcp.config import Config; print('Config loaded successfully')"
```

#### 2. 数据库连接失败

```bash
# 检查数据库状态
sudo systemctl status postgresql

# 检查连接
pg_isready -h localhost -p 5432

# 重置数据库
sudo -u postgres dropdb argus_db
sudo -u postgres createdb argus_db -O argus
```

#### 3. Redis连接失败

```bash
# 检查Redis状态
sudo systemctl status redis

# 测试连接
redis-cli ping

# 重启Redis
sudo systemctl restart redis
```

#### 4. WebSocket连接问题

```bash
# 测试WebSocket连接
websocat ws://localhost:8000/ws

# 检查防火墙
sudo ufw status

# 检查Nginx配置
nginx -t
```

### 日志分析

```bash
# 查看应用日志
tail -f logs/argus-mcp.log

# 查看系统日志
journalctl -u argus-mcp -f

# 查看Docker日志
docker-compose logs -f --tail=100
```

## 性能优化

### 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_trading_dates ON trading_dates(date);
CREATE INDEX idx_stock_list ON stock_list(code);
CREATE INDEX idx_market_data ON market_data(code, date);

-- 优化配置
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
```

### Redis优化

```bash
# 优化Redis配置
echo "maxmemory 256mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
sudo systemctl restart redis
```

### 应用优化

```python
# 启用缓存
CACHE_ENABLED=true
CACHE_SIZE=10000
CACHE_TTL=3600

# 连接池优化
CONNECTION_POOL_SIZE=20
CONNECTION_TIMEOUT=30

# 异步处理
ENABLE_ASYNC=true
WORKER_PROCESSES=4
```

## 备份和恢复

### 数据库备份

```bash
# 创建备份
pg_dump -h localhost -U argus argus_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 自动备份脚本
cat > scripts/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U argus argus_db > $BACKUP_DIR/backup_$DATE.sql
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
EOF
chmod +x scripts/backup-db.sh

# 设置定时任务
echo "0 2 * * * /path/to/project/scripts/backup-db.sh" | crontab -
```

### Redis备份

```bash
# 创建备份
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb backup/redis_$(date +%Y%m%d_%H%M%S).rdb

# 恢复备份
sudo systemctl stop redis
cp backup/redis_backup.rdb /var/lib/redis/dump.rdb
sudo systemctl start redis
```

### 应用备份

```bash
# 备份配置文件
tar -czf backup/config_$(date +%Y%m%d_%H%M%S).tar.gz config/ .env

# 备份日志文件
tar -czf backup/logs_$(date +%Y%m%d_%H%M%S).tar.gz logs/
```

## 安全维护

### 安全更新

```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 更新Python依赖
pip install --upgrade -r requirements.txt

# 更新Docker镜像
docker-compose pull
docker-compose up -d
```

### SSL证书管理

```bash
# 使用Let's Encrypt
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com

# 自动续期
sudo crontab -e
# 添加: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 访问控制

```bash
# 设置防火墙
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp

# 配置fail2ban
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

## 运维工具

### 日常检查脚本

```bash
# 创建日常检查脚本
cat > scripts/daily-check.sh << 'EOF'
#!/bin/bash
DATE=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$DATE] 开始日常检查"

# 检查服务状态
./scripts/health-check.sh

# 检查磁盘空间
df -h

# 检查内存使用
free -h

# 检查日志错误
grep -i error logs/argus-mcp.log | tail -10

DATE=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$DATE] 日常检查完成"
EOF

chmod +x scripts/daily-check.sh
```

### 监控脚本

```bash
# 运行监控脚本
./scripts/monitor.sh

# 持续监控
nohup ./scripts/monitor.sh --continuous > logs/monitor.log 2>&1 &
```

## 联系支持

### 获取帮助

- **文档**: 查看项目文档和README
- **问题报告**: 在GitHub Issues中创建新问题
- **技术支持**: 联系开发团队

### 紧急联系

| 情况 | 联系方式 |
|------|----------|
| 服务完全不可用 | 立即检查日志和系统状态 |
| 数据丢失 | 启动备份恢复流程 |
| 安全事件 | 立即断开网络连接并联系安全团队 |

---

**注意**: 本指南会定期更新，请确保使用最新版本。