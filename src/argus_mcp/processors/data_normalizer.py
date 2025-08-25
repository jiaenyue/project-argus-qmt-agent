# -*- coding: utf-8 -*-
"""
Data format normalizer for historical K-line data.

This module provides enhanced data normalization capabilities based on the existing
normalize_xtdata.py functionality, with additional support for OHLC validation,
precision control, and multi-source data format conversion.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np

from ..data_models.historical_data import (
    StandardKLineData,
    ValidationResult,
    DataQualityMetrics,
    AnomalyReport,
    SupportedPeriod
)

logger = logging.getLogger(__name__)


class DataNormalizer:
    """Enhanced data normalizer for historical K-line data."""
    
    # Column mapping from various data source formats to standard format
    COLUMN_MAPPINGS = {
        # xtquant format
        "open": "open",
        "high": "high", 
        "low": "low",
        "close": "close",
        "vol": "volume",
        "volume": "volume",
        "amount": "amount",
        "amt": "amount",
        
        # Alternative formats
        "o": "open",
        "h": "high",
        "l": "low", 
        "c": "close",
        "v": "volume",
        "a": "amount",
        
        # Uppercase variants
        "OPEN": "open",
        "HIGH": "high",
        "LOW": "low",
        "CLOSE": "close",
        "VOLUME": "volume",
        "AMOUNT": "amount",
        "VOL": "volume",
        "AMT": "amount",
        
        # Other common formats
        "opening_price": "open",
        "highest_price": "high",
        "lowest_price": "low",
        "closing_price": "close",
        "trade_volume": "volume",
        "trade_amount": "amount",
        "turnover": "amount"
    }
    
    # Required fields for K-line data
    REQUIRED_FIELDS = ["open", "high", "low", "close", "volume"]
    
    def __init__(self):
        """Initialize the data normalizer."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def normalize_kline_data(
        self,
        raw_data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]],
        symbol: Optional[str] = None,
        period: Optional[str] = None
    ) -> List[StandardKLineData]:
        """
        Normalize raw K-line data to StandardKLineData format.
        
        Args:
            raw_data: Raw data from various sources
            symbol: Stock symbol for logging
            period: Data period for validation
            
        Returns:
            List of StandardKLineData objects
            
        Raises:
            ValueError: If data format is invalid or required fields are missing
        """
        try:
            # Convert input to DataFrame if needed
            df = self._convert_to_dataframe(raw_data)
            
            if df.empty:
                self.logger.warning(f"Empty data received for {symbol}")
                return []
            
            # Normalize column names
            df = self._normalize_column_names(df)
            
            # Validate required fields
            self._validate_required_fields(df)
            
            # Ensure proper index (datetime)
            df = self._normalize_index(df)
            
            # Normalize data types and precision
            df = self._normalize_data_types(df)
            
            # Convert to StandardKLineData objects
            kline_data = self._convert_to_standard_format(df, symbol)
            
            # Validate OHLC logic for each record
            validated_data = []
            for data in kline_data:
                validation_result = self.validate_ohlc_logic(data)
                if validation_result.is_valid:
                    data.quality_score = validation_result.quality_score
                    validated_data.append(data)
                else:
                    self.logger.warning(
                        f"OHLC validation failed for {symbol} at {data.timestamp}: "
                        f"{', '.join(validation_result.errors)}"
                    )
                    # Still include the data but with lower quality score
                    data.quality_score = max(0.1, validation_result.quality_score)
                    validated_data.append(data)
            
            self.logger.info(
                f"Normalized {len(validated_data)} records for {symbol} ({period})"
            )
            
            return validated_data
            
        except Exception as e:
            self.logger.error(f"Failed to normalize data for {symbol}: {str(e)}")
            raise ValueError(f"数据标准化失败: {str(e)}")
    
    def validate_ohlc_logic(self, data: StandardKLineData) -> ValidationResult:
        """
        Validate OHLC logical relationships.
        
        OHLC validation rules:
        - High >= max(Open, Close)
        - Low <= min(Open, Close)  
        - High >= Low
        - All prices > 0
        - Volume >= 0
        
        Args:
            data: StandardKLineData to validate
            
        Returns:
            ValidationResult with validation status and quality score
        """
        errors = []
        warnings = []
        quality_score = 1.0
        
        try:
            # Convert Decimal to float for comparison
            open_price = float(data.open)
            high_price = float(data.high)
            low_price = float(data.low)
            close_price = float(data.close)
            volume = data.volume
            amount = float(data.amount) if data.amount else 0
            
            # Check for positive prices
            if any(price <= 0 for price in [open_price, high_price, low_price, close_price]):
                errors.append("价格数据必须大于0")
                quality_score -= 0.3
            
            # Check High >= Low
            if high_price < low_price:
                errors.append(f"最高价({high_price})不能小于最低价({low_price})")
                quality_score -= 0.4
            
            # Check High >= max(Open, Close)
            max_oc = max(open_price, close_price)
            if high_price < max_oc:
                errors.append(f"最高价({high_price})不能小于开盘价和收盘价的最大值({max_oc})")
                quality_score -= 0.3
            
            # Check Low <= min(Open, Close)
            min_oc = min(open_price, close_price)
            if low_price > min_oc:
                errors.append(f"最低价({low_price})不能大于开盘价和收盘价的最小值({min_oc})")
                quality_score -= 0.3
            
            # Check volume
            if volume < 0:
                errors.append("成交量不能为负数")
                quality_score -= 0.2
            
            # Check amount consistency (if both volume and amount are available)
            if volume > 0 and amount > 0:
                avg_price = (open_price + high_price + low_price + close_price) / 4
                expected_amount = volume * avg_price
                amount_diff_ratio = abs(amount - expected_amount) / expected_amount
                
                if amount_diff_ratio > 0.5:  # 50% difference threshold
                    warnings.append(f"成交额({amount})与预期值({expected_amount:.2f})差异较大")
                    quality_score -= 0.1
            
            # Additional quality checks
            price_range = high_price - low_price
            avg_price = (open_price + close_price) / 2
            
            # Check for suspicious price ranges
            if avg_price > 0:
                range_ratio = price_range / avg_price
                if range_ratio > 0.2:  # 20% daily range seems excessive
                    warnings.append(f"价格波动范围({range_ratio:.2%})异常大")
                    quality_score -= 0.05
            
            # Ensure quality score is within bounds
            quality_score = max(0.0, min(1.0, quality_score))
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                quality_score=quality_score
            )
            
        except Exception as e:
            self.logger.error(f"OHLC validation error: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[f"验证过程出错: {str(e)}"],
                warnings=[],
                quality_score=0.0
            )
    
    def calculate_data_quality_metrics(
        self,
        data: List[StandardKLineData],
        expected_count: Optional[int] = None
    ) -> DataQualityMetrics:
        """
        Calculate comprehensive data quality metrics.
        
        Args:
            data: List of StandardKLineData
            expected_count: Expected number of records
            
        Returns:
            DataQualityMetrics object
        """
        if not data:
            return DataQualityMetrics(
                completeness_rate=0.0,
                accuracy_score=0.0,
                timeliness_score=0.0,
                consistency_score=0.0,
                anomaly_count=0,
                total_records=0,
                missing_records=expected_count or 0,
                invalid_ohlc_count=0
            )
        
        total_records = len(data)
        missing_records = max(0, (expected_count or total_records) - total_records)
        
        # Calculate completeness rate
        completeness_rate = total_records / (expected_count or total_records) if expected_count else 1.0
        
        # Calculate accuracy score (average quality score)
        accuracy_score = sum(d.quality_score for d in data) / total_records
        
        # Calculate consistency score (check for data gaps and duplicates)
        timestamps = [d.timestamp for d in data]
        unique_timestamps = set(timestamps)
        consistency_score = len(unique_timestamps) / total_records if total_records > 0 else 1.0
        
        # Calculate timeliness score (based on data freshness)
        if data:
            latest_timestamp = max(timestamps)
            now = datetime.now(timezone.utc)
            if latest_timestamp.tzinfo is None:
                latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
            
            time_diff_hours = (now - latest_timestamp).total_seconds() / 3600
            # Timeliness decreases as data gets older
            timeliness_score = max(0.0, 1.0 - (time_diff_hours / 24))  # Full score within 24 hours
        else:
            timeliness_score = 0.0
        
        # Count anomalies (low quality scores)
        anomaly_count = sum(1 for d in data if d.quality_score < 0.8)
        
        # Count invalid OHLC records
        invalid_ohlc_count = 0
        for d in data:
            validation = self.validate_ohlc_logic(d)
            if not validation.is_valid:
                invalid_ohlc_count += 1
        
        return DataQualityMetrics(
            completeness_rate=completeness_rate,
            accuracy_score=accuracy_score,
            timeliness_score=timeliness_score,
            consistency_score=consistency_score,
            anomaly_count=anomaly_count,
            total_records=total_records,
            missing_records=missing_records,
            invalid_ohlc_count=invalid_ohlc_count
        )
    
    def detect_anomalies(self, data: List[StandardKLineData]) -> List[AnomalyReport]:
        """
        Detect anomalies in the data.
        
        Args:
            data: List of StandardKLineData
            
        Returns:
            List of AnomalyReport objects
        """
        anomalies = []
        
        if not data:
            return anomalies
        
        # Sort data by timestamp
        sorted_data = sorted(data, key=lambda x: x.timestamp)
        
        for i, record in enumerate(sorted_data):
            # Check OHLC validation
            validation = self.validate_ohlc_logic(record)
            if not validation.is_valid:
                anomalies.append(AnomalyReport(
                    timestamp=record.timestamp,
                    anomaly_type="OHLC_VALIDATION_ERROR",
                    description="; ".join(validation.errors),
                    severity="high",
                    suggested_action="检查数据源或手动修正数据",
                    raw_data={
                        "open": float(record.open),
                        "high": float(record.high),
                        "low": float(record.low),
                        "close": float(record.close),
                        "volume": record.volume
                    }
                ))
            
            # Check for price spikes (compared to previous record)
            if i > 0:
                prev_record = sorted_data[i-1]
                price_change = abs(float(record.close) - float(prev_record.close)) / float(prev_record.close)
                
                if price_change > 0.3:  # 30% price change threshold
                    anomalies.append(AnomalyReport(
                        timestamp=record.timestamp,
                        anomaly_type="PRICE_SPIKE",
                        description=f"价格变化异常: {price_change:.2%}",
                        severity="medium",
                        suggested_action="验证价格数据准确性",
                        raw_data={
                            "current_close": float(record.close),
                            "previous_close": float(prev_record.close),
                            "change_ratio": price_change
                        }
                    ))
            
            # Check for zero volume with non-zero price change
            if record.volume == 0 and i > 0:
                prev_record = sorted_data[i-1]
                if record.close != prev_record.close:
                    anomalies.append(AnomalyReport(
                        timestamp=record.timestamp,
                        anomaly_type="ZERO_VOLUME_PRICE_CHANGE",
                        description="零成交量但价格发生变化",
                        severity="low",
                        suggested_action="检查成交量数据",
                        raw_data={
                            "volume": record.volume,
                            "price_change": float(record.close) - float(prev_record.close)
                        }
                    ))
        
        return anomalies
    
    def _convert_to_dataframe(self, raw_data: Union[pd.DataFrame, List[Dict], Dict]) -> pd.DataFrame:
        """Convert various input formats to DataFrame."""
        if isinstance(raw_data, pd.DataFrame):
            return raw_data.copy()
        elif isinstance(raw_data, list):
            return pd.DataFrame(raw_data)
        elif isinstance(raw_data, dict):
            return pd.DataFrame([raw_data])
        else:
            raise ValueError(f"不支持的数据格式: {type(raw_data)}")
    
    def _normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names using the mapping."""
        df = df.copy()
        
        # Create case-insensitive mapping
        normalized_columns = {}
        for col in df.columns:
            col_str = str(col).strip()
            col_lower = col_str.lower()
            
            # Try exact match first
            if col_lower in self.COLUMN_MAPPINGS:
                normalized_columns[col] = self.COLUMN_MAPPINGS[col_lower]
            elif col_str in self.COLUMN_MAPPINGS:
                normalized_columns[col] = self.COLUMN_MAPPINGS[col_str]
            else:
                # Keep original column name if no mapping found
                normalized_columns[col] = col_lower
        
        return df.rename(columns=normalized_columns)
    
    def _validate_required_fields(self, df: pd.DataFrame) -> None:
        """Validate that required fields are present."""
        missing_fields = []
        for field in self.REQUIRED_FIELDS:
            if field not in df.columns:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"缺少必需字段: {missing_fields}")
    
    def _normalize_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize DataFrame index to DatetimeIndex."""
        df = df.copy()
        
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as e:
                self.logger.warning(f"无法转换索引为日期时间格式: {str(e)}")
                # If index conversion fails, try to find a time column
                time_columns = ['time', 'timestamp', 'date', 'datetime']
                for col in time_columns:
                    if col in df.columns:
                        try:
                            df.index = pd.to_datetime(df[col])
                            df = df.drop(columns=[col])
                            break
                        except Exception:
                            continue
        
        return df
    
    def _normalize_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize data types and precision."""
        df = df.copy()
        
        # Price fields - convert to Decimal with 4 decimal places
        price_fields = ['open', 'high', 'low', 'close']
        for field in price_fields:
            if field in df.columns:
                df[field] = df[field].apply(self._to_decimal_price)
        
        # Amount field - convert to Decimal with 2 decimal places
        if 'amount' in df.columns:
            df['amount'] = df['amount'].apply(self._to_decimal_amount)
        else:
            # If amount is missing, set to 0
            df['amount'] = Decimal('0.00')
        
        # Volume field - convert to integer
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
        
        return df
    
    def _to_decimal_price(self, value) -> Decimal:
        """Convert value to Decimal with 4 decimal places."""
        try:
            if pd.isna(value) or value is None:
                return Decimal('0.0000')
            return Decimal(str(float(value))).quantize(Decimal('0.0001'))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('0.0000')
    
    def _to_decimal_amount(self, value) -> Decimal:
        """Convert value to Decimal with 2 decimal places."""
        try:
            if pd.isna(value) or value is None:
                return Decimal('0.00')
            return Decimal(str(float(value))).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('0.00')
    
    def _convert_to_standard_format(self, df: pd.DataFrame, symbol: Optional[str] = None) -> List[StandardKLineData]:
        """Convert DataFrame to list of StandardKLineData."""
        kline_data = []
        
        for timestamp, row in df.iterrows():
            try:
                # Ensure timestamp has timezone info
                if isinstance(timestamp, pd.Timestamp):
                    if timestamp.tz is None:
                        timestamp = timestamp.tz_localize('UTC')
                    timestamp = timestamp.to_pydatetime()
                elif isinstance(timestamp, datetime):
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                
                kline_data.append(StandardKLineData(
                    timestamp=timestamp,
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=int(row['volume']),
                    amount=row['amount'],
                    quality_score=1.0,  # Will be updated during validation
                    code=symbol
                ))
            except Exception as e:
                self.logger.warning(f"跳过无效记录 {timestamp}: {str(e)}")
                continue
        
        return kline_data