# Project Argus QMT Data Agent - 部署运维指南

## 1. 系统要求

### 1.1 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 2核心 | 4核心+ |
| 内存 | 4GB | 8GB+ |
| 存储 | 20GB可用空间 | 50GB+ SSD |
| 网络 | 100Mbps | 1Gbps+ |

### 1.2 软件要求

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| 操作系统 | Windows 10/11 或 Windows Server 2019+ | 必须是Windows环境 |
| Python | 3.10.18 (推荐使用Conda环境管理) | Conda 环境: qmt_py310 |
| miniQMT客户端 | 最新版本 | 迅投量化交易客户端 |
| xtquant库 | 最新版本 | miniQMT Python SDK |
| Node.js | 18+ | MCP功能需要 |

### 1.3 网络要求

- **出站连接**: 需要访问证券交易所数据源
- **入站连接**: API服务端口（默认8000）
- **防火墙**: 允许Python应用网络访问
- **代理设置**: 如有企业代理，需要配置相应设置

## 2. 安装部署

### 2.1 环境准备

#### 步骤1: 安装Python环境
```bash
# 激活Conda环境 (推荐)
conda activate qmt_py310

# 或使用批处理脚本
activate_env.bat

# 验证Python版本和环境
python --version
conda info --envs

# 备选方案 - 虚拟环境 (不推荐)
python -m venv qmt_env
qmt_env\Scripts\activate
```

#### 步骤2: 安装miniQMT客户端
1. 从迅投官网下载miniQMT客户端
2. 按照官方指南完成安装和配置
3. 确保客户端能正常连接和获取数据
4. 安装xtquant Python库

#### 步骤3: 克隆项目代码
```bash
git clone <项目仓库地址>
cd project-argus-qmt-agent
```

### 2.2 依赖安装

#### 安装Python依赖
```bash
# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate

# 安装项目依赖
pip install -r requirements.txt

# 验证关键依赖
python -c "import xtquant; print('xtquant installed successfully')"
python -c "import fastapi; print('FastAPI installed successfully')"
```

#### 安装Node.js依赖（MCP功能）
```bash
# 安装Node.js（如果未安装）
# 从 https://nodejs.org 下载并安装

# 验证安装
node --version
npm --version

# 安装MCP相关依赖
npm install -g @modelcontextprotocol/inspector
```

### 2.3 配置文件设置

#### 创建配置文件
```bash
# 复制配置模板
cp config.example.json config.json
```

#### 配置示例 (config.json)
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": false
  },
  "xtquant": {
    "timeout": 30,
    "retry_count": 3
  },
  "logging": {
    "level": "INFO",
    "file": "logs/app.log",
    "max_size": "10MB",
    "backup_count": 5
  },
  "mcp": {
    "enabled": true,
    "port": 3000
  }
}
```

## 3. 服务启动

### 3.1 开发模式启动

#### 启动API服务
```bash
# 激活虚拟环境
venv\Scripts\activate

# 启动FastAPI服务
python main.py direct

# 或者使用uvicorn直接启动
uvicorn data_agent_service.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 启动MCP服务
```bash
# 在新的命令行窗口中
python main.py inspector
```

### 3.2 生产模式部署

#### 使用NSSM部署为Windows服务

1. **下载NSSM**
```bash
# 从 https://nssm.cc/download 下载NSSM
# 解压到系统目录或添加到PATH
```

2. **创建服务脚本** (start_service.bat)
```batch
@echo off
cd /d "D:\Stocks\project-argus-qmt-agent"
venv\Scripts\activate
python main.py direct
```

3. **安装Windows服务**
```bash
# 以管理员身份运行命令提示符
nssm install "ArgusQMTDataAgent" "D:\Stocks\project-argus-qmt-agent\start_service.bat"

# 配置服务
nssm set "ArgusQMTDataAgent" DisplayName "Argus QMT Data Agent"
nssm set "ArgusQMTDataAgent" Description "QMT数据代理服务"
nssm set "ArgusQMTDataAgent" Start SERVICE_AUTO_START

# 启动服务
nssm start "ArgusQMTDataAgent"
```

4. **服务管理命令**
```bash
# 查看服务状态
nssm status "ArgusQMTDataAgent"

# 停止服务
nssm stop "ArgusQMTDataAgent"

# 重启服务
nssm restart "ArgusQMTDataAgent"

# 卸载服务
nssm remove "ArgusQMTDataAgent" confirm
```



## 4. 监控和维护

### 4.1 健康检查

#### API健康检查
```bash
# 检查服务状态
curl http://localhost:8000/health

# 检查API文档
curl http://localhost:8000/docs

# 测试核心API
curl "http://localhost:8000/api/v1/get_trading_dates?market=SH&count=5"
```

#### 系统资源监控
```powershell
# 检查进程状态
Get-Process python

# 检查端口占用
netstat -an | findstr :8000

# 检查内存使用
Get-Process python | Select-Object ProcessName, WorkingSet, CPU
```

### 4.2 日志管理

#### 日志文件位置
```
logs/
├── app.log              # 应用主日志
├── error.log            # 错误日志
├── access.log           # 访问日志
└── performance.log      # 性能日志
```

#### 日志查看命令
```bash
# 查看最新日志
tail -f logs/app.log

# 查看错误日志
findstr "ERROR" logs/app.log

# 查看特定时间段日志
findstr "2025-01-" logs/app.log
```

#### 日志轮转配置
```python
# 在logging配置中设置
"handlers": {
    "file": {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": "logs/app.log",
        "maxBytes": 10485760,  # 10MB
        "backupCount": 5
    }
}
```

### 4.3 性能监控

#### 关键指标监控

1. **响应时间监控**
```python
# 在API中添加性能监控
import time
from functools import wraps

def monitor_performance(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"{func.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return wrapper
```

2. **系统资源监控脚本**
```python
# monitor.py
import psutil
import time
import logging

def monitor_system():
    while True:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        logging.info(f"CPU: {cpu_percent}%, Memory: {memory.percent}%, Disk: {disk.percent}%")
        time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    monitor_system()
```

### 4.4 备份和恢复

#### 数据备份策略
```bash
# 创建备份脚本 backup.bat
@echo off
set BACKUP_DIR=D:\Backups\argus-qmt-agent\%date:~0,4%%date:~5,2%%date:~8,2%
mkdir "%BACKUP_DIR%"

# 备份配置文件
copy config.json "%BACKUP_DIR%\"

# 备份日志文件
xcopy logs "%BACKUP_DIR%\logs\" /E /I

# 备份代码（如有本地修改）
xcopy src "%BACKUP_DIR%\src\" /E /I

echo Backup completed to %BACKUP_DIR%
```

#### 恢复流程
1. 停止服务
2. 恢复配置文件
3. 重新安装依赖
4. 启动服务
5. 验证功能

## 5. 故障排查

### 5.1 常见问题

#### 问题1: 服务启动失败
**症状**: Python进程无法启动或立即退出

**排查步骤**:
```bash
# 检查Python环境
python --version

# 检查依赖安装
pip list | findstr fastapi
pip list | findstr xtquant

# 检查配置文件
python -c "import json; print(json.load(open('config.json')))"

# 查看详细错误
python main.py direct --debug
```

**解决方案**:
- 重新安装Python依赖
- 检查配置文件格式
- 确认miniQMT客户端正常运行

#### 问题2: API请求超时
**症状**: 客户端请求返回超时错误

**排查步骤**:
```bash
# 检查服务状态
curl http://localhost:8000/health

# 检查miniQMT连接
python -c "import xtquant; print(xtquant.get_trading_dates('SH', count=1))"

# 检查网络连接
ping 数据源服务器IP
```

**解决方案**:
- 增加超时时间配置
- 检查miniQMT客户端状态
- 验证网络连接

#### 问题3: 内存使用过高
**症状**: 系统内存占用持续增长

**排查步骤**:
```bash
# 监控内存使用
Get-Process python | Select-Object ProcessName, WorkingSet

# 检查日志文件大小
dir logs

# 分析内存泄漏
python -m memory_profiler main.py
```

**解决方案**:
- 实现数据缓存清理
- 配置日志轮转
- 重启服务释放内存

### 5.2 性能优化

#### 数据库连接优化
```python
# 实现连接池
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "sqlite:///data.db",
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

#### 缓存机制
```python
# 使用本地内存缓存
from functools import wraps
from cachetools import TTLCache
import json
import time

# 创建TTL缓存实例
cache = TTLCache(maxsize=1000, ttl=300)  # 最大1000项，5分钟过期

def cache_result(expire_time=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            if cache_key in cache:
                return cache[cache_key]
            
            result = func(*args, **kwargs)
            cache[cache_key] = result
            return result
        return wrapper
    return decorator
```

## 6. 安全配置

### 6.1 API安全

#### 实现API Key认证
```python
# security.py
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer

security = HTTPBearer()

def verify_api_key(token: str = Depends(security)):
    if token.credentials != "your-secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
    return token.credentials

# 在API路由中使用
@app.get("/api/v1/protected")
async def protected_endpoint(api_key: str = Depends(verify_api_key)):
    return {"message": "Access granted"}
```

#### HTTPS配置
```bash
# 生成自签名证书（开发环境）
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# 启动HTTPS服务
uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem
```

### 6.2 防火墙配置

```bash
# Windows防火墙规则
netsh advfirewall firewall add rule name="Argus QMT API" dir=in action=allow protocol=TCP localport=8000

# 限制访问IP（可选）
netsh advfirewall firewall add rule name="Argus QMT API Restricted" dir=in action=allow protocol=TCP localport=8000 remoteip=192.168.1.0/24
```

## 7. 升级和维护

### 7.1 版本升级流程

1. **备份当前环境**
2. **下载新版本代码**
3. **更新依赖包**
4. **迁移配置文件**
5. **测试新功能**
6. **部署到生产环境**

### 7.2 定期维护任务

#### 每日维护
- 检查服务状态
- 查看错误日志
- 监控系统资源

#### 每周维护
- 清理日志文件
- 检查磁盘空间
- 更新安全补丁

#### 每月维护
- 性能评估
- 备份验证
- 依赖包更新

### 7.3 监控告警设置

```python
# alert.py - 简单的告警脚本
import smtplib
from email.mime.text import MIMEText
import psutil

def send_alert(subject, message):
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = 'alert@company.com'
    msg['To'] = 'admin@company.com'
    
    server = smtplib.SMTP('smtp.company.com', 587)
    server.starttls()
    server.login('alert@company.com', 'password')
    server.send_message(msg)
    server.quit()

def check_system_health():
    # 检查CPU使用率
    if psutil.cpu_percent() > 80:
        send_alert("High CPU Usage", f"CPU usage is {psutil.cpu_percent()}%")
    
    # 检查内存使用率
    memory = psutil.virtual_memory()
    if memory.percent > 85:
        send_alert("High Memory Usage", f"Memory usage is {memory.percent}%")
    
    # 检查磁盘空间
    disk = psutil.disk_usage('/')
    if disk.percent > 90:
        send_alert("Low Disk Space", f"Disk usage is {disk.percent}%")

if __name__ == "__main__":
    check_system_health()
```

通过以上部署运维指南，您可以成功部署和维护Project Argus QMT Data Agent服务，确保系统的稳定运行和高可用性。