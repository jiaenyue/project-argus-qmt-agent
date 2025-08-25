"""
独立的简化启动文件
不依赖复杂的中间件和启动事件
"""

import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用实例
app = FastAPI(
    title="Data Agent Service",
    description="QMT数据代理服务",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock缓存数据
mock_cache_data = {
    "trading_dates": ["2024-01-01", "2024-01-02", "2024-01-03"],
    "stock_list": ["000001.SZ", "000002.SZ", "600000.SH"],
    "market_data": {"000001.SZ": {"price": 10.25, "volume": 1000000}}
}

@app.get("/")
async def root():
    """根路径"""
    return {"message": "Data Agent Service is running", "status": "ok"}

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "service": "data_agent_service",
        "version": "1.0.0"
    }

@app.get("/cache/stats")
async def get_cache_stats(api_key: str = "demo_key_123"):
    """获取缓存统计信息"""
    if api_key != "demo_key_123":
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "total_keys": len(mock_cache_data),
            "memory_usage": "10MB",
            "hit_rate": 85.5,
            "last_updated": "2024-01-01T00:00:00Z"
        }
    }

@app.post("/cache/clear")
async def clear_cache(api_key: str = "demo_key_123", pattern: str = None):
    """清理缓存"""
    if api_key != "demo_key_123":
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if pattern:
        # 模拟按模式清理
        cleared_keys = [key for key in mock_cache_data.keys() if pattern in key]
    else:
        # 清理所有
        cleared_keys = list(mock_cache_data.keys())
        mock_cache_data.clear()
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "cleared_keys": cleared_keys,
            "cleared_count": len(cleared_keys)
        }
    }

@app.get("/cache/keys")
async def get_cache_keys(api_key: str = "demo_key_123"):
    """获取缓存键列表"""
    if api_key != "demo_key_123":
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "keys": list(mock_cache_data.keys()),
            "count": len(mock_cache_data)
        }
    }

@app.get("/cache/warmup/status")
async def get_warmup_status(api_key: str = "demo_key_123"):
    """获取缓存预热状态"""
    if api_key != "demo_key_123":
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "status": "running",
            "progress": 75.5,
            "last_warmup": "2024-01-01T00:00:00Z",
            "next_warmup": "2024-01-01T01:00:00Z"
        }
    }

@app.post("/cache/warmup/start")
async def start_warmup(api_key: str = "demo_key_123"):
    """启动缓存预热"""
    if api_key != "demo_key_123":
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "status": "started",
            "estimated_duration": "5 minutes",
            "start_time": "2024-01-01T00:00:00Z"
        }
    }

def main():
    """主函数"""
    try:
        logger.info("数据代理服务启动成功")
        
        # 启动服务器
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8003,
            log_level="info",
            access_log=True,
            reload=False
        )
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise

if __name__ == "__main__":
    main()