"""
应用启动和关闭事件处理模块
"""

import time
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .health_check import health_checker
from .database_query_optimizer import get_global_query_optimizer
from .performance_monitor import get_global_performance_monitor
from .data_storage_service import get_data_storage_service, shutdown_data_storage_service
from .xtquant_connection_pool import get_connection_pool

logger = logging.getLogger(__name__)

# 可选增强功能模块
try:
    from ..src.argus_mcp.advanced_cache_optimizer import get_cache_optimizer
except Exception:
    get_cache_optimizer = None

try:
    from ..src.argus_mcp.enhanced_market_data_processor import init_market_data_processor
except Exception:
    init_market_data_processor = None

try:
    from ..src.argus_mcp.intelligent_connection_pool import get_pool_manager, PoolConfiguration
except Exception:
    get_pool_manager = None
    PoolConfiguration = None


def setup_startup_shutdown_events(app: FastAPI):
    """设置应用启动和关闭事件"""
    
    @app.on_event("startup")
    async def startup_event():
        """应用启动事件"""
        start_time = time.time()
        logger.info("Starting QMT Data Agent API...")
        
        try:
            # 设置健康检查器的启动时间
            health_checker.set_start_time(start_time)
            
            # 启动查询优化器
            logger.info("Starting query optimizer...")
            query_optimizer = get_global_query_optimizer()
            await query_optimizer.start()
            
            # 启动性能监控器
            logger.info("Starting performance monitor...")
            performance_monitor = get_global_performance_monitor()
            performance_monitor.start()
            
            # 启动数据存储服务
            logger.info("Starting data storage service...")
            data_storage_service = get_data_storage_service()
            # 数据存储服务不需要显式启动
            
            # 初始化连接池
            logger.info("Initializing connection pool...")
            connection_pool = get_connection_pool()
            # 连接池在构造函数中已经初始化，无需额外调用initialize
            
            # 初始化缓存管理器
            logger.info("Initializing cache manager...")
            from .cache_manager import init_cache_manager
            cache_manager = await init_cache_manager()
            
            # 初始化增强功能
            if get_cache_optimizer or init_market_data_processor or get_pool_manager:
                logger.info("Initializing enhanced features...")
                
                # 初始化高级缓存优化器
                advanced_cache_optimizer = None
                if get_cache_optimizer:
                    try:
                        logger.info("Initializing advanced cache optimizer...")
                        advanced_cache_optimizer = get_cache_optimizer()
                        await advanced_cache_optimizer.initialize()
                    except Exception as e:
                        logger.warning(f"Failed to initialize advanced cache optimizer: {e}")
                
                # 初始化增强的市场数据处理器
                if init_market_data_processor:
                    try:
                        logger.info("Initializing enhanced market data processor...")
                        enhanced_market_processor = await init_market_data_processor(
                            cache_optimizer=advanced_cache_optimizer
                        )
                    except Exception as e:
                        logger.warning(f"Failed to initialize enhanced market data processor: {e}")
                
                # 初始化智能连接池管理器
                if get_pool_manager and PoolConfiguration:
                    try:
                        logger.info("Initializing intelligent connection pool manager...")
                        intelligent_pool_manager = get_pool_manager()
                        
                        # 创建默认连接池
                        async def mock_connection_factory():
                            """模拟连接工厂"""
                            return {"connection": "mock_connection", "created_at": time.time()}
                        
                        default_config = PoolConfiguration(
                            min_connections=3,
                            max_connections=20,
                            enable_auto_scaling=True,
                            enable_health_check=True
                        )
                        
                        await intelligent_pool_manager.create_pool(
                            pool_name="default",
                            connection_factory=mock_connection_factory,
                            config=default_config
                        )
                        
                    except Exception as e:
                        logger.warning(f"Failed to initialize intelligent connection pool manager: {e}")
                
                logger.info("Enhanced features initialization completed")
            else:
                logger.info("No enhanced features available")
            
            # 等待一小段时间确保所有服务都已启动
            await asyncio.sleep(1)
            
            startup_duration = time.time() - start_time
            logger.info(f"QMT Data Agent API started successfully in {startup_duration:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Failed to start application: {str(e)}", exc_info=True)
            raise e
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭事件"""
        logger.info("Shutting down QMT Data Agent API...")
        
        try:
            # 关闭数据存储服务
            logger.info("Stopping data storage service...")
            shutdown_data_storage_service()
            
            # 关闭性能监控器
            logger.info("Stopping performance monitor...")
            from .performance_monitor import shutdown_global_performance_monitor
            shutdown_global_performance_monitor()
            
            # 关闭查询优化器
            logger.info("Stopping query optimizer...")
            from .database_query_optimizer import shutdown_global_query_optimizer
            await shutdown_global_query_optimizer()
            
            # 关闭缓存管理器
            logger.info("Stopping cache manager...")
            from .cache_manager import shutdown_cache_manager
            await shutdown_cache_manager()
            
            # 关闭连接池
            logger.info("Closing connection pool...")
            from .xtquant_connection_pool import shutdown_connection_pool
            shutdown_connection_pool()
            
            # 关闭增强功能
            if get_pool_manager or get_cache_optimizer:
                logger.info("Shutting down enhanced features...")
                
                # 关闭智能连接池管理器
                if get_pool_manager:
                    try:
                        logger.info("Shutting down intelligent connection pool manager...")
                        intelligent_pool_manager = get_pool_manager()
                        await intelligent_pool_manager.shutdown_all()
                    except Exception as e:
                        logger.warning(f"Error shutting down intelligent connection pool manager: {e}")
                
                # 关闭高级缓存优化器
                if get_cache_optimizer:
                    try:
                        logger.info("Shutting down advanced cache optimizer...")
                        advanced_cache_optimizer = get_cache_optimizer()
                        await advanced_cache_optimizer.shutdown()
                    except Exception as e:
                        logger.warning(f"Error shutting down advanced cache optimizer: {e}")
                
                logger.info("Enhanced features shutdown completed")
            
            logger.info("QMT Data Agent API shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)