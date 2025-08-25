"""
智能缓存策略和预热系统

提供智能的缓存管理策略，包括预热、热点数据识别和自适应TTL
"""

import asyncio
import time
from datetime import datetime, timedeltafrom ty
ping import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
import heapq

from src.argus_mcp.cache.historical_data_cache import HistoricalDataCache
from src.argus_mcp.monitoring.historical_performance_monitor import get_historical_performance_monitor
from src.argus_mcp.data_models.historical_data import SupportedPeriod

logger = logging.getLogger(__name__)


@dataclass
class HotDataPattern:
    """热点数据模式"""
    symbol: str
    period: str
    access_count: int = 0
    last_access: datetime = field(default_factory=datetime.now)
    access_frequency: float = 0.0  # 每小时访问次数
    priority_score: float = 0.0
    
    def update_access(self) -> None:
        """更新访问信息"""
        now = datetime.now()
        time_diff = (now - self.last_access).total_seconds() / 3600  # 小时
        
        self.access_count += 1
        self.last_access = now
        
        if time_diff > 0:
            self.access_frequency = self.access_count / time_diff
        
        # 计算优先级分数（考虑访问频率和最近访问时间）
        recency_factor = max(0, 1 - time_diff / 24)  # 24小时内的访问权重更高
        self.priority_score = self.access_frequency * (1 + recency_factor)


@dataclass
class CachePrewarmConfig:
    """缓存预热配置"""
    enabled: bool = True
    max_concurrent_preloads: int = 5
    preload_schedule_hours: List[int] = field(default_factory=lambda: [8, 12, 18])  # 预热时间点
    hot_data_threshold: int = 10  # 热点数据访问次数阈值
    preload_symbols: List[str] = field(default_factory=lambda: [
        '000001.SZ', '000002.SZ', '600000.SH', '600036.SH', '000858.SZ'
    ])
    preload_periods: List[str] = field(default_factory=lambda: ['1d', '1h', '5m'])
    preload_date_range_days: int = 30  # 预热数据的日期范围


class IntelligentCacheStrategy:
    """智能缓存策略管理器"""
    
    def __init__(
        self,
        cache: Optional[HistoricalDataCache] = None,
        config: Optional[CachePrewarmConfig] = None
    ):
        self.cache = cache or HistoricalDataCache()
        self.config = config or CachePrewarmConfig()
        self.monitor = get_historical_performance_monitor()
        
        # 热点数据跟踪
        self.hot_data_patterns: Dict[str, HotDataPattern] = {}
        self.access_history = deque(maxlen=10000)
        
        # 预热状态
        self.prewarming_active = False
        self.last_prewarm_time: Optional[datetime] = None
        self.preload_executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_preloads)
        
        # 自适应TTL
        self.adaptive_ttl_enabled = True
        self.ttl_adjustments: Dict[str, float] = defaultdict(lambda: 1.0)  # TTL调整因子
        
        # 线程安全
        self._lock = threading.Lock()
        
        # 启动后台任务
        self._start_background_tasks()
        
        logger.info("Intelligent cache strategy initialized")
    
    def _start_background_tasks(self) -> None:
        """启动后台任务"""
        # 启动预热调度器
        if self.config.enabled:
            asyncio.create_task(self._prewarm_scheduler())
        
        # 启动热点数据分析器
        asyncio.create_task(self._hot_data_analyzer())
    
    async def _prewarm_scheduler(self) -> None:
        """预热调度器"""
        while True:
            try:
                current_hour = datetime.now().hour
                
                if current_hour in self.config.preload_schedule_hours:
                    if (self.last_prewarm_time is None or 
                        datetime.now() - self.last_prewarm_time > timedelta(hours=1)):
                        
                        await self.prewarm_cache()
                        self.last_prewarm_time = datetime.now()
                
                # 每小时检查一次
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in prewarm scheduler: {e}")
                await asyncio.sleep(300)  # 出错后5分钟重试
    
    async def _hot_data_analyzer(self) -> None:
        """热点数据分析器"""
        while True:
            try:
                await self._analyze_access_patterns()
                await self._adjust_adaptive_ttl()
                
                # 每10分钟分析一次
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"Error in hot data analyzer: {e}")
                await asyncio.sleep(300)
    
    def record_access(self, symbol: str, period: str, cache_hit: bool = False) -> None:
        """记录数据访问"""
        with self._lock:
            key = f"{symbol}_{period}"
            
            # 更新热点数据模式
            if key not in self.hot_data_patterns:
                self.hot_data_patterns[key] = HotDataPattern(symbol=symbol, period=period)
            
            self.hot_data_patterns[key].update_access()
            
            # 记录访问历史
            self.access_history.append({
                'timestamp': datetime.now(),
                'symbol': symbol,
                'period': period,
                'cache_hit': cache_hit
            })
    
    async def _analyze_access_patterns(self) -> None:
        """分析访问模式"""
        with self._lock:
            # 清理过期的热点数据模式
            cutoff_time = datetime.now() - timedelta(days=7)
            expired_keys = [
                key for key, pattern in self.hot_data_patterns.items()
                if pattern.last_access < cutoff_time
            ]
            
            for key in expired_keys:
                del self.hot_data_patterns[key]
            
            # 识别新的热点数据
            hot_patterns = [
                pattern for pattern in self.hot_data_patterns.values()
                if pattern.access_count >= self.config.hot_data_threshold
            ]
            
            # 按优先级排序
            hot_patterns.sort(key=lambda x: x.priority_score, reverse=True)
            
            logger.info(f"Identified {len(hot_patterns)} hot data patterns")
            
            # 触发热点数据预加载
            if hot_patterns:
                await self._preload_hot_data(hot_patterns[:20])  # 预加载前20个热点
    
    async def _preload_hot_data(self, hot_patterns: List[HotDataPattern]) -> None:
        """预加载热点数据"""
        if self.prewarming_active:
            return
        
        self.prewarming_active = True
        
        try:
            tasks = []
            for pattern in hot_patterns:
                task = self._preload_single_pattern(pattern)
                tasks.append(task)
            
            # 限制并发数
            semaphore = asyncio.Semaphore(self.config.max_concurrent_preloads)
            
            async def limited_preload(task):
                async with semaphore:
                    return await task
            
            await asyncio.gather(*[limited_preload(task) for task in tasks], return_exceptions=True)
            
        finally:
            self.prewarming_active = False
    
    async def _preload_single_pattern(self, pattern: HotDataPattern) -> None:
        """预加载单个模式的数据"""
        try:
            # 计算预加载的日期范围
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=self.config.preload_date_range_days)
            
            # 检查缓存中是否已存在
            cache_key = self.cache._generate_cache_key(
                pattern.symbol,
                start_date.isoformat(),
                end_date.isoformat(),
                pattern.period
            )
            
            if await self.cache.get_cached_data(cache_key):
                return  # 已缓存，跳过
            
            # 从API获取数据并缓存
            from src.argus_mcp.api.enhanced_historical_api import EnhancedHistoricalDataAPI
            api = EnhancedHistoricalDataAPI()
            
            result = await api.get_historical_data(
                symbol=pattern.symbol,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                period=pattern.period
            )
            
            logger.info(f"Preloaded data for {pattern.symbol} {pattern.period}")
            
        except Exception as e:
            logger.error(f"Failed to preload {pattern.symbol} {pattern.period}: {e}")
    
    async def prewarm_cache(self) -> None:
        """执行缓存预热"""
        if self.prewarming_active:
            logger.info("Cache prewarming already in progress")
            return
        
        logger.info("Starting cache prewarming")
        self.prewarming_active = True
        
        try:
            tasks = []
            
            # 预热配置中的固定数据
            for symbol in self.config.preload_symbols:
                for period in self.config.preload_periods:
                    task = self._preload_symbol_period(symbol, period)
                    tasks.append(task)
            
            # 限制并发数
            semaphore = asyncio.Semaphore(self.config.max_concurrent_preloads)
            
            async def limited_preload(task):
                async with semaphore:
                    return await task
            
            results = await asyncio.gather(
                *[limited_preload(task) for task in tasks],
                return_exceptions=True
            )
            
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            error_count = len(results) - success_count
            
            logger.info(f"Cache prewarming completed: {success_count} success, {error_count} errors")
            
        finally:
            self.prewarming_active = False
    
    async def _preload_symbol_period(self, symbol: str, period: str) -> None:
        """预加载指定股票和周期的数据"""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=self.config.preload_date_range_days)
            
            from src.argus_mcp.api.enhanced_historical_api import EnhancedHistoricalDataAPI
            api = EnhancedHistoricalDataAPI()
            
            await api.get_historical_data(
                symbol=symbol,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                period=period
            )
            
        except Exception as e:
            logger.error(f"Failed to preload {symbol} {period}: {e}")
            raise
    
    async def _adjust_adaptive_ttl(self) -> None:
        """调整自适应TTL"""
        if not self.adaptive_ttl_enabled:
            return
        
        with self._lock:
            # 分析缓存命中率
            recent_accesses = [
                access for access in self.access_history
                if datetime.now() - access['timestamp'] < timedelta(hours=1)
            ]
            
            if len(recent_accesses) < 10:
                return
            
            # 按周期分组分析
            period_stats = defaultdict(lambda: {'hits': 0, 'total': 0})
            
            for access in recent_accesses:
                period = access['period']
                period_stats[period]['total'] += 1
                if access['cache_hit']:
                    period_stats[period]['hits'] += 1
            
            # 调整TTL因子
            for period, stats in period_stats.items():
                hit_rate = stats['hits'] / stats['total'] if stats['total'] > 0 else 0
                
                if hit_rate > 0.9:
                    # 命中率很高，可以延长TTL
                    self.ttl_adjustments[period] = min(2.0, self.ttl_adjustments[period] * 1.1)
                elif hit_rate < 0.5:
                    # 命中率较低，缩短TTL
                    self.ttl_adjustments[period] = max(0.5, self.ttl_adjustments[period] * 0.9)
    
    def get_adaptive_ttl(self, period: str, base_ttl: int) -> int:
        """获取自适应TTL"""
        if not self.adaptive_ttl_enabled:
            return base_ttl
        
        adjustment_factor = self.ttl_adjustments.get(period, 1.0)
        return int(base_ttl * adjustment_factor)
    
    def get_hot_data_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取热点数据推荐"""
        with self._lock:
            hot_patterns = sorted(
                self.hot_data_patterns.values(),
                key=lambda x: x.priority_score,
                reverse=True
            )
            
            return [
                {
                    'symbol': pattern.symbol,
                    'period': pattern.period,
                    'access_count': pattern.access_count,
                    'access_frequency': pattern.access_frequency,
                    'priority_score': pattern.priority_score,
                    'last_access': pattern.last_access.isoformat()
                }
                for pattern in hot_patterns[:limit]
            ]
    
    def get_cache_strategy_stats(self) -> Dict[str, Any]:
        """获取缓存策略统计"""
        with self._lock:
            return {
                'hot_data_patterns_count': len(self.hot_data_patterns),
                'access_history_size': len(self.access_history),
                'prewarming_active': self.prewarming_active,
                'last_prewarm_time': self.last_prewarm_time.isoformat() if self.last_prewarm_time else None,
                'adaptive_ttl_enabled': self.adaptive_ttl_enabled,
                'ttl_adjustments': dict(self.ttl_adjustments),
                'config': {
                    'enabled': self.config.enabled,
                    'max_concurrent_preloads': self.config.max_concurrent_preloads,
                    'preload_schedule_hours': self.config.preload_schedule_hours,
                    'hot_data_threshold': self.config.hot_data_threshold,
                    'preload_date_range_days': self.config.preload_date_range_days
                }
            }
    
    async def optimize_cache_performance(self) -> Dict[str, Any]:
        """优化缓存性能"""
        logger.info("Starting cache performance optimization")
        
        optimization_results = {
            'timestamp': datetime.now().isoformat(),
            'actions_taken': [],
            'performance_impact': {}
        }
        
        # 1. 清理过期缓存
        try:
            await self.cache.cleanup_expired_cache()
            optimization_results['actions_taken'].append('cleaned_expired_cache')
        except Exception as e:
            logger.error(f"Failed to clean expired cache: {e}")
        
        # 2. 预热热点数据
        try:
            hot_patterns = [
                pattern for pattern in self.hot_data_patterns.values()
                if pattern.priority_score > 5.0
            ]
            
            if hot_patterns:
                await self._preload_hot_data(hot_patterns[:10])
                optimization_results['actions_taken'].append(f'preloaded_{len(hot_patterns)}_hot_patterns')
        except Exception as e:
            logger.error(f"Failed to preload hot data: {e}")
        
        # 3. 调整TTL策略
        try:
            await self._adjust_adaptive_ttl()
            optimization_results['actions_taken'].append('adjusted_adaptive_ttl')
        except Exception as e:
            logger.error(f"Failed to adjust TTL: {e}")
        
        # 4. 获取性能指标
        try:
            performance_summary = self.monitor.get_performance_summary()
            optimization_results['performance_impact'] = {
                'cache_hit_rate': performance_summary.get('cache_performance', {}).get('hit_rate', 0),
                'avg_response_time': performance_summary.get('response_time', {}).get('avg', 0),
                'total_requests': performance_summary.get('total_requests', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
        
        logger.info(f"Cache optimization completed: {len(optimization_results['actions_taken'])} actions taken")
        return optimization_results


# 全局智能缓存策略实例
_global_cache_strategy: Optional[IntelligentCacheStrategy] = None

def get_intelligent_cache_strategy() -> IntelligentCacheStrategy:
    """获取全局智能缓存策略"""
    global _global_cache_strategy
    if _global_cache_strategy is None:
        _global_cache_strategy = IntelligentCacheStrategy()
    return _global_cache_strategy


# 便捷函数
async def optimize_cache_now() -> Dict[str, Any]:
    """立即优化缓存"""
    strategy = get_intelligent_cache_strategy()
    return await strategy.optimize_cache_performance()


async def prewarm_cache_now() -> None:
    """立即预热缓存"""
    strategy = get_intelligent_cache_strategy()
    await strategy.prewarm_cache()


def get_cache_recommendations() -> List[Dict[str, Any]]:
    """获取缓存优化建议"""
    strategy = get_intelligent_cache_strategy()
    return strategy.get_hot_data_recommendations()