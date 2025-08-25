# QMT Setup Guide for xtquant Integration

## Current Status
- ✅ QMT is installed at: `G:\Stock\GJ_QMT`
- ✅ QMT processes are running (XtMiniQmt.exe, miniquote.exe)
- ❌ QMT API service is not listening on expected ports
- ❌ xtquant cannot connect to QMT service

## Steps to Fix

### 1. Manual Login Required
You need to manually open and log into QMT:

1. Open QMT application (it should already be running)
2. Look for the QMT window in your taskbar or system tray
3. Log in with your trading account credentials
4. Wait for the application to fully load

### 2. Enable API Service (if needed)
Some QMT installations require enabling the API service:

1. In QMT, look for settings or preferences
2. Find "API" or "接口" settings
3. Enable the xtquant API service
4. The default ports should be 58610-58615

### 3. 验证QMT连接
启动服务验证QMT连接：

```bash
# 启动主服务
python main.py

# 服务启动后，通过API测试QMT连接
# 访问 http://localhost:8000/docs
# 测试 /health 端点查看QMT连接状态
```

如果服务正常启动且QMT连接成功，健康检查将显示QMT状态为"healthy"。

### 4. Common Issues

**Issue**: "无法连接xtquant服务"
**Solution**: 
- Ensure QMT is logged in (not just running)
- Check if API service is enabled in QMT settings
- Restart QMT if needed

**Issue**: Ports not listening
**Solution**:
- Wait 1-2 minutes after login for services to start
- Check Windows firewall isn't blocking the ports
- Verify QMT version supports xtquant API

### 5. Test Your Setup
Once logged in, your trading dates code should work:

```python
import time
from xtquant import xtdata

# This should work after proper login
dates = xtdata.get_trading_dates(
    market="SH", 
    start_time="20240101", 
    end_time="20241231",
    count=-1
)

def convert_timestamp(ts):
    return time.strftime("%Y%m%d", time.localtime(ts / 1000))

trading_dates = [convert_timestamp(ts) for ts in dates]
print("2024年上交所交易日历：", trading_dates)
```

## Next Steps
1. Log into QMT manually
2. Run `python qmt_diagnostic.py` to verify ports are listening
3. Run `python test_qmt_connection.py` to test the connection
4. If successful, your original trading dates code should work