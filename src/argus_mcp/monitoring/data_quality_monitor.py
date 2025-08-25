"""
数据质量监控器
实现历史数据的质量检查、异常检测和报告功能
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from ..data_models.historical_data import StandardKLineData, DataQualityMetrics, ValidationResult


class QualityCheckType(Enum):
    """质量检查类型枚举"""
    COMPLETENESS = "completeness"  # 完整性检查
    ACCURACY = "accuracy"  # 准确性检查
    CONSISTENCY = "consistency"  # 一致性检查
    VALIDITY = "validity"  # 有效性检查
    TIMELINESS = "timeliness"  # 时效性检查


class AnomalyType(Enum):
    """异常类型枚举"""
    MISSING_DATA = "missing_data"  # 数据缺失
    PRICE_ANOMALY = "price_anomaly"  # 价格异常
    VOLUME_ANOMALY = "volume_anomaly"  # 成交量异常
    OHLC_INCONSISTENCY = "ohlc_inconsistency"  # OHLC逻辑不一致
    DUPLICATE_RECORDS = "duplicate_records"  # 重复记录
    OUTLIER_VALUES = "outlier_values"  # 异常值


@dataclass
class QualityIssue:
    """质量问题数据类"""
    issue_type: QualityCheckType
    anomaly_type: Optional[AnomalyType]
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    affected_records: int
    first_occurrence: datetime
    last_occurrence: datetime
    stock_code: str
    period: str
    details: Dict[str, Any]


@dataclass
class QualityReport:
    """质量报告数据类"""
    stock_code: str
    period: str
    total_records: int
    quality_score: float  # 0-100
    issues: List[QualityIssue]
    metrics: DataQualityMetrics
    generated_at: datetime
    check_duration: timedelta


class DataQualityMonitor:
    """
    数据质量监控器
    
    负责监控历史数据的质量，包括：
    - 数据完整性检查
    - 数据准确性验证
    - 异常数据检测
    - 质量指标计算
    - 质量报告生成
    """
    
    def __init__(self, 
                 completeness_threshold: float = 0.95,
                 accuracy_threshold: float = 0.98,
                 outlier_zscore: float = 3.0,
                 volume_spike_threshold: float = 5.0):
        """
        初始化数据质量监控器
        
        Args:
            completeness_threshold: 完整性阈值 (0-1)
            accuracy_threshold: 准确性阈值 (0-1)
            outlier_zscore: 异常值检测的Z-score阈值
            volume_spike_threshold: 成交量异常倍数阈值
        """
        self.completeness_threshold = completeness_threshold
        self.accuracy_threshold = accuracy_threshold
        self.outlier_zscore = outlier_zscore
        self.volume_spike_threshold = volume_spike_threshold
        
        self.logger = logging.getLogger(__name__)
        
    def check_data_quality(self, 
                          data: List[StandardKLineData], 
                          stock_code: str, 
                          period: str) -> QualityReport:
        """
        检查数据质量并生成质量报告
        
        Args:
            data: K线数据列表
            stock_code: 股票代码
            period: 数据周期
            
        Returns:
            QualityReport: 质量报告
        """
        start_time = datetime.now()
        
        if not data:
            return QualityReport(
                stock_code=stock_code,
                period=period,
                total_records=0,
                quality_score=0.0,
                issues=[],
                metrics=DataQualityMetrics(
                    completeness_rate=0.0,
                    accuracy_score=0.0,
                    timeliness_score=0.0,
                    consistency_score=0.0,
                    anomaly_count=0,
                    total_records=0,
                    missing_records=0,
                    invalid_ohlc_count=0
                ),
                generated_at=datetime.now(),
                check_duration=timedelta(0)
            )
        
        # 转换为DataFrame便于处理
        df = self._convert_to_dataframe(data)
        
        # 执行各项质量检查
        issues = []
        
        # 1. 完整性检查
        completeness_issues = self._check_completeness(df, stock_code, period)
        issues.extend(completeness_issues)
        
        # 2. 准确性检查
        accuracy_issues = self._check_accuracy(df, stock_code, period)
        issues.extend(accuracy_issues)
        
        # 3. 一致性检查
        consistency_issues = self._check_consistency(df, stock_code, period)
        issues.extend(consistency_issues)
        
        # 4. 有效性检查
        validity_issues = self._check_validity(df, stock_code, period)
        issues.extend(validity_issues)
        
        # 5. 异常检测
        anomaly_issues = self._detect_anomalies(df, stock_code, period)
        issues.extend(anomaly_issues)
        
        # 计算质量指标
        metrics = self._calculate_quality_metrics(df, issues)
        
        # 计算质量评分
        quality_score = self._calculate_quality_score(metrics, issues)
        
        check_duration = datetime.now() - start_time
        
        return QualityReport(
            stock_code=stock_code,
            period=period,
            total_records=len(data),
            quality_score=quality_score,
            issues=issues,
            metrics=metrics,
            generated_at=datetime.now(),
            check_duration=check_duration
        )
    
    def _convert_to_dataframe(self, data: List[StandardKLineData]) -> pd.DataFrame:
        """将K线数据转换为DataFrame"""
        records = []
        for item in data:
            record = {
                'datetime': pd.to_datetime(item.timestamp),
                'open': float(item.open),
                'high': float(item.high),
                'low': float(item.low),
                'close': float(item.close),
                'volume': int(item.volume),
                'amount': float(item.amount),
                'code': getattr(item, 'code', None)
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        df = df.sort_values('datetime')
        df = df.set_index('datetime')
        return df
    
    def _check_completeness(self, df: pd.DataFrame, stock_code: str, period: str) -> List[QualityIssue]:
        """检查数据完整性"""
        issues = []
        
        # 检查缺失值
        missing_values = df.isnull().sum()
        for column, count in missing_values.items():
            if count > 0:
                issues.append(QualityIssue(
                    issue_type=QualityCheckType.COMPLETENESS,
                    anomaly_type=AnomalyType.MISSING_DATA,
                    severity='high' if count > len(df) * 0.1 else 'medium',
                    description=f"列 {column} 存在 {count} 个缺失值",
                    affected_records=count,
                    first_occurrence=df.index[0],
                    last_occurrence=df.index[-1],
                    stock_code=stock_code,
                    period=period,
                    details={'column': column, 'missing_count': count}
                ))
        
        # 检查时间序列完整性
        expected_freq = self._get_expected_frequency(period)
        if expected_freq:
            expected_range = pd.date_range(
                start=df.index.min(),
                end=df.index.max(),
                freq=expected_freq
            )
            missing_dates = expected_range.difference(df.index)
            
            if len(missing_dates) > 0:
                issues.append(QualityIssue(
                    issue_type=QualityCheckType.COMPLETENESS,
                    anomaly_type=AnomalyType.MISSING_DATA,
                    severity='medium',
                    description=f"时间序列缺失 {len(missing_dates)} 个数据点",
                    affected_records=len(missing_dates),
                    first_occurrence=missing_dates[0],
                    last_occurrence=missing_dates[-1],
                    stock_code=stock_code,
                    period=period,
                    details={'missing_dates_count': len(missing_dates)}
                ))
        
        return issues
    
    def _check_accuracy(self, df: pd.DataFrame, stock_code: str, period: str) -> List[QualityIssue]:
        """检查数据准确性"""
        issues = []
        
        # 检查价格合理性
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if col in df.columns:
                negative_prices = df[df[col] < 0]
                if not negative_prices.empty:
                    issues.append(QualityIssue(
                        issue_type=QualityCheckType.ACCURACY,
                        anomaly_type=AnomalyType.OUTLIER_VALUES,
                        severity='critical',
                        description=f"列 {col} 存在负价格",
                        affected_records=len(negative_prices),
                        first_occurrence=negative_prices.index[0],
                        last_occurrence=negative_prices.index[-1],
                        stock_code=stock_code,
                        period=period,
                        details={'column': col, 'negative_count': len(negative_prices)}
                    ))
        
        # 检查成交量合理性
        if 'volume' in df.columns:
            negative_volumes = df[df['volume'] < 0]
            if not negative_volumes.empty:
                issues.append(QualityIssue(
                    issue_type=QualityCheckType.ACCURACY,
                    anomaly_type=AnomalyType.OUTLIER_VALUES,
                    severity='critical',
                    description="成交量存在负值",
                    affected_records=len(negative_volumes),
                    first_occurrence=negative_volumes.index[0],
                    last_occurrence=negative_volumes.index[-1],
                    stock_code=stock_code,
                    period=period,
                    details={'negative_volume_count': len(negative_volumes)}
                ))
        
        return issues
    
    def _check_consistency(self, df: pd.DataFrame, stock_code: str, period: str) -> List[QualityIssue]:
        """检查数据一致性"""
        issues = []
        
        # 检查OHLC逻辑关系
        ohlc_inconsistencies = df[
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        ]
        
        if not ohlc_inconsistencies.empty:
            issues.append(QualityIssue(
                issue_type=QualityCheckType.CONSISTENCY,
                anomaly_type=AnomalyType.OHLC_INCONSISTENCY,
                severity='high',
                description="OHLC价格逻辑不一致",
                affected_records=len(ohlc_inconsistencies),
                first_occurrence=ohlc_inconsistencies.index[0],
                last_occurrence=ohlc_inconsistencies.index[-1],
                stock_code=stock_code,
                period=period,
                details={'inconsistent_count': len(ohlc_inconsistencies)}
            ))
        
        # 检查重复记录
        duplicates = df[df.duplicated()]
        if not duplicates.empty:
            issues.append(QualityIssue(
                issue_type=QualityCheckType.CONSISTENCY,
                anomaly_type=AnomalyType.DUPLICATE_RECORDS,
                severity='medium',
                description=f"发现 {len(duplicates)} 条重复记录",
                affected_records=len(duplicates),
                first_occurrence=duplicates.index[0],
                last_occurrence=duplicates.index[-1],
                stock_code=stock_code,
                period=period,
                details={'duplicate_count': len(duplicates)}
            ))
        
        return issues
    
    def _check_validity(self, df: pd.DataFrame, stock_code: str, period: str) -> List[QualityIssue]:
        """检查数据有效性"""
        issues = []
        
        # 检查价格范围有效性
        max_price = df[['open', 'high', 'low', 'close']].max().max()
        if max_price > 10000:  # 假设合理价格上限
            issues.append(QualityIssue(
                issue_type=QualityCheckType.VALIDITY,
                anomaly_type=AnomalyType.OUTLIER_VALUES,
                severity='medium',
                description=f"价格异常高: {max_price}",
                affected_records=len(df[df[['open', 'high', 'low', 'close']] > 10000].dropna(how='all')),
                first_occurrence=df.index[0],
                last_occurrence=df.index[-1],
                stock_code=stock_code,
                period=period,
                details={'max_price': max_price}
            ))
        
        return issues
    
    def _detect_anomalies(self, df: pd.DataFrame, stock_code: str, period: str) -> List[QualityIssue]:
        """检测数据异常"""
        issues = []
        
        # 价格异常检测（使用Z-score）
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in df.columns:
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                outliers = df[z_scores > self.outlier_zscore]
                
                if not outliers.empty:
                    issues.append(QualityIssue(
                        issue_type=QualityCheckType.VALIDITY,
                        anomaly_type=AnomalyType.PRICE_ANOMALY,
                        severity='low',
                        description=f"{col}价格异常 (Z-score > {self.outlier_zscore})",
                        affected_records=len(outliers),
                        first_occurrence=outliers.index[0],
                        last_occurrence=outliers.index[-1],
                        stock_code=stock_code,
                        period=period,
                        details={'column': col, 'outlier_count': len(outliers)}
                    ))
        
        # 成交量异常检测
        if 'volume' in df.columns:
            volume_mean = df['volume'].mean()
            volume_std = df['volume'].std()
            
            if volume_std > 0:
                volume_spikes = df[df['volume'] > volume_mean + self.volume_spike_threshold * volume_std]
                
                if not volume_spikes.empty:
                    issues.append(QualityIssue(
                        issue_type=QualityCheckType.VALIDITY,
                        anomaly_type=AnomalyType.VOLUME_ANOMALY,
                        severity='low',
                        description=f"成交量异常激增 (>{self.volume_spike_threshold}倍标准差)",
                        affected_records=len(volume_spikes),
                        first_occurrence=volume_spikes.index[0],
                        last_occurrence=volume_spikes.index[-1],
                        stock_code=stock_code,
                        period=period,
                        details={'spike_count': len(volume_spikes)}
                    ))
        
        return issues
    
    def _calculate_quality_metrics(self, df: pd.DataFrame, issues: List[QualityIssue]) -> DataQualityMetrics:
        """计算质量指标"""
        total_records = len(df)
        
        # 计算完整性
        completeness = 1.0 - (sum(issue.affected_records for issue in issues 
                                if issue.issue_type == QualityCheckType.COMPLETENESS) / total_records)
        
        # 计算准确性
        accuracy = 1.0 - (sum(issue.affected_records for issue in issues 
                            if issue.issue_type == QualityCheckType.ACCURACY) / total_records)
        
        # 计算一致性
        consistency = 1.0 - (sum(issue.affected_records for issue in issues 
                             if issue.issue_type == QualityCheckType.CONSISTENCY) / total_records)
        
        # 计算有效性
        validity = 1.0 - (sum(issue.affected_records for issue in issues 
                            if issue.issue_type == QualityCheckType.VALIDITY) / total_records)
        
        # Count anomalies and OHLC errors
        anomaly_count = sum(1 for issue in issues if issue.issue_type in [QualityCheckType.ACCURACY, QualityCheckType.VALIDITY])
        invalid_ohlc_count = sum(1 for issue in issues if issue.issue_type == QualityCheckType.CONSISTENCY)
        missing_records = sum(issue.affected_records for issue in issues if issue.issue_type == QualityCheckType.COMPLETENESS)
        
        return DataQualityMetrics(
            completeness_rate=max(0.0, min(1.0, completeness)),
            accuracy_score=max(0.0, min(1.0, accuracy)),
            timeliness_score=1.0,  # Assume timely for now
            consistency_score=max(0.0, min(1.0, consistency)),
            anomaly_count=anomaly_count,
            total_records=total_records,
            missing_records=missing_records,
            invalid_ohlc_count=invalid_ohlc_count
        )
    
    def _calculate_quality_score(self, metrics: DataQualityMetrics, issues: List[QualityIssue]) -> float:
        """计算综合质量评分"""
        # 基础分数基于四个维度
        base_score = (metrics.completeness_rate + metrics.accuracy_score + 
                     metrics.consistency_score + metrics.timeliness_score) / 4 * 100
        
        # 根据严重问题扣分
        critical_issues = [issue for issue in issues if issue.severity == 'critical']
        high_issues = [issue for issue in issues if issue.severity == 'high']
        
        penalty = len(critical_issues) * 20 + len(high_issues) * 10
        final_score = max(0.0, min(100.0, base_score - penalty))
        
        return final_score
    
    def _get_expected_frequency(self, period: str) -> Optional[str]:
        """根据周期获取期望的频率字符串"""
        freq_map = {
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '30m': '30min',
            '1h': '1H',
            '1d': '1D',
            '1w': '1W',
            '1M': '1M'
        }
        return freq_map.get(period)
    
    def generate_batch_report(self, 
                            data_dict: Dict[str, List[StandardKLineData]],
                            period: str) -> Dict[str, QualityReport]:
        """
        批量生成质量报告
        
        Args:
            data_dict: 股票代码到K线数据的映射
            period: 数据周期
            
        Returns:
            Dict[str, QualityReport]: 股票代码到质量报告的映射
        """
        reports = {}
        for stock_code, data in data_dict.items():
            reports[stock_code] = self.check_data_quality(data, stock_code, period)
        
        return reports
    
    def get_summary_statistics(self, reports: Dict[str, QualityReport]) -> Dict[str, Any]:
        """获取汇总统计信息"""
        if not reports:
            return {}
        
        quality_scores = [report.quality_score for report in reports.values()]
        total_issues = sum(len(report.issues) for report in reports.values())
        
        return {
            'total_stocks': len(reports),
            'average_quality_score': np.mean(quality_scores),
            'min_quality_score': np.min(quality_scores),
            'max_quality_score': np.max(quality_scores),
            'total_issues': total_issues,
            'critical_issues': sum(1 for report in reports.values() 
                                 for issue in report.issues 
                                 if issue.severity == 'critical'),
            'high_issues': sum(1 for report in reports.values() 
                            for issue in report.issues 
                            if issue.severity == 'high'),
            'medium_issues': sum(1 for report in reports.values() 
                             for issue in report.issues 
                             if issue.severity == 'medium'),
            'low_issues': sum(1 for report in reports.values() 
                           for issue in report.issues 
                           if issue.severity == 'low')
        }