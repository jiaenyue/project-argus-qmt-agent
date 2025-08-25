#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存预热服务
智能预加载常用数据，提高缓存命中率
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

from .cache_manager import get_cache_manager
from .advanced_cache_strategy import get_advanced_cache_strategy, CachePriority
from .xtquant_connection_pool import get_connection_pool
from .performance_optimizer import get_global_optimizer

logger = logging.getLogger(__name__)

@dataclass
class WarmupTask:
    """预热任务"""
    name: str
    function: Callable
    args: tuple = ()
    kwargs: dict = None
    priority: int = 1
    interval: int = 300  # 5分钟
    last_run: float = 0
    enabled: bool = True
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}
    
    def should_run(self) -> bool:
        """检查是否应该运行"""
        if not self.enabled:
            return False
        return time.time() - self.last_run >= self.interval
    
    def mark_run(self):
        """标记已运行"""
        self.last_run = time.time()

class CacheWarmupService:
    """缓存预热服务"""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.advanced_cache = get_advanced_cache_strategy()
        self.connection_pool = get_connection_pool()
        self.performance_optimizer = get_global_optimizer()
        
        # 预热任务
        self.warmup_tasks: Dict[str, WarmupTask] = {}
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="warmup")
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'total_warmups': 0,
            'successful_warmups': 0,
            'failed_warmups': 0,
            'last_warmup_time': None,
            'warmup_duration': 0
        }
        
        # 注册默认预热任务
        self._register_default_tasks()
    
    def _register_default_tasks(self):
        """注册默认预热任务"""
        # 预热热门股票数据
        self.register_task(
            "popular_stocks",
            self._warmup_popular_stocks,
            priority=1,
            interval=300  # 5分钟
        )
        
        # 预热市场指数数据
        self.register_task(
            "market_indices",
            self._warmup_market_indices,
            priority=2,
            interval=600  # 10分钟
        )
        
        # 预热交易日历
        self.register_task(
            "trading_calendar",
            self._warmup_trading_calendar,
            priority=3,
            interval=3600  # 1小时
        )
        
        # 预热板块数据
        self.register_task(
            "sector_data",
            self._warmup_sector_data,
            priority=4,
            interval=1800  # 30分钟
        )
    
    def register_task(
        self,
        name: str,
        function: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: int = 1,
        interval: int = 300,
        enabled: bool = True
    ):
        """注册预热任务"""
        with self.lock:
            task = WarmupTask(
                name=name,
                function=function,
                args=args,
                kwargs=kwargs or {},
                priority=priority,
                interval=interval,
                enabled=enabled
            )
            self.warmup_tasks[name] = task
            logger.info(f"注册预热任务: {name}")
    
    def unregister_task(self, name: str):
        """注销预热任务"""
        with self.lock:
            if name in self.warmup_tasks:
                del self.warmup_tasks[name]
                logger.info(f"注销预热任务: {name}")
    
    def enable_task(self, name: str):
        """启用预热任务"""
        with self.lock:
            if name in self.warmup_tasks:
                self.warmup_tasks[name].enabled = True
                logger.info(f"启用预热任务: {name}")
    
    def disable_task(self, name: str):
        """禁用预热任务"""
        with self.lock:
            if name in self.warmup_tasks:
                self.warmup_tasks[name].enabled = False
                logger.info(f"禁用预热任务: {name}")
    
    async def start(self):
        """启动预热服务"""
        if self.running:
            return
        
        self.running = True
        logger.info("启动缓存预热服务")
        
        # 启动预热循环
        asyncio.create_task(self._warmup_loop())
    
    async def stop(self):
        """停止预热服务"""
        self.running = False
        self.executor.shutdown(wait=True)
        logger.info("停止缓存预热服务")
    
    async def _warmup_loop(self):
        """预热循环"""
        while self.running:
            try:
                await self._run_warmup_tasks()
                await asyncio.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"预热循环发生错误: {e}")
                await asyncio.sleep(60)
    
    async def _run_warmup_tasks(self):
        """运行预热任务"""
        start_time = time.time()
        
        with self.lock:
            # 获取需要运行的任务
            tasks_to_run = [
                task for task in self.warmup_tasks.values()
                if task.should_run()
            ]
        
        if not tasks_to_run:
            return
        
        # 按优先级排序
        tasks_to_run.sort(key=lambda x: x.priority)
        
        logger.info(f"开始运行 {len(tasks_to_run)} 个预热任务")
        
        # 并发运行任务
        tasks = []
        for task in tasks_to_run:
            tasks.append(self._run_single_task(task))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        
        self.stats['total_warmups'] += len(tasks_to_run)
        self.stats['successful_warmups'] += successful
        self.stats['failed_warmups'] += failed
        self.stats['last_warmup_time'] = datetime.now().isoformat()
        self.stats['warmup_duration'] = time.time() - start_time
        
        logger.info(f"预热任务完成: 成功 {successful}, 失败 {failed}, 耗时 {self.stats['warmup_duration']:.2f}s")
    
    async def _run_single_task(self, task: WarmupTask):
        """运行单个预热任务"""
        try:
            logger.debug(f"运行预热任务: {task.name}")
            
            # 在线程池中运行任务
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                task.function,
                *task.args,
                **task.kwargs
            )
            
            task.mark_run()
            logger.debug(f"预热任务完成: {task.name}")
            
        except Exception as e:
            logger.error(f"预热任务失败 {task.name}: {e}")
            raise
    
    def _warmup_popular_stocks(self):
        """预热热门股票数据"""
        try:
            # 热门股票列表
            popular_stocks = [
                '000001.SZ',  # 平安银行
                '000002.SZ',  # 万科A
                '600000.SH',  # 浦发银行
                '600036.SH',  # 招商银行
                '600519.SH',  # 贵州茅台
                '000858.SZ',  # 五粮液
                '002415.SZ',  # 海康威视
                '300059.SZ',  # 东方财富
                '600276.SH',  # 恒瑞医药
                '000725.SZ'   # 京东方A
            ]
            
            with self.connection_pool.get_connection() as conn:
                if not conn or conn.status.name != 'CONNECTED':
                    logger.warning("QMT连接不可用，跳过预热")
                    return
                
                from xtquant import xtdata
                
                # 预热最新行情数据
                for symbol in popular_stocks:
                    try:
                        # 获取最新行情
                        market_data = xtdata.get_market_data(
                            ['open', 'high', 'low', 'close', 'volume'],
                            [symbol],
                            period='1d',
                            count=1
                        )
                        
                        if market_data:
                            # 存储到高级缓存
                            cache_key = f"market_data:{symbol}:latest"
                            asyncio.create_task(
                                self.advanced_cache.set(
                                    cache_key,
                                    market_data,
                                    ttl=60,  # 1分钟
                                    priority=CachePriority.HIGH,
                                    tags=['market_data', 'popular']
                                )
                            )
                        
                        # 获取完整行情数据
                        full_data = xtdata.get_full_market_data(
                            ['open', 'high', 'low', 'close', 'volume'],
                            [symbol]
                        )
                        
                        if full_data:
                            cache_key = f"full_market_data:{symbol}"
                            asyncio.create_task(
                                self.advanced_cache.set(
                                    cache_key,
                                    full_data,
                                    ttl=60,  # 1分钟
                                    priority=CachePriority.HIGH,
                                    tags=['full_market_data', 'popular']
                                )
                            )
                        
                    except Exception as e:
                        logger.warning(f"预热股票 {symbol} 数据失败: {e}")
                        continue
                
                logger.info(f"预热了 {len(popular_stocks)} 只热门股票数据")
                
        except Exception as e:
            logger.error(f"预热热门股票数据失败: {e}")
            raise
    
    def _warmup_market_indices(self):
        """预热市场指数数据"""
        try:
            # 主要指数
            indices = [
                '000001.SH',  # 上证指数
                '399001.SZ',  # 深证成指
                '399006.SZ',  # 创业板指
                '000300.SH',  # 沪深300
                '000905.SH',  # 中证500
                '000852.SH'   # 中证1000
            ]
            
            with self.connection_pool.get_connection() as conn:
                if not conn or conn.status.name != 'CONNECTED':
                    logger.warning("QMT连接不可用，跳过预热")
                    return
                
                from xtquant import xtdata
                
                for index in indices:
                    try:
                        # 获取指数数据
                        index_data = xtdata.get_market_data(
                            ['open', 'high', 'low', 'close', 'volume'],
                            [index],
                            period='1d',
                            count=5  # 最近5天
                        )
                        
                        if index_data:
                            cache_key = f"index_data:{index}:5d"
                            asyncio.create_task(
                                self.advanced_cache.set(
                                    cache_key,
                                    index_data,
                                    ttl=600,  # 10分钟
                                    priority=CachePriority.MEDIUM,
                                    tags=['index_data', 'market']
                                )
                            )
                        
                    except Exception as e:
                        logger.warning(f"预热指数 {index} 数据失败: {e}")
                        continue
                
                logger.info(f"预热了 {len(indices)} 个市场指数数据")
                
        except Exception as e:
            logger.error(f"预热市场指数数据失败: {e}")
            raise
    
    def _warmup_trading_calendar(self):
        """预热交易日历"""
        try:
            with self.connection_pool.get_connection() as conn:
                if not conn or conn.status.name != 'CONNECTED':
                    logger.warning("QMT连接不可用，跳过预热")
                    return
                
                from xtquant import xtdata
                
                markets = ['SH', 'SZ']
                
                for market in markets:
                    try:
                        # 获取最近30个交易日
                        trading_dates = xtdata.get_trading_dates(market, count=30)
                        
                        if trading_dates:
                            cache_key = f"trading_dates:{market}:30d"
                            asyncio.create_task(
                                self.advanced_cache.set(
                                    cache_key,
                                    trading_dates,
                                    ttl=3600,  # 1小时
                                    priority=CachePriority.MEDIUM,
                                    tags=['trading_dates', 'calendar']
                                )
                            )
                        
                        # 获取未来30个交易日（如果支持）
                        try:
                            future_dates = xtdata.get_trading_dates(
                                market,
                                start_time=datetime.now().strftime('%Y%m%d'),
                                count=30
                            )
                            
                            if future_dates:
                                cache_key = f"trading_dates:{market}:future_30d"
                                asyncio.create_task(
                                    self.advanced_cache.set(
                                        cache_key,
                                        future_dates,
                                        ttl=3600,  # 1小时
                                        priority=CachePriority.LOW,
                                        tags=['trading_dates', 'future']
                                    )
                                )
                        except Exception:
                            pass  # 忽略未来日期获取失败
                        
                    except Exception as e:
                        logger.warning(f"预热市场 {market} 交易日历失败: {e}")
                        continue
                
                logger.info(f"预热了 {len(markets)} 个市场的交易日历")
                
        except Exception as e:
            logger.error(f"预热交易日历失败: {e}")
            raise
    
    def _warmup_sector_data(self):
        """预热板块数据"""
        try:
            # 主要板块
            sectors = [
                '银行',
                '证券',
                '保险',
                '房地产',
                '医药生物',
                '食品饮料',
                '电子',
                '计算机',
                '通信',
                '新能源'
            ]
            
            with self.connection_pool.get_connection() as conn:
                if not conn or conn.status.name != 'CONNECTED':
                    logger.warning("QMT连接不可用，跳过预热")
                    return
                
                from xtquant import xtdata
                
                for sector in sectors:
                    try:
                        # 获取板块股票列表
                        stock_list = xtdata.get_stock_list_in_sector(sector)
                        
                        if stock_list:
                            cache_key = f"sector_stocks:{sector}"
                            asyncio.create_task(
                                self.advanced_cache.set(
                                    cache_key,
                                    stock_list,
                                    ttl=1800,  # 30分钟
                                    priority=CachePriority.LOW,
                                    tags=['sector_data', 'stocks']
                                )
                            )
                        
                    except Exception as e:
                        logger.warning(f"预热板块 {sector} 数据失败: {e}")
                        continue
                
                logger.info(f"预热了 {len(sectors)} 个板块数据")
                
        except Exception as e:
            logger.error(f"预热板块数据失败: {e}")
            raise
    
    async def manual_warmup(self, task_names: List[str] = None) -> Dict[str, Any]:
        """手动触发预热"""
        if task_names is None:
            task_names = list(self.warmup_tasks.keys())
        
        results = {}
        start_time = time.time()
        
        for task_name in task_names:
            if task_name not in self.warmup_tasks:
                results[task_name] = {'success': False, 'error': 'Task not found'}
                continue
            
            task = self.warmup_tasks[task_name]
            try:
                await self._run_single_task(task)
                results[task_name] = {'success': True}
            except Exception as e:
                results[task_name] = {'success': False, 'error': str(e)}
        
        duration = time.time() - start_time
        
        return {
            'results': results,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取预热统计信息"""
        with self.lock:
            task_stats = {}
            for name, task in self.warmup_tasks.items():
                task_stats[name] = {
                    'enabled': task.enabled,
                    'priority': task.priority,
                    'interval': task.interval,
                    'last_run': task.last_run,
                    'next_run': task.last_run + task.interval if task.enabled else None
                }
            
            return {
                'service_running': self.running,
                'total_tasks': len(self.warmup_tasks),
                'enabled_tasks': sum(1 for t in self.warmup_tasks.values() if t.enabled),
                'task_stats': task_stats,
                'warmup_stats': self.stats.copy()
            }
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息（异步版本）"""
        try:
            # 获取缓存管理器统计
            cache_stats = await self.cache_manager.get_stats()
            
            # 获取高级缓存统计
            advanced_stats = await self.advanced_cache.get_stats()
            
            # 获取预热服务统计
            warmup_stats = self.get_stats()
            
            return {
                'cache_manager': cache_stats,
                'advanced_cache': advanced_stats,
                'warmup_service': warmup_stats,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def clear_cache_by_pattern(self, pattern: str) -> int:
        """按模式清理缓存"""
        try:
            cleared_count = 0
            
            # 清理缓存管理器中的缓存
            if hasattr(self.cache_manager, 'clear_by_pattern'):
                cleared_count += await self.cache_manager.clear_by_pattern(pattern)
            
            # 清理高级缓存中的缓存
            if hasattr(self.advanced_cache, 'clear_by_pattern'):
                cleared_count += await self.advanced_cache.clear_by_pattern(pattern)
            
            return cleared_count
        except Exception as e:
            logger.error(f"按模式清理缓存失败: {e}")
            return 0
    
    async def clear_all_cache(self) -> int:
        """清理所有缓存"""
        try:
            cleared_count = 0
            
            # 清理缓存管理器中的缓存
            if hasattr(self.cache_manager, 'clear_all'):
                cleared_count += await self.cache_manager.clear_all()
            
            # 清理高级缓存中的缓存
            if hasattr(self.advanced_cache, 'clear_all'):
                cleared_count += await self.advanced_cache.clear_all()
            
            return cleared_count
        except Exception as e:
            logger.error(f"清理所有缓存失败: {e}")
            return 0
    
    async def optimize_cache(self) -> Dict[str, Any]:
        """优化缓存"""
        try:
            optimization_result = {
                'cache_manager': {},
                'advanced_cache': {},
                'timestamp': datetime.now().isoformat()
            }
            
            # 优化缓存管理器
            if hasattr(self.cache_manager, 'optimize'):
                optimization_result['cache_manager'] = await self.cache_manager.optimize()
            
            # 优化高级缓存
            if hasattr(self.advanced_cache, 'optimize'):
                optimization_result['advanced_cache'] = await self.advanced_cache.optimize()
            
            return optimization_result
        except Exception as e:
            logger.error(f"缓存优化失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    async def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        try:
            config = {
                'cache_manager': {},
                'advanced_cache': {},
                'warmup_service': {
                    'running': self.running,
                    'task_count': len(self.warmup_tasks)
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # 获取缓存管理器配置
            if hasattr(self.cache_manager, 'get_config'):
                config['cache_manager'] = await self.cache_manager.get_config()
            
            # 获取高级缓存配置
            if hasattr(self.advanced_cache, 'get_config'):
                config['advanced_cache'] = await self.advanced_cache.get_config()
            
            return config
        except Exception as e:
            logger.error(f"获取缓存配置失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    async def update_cache_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """更新缓存配置"""
        try:
            updated_config = {
                'cache_manager': {},
                'advanced_cache': {},
                'timestamp': datetime.now().isoformat()
            }
            
            # 更新缓存管理器配置
            if 'cache_manager' in config_dict and hasattr(self.cache_manager, 'update_config'):
                updated_config['cache_manager'] = await self.cache_manager.update_config(
                    config_dict['cache_manager']
                )
            
            # 更新高级缓存配置
            if 'advanced_cache' in config_dict and hasattr(self.advanced_cache, 'update_config'):
                updated_config['advanced_cache'] = await self.advanced_cache.update_config(
                    config_dict['advanced_cache']
                )
            
            return updated_config
        except Exception as e:
            logger.error(f"更新缓存配置失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    async def get_cache_keys(self, pattern: str = None, limit: int = 100) -> List[str]:
        """获取缓存键列表"""
        try:
            keys = []
            
            # 获取缓存管理器中的键
            if hasattr(self.cache_manager, 'get_keys'):
                cache_keys = await self.cache_manager.get_keys(pattern=pattern, limit=limit//2)
                keys.extend(cache_keys)
            
            # 获取高级缓存中的键
            if hasattr(self.advanced_cache, 'get_keys'):
                advanced_keys = await self.advanced_cache.get_keys(pattern=pattern, limit=limit//2)
                keys.extend(advanced_keys)
            
            # 去重并限制数量
            unique_keys = list(set(keys))
            return unique_keys[:limit]
        except Exception as e:
            logger.error(f"获取缓存键失败: {e}")
            return []

# 全局缓存预热服务实例
_cache_warmup_service: Optional[CacheWarmupService] = None

def get_cache_warmup_service() -> CacheWarmupService:
    """获取全局缓存预热服务实例"""
    global _cache_warmup_service
    if _cache_warmup_service is None:
        _cache_warmup_service = CacheWarmupService()
    return _cache_warmup_service

async def shutdown_cache_warmup_service():
    """关闭全局缓存预热服务"""
    global _cache_warmup_service
    if _cache_warmup_service is not None:
        await _cache_warmup_service.stop()
        _cache_warmup_service = None