"""Argus MCP Server - Cache Performance Testing.

This module provides comprehensive cache performance testing and benchmarking.
"""

import time
import asyncio
import random
import statistics
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import concurrent.futures
from contextlib import asynccontextmanager

from .cache_config import DataType
from .cache_analyzer import CachePerformanceAnalyzer
from .cache_optimizer import CacheOptimizer

logger = logging.getLogger(__name__)


@dataclass
class PerformanceTestResult:
    """Performance test result."""
    test_name: str
    start_time: float
    end_time: float
    duration: float
    operations_count: int
    operations_per_second: float
    hit_rate: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    memory_usage_mb: float
    error_count: int
    success_rate: float
    additional_metrics: Dict[str, Any]


@dataclass
class BenchmarkSuite:
    """Benchmark test suite configuration."""
    name: str
    description: str
    tests: List[Dict[str, Any]]
    warmup_operations: int = 1000
    test_duration: int = 60
    concurrent_users: int = 10


class CachePerformanceTester:
    """Comprehensive cache performance testing and benchmarking."""
    
    def __init__(self, cache_manager, analyzer: Optional[CachePerformanceAnalyzer] = None):
        """Initialize cache performance tester.
        
        Args:
            cache_manager: Cache manager instance
            analyzer: Optional cache performance analyzer
        """
        self.cache_manager = cache_manager
        self.analyzer = analyzer
        
        # Test configuration
        self.default_test_duration = 60  # seconds
        self.default_concurrent_users = 10
        self.warmup_operations = 1000
        
        # Test data generators
        self._data_generators = {
            DataType.LATEST_DATA: self._generate_latest_data,
            DataType.MARKET_STATUS: self._generate_market_status,
            DataType.STOCK_LIST: self._generate_stock_list,
            DataType.TRADING_DATES: self._generate_trading_dates,
            DataType.INSTRUMENT_DETAIL: self._generate_instrument_detail
        }
        
        # Predefined benchmark suites
        self._benchmark_suites = self._create_benchmark_suites()
        
        logger.info("Cache performance tester initialized")
    
    async def run_performance_test(self, test_config: Dict[str, Any]) -> PerformanceTestResult:
        """Run a single performance test."""
        test_name = test_config.get('name', 'unnamed_test')
        data_type = test_config.get('data_type', DataType.LATEST_DATA)
        operation_type = test_config.get('operation_type', 'mixed')  # get, set, mixed
        duration = test_config.get('duration', self.default_test_duration)
        concurrent_users = test_config.get('concurrent_users', self.default_concurrent_users)
        
        logger.info(f"Starting performance test: {test_name}")
        
        # Warmup
        await self._warmup_cache(data_type)
        
        # Collect initial metrics
        initial_stats = self.cache_manager.get_stats()
        initial_memory = initial_stats.get('memory_usage_mb', 0)
        
        # Run test
        start_time = time.time()
        
        # Create tasks for concurrent users
        tasks = []
        for user_id in range(concurrent_users):
            task = asyncio.create_task(
                self._run_user_operations(user_id, data_type, operation_type, duration)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        
        # Collect final metrics
        final_stats = self.cache_manager.get_stats()
        final_memory = final_stats.get('memory_usage_mb', 0)
        
        # Process results
        total_operations = 0
        total_errors = 0
        response_times = []
        
        for result in results:
            if isinstance(result, Exception):
                total_errors += 1
                logger.error(f"Task failed: {result}")
            else:
                operations, errors, times = result
                total_operations += operations
                total_errors += errors
                response_times.extend(times)
        
        # Calculate metrics
        duration = end_time - start_time
        operations_per_second = total_operations / duration if duration > 0 else 0
        
        # Calculate hit rate
        initial_hits = initial_stats.get('hits', 0)
        initial_misses = initial_stats.get('misses', 0)
        final_hits = final_stats.get('hits', 0)
        final_misses = final_stats.get('misses', 0)
        
        test_hits = final_hits - initial_hits
        test_misses = final_misses - initial_misses
        hit_rate = test_hits / (test_hits + test_misses) if (test_hits + test_misses) > 0 else 0
        
        # Calculate response time metrics
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p95_response_time = self._percentile(response_times, 95) if response_times else 0
        p99_response_time = self._percentile(response_times, 99) if response_times else 0
        
        # Success rate
        success_rate = (total_operations - total_errors) / total_operations if total_operations > 0 else 0
        
        result = PerformanceTestResult(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            operations_count=total_operations,
            operations_per_second=operations_per_second,
            hit_rate=hit_rate,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            memory_usage_mb=final_memory - initial_memory,
            error_count=total_errors,
            success_rate=success_rate,
            additional_metrics={
                'concurrent_users': concurrent_users,
                'data_type': data_type.value if hasattr(data_type, 'value') else str(data_type),
                'operation_type': operation_type
            }
        )
        
        logger.info(f"Performance test completed: {test_name} - {operations_per_second:.1f} ops/sec, {hit_rate:.1%} hit rate")
        return result
    
    async def run_benchmark_suite(self, suite_name: str) -> List[PerformanceTestResult]:
        """Run a predefined benchmark suite."""
        if suite_name not in self._benchmark_suites:
            raise ValueError(f"Unknown benchmark suite: {suite_name}")
        
        suite = self._benchmark_suites[suite_name]
        logger.info(f"Running benchmark suite: {suite.name}")
        
        results = []
        for test_config in suite.tests:
            # Add suite-level configuration
            test_config.update({
                'duration': suite.test_duration,
                'concurrent_users': suite.concurrent_users
            })
            
            result = await self.run_performance_test(test_config)
            results.append(result)
            
            # Brief pause between tests
            await asyncio.sleep(5)
        
        logger.info(f"Benchmark suite completed: {suite.name} - {len(results)} tests")
        return results
    
    async def run_optimization_validation(self, optimizer: CacheOptimizer) -> Dict[str, Any]:
        """Validate cache optimization effectiveness."""
        logger.info("Starting optimization validation")
        
        # Run baseline performance test
        baseline_config = {
            'name': 'baseline_performance',
            'data_type': DataType.LATEST_DATA,
            'operation_type': 'mixed',
            'duration': 30,
            'concurrent_users': 5
        }
        
        baseline_result = await self.run_performance_test(baseline_config)
        
        # Perform optimization
        if self.analyzer:
            analysis_result = await self.analyzer.analyze_performance()
            optimization_actions = await optimizer.optimize_cache(analysis_result)
        else:
            optimization_actions = []
        
        # Wait for optimization to take effect
        await asyncio.sleep(10)
        
        # Run post-optimization performance test
        optimized_config = baseline_config.copy()
        optimized_config['name'] = 'optimized_performance'
        
        optimized_result = await self.run_performance_test(optimized_config)
        
        # Calculate improvement metrics
        improvements = {
            'hit_rate_improvement': optimized_result.hit_rate - baseline_result.hit_rate,
            'response_time_improvement': baseline_result.avg_response_time - optimized_result.avg_response_time,
            'throughput_improvement': optimized_result.operations_per_second - baseline_result.operations_per_second,
            'success_rate_improvement': optimized_result.success_rate - baseline_result.success_rate
        }
        
        validation_result = {
            'baseline_result': asdict(baseline_result),
            'optimized_result': asdict(optimized_result),
            'optimization_actions': [asdict(action) for action in optimization_actions],
            'improvements': improvements,
            'validation_timestamp': time.time()
        }
        
        logger.info(f"Optimization validation completed. Hit rate improvement: {improvements['hit_rate_improvement']:.1%}")
        return validation_result
    
    async def _warmup_cache(self, data_type: DataType):
        """Warm up cache with test data."""
        logger.info(f"Warming up cache for {data_type}")
        
        generator = self._data_generators.get(data_type, self._generate_latest_data)
        
        for i in range(self.warmup_operations):
            key, value = generator(i)
            await self._safe_cache_operation('set', key, value)
            
            if i % 100 == 0:
                await asyncio.sleep(0.001)  # Brief pause to avoid overwhelming
    
    async def _run_user_operations(self, user_id: int, data_type: DataType, 
                                 operation_type: str, duration: int) -> Tuple[int, int, List[float]]:
        """Run operations for a single user."""
        generator = self._data_generators.get(data_type, self._generate_latest_data)
        
        operations_count = 0
        error_count = 0
        response_times = []
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                # Choose operation type
                if operation_type == 'get':
                    op = 'get'
                elif operation_type == 'set':
                    op = 'set'
                else:  # mixed
                    op = random.choice(['get', 'get', 'get', 'set'])  # 75% get, 25% set
                
                # Generate test data
                key, value = generator(operations_count + user_id * 10000)
                
                # Perform operation
                op_start = time.time()
                
                if op == 'get':
                    await self._safe_cache_operation('get', key)
                else:
                    await self._safe_cache_operation('set', key, value)
                
                op_end = time.time()
                response_times.append(op_end - op_start)
                operations_count += 1
                
                # Brief pause to simulate realistic usage
                await asyncio.sleep(random.uniform(0.001, 0.01))
                
            except Exception as e:
                error_count += 1
                logger.debug(f"Operation error for user {user_id}: {e}")
        
        return operations_count, error_count, response_times
    
    async def _safe_cache_operation(self, operation: str, key: str, value: Any = None) -> Any:
        """Perform cache operation with error handling."""
        try:
            if operation == 'get':
                return await asyncio.to_thread(self.cache_manager.get, key)
            elif operation == 'set':
                return await asyncio.to_thread(self.cache_manager.set, key, value)
            else:
                raise ValueError(f"Unknown operation: {operation}")
        except Exception as e:
            logger.debug(f"Cache operation failed: {e}")
            raise
    
    def _generate_latest_data(self, index: int) -> Tuple[str, Dict[str, Any]]:
        """Generate test data for latest data type."""
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA', 'NFLX']
        symbol = symbols[index % len(symbols)]
        
        key = f"latest_data:{symbol}"
        value = {
            'symbol': symbol,
            'price': round(random.uniform(100, 500), 2),
            'volume': random.randint(1000000, 10000000),
            'timestamp': time.time(),
            'change': round(random.uniform(-5, 5), 2)
        }
        
        return key, value
    
    def _generate_market_status(self, index: int) -> Tuple[str, Dict[str, Any]]:
        """Generate test data for market status."""
        key = "market_status"
        value = {
            'status': random.choice(['open', 'closed', 'pre_market', 'after_hours']),
            'timestamp': time.time(),
            'next_open': time.time() + 3600,
            'next_close': time.time() + 7200
        }
        
        return key, value
    
    def _generate_stock_list(self, index: int) -> Tuple[str, List[str]]:
        """Generate test data for stock list."""
        key = f"stock_list:sector_{index % 10}"
        value = [f"STOCK{i:04d}" for i in range(index * 10, (index + 1) * 10)]
        
        return key, value
    
    def _generate_trading_dates(self, index: int) -> Tuple[str, List[str]]:
        """Generate test data for trading dates."""
        key = f"trading_dates:{2024 + index % 5}"
        value = [f"2024-{month:02d}-{day:02d}" for month in range(1, 13) for day in range(1, 29)]
        
        return key, value
    
    def _generate_instrument_detail(self, index: int) -> Tuple[str, Dict[str, Any]]:
        """Generate test data for instrument detail."""
        instrument_id = f"INST{index:06d}"
        key = f"instrument_detail:{instrument_id}"
        value = {
            'id': instrument_id,
            'name': f"Instrument {index}",
            'type': random.choice(['stock', 'bond', 'option', 'future']),
            'exchange': random.choice(['NYSE', 'NASDAQ', 'AMEX']),
            'sector': random.choice(['Technology', 'Healthcare', 'Finance', 'Energy']),
            'market_cap': random.randint(1000000, 1000000000)
        }
        
        return key, value
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _create_benchmark_suites(self) -> Dict[str, BenchmarkSuite]:
        """Create predefined benchmark suites."""
        return {
            'basic_performance': BenchmarkSuite(
                name='Basic Performance',
                description='Basic cache performance tests',
                tests=[
                    {'name': 'get_heavy_load', 'data_type': DataType.LATEST_DATA, 'operation_type': 'get'},
                    {'name': 'set_heavy_load', 'data_type': DataType.LATEST_DATA, 'operation_type': 'set'},
                    {'name': 'mixed_load', 'data_type': DataType.LATEST_DATA, 'operation_type': 'mixed'}
                ],
                test_duration=30,
                concurrent_users=5
            ),
            'data_type_comparison': BenchmarkSuite(
                name='Data Type Comparison',
                description='Compare performance across different data types',
                tests=[
                    {'name': 'latest_data_test', 'data_type': DataType.LATEST_DATA, 'operation_type': 'mixed'},
                    {'name': 'market_status_test', 'data_type': DataType.MARKET_STATUS, 'operation_type': 'mixed'},
                    {'name': 'stock_list_test', 'data_type': DataType.STOCK_LIST, 'operation_type': 'mixed'},
                    {'name': 'instrument_detail_test', 'data_type': DataType.INSTRUMENT_DETAIL, 'operation_type': 'mixed'}
                ],
                test_duration=30,
                concurrent_users=3
            ),
            'stress_test': BenchmarkSuite(
                name='Stress Test',
                description='High-load stress testing',
                tests=[
                    {'name': 'high_concurrency', 'data_type': DataType.LATEST_DATA, 'operation_type': 'mixed'},
                    {'name': 'sustained_load', 'data_type': DataType.LATEST_DATA, 'operation_type': 'mixed'}
                ],
                test_duration=120,
                concurrent_users=20
            )
        }
    
    def get_available_suites(self) -> List[str]:
        """Get list of available benchmark suites."""
        return list(self._benchmark_suites.keys())
    
    def export_test_results(self, results: List[PerformanceTestResult]) -> str:
        """Export test results as JSON."""
        import json
        
        export_data = {
            'test_summary': {
                'total_tests': len(results),
                'export_timestamp': time.time(),
                'export_date': datetime.now().isoformat()
            },
            'results': [asdict(result) for result in results]
        }
        
        return json.dumps(export_data, indent=2, default=str)