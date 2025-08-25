#!/usr/bin/env python3
"""
WebSocket 实时数据系统 - 负载测试脚本
根据 tasks.md 任务9要求实现的扩展性和负载测试
"""

import asyncio
import aiohttp
import json
import time
import statistics
import argparse
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """负载测试配置"""
    websocket_url: str = "ws://localhost:8765"
    api_url: str = "http://localhost:8080"
    concurrent_connections: int = 100
    test_duration: int = 60  # 秒
    message_rate: int = 10  # 每秒消息数
    ramp_up_time: int = 10  # 秒
    connection_timeout: int = 10
    message_timeout: int = 5


@dataclass
class ConnectionStats:
    """连接统计"""
    connection_id: str
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    messages_sent: int = 0
    messages_received: int = 0
    errors: List[str] = field(default_factory=list)
    response_times: List[float] = field(default_factory=list)


@dataclass
class TestResults:
    """测试结果"""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    total_messages_sent: int = 0
    total_messages_received: int = 0
    total_errors: int = 0
    test_duration: float = 0
    connection_stats: List[ConnectionStats] = field(default_factory=list)
    
    @property
    def connection_success_rate(self) -> float:
        return (self.successful_connections / self.total_connections * 100) if self.total_connections > 0 else 0
    
    @property
    def message_success_rate(self) -> float:
        return (self.total_messages_received / self.total_messages_sent * 100) if self.total_messages_sent > 0 else 0
    
    @property
    def messages_per_second(self) -> float:
        return self.total_messages_sent / self.test_duration if self.test_duration > 0 else 0
    
    @property
    def average_response_time(self) -> float:
        all_response_times = []
        for stats in self.connection_stats:
            all_response_times.extend(stats.response_times)
        return statistics.mean(all_response_times) if all_response_times else 0


class WebSocketLoadTester:
    """WebSocket负载测试器"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results = TestResults()
        self.active_connections: Dict[str, aiohttp.ClientWebSocketResponse] = {}
        self.connection_stats: Dict[str, ConnectionStats] = {}
        self.test_start_time: Optional[datetime] = None
        self.test_end_time: Optional[datetime] = None
        self._stop_event = asyncio.Event()
    
    async def run_load_test(self) -> TestResults:
        """运行负载测试"""
        logger.info(f"开始负载测试: {self.config.concurrent_connections} 并发连接, {self.config.test_duration}秒")
        
        self.test_start_time = datetime.now()
        
        try:
            # 创建连接任务
            connection_tasks = []
            for i in range(self.config.concurrent_connections):
                connection_id = f"conn-{i:04d}"
                task = asyncio.create_task(self._connection_worker(connection_id))
                connection_tasks.append(task)
                
                # 渐进式连接建立
                if self.config.ramp_up_time > 0:
                    await asyncio.sleep(self.config.ramp_up_time / self.config.concurrent_connections)
            
            # 运行测试指定时间
            await asyncio.sleep(self.config.test_duration)
            
            # 停止测试
            self._stop_event.set()
            
            # 等待所有连接关闭
            logger.info("等待连接关闭...")
            await asyncio.gather(*connection_tasks, return_exceptions=True)
            
        finally:
            self.test_end_time = datetime.now()
            self._calculate_results()
        
        return self.results
    
    async def _connection_worker(self, connection_id: str):
        """连接工作器"""
        stats = ConnectionStats(connection_id=connection_id)
        self.connection_stats[connection_id] = stats
        
        session = None
        websocket = None
        
        try:
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=self.config.connection_timeout)
            session = aiohttp.ClientSession(timeout=timeout)
            
            # 建立WebSocket连接
            stats.connected_at = datetime.now()
            websocket = await session.ws_connect(self.config.websocket_url)
            self.active_connections[connection_id] = websocket
            
            logger.debug(f"连接 {connection_id} 已建立")
            
            # 发送订阅消息
            subscribe_message = {
                "type": "subscribe",
                "symbol": "000001.SZ",
                "data_type": "quote"
            }
            await websocket.send_str(json.dumps(subscribe_message))
            stats.messages_sent += 1
            
            # 消息发送和接收循环
            message_task = asyncio.create_task(self._message_sender(websocket, stats))
            receive_task = asyncio.create_task(self._message_receiver(websocket, stats))
            
            # 等待测试结束或连接断开
            await asyncio.wait([
                asyncio.create_task(self._stop_event.wait()),
                message_task,
                receive_task
            ], return_when=asyncio.FIRST_COMPLETED)
            
        except Exception as e:
            error_msg = f"连接错误: {str(e)}"
            stats.errors.append(error_msg)
            logger.error(f"连接 {connection_id}: {error_msg}")
            
        finally:
            # 清理资源
            stats.disconnected_at = datetime.now()
            
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
            
            if websocket and not websocket.closed:
                await websocket.close()
            
            if session:
                await session.close()
            
            logger.debug(f"连接 {connection_id} 已关闭")
    
    async def _message_sender(self, websocket: aiohttp.ClientWebSocketResponse, stats: ConnectionStats):
        """消息发送器"""
        message_interval = 1.0 / self.config.message_rate if self.config.message_rate > 0 else 1.0
        
        try:
            while not self._stop_event.is_set() and not websocket.closed:
                # 发送ping消息
                ping_message = {
                    "type": "ping",
                    "timestamp": time.time()
                }
                
                send_time = time.time()
                await websocket.send_str(json.dumps(ping_message))
                stats.messages_sent += 1
                
                # 等待下一次发送
                await asyncio.sleep(message_interval)
                
        except Exception as e:
            stats.errors.append(f"发送错误: {str(e)}")
    
    async def _message_receiver(self, websocket: aiohttp.ClientWebSocketResponse, stats: ConnectionStats):
        """消息接收器"""
        try:
            async for msg in websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        stats.messages_received += 1
                        
                        # 计算响应时间
                        if data.get("type") == "pong" and "timestamp" in data:
                            response_time = (time.time() - data["timestamp"]) * 1000  # 毫秒
                            stats.response_times.append(response_time)
                        
                    except json.JSONDecodeError:
                        stats.errors.append("JSON解析错误")
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    stats.errors.append(f"WebSocket错误: {websocket.exception()}")
                    break
                    
        except Exception as e:
            stats.errors.append(f"接收错误: {str(e)}")
    
    def _calculate_results(self):
        """计算测试结果"""
        self.results.total_connections = len(self.connection_stats)
        self.results.connection_stats = list(self.connection_stats.values())
        
        for stats in self.connection_stats.values():
            if stats.connected_at:
                self.results.successful_connections += 1
            else:
                self.results.failed_connections += 1
            
            self.results.total_messages_sent += stats.messages_sent
            self.results.total_messages_received += stats.messages_received
            self.results.total_errors += len(stats.errors)
        
        if self.test_start_time and self.test_end_time:
            self.results.test_duration = (self.test_end_time - self.test_start_time).total_seconds()


class SystemLoadTester:
    """系统负载测试器"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.websocket_tester = WebSocketLoadTester(config)
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """运行综合负载测试"""
        logger.info("开始综合负载测试...")
        
        results = {
            "test_config": {
                "websocket_url": self.config.websocket_url,
                "api_url": self.config.api_url,
                "concurrent_connections": self.config.concurrent_connections,
                "test_duration": self.config.test_duration,
                "message_rate": self.config.message_rate
            },
            "websocket_test": None,
            "api_test": None,
            "system_metrics": None
        }
        
        # WebSocket负载测试
        logger.info("执行WebSocket负载测试...")
        websocket_results = await self.websocket_tester.run_load_test()
        results["websocket_test"] = self._format_websocket_results(websocket_results)
        
        # API负载测试
        logger.info("执行API负载测试...")
        api_results = await self._run_api_load_test()
        results["api_test"] = api_results
        
        # 系统指标收集
        logger.info("收集系统指标...")
        system_metrics = await self._collect_system_metrics()
        results["system_metrics"] = system_metrics
        
        return results
    
    def _format_websocket_results(self, results: TestResults) -> Dict[str, Any]:
        """格式化WebSocket测试结果"""
        return {
            "summary": {
                "total_connections": results.total_connections,
                "successful_connections": results.successful_connections,
                "failed_connections": results.failed_connections,
                "connection_success_rate": round(results.connection_success_rate, 2),
                "total_messages_sent": results.total_messages_sent,
                "total_messages_received": results.total_messages_received,
                "message_success_rate": round(results.message_success_rate, 2),
                "messages_per_second": round(results.messages_per_second, 2),
                "average_response_time_ms": round(results.average_response_time, 2),
                "total_errors": results.total_errors,
                "test_duration": round(results.test_duration, 2)
            },
            "response_time_stats": self._calculate_response_time_stats(results),
            "error_summary": self._summarize_errors(results)
        }
    
    def _calculate_response_time_stats(self, results: TestResults) -> Dict[str, float]:
        """计算响应时间统计"""
        all_response_times = []
        for stats in results.connection_stats:
            all_response_times.extend(stats.response_times)
        
        if not all_response_times:
            return {}
        
        return {
            "min": round(min(all_response_times), 2),
            "max": round(max(all_response_times), 2),
            "mean": round(statistics.mean(all_response_times), 2),
            "median": round(statistics.median(all_response_times), 2),
            "p95": round(statistics.quantiles(all_response_times, n=20)[18], 2),
            "p99": round(statistics.quantiles(all_response_times, n=100)[98], 2)
        }
    
    def _summarize_errors(self, results: TestResults) -> Dict[str, int]:
        """汇总错误信息"""
        error_counts = {}
        for stats in results.connection_stats:
            for error in stats.errors:
                error_type = error.split(":")[0]
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        return error_counts
    
    async def _run_api_load_test(self) -> Dict[str, Any]:
        """运行API负载测试"""
        api_results = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time_ms": 0,
            "requests_per_second": 0,
            "errors": {}
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.connection_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 并发API请求
                tasks = []
                for i in range(self.config.concurrent_connections):
                    task = asyncio.create_task(self._api_request_worker(session, f"api-{i:04d}"))
                    tasks.append(task)
                
                # 收集结果
                request_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                response_times = []
                for result in request_results:
                    if isinstance(result, dict):
                        api_results["total_requests"] += 1
                        if result["success"]:
                            api_results["successful_requests"] += 1
                            response_times.append(result["response_time"])
                        else:
                            api_results["failed_requests"] += 1
                            error_type = result.get("error", "unknown")
                            api_results["errors"][error_type] = api_results["errors"].get(error_type, 0) + 1
                
                if response_times:
                    api_results["average_response_time_ms"] = round(statistics.mean(response_times), 2)
                
                if self.config.test_duration > 0:
                    api_results["requests_per_second"] = round(
                        api_results["total_requests"] / self.config.test_duration, 2
                    )
        
        except Exception as e:
            logger.error(f"API负载测试错误: {e}")
            api_results["errors"]["test_error"] = str(e)
        
        return api_results
    
    async def _api_request_worker(self, session: aiohttp.ClientSession, worker_id: str) -> Dict[str, Any]:
        """API请求工作器"""
        try:
            start_time = time.time()
            async with session.get(f"{self.config.api_url}/health") as response:
                response_time = (time.time() - start_time) * 1000
                
                return {
                    "worker_id": worker_id,
                    "success": response.status == 200,
                    "response_time": response_time,
                    "status_code": response.status
                }
        
        except Exception as e:
            return {
                "worker_id": worker_id,
                "success": False,
                "response_time": 0,
                "error": str(e)
            }
    
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        metrics = {
            "load_balancer": {},
            "service_discovery": {},
            "scaling_manager": {}
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 收集负载均衡器指标
                try:
                    async with session.get(f"{self.config.api_url}/stats") as response:
                        if response.status == 200:
                            data = await response.json()
                            metrics["load_balancer"] = data.get("load_balancer", {})
                            metrics["service_discovery"] = data.get("service_discovery", {})
                            metrics["scaling_manager"] = data.get("scaling_manager", {})
                except Exception as e:
                    logger.warning(f"无法收集系统指标: {e}")
        
        except Exception as e:
            logger.error(f"系统指标收集错误: {e}")
        
        return metrics


def print_test_results(results: Dict[str, Any]):
    """打印测试结果"""
    print("\n" + "="*80)
    print("WebSocket 实时数据系统负载测试报告")
    print("="*80)
    
    # 测试配置
    config = results["test_config"]
    print(f"\n测试配置:")
    print(f"  WebSocket URL: {config['websocket_url']}")
    print(f"  API URL: {config['api_url']}")
    print(f"  并发连接数: {config['concurrent_connections']}")
    print(f"  测试时长: {config['test_duration']}秒")
    print(f"  消息频率: {config['message_rate']}/秒")
    
    # WebSocket测试结果
    ws_test = results.get("websocket_test", {})
    if ws_test:
        summary = ws_test["summary"]
        print(f"\nWebSocket测试结果:")
        print(f"  连接成功率: {summary['connection_success_rate']}% ({summary['successful_connections']}/{summary['total_connections']})")
        print(f"  消息成功率: {summary['message_success_rate']}% ({summary['total_messages_received']}/{summary['total_messages_sent']})")
        print(f"  消息吞吐量: {summary['messages_per_second']} 消息/秒")
        print(f"  平均响应时间: {summary['average_response_time_ms']}ms")
        print(f"  总错误数: {summary['total_errors']}")
        
        # 响应时间统计
        rt_stats = ws_test.get("response_time_stats", {})
        if rt_stats:
            print(f"\n响应时间统计 (ms):")
            print(f"  最小值: {rt_stats.get('min', 'N/A')}")
            print(f"  最大值: {rt_stats.get('max', 'N/A')}")
            print(f"  平均值: {rt_stats.get('mean', 'N/A')}")
            print(f"  中位数: {rt_stats.get('median', 'N/A')}")
            print(f"  95百分位: {rt_stats.get('p95', 'N/A')}")
            print(f"  99百分位: {rt_stats.get('p99', 'N/A')}")
    
    # API测试结果
    api_test = results.get("api_test", {})
    if api_test:
        print(f"\nAPI测试结果:")
        print(f"  请求成功率: {api_test['successful_requests']}/{api_test['total_requests']}")
        print(f"  平均响应时间: {api_test['average_response_time_ms']}ms")
        print(f"  请求吞吐量: {api_test['requests_per_second']} 请求/秒")
    
    # 系统指标
    system_metrics = results.get("system_metrics", {})
    if system_metrics:
        lb_metrics = system_metrics.get("load_balancer", {})
        if lb_metrics:
            print(f"\n负载均衡器指标:")
            print(f"  健康节点: {lb_metrics.get('healthy_nodes', 'N/A')}/{lb_metrics.get('total_nodes', 'N/A')}")
            print(f"  总客户端: {lb_metrics.get('total_clients', 'N/A')}")
    
    print("\n" + "="*80)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="WebSocket实时数据系统负载测试工具")
    parser.add_argument("--websocket-url", default="ws://localhost:8765", help="WebSocket服务器URL")
    parser.add_argument("--api-url", default="http://localhost:8080", help="API服务器URL")
    parser.add_argument("--connections", type=int, default=100, help="并发连接数")
    parser.add_argument("--duration", type=int, default=60, help="测试时长（秒）")
    parser.add_argument("--message-rate", type=int, default=10, help="每秒消息数")
    parser.add_argument("--ramp-up", type=int, default=10, help="连接建立时间（秒）")
    parser.add_argument("--output", help="结果输出文件（JSON格式）")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 创建测试配置
    config = LoadTestConfig(
        websocket_url=args.websocket_url,
        api_url=args.api_url,
        concurrent_connections=args.connections,
        test_duration=args.duration,
        message_rate=args.message_rate,
        ramp_up_time=args.ramp_up
    )
    
    # 运行负载测试
    tester = SystemLoadTester(config)
    
    try:
        results = await tester.run_comprehensive_test()
        
        # 输出结果
        print_test_results(results)
        
        # 保存结果到文件
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n结果已保存到: {args.output}")
        
        # 根据测试结果设置退出码
        ws_test = results.get("websocket_test", {})
        if ws_test:
            summary = ws_test["summary"]
            if summary["connection_success_rate"] < 95 or summary["message_success_rate"] < 95:
                sys.exit(1)  # 测试失败
        
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"测试执行错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())