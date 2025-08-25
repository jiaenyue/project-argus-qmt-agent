# Project Argus QMT Agent - Windows版本

> **专为Windows + MiniQMT环境优化的量化交易数据代理系统**

## 🎯 项目简介

Project Argus QMT Agent是一个专为**Windows平台**设计的量化交易数据代理系统，提供高性能、高可用的数据获取服务。与通用版本不同，本版本完全针对Windows + MiniQMT环境进行优化，无需Docker或Kubernetes，支持原生Windows服务部署。

## ✨ Windows特色功能

### 🔧 Windows原生支持
- **Windows服务**: 使用pywin32创建系统服务，支持开机自启动
- **MiniQMT集成**: 直接连接本地MiniQMT客户端，无需额外配置
- **任务计划**: 集成Windows任务计划程序，支持定时任务
- **通知系统**: Windows原生通知提醒

### ⚡ 性能优化
- **Windows内存优化**: 专为Windows内存管理优化
- **本地缓存**: 使用Windows文件系统缓存
- **MiniQMT直连**: 绕过网络延迟，本地极速访问
- **单机性能**: 单台Windows机器支持800+ QPS

### 🛡️ Windows安全
- **防火墙集成**: 自动配置Windows防火墙规则
- **服务权限**: 最小权限原则运行Windows服务
- **事件日志**: 集成Windows事件查看器
- **本地加密**: Windows原生加密存储敏感数据

## 🚀 快速开始 (Windows)

### 系统要求
- **操作系统**: Windows 10/11 (64位)
- **Python**: 3.11+ (Windows版)
- **MiniQMT**: 从券商官网下载最新版
- **Redis**: Windows版Redis (可选，用于缓存)

### 安装步骤

#### 1. 环境准备
```cmd
# 安装Python 3.11+ (Windows版)
# 下载地址: https://python.org/downloads/

# 安装MiniQMT客户端
# 从券商官网下载并安装MiniQMT

# 安装Redis (Windows版)
# 下载地址: https://github.com/tporadowski/redis/releases
```

#### 2. 项目部署
```cmd
# 克隆项目
git clone <repository-url>
cd project-argus-qmt-agent

# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.example .env
# 编辑.env文件，配置MiniQMT路径和参数
```

#### 3. 配置MiniQMT路径
编辑 `.env` 文件：
```env
# MiniQMT配置
MINIQMT_PATH=C:\Users\你的用户名\AppData\Local\MiniQMT\userdata_mini\
MINIQMT_ACCOUNT=你的账号
MINIQMT_PASSWORD=你的密码

# Redis配置 (可选)
REDIS_URL=redis://localhost:6379/0

# 服务配置
SERVICE_NAME=argus-qmt-agent
SERVICE_DISPLAY_NAME=Argus QMT Agent
SERVICE_DESCRIPTION=Windows量化交易数据代理服务
```

#### 4. 安装Windows服务
```cmd
# 安装服务
python service.py install

# 启动服务
net start argus-qmt-agent

# 查看服务状态
sc query argus-qmt-agent
```

#### 5. 验证安装
```cmd
# 测试API
curl http://localhost:8000/health

# 查看服务日志
eventvwr.msc  # 打开事件查看器
# 查看 "应用程序和服务日志" -> "Argus QMT Agent"
```

## 📊 API文档

### 基础API
- **健康检查**: `GET http://localhost:8000/health`
- **API文档**: `GET http://localhost:8000/docs`
- **数据状态**: `GET http://localhost:8000/status`

### 数据接口
```bash
# 获取股票列表
curl http://localhost:8000/api/stocks

# 获取K线数据
curl "http://localhost:8000/api/kline?symbol=000001&period=1d"

# 获取实时行情
curl http://localhost:8000/api/quote/000001

# WebSocket实时数据
# 连接: ws://localhost:8000/ws/quote/000001
```

## 🔧 Windows服务管理

### 常用命令
```cmd
# 安装服务
python service.py install

# 卸载服务
python service.py remove

# 启动服务
net start argus-qmt-agent

# 停止服务
net stop argus-qmt-agent

# 重启服务
net stop argus-qmt-agent && net start argus-qmt-agent

# 查看服务状态
sc query argus-qmt-agent

# 查看服务配置
sc qc argus-qmt-agent
```

### 任务计划程序
```cmd
# 创建定时任务 (例如每天9:30启动)
schtasks /create /tn "ArgusQMTDaily" /tr "net start argus-qmt-agent" /sc daily /st 09:30

# 删除定时任务
schtasks /delete /tn "ArgusQMTDaily" /f
```

## 📈 性能监控

### Windows性能计数器
```cmd
# 查看性能计数器
typeperf "\Process(argus-qmt-agent)\% Processor Time"
typeperf "\Process(argus-qmt-agent)\Working Set"

# 实时监控
perfmon  # 打开性能监视器
```

### 日志文件位置
- **服务日志**: `C:\ProgramData\argus-qmt-agent\logs\`
- **Windows事件日志**: 事件查看器 -> 应用程序 -> Argus QMT Agent
- **MiniQMT日志**: 与MiniQMT客户端日志集成

## 🛠️ 故障排除

### 常见问题

#### 1. 服务无法启动
```cmd
# 检查服务状态
sc query argus-qmt-agent

# 查看错误日志
eventvwr.msc

# 手动启动调试
python main.py --debug
```

#### 2. MiniQMT连接失败
- 确认MiniQMT客户端已启动
- 检查账号密码配置
- 验证MiniQMT路径配置

#### 3. 端口冲突
```cmd
# 检查端口占用
netstat -ano | findstr 8000
taskkill /PID <PID> /F  # 强制结束占用进程
```

#### 4. 权限问题
- 确保使用管理员权限运行
- 检查Windows防火墙设置
- 验证服务账户权限

### Windows特定调试
```cmd
# 服务调试模式
python service.py debug

# 查看Windows事件日志
wevtutil qe Application /q:"*[System[Provider[@Name='argus-qmt-agent']]]" /f:text

# 检查服务依赖
sc qc argus-qmt-agent
```

## 📋 系统要求

### 最低配置
- **操作系统**: Windows 10 64位
- **内存**: 2GB RAM
- **磁盘**: 500MB可用空间
- **网络**: 稳定的互联网连接

### 推荐配置
- **操作系统**: Windows 11 64位
- **内存**: 4GB RAM
- **磁盘**: 1GB可用空间 (含缓存)
- **CPU**: 4核心以上

### 支持券商
- **支持券商**: 所有支持MiniQMT的券商
- **常见券商**: 华泰证券、国泰君安、中信证券等
- **版本要求**: MiniQMT最新版本

## 📞 技术支持

### Windows技术支持
- **文档**: 查看 `docs/windows/` 目录
- **FAQ**: 查看 `docs/windows/FAQ.md`
- **Issues**: GitHub Issues (标记Windows标签)
- **社区**: Windows量化交易技术群

### 联系方式
- **邮件**: support@argus-qmt.com
- **QQ群**: 123456789 (Windows量化技术群)
- **微信群**: 扫码加入Windows量化交流群

## 📄 许可证

本项目采用MIT许可证，详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

感谢以下项目对Windows版本的支持：
- **pywin32**: Windows服务支持
- **xtquant**: MiniQMT数据接口
- **Redis for Windows**: Windows版Redis
- **Windows社区**: 提供测试和反馈

---

**注意**: 本版本专为Windows + MiniQMT环境设计，不支持Linux/macOS或Docker部署。如需跨平台版本，请查看项目主分支。