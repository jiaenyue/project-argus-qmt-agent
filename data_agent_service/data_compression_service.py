"""数据压缩和归档服务

实现数据压缩、归档和清理功能，优化存储空间使用。
"""

import logging
import gzip
import lzma
import zlib
import pickle
import json
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from pathlib import Path
import os
from sqlalchemy import text, and_, or_
from sqlalchemy.orm import Session

from .database_config import get_database_manager
from .database_models import (
    DataBackup, DataPartition, DataQualityMetrics, SystemMetrics
)
from .exception_handler import safe_execute

logger = logging.getLogger(__name__)

class CompressionAlgorithm(Enum):
    """压缩算法枚举"""
    GZIP = "gzip"
    LZMA = "lzma"
    ZLIB = "zlib"
    NONE = "none"

class ArchiveStatus(Enum):
    """归档状态枚举"""
    ACTIVE = "active"
    COMPRESSED = "compressed"
    ARCHIVED = "archived"
    DELETED = "deleted"

@dataclass
class CompressionConfig:
    """压缩配置"""
    algorithm: CompressionAlgorithm = CompressionAlgorithm.GZIP
    compression_level: int = 6
    chunk_size: int = 8192
    enable_compression: bool = True
    compression_threshold_mb: float = 100.0  # MB
    archive_after_days: int = 30
    delete_after_days: int = 365
    max_compression_ratio: float = 0.8  # 最大压缩比

@dataclass
class CompressionResult:
    """压缩结果"""
    original_size: int
    compressed_size: int
    compression_ratio: float
    algorithm: CompressionAlgorithm
    compression_time: float
    success: bool
    error_message: Optional[str] = None

@dataclass
class ArchiveInfo:
    """归档信息"""
    table_name: str
    partition_name: str
    record_count: int
    original_size_mb: float
    compressed_size_mb: float
    compression_ratio: float
    archive_date: datetime
    status: ArchiveStatus
    file_path: Optional[str] = None

class DataCompressor:
    """数据压缩器"""
    
    def __init__(self, config: CompressionConfig):
        self.config = config
        
    def compress_data(self, data: bytes) -> CompressionResult:
        """压缩数据"""
        start_time = datetime.now()
        original_size = len(data)
        
        try:
            if self.config.algorithm == CompressionAlgorithm.GZIP:
                compressed_data = gzip.compress(
                    data, 
                    compresslevel=self.config.compression_level
                )
            elif self.config.algorithm == CompressionAlgorithm.LZMA:
                compressed_data = lzma.compress(
                    data, 
                    preset=self.config.compression_level
                )
            elif self.config.algorithm == CompressionAlgorithm.ZLIB:
                compressed_data = zlib.compress(
                    data, 
                    level=self.config.compression_level
                )
            else:
                compressed_data = data
            
            compressed_size = len(compressed_data)
            compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
            compression_time = (datetime.now() - start_time).total_seconds()
            
            return CompressionResult(
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio,
                algorithm=self.config.algorithm,
                compression_time=compression_time,
                success=True
            )
            
        except Exception as e:
            logger.error(f"数据压缩失败: {e}")
            return CompressionResult(
                original_size=original_size,
                compressed_size=original_size,
                compression_ratio=1.0,
                algorithm=self.config.algorithm,
                compression_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error_message=str(e)
            )
    
    def decompress_data(self, compressed_data: bytes) -> bytes:
        """解压缩数据"""
        try:
            if self.config.algorithm == CompressionAlgorithm.GZIP:
                return gzip.decompress(compressed_data)
            elif self.config.algorithm == CompressionAlgorithm.LZMA:
                return lzma.decompress(compressed_data)
            elif self.config.algorithm == CompressionAlgorithm.ZLIB:
                return zlib.decompress(compressed_data)
            else:
                return compressed_data
                
        except Exception as e:
            logger.error(f"数据解压缩失败: {e}")
            raise
    
    def compress_json(self, data: Dict[str, Any]) -> Tuple[bytes, CompressionResult]:
        """压缩JSON数据"""
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        result = self.compress_data(json_data)
        
        if result.success:
            compressed_data = self.compress_data(json_data)
            return json_data if not result.success else self._get_compressed_bytes(json_data), result
        
        return json_data, result
    
    def _get_compressed_bytes(self, data: bytes) -> bytes:
        """获取压缩后的字节数据"""
        if self.config.algorithm == CompressionAlgorithm.GZIP:
            return gzip.compress(data, compresslevel=self.config.compression_level)
        elif self.config.algorithm == CompressionAlgorithm.LZMA:
            return lzma.compress(data, preset=self.config.compression_level)
        elif self.config.algorithm == CompressionAlgorithm.ZLIB:
            return zlib.compress(data, level=self.config.compression_level)
        else:
            return data

class DataArchiver:
    """数据归档器"""
    
    def __init__(self, config: CompressionConfig, archive_path: str = "./archives"):
        self.config = config
        self.archive_path = Path(archive_path)
        self.archive_path.mkdir(parents=True, exist_ok=True)
        self.compressor = DataCompressor(config)
        
    async def archive_partition(self, table_name: str, partition_name: str) -> ArchiveInfo:
        """归档分区数据"""
        db_manager = get_database_manager()
        
        try:
            with db_manager.get_session() as session:
                # 获取分区数据
                if table_name == "market_data":
                    query = session.query(MarketData).filter(
                        MarketData.partition_key == partition_name
                    )
                elif table_name == "kline_data":
                    query = session.query(KlineData).filter(
                        KlineData.partition_key == partition_name
                    )
                else:
                    raise ValueError(f"不支持的表名: {table_name}")
                
                # 获取记录数量
                record_count = query.count()
                
                if record_count == 0:
                    logger.warning(f"分区 {partition_name} 没有数据")
                    return ArchiveInfo(
                        table_name=table_name,
                        partition_name=partition_name,
                        record_count=0,
                        original_size_mb=0.0,
                        compressed_size_mb=0.0,
                        compression_ratio=1.0,
                        archive_date=datetime.now(),
                        status=ArchiveStatus.ARCHIVED
                    )
                
                # 导出数据
                data_list = []
                for record in query.all():
                    data_dict = {
                        column.name: getattr(record, column.name)
                        for column in record.__table__.columns
                    }
                    # 处理日期时间字段
                    for key, value in data_dict.items():
                        if isinstance(value, datetime):
                            data_dict[key] = value.isoformat()
                    data_list.append(data_dict)
                
                # 序列化数据
                json_data = json.dumps(data_list, ensure_ascii=False).encode('utf-8')
                original_size = len(json_data)
                
                # 压缩数据
                compression_result = self.compressor.compress_data(json_data)
                
                # 保存归档文件
                archive_filename = f"{table_name}_{partition_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.archive"
                archive_file_path = self.archive_path / archive_filename
                
                with open(archive_file_path, 'wb') as f:
                    if compression_result.success:
                        compressed_data = self.compressor._get_compressed_bytes(json_data)
                        f.write(compressed_data)
                    else:
                        f.write(json_data)
                
                # 创建归档信息
                archive_info = ArchiveInfo(
                    table_name=table_name,
                    partition_name=partition_name,
                    record_count=record_count,
                    original_size_mb=original_size / (1024 * 1024),
                    compressed_size_mb=compression_result.compressed_size / (1024 * 1024),
                    compression_ratio=compression_result.compression_ratio,
                    archive_date=datetime.now(),
                    status=ArchiveStatus.ARCHIVED,
                    file_path=str(archive_file_path)
                )
                
                logger.info(f"分区 {partition_name} 归档完成: {record_count} 条记录, "
                           f"压缩比 {compression_result.compression_ratio:.2%}")
                
                return archive_info
                
        except Exception as e:
            logger.error(f"归档分区 {partition_name} 失败: {e}")
            raise
    
    async def restore_partition(self, archive_file_path: str, table_name: str) -> int:
        """从归档文件恢复分区数据"""
        db_manager = get_database_manager()
        
        try:
            # 读取归档文件
            with open(archive_file_path, 'rb') as f:
                compressed_data = f.read()
            
            # 解压缩数据
            try:
                json_data = self.compressor.decompress_data(compressed_data)
            except:
                # 如果解压缩失败，可能是未压缩的数据
                json_data = compressed_data
            
            # 解析JSON数据
            data_list = json.loads(json_data.decode('utf-8'))
            
            # 恢复数据到数据库
            with db_manager.get_session() as session:
                restored_count = 0
                
                for data_dict in data_list:
                    # 处理日期时间字段
                    for key, value in data_dict.items():
                        if isinstance(value, str) and 'T' in value:
                            try:
                                data_dict[key] = datetime.fromisoformat(value)
                            except:
                                pass
                    
                    if table_name == "market_data":
                        record = MarketData(**data_dict)
                    elif table_name == "kline_data":
                        record = KlineData(**data_dict)
                    else:
                        raise ValueError(f"不支持的表名: {table_name}")
                    
                    session.add(record)
                    restored_count += 1
                
                session.commit()
                
                logger.info(f"从归档文件恢复 {restored_count} 条记录")
                return restored_count
                
        except Exception as e:
            logger.error(f"恢复归档文件 {archive_file_path} 失败: {e}")
            raise

class DataCompressionService:
    """数据压缩和归档服务"""
    
    def __init__(self, config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()
        self.compressor = DataCompressor(self.config)
        self.archiver = DataArchiver(self.config)
        self._running = False
        
        logger.info("数据压缩和归档服务已初始化")
    
    async def start_service(self):
        """启动服务"""
        if self._running:
            return
        
        self._running = True
        logger.info("数据压缩和归档服务已启动")
        
        # 启动定期归档任务
        asyncio.create_task(self._periodic_archive_task())
    
    async def stop_service(self):
        """停止服务"""
        self._running = False
        logger.info("数据压缩和归档服务已停止")
    
    async def _periodic_archive_task(self):
        """定期归档任务"""
        while self._running:
            try:
                await self.auto_archive_old_data()
                await asyncio.sleep(3600)  # 每小时检查一次
            except Exception as e:
                logger.error(f"定期归档任务失败: {e}")
                await asyncio.sleep(300)  # 出错后5分钟重试
    
    async def auto_archive_old_data(self) -> List[ArchiveInfo]:
        """自动归档旧数据"""
        if not self.config.enable_compression:
            return []
        
        db_manager = get_database_manager()
        archive_results = []
        
        try:
            with db_manager.get_session() as session:
                # 查找需要归档的分区
                cutoff_date = datetime.now() - timedelta(days=self.config.archive_after_days)
                
                # 查询旧分区
                old_partitions = session.query(DataPartition).filter(
                    and_(
                        DataPartition.created_at < cutoff_date,
                        DataPartition.status == "active"
                    )
                ).all()
                
                for partition in old_partitions:
                    try:
                        # 归档分区
                        archive_info = await self.archiver.archive_partition(
                            partition.table_name,
                            partition.partition_name
                        )
                        archive_results.append(archive_info)
                        
                        # 更新分区状态
                        partition.status = "archived"
                        session.commit()
                        
                    except Exception as e:
                        logger.error(f"归档分区 {partition.partition_name} 失败: {e}")
                        session.rollback()
                
                logger.info(f"自动归档完成: {len(archive_results)} 个分区")
                return archive_results
                
        except Exception as e:
            logger.error(f"自动归档失败: {e}")
            return []
    
    async def cleanup_old_archives(self) -> int:
        """清理旧归档文件"""
        if not self.config.enable_compression:
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.delete_after_days)
            deleted_count = 0
            
            for archive_file in self.archiver.archive_path.glob("*.archive"):
                file_stat = archive_file.stat()
                file_date = datetime.fromtimestamp(file_stat.st_mtime)
                
                if file_date < cutoff_date:
                    archive_file.unlink()
                    deleted_count += 1
                    logger.info(f"删除旧归档文件: {archive_file.name}")
            
            logger.info(f"清理完成: 删除 {deleted_count} 个旧归档文件")
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理旧归档文件失败: {e}")
            return 0
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """获取压缩统计信息"""
        try:
            archive_files = list(self.archiver.archive_path.glob("*.archive"))
            total_files = len(archive_files)
            total_size = sum(f.stat().st_size for f in archive_files)
            
            return {
                "total_archive_files": total_files,
                "total_archive_size_mb": total_size / (1024 * 1024),
                "compression_algorithm": self.config.algorithm.value,
                "compression_level": self.config.compression_level,
                "archive_path": str(self.archiver.archive_path),
                "config": asdict(self.config)
            }
            
        except Exception as e:
            logger.error(f"获取压缩统计信息失败: {e}")
            return {"error": str(e)}

# 全局服务实例
_compression_service: Optional[DataCompressionService] = None

def get_compression_service(config: Optional[CompressionConfig] = None) -> DataCompressionService:
    """获取数据压缩服务实例"""
    global _compression_service
    if _compression_service is None:
        _compression_service = DataCompressionService(config)
    return _compression_service