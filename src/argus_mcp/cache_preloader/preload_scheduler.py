"""
Preload scheduler for intelligent cache management.

This module provides scheduling functionality for cache preloading tasks,
including startup, periodic, and demand-based scheduling.
"""

import asyncio
import time
from typing import Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor
import logging

from .preload_tasks import PreloadTaskManager, PreloadTask
from .access_patterns import AccessPatternAnalyzer
from .data_loaders import DataLoaders

logger = logging.getLogger(__name__)


class PreloadScheduler:
    """Scheduler for cache preload tasks with intelligent timing and dependency resolution."""
    
    def __init__(self, cache_manager, data_service_client, max_workers: int = 4):
        """Initialize preload scheduler.
        
        Args:
            cache_manager: Cache manager instance
            data_service_client: Data service client for loading data
            max_workers: Maximum number of worker threads
        """
        self.cache_manager = cache_manager
        self.data_service_client = data_service_client
        self.max_workers = max_workers
        
        # Core components
        self.task_manager = PreloadTaskManager()
        self.pattern_analyzer = AccessPatternAnalyzer()
        self.data_loaders = DataLoaders(cache_manager, data_service_client)
        
        # Execution components
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # Configuration
        self._config = self._initialize_config()
        
        # Statistics
        self._stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'start_time': time.time(),
            'last_optimization': 0
        }
        
        logger.info("Preload scheduler initialized")
    
    def _initialize_config(self) -> Dict[str, Any]:
        """Initialize scheduler configuration."""
        return {
            'startup_preload': True,
            'periodic_preload': True,
            'demand_preload': True,
            'scheduler_interval': 60,  # Check every minute
            'preload_timeout': 30,     # Timeout for individual preload operations
            'optimization_interval': 3600,  # Optimize every hour
            'max_concurrent_tasks': 3,  # Maximum concurrent preload tasks
            'demand_check_interval': 300,  # Check demand patterns every 5 minutes
        }
    
    async def start(self):
        """Start the preload scheduler."""
        if self._running:
            logger.warning("Preload scheduler is already running")
            return
        
        self._running = True
        
        # Register default tasks
        await self._register_default_tasks()
        
        # Start scheduler loop
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # Perform startup preload
        if self._config['startup_preload']:
            await self._perform_startup_preload()
        
        logger.info("Preload scheduler started")
    
    async def stop(self):
        """Stop the preload scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        self._executor.shutdown(wait=True)
        logger.info("Preload scheduler stopped")
    
    async def _register_default_tasks(self):
        """Register default preload tasks for common data types."""
        # Trading dates - preload at startup and daily
        trading_dates_task = PreloadTask(
            data_type="trading_dates",
            key_pattern="trading_dates:*",
            loader_func=self.data_loaders.load_trading_dates,
            priority=9,
            schedule="startup"
        )
        self.task_manager.register_task("trading_dates", trading_dates_task)
        
        # Daily trading dates update
        trading_dates_daily = PreloadTask(
            data_type="trading_dates",
            key_pattern="trading_dates:*",
            loader_func=self.data_loaders.load_trading_dates,
            priority=8,
            schedule="periodic",
            interval=86400  # Daily
        )
        self.task_manager.register_task("trading_dates_daily", trading_dates_daily)
        
        # Stock list - preload at startup and every 30 minutes
        stock_list_task = PreloadTask(
            data_type="stock_list",
            key_pattern="stock_list:*",
            loader_func=self.data_loaders.load_stock_list,
            priority=8,
            schedule="startup"
        )
        self.task_manager.register_task("stock_list", stock_list_task)
        
        stock_list_periodic = PreloadTask(
            data_type="stock_list",
            key_pattern="stock_list:*",
            loader_func=self.data_loaders.load_stock_list,
            priority=7,
            schedule="periodic",
            interval=1800  # 30 minutes
        )
        self.task_manager.register_task("stock_list_periodic", stock_list_periodic)
        
        # Market status - preload every minute during trading hours
        market_status_task = PreloadTask(
            data_type="market_status",
            key_pattern="market_status:*",
            loader_func=self.data_loaders.load_market_status,
            priority=10,
            schedule="periodic",
            interval=60  # 1 minute
        )
        self.task_manager.register_task("market_status", market_status_task)
        
        # Popular instruments - demand-based preloading
        popular_instruments_task = PreloadTask(
            data_type="instrument_detail",
            key_pattern="instrument:*",
            loader_func=self.data_loaders.load_popular_instruments,
            priority=6,
            schedule="demand"
        )
        self.task_manager.register_task("popular_instruments", popular_instruments_task)
        
        # Market indices - periodic preloading
        indices_task = PreloadTask(
            data_type="market_indices",
            key_pattern="index:*",
            loader_func=self.data_loaders.load_market_indices,
            priority=7,
            schedule="periodic",
            interval=300  # 5 minutes
        )
        self.task_manager.register_task("market_indices", indices_task)
        
        logger.info("Registered default preload tasks")
    
    async def _scheduler_loop(self):
        """Main scheduler loop for periodic and demand-based preloading."""
        last_demand_check = 0
        last_optimization = 0
        
        while self._running:
            try:
                current_time = time.time()
                
                # Check periodic tasks
                if self._config['periodic_preload']:
                    await self._check_periodic_tasks(current_time)
                
                # Check demand-based tasks
                if (self._config['demand_preload'] and 
                    current_time - last_demand_check >= self._config['demand_check_interval']):
                    await self._check_demand_tasks(current_time)
                    last_demand_check = current_time
                
                # Optimize task intervals
                if (current_time - last_optimization >= self._config['optimization_interval']):
                    self._optimize_tasks()
                    last_optimization = current_time
                
                await asyncio.sleep(self._config['scheduler_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self._config['scheduler_interval'])
    
    async def _perform_startup_preload(self):
        """Perform startup preloading with dependency resolution."""
        logger.info("Starting startup preload")
        
        startup_tasks = self.task_manager.get_startup_tasks()
        
        if not startup_tasks:
            logger.info("No startup tasks to execute")
            return
        
        # Execute tasks in dependency order
        executed_count = 0
        for task_id, task in startup_tasks:
            try:
                await self._execute_task(task_id, task)
                executed_count += 1
            except Exception as e:
                logger.error(f"Error executing startup task {task_id}: {e}")
        
        logger.info(f"Completed startup preload ({executed_count}/{len(startup_tasks)} tasks)")
    
    async def _check_periodic_tasks(self, current_time: float):
        """Check and execute periodic tasks that are due."""
        periodic_tasks = self.task_manager.get_periodic_tasks(current_time)
        
        if not periodic_tasks:
            return
        
        # Limit concurrent executions
        semaphore = asyncio.Semaphore(self._config['max_concurrent_tasks'])
        
        async def execute_with_semaphore(task_id: str, task: PreloadTask):
            async with semaphore:
                await self._execute_task(task_id, task)
        
        # Execute tasks concurrently
        tasks = [
            execute_with_semaphore(task_id, task)
            for task_id, task in periodic_tasks
        ]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_demand_tasks(self, current_time: float):
        """Check demand patterns and trigger preloading if needed."""
        try:
            # Get preload candidates from pattern analysis
            candidates = self.pattern_analyzer.get_preload_candidates(current_time)
            
            if not candidates:
                return
            
            logger.debug(f"Found {len(candidates)} preload candidates")
            
            # Get demand tasks
            demand_tasks = dict(self.task_manager.get_demand_tasks())
            
            # Execute relevant demand tasks
            executed_tasks = []
            for key, data_type, priority in candidates[:5]:  # Limit to top 5
                # Find matching demand task
                matching_task = None
                for task_id, task in demand_tasks.items():
                    if task.data_type == data_type:
                        matching_task = (task_id, task)
                        break
                
                if matching_task:
                    task_id, task = matching_task
                    executed_tasks.append(self._execute_task(task_id, task))
            
            if executed_tasks:
                await asyncio.gather(*executed_tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Error in demand task checking: {e}")
    
    async def _execute_task(self, task_id: str, task: PreloadTask):
        """Execute a single preload task."""
        try:
            logger.debug(f"Executing preload task: {task_id}")
            
            start_time = time.time()
            
            # Execute the loader function in thread pool
            result = await asyncio.wait_for(
                self._run_loader_in_executor(task.loader_func, task.data_type),
                timeout=self._config['preload_timeout']
            )
            
            execution_time = time.time() - start_time
            items_loaded = len(result) if result else 0
            
            # Record execution results
            success = result is not None and len(result) > 0
            self.task_manager.record_execution(
                task_id, success, execution_time, items_loaded
            )
            
            # Update statistics
            self._stats['total_executions'] += 1
            if success:
                self._stats['successful_executions'] += 1
                logger.debug(
                    f"Task {task_id} completed successfully "
                    f"({execution_time:.2f}s, {items_loaded} items)"
                )
            else:
                self._stats['failed_executions'] += 1
                logger.warning(f"Task {task_id} returned no data")
                
        except asyncio.TimeoutError:
            self.task_manager.record_execution(
                task_id, False, self._config['preload_timeout'], 0, "Timeout"
            )
            self._stats['total_executions'] += 1
            self._stats['failed_executions'] += 1
            logger.error(f"Task {task_id} timed out")
            
        except Exception as e:
            self.task_manager.record_execution(
                task_id, False, 0, 0, str(e)
            )
            self._stats['total_executions'] += 1
            self._stats['failed_executions'] += 1
            logger.error(f"Error executing task {task_id}: {e}")
    
    async def _run_loader_in_executor(self, loader_func, data_type: str):
        """Run a loader function in the thread pool executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, loader_func, data_type)
    
    def _optimize_tasks(self):
        """Optimize task intervals and configurations based on performance."""
        try:
            logger.debug("Optimizing task configurations")
            
            # Optimize task intervals
            self.task_manager.optimize_task_intervals()
            
            # Update last optimization time
            self._stats['last_optimization'] = time.time()
            
        except Exception as e:
            logger.error(f"Error optimizing tasks: {e}")
    
    def record_cache_access(self, key: str, data_type: str, timestamp: Optional[float] = None):
        """Record a cache access for pattern analysis.
        
        Args:
            key: Cache key that was accessed
            data_type: Type of data accessed
            timestamp: Access timestamp (current time if None)
        """
        self.pattern_analyzer.record_access(key, data_type, timestamp)
    
    async def register_task(self, task_id: str, task: PreloadTask) -> bool:
        """Register a new preload task.
        
        Args:
            task_id: Unique task identifier
            task: PreloadTask instance
            
        Returns:
            True if task was registered successfully
        """
        return self.task_manager.register_task(task_id, task)
    
    async def unregister_task(self, task_id: str) -> bool:
        """Unregister a preload task.
        
        Args:
            task_id: Task identifier to remove
            
        Returns:
            True if task was removed successfully
        """
        return self.task_manager.unregister_task(task_id)
    
    async def force_execute_task(self, task_id: str) -> bool:
        """Force execution of a specific preload task.
        
        Args:
            task_id: Task ID to execute
            
        Returns:
            True if task was executed successfully
        """
        if task_id not in self.task_manager.tasks:
            logger.error(f"Task not found: {task_id}")
            return False
        
        task = self.task_manager.tasks[task_id]
        try:
            await self._execute_task(task_id, task)
            return True
        except Exception as e:
            logger.error(f"Error force executing task {task_id}: {e}")
            return False
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get comprehensive scheduler statistics.
        
        Returns:
            Dictionary with scheduler statistics
        """
        current_time = time.time()
        uptime = current_time - self._stats['start_time']
        
        stats = {
            'uptime_hours': uptime / 3600,
            'scheduler_stats': {
                'total_executions': self._stats['total_executions'],
                'successful_executions': self._stats['successful_executions'],
                'failed_executions': self._stats['failed_executions'],
                'success_rate': (
                    self._stats['successful_executions'] / 
                    max(self._stats['total_executions'], 1)
                ),
                'last_optimization': self._stats['last_optimization']
            },
            'task_stats': self.task_manager.get_task_statistics(),
            'pattern_stats': self.pattern_analyzer.get_pattern_stats(),
            'configuration': self._config
        }
        
        return stats
    
    def update_config(self, config_updates: Dict[str, Any]):
        """Update scheduler configuration.
        
        Args:
            config_updates: Dictionary of configuration updates
        """
        self._config.update(config_updates)
        logger.info(f"Updated scheduler configuration: {config_updates}")
    
    def is_running(self) -> bool:
        """Check if scheduler is running.
        
        Returns:
            True if scheduler is running
        """
        return self._running