"""
Preload task management for cache preloader.

This module defines preload tasks and provides task management functionality
including registration, scheduling, and dependency resolution.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict, Set, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class PreloadTask:
    """Represents a cache preload task with scheduling and dependency information."""
    
    data_type: str
    key_pattern: str
    loader_func: Callable
    priority: int
    schedule: str  # 'startup', 'periodic', 'demand'
    interval: Optional[int] = None  # For periodic tasks
    dependencies: Optional[List[str]] = None
    last_run: Optional[float] = None
    success_count: int = 0
    failure_count: int = 0
    adaptive_interval: Optional[float] = None  # Dynamically adjusted interval
    performance_score: float = 0  # Task performance metric
    
    def __post_init__(self):
        """Initialize dependencies as empty list if None."""
        if self.dependencies is None:
            self.dependencies = []
    
    def get_success_rate(self) -> float:
        """Calculate task success rate."""
        total_runs = self.success_count + self.failure_count
        if total_runs == 0:
            return 0.0
        return self.success_count / total_runs
    
    def should_run(self, current_time: float) -> bool:
        """Check if task should run based on schedule and interval."""
        if self.schedule == "startup":
            return self.last_run is None
        elif self.schedule == "periodic" and self.interval:
            if self.last_run is None:
                return True
            return current_time - self.last_run >= self.interval
        elif self.schedule == "demand":
            # Demand tasks are triggered externally
            return False
        return False
    
    def update_performance_score(self, execution_time: float, items_loaded: int):
        """Update performance score based on execution results."""
        # Calculate efficiency: items per second
        if execution_time > 0:
            efficiency = items_loaded / execution_time
            
            # Update performance score with exponential moving average
            alpha = 0.3  # Smoothing factor
            new_score = min(efficiency / 100, 1.0)  # Normalize to 0-1
            
            if self.performance_score == 0:
                self.performance_score = new_score
            else:
                self.performance_score = (
                    alpha * new_score + (1 - alpha) * self.performance_score
                )


class PreloadTaskManager:
    """Manages preload tasks including registration, scheduling, and execution."""
    
    def __init__(self):
        self.tasks: Dict[str, PreloadTask] = {}
        self.task_execution_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
    
    def register_task(self, task_id: str, task: PreloadTask) -> bool:
        """Register a new preload task.
        
        Args:
            task_id: Unique task identifier
            task: PreloadTask instance
            
        Returns:
            True if task was registered successfully
        """
        if task_id in self.tasks:
            logger.warning(f"Task {task_id} already exists, updating")
        
        # Validate task
        if not self._validate_task(task):
            logger.error(f"Invalid task configuration for {task_id}")
            return False
        
        self.tasks[task_id] = task
        logger.info(f"Registered preload task: {task_id} ({task.schedule})")
        return True
    
    def unregister_task(self, task_id: str) -> bool:
        """Unregister a preload task.
        
        Args:
            task_id: Task identifier to remove
            
        Returns:
            True if task was removed successfully
        """
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} not found for removal")
            return False
        
        del self.tasks[task_id]
        logger.info(f"Unregistered preload task: {task_id}")
        return True
    
    def get_runnable_tasks(self, current_time: float) -> List[tuple]:
        """Get list of tasks that should run now.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            List of (task_id, task) tuples sorted by priority
        """
        runnable = []
        
        for task_id, task in self.tasks.items():
            if task.should_run(current_time):
                runnable.append((task_id, task))
        
        # Sort by priority (higher first)
        runnable.sort(key=lambda x: x[1].priority, reverse=True)
        
        return runnable
    
    def get_startup_tasks(self) -> List[tuple]:
        """Get startup tasks sorted by priority and dependencies.
        
        Returns:
            List of (task_id, task) tuples in execution order
        """
        startup_tasks = [
            (task_id, task) for task_id, task in self.tasks.items()
            if task.schedule == "startup"
        ]
        
        # Sort by priority first
        startup_tasks.sort(key=lambda x: x[1].priority, reverse=True)
        
        # Resolve dependencies
        return self._resolve_dependencies(startup_tasks)
    
    def get_periodic_tasks(self, current_time: float) -> List[tuple]:
        """Get periodic tasks that should run now.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            List of (task_id, task) tuples
        """
        periodic_tasks = []
        
        for task_id, task in self.tasks.items():
            if (task.schedule == "periodic" and 
                task.should_run(current_time)):
                periodic_tasks.append((task_id, task))
        
        # Sort by priority
        periodic_tasks.sort(key=lambda x: x[1].priority, reverse=True)
        
        return periodic_tasks
    
    def get_demand_tasks(self) -> List[tuple]:
        """Get demand-based tasks.
        
        Returns:
            List of (task_id, task) tuples
        """
        demand_tasks = [
            (task_id, task) for task_id, task in self.tasks.items()
            if task.schedule == "demand"
        ]
        
        # Sort by priority
        demand_tasks.sort(key=lambda x: x[1].priority, reverse=True)
        
        return demand_tasks
    
    def record_execution(self, task_id: str, success: bool, 
                        execution_time: float, items_loaded: int = 0,
                        error_message: Optional[str] = None):
        """Record task execution results.
        
        Args:
            task_id: Task identifier
            success: Whether execution was successful
            execution_time: Time taken to execute
            items_loaded: Number of items loaded
            error_message: Error message if failed
        """
        if task_id not in self.tasks:
            logger.warning(f"Recording execution for unknown task: {task_id}")
            return
        
        task = self.tasks[task_id]
        current_time = time.time()
        
        # Update task statistics
        if success:
            task.success_count += 1
            task.last_run = current_time
            task.update_performance_score(execution_time, items_loaded)
        else:
            task.failure_count += 1
        
        # Record in history
        execution_record = {
            'task_id': task_id,
            'timestamp': current_time,
            'success': success,
            'execution_time': execution_time,
            'items_loaded': items_loaded,
            'error_message': error_message
        }
        
        self.task_execution_history.append(execution_record)
        
        # Trim history if too large
        if len(self.task_execution_history) > self.max_history_size:
            self.task_execution_history = self.task_execution_history[-self.max_history_size:]
        
        logger.debug(
            f"Recorded execution for {task_id}: "
            f"success={success}, time={execution_time:.2f}s, items={items_loaded}"
        )
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """Get comprehensive task statistics.
        
        Returns:
            Dictionary with task statistics
        """
        stats = {
            'total_tasks': len(self.tasks),
            'task_breakdown': {
                'startup': 0,
                'periodic': 0,
                'demand': 0
            },
            'execution_stats': {
                'total_executions': len(self.task_execution_history),
                'successful_executions': 0,
                'failed_executions': 0,
                'average_execution_time': 0,
                'total_items_loaded': 0
            },
            'task_details': {}
        }
        
        # Count tasks by schedule type
        for task in self.tasks.values():
            stats['task_breakdown'][task.schedule] += 1
        
        # Analyze execution history
        if self.task_execution_history:
            successful = [r for r in self.task_execution_history if r['success']]
            failed = [r for r in self.task_execution_history if not r['success']]
            
            stats['execution_stats']['successful_executions'] = len(successful)
            stats['execution_stats']['failed_executions'] = len(failed)
            
            if self.task_execution_history:
                avg_time = sum(r['execution_time'] for r in self.task_execution_history)
                stats['execution_stats']['average_execution_time'] = (
                    avg_time / len(self.task_execution_history)
                )
                
                stats['execution_stats']['total_items_loaded'] = sum(
                    r['items_loaded'] for r in self.task_execution_history
                )
        
        # Add individual task details
        for task_id, task in self.tasks.items():
            stats['task_details'][task_id] = {
                'data_type': task.data_type,
                'schedule': task.schedule,
                'priority': task.priority,
                'success_count': task.success_count,
                'failure_count': task.failure_count,
                'success_rate': task.get_success_rate(),
                'performance_score': task.performance_score,
                'last_run': task.last_run
            }
        
        return stats
    
    def optimize_task_intervals(self):
        """Optimize task intervals based on performance and access patterns."""
        for task_id, task in self.tasks.items():
            if task.schedule != "periodic" or not task.interval:
                continue
            
            # Adjust interval based on performance and success rate
            success_rate = task.get_success_rate()
            performance = task.performance_score
            
            if success_rate > 0.9 and performance > 0.7:
                # High performance, can reduce interval (run more frequently)
                new_interval = max(task.interval * 0.8, 60)  # Min 1 minute
            elif success_rate < 0.5 or performance < 0.3:
                # Poor performance, increase interval
                new_interval = min(task.interval * 1.5, 3600)  # Max 1 hour
            else:
                continue  # No change needed
            
            if abs(new_interval - task.interval) > 30:  # Only change if significant
                logger.info(
                    f"Optimizing interval for {task_id}: "
                    f"{task.interval}s -> {new_interval}s"
                )
                task.adaptive_interval = new_interval
    
    def _validate_task(self, task: PreloadTask) -> bool:
        """Validate task configuration.
        
        Args:
            task: Task to validate
            
        Returns:
            True if task is valid
        """
        # Check required fields
        if not task.data_type or not task.key_pattern or not task.loader_func:
            return False
        
        # Check priority range
        if not (1 <= task.priority <= 10):
            return False
        
        # Check schedule type
        if task.schedule not in ['startup', 'periodic', 'demand']:
            return False
        
        # Check periodic task has interval
        if task.schedule == 'periodic' and not task.interval:
            return False
        
        # Check dependencies exist
        if task.dependencies:
            for dep in task.dependencies:
                if dep not in self.tasks:
                    logger.warning(f"Dependency {dep} not found")
        
        return True
    
    def _resolve_dependencies(self, tasks: List[tuple]) -> List[tuple]:
        """Resolve task dependencies and return in execution order.
        
        Args:
            tasks: List of (task_id, task) tuples
            
        Returns:
            List of tasks in dependency-resolved order
        """
        resolved = []
        remaining = dict(tasks)
        executed_ids = set()
        
        # Simple dependency resolution (could be improved with topological sort)
        max_iterations = len(remaining) * 2  # Prevent infinite loops
        iteration = 0
        
        while remaining and iteration < max_iterations:
            iteration += 1
            made_progress = False
            
            for task_id, task in list(remaining.items()):
                # Check if all dependencies are satisfied
                if all(dep in executed_ids for dep in task.dependencies):
                    resolved.append((task_id, task))
                    executed_ids.add(task_id)
                    del remaining[task_id]
                    made_progress = True
            
            if not made_progress:
                # Add remaining tasks (circular dependencies or missing deps)
                logger.warning(f"Could not resolve dependencies for {len(remaining)} tasks")
                resolved.extend(remaining.items())
                break
        
        return resolved