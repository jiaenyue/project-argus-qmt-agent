#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型定义
支持分区存储、数据完整性约束和性能优化的SQLAlchemy模型
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Date, Text, Boolean,
    Index, UniqueConstraint, CheckConstraint, ForeignKey, BigInteger,
    DECIMAL, JSON, LargeBinary
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from enum import Enum

Base = declarative_base()

class DataStatus(Enum):
    """数据状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PROCESSING = "processing"

class DataQuality(Enum):
    """数据质量枚举"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

class MarketData(Base):
    """市场数据表 - 支持按日期和股票代码分区"""
    __tablename__ = 'market_data'
    
    # 主键和分区键
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String(20), nullable=False, index=True)  # 股票代码
    trade_date = Column(Date, nullable=False, index=True)    # 交易日期
    
    # 市场数据字段
    open_price = Column(DECIMAL(10, 3), nullable=True)
    high_price = Column(DECIMAL(10, 3), nullable=True)
    low_price = Column(DECIMAL(10, 3), nullable=True)
    close_price = Column(DECIMAL(10, 3), nullable=True)
    volume = Column(BigInteger, nullable=True)
    amount = Column(DECIMAL(20, 2), nullable=True)
    turnover_rate = Column(DECIMAL(8, 4), nullable=True)
    
    # 扩展字段
    pre_close = Column(DECIMAL(10, 3), nullable=True)
    change_amount = Column(DECIMAL(10, 3), nullable=True)
    change_rate = Column(DECIMAL(8, 4), nullable=True)
    
    # 元数据
    data_source = Column(String(50), nullable=False, default='xtdata')
    data_quality = Column(String(20), nullable=False, default=DataQuality.UNKNOWN.value)
    status = Column(String(20), nullable=False, default=DataStatus.ACTIVE.value)
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # 数据完整性约束
    __table_args__ = (
        UniqueConstraint('symbol', 'trade_date', name='uq_market_data_symbol_date'),
        CheckConstraint('open_price >= 0', name='ck_market_data_open_positive'),
        CheckConstraint('high_price >= 0', name='ck_market_data_high_positive'),
        CheckConstraint('low_price >= 0', name='ck_market_data_low_positive'),
        CheckConstraint('close_price >= 0', name='ck_market_data_close_positive'),
        CheckConstraint('volume >= 0', name='ck_market_data_volume_positive'),
        CheckConstraint('amount >= 0', name='ck_market_data_amount_positive'),
        # 分区索引
        Index('idx_market_data_date_symbol', 'trade_date', 'symbol'),
        Index('idx_market_data_symbol_date', 'symbol', 'trade_date'),
        Index('idx_market_data_created_at', 'created_at'),
        Index('idx_market_data_status', 'status'),
    )
    
    @validates('symbol')
    def validate_symbol(self, key, symbol):
        if not symbol or len(symbol.strip()) == 0:
            raise ValueError("股票代码不能为空")
        return symbol.upper().strip()
    
    @validates('data_quality')
    def validate_data_quality(self, key, quality):
        if quality not in [q.value for q in DataQuality]:
            raise ValueError(f"无效的数据质量值: {quality}")
        return quality

class KlineData(Base):
    """K线数据表 - 支持多周期K线数据"""
    __tablename__ = 'kline_data'
    
    # 主键和分区键
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String(20), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    period = Column(String(10), nullable=False, index=True)  # 1d, 1h, 30m, 15m, 5m, 1m
    timestamp = Column(DateTime, nullable=False, index=True)  # 精确时间戳
    
    # K线数据字段
    open_price = Column(DECIMAL(10, 3), nullable=False)
    high_price = Column(DECIMAL(10, 3), nullable=False)
    low_price = Column(DECIMAL(10, 3), nullable=False)
    close_price = Column(DECIMAL(10, 3), nullable=False)
    volume = Column(BigInteger, nullable=False, default=0)
    amount = Column(DECIMAL(20, 2), nullable=False, default=0)
    
    # 技术指标字段（可选）
    ma5 = Column(DECIMAL(10, 3), nullable=True)
    ma10 = Column(DECIMAL(10, 3), nullable=True)
    ma20 = Column(DECIMAL(10, 3), nullable=True)
    ma60 = Column(DECIMAL(10, 3), nullable=True)
    
    # 元数据
    data_source = Column(String(50), nullable=False, default='xtdata')
    data_quality = Column(String(20), nullable=False, default=DataQuality.UNKNOWN.value)
    status = Column(String(20), nullable=False, default=DataStatus.ACTIVE.value)
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # 数据完整性约束
    __table_args__ = (
        UniqueConstraint('symbol', 'period', 'timestamp', name='uq_kline_symbol_period_time'),
        CheckConstraint('open_price > 0', name='ck_kline_open_positive'),
        CheckConstraint('high_price > 0', name='ck_kline_high_positive'),
        CheckConstraint('low_price > 0', name='ck_kline_low_positive'),
        CheckConstraint('close_price > 0', name='ck_kline_close_positive'),
        CheckConstraint('high_price >= low_price', name='ck_kline_high_low'),
        CheckConstraint('volume >= 0', name='ck_kline_volume_positive'),
        CheckConstraint('amount >= 0', name='ck_kline_amount_positive'),
        # 分区索引
        Index('idx_kline_date_symbol_period', 'trade_date', 'symbol', 'period'),
        Index('idx_kline_symbol_period_time', 'symbol', 'period', 'timestamp'),
        Index('idx_kline_timestamp', 'timestamp'),
        Index('idx_kline_created_at', 'created_at'),
    )
    
    @validates('period')
    def validate_period(self, key, period):
        valid_periods = ['1d', '1h', '30m', '15m', '5m', '1m']
        if period not in valid_periods:
            raise ValueError(f"无效的K线周期: {period}，支持的周期: {valid_periods}")
        return period

class TradingCalendar(Base):
    """交易日历表"""
    __tablename__ = 'trading_calendar'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trade_date = Column(Date, nullable=False, unique=True, index=True)
    is_trading_day = Column(Boolean, nullable=False, default=True)
    market = Column(String(20), nullable=False, default='SSE')  # SSE, SZSE
    
    # 节假日信息
    holiday_name = Column(String(100), nullable=True)
    holiday_type = Column(String(50), nullable=True)  # national, weekend, special
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_trading_calendar_date', 'trade_date'),
        Index('idx_trading_calendar_market_date', 'market', 'trade_date'),
    )

class DataPartition(Base):
    """数据分区管理表"""
    __tablename__ = 'data_partitions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_name = Column(String(100), nullable=False, index=True)
    partition_name = Column(String(100), nullable=False, index=True)
    partition_key = Column(String(100), nullable=False)  # 分区键值
    
    # 分区信息
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    record_count = Column(BigInteger, nullable=False, default=0)
    size_bytes = Column(BigInteger, nullable=False, default=0)
    
    # 分区状态
    status = Column(String(20), nullable=False, default=DataStatus.ACTIVE.value)
    is_compressed = Column(Boolean, nullable=False, default=False)
    compression_ratio = Column(DECIMAL(5, 2), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_accessed = Column(DateTime, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('table_name', 'partition_name', name='uq_partition_table_name'),
        Index('idx_partition_table', 'table_name'),
        Index('idx_partition_status', 'status'),
        Index('idx_partition_dates', 'start_date', 'end_date'),
    )

class DataQualityMetrics(Base):
    """数据质量指标表"""
    __tablename__ = 'data_quality_metrics'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_name = Column(String(100), nullable=False, index=True)
    symbol = Column(String(20), nullable=True, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    
    # 质量指标
    completeness_score = Column(DECIMAL(5, 2), nullable=False, default=0)  # 完整性评分 0-100
    accuracy_score = Column(DECIMAL(5, 2), nullable=False, default=0)     # 准确性评分 0-100
    consistency_score = Column(DECIMAL(5, 2), nullable=False, default=0)  # 一致性评分 0-100
    timeliness_score = Column(DECIMAL(5, 2), nullable=False, default=0)   # 及时性评分 0-100
    
    # 详细指标
    missing_fields = Column(Integer, nullable=False, default=0)
    total_fields = Column(Integer, nullable=False, default=0)
    anomaly_count = Column(Integer, nullable=False, default=0)
    
    # 质量问题
    quality_issues = Column(JSON, nullable=True)  # 存储质量问题详情
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    __table_args__ = (
        Index('idx_quality_table_date', 'table_name', 'trade_date'),
        Index('idx_quality_symbol_date', 'symbol', 'trade_date'),
        Index('idx_quality_scores', 'completeness_score', 'accuracy_score'),
    )

class DataBackup(Base):
    """数据备份记录表"""
    __tablename__ = 'data_backups'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    backup_name = Column(String(200), nullable=False, unique=True, index=True)
    backup_type = Column(String(50), nullable=False)  # full, incremental, differential
    
    # 备份范围
    table_names = Column(JSON, nullable=False)  # 备份的表列表
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    # 备份信息
    backup_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False, default=0)
    record_count = Column(BigInteger, nullable=False, default=0)
    compression_type = Column(String(20), nullable=True)  # gzip, lz4, zstd
    
    # 备份状态
    status = Column(String(20), nullable=False, default='pending')  # pending, running, completed, failed
    progress = Column(DECIMAL(5, 2), nullable=False, default=0)  # 0-100
    error_message = Column(Text, nullable=True)
    
    # 验证信息
    checksum = Column(String(64), nullable=True)  # SHA256校验和
    is_verified = Column(Boolean, nullable=False, default=False)
    
    # 时间戳
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    __table_args__ = (
        Index('idx_backup_type_status', 'backup_type', 'status'),
        Index('idx_backup_dates', 'start_date', 'end_date'),
        Index('idx_backup_created', 'created_at'),
    )

class SystemMetrics(Base):
    """系统性能指标表"""
    __tablename__ = 'system_metrics'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram
    
    # 指标值
    value = Column(DECIMAL(20, 6), nullable=False)
    unit = Column(String(20), nullable=True)
    
    # 标签和维度
    labels = Column(JSON, nullable=True)  # 指标标签
    dimensions = Column(JSON, nullable=True)  # 指标维度
    
    # 时间戳
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    __table_args__ = (
        Index('idx_metrics_name_time', 'metric_name', 'timestamp'),
        Index('idx_metrics_type_time', 'metric_type', 'timestamp'),
        Index('idx_metrics_timestamp', 'timestamp'),
    )

# 数据库配置和工具函数
def get_partition_name(table_name: str, date_value: date, symbol: str = None) -> str:
    """生成分区名称"""
    date_str = date_value.strftime('%Y%m%d')
    if symbol:
        return f"{table_name}_p_{date_str}_{symbol}"
    else:
        return f"{table_name}_p_{date_str}"

def get_partition_key(date_value: date, symbol: str = None) -> str:
    """生成分区键"""
    if symbol:
        return f"date={date_value.strftime('%Y-%m-%d')},symbol={symbol}"
    else:
        return f"date={date_value.strftime('%Y-%m-%d')}"

def validate_data_integrity(data: Dict[str, Any], table_name: str) -> Dict[str, Any]:
    """验证数据完整性"""
    issues = []
    
    if table_name in ['market_data', 'kline_data']:
        # 检查必需字段
        required_fields = ['symbol', 'trade_date']
        for field in required_fields:
            if not data.get(field):
                issues.append(f"缺少必需字段: {field}")
        
        # 检查价格字段
        price_fields = ['open_price', 'high_price', 'low_price', 'close_price']
        for field in price_fields:
            value = data.get(field)
            if value is not None and value <= 0:
                issues.append(f"价格字段 {field} 必须大于0")
        
        # 检查高低价关系
        high = data.get('high_price')
        low = data.get('low_price')
        if high is not None and low is not None and high < low:
            issues.append("最高价不能低于最低价")
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues,
        'quality_score': max(0, 100 - len(issues) * 10)
    }