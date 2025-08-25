#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebSocket 故障排除和调试指南

本指南提供 WebSocket 实时数据系统的故障排除方法、调试技巧和问题解决方案，
帮助开发者快速定位和解决 WebSocket 相关问题。

涵盖内容：
1. 常见 WebSocket 连接问题及解决方案
2. 数据传输和协议问题诊断
3. 性能问题分析和优化
4. 错误处理和日志分析
5. 调试工具和监控方法
6. 生产环境问题排查

前置条件：
- 已完成 WebSocket 基础教程
- 了解网络协议基础
- 熟悉日志分析方法

作者: Argus 开发团队
创建时间: 2025-01-15
最后更新: 2025-01-15
"""

import asyncio
import json
import logging
import time
import sys
import traceback
import socket
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException, InvalidStatusCode
import psutil
import threading
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import platform

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)


class ProblemType(str, Enum):
    """问题类型枚举"""
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_DROPPED = "connection_dropped"
    SLOW_RESPONSE = "slow_response"
    DATA_CORRUPTION = "data_corruption"
    MEMORY_LEAK = "memory_leak"
    HIGH_CPU = "high_cpu"
    PROTOCOL_ERROR = "protocol_error"
    AUTHENTICATION_ERROR = "authentication_error"


class Severity(str, Enum):
    """严重程度枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DiagnosticResult:
    """诊断结果"""
    problem_type: ProblemType
    severity: Severity
    description: str
    symptoms: List[str] = field(default_factory=list)
    possible_causes: List[str] = field(default_factory=list)
    solutions: List[str] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionDiagnostic:
    """连接诊断信息"""
    timestamp: datetime = field(default_factory=datetime.now)
    server_url: str = ""
    connection_time_ms: float = 0.0
    ssl_enabled: bool = False
    ssl_version: str = ""
    response_code: Optional[int] = None
    error_message: str = ""
    network_latency_ms: float = 0.0
    dns_resolution_time_ms: float = 0.0


class NetworkDiagnostics:
    """网络诊断工具"""
    
    @staticmethod
    def ping_host(host: str, timeout: float = 5.0) -> Tuple[bool, float]:
        """Ping主机测试连通性
        
        Args:
            host: 主机地址
            timeout: 超时时间
            
        Returns:
            Tuple[bool, float]: (是否成功, 延迟ms)
        """
        try:
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
            else:
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), host]
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            latency = (time.time() - start_time) * 1000
            
            return result.returncode == 0, latency
            
        except Exception as e:
            logger.error(f"Ping测试失败: {e}")
            return False, 0.0
    
    @staticmethod
    def test_tcp_connection(host: str, port: int, timeout: float = 5.0) -> Tuple[bool, float]:
        """测试TCP连接
        
        Args:
            host: 主机地址
            port: 端口号
            timeout: 超时时间
            
        Returns:
            Tuple[bool, float]: (是否成功, 连接时间ms)
        """
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((host, port))
            connection_time = (time.time() - start_time) * 1000
            
            sock.close()
            return result == 0, connection_time
            
        except Exception as e:
            logger.error(f"TCP连接测试失败: {e}")
            return False, 0.0
    
    @staticmethod
    def resolve_dns(hostname: str, timeout: float = 5.0) -> Tuple[bool, float, List[str]]:
        """DNS解析测试
        
        Args:
            hostname: 主机名
            timeout: 超时时间
            
        Returns:
            Tuple[bool, float, List[str]]: (是否成功, 解析时间ms, IP地址列表)
        """
        try:
            start_time = time.time()
            
            # 设置DNS超时（这在Python中比较复杂，简化处理）
            socket.setdefaulttimeout(timeout)
            
            ip_addresses = socket.gethostbyname_ex(hostname)[2]
            resolution_time = (time.time() - start_time) * 1000
            
            socket.setdefaulttimeout(None)  # 重置超时
            return True, resolution_time, ip_addresses
            
        except Exception as e:
            logger.error(f"DNS解析失败: {e}")
            socket.setdefaulttimeout(None)
            return False, 0.0, []
    
    @staticmethod
    def get_network_interfaces() -> List[Dict[str, Any]]:
        """获取网络接口信息"""
        try:
            interfaces = []
            for interface, addrs in psutil.net_if_addrs().items():
                interface_info = {
                    "name": interface,
                    "addresses": []
                }
                
                for addr in addrs:
                    interface_info["addresses"].append({
                        "family": str(addr.family),
                        "address": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast
                    })
                
                interfaces.append(interface_info)
            
            return interfaces
            
        except Exception as e:
            logger.error(f"获取网络接口信息失败: {e}")
            return []


class WebSocketDiagnostics:
    """WebSocket诊断工具"""
    
    def __init__(self):
        self.diagnostic_history: List[ConnectionDiagnostic] = []
        self.network_diagnostics = NetworkDiagnostics()
    
    async def diagnose_connection(self, url: str, timeout: float = 10.0) -> ConnectionDiagnostic:
        """诊断WebSocket连接
        
        Args:
            url: WebSocket URL
            timeout: 超时时间
            
        Returns:
            ConnectionDiagnostic: 诊断结果
        """
        diagnostic = ConnectionDiagnostic(server_url=url)
        
        try:
            # 解析URL
            if url.startswith("wss://"):
                diagnostic.ssl_enabled = True
                host = url[6:].split("/")[0].split(":")[0]
                port = int(url[6:].split("/")[0].split(":")[1]) if ":" in url[6:].split("/")[0] else 443
            elif url.startswith("ws://"):
                host = url[5:].split("/")[0].split(":")[0]
                port = int(url[5:].split("/")[0].split(":")[1]) if ":" in url[5:].split("/")[0] else 80
            else:
                diagnostic.error_message = "无效的WebSocket URL格式"
                return diagnostic
            
            # DNS解析测试
            dns_success, dns_time, ip_addresses = self.network_diagnostics.resolve_dns(host)
            diagnostic.dns_resolution_time_ms = dns_time
            
            if not dns_success:
                diagnostic.error_message = f"DNS解析失败: {host}"
                return diagnostic
            
            logger.info(f"DNS解析成功: {host} -> {ip_addresses}")
            
            # 网络连通性测试
            ping_success, ping_time = self.network_diagnostics.ping_host(host)
            diagnostic.network_latency_ms = ping_time
            
            if not ping_success:
                logger.warning(f"Ping测试失败: {host}")
            
            # TCP连接测试
            tcp_success, tcp_time = self.network_diagnostics.test_tcp_connection(host, port)
            
            if not tcp_success:
                diagnostic.error_message = f"TCP连接失败: {host}:{port}"
                return diagnostic
            
            logger.info(f"TCP连接成功: {host}:{port} ({tcp_time:.2f}ms)")
            
            # WebSocket连接测试
            start_time = time.time()
            
            try:
                websocket = await asyncio.wait_for(
                    websockets.connect(url, ping_timeout=timeout),
                    timeout=timeout
                )
                
                diagnostic.connection_time_ms = (time.time() - start_time) * 1000
                diagnostic.response_code = 101  # WebSocket升级成功
                
                # 获取SSL信息
                if diagnostic.ssl_enabled and hasattr(websocket, 'transport'):
                    ssl_object = websocket.transport.get_extra_info('ssl_object')
                    if ssl_object:
                        diagnostic.ssl_version = ssl_object.version()
                
                await websocket.close()
                logger.info(f"WebSocket连接成功: {url} ({diagnostic.connection_time_ms:.2f}ms)")
                
            except asyncio.TimeoutError:
                diagnostic.error_message = f"WebSocket连接超时 ({timeout}s)"
            except InvalidStatusCode as e:
                diagnostic.response_code = e.status_code
                diagnostic.error_message = f"WebSocket握手失败: HTTP {e.status_code}"
            except Exception as e:
                diagnostic.error_message = f"WebSocket连接失败: {str(e)}"
            
        except Exception as e:
            diagnostic.error_message = f"诊断过程出错: {str(e)}"
        
        self.diagnostic_history.append(diagnostic)
        return diagnostic
    
    async def test_message_exchange(self, url: str, test_message: Dict[str, Any] = None) -> Dict[str, Any]:
        """测试消息收发
        
        Args:
            url: WebSocket URL
            test_message: 测试消息
            
        Returns:
            Dict: 测试结果
        """
        if test_message is None:
            test_message = {
                "type": "ping",
                "timestamp": datetime.now().isoformat(),
                "test_data": "WebSocket诊断测试"
            }
        
        result = {
            "success": False,
            "send_time_ms": 0.0,
            "receive_time_ms": 0.0,
            "round_trip_time_ms": 0.0,
            "message_sent": False,
            "message_received": False,
            "response_data": None,
            "error": None
        }
        
        try:
            websocket = await websockets.connect(url, ping_timeout=10)
            
            # 发送测试消息
            send_start = time.time()
            await websocket.send(json.dumps(test_message))
            result["send_time_ms"] = (time.time() - send_start) * 1000
            result["message_sent"] = True
            
            # 等待响应
            try:
                receive_start = time.time()
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                result["receive_time_ms"] = (time.time() - receive_start) * 1000
                result["message_received"] = True
                result["round_trip_time_ms"] = result["send_time_ms"] + result["receive_time_ms"]
                
                try:
                    result["response_data"] = json.loads(response)
                except json.JSONDecodeError:
                    result["response_data"] = response
                
                result["success"] = True
                
            except asyncio.TimeoutError:
                result["error"] = "等待响应超时"
            
            await websocket.close()
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def analyze_connection_pattern(self, hours: int = 24) -> Dict[str, Any]:
        """分析连接模式
        
        Args:
            hours: 分析时间范围（小时）
            
        Returns:
            Dict: 分析结果
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_diagnostics = [
            d for d in self.diagnostic_history
            if d.timestamp >= cutoff_time
        ]
        
        if not recent_diagnostics:
            return {"error": "没有足够的诊断数据"}
        
        # 统计分析
        total_attempts = len(recent_diagnostics)
        successful_connections = len([d for d in recent_diagnostics if not d.error_message])
        success_rate = successful_connections / total_attempts * 100
        
        connection_times = [d.connection_time_ms for d in recent_diagnostics if d.connection_time_ms > 0]
        avg_connection_time = sum(connection_times) / len(connection_times) if connection_times else 0
        
        dns_times = [d.dns_resolution_time_ms for d in recent_diagnostics if d.dns_resolution_time_ms > 0]
        avg_dns_time = sum(dns_times) / len(dns_times) if dns_times else 0
        
        # 错误分析
        error_types = {}
        for d in recent_diagnostics:
            if d.error_message:
                error_types[d.error_message] = error_types.get(d.error_message, 0) + 1
        
        return {
            "analysis_period_hours": hours,
            "total_attempts": total_attempts,
            "successful_connections": successful_connections,
            "success_rate_percent": success_rate,
            "average_connection_time_ms": avg_connection_time,
            "average_dns_resolution_time_ms": avg_dns_time,
            "common_errors": sorted(error_types.items(), key=lambda x: x[1], reverse=True)
        }


class ProblemDiagnosticEngine:
    """问题诊断引擎"""
    
    def __init__(self):
        self.diagnostic_rules = self._load_diagnostic_rules()
    
    def _load_diagnostic_rules(self) -> List[Dict[str, Any]]:
        """加载诊断规则"""
        return [
            {
                "problem_type": ProblemType.CONNECTION_FAILED,
                "symptoms": ["连接超时", "连接被拒绝", "DNS解析失败"],
                "conditions": lambda d: d.error_message and ("超时" in d.error_message or "拒绝" in d.error_message),
                "severity": Severity.HIGH,
                "solutions": [
                    "检查网络连接",
                    "验证服务器地址和端口",
                    "检查防火墙设置",
                    "确认服务器是否运行"
                ]
            },
            {
                "problem_type": ProblemType.SLOW_RESPONSE,
                "symptoms": ["连接时间过长", "响应延迟高"],
                "conditions": lambda d: d.connection_time_ms > 5000,
                "severity": Severity.MEDIUM,
                "solutions": [
                    "检查网络质量",
                    "优化服务器性能",
                    "考虑使用CDN",
                    "检查服务器负载"
                ]
            },
            {
                "problem_type": ProblemType.PROTOCOL_ERROR,
                "symptoms": ["HTTP状态码错误", "握手失败"],
                "conditions": lambda d: d.response_code and d.response_code != 101,
                "severity": Severity.HIGH,
                "solutions": [
                    "检查WebSocket协议支持",
                    "验证请求头信息",
                    "检查服务器配置",
                    "确认API版本兼容性"
                ]
            }
        ]
    
    def diagnose_problem(self, diagnostic: ConnectionDiagnostic) -> List[DiagnosticResult]:
        """诊断问题
        
        Args:
            diagnostic: 连接诊断信息
            
        Returns:
            List[DiagnosticResult]: 诊断结果列表
        """
        results = []
        
        for rule in self.diagnostic_rules:
            try:
                if rule["conditions"](diagnostic):
                    result = DiagnosticResult(
                        problem_type=rule["problem_type"],
                        severity=rule["severity"],
                        description=f"检测到问题: {rule['problem_type'].value}",
                        symptoms=rule["symptoms"],
                        solutions=rule["solutions"],
                        additional_info={
                            "diagnostic_data": {
                                "connection_time_ms": diagnostic.connection_time_ms,
                                "dns_time_ms": diagnostic.dns_resolution_time_ms,
                                "network_latency_ms": diagnostic.network_latency_ms,
                                "response_code": diagnostic.response_code,
                                "error_message": diagnostic.error_message
                            }
                        }
                    )
                    results.append(result)
            except Exception as e:
                logger.error(f"诊断规则执行失败: {e}")
        
        return results


class DebugWebSocketClient:
    """调试用WebSocket客户端"""
    
    def __init__(self, url: str, debug_level: str = "INFO"):
        self.url = url
        self.websocket = None
        self.is_connected = False
        self.debug_info = {
            "connection_attempts": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": [],
            "performance_metrics": []
        }
        
        # 设置调试日志级别
        debug_logger = logging.getLogger("websockets")
        debug_logger.setLevel(getattr(logging, debug_level.upper()))
    
    async def connect_with_debug(self) -> Dict[str, Any]:
        """带调试信息的连接"""
        self.debug_info["connection_attempts"] += 1
        connection_info = {
            "attempt": self.debug_info["connection_attempts"],
            "start_time": datetime.now(),
            "success": False,
            "error": None,
            "connection_time_ms": 0,
            "headers": {},
            "extensions": []
        }
        
        try:
            start_time = time.time()
            
            # 连接时记录详细信息
            self.websocket = await websockets.connect(
                self.url,
                extra_headers={"User-Agent": "DebugWebSocketClient/1.0"},
                ping_interval=20,
                ping_timeout=10
            )
            
            connection_info["connection_time_ms"] = (time.time() - start_time) * 1000
            connection_info["success"] = True
            self.is_connected = True
            
            # 记录连接信息
            if hasattr(self.websocket, 'request_headers'):
                connection_info["headers"] = dict(self.websocket.request_headers)
            
            if hasattr(self.websocket, 'extensions'):
                connection_info["extensions"] = list(self.websocket.extensions)
            
            logger.info(f"WebSocket连接成功: {self.url}")
            logger.debug(f"连接详情: {connection_info}")
            
        except Exception as e:
            connection_info["error"] = str(e)
            connection_info["traceback"] = traceback.format_exc()
            self.debug_info["errors"].append(connection_info)
            
            logger.error(f"WebSocket连接失败: {e}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
        
        return connection_info
    
    async def send_debug_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """发送调试消息"""
        if not self.is_connected or not self.websocket:
            return {"error": "WebSocket未连接"}
        
        send_info = {
            "message": message,
            "send_time": datetime.now(),
            "success": False,
            "error": None,
            "send_duration_ms": 0
        }
        
        try:
            start_time = time.time()
            message_str = json.dumps(message)
            
            await self.websocket.send(message_str)
            
            send_info["send_duration_ms"] = (time.time() - start_time) * 1000
            send_info["success"] = True
            send_info["message_size_bytes"] = len(message_str.encode('utf-8'))
            
            self.debug_info["messages_sent"] += 1
            
            logger.debug(f"消息发送成功: {message.get('type', 'unknown')} "
                        f"({send_info['message_size_bytes']} bytes, "
                        f"{send_info['send_duration_ms']:.2f}ms)")
            
        except Exception as e:
            send_info["error"] = str(e)
            send_info["traceback"] = traceback.format_exc()
            self.debug_info["errors"].append(send_info)
            
            logger.error(f"消息发送失败: {e}")
        
        return send_info
    
    async def receive_debug_message(self, timeout: float = 5.0) -> Dict[str, Any]:
        """接收调试消息"""
        if not self.is_connected or not self.websocket:
            return {"error": "WebSocket未连接"}
        
        receive_info = {
            "receive_time": datetime.now(),
            "success": False,
            "error": None,
            "message": None,
            "receive_duration_ms": 0,
            "message_size_bytes": 0
        }
        
        try:
            start_time = time.time()
            
            raw_message = await asyncio.wait_for(
                self.websocket.recv(), timeout=timeout
            )
            
            receive_info["receive_duration_ms"] = (time.time() - start_time) * 1000
            receive_info["message_size_bytes"] = len(raw_message.encode('utf-8') if isinstance(raw_message, str) else raw_message)
            
            try:
                receive_info["message"] = json.loads(raw_message)
            except json.JSONDecodeError:
                receive_info["message"] = raw_message
            
            receive_info["success"] = True
            self.debug_info["messages_received"] += 1
            
            logger.debug(f"消息接收成功: {receive_info['message_size_bytes']} bytes, "
                        f"{receive_info['receive_duration_ms']:.2f}ms")
            
        except asyncio.TimeoutError:
            receive_info["error"] = f"接收消息超时 ({timeout}s)"
        except Exception as e:
            receive_info["error"] = str(e)
            receive_info["traceback"] = traceback.format_exc()
            self.debug_info["errors"].append(receive_info)
            
            logger.error(f"消息接收失败: {e}")
        
        return receive_info
    
    async def run_connection_test(self, duration: int = 30) -> Dict[str, Any]:
        """运行连接测试"""
        test_result = {
            "test_duration_seconds": duration,
            "start_time": datetime.now(),
            "connection_stable": True,
            "disconnection_count": 0,
            "message_exchange_count": 0,
            "average_latency_ms": 0,
            "errors": []
        }
        
        try:
            # 连接测试
            connection_info = await self.connect_with_debug()
            if not connection_info["success"]:
                test_result["connection_stable"] = False
                test_result["errors"].append(connection_info)
                return test_result
            
            # 消息交换测试
            latencies = []
            start_time = time.time()
            
            while time.time() - start_time < duration:
                try:
                    # 发送ping消息
                    ping_message = {
                        "type": "ping",
                        "timestamp": datetime.now().isoformat(),
                        "test_id": int(time.time() * 1000)
                    }
                    
                    send_start = time.time()
                    send_info = await self.send_debug_message(ping_message)
                    
                    if send_info["success"]:
                        # 等待响应
                        receive_info = await self.receive_debug_message(timeout=5.0)
                        
                        if receive_info["success"]:
                            latency = (time.time() - send_start) * 1000
                            latencies.append(latency)
                            test_result["message_exchange_count"] += 1
                        else:
                            test_result["errors"].append(receive_info)
                    else:
                        test_result["errors"].append(send_info)
                    
                    await asyncio.sleep(1)  # 每秒一次测试
                    
                except Exception as e:
                    test_result["errors"].append({
                        "error": str(e),
                        "timestamp": datetime.now()
                    })
                    test_result["disconnection_count"] += 1
            
            # 计算平均延迟
            if latencies:
                test_result["average_latency_ms"] = sum(latencies) / len(latencies)
            
            await self.disconnect()
            
        except Exception as e:
            test_result["connection_stable"] = False
            test_result["errors"].append({
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now()
            })
        
        test_result["end_time"] = datetime.now()
        return test_result
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("WebSocket连接已断开")
    
    def get_debug_summary(self) -> Dict[str, Any]:
        """获取调试摘要"""
        return {
            "connection_attempts": self.debug_info["connection_attempts"],
            "messages_sent": self.debug_info["messages_sent"],
            "messages_received": self.debug_info["messages_received"],
            "total_errors": len(self.debug_info["errors"]),
            "error_types": list(set([
                error.get("error", "unknown") for error in self.debug_info["errors"]
            ])),
            "success_rate": (
                (self.debug_info["messages_sent"] + self.debug_info["messages_received"]) /
                max(self.debug_info["connection_attempts"] * 2, 1) * 100
            )
        }


async def demo_connection_diagnostics():
    """连接诊断演示"""
    print("🔍 WebSocket 连接诊断演示")
    
    # 创建诊断工具
    diagnostics = WebSocketDiagnostics()
    diagnostic_engine = ProblemDiagnosticEngine()
    
    # 测试URL列表
    test_urls = [
        "ws://localhost:8765",  # 正常服务
        "ws://localhost:9999",  # 不存在的服务
        "ws://nonexistent.example.com:8765",  # 不存在的主机
        "wss://echo.websocket.org"  # 公共测试服务
    ]
    
    print(f"📡 测试 {len(test_urls)} 个WebSocket服务...")
    
    for url in test_urls:
        print(f"\n🔗 诊断: {url}")
        
        try:
            # 执行诊断
            diagnostic = await diagnostics.diagnose_connection(url, timeout=10.0)
            
            # 显示诊断结果
            if diagnostic.error_message:
                print(f"❌ 连接失败: {diagnostic.error_message}")
            else:
                print(f"✅ 连接成功: {diagnostic.connection_time_ms:.2f}ms")
            
            print(f"   DNS解析: {diagnostic.dns_resolution_time_ms:.2f}ms")
            print(f"   网络延迟: {diagnostic.network_latency_ms:.2f}ms")
            
            if diagnostic.ssl_enabled:
                print(f"   SSL版本: {diagnostic.ssl_version}")
            
            # 问题诊断
            problems = diagnostic_engine.diagnose_problem(diagnostic)
            if problems:
                print(f"⚠️ 发现 {len(problems)} 个问题:")
                for problem in problems:
                    print(f"   - {problem.problem_type.value} ({problem.severity.value})")
                    print(f"     症状: {', '.join(problem.symptoms)}")
                    print(f"     建议: {problem.solutions[0] if problem.solutions else '无'}")
            
        except Exception as e:
            print(f"❌ 诊断失败: {e}")
    
    # 分析连接模式
    print(f"\n📊 连接模式分析:")
    analysis = diagnostics.analyze_connection_pattern(hours=1)
    
    if "error" not in analysis:
        print(f"   总尝试次数: {analysis['total_attempts']}")
        print(f"   成功连接: {analysis['successful_connections']}")
        print(f"   成功率: {analysis['success_rate_percent']:.1f}%")
        print(f"   平均连接时间: {analysis['average_connection_time_ms']:.2f}ms")
        
        if analysis['common_errors']:
            print(f"   常见错误:")
            for error, count in analysis['common_errors'][:3]:
                print(f"     - {error}: {count} 次")


async def demo_message_debugging():
    """消息调试演示"""
    print("🐛 WebSocket 消息调试演示")
    
    # 创建调试客户端
    debug_client = DebugWebSocketClient(
        url="ws://localhost:8765",
        debug_level="DEBUG"
    )
    
    try:
        print("🔗 连接到WebSocket服务...")
        connection_info = await debug_client.connect_with_debug()
        
        if not connection_info["success"]:
            print(f"❌ 连接失败: {connection_info['error']}")
            return
        
        print(f"✅ 连接成功 ({connection_info['connection_time_ms']:.2f}ms)")
        
        # 测试消息发送
        print("\n📤 测试消息发送...")
        test_messages = [
            {"type": "ping", "data": "test"},
            {"type": "subscribe", "data": {"symbol": "000001.SZ", "data_type": "quote"}},
            {"type": "get_stats", "data": {}},
            {"type": "invalid_message", "data": "this should cause an error"}
        ]
        
        for message in test_messages:
            print(f"发送: {message['type']}")
            send_info = await debug_client.send_debug_message(message)
            
            if send_info["success"]:
                print(f"  ✅ 发送成功 ({send_info['send_duration_ms']:.2f}ms, "
                      f"{send_info['message_size_bytes']} bytes)")
                
                # 尝试接收响应
                receive_info = await debug_client.receive_debug_message(timeout=3.0)
                if receive_info["success"]:
                    response_type = receive_info["message"].get("type", "unknown") if isinstance(receive_info["message"], dict) else "raw"
                    print(f"  📥 收到响应: {response_type} ({receive_info['receive_duration_ms']:.2f}ms)")
                else:
                    print(f"  ⚠️ 未收到响应: {receive_info['error']}")
            else:
                print(f"  ❌ 发送失败: {send_info['error']}")
            
            await asyncio.sleep(1)
        
        # 显示调试摘要
        print(f"\n📊 调试摘要:")
        summary = debug_client.get_debug_summary()
        print(f"   连接尝试: {summary['connection_attempts']}")
        print(f"   发送消息: {summary['messages_sent']}")
        print(f"   接收消息: {summary['messages_received']}")
        print(f"   错误次数: {summary['total_errors']}")
        print(f"   成功率: {summary['success_rate']:.1f}%")
        
        if summary['error_types']:
            print(f"   错误类型: {', '.join(summary['error_types'])}")
        
    except Exception as e:
        print(f"❌ 调试演示失败: {e}")
        print(f"错误详情: {traceback.format_exc()}")
    finally:
        await debug_client.disconnect()


async def demo_performance_debugging():
    """性能调试演示"""
    print("⚡ WebSocket 性能调试演示")
    
    debug_client = DebugWebSocketClient("ws://localhost:8765")
    
    try:
        print("🏃 运行30秒连接稳定性测试...")
        test_result = await debug_client.run_connection_test(duration=30)
        
        print(f"\n📊 测试结果:")
        print(f"   测试时长: {test_result['test_duration_seconds']} 秒")
        print(f"   连接稳定: {'✅' if test_result['connection_stable'] else '❌'}")
        print(f"   断线次数: {test_result['disconnection_count']}")
        print(f"   消息交换: {test_result['message_exchange_count']} 次")
        print(f"   平均延迟: {test_result['average_latency_ms']:.2f}ms")
        print(f"   错误次数: {len(test_result['errors'])}")
        
        if test_result['errors']:
            print(f"\n❌ 错误详情:")
            for i, error in enumerate(test_result['errors'][:3]):  # 显示前3个错误
                print(f"   {i+1}. {error.get('error', 'Unknown error')}")
        
        # 性能评估
        print(f"\n📈 性能评估:")
        if test_result['average_latency_ms'] < 50:
            print("   延迟: 优秀 (<50ms)")
        elif test_result['average_latency_ms'] < 100:
            print("   延迟: 良好 (50-100ms)")
        elif test_result['average_latency_ms'] < 200:
            print("   延迟: 一般 (100-200ms)")
        else:
            print("   延迟: 较差 (>200ms)")
        
        if test_result['disconnection_count'] == 0:
            print("   稳定性: 优秀 (无断线)")
        elif test_result['disconnection_count'] <= 2:
            print("   稳定性: 良好 (偶尔断线)")
        else:
            print("   稳定性: 较差 (频繁断线)")
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")


def print_troubleshooting_guide():
    """打印故障排除指南"""
    print("\n" + "="*60)
    print("📚 WebSocket 故障排除指南")
    print("="*60)
    
    troubleshooting_guide = {
        "连接问题": {
            "症状": ["连接超时", "连接被拒绝", "握手失败"],
            "可能原因": [
                "服务器未运行或不可达",
                "防火墙阻止连接",
                "网络配置问题",
                "DNS解析失败"
            ],
            "解决方案": [
                "1. 检查服务器状态: telnet <host> <port>",
                "2. 验证防火墙设置",
                "3. 测试网络连通性: ping <host>",
                "4. 检查DNS解析: nslookup <host>",
                "5. 确认WebSocket服务正常运行"
            ]
        },
        "性能问题": {
            "症状": ["响应缓慢", "高延迟", "消息丢失"],
            "可能原因": [
                "网络带宽不足",
                "服务器负载过高",
                "客户端处理能力不足",
                "消息队列积压"
            ],
            "解决方案": [
                "1. 监控网络带宽使用",
                "2. 检查服务器CPU和内存使用",
                "3. 优化消息处理逻辑",
                "4. 实现消息批处理",
                "5. 使用数据压缩"
            ]
        },
        "数据问题": {
            "症状": ["数据格式错误", "消息乱序", "数据不一致"],
            "可能原因": [
                "JSON序列化/反序列化错误",
                "字符编码问题",
                "并发处理导致的竞态条件",
                "缓存同步问题"
            ],
            "解决方案": [
                "1. 验证JSON格式和编码",
                "2. 实现消息序号机制",
                "3. 添加数据校验",
                "4. 使用事务处理",
                "5. 实现数据一致性检查"
            ]
        },
        "安全问题": {
            "症状": ["认证失败", "权限错误", "连接被拒绝"],
            "可能原因": [
                "认证令牌过期或无效",
                "SSL/TLS配置错误",
                "跨域请求被阻止",
                "权限配置不正确"
            ],
            "解决方案": [
                "1. 检查认证令牌有效性",
                "2. 验证SSL证书配置",
                "3. 配置CORS策略",
                "4. 检查用户权限设置",
                "5. 启用详细的安全日志"
            ]
        }
    }
    
    for category, info in troubleshooting_guide.items():
        print(f"\n🔧 {category}")
        print(f"症状: {', '.join(info['症状'])}")
        print(f"可能原因:")
        for cause in info['可能原因']:
            print(f"  • {cause}")
        print(f"解决方案:")
        for solution in info['解决方案']:
            print(f"  {solution}")


async def main():
    """主函数"""
    print("🎓 WebSocket 故障排除和调试指南")
    print("本指南帮助您诊断和解决 WebSocket 相关问题")
    
    try:
        # 运行连接诊断演示
        await demo_connection_diagnostics()
        
        print("\n" + "="*60)
        input("按 Enter 键继续消息调试演示...")
        
        # 运行消息调试演示
        await demo_message_debugging()
        
        print("\n" + "="*60)
        input("按 Enter 键继续性能调试演示...")
        
        # 运行性能调试演示
        await demo_performance_debugging()
        
        # 显示故障排除指南
        print_troubleshooting_guide()
        
    except KeyboardInterrupt:
        print("\n⏹️ 演示被用户中断")
    except Exception as e:
        print(f"❌ 演示运行出错: {e}")
        print(f"错误详情: {traceback.format_exc()}")
    
    print("\n🎉 WebSocket 故障排除指南完成！")
    print("\n📚 调试要点总结：")
    print("1. 系统性诊断 - 从网络到应用层逐步排查")
    print("2. 详细日志记录 - 记录关键操作和错误信息")
    print("3. 性能监控 - 持续监控连接和消息处理性能")
    print("4. 自动化测试 - 定期执行连接和功能测试")
    print("5. 问题分类 - 按问题类型制定解决方案")
    print("\n💡 最佳实践建议：")
    print("- 建立完善的监控和告警机制")
    print("- 实现自动重连和错误恢复")
    print("- 定期进行压力测试和稳定性测试")
    print("- 保持详细的操作和错误日志")
    print("- 建立问题处理流程和知识库")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 指南结束")
    except Exception as e:
        logger.error(f"指南运行失败: {e}")
        sys.exit(1)