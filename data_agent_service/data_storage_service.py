#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据持久化服务
支持批量写入、查询、增量更新、数据压缩和归档
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import and_, or_, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import pandas as pd
import numpy as np
from decimal import Decimal
import json
import gzip
import pickle
from pathlib import Path

from .database_config import get_database_manager, get_partition_manager
from .database_models import (
    MarketData, KlineData, TradingCalendar, DataPartition,
    DataQualityMetrics, DataBackup, SystemMetrics,
    DataStatus, DataQuality, validate_data_integrity
)
from .performance_optimizer import get_global_optimizer
from .exception_handler import get_global_exception_handler, safe_execute

logger = logging.getLogger(__name__)

@dataclass
class BatchWriteResult:
    """批量写入结果"""
    success_count: int = 0
    error_count: int = 0
    duplicate_count: int = 0
    total_count: int = 0
    errors: List[str] = None
    execution_time: float = 0.0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return (self.success_count / self.total_count * 100) if self.total_count > 0 else 0.0

@dataclass
class QueryOptions:
    """查询选项"""
    limit: Optional[int] = None
    offset: Optional[int] = None
    order_by: Optional[str] = None
    order_desc: bool = False
    include_deleted: bool = False
    cache_ttl: Optional[int] = 300  # 缓存TTL（秒）

class DataStorageService:
    """数据存储服务"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.partition_manager = get_partition_manager()
        self.performance_optimizer = get_global_optimizer()
        self.exception_handler = get_global_exception_handler()
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="DataStorage")
        
        # 批量写入配置
        self.batch_size = 1000
        self.max_retries = 3
        self.retry_delay = 1.0
        
        logger.info("数据存储服务已初始化")
    
    async def batch_insert_market_data(self, data_list: List[Dict[str, Any]]) -> BatchWriteResult:
        """批量插入市场数据"""
        return await self._batch_insert_data(data_list, MarketData, "market_data")
    
    async def batch_insert_kline_data(self, data_list: List[Dict[str, Any]]) -> BatchWriteResult:
        """批量插入K线数据"""
        return await self._batch_insert_data(data_list, KlineData, "kline_data")
    
    async def _batch_insert_data(self, data_list: List[Dict[str, Any]], 
                               model_class, table_name: str) -> BatchWriteResult:
        """通用批量插入数据方法"""
        start_time = datetime.now()
        result = BatchWriteResult(total_count=len(data_list))
        
        if not data_list:
            return result
        
        # 数据验证和预处理
        validated_data = []
        for item in data_list:
            try:
                # 数据完整性验证
                validation_result = validate_data_integrity(item, table_name)
                if not validation_result['is_valid']:
                    result.error_count += 1
                    result.errors.extend(validation_result['issues'])
                    continue
                
                # 数据类型转换
                processed_item = self._preprocess_data(item, model_class)
                validated_data.append(processed_item)
                
            except Exception as e:
                result.error_count += 1
                result.errors.append(f"数据预处理错误: {str(e)}")
                logger.error(f"数据预处理错误: {e}")
        
        if not validated_data:
            result.execution_time = (datetime.now() - start_time).total_seconds()
            return result
        
        # 分批处理
        batches = [validated_data[i:i + self.batch_size] 
                  for i in range(0, len(validated_data), self.batch_size)]
        
        # 并发执行批量插入
        tasks = []
        for batch in batches:
            task = asyncio.create_task(
                self._insert_batch_with_retry(batch, model_class, table_name)
            )
            tasks.append(task)
        
        # 等待所有任务完成
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 汇总结果
        for batch_result in batch_results:
            if isinstance(batch_result, Exception):
                result.error_count += 1
                result.errors.append(f"批处理错误: {str(batch_result)}")
            elif isinstance(batch_result, BatchWriteResult):
                result.success_count += batch_result.success_count
                result.error_count += batch_result.error_count
                result.duplicate_count += batch_result.duplicate_count
                result.errors.extend(batch_result.errors)
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        
        # 记录性能指标
        await self._record_performance_metrics(table_name, "batch_insert", result)
        
        logger.info(f"批量插入完成 - 表: {table_name}, 成功: {result.success_count}, "
                   f"错误: {result.error_count}, 耗时: {result.execution_time:.2f}s")
        
        return result
    
    async def _insert_batch_with_retry(self, batch_data: List[Dict[str, Any]], 
                                     model_class, table_name: str) -> BatchWriteResult:
        """带重试的批量插入"""
        result = BatchWriteResult(total_count=len(batch_data))
        
        for attempt in range(self.max_retries):
            try:
                with self.db_manager.get_session() as session:
                    # 创建模型实例
                    instances = []
                    for item in batch_data:
                        try:
                            instance = model_class(**item)
                            instances.append(instance)
                        except Exception as e:
                            result.error_count += 1
                            result.errors.append(f"创建模型实例错误: {str(e)}")
                    
                    if not instances:
                        break
                    
                    # 批量插入
                    session.bulk_save_objects(instances)
                    session.commit()
                    
                    result.success_count = len(instances)
                    break
                    
            except IntegrityError as e:
                # 处理重复数据
                if "duplicate key" in str(e).lower():
                    result.duplicate_count += len(batch_data)
                    logger.warning(f"检测到重复数据: {str(e)}")
                    break
                else:
                    result.error_count += len(batch_data)
                    result.errors.append(f"完整性约束错误: {str(e)}")
                    break
                    
            except SQLAlchemyError as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    logger.warning(f"数据库错误，重试 {attempt + 1}/{self.max_retries}: {str(e)}")
                    continue
                else:
                    result.error_count += len(batch_data)
                    result.errors.append(f"数据库错误: {str(e)}")
                    break
                    
            except Exception as e:
                result.error_count += len(batch_data)
                result.errors.append(f"未知错误: {str(e)}")
                logger.error(f"批量插入未知错误: {e}")
                break
        
        return result
    
    def _preprocess_data(self, data: Dict[str, Any], model_class) -> Dict[str, Any]:
        """数据预处理"""
        processed = data.copy()
        
        # 处理日期字段
        if 'trade_date' in processed:
            if isinstance(processed['trade_date'], str):
                processed['trade_date'] = datetime.strptime(
                    processed['trade_date'], '%Y-%m-%d'
                ).date()
        
        # 处理时间戳字段
        if 'timestamp' in processed:
            if isinstance(processed['timestamp'], str):
                processed['timestamp'] = datetime.fromisoformat(
                    processed['timestamp'].replace('Z', '+00:00')
                )
        
        # 处理价格字段（转换为Decimal）
        price_fields = ['open_price', 'high_price', 'low_price', 'close_price', 
                       'pre_close', 'change_amount']
        for field in price_fields:
            if field in processed and processed[field] is not None:
                processed[field] = Decimal(str(processed[field]))
        
        # 处理数量字段
        if 'volume' in processed and processed['volume'] is not None:
            processed['volume'] = int(processed['volume'])
        
        if 'amount' in processed and processed['amount'] is not None:
            processed['amount'] = Decimal(str(processed['amount']))
        
        # 设置默认值
        if 'data_source' not in processed:
            processed['data_source'] = 'xtdata'
        
        if 'data_quality' not in processed:
            processed['data_quality'] = DataQuality.UNKNOWN.value
        
        if 'status' not in processed:
            processed['status'] = DataStatus.ACTIVE.value
        
        return processed
    
    @safe_execute
    async def query_market_data(self, symbols: List[str] = None, 
                              start_date: date = None, end_date: date = None,
                              options: QueryOptions = None) -> List[Dict[str, Any]]:
        """查询市场数据"""
        return await self._query_data(
            MarketData, symbols, start_date, end_date, options
        )
    
    @safe_execute
    async def query_kline_data(self, symbols: List[str] = None, 
                             period: str = None, start_date: date = None, 
                             end_date: date = None, options: QueryOptions = None) -> List[Dict[str, Any]]:
        """查询K线数据"""
        return await self._query_data(
            KlineData, symbols, start_date, end_date, options, period=period
        )
    
    async def _query_data(self, model_class, symbols: List[str] = None,
                        start_date: date = None, end_date: date = None,
                        options: QueryOptions = None, **kwargs) -> List[Dict[str, Any]]:
        """通用数据查询方法"""
        if options is None:
            options = QueryOptions()
        
        # 构建缓存键
        cache_key = self._build_cache_key(
            model_class.__tablename__, symbols, start_date, end_date, options, **kwargs
        )
        
        # 尝试从缓存获取
        if options.cache_ttl and options.cache_ttl > 0:
            cached_result = await self.performance_optimizer.get_cached_result(cache_key)
            if cached_result is not None:
                logger.debug(f"从缓存获取数据: {cache_key}")
                return cached_result
        
        start_time = datetime.now()
        
        try:
            with self.db_manager.get_session() as session:
                # 构建查询
                query = session.query(model_class)
                
                # 添加过滤条件
                if symbols:
                    query = query.filter(model_class.symbol.in_(symbols))
                
                if start_date:
                    query = query.filter(model_class.trade_date >= start_date)
                
                if end_date:
                    query = query.filter(model_class.trade_date <= end_date)
                
                # K线数据特殊过滤
                if hasattr(model_class, 'period') and 'period' in kwargs:
                    query = query.filter(model_class.period == kwargs['period'])
                
                # 状态过滤
                if not options.include_deleted:
                    query = query.filter(model_class.status != DataStatus.DELETED.value)
                
                # 排序
                if options.order_by:
                    order_field = getattr(model_class, options.order_by, None)
                    if order_field:
                        if options.order_desc:
                            query = query.order_by(order_field.desc())
                        else:
                            query = query.order_by(order_field)
                
                # 分页
                if options.limit:
                    query = query.limit(options.limit)
                
                if options.offset:
                    query = query.offset(options.offset)
                
                # 执行查询
                results = query.all()
                
                # 转换为字典列表
                data = []
                for result in results:
                    item = {}
                    for column in result.__table__.columns:
                        value = getattr(result, column.name)
                        if isinstance(value, (datetime, date)):
                            item[column.name] = value.isoformat()
                        elif isinstance(value, Decimal):
                            item[column.name] = float(value)
                        else:
                            item[column.name] = value
                    data.append(item)
                
                # 缓存结果
                if options.cache_ttl and options.cache_ttl > 0:
                    await self.performance_optimizer.cache_result(
                        cache_key, data, ttl=options.cache_ttl
                    )
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # 记录性能指标
                await self._record_performance_metrics(
                    model_class.__tablename__, "query", {
                        'record_count': len(data),
                        'execution_time': execution_time
                    }
                )
                
                logger.info(f"查询完成 - 表: {model_class.__tablename__}, "
                           f"记录数: {len(data)}, 耗时: {execution_time:.2f}s")
                
                return data
                
        except Exception as e:
            logger.error(f"查询数据错误: {e}")
            raise
    
    def _build_cache_key(self, table_name: str, symbols: List[str] = None,
                        start_date: date = None, end_date: date = None,
                        options: QueryOptions = None, **kwargs) -> str:
        """构建缓存键"""
        key_parts = [table_name]
        
        if symbols:
            key_parts.append(f"symbols_{','.join(sorted(symbols))}")
        
        if start_date:
            key_parts.append(f"start_{start_date.isoformat()}")
        
        if end_date:
            key_parts.append(f"end_{end_date.isoformat()}")
        
        if options:
            if options.limit:
                key_parts.append(f"limit_{options.limit}")
            if options.offset:
                key_parts.append(f"offset_{options.offset}")
            if options.order_by:
                key_parts.append(f"order_{options.order_by}_{options.order_desc}")
        
        for key, value in kwargs.items():
            if value is not None:
                key_parts.append(f"{key}_{value}")
        
        return "_".join(key_parts)
    
    async def update_data_incremental(self, table_name: str, 
                                    updates: List[Dict[str, Any]]) -> BatchWriteResult:
        """增量数据更新"""
        start_time = datetime.now()
        result = BatchWriteResult(total_count=len(updates))
        
        if not updates:
            return result
        
        model_class = self._get_model_class(table_name)
        if not model_class:
            result.error_count = len(updates)
            result.errors.append(f"未知的表名: {table_name}")
            return result
        
        try:
            with self.db_manager.get_session() as session:
                for update_data in updates:
                    try:
                        # 查找现有记录
                        query = session.query(model_class)
                        
                        # 构建查找条件
                        if 'symbol' in update_data and 'trade_date' in update_data:
                            query = query.filter(
                                and_(
                                    model_class.symbol == update_data['symbol'],
                                    model_class.trade_date == update_data['trade_date']
                                )
                            )
                        elif 'id' in update_data:
                            query = query.filter(model_class.id == update_data['id'])
                        else:
                            result.error_count += 1
                            result.errors.append("缺少更新条件（symbol+trade_date 或 id）")
                            continue
                        
                        existing = query.first()
                        
                        if existing:
                            # 更新现有记录
                            for key, value in update_data.items():
                                if hasattr(existing, key) and key != 'id':
                                    setattr(existing, key, value)
                            existing.updated_at = datetime.now()
                            result.success_count += 1
                        else:
                            # 创建新记录
                            processed_data = self._preprocess_data(update_data, model_class)
                            new_instance = model_class(**processed_data)
                            session.add(new_instance)
                            result.success_count += 1
                            
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(f"更新记录错误: {str(e)}")
                        logger.error(f"更新记录错误: {e}")
                
                session.commit()
                
        except Exception as e:
            result.error_count += len(updates)
            result.errors.append(f"增量更新错误: {str(e)}")
            logger.error(f"增量更新错误: {e}")
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        
        # 记录性能指标
        await self._record_performance_metrics(table_name, "incremental_update", result)
        
        logger.info(f"增量更新完成 - 表: {table_name}, 成功: {result.success_count}, "
                   f"错误: {result.error_count}, 耗时: {result.execution_time:.2f}s")
        
        return result
    
    def _get_model_class(self, table_name: str):
        """根据表名获取模型类"""
        model_mapping = {
            'market_data': MarketData,
            'kline_data': KlineData,
            'trading_calendar': TradingCalendar,
        }
        return model_mapping.get(table_name)
    
    async def _record_performance_metrics(self, table_name: str, operation: str, 
                                        metrics: Union[BatchWriteResult, Dict[str, Any]]):
        """记录性能指标"""
        try:
            if isinstance(metrics, BatchWriteResult):
                metric_data = {
                    'success_count': metrics.success_count,
                    'error_count': metrics.error_count,
                    'total_count': metrics.total_count,
                    'execution_time': metrics.execution_time,
                    'success_rate': metrics.success_rate
                }
            else:
                metric_data = metrics
            
            # 记录到系统指标表
            with self.db_manager.get_session() as session:
                for metric_name, value in metric_data.items():
                    metric = SystemMetrics(
                        metric_name=f"storage_{operation}_{metric_name}",
                        metric_type="gauge",
                        value=Decimal(str(value)),
                        labels={
                            'table': table_name,
                            'operation': operation
                        },
                        timestamp=datetime.now()
                    )
                    session.add(metric)
                session.commit()
                
        except Exception as e:
            logger.error(f"记录性能指标错误: {e}")
    
    async def get_storage_statistics(self, table_name: str = None) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            with self.db_manager.get_session() as session:
                stats = {}
                
                # 表级统计
                tables_to_check = [table_name] if table_name else ['market_data', 'kline_data']
                
                for table in tables_to_check:
                    model_class = self._get_model_class(table)
                    if not model_class:
                        continue
                    
                    # 记录数统计
                    total_count = session.query(func.count(model_class.id)).scalar()
                    
                    # 日期范围统计
                    date_range = session.query(
                        func.min(model_class.trade_date),
                        func.max(model_class.trade_date)
                    ).first()
                    
                    # 状态统计
                    status_stats = session.query(
                        model_class.status,
                        func.count(model_class.id)
                    ).group_by(model_class.status).all()
                    
                    stats[table] = {
                        'total_records': total_count,
                        'date_range': {
                            'start': date_range[0].isoformat() if date_range[0] else None,
                            'end': date_range[1].isoformat() if date_range[1] else None
                        },
                        'status_distribution': {status: count for status, count in status_stats}
                    }
                
                # 分区统计
                if self.db_manager.config.enable_partitioning:
                    partition_info = {}
                    for table in tables_to_check:
                        partitions = self.partition_manager.get_partition_info(table)
                        partition_info[table] = {
                            'partition_count': len(partitions),
                            'total_size': sum(p['size_bytes'] for p in partitions),
                            'partitions': partitions
                        }
                    stats['partitions'] = partition_info
                
                # 连接池统计
                stats['connection_pool'] = self.db_manager.get_connection_info()
                
                return stats
                
        except Exception as e:
            logger.error(f"获取存储统计信息错误: {e}")
            return {}
    
    async def cleanup_old_data(self, table_name: str, retention_days: int = 365) -> Dict[str, Any]:
        """清理过期数据"""
        cutoff_date = datetime.now().date() - timedelta(days=retention_days)
        
        model_class = self._get_model_class(table_name)
        if not model_class:
            return {'error': f'未知的表名: {table_name}'}
        
        try:
            with self.db_manager.get_session() as session:
                # 统计要删除的记录数
                count_query = session.query(func.count(model_class.id)).filter(
                    model_class.trade_date < cutoff_date
                )
                delete_count = count_query.scalar()
                
                if delete_count == 0:
                    return {
                        'table': table_name,
                        'deleted_count': 0,
                        'cutoff_date': cutoff_date.isoformat(),
                        'message': '没有需要清理的数据'
                    }
                
                # 执行删除
                delete_query = session.query(model_class).filter(
                    model_class.trade_date < cutoff_date
                )
                delete_query.delete(synchronize_session=False)
                session.commit()
                
                logger.info(f"清理过期数据完成 - 表: {table_name}, 删除记录数: {delete_count}")
                
                return {
                    'table': table_name,
                    'deleted_count': delete_count,
                    'cutoff_date': cutoff_date.isoformat(),
                    'message': f'成功清理 {delete_count} 条过期数据'
                }
                
        except Exception as e:
            logger.error(f"清理过期数据错误: {e}")
            return {
                'table': table_name,
                'error': str(e),
                'cutoff_date': cutoff_date.isoformat()
            }
    
    def close(self):
        """关闭服务"""
        if self.executor:
            self.executor.shutdown(wait=True)
        logger.info("数据存储服务已关闭")

# 全局数据存储服务实例
_storage_service: Optional[DataStorageService] = None

def get_data_storage_service() -> DataStorageService:
    """获取全局数据存储服务实例"""
    global _storage_service
    if _storage_service is None:
        _storage_service = DataStorageService()
    return _storage_service

def shutdown_data_storage_service():
    """关闭全局数据存储服务实例"""
    global _storage_service
    if _storage_service:
        _storage_service.close()
        _storage_service = None

# 向后兼容的别名
get_storage_service = get_data_storage_service
shutdown_storage_service = shutdown_data_storage_service