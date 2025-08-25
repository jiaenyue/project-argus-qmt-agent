"""
增强的市场数据处理器
提供高性能的实时市场数据处理和批量数据获取功能
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
from enum import Enum
import threading
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class MarketDataType(Enum):
    """市场数据类型"""
    REAL_TIME = "real_time"
    SNAPSHOT = "snapshot"
    HISTORICAL = "historical"
    TICK = "tick"
    KLINE = "kline"

class DataQuality(Enum):
    """数据质量等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

@dataclass
class MarketDataPoint:
    """市场数据点"""
    symbol: str
    timestamp: float
    price: float
    volume: int
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    prev_close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    turnover: float = 0.0
    data_type: MarketDataType = MarketDataType.REAL_TIME
    quality: DataQuality = DataQuality.UNKNOWN
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketDataPoint':
        """从字典创建"""
        return cls(**data)

@dataclass
class BatchProcessingResult:
    """批量处理结果"""
    total_requested: int
    successful: int
    failed: int
    processing_time: float
    data: List[MarketDataPoint]
    errors: List[str]
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requested == 0:
            return 0.0
        return self.successful / self.total_requested

class DataAggregator:
    """数据聚合器"""
    
    def __init__(self):
        self.aggregation_rules = {
            'price': 'last',
            'volume': 'sum',
            'turnover': 'sum',
            'high_price': 'max',
            'low_price': 'min',
            'open_price': 'first'
        }
    
    def aggregate_data(self, data_points: List[MarketDataPoint], 
                      interval: str = '1min') -> List[MarketDataPoint]:
        """聚合数据点"""
        if not data_points:
            return []
        
        # 按symbol分组
        grouped_data = defaultdict(list)
        for point in data_points:
            grouped_data[point.symbol].append(point)
        
        aggregated_results = []
        
        for symbol, points in grouped_data.items():
            # 按时间间隔聚合
            df = pd.DataFrame([point.to_dict() for point in points])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('datetime', inplace=True)
            
            # 重采样
            resampled = df.resample(interval).agg(self.aggregation_rules)
            
            # 转换回MarketDataPoint
            for timestamp, row in resampled.iterrows():
                if not pd.isna(row['price']):
                    aggregated_point = MarketDataPoint(
                        symbol=symbol,
                        timestamp=timestamp.timestamp(),
                        price=row['price'],
                        volume=int(row['volume']) if not pd.isna(row['volume']) else 0,
                        high_price=row['high_price'] if not pd.isna(row['high_price']) else row['price'],
                        low_price=row['low_price'] if not pd.isna(row['low_price']) else row['price'],
                        open_price=row['open_price'] if not pd.isna(row['open_price']) else row['price'],
                        turnover=row['turnover'] if not pd.isna(row['turnover']) else 0.0,
                        data_type=MarketDataType.KLINE
                    )
                    aggregated_results.append(aggregated_point)
        
        return aggregated_results

class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        self.validation_rules = {
            'price_range': (0.01, 10000.0),  # 价格范围
            'volume_range': (0, 1000000000),  # 成交量范围
            'change_pct_range': (-20.0, 20.0),  # 涨跌幅范围
        }
    
    def validate_data_point(self, data_point: MarketDataPoint) -> Tuple[bool, List[str]]:
        """验证单个数据点"""
        errors = []
        
        # 价格验证
        if not (self.validation_rules['price_range'][0] <= 
                data_point.price <= 
                self.validation_rules['price_range'][1]):
            errors.append(f"Price {data_point.price} out of valid range")
        
        # 成交量验证
        if not (self.validation_rules['volume_range'][0] <= 
                data_point.volume <= 
                self.validation_rules['volume_range'][1]):
            errors.append(f"Volume {data_point.volume} out of valid range")
        
        # 涨跌幅验证
        if abs(data_point.change_pct) > self.validation_rules['change_pct_range'][1]:
            errors.append(f"Change percentage {data_point.change_pct} out of valid range")
        
        # 时间戳验证
        current_time = time.time()
        if data_point.timestamp > current_time + 300:  # 未来5分钟内
            errors.append(f"Timestamp {data_point.timestamp} is too far in the future")
        
        # 买卖价验证
        if data_point.bid_price > data_point.ask_price and data_point.ask_price > 0:
            errors.append("Bid price cannot be higher than ask price")
        
        return len(errors) == 0, errors
    
    def assess_data_quality(self, data_point: MarketDataPoint) -> DataQuality:
        """评估数据质量"""
        is_valid, errors = self.validate_data_point(data_point)
        
        if not is_valid:
            return DataQuality.LOW
        
        # 检查数据完整性
        completeness_score = 0
        total_fields = 0
        
        for field_name, field_value in asdict(data_point).items():
            if field_name not in ['data_type', 'quality']:
                total_fields += 1
                if field_value is not None and field_value != 0:
                    completeness_score += 1
        
        completeness_ratio = completeness_score / total_fields
        
        if completeness_ratio >= 0.9:
            return DataQuality.HIGH
        elif completeness_ratio >= 0.7:
            return DataQuality.MEDIUM
        else:
            return DataQuality.LOW

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self.batch_size = 100
        self.cache_hit_stats = defaultdict(int)
        self.processing_times = deque(maxlen=1000)
    
    async def parallel_fetch(self, symbols: List[str], 
                           fetch_function, 
                           max_concurrent: int = 5) -> List[Any]:
        """并行获取数据"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(symbol):
            async with semaphore:
                return await fetch_function(symbol)
        
        tasks = [fetch_with_semaphore(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常
        valid_results = [
            result for result in results 
            if not isinstance(result, Exception)
        ]
        
        return valid_results
    
    def optimize_batch_size(self, processing_times: List[float]) -> int:
        """优化批处理大小"""
        if len(processing_times) < 10:
            return self.batch_size
        
        # 计算最优批处理大小
        avg_time = np.mean(processing_times[-50:])  # 最近50次的平均时间
        
        if avg_time < 0.1:  # 100ms以下
            return min(self.batch_size * 2, 500)
        elif avg_time > 1.0:  # 1秒以上
            return max(self.batch_size // 2, 10)
        else:
            return self.batch_size
    
    def record_processing_time(self, processing_time: float):
        """记录处理时间"""
        self.processing_times.append(processing_time)
        
        # 动态调整批处理大小
        if len(self.processing_times) % 10 == 0:
            self.batch_size = self.optimize_batch_size(list(self.processing_times))

class EnhancedMarketDataProcessor:
    """增强的市场数据处理器"""
    
    def __init__(self, data_service_client=None, cache_optimizer=None):
        self.data_service_client = data_service_client
        self.cache_optimizer = cache_optimizer
        self.aggregator = DataAggregator()
        self.validator = DataValidator()
        self.optimizer = PerformanceOptimizer()
        
        # 配置参数
        self.max_batch_size = 1000
        self.cache_ttl = 30  # 30秒缓存
        self.retry_attempts = 3
        self.timeout = 10.0
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'processing_errors': 0,
            'avg_processing_time': 0.0
        }
        
        # 实时数据缓冲区
        self.real_time_buffer = defaultdict(deque)
        self.buffer_max_size = 1000
    
    async def get_latest_market_data(self, symbols: Union[str, List[str]], 
                                   fields: Optional[List[str]] = None,
                                   use_cache: bool = True,
                                   quality_filter: Optional[DataQuality] = None) -> BatchProcessingResult:
        """获取最新市场数据（增强版）"""
        start_time = time.time()
        
        # 标准化输入
        if isinstance(symbols, str):
            symbols = [symbols]
        
        if not symbols:
            return BatchProcessingResult(0, 0, 0, 0.0, [], ["No symbols provided"])
        
        self.stats['total_requests'] += 1
        
        try:
            # 批量处理
            results = []
            errors = []
            successful = 0
            failed = 0
            
            # 分批处理
            for i in range(0, len(symbols), self.optimizer.batch_size):
                batch_symbols = symbols[i:i + self.optimizer.batch_size]
                batch_result = await self._process_latest_data_batch(
                    batch_symbols, fields, use_cache, quality_filter
                )
                
                results.extend(batch_result.data)
                errors.extend(batch_result.errors)
                successful += batch_result.successful
                failed += batch_result.failed
            
            processing_time = time.time() - start_time
            self.optimizer.record_processing_time(processing_time)
            
            # 更新统计信息
            self._update_stats(processing_time)
            
            return BatchProcessingResult(
                total_requested=len(symbols),
                successful=successful,
                failed=failed,
                processing_time=processing_time,
                data=results,
                errors=errors
            )
            
        except Exception as e:
            self.stats['processing_errors'] += 1
            logger.error(f"Error in get_latest_market_data: {e}")
            
            return BatchProcessingResult(
                total_requested=len(symbols),
                successful=0,
                failed=len(symbols),
                processing_time=time.time() - start_time,
                data=[],
                errors=[str(e)]
            )
    
    async def get_full_market_data(self, symbols: Union[str, List[str]] = None,
                                 market: str = "SH",
                                 data_types: List[MarketDataType] = None,
                                 include_suspended: bool = False,
                                 quality_threshold: DataQuality = DataQuality.MEDIUM) -> BatchProcessingResult:
        """获取完整市场数据（增强版）"""
        start_time = time.time()
        
        if data_types is None:
            data_types = [MarketDataType.REAL_TIME, MarketDataType.SNAPSHOT]
        
        try:
            # 如果没有指定symbols，获取市场所有股票
            if symbols is None:
                symbols = await self._get_market_symbols(market)
            elif isinstance(symbols, str):
                symbols = [symbols]
            
            # 并行获取不同类型的数据
            all_results = []
            all_errors = []
            total_successful = 0
            total_failed = 0
            
            for data_type in data_types:
                type_result = await self._get_data_by_type(
                    symbols, data_type, include_suspended, quality_threshold
                )
                
                all_results.extend(type_result.data)
                all_errors.extend(type_result.errors)
                total_successful += type_result.successful
                total_failed += type_result.failed
            
            # 数据去重和合并
            merged_data = self._merge_duplicate_data(all_results)
            
            processing_time = time.time() - start_time
            self.optimizer.record_processing_time(processing_time)
            
            return BatchProcessingResult(
                total_requested=len(symbols) * len(data_types),
                successful=total_successful,
                failed=total_failed,
                processing_time=processing_time,
                data=merged_data,
                errors=all_errors
            )
            
        except Exception as e:
            self.stats['processing_errors'] += 1
            logger.error(f"Error in get_full_market_data: {e}")
            
            return BatchProcessingResult(
                total_requested=len(symbols) if symbols else 0,
                successful=0,
                failed=len(symbols) if symbols else 0,
                processing_time=time.time() - start_time,
                data=[],
                errors=[str(e)]
            )
    
    async def get_real_time_stream(self, symbols: List[str],
                                 callback=None,
                                 buffer_size: int = 100) -> asyncio.Queue:
        """获取实时数据流"""
        stream_queue = asyncio.Queue(maxsize=buffer_size)
        
        async def stream_worker():
            while True:
                try:
                    # 获取实时数据
                    result = await self.get_latest_market_data(symbols, use_cache=False)
                    
                    for data_point in result.data:
                        # 添加到缓冲区
                        self._add_to_buffer(data_point)
                        
                        # 发送到队列
                        if not stream_queue.full():
                            await stream_queue.put(data_point)
                        
                        # 调用回调函数
                        if callback:
                            await callback(data_point)
                    
                    await asyncio.sleep(1)  # 1秒间隔
                    
                except Exception as e:
                    logger.error(f"Error in real-time stream: {e}")
                    await asyncio.sleep(5)  # 错误时等待5秒
        
        # 启动流处理任务
        asyncio.create_task(stream_worker())
        
        return stream_queue
    
    async def get_aggregated_data(self, symbols: List[str],
                                interval: str = "1min",
                                start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None) -> List[MarketDataPoint]:
        """获取聚合数据"""
        # 从缓冲区获取历史数据
        all_data = []
        
        for symbol in symbols:
            if symbol in self.real_time_buffer:
                symbol_data = list(self.real_time_buffer[symbol])
                
                # 时间过滤
                if start_time or end_time:
                    filtered_data = []
                    for point in symbol_data:
                        point_time = datetime.fromtimestamp(point.timestamp)
                        
                        if start_time and point_time < start_time:
                            continue
                        if end_time and point_time > end_time:
                            continue
                        
                        filtered_data.append(point)
                    
                    symbol_data = filtered_data
                
                all_data.extend(symbol_data)
        
        # 聚合数据
        return self.aggregator.aggregate_data(all_data, interval)
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        cache_hit_rate = 0.0
        if self.stats['total_requests'] > 0:
            cache_hit_rate = self.stats['cache_hits'] / self.stats['total_requests']
        
        return {
            **self.stats,
            'cache_hit_rate': cache_hit_rate,
            'current_batch_size': self.optimizer.batch_size,
            'buffer_sizes': {
                symbol: len(buffer) 
                for symbol, buffer in self.real_time_buffer.items()
            },
            'recent_processing_times': list(self.optimizer.processing_times)[-10:]
        }
    
    async def optimize_performance(self) -> Dict[str, Any]:
        """优化性能"""
        optimization_results = {
            'cache_optimization': {},
            'batch_size_adjustment': self.optimizer.batch_size,
            'buffer_cleanup': 0,
            'recommendations': []
        }
        
        # 缓存优化
        if self.cache_optimizer:
            cache_results = await self.cache_optimizer.optimize_cache()
            optimization_results['cache_optimization'] = cache_results
        
        # 清理过期缓冲区数据
        cleaned_count = self._cleanup_buffers()
        optimization_results['buffer_cleanup'] = cleaned_count
        
        # 生成性能建议
        recommendations = self._generate_performance_recommendations()
        optimization_results['recommendations'] = recommendations
        
        return optimization_results
    
    # 私有方法
    async def _process_latest_data_batch(self, symbols: List[str], 
                                       fields: Optional[List[str]],
                                       use_cache: bool,
                                       quality_filter: Optional[DataQuality]) -> BatchProcessingResult:
        """处理最新数据批次"""
        results = []
        errors = []
        successful = 0
        failed = 0
        
        # 并行获取数据
        fetch_tasks = []
        for symbol in symbols:
            task = self._fetch_single_latest_data(symbol, fields, use_cache)
            fetch_tasks.append(task)
        
        # 等待所有任务完成
        completed_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        for i, result in enumerate(completed_results):
            symbol = symbols[i]
            
            if isinstance(result, Exception):
                errors.append(f"Error fetching {symbol}: {str(result)}")
                failed += 1
                continue
            
            if result is None:
                errors.append(f"No data available for {symbol}")
                failed += 1
                continue
            
            # 验证数据质量
            is_valid, validation_errors = self.validator.validate_data_point(result)
            if not is_valid:
                errors.extend([f"{symbol}: {error}" for error in validation_errors])
                failed += 1
                continue
            
            # 评估数据质量
            result.quality = self.validator.assess_data_quality(result)
            
            # 质量过滤
            if quality_filter and result.quality.value < quality_filter.value:
                errors.append(f"{symbol}: Data quality {result.quality.value} below threshold")
                failed += 1
                continue
            
            results.append(result)
            successful += 1
        
        return BatchProcessingResult(
            total_requested=len(symbols),
            successful=successful,
            failed=failed,
            processing_time=0.0,  # 在上层计算
            data=results,
            errors=errors
        )
    
    async def _fetch_single_latest_data(self, symbol: str, 
                                      fields: Optional[List[str]],
                                      use_cache: bool) -> Optional[MarketDataPoint]:
        """获取单个股票的最新数据"""
        cache_key = f"latest_market_data:{symbol}"
        
        # 尝试从缓存获取
        if use_cache and self.cache_optimizer:
            cached_data = await self.cache_optimizer.get(cache_key)
            if cached_data:
                self.stats['cache_hits'] += 1
                return MarketDataPoint.from_dict(cached_data)
        
        self.stats['cache_misses'] += 1
        
        # 从数据服务获取
        try:
            if self.data_service_client:
                # 调用实际的数据服务
                raw_data = await self._call_data_service(symbol, fields)
                if raw_data:
                    data_point = self._convert_to_market_data_point(symbol, raw_data)
                    
                    # 缓存数据
                    if use_cache and self.cache_optimizer:
                        await self.cache_optimizer.set(
                            cache_key, 
                            data_point.to_dict(), 
                            custom_ttl=self.cache_ttl
                        )
                    
                    return data_point
            
            # 模拟数据（用于测试）
            return self._generate_mock_data(symbol)
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    async def _call_data_service(self, symbol: str, fields: Optional[List[str]]) -> Optional[Dict]:
        """调用数据服务"""
        if not self.data_service_client:
            return None
        
        try:
            # 这里应该调用实际的数据服务API
            # 暂时返回None，让它使用模拟数据
            return None
        except Exception as e:
            logger.error(f"Data service call failed for {symbol}: {e}")
            return None
    
    def _convert_to_market_data_point(self, symbol: str, raw_data: Dict) -> MarketDataPoint:
        """转换原始数据为MarketDataPoint"""
        return MarketDataPoint(
            symbol=symbol,
            timestamp=time.time(),
            price=raw_data.get('price', 0.0),
            volume=raw_data.get('volume', 0),
            bid_price=raw_data.get('bid_price', 0.0),
            ask_price=raw_data.get('ask_price', 0.0),
            bid_volume=raw_data.get('bid_volume', 0),
            ask_volume=raw_data.get('ask_volume', 0),
            open_price=raw_data.get('open_price', 0.0),
            high_price=raw_data.get('high_price', 0.0),
            low_price=raw_data.get('low_price', 0.0),
            prev_close=raw_data.get('prev_close', 0.0),
            change=raw_data.get('change', 0.0),
            change_pct=raw_data.get('change_pct', 0.0),
            turnover=raw_data.get('turnover', 0.0),
            data_type=MarketDataType.REAL_TIME
        )
    
    def _generate_mock_data(self, symbol: str) -> MarketDataPoint:
        """生成模拟数据"""
        import random
        
        base_price = 10.0 + random.random() * 90.0
        change_pct = (random.random() - 0.5) * 20.0  # -10% to +10%
        
        return MarketDataPoint(
            symbol=symbol,
            timestamp=time.time(),
            price=base_price,
            volume=random.randint(1000, 1000000),
            bid_price=base_price * 0.999,
            ask_price=base_price * 1.001,
            bid_volume=random.randint(100, 10000),
            ask_volume=random.randint(100, 10000),
            open_price=base_price * 0.995,
            high_price=base_price * 1.05,
            low_price=base_price * 0.95,
            prev_close=base_price / (1 + change_pct / 100),
            change=base_price - (base_price / (1 + change_pct / 100)),
            change_pct=change_pct,
            turnover=base_price * random.randint(1000, 1000000),
            data_type=MarketDataType.REAL_TIME,
            quality=DataQuality.HIGH
        )
    
    async def _get_market_symbols(self, market: str) -> List[str]:
        """获取市场所有股票代码"""
        # 这里应该从实际的数据源获取
        # 暂时返回一些示例股票代码
        if market == "SH":
            return ["000001.SH", "000002.SH", "600000.SH", "600036.SH", "600519.SH"]
        elif market == "SZ":
            return ["000001.SZ", "000002.SZ", "300001.SZ", "300015.SZ", "002415.SZ"]
        else:
            return []
    
    async def _get_data_by_type(self, symbols: List[str], 
                              data_type: MarketDataType,
                              include_suspended: bool,
                              quality_threshold: DataQuality) -> BatchProcessingResult:
        """按类型获取数据"""
        # 根据数据类型调用不同的获取方法
        if data_type == MarketDataType.REAL_TIME:
            return await self.get_latest_market_data(
                symbols, 
                quality_filter=quality_threshold
            )
        else:
            # 其他数据类型的处理逻辑
            return BatchProcessingResult(0, 0, 0, 0.0, [], [])
    
    def _merge_duplicate_data(self, data_points: List[MarketDataPoint]) -> List[MarketDataPoint]:
        """合并重复数据"""
        # 按symbol分组，保留最新的数据
        symbol_data = {}
        
        for point in data_points:
            if (point.symbol not in symbol_data or 
                point.timestamp > symbol_data[point.symbol].timestamp):
                symbol_data[point.symbol] = point
        
        return list(symbol_data.values())
    
    def _add_to_buffer(self, data_point: MarketDataPoint):
        """添加到实时缓冲区"""
        buffer = self.real_time_buffer[data_point.symbol]
        buffer.append(data_point)
        
        # 保持缓冲区大小
        while len(buffer) > self.buffer_max_size:
            buffer.popleft()
    
    def _cleanup_buffers(self) -> int:
        """清理过期缓冲区数据"""
        cleaned_count = 0
        current_time = time.time()
        
        for symbol, buffer in self.real_time_buffer.items():
            original_size = len(buffer)
            
            # 移除1小时前的数据
            while buffer and current_time - buffer[0].timestamp > 3600:
                buffer.popleft()
                cleaned_count += 1
        
        return cleaned_count
    
    def _update_stats(self, processing_time: float):
        """更新统计信息"""
        if self.stats['total_requests'] == 1:
            self.stats['avg_processing_time'] = processing_time
        else:
            # 指数移动平均
            alpha = 0.1
            self.stats['avg_processing_time'] = (
                alpha * processing_time + 
                (1 - alpha) * self.stats['avg_processing_time']
            )
    
    def _generate_performance_recommendations(self) -> List[str]:
        """生成性能建议"""
        recommendations = []
        
        # 缓存命中率建议
        cache_hit_rate = self.stats['cache_hits'] / max(1, self.stats['total_requests'])
        if cache_hit_rate < 0.5:
            recommendations.append("缓存命中率较低，建议增加缓存时间或优化缓存策略")
        
        # 处理时间建议
        if self.stats['avg_processing_time'] > 2.0:
            recommendations.append("平均处理时间较长，建议优化批处理大小或增加并发数")
        
        # 错误率建议
        error_rate = self.stats['processing_errors'] / max(1, self.stats['total_requests'])
        if error_rate > 0.1:
            recommendations.append("错误率较高，建议检查数据源连接或增加重试机制")
        
        return recommendations

# 全局实例
_market_data_processor: Optional[EnhancedMarketDataProcessor] = None

def get_market_data_processor() -> EnhancedMarketDataProcessor:
    """获取市场数据处理器实例"""
    global _market_data_processor
    if _market_data_processor is None:
        _market_data_processor = EnhancedMarketDataProcessor()
    return _market_data_processor

async def init_market_data_processor(data_service_client=None, 
                                   cache_optimizer=None) -> EnhancedMarketDataProcessor:
    """初始化市场数据处理器"""
    global _market_data_processor
    _market_data_processor = EnhancedMarketDataProcessor(
        data_service_client=data_service_client,
        cache_optimizer=cache_optimizer
    )
    return _market_data_processor