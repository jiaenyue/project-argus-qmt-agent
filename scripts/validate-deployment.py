#!/usr/bin/env python3
"""
WebSocket 实时数据系统 - 部署验证脚本
根据 tasks.md 任务9要求实现的部署验证和健康检查
"""

import asyncio
import aiohttp
import json
import time
import sys
import argparse
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """验证状态"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class ValidationResult:
    """验证结果"""
    test_name: str
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None


class DeploymentValidator:
    """部署验证器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results: List[ValidationResult] = []
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def validate_deployment(self) -> List[ValidationResult]:
        """验证部署"""
        logger.info("开始部署验证...")
        
        # 基础连通性测试
        await self._test_basic_connectivity()
        
        # 服务健康检查
        await self._test_service_health()
        
        # WebSocket功能测试
        await self._test_websocket_functionality()
        
        # 负载均衡测试
        await self._test_load_balancing()
        
        # 服务发现测试
        await self._test_service_discovery()
        
        # 扩展功能测试
        await self._test_scaling_functionality()
        
        # 监控和指标测试
        await self._test_monitoring()
        
        # 性能基准测试
        await self._test_performance_baseline()
        
        logger.info("部署验证完成")
        return self.results
    
    async def _test_basic_connectivity(self):
        """测试基础连通性"""
        logger.info("测试基础连通性...")
        
        # 测试WebSocket服务器连通性
        for i, server_url in enumerate(self.config.get("websocket_servers", [])):
            await self._run_test(
                f"websocket-server-{i+1}-connectivity",
                self._check_http_connectivity,
                server_url.replace("ws://", "http://").replace("wss://", "https://")
            )
        
        # 测试负载均衡器连通性
        lb_url = self.config.get("load_balancer_url")
        if lb_url:
            await self._run_test(
                "load-balancer-connectivity",
                self._check_http_connectivity,
                lb_url
            )
        
        # 测试Consul连通性
        consul_url = self.config.get("consul_url")
        if consul_url:
            await self._run_test(
                "consul-connectivity",
                self._check_http_connectivity,
                consul_url
            )
    
    async def _test_service_health(self):
        """测试服务健康状态"""
        logger.info("测试服务健康状态...")
        
        # 测试WebSocket服务器健康状态
        for i, server_url in enumerate(self.config.get("websocket_servers", [])):
            health_url = server_url.replace("ws://", "http://").replace("wss://", "https://") + "/health"
            await self._run_test(
                f"websocket-server-{i+1}-health",
                self._check_health_endpoint,
                health_url
            )
        
        # 测试负载均衡器健康状态
        lb_url = self.config.get("load_balancer_url")
        if lb_url:
            await self._run_test(
                "load-balancer-health",
                self._check_health_endpoint,
                f"{lb_url}/health"
            )
    
    async def _test_websocket_functionality(self):
        """测试WebSocket功能"""
        logger.info("测试WebSocket功能...")
        
        for i, server_url in enumerate(self.config.get("websocket_servers", [])):
            await self._run_test(
                f"websocket-server-{i+1}-functionality",
                self._test_websocket_connection,
                server_url
            )
    
    async def _test_load_balancing(self):
        """测试负载均衡功能"""
        logger.info("测试负载均衡功能...")
        
        lb_url = self.config.get("load_balancer_url")
        if lb_url:
            await self._run_test(
                "load-balancer-stats",
                self._check_load_balancer_stats,
                f"{lb_url}/stats"
            )
            
            await self._run_test(
                "load-balancer-nodes",
                self._check_load_balancer_nodes,
                f"{lb_url}/nodes"
            )
    
    async def _test_service_discovery(self):
        """测试服务发现功能"""
        logger.info("测试服务发现功能...")
        
        consul_url = self.config.get("consul_url")
        if consul_url:
            await self._run_test(
                "service-discovery-services",
                self._check_consul_services,
                f"{consul_url}/v1/health/service/websocket-server"
            )
        
        lb_url = self.config.get("load_balancer_url")
        if lb_url:
            await self._run_test(
                "service-discovery-integration",
                self._check_service_discovery_integration,
                f"{lb_url}/services"
            )
    
    async def _test_scaling_functionality(self):
        """测试扩展功能"""
        logger.info("测试扩展功能...")
        
        lb_url = self.config.get("load_balancer_url")
        if lb_url:
            await self._run_test(
                "scaling-evaluation",
                self._check_scaling_evaluation,
                f"{lb_url}/scaling/evaluate"
            )
    
    async def _test_monitoring(self):
        """测试监控功能"""
        logger.info("测试监控功能...")
        
        # 测试Prometheus指标
        for i, server_url in enumerate(self.config.get("websocket_servers", [])):
            metrics_url = server_url.replace("ws://", "http://").replace("wss://", "https://") + "/metrics"
            await self._run_test(
                f"websocket-server-{i+1}-metrics",
                self._check_prometheus_metrics,
                metrics_url
            )
        
        # 测试Prometheus服务器
        prometheus_url = self.config.get("prometheus_url")
        if prometheus_url:
            await self._run_test(
                "prometheus-connectivity",
                self._check_http_connectivity,
                prometheus_url
            )
    
    async def _test_performance_baseline(self):
        """测试性能基准"""
        logger.info("测试性能基准...")
        
        # 简单的性能测试
        for i, server_url in enumerate(self.config.get("websocket_servers", [])):
            await self._run_test(
                f"websocket-server-{i+1}-performance",
                self._test_basic_performance,
                server_url
            )
    
    async def _run_test(self, test_name: str, test_func, *args, **kwargs) -> ValidationResult:
        """运行单个测试"""
        start_time = time.time()
        
        try:
            result = await test_func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            if isinstance(result, ValidationResult):
                result.duration_ms = duration_ms
                self.results.append(result)
                return result
            else:
                # 如果测试函数返回布尔值或其他类型
                status = ValidationStatus.PASS if result else ValidationStatus.FAIL
                validation_result = ValidationResult(
                    test_name=test_name,
                    status=status,
                    message="测试完成" if result else "测试失败",
                    duration_ms=duration_ms
                )
                self.results.append(validation_result)
                return validation_result
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            validation_result = ValidationResult(
                test_name=test_name,
                status=ValidationStatus.FAIL,
                message=f"测试异常: {str(e)}",
                duration_ms=duration_ms
            )
            self.results.append(validation_result)
            return validation_result
    
    async def _check_http_connectivity(self, url: str) -> ValidationResult:
        """检查HTTP连通性"""
        try:
            async with self.session.get(url) as response:
                if response.status < 400:
                    return ValidationResult(
                        test_name="http-connectivity",
                        status=ValidationStatus.PASS,
                        message=f"HTTP连接成功 (状态码: {response.status})",
                        details={"status_code": response.status, "url": url}
                    )
                else:
                    return ValidationResult(
                        test_name="http-connectivity",
                        status=ValidationStatus.FAIL,
                        message=f"HTTP连接失败 (状态码: {response.status})",
                        details={"status_code": response.status, "url": url}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="http-connectivity",
                status=ValidationStatus.FAIL,
                message=f"连接异常: {str(e)}",
                details={"error": str(e), "url": url}
            )
    
    async def _check_health_endpoint(self, url: str) -> ValidationResult:
        """检查健康检查端点"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get("status", "unknown")
                    
                    if status == "healthy":
                        return ValidationResult(
                            test_name="health-check",
                            status=ValidationStatus.PASS,
                            message="服务健康状态正常",
                            details=data
                        )
                    else:
                        return ValidationResult(
                            test_name="health-check",
                            status=ValidationStatus.WARN,
                            message=f"服务健康状态: {status}",
                            details=data
                        )
                else:
                    return ValidationResult(
                        test_name="health-check",
                        status=ValidationStatus.FAIL,
                        message=f"健康检查失败 (状态码: {response.status})",
                        details={"status_code": response.status}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="health-check",
                status=ValidationStatus.FAIL,
                message=f"健康检查异常: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _test_websocket_connection(self, url: str) -> ValidationResult:
        """测试WebSocket连接"""
        try:
            async with self.session.ws_connect(url) as ws:
                # 发送ping消息
                ping_message = {
                    "type": "ping",
                    "timestamp": time.time()
                }
                await ws.send_str(json.dumps(ping_message))
                
                # 等待响应
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "pong":
                            return ValidationResult(
                                test_name="websocket-functionality",
                                status=ValidationStatus.PASS,
                                message="WebSocket连接和消息处理正常",
                                details={"response": data}
                            )
                    
                    return ValidationResult(
                        test_name="websocket-functionality",
                        status=ValidationStatus.WARN,
                        message="WebSocket连接成功但响应异常",
                        details={"message_type": str(msg.type)}
                    )
                
                except asyncio.TimeoutError:
                    return ValidationResult(
                        test_name="websocket-functionality",
                        status=ValidationStatus.WARN,
                        message="WebSocket连接成功但响应超时",
                        details={"timeout": 5.0}
                    )
        
        except Exception as e:
            return ValidationResult(
                test_name="websocket-functionality",
                status=ValidationStatus.FAIL,
                message=f"WebSocket连接失败: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_load_balancer_stats(self, url: str) -> ValidationResult:
        """检查负载均衡器统计信息"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    lb_stats = data.get("load_balancer", {})
                    
                    healthy_nodes = lb_stats.get("healthy_nodes", 0)
                    total_nodes = lb_stats.get("total_nodes", 0)
                    
                    if healthy_nodes > 0:
                        return ValidationResult(
                            test_name="load-balancer-stats",
                            status=ValidationStatus.PASS,
                            message=f"负载均衡器正常 ({healthy_nodes}/{total_nodes} 节点健康)",
                            details=lb_stats
                        )
                    else:
                        return ValidationResult(
                            test_name="load-balancer-stats",
                            status=ValidationStatus.FAIL,
                            message="负载均衡器没有健康节点",
                            details=lb_stats
                        )
                else:
                    return ValidationResult(
                        test_name="load-balancer-stats",
                        status=ValidationStatus.FAIL,
                        message=f"获取负载均衡器统计失败 (状态码: {response.status})",
                        details={"status_code": response.status}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="load-balancer-stats",
                status=ValidationStatus.FAIL,
                message=f"负载均衡器统计检查异常: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_load_balancer_nodes(self, url: str) -> ValidationResult:
        """检查负载均衡器节点"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    nodes = await response.json()
                    
                    healthy_count = sum(1 for node in nodes.values() if node.get("is_healthy", False))
                    total_count = len(nodes)
                    
                    if healthy_count > 0:
                        return ValidationResult(
                            test_name="load-balancer-nodes",
                            status=ValidationStatus.PASS,
                            message=f"负载均衡器节点正常 ({healthy_count}/{total_count} 健康)",
                            details={"nodes": nodes, "healthy_count": healthy_count, "total_count": total_count}
                        )
                    else:
                        return ValidationResult(
                            test_name="load-balancer-nodes",
                            status=ValidationStatus.FAIL,
                            message="没有健康的负载均衡器节点",
                            details={"nodes": nodes}
                        )
                else:
                    return ValidationResult(
                        test_name="load-balancer-nodes",
                        status=ValidationStatus.FAIL,
                        message=f"获取负载均衡器节点失败 (状态码: {response.status})",
                        details={"status_code": response.status}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="load-balancer-nodes",
                status=ValidationStatus.FAIL,
                message=f"负载均衡器节点检查异常: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_consul_services(self, url: str) -> ValidationResult:
        """检查Consul服务"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    services = await response.json()
                    
                    healthy_services = [
                        service for service in services
                        if all(check.get("Status") == "passing" for check in service.get("Checks", []))
                    ]
                    
                    if healthy_services:
                        return ValidationResult(
                            test_name="consul-services",
                            status=ValidationStatus.PASS,
                            message=f"Consul服务发现正常 ({len(healthy_services)}/{len(services)} 服务健康)",
                            details={"healthy_services": len(healthy_services), "total_services": len(services)}
                        )
                    else:
                        return ValidationResult(
                            test_name="consul-services",
                            status=ValidationStatus.FAIL,
                            message="Consul中没有健康的服务实例",
                            details={"services": services}
                        )
                else:
                    return ValidationResult(
                        test_name="consul-services",
                        status=ValidationStatus.FAIL,
                        message=f"Consul服务查询失败 (状态码: {response.status})",
                        details={"status_code": response.status}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="consul-services",
                status=ValidationStatus.FAIL,
                message=f"Consul服务检查异常: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_service_discovery_integration(self, url: str) -> ValidationResult:
        """检查服务发现集成"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    services = await response.json()
                    
                    healthy_services = [s for s in services if s.get("status") == "healthy"]
                    
                    if healthy_services:
                        return ValidationResult(
                            test_name="service-discovery-integration",
                            status=ValidationStatus.PASS,
                            message=f"服务发现集成正常 ({len(healthy_services)}/{len(services)} 服务健康)",
                            details={"healthy_services": len(healthy_services), "total_services": len(services)}
                        )
                    else:
                        return ValidationResult(
                            test_name="service-discovery-integration",
                            status=ValidationStatus.FAIL,
                            message="服务发现集成中没有健康服务",
                            details={"services": services}
                        )
                else:
                    return ValidationResult(
                        test_name="service-discovery-integration",
                        status=ValidationStatus.FAIL,
                        message=f"服务发现集成检查失败 (状态码: {response.status})",
                        details={"status_code": response.status}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="service-discovery-integration",
                status=ValidationStatus.FAIL,
                message=f"服务发现集成检查异常: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_scaling_evaluation(self, url: str) -> ValidationResult:
        """检查扩展评估"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    action = data.get("recommended_action")
                    
                    if action in ["scale_up", "scale_down", "no_action"]:
                        return ValidationResult(
                            test_name="scaling-evaluation",
                            status=ValidationStatus.PASS,
                            message=f"扩展评估正常 (建议动作: {action})",
                            details=data
                        )
                    else:
                        return ValidationResult(
                            test_name="scaling-evaluation",
                            status=ValidationStatus.WARN,
                            message=f"扩展评估返回未知动作: {action}",
                            details=data
                        )
                else:
                    return ValidationResult(
                        test_name="scaling-evaluation",
                        status=ValidationStatus.FAIL,
                        message=f"扩展评估失败 (状态码: {response.status})",
                        details={"status_code": response.status}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="scaling-evaluation",
                status=ValidationStatus.FAIL,
                message=f"扩展评估检查异常: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_prometheus_metrics(self, url: str) -> ValidationResult:
        """检查Prometheus指标"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    metrics_text = await response.text()
                    
                    # 检查是否包含关键指标
                    key_metrics = [
                        "websocket_active_connections",
                        "websocket_messages_sent_total",
                        "websocket_messages_received_total"
                    ]
                    
                    found_metrics = [metric for metric in key_metrics if metric in metrics_text]
                    
                    if len(found_metrics) >= len(key_metrics) * 0.8:  # 至少80%的关键指标存在
                        return ValidationResult(
                            test_name="prometheus-metrics",
                            status=ValidationStatus.PASS,
                            message=f"Prometheus指标正常 ({len(found_metrics)}/{len(key_metrics)} 关键指标)",
                            details={"found_metrics": found_metrics, "total_metrics": len(key_metrics)}
                        )
                    else:
                        return ValidationResult(
                            test_name="prometheus-metrics",
                            status=ValidationStatus.WARN,
                            message=f"部分Prometheus指标缺失 ({len(found_metrics)}/{len(key_metrics)} 关键指标)",
                            details={"found_metrics": found_metrics, "missing_metrics": list(set(key_metrics) - set(found_metrics))}
                        )
                else:
                    return ValidationResult(
                        test_name="prometheus-metrics",
                        status=ValidationStatus.FAIL,
                        message=f"Prometheus指标获取失败 (状态码: {response.status})",
                        details={"status_code": response.status}
                    )
        except Exception as e:
            return ValidationResult(
                test_name="prometheus-metrics",
                status=ValidationStatus.FAIL,
                message=f"Prometheus指标检查异常: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _test_basic_performance(self, url: str) -> ValidationResult:
        """测试基本性能"""
        try:
            # 简单的连接性能测试
            connection_times = []
            
            for _ in range(5):
                start_time = time.time()
                async with self.session.ws_connect(url) as ws:
                    connection_time = (time.time() - start_time) * 1000
                    connection_times.append(connection_time)
                    
                    # 发送简单消息测试响应时间
                    await ws.send_str(json.dumps({"type": "ping", "timestamp": time.time()}))
                    
                    try:
                        await asyncio.wait_for(ws.receive(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
            
            avg_connection_time = sum(connection_times) / len(connection_times)
            
            if avg_connection_time < 1000:  # 1秒内
                return ValidationResult(
                    test_name="basic-performance",
                    status=ValidationStatus.PASS,
                    message=f"基本性能正常 (平均连接时间: {avg_connection_time:.1f}ms)",
                    details={"average_connection_time_ms": avg_connection_time, "connection_times": connection_times}
                )
            else:
                return ValidationResult(
                    test_name="basic-performance",
                    status=ValidationStatus.WARN,
                    message=f"连接性能较慢 (平均连接时间: {avg_connection_time:.1f}ms)",
                    details={"average_connection_time_ms": avg_connection_time, "connection_times": connection_times}
                )
        
        except Exception as e:
            return ValidationResult(
                test_name="basic-performance",
                status=ValidationStatus.FAIL,
                message=f"性能测试异常: {str(e)}",
                details={"error": str(e)}
            )


def print_validation_results(results: List[ValidationResult]):
    """打印验证结果"""
    print("\n" + "="*80)
    print("WebSocket 实时数据系统部署验证报告")
    print("="*80)
    
    # 统计结果
    total_tests = len(results)
    passed_tests = len([r for r in results if r.status == ValidationStatus.PASS])
    failed_tests = len([r for r in results if r.status == ValidationStatus.FAIL])
    warned_tests = len([r for r in results if r.status == ValidationStatus.WARN])
    skipped_tests = len([r for r in results if r.status == ValidationStatus.SKIP])
    
    print(f"\n测试总结:")
    print(f"  总测试数: {total_tests}")
    print(f"  通过: {passed_tests}")
    print(f"  失败: {failed_tests}")
    print(f"  警告: {warned_tests}")
    print(f"  跳过: {skipped_tests}")
    print(f"  成功率: {(passed_tests / total_tests * 100):.1f}%")
    
    # 详细结果
    print(f"\n详细结果:")
    for result in results:
        status_icon = {
            ValidationStatus.PASS: "✅",
            ValidationStatus.FAIL: "❌",
            ValidationStatus.WARN: "⚠️",
            ValidationStatus.SKIP: "⏭️"
        }.get(result.status, "❓")
        
        duration_str = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
        print(f"  {status_icon} {result.test_name}: {result.message}{duration_str}")
        
        if result.status == ValidationStatus.FAIL and result.details:
            error = result.details.get("error")
            if error:
                print(f"    错误: {error}")
    
    print("\n" + "="*80)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="WebSocket实时数据系统部署验证工具")
    parser.add_argument("--config", default="validation-config.json", help="验证配置文件")
    parser.add_argument("--websocket-servers", nargs="+", default=["ws://localhost:8765"], help="WebSocket服务器URL列表")
    parser.add_argument("--load-balancer", default="http://localhost:8090", help="负载均衡器URL")
    parser.add_argument("--consul", default="http://localhost:8500", help="Consul URL")
    parser.add_argument("--prometheus", help="Prometheus URL")
    parser.add_argument("--output", help="结果输出文件（JSON格式）")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 构建配置
    config = {
        "websocket_servers": args.websocket_servers,
        "load_balancer_url": args.load_balancer,
        "consul_url": args.consul,
        "prometheus_url": args.prometheus
    }
    
    # 如果有配置文件，加载配置
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            file_config = json.load(f)
            config.update(file_config)
    except FileNotFoundError:
        logger.info(f"配置文件 {args.config} 不存在，使用命令行参数")
    except Exception as e:
        logger.warning(f"加载配置文件失败: {e}")
    
    # 运行验证
    async with DeploymentValidator(config) as validator:
        results = await validator.validate_deployment()
    
    # 输出结果
    print_validation_results(results)
    
    # 保存结果到文件
    if args.output:
        output_data = {
            "timestamp": time.time(),
            "config": config,
            "results": [
                {
                    "test_name": r.test_name,
                    "status": r.status,
                    "message": r.message,
                    "details": r.details,
                    "duration_ms": r.duration_ms
                }
                for r in results
            ]
        }
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n结果已保存到: {args.output}")
    
    # 根据验证结果设置退出码
    failed_tests = len([r for r in results if r.status == ValidationStatus.FAIL])
    if failed_tests > 0:
        sys.exit(1)  # 有失败的测试
    
    warned_tests = len([r for r in results if r.status == ValidationStatus.WARN])
    if warned_tests > 0:
        sys.exit(2)  # 有警告的测试
    
    sys.exit(0)  # 所有测试通过


if __name__ == "__main__":
    asyncio.run(main())