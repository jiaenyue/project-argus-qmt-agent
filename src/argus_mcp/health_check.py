"""
WebSocket 实时数据系统 - 健康检查工具
根据 tasks.md 任务9要求实现的健康检查和监控支持
"""

import asyncio
import aiohttp
import json
import sys
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class HealthStatus(str, Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    service_name: str
    status: HealthStatus
    response_time_ms: float
    details: Dict[str, Any]
    error: Optional[str] = None


class HealthChecker:
    """健康检查器"""
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def check_http_endpoint(
        self,
        url: str,
        service_name: str,
        expected_status: int = 200
    ) -> HealthCheckResult:
        """检查HTTP端点健康状态"""
        start_time = time.time()
        
        try:
            async with self.session.get(url) as response:
                response_time = (time.time() - start_time) * 1000
                
                if response.status == expected_status:
                    try:
                        data = await response.json()
                        status = HealthStatus(data.get("status", "unknown"))
                    except:
                        status = HealthStatus.HEALTHY
                    
                    return HealthCheckResult(
                        service_name=service_name,
                        status=status,
                        response_time_ms=response_time,
                        details=data if 'data' in locals() else {"http_status": response.status}
                    )
                else:
                    return HealthCheckResult(
                        service_name=service_name,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=response_time,
                        details={"http_status": response.status},
                        error=f"HTTP {response.status}"
                    )
        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={},
                error="Timeout"
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={},
                error=str(e)
            )
    
    async def check_websocket_endpoint(
        self,
        url: str,
        service_name: str
    ) -> HealthCheckResult:
        """检查WebSocket端点健康状态"""
        start_time = time.time()
        
        try:
            # 尝试建立WebSocket连接
            async with self.session.ws_connect(url) as ws:
                response_time = (time.time() - start_time) * 1000
                
                # 发送ping消息
                await ws.send_str(json.dumps({
                    "type": "ping",
                    "timestamp": time.time()
                }))
                
                # 等待响应
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "pong":
                            return HealthCheckResult(
                                service_name=service_name,
                                status=HealthStatus.HEALTHY,
                                response_time_ms=response_time,
                                details={"websocket": "responsive"}
                            )
                except asyncio.TimeoutError:
                    pass
                
                return HealthCheckResult(
                    service_name=service_name,
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time,
                    details={"websocket": "connected_but_unresponsive"}
                )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={},
                error=str(e)
            )
    
    async def check_consul_service(
        self,
        consul_host: str,
        consul_port: int,
        service_name: str
    ) -> HealthCheckResult:
        """检查Consul服务发现"""
        url = f"http://{consul_host}:{consul_port}/v1/health/service/{service_name}"
        
        start_time = time.time()
        
        try:
            async with self.session.get(url) as response:
                response_time = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    healthy_instances = len([
                        item for item in data
                        if all(check.get("Status") == "passing" for check in item.get("Checks", []))
                    ])
                    
                    total_instances = len(data)
                    
                    if healthy_instances == 0:
                        status = HealthStatus.UNHEALTHY
                    elif healthy_instances < total_instances:
                        status = HealthStatus.DEGRADED
                    else:
                        status = HealthStatus.HEALTHY
                    
                    return HealthCheckResult(
                        service_name=f"consul-{service_name}",
                        status=status,
                        response_time_ms=response_time,
                        details={
                            "total_instances": total_instances,
                            "healthy_instances": healthy_instances
                        }
                    )
                else:
                    return HealthCheckResult(
                        service_name=f"consul-{service_name}",
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=response_time,
                        details={"http_status": response.status},
                        error=f"HTTP {response.status}"
                    )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=f"consul-{service_name}",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={},
                error=str(e)
            )


class SystemHealthChecker:
    """系统健康检查器"""
    
    def __init__(self):
        self.health_checker = HealthChecker()
    
    async def check_websocket_system(
        self,
        websocket_servers: List[str],
        load_balancer_url: Optional[str] = None,
        consul_host: Optional[str] = None,
        consul_port: int = 8500
    ) -> Dict[str, Any]:
        """检查整个WebSocket系统健康状态"""
        
        async with self.health_checker:
            results = []
            
            # 检查WebSocket服务器
            for i, server_url in enumerate(websocket_servers):
                # 检查HTTP健康端点
                http_url = server_url.replace("ws://", "http://").replace("wss://", "https://")
                if not http_url.endswith("/health"):
                    http_url = http_url.rstrip("/") + "/health"
                
                http_result = await self.health_checker.check_http_endpoint(
                    http_url,
                    f"websocket-server-{i+1}-http"
                )
                results.append(http_result)
                
                # 检查WebSocket端点
                ws_result = await self.health_checker.check_websocket_endpoint(
                    server_url,
                    f"websocket-server-{i+1}-ws"
                )
                results.append(ws_result)
            
            # 检查负载均衡器
            if load_balancer_url:
                lb_result = await self.health_checker.check_http_endpoint(
                    f"{load_balancer_url}/health",
                    "load-balancer"
                )
                results.append(lb_result)
            
            # 检查Consul服务发现
            if consul_host:
                consul_result = await self.health_checker.check_consul_service(
                    consul_host,
                    consul_port,
                    "websocket-server"
                )
                results.append(consul_result)
            
            # 计算整体健康状态
            overall_status = self._calculate_overall_status(results)
            
            return {
                "overall_status": overall_status,
                "timestamp": time.time(),
                "checks": [
                    {
                        "service": result.service_name,
                        "status": result.status,
                        "response_time_ms": result.response_time_ms,
                        "details": result.details,
                        "error": result.error
                    }
                    for result in results
                ],
                "summary": self._generate_summary(results)
            }
    
    def _calculate_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """计算整体健康状态"""
        if not results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.status for result in results]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN
    
    def _generate_summary(self, results: List[HealthCheckResult]) -> Dict[str, Any]:
        """生成健康检查摘要"""
        total = len(results)
        healthy = len([r for r in results if r.status == HealthStatus.HEALTHY])
        degraded = len([r for r in results if r.status == HealthStatus.DEGRADED])
        unhealthy = len([r for r in results if r.status == HealthStatus.UNHEALTHY])
        
        avg_response_time = sum(r.response_time_ms for r in results) / total if total > 0 else 0
        
        return {
            "total_checks": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "average_response_time_ms": round(avg_response_time, 2),
            "health_percentage": round((healthy / total) * 100, 1) if total > 0 else 0
        }


async def main():
    """主函数 - 命令行健康检查工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="WebSocket系统健康检查工具")
    parser.add_argument(
        "--websocket-servers",
        nargs="+",
        default=["ws://localhost:8765"],
        help="WebSocket服务器URL列表"
    )
    parser.add_argument(
        "--load-balancer",
        default="http://localhost:8090",
        help="负载均衡器URL"
    )
    parser.add_argument(
        "--consul-host",
        default="localhost",
        help="Consul主机地址"
    )
    parser.add_argument(
        "--consul-port",
        type=int,
        default=8500,
        help="Consul端口"
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="输出格式"
    )
    parser.add_argument(
        "--exit-code",
        action="store_true",
        help="根据健康状态设置退出码"
    )
    
    args = parser.parse_args()
    
    # 执行健康检查
    checker = SystemHealthChecker()
    result = await checker.check_websocket_system(
        websocket_servers=args.websocket_servers,
        load_balancer_url=args.load_balancer,
        consul_host=args.consul_host,
        consul_port=args.consul_port
    )
    
    # 输出结果
    if args.output == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        # 文本格式输出
        print(f"WebSocket系统健康检查报告")
        print(f"=" * 50)
        print(f"整体状态: {result['overall_status']}")
        print(f"检查时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result['timestamp']))}")
        print()
        
        print("检查详情:")
        for check in result['checks']:
            status_icon = {
                "healthy": "✅",
                "degraded": "⚠️",
                "unhealthy": "❌",
                "unknown": "❓"
            }.get(check['status'], "❓")
            
            print(f"  {status_icon} {check['service']}: {check['status']} ({check['response_time_ms']:.1f}ms)")
            if check['error']:
                print(f"    错误: {check['error']}")
        
        print()
        print("摘要:")
        summary = result['summary']
        print(f"  总检查数: {summary['total_checks']}")
        print(f"  健康: {summary['healthy']}")
        print(f"  降级: {summary['degraded']}")
        print(f"  不健康: {summary['unhealthy']}")
        print(f"  健康率: {summary['health_percentage']}%")
        print(f"  平均响应时间: {summary['average_response_time_ms']}ms")
    
    # 设置退出码
    if args.exit_code:
        if result['overall_status'] == HealthStatus.HEALTHY:
            sys.exit(0)
        elif result['overall_status'] == HealthStatus.DEGRADED:
            sys.exit(1)
        else:
            sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())