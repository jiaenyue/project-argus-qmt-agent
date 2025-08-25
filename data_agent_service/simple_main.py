"""
简化的主应用入口文件
避免复杂的相对导入问题
"""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# ---------------- 新增：挂载增强功能路由 ----------------
try:
    # 直接挂载增强功能API端点（包含 /enhanced/health 等）
    from .api_endpoints.enhanced_features_endpoints import router as enhanced_features_router
    app.include_router(enhanced_features_router)
    logger.info("增强功能API端点已加载 (simple_main)")
except Exception as e:
    logger.warning(f"增强功能API端点加载失败 (simple_main): {e}")
# ------------------------------------------------------

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

@app.get("/cache/keys")
async def get_cache_keys(api_key: str = "demo_key_123"):
    """获取缓存键列表"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "keys": ["trading_dates", "stock_list", "market_data"],
            "count": 3
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
            port=8001,
            log_level="info",
            access_log=True,
            reload=False
        )
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise

if __name__ == "__main__":
    main()