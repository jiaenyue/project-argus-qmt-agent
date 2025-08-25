"""数据备份和恢复服务

实现自动数据备份、恢复和验证功能，确保数据安全性。
"""

import logging
import shutil
import hashlib
import json
import gzip
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from pathlib import Path
import os
from sqlalchemy import text, and_, or_, func
from sqlalchemy.orm import Session
import subprocess

from .database_config import get_database_manager
from .database_models import (
    MarketData, KlineData, DataPartition, 
    DataQualityMetrics, SystemMetrics, DataBackup
)
from .exception_handler import safe_execute
from .data_compression_service import DataCompressor, CompressionConfig

logger = logging.getLogger(__name__)

class BackupType(Enum):
    """备份类型枚举"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SCHEMA_ONLY = "schema_only"

class BackupStatus(Enum):
    """备份状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"

@dataclass
class BackupConfig:
    """备份配置"""
    backup_path: str = "./backups"
    enable_backup: bool = True
    backup_interval_hours: int = 24
    retention_days: int = 30
    compression_enabled: bool = True
    verification_enabled: bool = True
    max_backup_size_gb: float = 10.0
    backup_types: List[BackupType] = None
    
    def __post_init__(self):
        if self.backup_types is None:
            self.backup_types = [BackupType.FULL, BackupType.INCREMENTAL]

@dataclass
class BackupInfo:
    """备份信息"""
    backup_id: str
    backup_type: BackupType
    backup_path: str
    file_size_mb: float
    record_count: int
    checksum: str
    created_at: datetime
    status: BackupStatus
    tables_included: List[str]
    compression_ratio: Optional[float] = None
    error_message: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None

@dataclass
class RestoreInfo:
    """恢复信息"""
    restore_id: str
    backup_id: str
    restore_path: str
    restored_records: int
    restore_time: float
    status: str
    created_at: datetime
    error_message: Optional[str] = None

class DatabaseBackupManager:
    """数据库备份管理器"""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.backup_path = Path(config.backup_path)
        self.backup_path.mkdir(parents=True, exist_ok=True)
        self.compressor = DataCompressor(CompressionConfig()) if config.compression_enabled else None
        
    def _generate_backup_id(self) -> str:
        """生成备份ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"backup_{timestamp}_{hash(str(datetime.now())) % 10000:04d}"
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件校验和"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def create_full_backup(self, tables: Optional[List[str]] = None) -> BackupInfo:
        """创建完整备份"""
        backup_id = self._generate_backup_id()
        backup_filename = f"{backup_id}_full.backup"
        backup_file_path = self.backup_path / backup_filename
        
        db_manager = get_database_manager()
        start_time = datetime.now()
        
        try:
            backup_data = {
                "backup_id": backup_id,
                "backup_type": BackupType.FULL.value,
                "created_at": start_time.isoformat(),
                "tables": {},
                "metadata": {
                    "version": "1.0",
                    "database_info": db_manager.get_connection_info()
                }
            }
            
            total_records = 0
            tables_to_backup = tables or ["market_data", "kline_data", "trading_calendar", "data_partitions"]
            
            with db_manager.get_session() as session:
                for table_name in tables_to_backup:
                    logger.info(f"备份表: {table_name}")
                    
                    if table_name == "market_data":
                        query = session.query(MarketData)
                        records = query.all()
                    elif table_name == "kline_data":
                        query = session.query(KlineData)
                        records = query.all()
                    elif table_name == "trading_calendar":
                        # 假设有交易日历表
                        records = []
                    elif table_name == "data_partitions":
                        query = session.query(DataPartition)
                        records = query.all()
                    else:
                        logger.warning(f"未知表名: {table_name}")
                        continue
                    
                    # 序列化记录
                    table_data = []
                    for record in records:
                        record_dict = {
                            column.name: getattr(record, column.name)
                            for column in record.__table__.columns
                        }
                        # 处理日期时间字段
                        for key, value in record_dict.items():
                            if isinstance(value, datetime):
                                record_dict[key] = value.isoformat()
                        table_data.append(record_dict)
                    
                    backup_data["tables"][table_name] = {
                        "records": table_data,
                        "count": len(table_data),
                        "backup_time": datetime.now().isoformat()
                    }
                    
                    total_records += len(table_data)
                    logger.info(f"表 {table_name} 备份完成: {len(table_data)} 条记录")
            
            # 保存备份文件
            backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
            
            if self.compressor:
                # 压缩备份数据
                compressed_data = gzip.compress(backup_json.encode('utf-8'))
                with open(backup_file_path, 'wb') as f:
                    f.write(compressed_data)
                compression_ratio = len(compressed_data) / len(backup_json.encode('utf-8'))
            else:
                with open(backup_file_path, 'w', encoding='utf-8') as f:
                    f.write(backup_json)
                compression_ratio = None
            
            # 计算文件信息
            file_size_mb = backup_file_path.stat().st_size / (1024 * 1024)
            checksum = self._calculate_checksum(backup_file_path)
            
            # 创建备份信息
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type=BackupType.FULL,
                backup_path=str(backup_file_path),
                file_size_mb=file_size_mb,
                record_count=total_records,
                checksum=checksum,
                created_at=start_time,
                status=BackupStatus.COMPLETED,
                tables_included=tables_to_backup,
                compression_ratio=compression_ratio
            )
            
            # 保存备份记录到数据库
            await self._save_backup_record(backup_info)
            
            logger.info(f"完整备份创建成功: {backup_id}, {total_records} 条记录, {file_size_mb:.2f} MB")
            return backup_info
            
        except Exception as e:
            logger.error(f"创建完整备份失败: {e}")
            # 清理失败的备份文件
            if backup_file_path.exists():
                backup_file_path.unlink()
            
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type=BackupType.FULL,
                backup_path=str(backup_file_path),
                file_size_mb=0.0,
                record_count=0,
                checksum="",
                created_at=start_time,
                status=BackupStatus.FAILED,
                tables_included=tables or [],
                error_message=str(e)
            )
            
            await self._save_backup_record(backup_info)
            raise
    
    async def create_incremental_backup(self, since_datetime: datetime, tables: Optional[List[str]] = None) -> BackupInfo:
        """创建增量备份"""
        backup_id = self._generate_backup_id()
        backup_filename = f"{backup_id}_incremental.backup"
        backup_file_path = self.backup_path / backup_filename
        
        db_manager = get_database_manager()
        start_time = datetime.now()
        
        try:
            backup_data = {
                "backup_id": backup_id,
                "backup_type": BackupType.INCREMENTAL.value,
                "created_at": start_time.isoformat(),
                "since_datetime": since_datetime.isoformat(),
                "tables": {},
                "metadata": {
                    "version": "1.0",
                    "database_info": db_manager.get_connection_info()
                }
            }
            
            total_records = 0
            tables_to_backup = tables or ["market_data", "kline_data"]
            
            with db_manager.get_session() as session:
                for table_name in tables_to_backup:
                    logger.info(f"增量备份表: {table_name}")
                    
                    if table_name == "market_data":
                        query = session.query(MarketData).filter(
                            MarketData.updated_at > since_datetime
                        )
                        records = query.all()
                    elif table_name == "kline_data":
                        query = session.query(KlineData).filter(
                            KlineData.updated_at > since_datetime
                        )
                        records = query.all()
                    else:
                        logger.warning(f"增量备份不支持表: {table_name}")
                        continue
                    
                    # 序列化记录
                    table_data = []
                    for record in records:
                        record_dict = {
                            column.name: getattr(record, column.name)
                            for column in record.__table__.columns
                        }
                        # 处理日期时间字段
                        for key, value in record_dict.items():
                            if isinstance(value, datetime):
                                record_dict[key] = value.isoformat()
                        table_data.append(record_dict)
                    
                    backup_data["tables"][table_name] = {
                        "records": table_data,
                        "count": len(table_data),
                        "backup_time": datetime.now().isoformat()
                    }
                    
                    total_records += len(table_data)
                    logger.info(f"表 {table_name} 增量备份完成: {len(table_data)} 条记录")
            
            # 保存备份文件
            backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
            
            if self.compressor:
                compressed_data = gzip.compress(backup_json.encode('utf-8'))
                with open(backup_file_path, 'wb') as f:
                    f.write(compressed_data)
                compression_ratio = len(compressed_data) / len(backup_json.encode('utf-8'))
            else:
                with open(backup_file_path, 'w', encoding='utf-8') as f:
                    f.write(backup_json)
                compression_ratio = None
            
            # 计算文件信息
            file_size_mb = backup_file_path.stat().st_size / (1024 * 1024)
            checksum = self._calculate_checksum(backup_file_path)
            
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type=BackupType.INCREMENTAL,
                backup_path=str(backup_file_path),
                file_size_mb=file_size_mb,
                record_count=total_records,
                checksum=checksum,
                created_at=start_time,
                status=BackupStatus.COMPLETED,
                tables_included=tables_to_backup,
                compression_ratio=compression_ratio
            )
            
            await self._save_backup_record(backup_info)
            
            logger.info(f"增量备份创建成功: {backup_id}, {total_records} 条记录")
            return backup_info
            
        except Exception as e:
            logger.error(f"创建增量备份失败: {e}")
            if backup_file_path.exists():
                backup_file_path.unlink()
            raise
    
    async def restore_backup(self, backup_id: str, target_tables: Optional[List[str]] = None) -> RestoreInfo:
        """恢复备份"""
        restore_id = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(backup_id) % 1000:03d}"
        start_time = datetime.now()
        
        try:
            # 查找备份文件
            backup_files = list(self.backup_path.glob(f"{backup_id}_*.backup"))
            if not backup_files:
                raise FileNotFoundError(f"未找到备份文件: {backup_id}")
            
            backup_file_path = backup_files[0]
            
            # 读取备份文件
            if self.compressor and backup_file_path.suffix == '.backup':
                with open(backup_file_path, 'rb') as f:
                    compressed_data = f.read()
                try:
                    backup_json = gzip.decompress(compressed_data).decode('utf-8')
                except:
                    # 如果解压缩失败，可能是未压缩的文件
                    backup_json = compressed_data.decode('utf-8')
            else:
                with open(backup_file_path, 'r', encoding='utf-8') as f:
                    backup_json = f.read()
            
            backup_data = json.loads(backup_json)
            
            # 恢复数据
            db_manager = get_database_manager()
            total_restored = 0
            
            tables_to_restore = target_tables or list(backup_data["tables"].keys())
            
            with db_manager.get_session() as session:
                for table_name in tables_to_restore:
                    if table_name not in backup_data["tables"]:
                        logger.warning(f"备份中不包含表: {table_name}")
                        continue
                    
                    table_data = backup_data["tables"][table_name]["records"]
                    logger.info(f"恢复表 {table_name}: {len(table_data)} 条记录")
                    
                    for record_dict in table_data:
                        # 处理日期时间字段
                        for key, value in record_dict.items():
                            if isinstance(value, str) and 'T' in value:
                                try:
                                    record_dict[key] = datetime.fromisoformat(value)
                                except:
                                    pass
                        
                        if table_name == "market_data":
                            record = MarketData(**record_dict)
                        elif table_name == "kline_data":
                            record = KlineData(**record_dict)
                        elif table_name == "data_partitions":
                            record = DataPartition(**record_dict)
                        else:
                            logger.warning(f"不支持恢复表: {table_name}")
                            continue
                        
                        session.merge(record)  # 使用merge避免主键冲突
                        total_restored += 1
                
                session.commit()
            
            restore_time = (datetime.now() - start_time).total_seconds()
            
            restore_info = RestoreInfo(
                restore_id=restore_id,
                backup_id=backup_id,
                restore_path=str(backup_file_path),
                restored_records=total_restored,
                restore_time=restore_time,
                status="completed",
                created_at=start_time
            )
            
            logger.info(f"备份恢复成功: {backup_id}, 恢复 {total_restored} 条记录, 耗时 {restore_time:.2f} 秒")
            return restore_info
            
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            restore_info = RestoreInfo(
                restore_id=restore_id,
                backup_id=backup_id,
                restore_path="",
                restored_records=0,
                restore_time=(datetime.now() - start_time).total_seconds(),
                status="failed",
                created_at=start_time,
                error_message=str(e)
            )
            return restore_info
    
    async def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        """验证备份完整性"""
        try:
            # 查找备份文件
            backup_files = list(self.backup_path.glob(f"{backup_id}_*.backup"))
            if not backup_files:
                return {"status": "failed", "error": "备份文件不存在"}
            
            backup_file_path = backup_files[0]
            
            # 验证文件完整性
            current_checksum = self._calculate_checksum(backup_file_path)
            
            # 从数据库获取原始校验和
            db_manager = get_database_manager()
            with db_manager.get_session() as session:
                backup_record = session.query(DataBackup).filter(
                    DataBackup.backup_id == backup_id
                ).first()
                
                if not backup_record:
                    return {"status": "failed", "error": "备份记录不存在"}
                
                original_checksum = backup_record.checksum
            
            # 校验和比较
            checksum_valid = current_checksum == original_checksum
            
            # 尝试读取和解析备份文件
            try:
                if self.compressor:
                    with open(backup_file_path, 'rb') as f:
                        compressed_data = f.read()
                    backup_json = gzip.decompress(compressed_data).decode('utf-8')
                else:
                    with open(backup_file_path, 'r', encoding='utf-8') as f:
                        backup_json = f.read()
                
                backup_data = json.loads(backup_json)
                structure_valid = True
                
                # 验证备份数据结构
                required_fields = ["backup_id", "backup_type", "created_at", "tables"]
                for field in required_fields:
                    if field not in backup_data:
                        structure_valid = False
                        break
                
            except Exception as e:
                structure_valid = False
                backup_data = None
            
            verification_result = {
                "status": "verified" if checksum_valid and structure_valid else "corrupted",
                "checksum_valid": checksum_valid,
                "structure_valid": structure_valid,
                "original_checksum": original_checksum,
                "current_checksum": current_checksum,
                "file_size_mb": backup_file_path.stat().st_size / (1024 * 1024),
                "verification_time": datetime.now().isoformat()
            }
            
            if backup_data:
                verification_result["tables_count"] = len(backup_data.get("tables", {}))
                verification_result["total_records"] = sum(
                    table_info.get("count", 0) 
                    for table_info in backup_data.get("tables", {}).values()
                )
            
            return verification_result
            
        except Exception as e:
            logger.error(f"验证备份失败: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def _save_backup_record(self, backup_info: BackupInfo):
        """保存备份记录到数据库"""
        db_manager = get_database_manager()
        
        try:
            with db_manager.get_session() as session:
                backup_record = DataBackup(
                    backup_id=backup_info.backup_id,
                    backup_type=backup_info.backup_type.value,
                    file_path=backup_info.backup_path,
                    file_size_mb=backup_info.file_size_mb,
                    record_count=backup_info.record_count,
                    checksum=backup_info.checksum,
                    status=backup_info.status.value,
                    tables_included=','.join(backup_info.tables_included),
                    compression_ratio=backup_info.compression_ratio,
                    error_message=backup_info.error_message,
                    created_at=backup_info.created_at
                )
                
                session.add(backup_record)
                session.commit()
                
        except Exception as e:
            logger.error(f"保存备份记录失败: {e}")

class DataBackupService:
    """数据备份和恢复服务"""
    
    def __init__(self, config: Optional[BackupConfig] = None):
        self.config = config or BackupConfig()
        self.backup_manager = DatabaseBackupManager(self.config)
        self._running = False
        self._last_backup_time: Optional[datetime] = None
        
        logger.info("数据备份和恢复服务已初始化")
    
    async def start_service(self):
        """启动服务"""
        if self._running:
            return
        
        self._running = True
        logger.info("数据备份和恢复服务已启动")
        
        # 启动定期备份任务
        if self.config.enable_backup:
            asyncio.create_task(self._periodic_backup_task())
    
    async def stop_service(self):
        """停止服务"""
        self._running = False
        logger.info("数据备份和恢复服务已停止")
    
    async def _periodic_backup_task(self):
        """定期备份任务"""
        while self._running:
            try:
                await self._auto_backup()
                await asyncio.sleep(self.config.backup_interval_hours * 3600)
            except Exception as e:
                logger.error(f"定期备份任务失败: {e}")
                await asyncio.sleep(1800)  # 出错后30分钟重试
    
    async def _auto_backup(self):
        """自动备份"""
        try:
            current_time = datetime.now()
            
            # 检查是否需要完整备份
            if (self._last_backup_time is None or 
                (current_time - self._last_backup_time).days >= 7):
                
                logger.info("开始自动完整备份")
                backup_info = await self.backup_manager.create_full_backup()
                
                if backup_info.status == BackupStatus.COMPLETED:
                    self._last_backup_time = current_time
                    logger.info(f"自动完整备份成功: {backup_info.backup_id}")
                    
                    # 验证备份
                    if self.config.verification_enabled:
                        verification_result = await self.backup_manager.verify_backup(backup_info.backup_id)
                        logger.info(f"备份验证结果: {verification_result['status']}")
            
            else:
                # 创建增量备份
                logger.info("开始自动增量备份")
                backup_info = await self.backup_manager.create_incremental_backup(
                    since_datetime=self._last_backup_time
                )
                
                if backup_info.status == BackupStatus.COMPLETED:
                    logger.info(f"自动增量备份成功: {backup_info.backup_id}")
            
            # 清理旧备份
            await self._cleanup_old_backups()
            
        except Exception as e:
            logger.error(f"自动备份失败: {e}")
    
    async def _cleanup_old_backups(self):
        """清理旧备份"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            deleted_count = 0
            
            for backup_file in self.backup_manager.backup_path.glob("*.backup"):
                file_stat = backup_file.stat()
                file_date = datetime.fromtimestamp(file_stat.st_mtime)
                
                if file_date < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.info(f"删除旧备份文件: {backup_file.name}")
            
            logger.info(f"清理完成: 删除 {deleted_count} 个旧备份文件")
            
        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """获取备份统计信息"""
        try:
            backup_files = list(self.backup_manager.backup_path.glob("*.backup"))
            total_files = len(backup_files)
            total_size = sum(f.stat().st_size for f in backup_files)
            
            return {
                "total_backup_files": total_files,
                "total_backup_size_mb": total_size / (1024 * 1024),
                "backup_path": str(self.backup_manager.backup_path),
                "last_backup_time": self._last_backup_time.isoformat() if self._last_backup_time else None,
                "config": asdict(self.config)
            }
            
        except Exception as e:
            logger.error(f"获取备份统计信息失败: {e}")
            return {"error": str(e)}

# 全局服务实例
_backup_service: Optional[DataBackupService] = None

def get_backup_service(config: Optional[BackupConfig] = None) -> DataBackupService:
    """获取数据备份服务实例"""
    global _backup_service
    if _backup_service is None:
        _backup_service = DataBackupService(config)
    return _backup_service