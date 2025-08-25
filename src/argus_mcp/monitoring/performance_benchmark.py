"""
历史数据性能基准测试和负载测试工具

提供全面的性能测试功能，包括基准测试、负载测试和并发测试
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import json
import random

from src.argus_mcp.api.enhanced_historical_api import EnhancedHistoricalDataAPI
from src.argus_mcp.monitoring.historical_performance_monitor import get_historical_performance_monitor
from src.argus_mcp.data_models.historical_data import SupportedPeriod

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    cache_hit_rate: float
    error_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'test_name': self.test_name,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'total_time': self.total_time,
            'avg_response_time': self.avg_response_time,
            'min_response_time': self.min_response_time,
            'max_response_time': self.max_response_time,
            'p50_response_time': self.p50_response_time,
            'p95_response_time': self.p95_response_time,
            'p99_response_time': self.p99_response_time,
            'requests_per_second': self.requests_per_second,
            'cache_hit_rate': self.cache_hit_rate,
            'error_rate': self.error_rate,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'errors': self.errors
        }


@dataclass
class LoadTestConfig:
    """负载测试配置"""
    concurrent_users: int = 10
    requests_per_user: int = 100
    ramp_up_time: int = 30  # 秒
    test_duration: int = 300  # 秒
    symbols: List[str] = field(default_factory=lambda: ['000001.SZ', '000002.SZ', '600000.SH'])
    periods: List[str] = field(default_factory=lambda: ['1d', '1h', '5m'])
    date_ranges: List[Tuple[str, str]] = field(default_factory=lambda: [
        ('2024-01-01', '2024-01-31'),
        ('2024-02-01', '2024-02-29'),
        ('2024-03-01', '2024-03-31')
    ])


class PerformanceBenchmark:
    """性能基准测试器"""
    
    def __init__(self, api: Optional[EnhancedHistoricalDataAPI] = None):
        self.api = api or EnhancedHistoricalDataAPI()
        self.monitor = get_historical_performance_monitor()
        self.results: List[BenchmarkResult] = []
        
    async def run_single_request_benchmark(
        self,
        symbol: str = '000001.SZ',
        period: str = '1d',
        start_date: str = '2024-01-01',
        end_date: str = '2024-01-31',
        iterations: int = 100
    ) -> BenchmarkResult:
        """单请求基准测试"""
        logger.info(f"Running single request benchmark: {iterations} iterations")
        
        response_times = []
        errors = []
        successful_requests = 0
        cache_hits = 0
        
        start_time = time.time()
        
        for i in range(iterations):
            request_start = time.time()
            try:
                result = await self.api.get_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period
                )
                
                request_end = time.time()
                response_time = request_end - request_start
                response_times.append(response_time)
                successful_requests += 1
                
                # 检查是否来自缓存
                if hasattr(result, 'metadata') and result.metadata.cache_hit:
                    cache_hits += 1
                    
            except Exception as e:
                request_end = time.time()
                response_time = request_end - request_start
                response_times.append(response_time)
                errors.append(str(e))
                logger.error(f"Request {i+1} failed: {e}")
        
        total_time = time.time() - start_time
        
        # 计算统计指标
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p50_response_time = statistics.median(response_times)
            p95_response_time = self._percentile(response_times, 95)
            p99_response_time = self._percentile(response_times, 99)
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p50_response_time = p95_response_time = p99_response_time = 0
        
        result = BenchmarkResult(
            test_name=f"single_request_{symbol}_{period}",
            total_requests=iterations,
            successful_requests=successful_requests,
            failed_requests=iterations - successful_requests,
            total_time=total_time,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p50_response_time=p50_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=iterations / total_time if total_time > 0 else 0,
            cache_hit_rate=cache_hits / successful_requests if successful_requests > 0 else 0,
            error_rate=(iterations - successful_requests) / iterations,
            memory_usage_mb=self._get_memory_usage(),
            cpu_usage_percent=0.0,  # 需要系统监控
            errors=errors
        )
        
        self.results.append(result)
        return result
    
    async def run_concurrent_benchmark(
        self,
        concurrent_requests: int = 10,
        total_requests: int = 100,
        symbols: Optional[List[str]] = None,
        periods: Optional[List[str]] = None
    ) -> BenchmarkResult:
        """并发请求基准测试"""
        logger.info(f"Running concurrent benchmark: {concurrent_requests} concurrent, {total_requests} total")
        
        symbols = symbols or ['000001.SZ', '000002.SZ', '600000.SH']
        periods = periods or ['1d', '1h', '5m']
        
        response_times = []
        errors = []
        successful_requests = 0
        cache_hits = 0
        
        start_time = time.time()
        
        # 创建任务队列
        tasks = []
        for i in range(total_requests):
            symbol = random.choice(symbols)
            period = random.choice(periods)
            start_date = '2024-01-01'
            end_date = '2024-01-31'
            
            task = self._single_request_task(symbol, period, start_date, end_date)
            tasks.append(task)
        
        # 控制并发数量
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def limited_task(task):
            async with semaphore:
                return await task
        
        # 执行所有任务
        results = await asyncio.gather(
            *[limited_task(task) for task in tasks],
            return_exceptions=True
        )
        
        total_time = time.time() - start_time
        
        # 处理结果
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                response_time, cache_hit = result
                response_times.append(response_time)
                successful_requests += 1
                if cache_hit:
                    cache_hits += 1
        
        # 计算统计指标
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p50_response_time = statistics.median(response_times)
            p95_response_time = self._percentile(response_times, 95)
            p99_response_time = self._percentile(response_times, 99)
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p50_response_time = p95_response_time = p99_response_time = 0
        
        result = BenchmarkResult(
            test_name=f"concurrent_{concurrent_requests}x{total_requests}",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=total_requests - successful_requests,
            total_time=total_time,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p50_response_time=p50_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=total_requests / total_time if total_time > 0 else 0,
            cache_hit_rate=cache_hits / successful_requests if successful_requests > 0 else 0,
            error_rate=(total_requests - successful_requests) / total_requests,
            memory_usage_mb=self._get_memory_usage(),
            cpu_usage_percent=0.0,
            errors=errors
        )
        
        self.results.append(result)
        return result
    
    async def _single_request_task(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str
    ) -> Tuple[float, bool]:
        """单个请求任务"""
        request_start = time.time()
        
        result = await self.api.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period
        )
        
        request_end = time.time()
        response_time = request_end - request_start
        
        cache_hit = hasattr(result, 'metadata') and result.metadata.cache_hit
        
        return response_time, cache_hit
    
    async def run_load_test(self, config: LoadTestConfig) -> List[BenchmarkResult]:
        """负载测试"""
        logger.info(f"Running load test: {config.concurrent_users} users, {config.requests_per_user} requests each")
        
        results = []
        
        # 分阶段增加负载
        ramp_up_step = config.ramp_up_time / config.concurrent_users
        
        tasks = []
        for user_id in range(config.concurrent_users):
            # 延迟启动用户
            delay = user_id * ramp_up_step
            task = self._user_simulation_task(user_id, config, delay)
            tasks.append(task)
        
        # 执行所有用户任务
        user_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 汇总结果
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        all_response_times = []
        all_errors = []
        cache_hits = 0
        
        for user_result in user_results:
            if isinstance(user_result, Exception):
                all_errors.append(str(user_result))
                continue
            
            user_total, user_success, user_response_times, user_cache_hits, user_errors = user_result
            total_requests += user_total
            successful_requests += user_success
            failed_requests += user_total - user_success
            all_response_times.extend(user_response_times)
            cache_hits += user_cache_hits
            all_errors.extend(user_errors)
        
        # 计算统计指标
        if all_response_times:
            avg_response_time = statistics.mean(all_response_times)
            min_response_time = min(all_response_times)
            max_response_time = max(all_response_times)
            p50_response_time = statistics.median(all_response_times)
            p95_response_time = self._percentile(all_response_times, 95)
            p99_response_time = self._percentile(all_response_times, 99)
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p50_response_time = p95_response_time = p99_response_time = 0
        
        result = BenchmarkResult(
            test_name=f"load_test_{config.concurrent_users}users",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_time=config.test_duration,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p50_response_time=p50_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=total_requests / config.test_duration if config.test_duration > 0 else 0,
            cache_hit_rate=cache_hits / successful_requests if successful_requests > 0 else 0,
            error_rate=failed_requests / total_requests if total_requests > 0 else 0,
            memory_usage_mb=self._get_memory_usage(),
            cpu_usage_percent=0.0,
            errors=all_errors
        )
        
        results.append(result)
        self.results.extend(results)
        return results
    
    async def _user_simulation_task(
        self,
        user_id: int,
        config: LoadTestConfig,
        delay: float
    ) -> Tuple[int, int, List[float], int, List[str]]:
        """用户模拟任务"""
        await asyncio.sleep(delay)
        
        response_times = []
        errors = []
        successful_requests = 0
        cache_hits = 0
        
        start_time = time.time()
        
        for request_id in range(config.requests_per_user):
            # 检查是否超过测试时间
            if time.time() - start_time > config.test_duration:
                break
            
            try:
                symbol = random.choice(config.symbols)
                period = random.choice(config.periods)
                start_date, end_date = random.choice(config.date_ranges)
                
                request_start = time.time()
                result = await self.api.get_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period
                )
                request_end = time.time()
                
                response_time = request_end - request_start
                response_times.append(response_time)
                successful_requests += 1
                
                if hasattr(result, 'metadata') and result.metadata.cache_hit:
                    cache_hits += 1
                
                # 模拟用户思考时间
                await asyncio.sleep(random.uniform(0.1, 1.0))
                
            except Exception as e:
                errors.append(f"User {user_id}, Request {request_id}: {str(e)}")
        
        return config.requests_per_user, successful_requests, response_times, cache_hits, errors
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        
        return sorted_data[index]
    
    def _get_memory_usage(self) -> float:
        """获取内存使用量（MB）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def generate_report(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """生成测试报告"""
        if not self.results:
            return {'error': 'No benchmark results available'}
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': len(self.results),
                'total_requests': sum(r.total_requests for r in self.results),
                'total_successful': sum(r.successful_requests for r in self.results),
                'total_failed': sum(r.failed_requests for r in self.results),
                'overall_success_rate': sum(r.successful_requests for r in self.results) / sum(r.total_requests for r in self.results),
                'avg_response_time': statistics.mean([r.avg_response_time for r in self.results]),
                'avg_cache_hit_rate': statistics.mean([r.cache_hit_rate for r in self.results])
            },
            'test_results': [result.to_dict() for result in self.results],
            'recommendations': self._generate_recommendations()
        }
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Benchmark report saved to {output_file}")
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """生成性能优化建议"""
        recommendations = []
        
        if not self.results:
            return recommendations
        
        avg_response_time = statistics.mean([r.avg_response_time for r in self.results])
        avg_cache_hit_rate = statistics.mean([r.cache_hit_rate for r in self.results])
        avg_error_rate = statistics.mean([r.error_rate for r in self.results])
        
        if avg_response_time > 1.0:
            recommendations.append("平均响应时间较高，建议优化数据获取逻辑或增加缓存")
        
        if avg_cache_hit_rate < 0.7:
            recommendations.append("缓存命中率较低，建议优化缓存策略或增加预热")
        
        if avg_error_rate > 0.05:
            recommendations.append("错误率较高，建议检查数据源连接和错误处理逻辑")
        
        # 检查并发性能
        concurrent_results = [r for r in self.results if 'concurrent' in r.test_name]
        if concurrent_results:
            max_rps = max(r.requests_per_second for r in concurrent_results)
            if max_rps < 50:
                recommendations.append("并发处理能力较低，建议优化异步处理和连接池配置")
        
        return recommendations


# 便捷函数
async def run_quick_benchmark(
    api: Optional[EnhancedHistoricalDataAPI] = None,
    output_file: Optional[str] = None
) -> Dict[str, Any]:
    """快速基准测试"""
    benchmark = PerformanceBenchmark(api)
    
    # 单请求测试
    await benchmark.run_single_request_benchmark(iterations=50)
    
    # 并发测试
    await benchmark.run_concurrent_benchmark(concurrent_requests=5, total_requests=50)
    
    return benchmark.generate_report(output_file)


async def run_full_load_test(
    api: Optional[EnhancedHistoricalDataAPI] = None,
    output_file: Optional[str] = None
) -> Dict[str, Any]:
    """完整负载测试"""
    benchmark = PerformanceBenchmark(api)
    
    config = LoadTestConfig(
        concurrent_users=20,
        requests_per_user=50,
        test_duration=300
    )
    
    await benchmark.run_load_test(config)
    
    return benchmark.generate_report(output_file)