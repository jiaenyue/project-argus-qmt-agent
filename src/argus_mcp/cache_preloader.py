"""Argus MCP Server - Cache Preloader.

This module provides intelligent cache preloading capabilities to improve
cache hit rates and reduce latency for frequently accessed data.
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional

from .cache_preloader.preload_scheduler import PreloadScheduler
from .cache_preloader.preload_tasks import PreloadTask
from .cache_preloader.access_patterns import AccessPattern

logger = logging.getLogger(__name__)





class CachePreloader:
    """Intelligent cache preloader with pattern analysis and adaptive scheduling."""
    
    def __init__(self, cache_manager, data_service_client, max_workers: int = 4):
        """Initialize the cache preloader.
        
        Args:
            cache_manager: Cache manager instance for storing preloaded data
            data_service_client: Client for accessing data services
            max_workers: Maximum number of worker threads for preloading
        """
        self.cache_manager = cache_manager
        self.data_service_client = data_service_client
        self.max_workers = max_workers
        
        # Initialize scheduler with all components
        self.scheduler = PreloadScheduler(
            cache_manager=cache_manager,
            data_service_client=data_service_client,
            max_workers=max_workers
        )
        
        # Statistics
        self._stats = {
            'start_time': time.time()
        }
        
        logger.info("Cache preloader initialized")
    
    async def start(self):
        """Start the cache preloader with all its components."""
        await self.scheduler.start()
        logger.info("Cache preloader started")
    
    async def stop(self):
        """Stop the cache preloader and cleanup resources."""
        await self.scheduler.stop()
        logger.info("Cache preloader stopped")
    
    async def _register_default_tasks(self):
        """Register default preload tasks for common data types."""
        # Trading dates - preload at startup and daily
        await self.register_preload_task(
            task_id="trading_dates",
            data_type="trading_dates",
            key_pattern="trading_dates:*",
            loader_func=self._load_trading_dates,
            priority=9,
            schedule="startup"
        )
        
        await self.register_preload_task(
            task_id="trading_dates_daily",
            data_type="trading_dates",
            key_pattern="trading_dates:*",
            loader_func=self._load_trading_dates,
            priority=8,
            schedule="periodic",
            interval=86400  # Daily
        )
        
        # Stock list - preload at startup and every 30 minutes
        await self.register_preload_task(
            task_id="stock_list",
            data_type="stock_list",
            key_pattern="stock_list:*",
            loader_func=self._load_stock_list,
            priority=8,
            schedule="startup"
        )
        
        await self.register_preload_task(
            task_id="stock_list_periodic",
            data_type="stock_list",
            key_pattern="stock_list:*",
            loader_func=self._load_stock_list,
            priority=7,
            schedule="periodic",
            interval=1800  # 30 minutes
        )
        
        # Market status - preload every minute during trading hours
        await self.register_preload_task(
            task_id="market_status",
            data_type="market_status",
            key_pattern="market_status:*",
            loader_func=self._load_market_status,
            priority=10,
            schedule="periodic",
            interval=60  # 1 minute
        )
        
        # Popular instrument details - demand-based preloading
        await self.register_preload_task(
            task_id="popular_instruments",
            data_type="instrument_detail",
            key_pattern="instrument:*",
            loader_func=self._load_popular_instruments,
            priority=6,
            schedule="demand"
        )
    
    async def register_preload_task(self, task_id: str, task: PreloadTask) -> bool:
        """Register a new preload task.
        
        Args:
            task_id: Unique task identifier
            task: PreloadTask instance
            
        Returns:
            True if task was registered successfully
        """
        return await self.scheduler.register_task(task_id, task)
    
    async def _scheduler_loop(self):
        """Main scheduler loop for periodic and demand-based preloading."""
        while self._running:
            try:
                current_time = time.time()
                
                # Check periodic tasks
                for task_id, task in self._preload_tasks.items():
                    if task.schedule == "periodic" and task.interval:
                        if (task.last_run is None or 
                            current_time - task.last_run >= task.interval):
                            await self._execute_preload_task(task_id, task)
                
                # Check demand-based tasks
                if self._preload_config['demand_preload']:
                    await self._check_demand_preload()
                
                # Update access patterns
                await self._update_access_patterns()
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in preloader scheduler: {e}")
                await asyncio.sleep(60)
    
    async def _perform_startup_preload(self):
        """Perform startup preloading."""
        logger.info("Starting startup preload")
        
        startup_tasks = [
            (task_id, task) for task_id, task in self._preload_tasks.items()
            if task.schedule == "startup"
        ]
        
        # Sort by priority (higher first)
        startup_tasks.sort(key=lambda x: x[1].priority, reverse=True)
        
        # Execute tasks with dependency resolution
        executed_tasks = set()
        
        for task_id, task in startup_tasks:
            if await self._can_execute_task(task, executed_tasks):
                await self._execute_preload_task(task_id, task)
                executed_tasks.add(task_id)
        
        logger.info(f"Completed startup preload ({len(executed_tasks)} tasks)")
    
    async def _can_execute_task(self, task: PreloadTask, executed_tasks: Set[str]) -> bool:
        """Check if a task can be executed based on dependencies."""
        if not task.dependencies:
            return True
        
        return all(dep in executed_tasks for dep in task.dependencies)
    
    async def _execute_preload_task(self, task_id: str, task: PreloadTask):
        """Execute a preload task."""
        try:
            logger.debug(f"Executing preload task: {task_id}")
            
            start_time = time.time()
            
            # Execute the loader function
            result = await asyncio.wait_for(
                self._run_loader_function(task.loader_func, task.data_type),
                timeout=self._preload_config['preload_timeout']
            )
            
            execution_time = time.time() - start_time
            
            if result:
                task.success_count += 1
                task.last_run = time.time()
                self._preload_stats['successful_preloads'] += 1
                
                logger.debug(
                    f"Preload task {task_id} completed successfully "
                    f"({execution_time:.2f}s, {len(result)} items)"
                )
                
                # Record performance improvement
                cache_monitor.record_cache_access(
                    cache_level="preload",
                    data_type=task.data_type,
                    hit=True,
                    access_time=execution_time,
                    memory_usage=0,  # Will be updated by cache manager
                    entry_count=len(result)
                )
            else:
                task.failure_count += 1
                self._preload_stats['failed_preloads'] += 1
                logger.warning(f"Preload task {task_id} returned no data")
                
        except asyncio.TimeoutError:
            task.failure_count += 1
            self._preload_stats['failed_preloads'] += 1
            logger.error(f"Preload task {task_id} timed out")
            
        except Exception as e:
            task.failure_count += 1
            self._preload_stats['failed_preloads'] += 1
            logger.error(f"Error executing preload task {task_id}: {e}")
        
        finally:
            self._preload_stats['total_tasks'] += 1
    
    async def _run_loader_function(self, loader_func: Callable, data_type: str) -> Optional[List[Any]]:
        """Run a loader function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, loader_func, data_type)
    
    async def _check_demand_preload(self):
        """Enhanced demand-based preloading with intelligent pattern analysis."""
        try:
            current_time = time.time()
            
            # Analyze individual key patterns
            for key, pattern in self._access_patterns.items():
                if pattern.access_count < 3:  # Need minimum access history
                    continue
                
                # Calculate preload score using weighted factors
                preload_score = self._calculate_preload_score(pattern, current_time)
                
                if preload_score >= self._adaptive_thresholds['min_confidence']:
                    # Extract data type from key
                    data_type = self._extract_data_type_from_key(key)
                    
                    await self._trigger_intelligent_preload(key, data_type, pattern, preload_score)
            
            # Analyze data type level patterns
            for data_type, pattern in self._data_type_patterns.items():
                if pattern.access_count < 5:  # Need more history for data type patterns
                    continue
                
                preload_score = self._calculate_preload_score(pattern, current_time)
                
                if preload_score >= self._adaptive_thresholds['min_confidence']:
                    await self._trigger_data_type_preload(data_type, pattern, preload_score)
                        
        except Exception as e:
            logger.error(f"Error in demand preload check: {e}")
    
    def _calculate_preload_score(self, pattern: AccessPattern, current_time: float) -> float:
        """Calculate intelligent preload score based on multiple factors."""
        try:
            # Time-based factors
            time_to_predicted = pattern.next_predicted_access - current_time
            recency_score = max(0, 1 - (current_time - pattern.last_access) / 3600)  # Decay over 1 hour
            
            # Prediction timing score (higher if predicted access is soon)
            timing_score = 0
            if 0 < time_to_predicted <= 300:  # Next 5 minutes
                timing_score = 1 - (time_to_predicted / 300)
            elif time_to_predicted <= 0:  # Overdue
                timing_score = 0.8
            
            # Velocity score (normalized)
            velocity_score = min(pattern.access_velocity / 2.0, 1.0)  # Cap at 2 accesses/minute
            
            # Trend score (positive trend = increasing frequency)
            trend_score = max(0, pattern.trend_score)
            
            # Seasonality score (regular patterns)
            seasonality_score = pattern.seasonality_score
            
            # Weighted combination
            total_score = (
                velocity_score * self._pattern_weights['velocity'] +
                trend_score * self._pattern_weights['trend'] +
                seasonality_score * self._pattern_weights['seasonality'] +
                recency_score * self._pattern_weights['recency']
            )
            
            # Boost score if timing is good
            if timing_score > 0:
                total_score = min(1.0, total_score + timing_score * 0.3)
            
            # Apply confidence multiplier
            final_score = total_score * pattern.prediction_confidence
            
            return min(final_score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating preload score: {e}")
            return 0
    
    def _extract_data_type_from_key(self, key: str) -> str:
        """Extract data type from cache key."""
        # Simple extraction based on key prefix
        if ':' in key:
            return key.split(':', 1)[0]
        return 'unknown'
    
    async def _trigger_intelligent_preload(self, key: str, data_type: str, 
                                         pattern: AccessPattern, score: float):
        """Trigger intelligent preloading for a specific key."""
        try:
            logger.info(
                f"Triggering intelligent preload for {key} "
                f"(score: {score:.3f}, confidence: {pattern.prediction_confidence:.3f})"
            )
            
            # Create or find appropriate preload task
            task_id = f"intelligent_{data_type}_{hash(key) % 10000}"
            
            if task_id not in self._preload_tasks:
                # Create dynamic preload task
                task = PreloadTask(
                    data_type=data_type,
                    key_pattern=key,
                    loader_func=getattr(self, f"_load_{data_type}", self._load_generic),
                    priority=min(10, int(score * 10)),
                    schedule="demand",
                    performance_score=score
                )
                self._preload_tasks[task_id] = task
            
            # Execute the preload task
            await self._execute_preload_task(task_id, self._preload_tasks[task_id])
            
            # Update statistics
            if 'intelligent_preloads' not in self._preload_stats:
                self._preload_stats['intelligent_preloads'] = 0
            self._preload_stats['intelligent_preloads'] += 1
            
        except Exception as e:
            logger.error(f"Error in intelligent preload for {key}: {e}")
    
    async def _trigger_data_type_preload(self, data_type: str, 
                                       pattern: AccessPattern, score: float):
        """Trigger preloading for an entire data type based on patterns."""
        try:
            logger.info(
                f"Triggering data type preload for {data_type} "
                f"(score: {score:.3f}, velocity: {pattern.access_velocity:.2f})"
            )
            
            # Find or create data type preload task
            task_id = f"datatype_{data_type}_preload"
            
            if task_id not in self._preload_tasks:
                task = PreloadTask(
                    data_type=data_type,
                    key_pattern=f"{data_type}:*",
                    loader_func=getattr(self, f"_load_{data_type}", self._load_generic),
                    priority=min(10, int(score * 10)),
                    schedule="demand",
                    performance_score=score
                )
                self._preload_tasks[task_id] = task
            
            # Execute with adaptive timing
            task = self._preload_tasks[task_id]
            
            # Avoid too frequent execution
            min_interval = max(60, pattern.avg_interval * 0.3) if pattern.avg_interval > 0 else 60
            
            if (task.last_run is None or 
                time.time() - task.last_run >= min_interval):
                
                await self._execute_preload_task(task_id, task)
                
                # Update statistics
                if 'datatype_preloads' not in self._preload_stats:
                    self._preload_stats['datatype_preloads'] = 0
                self._preload_stats['datatype_preloads'] += 1
            
        except Exception as e:
            logger.error(f"Error in data type preload for {data_type}: {e}")
    
    def _trigger_demand_preload(self, data_type: str, metrics: Dict[str, Any]):
        """Trigger demand-based preloading for a specific data type."""
        try:
            # Find existing demand-based tasks for this data type
            demand_tasks = [
                (task_id, task) for task_id, task in self._preload_tasks.items()
                if task.schedule == "demand" and task.data_type == data_type
            ]
            
            if not demand_tasks:
                # Create a new demand-based preload task
                task_id = f"demand_{data_type}_{int(time.time())}"
                task = PreloadTask(
                    data_type=data_type,
                    key_pattern=f"{data_type}:*",
                    loader_func=getattr(self, f"_load_{data_type}", self._load_generic),
                    priority=8,
                    schedule="demand"
                )
                self._preload_tasks[task_id] = task
                demand_tasks = [(task_id, task)]
            
            # Execute demand preloading with enhanced metrics
            for task_id, task in demand_tasks:
                # Avoid too frequent demand preloading
                if (task.last_run is None or 
                    time.time() - task.last_run >= max(60, metrics.get('avg_interval', 300) * 0.5)):
                    
                    logger.info(f"Triggering demand preload for {data_type} with confidence {metrics.get('confidence', 0):.2f}")
                    
                    # Schedule the task for execution
                    asyncio.create_task(self._execute_preload_task(task_id, task))
                    
                    # Update preload statistics
                    if 'demand_preloads' not in self._preload_stats:
                        self._preload_stats['demand_preloads'] = 0
                    self._preload_stats['demand_preloads'] += 1
                    self._preload_stats['last_demand_preload'] = time.time()
                    
        except Exception as e:
            logger.error(f"Error triggering demand preload for {data_type}: {e}")
     
    async def _update_access_patterns(self):
        """Update access patterns for intelligent preloading."""
        current_time = time.time()
        
        # Analyze all patterns and update predictions
        for key, pattern in self._access_patterns.items():
            pattern.update_predictions()
            
            # Check if we should trigger predictive preloading
            if pattern.should_preload(current_time, self._adaptive_thresholds):
                await self._trigger_predictive_preload(key, pattern)
        
        # Analyze data type patterns for bulk preloading
        for data_type, pattern in self._data_type_patterns.items():
            pattern.update_predictions()
            
            if pattern.should_preload(current_time, self._adaptive_thresholds):
                await self._trigger_data_type_bulk_preload(data_type, pattern)
    
    async def _trigger_predictive_preload(self, key: str, pattern: AccessPattern):
        """Trigger predictive preloading for a specific key."""
        try:
            # Extract data type from key
            data_type = self._extract_data_type_from_key(key)
            
            # Check if key is already cached
            cached_value = await self.cache_manager.get(key)
            if cached_value is not None:
                return  # Already cached
            
            # Find appropriate loader function
            loader_func = self._get_loader_for_key(key, data_type)
            if loader_func:
                logger.info(f"Triggering predictive preload for key: {key}")
                await self._run_loader_function(loader_func, data_type)
                
        except Exception as e:
            logger.error(f"Error in predictive preload for {key}: {e}")
    
    async def _trigger_data_type_bulk_preload(self, data_type: str, pattern: AccessPattern):
        """Trigger bulk preloading for a data type."""
        try:
            # Find preload task for this data type
            matching_tasks = [
                task for task in self._preload_tasks.values()
                if task.data_type == data_type
            ]
            
            if matching_tasks:
                task = matching_tasks[0]  # Use first matching task
                task_id = f"bulk_{data_type}_{int(time.time())}"
                logger.info(f"Triggering bulk preload for data type: {data_type}")
                await self._execute_preload_task(task_id, task)
                
        except Exception as e:
            logger.error(f"Error in bulk preload for {data_type}: {e}")
    
    def _get_loader_for_key(self, key: str, data_type: str) -> Optional[callable]:
        """Get appropriate loader function for a specific key."""
        loader_map = {
            'trading_dates': self._load_trading_dates,
            'stock_list': self._load_stock_list,
            'market_status': self._load_market_status,
            'instrument_detail': self._load_popular_instruments,
            'price_data': self._load_price_data,
            'market_data': self._load_market_data
        }
        
        return loader_map.get(data_type)
    
    def _load_price_data(self, data_type: str) -> List[Dict[str, Any]]:
        """Load price data for instruments."""
        try:
            # Mock price data loading
            result = []
            popular_codes = ['000001', '000002', '600000', '600036']
            
            for code in popular_codes:
                key = f'price:{code}:latest'
                data = {
                    'code': code,
                    'price': 10.0 + hash(code) % 50,
                    'change': (hash(code) % 200 - 100) / 100,
                    'timestamp': time.time()
                }
                
                result.append({
                    'key': key,
                    'data': data,
                    'ttl': cache_config.calculate_ttl('price_data')
                })
                
                asyncio.create_task(self.cache_manager.set(
                    key, data, cache_config.calculate_ttl('price_data'), 'price_data'
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"Error loading price data: {e}")
            return []
    
    def _load_market_data(self, data_type: str) -> List[Dict[str, Any]]:
        """Load general market data."""
        try:
            result = [
                {
                    'key': 'market:indices',
                    'data': {
                        'shanghai': {'value': 3000, 'change': 0.5},
                        'shenzhen': {'value': 2000, 'change': -0.3}
                    },
                    'ttl': cache_config.calculate_ttl('market_data')
                },
                {
                    'key': 'market:volume',
                    'data': {'total_volume': 1000000000, 'timestamp': time.time()},
                    'ttl': cache_config.calculate_ttl('market_data')
                }
            ]
            
            for item in result:
                asyncio.create_task(self.cache_manager.set(
                    item['key'], item['data'], item['ttl'], 'market_data'
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"Error loading market data: {e}")
            return []
    
    def record_cache_access(self, key: str, data_type: str, timestamp: Optional[float] = None):
        """Record a cache access for pattern analysis.
        
        Args:
            key: Cache key that was accessed
            data_type: Type of data accessed
            timestamp: Access timestamp (current time if None)
        """
        self.scheduler.record_cache_access(key, data_type, timestamp)
    

    
    async def unregister_preload_task(self, task_id: str) -> bool:
        """Unregister a preload task.
        
        Args:
            task_id: Task identifier to remove
            
        Returns:
            True if task was removed successfully
        """
        return await self.scheduler.unregister_task(task_id)
    
    def get_preload_stats(self) -> Dict[str, Any]:
        """Get comprehensive preload statistics.
        
        Returns:
            Dictionary with preload statistics
        """
        return self.scheduler.get_scheduler_stats()
    
    async def force_preload(self, task_id: str) -> bool:
        """Force execution of a specific preload task.
        
        Args:
            task_id: Task ID to execute
            
        Returns:
            True if task was executed successfully
        """
        return await self.scheduler.force_execute_task(task_id)
    
    async def clear_preload_cache(self, data_type: Optional[str] = None):
        """Clear preloaded cache entries.
        
        Args:
            data_type: Specific data type to clear (all if None)
        """
        try:
            if data_type:
                # Get keys for specific data type from pattern analyzer
                pattern_stats = self.scheduler.pattern_analyzer.get_pattern_stats()
                keys_to_clear = []
                
                for key in self.scheduler.pattern_analyzer.patterns.keys():
                    if self.scheduler.pattern_analyzer._infer_data_type_from_key(key) == data_type:
                        keys_to_clear.append(key)
                
                for key in keys_to_clear:
                    self.cache_manager.delete(key)
                logger.info(f"Cleared preload cache for data type: {data_type}")
            else:
                # Clear all preload cache (this is aggressive)
                all_keys = list(self.scheduler.pattern_analyzer.patterns.keys())
                
                for key in all_keys:
                    self.cache_manager.delete(key)
                logger.info("Cleared all preload cache")
                
        except Exception as e:
            logger.error(f"Error clearing preload cache: {e}")
    
    def update_config(self, config_updates: Dict[str, Any]):
        """Update preloader configuration.
        
        Args:
            config_updates: Dictionary of configuration updates
        """
        self.scheduler.update_config(config_updates)
    
    def is_running(self) -> bool:
        """Check if preloader is running.
        
        Returns:
            True if preloader is running
        """
        return self.scheduler.is_running()