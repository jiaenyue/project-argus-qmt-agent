# -*- coding: utf-8 -*-
"""
多周期数据处理器

支持将不同周期的K线数据进行聚合、对齐和处理，实现从分钟级到月级数据的完整支持。
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import logging
from enum import Enum

from src.argus_mcp.data_models.historical_data import (
    StandardKLineData, 
    SupportedPeriod,
    DataQualityMetrics
)


class PeriodType(Enum):
    """周期类型枚举"""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"


class MultiPeriodProcessor:
    """多周期数据处理器"""
    
    def __init__(self):
        """初始化多周期处理器"""
        self.logger = logging.getLogger(__name__)
        
    def resample_data(self, 
                     data: List[StandardKLineData], 
                     target_period: PeriodType,
                     symbol: str) -> List[StandardKLineData]:
        """
        将数据重采样到指定周期
        
        Args:
            data: 原始K线数据列表
            target_period: 目标周期
            symbol: 股票代码
            
        Returns:
            重采样后的K线数据列表
        """
        if not data:
            return []
            
        # 转换为DataFrame
        df = self._convert_to_dataframe(data)
        
        # 设置时间索引
        df.set_index('timestamp', inplace=True)
        
        # 获取重采样频率
        freq = self._get_resample_freq(target_period)
        
        # 重采样数据
        resampled = self._perform_resampling(df, freq)
        
        # 转换回StandardKLineData
        return self._convert_back_to_standard(resampled, symbol, target_period)
    
    def align_data(self, 
                  data: List[StandardKLineData],
                  target_period: PeriodType) -> List[StandardKLineData]:
        """
        对齐数据到指定周期的标准时间点
        
        Args:
            data: 原始数据
            target_period: 目标周期
            
        Returns:
            对齐后的数据
        """
        if not data:
            return []
            
        # 获取对齐规则
        align_func = self._get_alignment_function(target_period)
        
        # 应用对齐
        return align_func(data)
    
    def aggregate_periods(self, 
                         data: List[StandardKLineData],
                         start_period: PeriodType,
                         target_period: PeriodType,
                         symbol: str) -> List[StandardKLineData]:
        """
        聚合数据从一个周期到另一个周期
        
        Args:
            data: 原始数据
            start_period: 起始周期
            target_period: 目标周期
            symbol: 股票代码
            
        Returns:
            聚合后的数据
        """
        # 检查是否可以直接聚合
        if self._can_direct_aggregate(start_period, target_period):
            return self.resample_data(data, target_period, symbol)
        else:
            # 需要多级聚合
            return self._multi_level_aggregate(data, start_period, target_period, symbol)
    
    def fill_missing_periods(self, 
                          data: List[StandardKLineData],
                          target_period: PeriodType,
                          start_time: datetime,
                          end_time: datetime) -> List[StandardKLineData]:
        """
        填充缺失的周期数据
        
        Args:
            data: 现有数据
            target_period: 目标周期
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            填充后的完整数据
        """
        if not data:
            return []
            
        # 生成完整的周期时间点
        expected_periods = self._generate_expected_periods(
            start_time, end_time, target_period
        )
        
        # 创建数据映射
        data_map = {d.timestamp: d for d in data}
        
        # 填充缺失数据
        filled_data = []
        for period_time in expected_periods:
            if period_time in data_map:
                filled_data.append(data_map[period_time])
            else:
                # 创建空数据点
                empty_data = self._create_empty_kline(period_time, target_period)
                filled_data.append(empty_data)
        
        return filled_data
    
    def validate_period_consistency(self, 
                                  data: List[StandardKLineData],
                                  target_period: PeriodType) -> bool:
        """
        验证周期数据的一致性
        
        Args:
            data: 待验证的数据
            target_period: 目标周期
            
        Returns:
            是否一致
        """
        if len(data) < 2:
            return True
            
        # 检查时间间隔一致性
        intervals = []
        for i in range(1, len(data)):
            interval = data[i].timestamp - data[i-1].timestamp
            intervals.append(interval)
        
        # 计算期望的间隔
        expected_interval = self._get_expected_interval(target_period)
        
        # 检查所有间隔是否一致
        for interval in intervals:
            if abs(interval.total_seconds() - expected_interval.total_seconds()) > 1:
                return False
                
        return True
    
    def _convert_to_dataframe(self, data: List[StandardKLineData]) -> pd.DataFrame:
        """将StandardKLineData转换为DataFrame"""
        records = []
        for item in data:
            records.append({
                'timestamp': item.timestamp,
                'open': float(item.open),
                'high': float(item.high),
                'low': float(item.low),
                'close': float(item.close),
                'volume': item.volume,
                'amount': float(item.amount)
            })
        
        return pd.DataFrame(records)
    
    def _get_resample_freq(self, period: PeriodType) -> str:
        """获取pandas重采样频率"""
        freq_map = {
            PeriodType.MINUTE_1: '1T',
            PeriodType.MINUTE_5: '5T',
            PeriodType.MINUTE_15: '15T',
            PeriodType.MINUTE_30: '30T',
            PeriodType.HOUR_1: '1H',
            PeriodType.HOUR_4: '4H',
            PeriodType.DAILY: '1D',
            PeriodType.WEEKLY: '1W',
            PeriodType.MONTHLY: '1M'
        }
        return freq_map[period]
    
    def _perform_resampling(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """执行数据重采样"""
        # 重采样规则
        resample_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'amount': 'sum'
        }
        
        # 执行重采样
        resampled = df.resample(freq).agg(resample_rules)
        
        # 删除空值
        resampled.dropna(inplace=True)
        
        return resampled
    
    def _convert_back_to_standard(self, 
                                df: pd.DataFrame,
                                symbol: str,
                                period: PeriodType) -> List[StandardKLineData]:
        """将DataFrame转换回StandardKLineData"""
        result = []
        
        for timestamp, row in df.iterrows():
            kline_data = StandardKLineData(
                timestamp=timestamp.to_pydatetime().replace(tzinfo=None),
                open=Decimal(str(row['open'])).quantize(Decimal('0.0001')),
                high=Decimal(str(row['high'])).quantize(Decimal('0.0001')),
                low=Decimal(str(row['low'])).quantize(Decimal('0.0001')),
                close=Decimal(str(row['close'])).quantize(Decimal('0.0001')),
                volume=int(row['volume']),
                amount=Decimal(str(row['amount'])).quantize(Decimal('0.01')),
                symbol=symbol,
                period=SupportedPeriod(period.value)
            )
            result.append(kline_data)
        
        return result
    
    def _get_alignment_function(self, period: PeriodType):
        """获取对齐函数"""
        alignment_functions = {
            PeriodType.MINUTE_1: self._align_minute_data,
            PeriodType.MINUTE_5: self._align_minute_data,
            PeriodType.MINUTE_15: self._align_minute_data,
            PeriodType.MINUTE_30: self._align_minute_data,
            PeriodType.HOUR_1: self._align_hour_data,
            PeriodType.HOUR_4: self._align_hour_data,
            PeriodType.DAILY: self._align_daily_data,
            PeriodType.WEEKLY: self._align_weekly_data,
            PeriodType.MONTHLY: self._align_monthly_data
        }
        return alignment_functions[period]
    
    def _align_minute_data(self, data: List[StandardKLineData]) -> List[StandardKLineData]:
        """对齐分钟级数据"""
        # 分钟数据通常不需要额外对齐
        return sorted(data, key=lambda x: x.timestamp)
    
    def _align_hour_data(self, data: List[StandardKLineData]) -> List[StandardKLineData]:
        """对齐小时级数据"""
        aligned_data = []
        for item in data:
            # 对齐到整点
            aligned_time = item.timestamp.replace(minute=0, second=0, microsecond=0)
            if aligned_time != item.timestamp:
                self.logger.warning(f"时间未对齐: {item.timestamp} -> {aligned_time}")
            aligned_data.append(item)
        return aligned_data
    
    def _align_daily_data(self, data: List[StandardKLineData]) -> List[StandardKLineData]:
        """对齐日级数据"""
        aligned_data = []
        for item in data:
            # 对齐到交易日结束时间
            aligned_time = item.timestamp.replace(hour=15, minute=0, second=0, microsecond=0)
            if aligned_time != item.timestamp:
                self.logger.warning(f"时间未对齐: {item.timestamp} -> {aligned_time}")
            aligned_data.append(item)
        return aligned_data
    
    def _align_weekly_data(self, data: List[StandardKLineData]) -> List[StandardKLineData]:
        """对齐周级数据"""
        aligned_data = []
        for item in data:
            # 对齐到周五收盘
            weekday = item.timestamp.weekday()
            days_to_friday = (4 - weekday) % 7
            aligned_date = item.timestamp + timedelta(days=days_to_friday)
            aligned_time = aligned_date.replace(hour=15, minute=0, second=0, microsecond=0)
            aligned_data.append(item)
        return aligned_data
    
    def _align_monthly_data(self, data: List[StandardKLineData]) -> List[StandardKLineData]:
        """对齐月级数据"""
        aligned_data = []
        for item in data:
            # 对齐到月末
            import calendar
            last_day = calendar.monthrange(item.timestamp.year, item.timestamp.month)[1]
            aligned_time = item.timestamp.replace(
                day=last_day, hour=15, minute=0, second=0, microsecond=0
            )
            aligned_data.append(item)
        return aligned_data
    
    def _can_direct_aggregate(self, start: PeriodType, target: PeriodType) -> bool:
        """检查是否可以直接聚合"""
        # 定义聚合关系
        aggregation_map = {
            PeriodType.MINUTE_1: [PeriodType.MINUTE_5, PeriodType.MINUTE_15, PeriodType.MINUTE_30, PeriodType.HOUR_1, PeriodType.DAILY],
            PeriodType.MINUTE_5: [PeriodType.MINUTE_15, PeriodType.MINUTE_30, PeriodType.HOUR_1, PeriodType.DAILY],
            PeriodType.MINUTE_15: [PeriodType.MINUTE_30, PeriodType.HOUR_1, PeriodType.DAILY],
            PeriodType.MINUTE_30: [PeriodType.HOUR_1, PeriodType.DAILY],
            PeriodType.HOUR_1: [PeriodType.HOUR_4, PeriodType.DAILY],
            PeriodType.HOUR_4: [PeriodType.DAILY],
            PeriodType.DAILY: [PeriodType.WEEKLY, PeriodType.MONTHLY],
            PeriodType.WEEKLY: [PeriodType.MONTHLY]
        }
        
        return target in aggregation_map.get(start, [])
    
    def _multi_level_aggregate(self, 
                             data: List[StandardKLineData],
                             start: PeriodType,
                             target: PeriodType,
                             symbol: str) -> List[StandardKLineData]:
        """多级聚合"""
        # 找到中间步骤
        intermediate_steps = self._find_aggregation_path(start, target)
        
        current_data = data
        for step in intermediate_steps:
            current_data = self.resample_data(current_data, step, symbol)
        
        return current_data
    
    def _find_aggregation_path(self, start: PeriodType, target: PeriodType) -> List[PeriodType]:
        """查找聚合路径"""
        # 简化的聚合路径查找
        paths = {
            (PeriodType.MINUTE_1, PeriodType.WEEKLY): [PeriodType.DAILY, PeriodType.WEEKLY],
            (PeriodType.MINUTE_1, PeriodType.MONTHLY): [PeriodType.DAILY, PeriodType.MONTHLY],
            (PeriodType.MINUTE_5, PeriodType.WEEKLY): [PeriodType.DAILY, PeriodType.WEEKLY],
            (PeriodType.MINUTE_5, PeriodType.MONTHLY): [PeriodType.DAILY, PeriodType.MONTHLY],
        }
        
        return paths.get((start, target), [target])
    
    def _generate_expected_periods(self, 
                                 start_time: datetime,
                                 end_time: datetime,
                                 period: PeriodType) -> List[datetime]:
        """生成期望的周期时间点"""
        periods = []
        current = start_time
        
        while current <= end_time:
            periods.append(current)
            current = self._add_period(current, period)
        
        return periods
    
    def _add_period(self, dt: datetime, period: PeriodType) -> datetime:
        """添加一个周期"""
        period_deltas = {
            PeriodType.MINUTE_1: timedelta(minutes=1),
            PeriodType.MINUTE_5: timedelta(minutes=5),
            PeriodType.MINUTE_15: timedelta(minutes=15),
            PeriodType.MINUTE_30: timedelta(minutes=30),
            PeriodType.HOUR_1: timedelta(hours=1),
            PeriodType.HOUR_4: timedelta(hours=4),
            PeriodType.DAILY: timedelta(days=1),
            PeriodType.WEEKLY: timedelta(weeks=1),
            PeriodType.MONTHLY: timedelta(days=30)  # 近似
        }
        
        return dt + period_deltas[period]
    
    def _create_empty_kline(self, timestamp: datetime, period: PeriodType) -> StandardKLineData:
        """创建空的K线数据"""
        return StandardKLineData(
            timestamp=timestamp,
            open=Decimal('0.0000'),
            high=Decimal('0.0000'),
            low=Decimal('0.0000'),
            close=Decimal('0.0000'),
            volume=0,
            amount=Decimal('0.00'),
            symbol="",
            period=SupportedPeriod(period.value)
        )
    
    def _get_expected_interval(self, period: PeriodType) -> timedelta:
        """获取期望的时间间隔"""
        intervals = {
            PeriodType.MINUTE_1: timedelta(minutes=1),
            PeriodType.MINUTE_5: timedelta(minutes=5),
            PeriodType.MINUTE_15: timedelta(minutes=15),
            PeriodType.MINUTE_30: timedelta(minutes=30),
            PeriodType.HOUR_1: timedelta(hours=1),
            PeriodType.HOUR_4: timedelta(hours=4),
            PeriodType.DAILY: timedelta(days=1),
            PeriodType.WEEKLY: timedelta(weeks=1),
            PeriodType.MONTHLY: timedelta(days=30)
        }
        return intervals[period]