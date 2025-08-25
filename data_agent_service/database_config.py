#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库配置模块
包含连接池配置、分区策略、性能优化等设置
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from contextlib import contextmanager
import logging
from datetime import datetime, timedelta

# 使用相对导入，避免绝对导入问题
try:
    from .exception_handler import safe_execute
except ImportError:
    def safe_execute(func):
        return func

try:
    from .connection_pool_optimizer import (
        ConnectionPoolManager, 
        PoolConfiguration, 
        get_connection_pool_manager
    )
except ImportError:
    # 提供默认实现
    class PoolConfiguration:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class ConnectionPoolManager:
        def __init__(self, url, config):
            self.url = url
            self.config = config
            self._engine = None
        
        def initialize(self):
            pass
        
        def get_engine(self):
            if self._engine is None:
                self._engine = create_engine(
                    self.url,
                    poolclass=QueuePool,
                    pool_size=getattr(self.config, 'pool_size', 20),
                    max_overflow=getattr(self.config, 'max_overflow', 30),
                    pool_timeout=getattr(self.config, 'pool_timeout', 30),
                    pool_recycle=getattr(self.config, 'pool_recycle', 3600),
                    pool_pre_ping=getattr(self.config, 'pool_pre_ping', True)
                )
            return self._engine
    
    def get_connection_pool_manager(url, config):
        return ConnectionPoolManager(url, config)

try:
    from .database_performance_optimizer import get_database_performance_optimizer
except ImportError:
    def get_database_performance_optimizer():
        class DummyOptimizer:
            async def analyze_performance(self):
                return {}
            async def optimize_database(self, auto_create_indexes=True):
                return {}
            def get_performance_report(self):
                return {}
        return DummyOptimizer()

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """数据库配置类"""
    # 基本连接配置
    host: str = "localhost"
    port: int = 5432
    database: str = "argus_qmt"
    username: str = "postgres"
    password: str = ""
    
    # 连接池配置
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    
    # 性能配置
    echo: bool = False
    echo_pool: bool = False
    isolation_level: str = "READ_COMMITTED"
    
    # 分区配置
    enable_partitioning: bool = True
    partition_by_date: bool = True
    partition_by_symbol: bool = False
    partition_retention_days: int = 365
    
    # 压缩配置
    enable_compression: bool = True
    compression_threshold_days: int = 30
    compression_algorithm: str = "gzip"
    
    # 备份配置
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    backup_retention_days: int = 30
    backup_path: str = "./backups"
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """从环境变量创建配置"""
        return cls(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'argus_qmt'),
            username=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            pool_size=int(os.getenv('DB_POOL_SIZE', '20')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '30')),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
            echo=os.getenv('DB_ECHO', 'false').lower() == 'true',
            enable_partitioning=os.getenv('DB_ENABLE_PARTITIONING', 'true').lower() == 'true',
            enable_compression=os.getenv('DB_ENABLE_COMPRESSION', 'true').lower() == 'true',
        )
    
    def get_database_url(self, async_driver: bool = False) -> str:
        """获取数据库连接URL"""
        driver = "postgresql+asyncpg" if async_driver else "postgresql+psycopg2"
        return f"{driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self.pool_manager: Optional[ConnectionPoolManager] = None
        self._initialized = False
        self._setup_engine()
        
        logger.info("数据库管理器已创建")
    
    def _setup_engine(self):
        """设置数据库引擎"""
        if self._initialized:
            return
        
        try:
            # 构建数据库URL
            database_url = self.config.get_database_url()
            
            # 创建连接池配置
            pool_config = PoolConfiguration(
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=self.config.pool_pre_ping,
                auto_tune=True,  # 启用自动调优
                min_pool_size=max(2, self.config.pool_size // 2),
                max_pool_size=min(50, self.config.pool_size * 2)
            )
            
            # 创建连接池管理器
            self.pool_manager = get_connection_pool_manager(database_url, pool_config)
            self.pool_manager.initialize()
            
            # 获取引擎
            self._engine = self.pool_manager.get_engine()
            
            # 创建会话工厂
            self._session_factory = sessionmaker(
                bind=self._engine,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            # 设置事件监听器
            self._setup_event_listeners()
            
            # 初始化性能优化器
            performance_optimizer = get_database_performance_optimizer()
            
            self._initialized = True
            logger.info(f"数据库引擎已创建: {self.config.host}:{self.config.port}/{self.config.database}")
            
        except Exception as e:
            logger.error(f"初始化数据库连接失败: {e}")
            raise
    
    def _setup_event_listeners(self):
        """设置事件监听器"""
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """连接时设置数据库参数"""
            if 'postgresql' in str(dbapi_connection):
                # PostgreSQL优化设置
                cursor = dbapi_connection.cursor()
                cursor.execute("SET statement_timeout = '300s'")
                cursor.execute("SET lock_timeout = '30s'")
                cursor.execute("SET idle_in_transaction_session_timeout = '600s'")
                cursor.close()
        
        @event.listens_for(self._engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """执行前记录SQL"""
            if self.config.echo:
                logger.debug(f"执行SQL: {statement[:200]}...")
        
        @event.listens_for(self._engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """执行后记录性能"""
            if hasattr(context, '_query_start_time'):
                duration = datetime.now() - context._query_start_time
                if duration.total_seconds() > 1.0:  # 记录慢查询
                    logger.warning(f"慢查询检测: {duration.total_seconds():.2f}s - {statement[:100]}...")
    
    @property
    def engine(self) -> Engine:
        """获取数据库引擎"""
        if self._engine is None:
            raise RuntimeError("数据库引擎未初始化")
        return self._engine
    
    @contextmanager
    def get_session(self):
        """获取数据库会话上下文管理器"""
        if self._session_factory is None:
            raise RuntimeError("会话工厂未初始化")
        
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库会话错误: {e}")
            raise
        finally:
            session.close()
    
    def create_session(self) -> Session:
        """创建新的数据库会话"""
        if self._session_factory is None:
            raise RuntimeError("会话工厂未初始化")
        return self._session_factory()
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            logger.info("数据库连接测试成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        if not self._initialized or not self._engine:
            return {"status": "not_initialized"}
        
        try:
            # 获取基础连接信息
            pool = self._engine.pool
            basic_info = {
                'pool_size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'invalid': pool.invalid(),
                'url': str(self._engine.url).replace(self.config.password, '***'),
                'dialect': str(self._engine.dialect.name),
                "status": "connected"
            }
            
            # 获取详细的连接池状态
            if self.pool_manager:
                pool_status = self.pool_manager.get_pool_status()
                basic_info.update({
                    "detailed_status": pool_status,
                    "pool_health": pool_status.get('health_status', {})
                })
            
            return basic_info
            
        except Exception as e:
            logger.error(f"获取连接信息失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def optimize_performance(self) -> Dict[str, Any]:
        """优化数据库性能"""
        if not self._initialized:
            return {"status": "not_initialized"}
        
        try:
            results = {}
            
            # 连接池优化
            if self.pool_manager:
                pool_optimization = await self.pool_manager.optimize_pool()
                results['pool_optimization'] = pool_optimization
            
            # 性能分析和优化
            performance_optimizer = get_database_performance_optimizer()
            performance_analysis = await performance_optimizer.analyze_performance()
            results['performance_analysis'] = performance_analysis
            
            # 数据库优化
            db_optimization = await performance_optimizer.optimize_database(auto_create_indexes=True)
            results['database_optimization'] = db_optimization
            
            return results
            
        except Exception as e:
            logger.error(f"数据库性能优化失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        if not self._initialized:
            return {"status": "not_initialized"}
        
        try:
            performance_optimizer = get_database_performance_optimizer()
            return performance_optimizer.get_performance_report()
        except Exception as e:
            logger.error(f"获取性能报告失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def close(self):
        """关闭数据库连接"""
        try:
            if self.pool_manager:
                self.pool_manager.cleanup()
            
            if self._engine:
                self._engine.dispose()
                logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"清理数据库连接失败: {e}")
        finally:
            self._initialized = False

class PartitionManager:
    """分区管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.config = db_manager.config
    
    def create_partition_sql(self, table_name: str, partition_name: str, 
                           start_date: str, end_date: str) -> str:
        """生成创建分区的SQL"""
        return f"""
        CREATE TABLE IF NOT EXISTS {partition_name} 
        PARTITION OF {table_name}
        FOR VALUES FROM ('{start_date}') TO ('{end_date}');
        
        CREATE INDEX IF NOT EXISTS idx_{partition_name}_trade_date 
        ON {partition_name} (trade_date);
        
        CREATE INDEX IF NOT EXISTS idx_{partition_name}_symbol 
        ON {partition_name} (symbol);
        """
    
    def create_monthly_partitions(self, table_name: str, start_date: datetime, 
                                months: int = 12) -> List[str]:
        """创建月度分区"""
        partitions = []
        current_date = start_date.replace(day=1)
        
        for i in range(months):
            # 计算分区范围
            partition_start = current_date
            if current_date.month == 12:
                partition_end = current_date.replace(year=current_date.year + 1, month=1)
            else:
                partition_end = current_date.replace(month=current_date.month + 1)
            
            # 生成分区名称
            partition_name = f"{table_name}_p_{partition_start.strftime('%Y%m')}"
            
            # 创建分区SQL
            sql = self.create_partition_sql(
                table_name, partition_name,
                partition_start.strftime('%Y-%m-%d'),
                partition_end.strftime('%Y-%m-%d')
            )
            
            try:
                with self.db_manager.get_session() as session:
                    session.execute(sql)
                partitions.append(partition_name)
                logger.info(f"创建分区成功: {partition_name}")
            except Exception as e:
                logger.error(f"创建分区失败 {partition_name}: {e}")
            
            current_date = partition_end
        
        return partitions
    
    def drop_old_partitions(self, table_name: str, retention_days: int = None) -> List[str]:
        """删除过期分区"""
        if retention_days is None:
            retention_days = self.config.partition_retention_days
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        dropped_partitions = []
        
        # 查询过期分区
        sql = f"""
        SELECT schemaname, tablename 
        FROM pg_tables 
        WHERE tablename LIKE '{table_name}_p_%' 
        AND tablename < '{table_name}_p_{cutoff_date.strftime('%Y%m')}'
        """
        
        try:
            with self.db_manager.get_session() as session:
                result = session.execute(sql)
                for row in result:
                    partition_name = row[1]
                    drop_sql = f"DROP TABLE IF EXISTS {partition_name}"
                    session.execute(drop_sql)
                    dropped_partitions.append(partition_name)
                    logger.info(f"删除过期分区: {partition_name}")
        except Exception as e:
            logger.error(f"删除过期分区失败: {e}")
        
        return dropped_partitions
    
    def get_partition_info(self, table_name: str) -> List[Dict[str, Any]]:
        """获取分区信息"""
        sql = f"""
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
            pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
        FROM pg_tables 
        WHERE tablename LIKE '{table_name}_p_%'
        ORDER BY tablename
        """
        
        partitions = []
        try:
            with self.db_manager.get_session() as session:
                result = session.execute(sql)
                for row in result:
                    partitions.append({
                        'schema': row[0],
                        'name': row[1],
                        'size': row[2],
                        'size_bytes': row[3]
                    })
        except Exception as e:
            logger.error(f"获取分区信息失败: {e}")
        
        return partitions

# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None
_partition_manager: Optional[PartitionManager] = None

def get_database_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        config = DatabaseConfig.from_env()
        _db_manager = DatabaseManager(config)
    return _db_manager

def get_partition_manager() -> PartitionManager:
    """获取全局分区管理器实例"""
    global _partition_manager
    if _partition_manager is None:
        db_manager = get_database_manager()
        _partition_manager = PartitionManager(db_manager)
    return _partition_manager

def init_database():
    """初始化数据库"""
    try:
        from .database_models import Base
    except ImportError:
        from .database_models import Base
    
    db_manager = get_database_manager()
    
    # 测试连接
    if not db_manager.test_connection():
        raise RuntimeError("数据库连接失败")
    
    # 创建表结构
    Base.metadata.create_all(db_manager.engine)
    logger.info("数据库表结构创建完成")
    
    # 创建分区（如果启用）
    if db_manager.config.enable_partitioning:
        partition_manager = get_partition_manager()
        
        # 为主要表创建分区
        tables_to_partition = ['market_data', 'kline_data']
        start_date = datetime.now().replace(day=1) - timedelta(days=365)
        
        for table_name in tables_to_partition:
            try:
                partitions = partition_manager.create_monthly_partitions(
                    table_name, start_date, months=24
                )
                logger.info(f"为表 {table_name} 创建了 {len(partitions)} 个分区")
            except Exception as e:
                logger.error(f"为表 {table_name} 创建分区失败: {e}")
    
    logger.info("数据库初始化完成")

def cleanup_database():
    """清理数据库资源"""
    global _db_manager, _partition_manager
    
    if _db_manager:
        _db_manager.close()
        _db_manager = None
    
    _partition_manager = None
    logger.info("数据库资源清理完成")