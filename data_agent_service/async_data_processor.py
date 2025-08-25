# -*- coding: utf-8 -*-
"""
异步数据处理模块

提供高效的异步数据处理能力，包括：
- 异步任务队列管理
- 并发工作池
- 批量数据处理
- 优先级任务调度
- 结果聚合和回调
"""

import asyncio
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union, Coroutine
from queue import PriorityQueue
import threading
from functools import wraps

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """任务优先级"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    
    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        return self.status == TaskStatus.FAILED

@dataclass
class AsyncTask:
    """异步任务"""
    task_id: str
    func: Union[Callable, Coroutine]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at

class BatchProcessor:
    """批量处理器"""
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batch_data: List[Any] = []
        self.last_flush = time.time()
        self.lock = threading.Lock()
        self.processor_func: Optional[Callable] = None
        
    def set_processor(self, func: Callable):
        """设置批量处理函数"""
        self.processor_func = func
        
    async def add_item(self, item: Any) -> bool:
        """添加项目到批次"""
        with self.lock:
            self.batch_data.append(item)
            
            # 检查是否需要刷新
            should_flush = (
                len(self.batch_data) >= self.batch_size or
                time.time() - self.last_flush >= self.flush_interval
            )
            
            if should_flush:
                await self._flush_batch()
                return True
                
        return False
        
    async def _flush_batch(self):
        """刷新批次数据"""
        if not self.batch_data or not self.processor_func:
            return
            
        batch_to_process = self.batch_data.copy()
        self.batch_data.clear()
        self.last_flush = time.time()
        
        try:
            if asyncio.iscoroutinefunction(self.processor_func):
                await self.processor_func(batch_to_process)
            else:
                self.processor_func(batch_to_process)
        except Exception as e:
            logger.error(f"批量处理失败: {e}")
            
    async def force_flush(self):
        """强制刷新"""
        with self.lock:
            await self._flush_batch()

class WorkerPool:
    """工作池"""
    
    def __init__(self, max_workers: int = 10, max_concurrent_tasks: int = 50):
        self.max_workers = max_workers
        self.max_concurrent_tasks = max_concurrent_tasks
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        
    async def submit_task(self, task: AsyncTask) -> TaskResult:
        """提交任务"""
        async with self.semaphore:
            try:
                result = await self._execute_task(task)
                return result
            except Exception as e:
                logger.error(f"任务执行失败 {task.task_id}: {e}")
                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error=e
                )
                
    async def _execute_task(self, task: AsyncTask) -> TaskResult:
        """执行任务"""
        start_time = datetime.now()
        
        try:
            # 根据函数类型选择执行方式
            if asyncio.iscoroutinefunction(task.func):
                # 异步函数
                if task.timeout:
                    result = await asyncio.wait_for(
                        task.func(*task.args, **task.kwargs),
                        timeout=task.timeout
                    )
                else:
                    result = await task.func(*task.args, **task.kwargs)
            else:
                # 同步函数，在线程池中执行
                loop = asyncio.get_event_loop()
                if task.timeout:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.executor,
                            lambda: task.func(*task.args, **task.kwargs)
                        ),
                        timeout=task.timeout
                    )
                else:
                    result = await loop.run_in_executor(
                        self.executor,
                        lambda: task.func(*task.args, **task.kwargs)
                    )
                    
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                start_time=start_time,
                end_time=end_time,
                execution_time=execution_time
            )
            
            # 执行回调
            if task.callback:
                try:
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback(task_result)
                    else:
                        task.callback(task_result)
                except Exception as e:
                    logger.error(f"任务回调执行失败 {task.task_id}: {e}")
                    
            return task_result
            
        except asyncio.TimeoutError:
            logger.warning(f"任务超时 {task.task_id}")
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=asyncio.TimeoutError("Task timeout")
            )
        except Exception as e:
            logger.error(f"任务执行异常 {task.task_id}: {e}")
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=e
            )
            
    def shutdown(self):
        """关闭工作池"""
        self.executor.shutdown(wait=True)

class AsyncDataProcessor:
    """异步数据处理器"""
    
    def __init__(self, 
                 max_workers: int = 10,
                 max_concurrent_tasks: int = 50,
                 max_queue_size: int = 1000):
        self.max_workers = max_workers
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size
        
        # 任务队列
        self.task_queue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self.worker_pool = WorkerPool(max_workers, max_concurrent_tasks)
        
        # 任务管理
        self.tasks: Dict[str, AsyncTask] = {}
        self.results: Dict[str, TaskResult] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "average_execution_time": 0.0,
            "queue_size": 0
        }
        
        # 批量处理器
        self.batch_processors: Dict[str, BatchProcessor] = {}
        
        # 控制标志
        self.is_running = False
        self.worker_tasks: List[asyncio.Task] = []
        
    async def start(self):
        """启动处理器"""
        if self.is_running:
            return
            
        self.is_running = True
        
        # 启动工作协程
        for i in range(self.max_workers):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
            
        logger.info(f"异步数据处理器已启动，工作线程数: {self.max_workers}")
        
    async def stop(self):
        """停止处理器"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # 取消所有工作任务
        for task in self.worker_tasks:
            task.cancel()
            
        # 等待任务完成
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        # 关闭工作池
        self.worker_pool.shutdown()
        
        # 强制刷新所有批量处理器
        for processor in self.batch_processors.values():
            await processor.force_flush()
            
        logger.info("异步数据处理器已停止")
        
    async def submit_task(self, 
                         func: Union[Callable, Coroutine],
                         *args,
                         priority: TaskPriority = TaskPriority.NORMAL,
                         timeout: Optional[float] = None,
                         max_retries: int = 3,
                         callback: Optional[Callable] = None,
                         **kwargs) -> str:
        """提交任务"""
        task_id = str(uuid.uuid4())
        
        task = AsyncTask(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            callback=callback
        )
        
        self.tasks[task_id] = task
        await self.task_queue.put(task)
        
        self.stats["total_tasks"] += 1
        self.stats["queue_size"] = self.task_queue.qsize()
        
        logger.debug(f"任务已提交: {task_id}")
        return task_id
        
    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """获取任务结果"""
        start_time = time.time()
        
        while True:
            if task_id in self.results:
                return self.results[task_id]
                
            if timeout and (time.time() - start_time) > timeout:
                return None
                
            await asyncio.sleep(0.1)
            
    async def wait_for_completion(self, task_ids: List[str], timeout: Optional[float] = None) -> Dict[str, TaskResult]:
        """等待多个任务完成"""
        results = {}
        start_time = time.time()
        
        while len(results) < len(task_ids):
            for task_id in task_ids:
                if task_id not in results and task_id in self.results:
                    results[task_id] = self.results[task_id]
                    
            if timeout and (time.time() - start_time) > timeout:
                break
                
            await asyncio.sleep(0.1)
            
        return results
        
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            self.results[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.CANCELLED
            )
            self.stats["cancelled_tasks"] += 1
            return True
            
        return False
        
    def create_batch_processor(self, 
                              name: str,
                              processor_func: Callable,
                              batch_size: int = 100,
                              flush_interval: float = 5.0) -> BatchProcessor:
        """创建批量处理器"""
        processor = BatchProcessor(batch_size, flush_interval)
        processor.set_processor(processor_func)
        self.batch_processors[name] = processor
        return processor
        
    def get_batch_processor(self, name: str) -> Optional[BatchProcessor]:
        """获取批量处理器"""
        return self.batch_processors.get(name)
        
    async def _worker(self, worker_name: str):
        """工作协程"""
        logger.debug(f"工作协程 {worker_name} 已启动")
        
        while self.is_running:
            try:
                # 获取任务
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                # 执行任务
                self.running_tasks[task.task_id] = asyncio.current_task()
                
                result = await self.worker_pool.submit_task(task)
                
                # 保存结果
                self.results[task.task_id] = result
                
                # 更新统计
                if result.is_success:
                    self.stats["completed_tasks"] += 1
                elif result.is_failed:
                    self.stats["failed_tasks"] += 1
                    
                    # 重试逻辑
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        await self.task_queue.put(task)
                        logger.info(f"任务 {task.task_id} 重试 {task.retry_count}/{task.max_retries}")
                        continue
                        
                # 更新平均执行时间
                if result.execution_time:
                    total_time = self.stats["average_execution_time"] * (self.stats["completed_tasks"] - 1)
                    self.stats["average_execution_time"] = (total_time + result.execution_time) / self.stats["completed_tasks"]
                    
                # 清理
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
                    
                self.stats["queue_size"] = self.task_queue.qsize()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"工作协程 {worker_name} 异常: {e}")
                
        logger.debug(f"工作协程 {worker_name} 已停止")
        
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "running_tasks": len(self.running_tasks),
            "pending_results": len(self.results),
            "batch_processors": len(self.batch_processors),
            "is_running": self.is_running
        }
        
    async def process_batch_data(self, 
                               processor_name: str,
                               data: List[Any]) -> bool:
        """批量处理数据"""
        processor = self.get_batch_processor(processor_name)
        if not processor:
            logger.error(f"批量处理器 {processor_name} 不存在")
            return False
            
        for item in data:
            await processor.add_item(item)
            
        return True

# 全局异步数据处理器实例
_global_async_processor: Optional[AsyncDataProcessor] = None
_processor_lock = threading.Lock()

def get_global_async_processor() -> AsyncDataProcessor:
    """获取全局异步数据处理器实例"""
    global _global_async_processor
    
    if _global_async_processor is None:
        with _processor_lock:
            if _global_async_processor is None:
                _global_async_processor = AsyncDataProcessor(
                    max_workers=10,
                    max_concurrent_tasks=50,
                    max_queue_size=1000
                )
                
    return _global_async_processor

async def shutdown_global_async_processor():
    """关闭全局异步数据处理器"""
    global _global_async_processor
    
    if _global_async_processor:
        await _global_async_processor.stop()
        _global_async_processor = None

# 装饰器
def async_task(priority: TaskPriority = TaskPriority.NORMAL,
              timeout: Optional[float] = None,
              max_retries: int = 3):
    """异步任务装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            processor = get_global_async_processor()
            task_id = await processor.submit_task(
                func, *args,
                priority=priority,
                timeout=timeout,
                max_retries=max_retries,
                **kwargs
            )
            return await processor.get_result(task_id)
        return wrapper
    return decorator