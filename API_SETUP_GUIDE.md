# API 配置指南

## 1. Tushare API 配置

### 1. 注册Tushare账号
1. 访问 [Tushare官网](https://tushare.pro/)
2. 注册账号并登录
3. 在个人中心获取你的API Token

### 2. 配置Token
在项目根目录的`.env`文件中设置：
```
TUSHARE_TOKEN=你的实际token
```

### 3. 测试连接
```bash
# 快速测试
python quick_test_tushare.py

# 完整测试
python test_tushare.py
```

## 验证数据源配置

### 启动服务验证
```bash
# 启动主服务
python main.py

# 访问API文档测试
# 浏览器打开 http://localhost:8000/docs
```

### 数据源状态检查
启动后通过API文档界面测试各数据源连接状态。

## 2. RQDatac API 配置

### 1. 注册RQDatac账号
1. 访问 [米筐官网](https://www.ricequant.com/)
2. 注册账号并登录
3. 获取数据权限

### 2. 配置用户名密码
在项目根目录的`.env`文件中设置：
```
RQDATAC_USERNAME=你的用户名
RQDATAC_PASSWORD=你的密码
```

### 3. 测试连接
```bash
# 快速测试
python quick_test_rqdatac.py

# 简化测试
python test_rqdatac_simple.py

# 完整测试
python test_rqdatac.py
```

## 测试脚本说明

### Tushare 测试脚本
- **`test_tushare.py`** - 完整测试
  - ✅ 基本连接测试
  - ✅ 股票基础信息获取
  - ✅ 日线数据获取
  - ✅ 指数数据获取
  - 📊 详细的数据展示和统计

- **`quick_test_tushare.py`** - 快速测试
  - 🔍 简单的连接验证
  - ⚡ 快速检查API是否可用

### RQDatac 测试脚本
- **`test_rqdatac.py`** - 完整测试
  - ✅ 基本信息和配额查询
  - ✅ 股票列表获取
  - ✅ 价格数据获取
  - ✅ 指数数据获取
  - ✅ 交易日历获取
  - ✅ 基本面数据获取

- **`quick_test_rqdatac.py`** - 快速测试
  - 🔍 简单的连接验证
  - ⚡ 快速检查API是否可用

- **`test_rqdatac_simple.py`** - 简化测试
  - 📈 核心功能测试
  - 🎯 专注于关键数据获取

### 综合测试
- **`test_all_apis.py`** - 一键测试所有API
  - 🚀 同时测试xtquant、Tushare、RQDatac
  - 📊 提供详细的可用性报告
  - 💡 给出使用建议

## 注意事项

### Tushare
1. **API限制**: 免费用户有调用频率限制
2. **数据延迟**: 免费版可能有数据延迟
3. **积分系统**: 部分高级数据需要积分

### RQDatac
1. **账号要求**: 需要有效的米筐账号
2. **数据权限**: 部分功能需要付费
3. **专业性**: 更适合专业量化研究

### xtquant
1. **客户端依赖**: 需要QMT客户端运行
2. **实时性**: 数据实时性好
3. **本地化**: 适合本地策略开发

## 常见问题

### Token/密码无效
- 检查配置是否正确复制
- 确认账号状态是否正常
- 验证网络连接

### 数据获取失败
- 检查API调用频率是否超限
- 确认请求的数据范围是否合理
- 查看具体错误信息

### 权限不足
- 某些数据需要VIP权限
- 检查账号等级和权限
- 考虑升级账号或使用其他数据源

## 数据源对比

| 数据源 | 优势 | 劣势 | 适用场景 |
|--------|------|------|----------|
| xtquant | 实时性好、本地化 | 需要QMT客户端 | 实时交易、本地策略 |
| Tushare | 数据全面、接口标准 | 有调用限制、部分收费 | 历史数据分析、回测 |
| RQDatac | 专业量化、数据质量高 | 需要付费、学习成本高 | 专业量化研究、机构级应用 |

建议根据具体需求选择合适的数据源，或者组合使用多个数据源以获得最佳效果。