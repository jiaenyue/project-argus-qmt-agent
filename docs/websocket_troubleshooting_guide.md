# WebSocket 实时数据服务故障排除指南

## 概述

本文档提供 WebSocket 实时数据服务的详细故障排除指南，帮助运维人员快速定位和解决常见问题。

## 目录

1. [故障排除流程](#故障排除流程)
2. [连接问题](#连接问题)
3. [性能问题](#性能问题)
4. [数据问题](#数据问题)
5. [资源问题](#资源问题)
6. [网络问题](#网络问题)
7. [配置问题](#配置问题)
8. [监控和诊断工具](#监控和诊断工具)

## 故障排除流程

### 基本排查步骤

1. **确认问题范围**
   - 影响所有用户还是部分用户？
   - 问题是间歇性还是持续性？
   - 何时开始出现问题？

2. **检查服务状态**
   ```bash
   # 检查服务运行状态
   systemctl status websocket-server
   docker ps | grep websocket
   kubectl get pods -n websocket-system
   ```

3. **查看实时日志**
   ```bash
   # 查看实时日志
   tail -f logs/websocket-server.log
   docker logs -f websocket-server
   kubectl logs -f deployment/websocket-server -n websocket-system
   ```

4. **检查系统资源**
   ```bash
   # 检查系统资源使用情况
   top
   htop
   free -h
   df -h
   ```

5. **验证网络连通性**
   ```bash
   # 测试网络连接
   telnet localhost 8765
   curl -I http://localhost:8080/health
   ```

## 连接问题

### 问题1: 客户端无法建立连接

**症状**:
- 客户端连接超时
- 连接被拒绝
- 握手失败

**可能原因**:
- 服务未启动
- 端口被占用或防火墙阻止
- 负载均衡器配置错误
- SSL证书问题

**排查步骤**:

1. **检查服务状态**
   ```bash
   # 检查进程是否运行
   ps aux | grep websocket-server
   
   # 检查端口监听
   netstat -tlnp | grep 8765
   ss -tlnp | grep 8765
   ```

2. **检查防火墙设置**
   ```bash
   # Ubuntu/Debian
   ufw status
   iptables -L
   
   # CentOS/RHEL
   firewall-cmd --list-all
   ```

3. **测试本地连接**
   ```bash
   # 使用 telnet 测试
   telnet localhost 8765
   
   # 使用 curl 测试 WebSocket 握手
   curl -i -N \
     -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: test" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8765/
   ```

4. **检查配置文件**
   ```bash
   # 验证配置语法
   python -c "import yaml; yaml.safe_load(open('config/websocket_config.yaml'))"
   ```

**解决方案**:
- 启动服务: `systemctl start websocket-server`
- 开放端口: `ufw allow 8765/tcp`
- 修复配置错误
- 更新SSL证书

### 问题2: 连接频繁断开

**症状**:
- 客户端连接不稳定
- 频繁重连
- 心跳超时

**可能原因**:
- 网络不稳定
- 心跳配置不当
- 负载均衡器超时设置
- 服务器资源不足

**排查步骤**:

1. **检查连接日志**
   ```bash
   # 查看断开连接的日志
   grep -i "disconnect\|closed\|timeout" logs/websocket-server.log | tail -20
   ```

2. **检查心跳配置**
   ```bash
   # 查看当前心跳设置
   curl http://localhost:8080/config | jq '.heartbeat'
   ```

3. **监控连接统计**
   ```bash
   # 实时监控连接数变化
   watch -n 2 'curl -s http://localhost:8080/stats | jq .connections'
   ```

4. **检查网络质量**
   ```bash
   # 检查网络延迟和丢包
   ping -c 100 target-host
   mtr target-host
   ```

**解决方案**:
- 调整心跳间隔: `HEARTBEAT_INTERVAL=30`
- 增加超时时间: `PING_TIMEOUT=30`
- 优化负载均衡器配置
- 增加服务器资源

### 问题3: 连接数达到上限

**症状**:
- 新连接被拒绝
- "MAX_CONNECTIONS_EXCEEDED" 错误
- 服务响应变慢

**排查步骤**:

1. **检查当前连接数**
   ```bash
   curl -s http://localhost:8080/stats | jq '.connections.active_connections'
   ```

2. **查看连接分布**
   ```bash
   # 按客户端IP统计连接数
   netstat -an | grep :8765 | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr
   ```

3. **检查僵尸连接**
   ```bash
   # 查看长时间无活动的连接
   curl -s http://localhost:8080/admin/connections | jq '.[] | select(.idle_time > 300)'
   ```

**解决方案**:
- 增加最大连接数: `MAX_CONNECTIONS=2000`
- 清理僵尸连接: `curl -X POST http://localhost:8080/admin/cleanup-connections`
- 实施连接限制策略
- 横向扩展服务实例

## 性能问题

### 问题4: 消息延迟过高

**症状**:
- 消息推送延迟超过预期
- 客户端接收数据不及时
- 延迟监控告警

**可能原因**:
- CPU使用率过高
- 内存不足
- 网络拥塞
- 消息队列积压
- 数据库查询慢

**排查步骤**:

1. **检查系统负载**
   ```bash
   # 查看CPU使用情况
   top -p $(pgrep websocket-server)
   
   # 查看系统负载
   uptime
   iostat 1 5
   ```

2. **检查内存使用**
   ```bash
   # 查看内存使用情况
   free -h
   ps aux --sort=-%mem | head -10
   ```

3. **检查消息队列**
   ```bash
   # 查看消息队列状态
   curl -s http://localhost:8080/stats | jq '.message_queue'
   ```

4. **检查网络延迟**
   ```bash
   # 测试网络延迟
   ping -c 10 target-host
   traceroute target-host
   ```

5. **分析延迟分布**
   ```bash
   # 查看延迟统计
   curl -s http://localhost:8080/metrics | grep latency
   ```

**解决方案**:
- 增加CPU资源
- 增加内存容量
- 优化消息批处理
- 调整网络配置
- 优化数据库查询

### 问题5: 内存使用过高

**症状**:
- 内存使用持续增长
- 出现OOM错误
- 系统响应变慢

**排查步骤**:

1. **监控内存趋势**
   ```bash
   # 实时监控内存使用
   watch -n 5 'free -h && ps aux --sort=-%mem | head -5'
   ```

2. **检查内存泄漏**
   ```bash
   # 查看进程内存映射
   pmap -d $(pgrep websocket-server)
   
   # 检查垃圾回收统计
   curl -s http://localhost:8080/admin/gc-stats
   ```

3. **分析内存分配**
   ```bash
   # 生成内存转储（如果支持）
   kill -USR1 $(pgrep websocket-server)
   ```

**解决方案**:
- 强制垃圾回收: `curl -X POST http://localhost:8080/admin/gc`
- 调整GC参数
- 增加内存限制
- 修复内存泄漏代码

### 问题6: CPU使用率过高

**症状**:
- CPU使用率持续超过80%
- 系统响应变慢
- 负载均衡器健康检查失败

**排查步骤**:

1. **分析CPU使用**
   ```bash
   # 查看CPU使用详情
   top -H -p $(pgrep websocket-server)
   
   # 使用perf分析热点
   perf top -p $(pgrep websocket-server)
   ```

2. **检查线程状态**
   ```bash
   # 查看线程数
   ps -eLf | grep websocket-server | wc -l
   
   # 查看线程状态
   curl -s http://localhost:8080/admin/threads
   ```

**解决方案**:
- 增加CPU核心数
- 优化算法复杂度
- 使用异步处理
- 实施负载均衡

## 数据问题

### 问题7: 数据推送失败

**症状**:
- 客户端收不到数据更新
- 数据推送错误日志
- 订阅状态异常

**排查步骤**:

1. **检查数据源状态**
   ```bash
   # 检查数据源连接
   curl -s http://localhost:8080/admin/datasource-status
   ```

2. **验证订阅状态**
   ```bash
   # 查看订阅统计
   curl -s http://localhost:8080/stats | jq '.subscriptions'
   ```

3. **检查数据流**
   ```bash
   # 监控数据推送
   tail -f logs/websocket-server.log | grep -i "publish\|push"
   ```

**解决方案**:
- 重启数据源连接
- 清理无效订阅
- 检查数据格式
- 修复推送逻辑

### 问题8: 数据不一致

**症状**:
- 不同客户端收到不同数据
- 数据时间戳错误
- 缓存数据过期

**排查步骤**:

1. **检查缓存状态**
   ```bash
   # 查看缓存统计
   redis-cli info memory
   redis-cli info stats
   ```

2. **验证数据时间戳**
   ```bash
   # 检查系统时间同步
   timedatectl status
   ntpq -p
   ```

3. **对比数据源**
   ```bash
   # 直接查询数据源
   curl -s http://data-source-api/latest-data
   ```

**解决方案**:
- 清理缓存: `redis-cli FLUSHDB`
- 同步系统时间: `ntpdate -s time.nist.gov`
- 重新加载数据
- 修复数据同步逻辑

## 资源问题

### 问题9: 磁盘空间不足

**症状**:
- 日志写入失败
- 临时文件创建失败
- 系统告警

**排查步骤**:

1. **检查磁盘使用**
   ```bash
   df -h
   du -sh /app/logs/*
   ```

2. **查找大文件**
   ```bash
   find /app -type f -size +100M -exec ls -lh {} \;
   ```

**解决方案**:
- 清理日志文件: `find /app/logs -name "*.log" -mtime +7 -delete`
- 配置日志轮转
- 增加磁盘空间
- 压缩历史数据

### 问题10: 文件描述符不足

**症状**:
- "Too many open files" 错误
- 新连接被拒绝
- 文件操作失败

**排查步骤**:

1. **检查文件描述符限制**
   ```bash
   ulimit -n
   cat /proc/$(pgrep websocket-server)/limits | grep files
   ```

2. **查看当前使用情况**
   ```bash
   lsof -p $(pgrep websocket-server) | wc -l
   ```

**解决方案**:
- 增加限制: `ulimit -n 65536`
- 修改系统配置: `/etc/security/limits.conf`
- 重启服务应用新限制

## 网络问题

### 问题11: 网络连接超时

**症状**:
- 连接建立超时
- 数据传输中断
- 网络错误日志

**排查步骤**:

1. **检查网络连通性**
   ```bash
   ping target-host
   telnet target-host 8765
   ```

2. **检查网络配置**
   ```bash
   ip route show
   netstat -rn
   ```

3. **分析网络流量**
   ```bash
   tcpdump -i any port 8765
   iftop
   ```

**解决方案**:
- 检查网络设备
- 调整超时参数
- 优化网络路由
- 联系网络管理员

### 问题12: 负载均衡器问题

**症状**:
- 请求分发不均
- 健康检查失败
- 会话粘性问题

**排查步骤**:

1. **检查负载均衡器状态**
   ```bash
   # Nginx
   nginx -t
   curl -I http://load-balancer/health
   
   # HAProxy
   echo "show stat" | socat stdio /var/run/haproxy/admin.sock
   ```

2. **验证后端服务**
   ```bash
   # 直接测试后端服务
   curl -I http://backend-server:8080/health
   ```

**解决方案**:
- 修复配置错误
- 重启负载均衡器
- 调整健康检查参数
- 更新后端服务列表

## 配置问题

### 问题13: 配置文件错误

**症状**:
- 服务启动失败
- 配置解析错误
- 参数不生效

**排查步骤**:

1. **验证配置语法**
   ```bash
   # YAML配置
   python -c "import yaml; yaml.safe_load(open('config/websocket_config.yaml'))"
   
   # JSON配置
   python -c "import json; json.load(open('config/websocket_config.json'))"
   ```

2. **检查配置加载**
   ```bash
   # 查看当前配置
   curl -s http://localhost:8080/config
   ```

**解决方案**:
- 修复语法错误
- 验证参数值
- 重新加载配置
- 恢复备份配置

### 问题14: 环境变量冲突

**症状**:
- 配置值不符合预期
- 环境变量未生效
- 配置覆盖问题

**排查步骤**:

1. **检查环境变量**
   ```bash
   env | grep WEBSOCKET
   printenv | grep -E "(WEBSOCKET|MAX_|LOG_)"
   ```

2. **验证配置优先级**
   ```bash
   # 查看最终配置
   curl -s http://localhost:8080/admin/effective-config
   ```

**解决方案**:
- 清理冲突的环境变量
- 明确配置优先级
- 使用配置文件管理
- 重启服务应用配置

## 监控和诊断工具

### 内置诊断接口

```bash
# 健康检查
curl http://localhost:8080/health

# 服务统计
curl http://localhost:8080/stats

# 配置信息
curl http://localhost:8080/config

# 连接详情
curl http://localhost:8080/admin/connections

# 性能指标
curl http://localhost:8080/metrics

# 垃圾回收统计
curl http://localhost:8080/admin/gc-stats

# 线程信息
curl http://localhost:8080/admin/threads
```

### 系统监控命令

```bash
# 系统资源监控
top
htop
iotop
nethogs

# 网络监控
netstat -tlnp
ss -tlnp
iftop
tcpdump

# 进程监控
ps aux
pstree
lsof

# 日志分析
tail -f logs/websocket-server.log
journalctl -u websocket-server -f
grep -E "(ERROR|WARN|CRITICAL)" logs/websocket-server.log
```

### 性能分析工具

```bash
# CPU性能分析
perf top -p $(pgrep websocket-server)
perf record -p $(pgrep websocket-server)
perf report

# 内存分析
valgrind --tool=memcheck ./websocket-server
pmap -d $(pgrep websocket-server)

# 网络分析
tcpdump -i any port 8765 -w capture.pcap
wireshark capture.pcap
```

### 自动化诊断脚本

```bash
#!/bin/bash
# websocket-diagnostic.sh

echo "=== WebSocket服务诊断报告 ==="
echo "生成时间: $(date)"
echo

echo "=== 服务状态 ==="
systemctl status websocket-server 2>/dev/null || echo "systemctl不可用"
docker ps | grep websocket 2>/dev/null || echo "Docker不可用"

echo
echo "=== 资源使用 ==="
echo "CPU使用率:"
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1

echo "内存使用:"
free -h | grep Mem

echo "磁盘使用:"
df -h | grep -E "(/$|/app)"

echo
echo "=== 网络状态 ==="
echo "端口监听:"
netstat -tlnp | grep 8765

echo "连接数:"
netstat -an | grep :8765 | wc -l

echo
echo "=== 服务健康检查 ==="
if curl -f http://localhost:8080/health >/dev/null 2>&1; then
    echo "健康检查: 通过"
    curl -s http://localhost:8080/stats | jq .
else
    echo "健康检查: 失败"
fi

echo
echo "=== 最近错误日志 ==="
tail -20 logs/websocket-server.log | grep -E "(ERROR|CRITICAL|WARN)"

echo "=== 诊断完成 ==="
```

## 总结

故障排除是一个系统性的过程，需要：

1. **建立监控体系**: 实时监控关键指标
2. **制定应急预案**: 准备常见问题的解决方案
3. **定期健康检查**: 主动发现潜在问题
4. **持续优化改进**: 根据问题模式优化系统
5. **文档持续更新**: 记录新问题和解决方案

遇到问题时，按照系统性的排查流程，结合监控数据和日志分析，通常能够快速定位和解决问题。对于复杂问题，建议保留现场信息并寻求技术支持。