#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebSocket 性能优化和最佳实践教程

本教程深入探讨 WebSocket 实时数据系统的性能优化技巧和最佳实践，
包括连接优化、数据压缩、批量处理、内存管理、错误处理等方面。

学习目标：
1. 掌握 WebSocket 连接性能优化技巧
2. 学会数据压缩和批量处理策略
3. 了解内存管理和资源优化方法
4. 掌握错误处理和恢复最佳实践
5. 学会性能监控和调优方法

前置条件：
- 已完成 WebSocket 基础教程（08-09）
- 了解 Python 异步编程
- 熟悉性能分析工具

作者: Argus 开发团队
创建时间: 2025-01-15
最后更新: 2025-01-15
"""

import asyncio
import json
import logging
import time
import sys
import gc
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import websockets
import zlib
import gzip
import pickle
from collections import deque, defaultdict
from dataclasses import dataclass, field
import numpy as np
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor
import aiofiles
import uvloop  # 高性能事件循环（需要安装：pip install uvloop）

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    message_rate: float = 0.0
    latency_ms: float = 0.0
    connection_count: int = 0
    error_rate: float = 0.0


@dataclass
class OptimizationConfig:
    """优化配置"""
    # 连接优化
    max_connections: int = 1000
    connection_pool_size: int = 100
    ping_interval: int = 20
    ping_timeout: int = 10
    
    # 数据处理优化
    enable_compression: bool = True
    compression_threshold: int = 1024
    batch_size: int = 100
    batch_timeout: float = 0.1
    
    # 内存管理
    max_message_history: int = 10000
    gc_interval: float = 60.0
    memory_threshold_mb: float = 512.0
    
    # 性能监控
    metrics_interval: float = 5.0
    enable_profiling: bool = False


class CompressionManager:
    """数据压缩管理器
    
    提供多种压缩算法和自适应压缩策略
    """
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.compression_stats = {
            'total_compressed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'compression_time': 0.0
        }
    
    def compress_data(self, data: str, algorithm: str = 'gzip') -> bytes:
        """压缩数据
        
        Args:
            data: 原始数据
            algorithm: 压缩算法 ('gzip', 'zlib', 'lz4')
            
        Returns:
            bytes: 压缩后的数据
        """
        if len(data) < self.config.compression_threshold:
            return data.encode('utf-8')
        
        start_time = time.time()
        original_size = len(data.encode('utf-8'))
        
        try:
            if algorithm == 'gzip':
                compressed = gzip.compress(data.encode('utf-8'))
            elif algorithm == 'zlib':
                compressed = zlib.compress(data.encode('utf-8'))
            else:
                # 默认使用 gzip
                compressed = gzip.compress(data.encode('utf-8'))
            
            # 更新统计
            compression_time = time.time() - start_time
            self.compression_stats['total_compressed'] += 1
            self.compression_stats['total_original_size'] += original_size
            self.compression_stats['total_compressed_size'] += len(compressed)
            self.compression_stats['compression_time'] += compression_time
            
            return compressed
            
        except Exception as e:
            logger.error(f"数据压缩失败: {e}")
            return data.encode('utf-8')
    
    def decompress_data(self, data: bytes, algorithm: str = 'gzip') -> str:
        """解压数据
        
        Args:
            data: 压缩数据
            algorithm: 压缩算法
            
        Returns:
            str: 解压后的数据
        """
        try:
            if algorithm == 'gzip':
                decompressed = gzip.decompress(data)
            elif algorithm == 'zlib':
                decompressed = zlib.decompress(data)
            else:
                decompressed = gzip.decompress(data)
            
            return decompressed.decode('utf-8')
            
        except Exception as e:
            logger.error(f"数据解压失败: {e}")
            return data.decode('utf-8')
    
    def get_compression_ratio(self) -> float:
        """获取压缩比"""
        if self.compression_stats['total_original_size'] == 0:
            return 0.0
        
        return (1 - self.compression_stats['total_compressed_size'] / 
                self.compression_stats['total_original_size']) * 100
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """获取压缩统计信息"""
        stats = self.compression_stats.copy()
        stats['compression_ratio'] = self.get_compression_ratio()
        stats['avg_compression_time'] = (
            stats['compression_time'] / max(stats['total_compressed'], 1)
        )
        return stats


class BatchProcessor:
    """批量处理器
    
    将多个消息批量处理以提高性能
    """
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.message_queue = asyncio.Queue()
        self.batch_buffer = []
        self.last_flush_time = time.time()
        self.is_running = False
        self.process_task = None
        
        # 统计信息
        self.stats = {
            'total_messages': 0,
            'total_batches': 0,
            'avg_batch_size': 0.0,
            'processing_time': 0.0
        }
    
    async def start(self):
        """启动批量处理器"""
        self.is_running = True
        self.process_task = asyncio.create_task(self._process_loop())
        logger.info("批量处理器已启动")
    
    async def stop(self):
        """停止批量处理器"""
        self.is_running = False
        
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
        
        # 处理剩余消息
        if self.batch_buffer:
            await self._flush_batch()
        
        logger.info("批量处理器已停止")
    
    async def add_message(self, message: Dict[str, Any]):
        """添加消息到批量处理队列
        
        Args:
            message: 消息内容
        """
        await self.message_queue.put(message)
        self.stats['total_messages'] += 1
    
    async def _process_loop(self):
        """批量处理循环"""
        try:
            while self.is_running:
                try:
                    # 等待消息或超时
                    message = await asyncio.wait_for(
                        self.message_queue.get(), 
                        timeout=self.config.batch_timeout
                    )
                    
                    self.batch_buffer.append(message)
                    
                    # 检查是否需要刷新批次
                    if (len(self.batch_buffer) >= self.config.batch_size or
                        time.time() - self.last_flush_time >= self.config.batch_timeout):
                        await self._flush_batch()
                    
                except asyncio.TimeoutError:
                    # 超时，刷新当前批次
                    if self.batch_buffer:
                        await self._flush_batch()
                    continue
                    
        except asyncio.CancelledError:
            logger.debug("批量处理循环被取消")
        except Exception as e:
            logger.error(f"批量处理循环出错: {e}")
    
    async def _flush_batch(self):
        """刷新批次"""
        if not self.batch_buffer:
            return
        
        start_time = time.time()
        batch_size = len(self.batch_buffer)
        
        try:
            # 处理批次消息
            await self._process_batch(self.batch_buffer.copy())
            
            # 更新统计
            processing_time = time.time() - start_time
            self.stats['total_batches'] += 1
            self.stats['processing_time'] += processing_time
            self.stats['avg_batch_size'] = (
                self.stats['total_messages'] / self.stats['total_batches']
            )
            
            logger.debug(f"处理批次: {batch_size} 条消息，耗时 {processing_time*1000:.2f}ms")
            
        except Exception as e:
            logger.error(f"批次处理失败: {e}")
        finally:
            self.batch_buffer.clear()
            self.last_flush_time = time.time()
    
    async def _process_batch(self, messages: List[Dict[str, Any]]):
        """处理批次消息
        
        Args:
            messages: 消息列表
        """
        # 这里可以实现具体的批量处理逻辑
        # 例如：批量写入数据库、批量发送通知等
        
        # 示例：按消息类型分组处理
        message_groups = defaultdict(list)
        for message in messages:
            message_type = message.get('type', 'unknown')
            message_groups[message_type].append(message)
        
        # 并行处理不同类型的消息
        tasks = []
        for message_type, group_messages in message_groups.items():
            task = asyncio.create_task(
                self._process_message_group(message_type, group_messages)
            )
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_message_group(self, message_type: str, messages: List[Dict[str, Any]]):
        """处理特定类型的消息组
        
        Args:
            message_type: 消息类型
            messages: 消息列表
        """
        # 根据消息类型实现不同的处理逻辑
        if message_type == 'market_data':
            await self._process_market_data_batch(messages)
        elif message_type == 'trade_data':
            await self._process_trade_data_batch(messages)
        else:
            logger.debug(f"处理 {len(messages)} 条 {message_type} 消息")
    
    async def _process_market_data_batch(self, messages: List[Dict[str, Any]]):
        """批量处理市场数据"""
        # 示例：批量更新价格缓存
        logger.debug(f"批量处理 {len(messages)} 条市场数据")
    
    async def _process_trade_data_batch(self, messages: List[Dict[str, Any]]):
        """批量处理交易数据"""
        # 示例：批量计算交易统计
        logger.debug(f"批量处理 {len(messages)} 条交易数据")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批量处理统计信息"""
        stats = self.stats.copy()
        stats['queue_size'] = self.message_queue.qsize()
        stats['buffer_size'] = len(self.batch_buffer)
        return stats


class MemoryManager:
    """内存管理器
    
    监控和优化内存使用
    """
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.process = psutil.Process()
        self.gc_task = None
        self.is_running = False
        
        # 内存统计
        self.memory_stats = {
            'peak_memory_mb': 0.0,
            'gc_collections': 0,
            'objects_collected': 0,
            'memory_warnings': 0
        }
    
    async def start(self):
        """启动内存管理器"""
        self.is_running = True
        self.gc_task = asyncio.create_task(self._gc_loop())
        logger.info("内存管理器已启动")
    
    async def stop(self):
        """停止内存管理器"""
        self.is_running = False
        
        if self.gc_task:
            self.gc_task.cancel()
            try:
                await self.gc_task
            except asyncio.CancelledError:
                pass
        
        logger.info("内存管理器已停止")
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用量（MB）"""
        try:
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # 更新峰值内存
            if memory_mb > self.memory_stats['peak_memory_mb']:
                self.memory_stats['peak_memory_mb'] = memory_mb
            
            return memory_mb
        except Exception as e:
            logger.error(f"获取内存使用量失败: {e}")
            return 0.0
    
    def check_memory_threshold(self) -> bool:
        """检查内存是否超过阈值"""
        current_memory = self.get_memory_usage()
        
        if current_memory > self.config.memory_threshold_mb:
            self.memory_stats['memory_warnings'] += 1
            logger.warning(f"内存使用量 {current_memory:.1f}MB 超过阈值 {self.config.memory_threshold_mb}MB")
            return True
        
        return False
    
    async def _gc_loop(self):
        """垃圾回收循环"""
        try:
            while self.is_running:
                await asyncio.sleep(self.config.gc_interval)
                
                if self.is_running:
                    await self._perform_gc()
                    
        except asyncio.CancelledError:
            logger.debug("垃圾回收循环被取消")
        except Exception as e:
            logger.error(f"垃圾回收循环出错: {e}")
    
    async def _perform_gc(self):
        """执行垃圾回收"""
        try:
            memory_before = self.get_memory_usage()
            
            # 执行垃圾回收
            collected = gc.collect()
            
            memory_after = self.get_memory_usage()
            memory_freed = memory_before - memory_after
            
            # 更新统计
            self.memory_stats['gc_collections'] += 1
            self.memory_stats['objects_collected'] += collected
            
            if memory_freed > 1.0:  # 释放超过1MB时记录日志
                logger.info(f"垃圾回收: 释放 {memory_freed:.1f}MB 内存，回收 {collected} 个对象")
            
            # 检查内存阈值
            self.check_memory_threshold()
            
        except Exception as e:
            logger.error(f"垃圾回收失败: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        stats = self.memory_stats.copy()
        stats['current_memory_mb'] = self.get_memory_usage()
        stats['memory_threshold_mb'] = self.config.memory_threshold_mb
        return stats


class PerformanceMonitor:
    """性能监控器
    
    监控系统性能指标和WebSocket性能
    """
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.process = psutil.Process()
        self.metrics_history = deque(maxlen=1000)
        self.monitor_task = None
        self.is_running = False
        
        # 性能统计
        self.performance_stats = {
            'avg_cpu_percent': 0.0,
            'avg_memory_mb': 0.0,
            'peak_message_rate': 0.0,
            'avg_latency_ms': 0.0,
            'total_network_bytes': 0
        }
        
        # 消息统计
        self.message_counter = 0
        self.last_message_count = 0
        self.last_metrics_time = time.time()
    
    async def start(self):
        """启动性能监控器"""
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("性能监控器已启动")
    
    async def stop(self):
        """停止性能监控器"""
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("性能监控器已停止")
    
    def record_message(self):
        """记录消息"""
        self.message_counter += 1
    
    def record_latency(self, latency_ms: float):
        """记录延迟"""
        # 更新平均延迟
        if self.performance_stats['avg_latency_ms'] == 0:
            self.performance_stats['avg_latency_ms'] = latency_ms
        else:
            self.performance_stats['avg_latency_ms'] = (
                self.performance_stats['avg_latency_ms'] * 0.9 + latency_ms * 0.1
            )
    
    async def _monitor_loop(self):
        """监控循环"""
        try:
            while self.is_running:
                await asyncio.sleep(self.config.metrics_interval)
                
                if self.is_running:
                    await self._collect_metrics()
                    
        except asyncio.CancelledError:
            logger.debug("性能监控循环被取消")
        except Exception as e:
            logger.error(f"性能监控循环出错: {e}")
    
    async def _collect_metrics(self):
        """收集性能指标"""
        try:
            current_time = time.time()
            
            # CPU使用率
            cpu_percent = self.process.cpu_percent()
            
            # 内存使用量
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # 网络IO
            net_io = psutil.net_io_counters()
            network_bytes_sent = net_io.bytes_sent if net_io else 0
            network_bytes_recv = net_io.bytes_recv if net_io else 0
            
            # 消息速率
            time_diff = current_time - self.last_metrics_time
            message_diff = self.message_counter - self.last_message_count
            message_rate = message_diff / time_diff if time_diff > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                message_rate=message_rate,
                latency_ms=self.performance_stats['avg_latency_ms']
            )
            
            # 添加到历史记录
            self.metrics_history.append(metrics)
            
            # 更新统计
            self._update_performance_stats(metrics)
            
            # 更新计数器
            self.last_message_count = self.message_counter
            self.last_metrics_time = current_time
            
            # 记录性能日志
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"性能指标: CPU {cpu_percent:.1f}% | "
                           f"内存 {memory_mb:.1f}MB | "
                           f"消息速率 {message_rate:.1f}/s | "
                           f"延迟 {metrics.latency_ms:.1f}ms")
            
        except Exception as e:
            logger.error(f"收集性能指标失败: {e}")
    
    def _update_performance_stats(self, metrics: PerformanceMetrics):
        """更新性能统计"""
        # 更新平均值
        if self.performance_stats['avg_cpu_percent'] == 0:
            self.performance_stats['avg_cpu_percent'] = metrics.cpu_percent
        else:
            self.performance_stats['avg_cpu_percent'] = (
                self.performance_stats['avg_cpu_percent'] * 0.9 + metrics.cpu_percent * 0.1
            )
        
        if self.performance_stats['avg_memory_mb'] == 0:
            self.performance_stats['avg_memory_mb'] = metrics.memory_mb
        else:
            self.performance_stats['avg_memory_mb'] = (
                self.performance_stats['avg_memory_mb'] * 0.9 + metrics.memory_mb * 0.1
            )
        
        # 更新峰值
        if metrics.message_rate > self.performance_stats['peak_message_rate']:
            self.performance_stats['peak_message_rate'] = metrics.message_rate
        
        # 更新网络总量
        self.performance_stats['total_network_bytes'] = (
            metrics.network_bytes_sent + metrics.network_bytes_recv
        )
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前性能指标"""
        return self.metrics_history[-1] if self.metrics_history else None
    
    def get_metrics_history(self, minutes: int = 60) -> List[PerformanceMetrics]:
        """获取性能指标历史
        
        Args:
            minutes: 历史时间范围（分钟）
            
        Returns:
            List[PerformanceMetrics]: 性能指标列表
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        return [
            metrics for metrics in self.metrics_history
            if metrics.timestamp >= cutoff_time
        ]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = self.performance_stats.copy()
        stats['total_messages'] = self.message_counter
        stats['metrics_collected'] = len(self.metrics_history)
        return stats
    
    def plot_performance_metrics(self, minutes: int = 30):
        """绘制性能指标图表
        
        Args:
            minutes: 时间范围（分钟）
        """
        history = self.get_metrics_history(minutes)
        
        if not history:
            logger.warning("没有性能指标数据可绘制")
            return
        
        # 提取数据
        timestamps = [m.timestamp for m in history]
        cpu_percents = [m.cpu_percent for m in history]
        memory_mbs = [m.memory_mb for m in history]
        message_rates = [m.message_rate for m in history]
        latencies = [m.latency_ms for m in history]
        
        # 创建图表
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # CPU使用率
        ax1.plot(timestamps, cpu_percents, 'b-', linewidth=2)
        ax1.set_title('CPU 使用率')
        ax1.set_ylabel('CPU %')
        ax1.grid(True, alpha=0.3)
        
        # 内存使用量
        ax2.plot(timestamps, memory_mbs, 'g-', linewidth=2)
        ax2.set_title('内存使用量')
        ax2.set_ylabel('内存 (MB)')
        ax2.grid(True, alpha=0.3)
        
        # 消息速率
        ax3.plot(timestamps, message_rates, 'r-', linewidth=2)
        ax3.set_title('消息速率')
        ax3.set_ylabel('消息/秒')
        ax3.grid(True, alpha=0.3)
        
        # 延迟
        ax4.plot(timestamps, latencies, 'm-', linewidth=2)
        ax4.set_title('平均延迟')
        ax4.set_ylabel('延迟 (ms)')
        ax4.grid(True, alpha=0.3)
        
        # 格式化时间轴
        for ax in [ax1, ax2, ax3, ax4]:
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.show()


class OptimizedWebSocketClient:
    """优化的WebSocket客户端
    
    集成所有性能优化功能
    """
    
    def __init__(self, 
                 uri: str = "ws://localhost:8765",
                 config: OptimizationConfig = None):
        """初始化优化客户端
        
        Args:
            uri: WebSocket服务地址
            config: 优化配置
        """
        self.uri = uri
        self.config = config or OptimizationConfig()
        self.client_id = f"optimized_client_{int(time.time())}"
        
        # WebSocket连接
        self.websocket = None
        self.is_connected = False
        self.is_running = False
        
        # 优化组件
        self.compression_manager = CompressionManager(self.config)
        self.batch_processor = BatchProcessor(self.config)
        self.memory_manager = MemoryManager(self.config)
        self.performance_monitor = PerformanceMonitor(self.config)
        
        # 数据存储（使用高效的数据结构）
        self.message_cache = deque(maxlen=self.config.max_message_history)
        self.subscription_cache = {}
        
        # 异步任务
        self.receive_task = None
        self.heartbeat_task = None
        
        # 统计信息
        self.client_stats = {
            'start_time': None,
            'messages_sent': 0,
            'messages_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'compression_enabled': self.config.enable_compression,
            'batch_processing_enabled': True
        }
    
    async def start(self):
        """启动优化客户端"""
        logger.info("🚀 启动优化WebSocket客户端")
        
        try:
            # 启动优化组件
            await self.batch_processor.start()
            await self.memory_manager.start()
            await self.performance_monitor.start()
            
            # 连接WebSocket
            await self._connect()
            
            self.client_stats['start_time'] = datetime.now()
            logger.info("✅ 优化客户端启动成功")
            
        except Exception as e:
            logger.error(f"启动优化客户端失败: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """停止优化客户端"""
        logger.info("⏹️ 停止优化WebSocket客户端")
        
        self.is_running = False
        self.is_connected = False
        
        # 停止异步任务
        tasks = [self.receive_task, self.heartbeat_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 关闭WebSocket连接
        if self.websocket:
            await self.websocket.close()
        
        # 停止优化组件
        await self.batch_processor.stop()
        await self.memory_manager.stop()
        await self.performance_monitor.stop()
        
        logger.info("优化客户端已停止")
    
    async def _connect(self):
        """连接WebSocket服务器"""
        try:
            logger.info(f"连接到 {self.uri}")
            
            # 使用优化的连接参数
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
                max_size=2**20,  # 1MB
                max_queue=2**5,  # 32
                compression=None  # 使用自定义压缩
            )
            
            self.is_connected = True
            self.is_running = True
            
            # 启动异步任务
            self.receive_task = asyncio.create_task(self._receive_loop())
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            logger.info("WebSocket连接成功")
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            raise
    
    async def _receive_loop(self):
        """消息接收循环"""
        try:
            while self.is_running and self.websocket:
                try:
                    # 接收消息
                    raw_message = await asyncio.wait_for(
                        self.websocket.recv(), timeout=1.0
                    )
                    
                    # 记录性能指标
                    self.performance_monitor.record_message()
                    
                    # 处理消息
                    await self._handle_raw_message(raw_message)
                    
                    # 更新统计
                    self.client_stats['messages_received'] += 1
                    if isinstance(raw_message, bytes):
                        self.client_stats['bytes_received'] += len(raw_message)
                    else:
                        self.client_stats['bytes_received'] += len(raw_message.encode('utf-8'))
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"接收消息时出错: {e}")
                    break
                    
        except asyncio.CancelledError:
            logger.debug("消息接收循环被取消")
        except Exception as e:
            logger.error(f"消息接收循环出错: {e}")
        finally:
            self.is_connected = False
    
    async def _handle_raw_message(self, raw_message):
        """处理原始消息"""
        try:
            # 解压消息（如果需要）
            if isinstance(raw_message, bytes):
                try:
                    message_str = self.compression_manager.decompress_data(raw_message)
                except:
                    message_str = raw_message.decode('utf-8')
            else:
                message_str = raw_message
            
            # 解析JSON
            message = json.loads(message_str)
            
            # 添加到批量处理器
            await self.batch_processor.add_message(message)
            
            # 添加到消息缓存
            self.message_cache.append({
                'timestamp': datetime.now(),
                'message': message
            })
            
            # 处理特定类型的消息
            await self._handle_message(message)
            
        except Exception as e:
            logger.error(f"处理原始消息失败: {e}")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """处理解析后的消息"""
        message_type = message.get("type", "unknown")
        
        if message_type == "market_data":
            await self._handle_market_data(message.get("data", {}))
        elif message_type == "heartbeat":
            await self._handle_heartbeat_response(message.get("data", {}))
        # 添加其他消息类型处理...
    
    async def _handle_market_data(self, data: Dict[str, Any]):
        """处理市场数据"""
        symbol = data.get("symbol", "")
        price = data.get("last_price", 0)
        
        # 记录延迟（如果有时间戳）
        if "timestamp" in data:
            try:
                server_time = datetime.fromisoformat(data["timestamp"])
                latency = (datetime.now() - server_time).total_seconds() * 1000
                self.performance_monitor.record_latency(latency)
            except:
                pass
        
        logger.debug(f"📈 {symbol}: ¥{price}")
    
    async def _handle_heartbeat_response(self, data: Dict[str, Any]):
        """处理心跳响应"""
        server_time = data.get("server_time")
        if server_time:
            try:
                server_dt = datetime.fromisoformat(server_time)
                latency = (datetime.now() - server_dt).total_seconds() * 1000
                self.performance_monitor.record_latency(latency)
            except:
                pass
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        try:
            while self.is_running and self.is_connected:
                await asyncio.sleep(30)  # 每30秒发送心跳
                
                if self.is_running and self.is_connected:
                    await self._send_heartbeat()
                    
        except asyncio.CancelledError:
            logger.debug("心跳循环被取消")
        except Exception as e:
            logger.error(f"心跳循环出错: {e}")
    
    async def _send_heartbeat(self):
        """发送心跳"""
        try:
            heartbeat_msg = {
                "type": "heartbeat",
                "data": {
                    "client_time": datetime.now().isoformat(),
                    "client_id": self.client_id
                }
            }
            
            await self.send_message(heartbeat_msg)
            
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")
    
    async def send_message(self, message: Dict[str, Any]):
        """发送消息（带优化）
        
        Args:
            message: 消息内容
        """
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket未连接，无法发送消息")
            return
        
        try:
            # 序列化消息
            message_str = json.dumps(message)
            
            # 压缩消息（如果启用）
            if self.config.enable_compression:
                message_data = self.compression_manager.compress_data(message_str)
            else:
                message_data = message_str
            
            # 发送消息
            await self.websocket.send(message_data)
            
            # 更新统计
            self.client_stats['messages_sent'] += 1
            if isinstance(message_data, bytes):
                self.client_stats['bytes_sent'] += len(message_data)
            else:
                self.client_stats['bytes_sent'] += len(message_data.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    async def subscribe(self, symbol: str, data_type: str = "quote"):
        """订阅数据
        
        Args:
            symbol: 股票代码
            data_type: 数据类型
        """
        subscription_request = {
            "type": "subscribe",
            "data": {
                "symbol": symbol,
                "data_type": data_type,
                "client_id": self.client_id
            }
        }
        
        await self.send_message(subscription_request)
        
        # 缓存订阅信息
        subscription_key = f"{symbol}_{data_type}"
        self.subscription_cache[subscription_key] = {
            "symbol": symbol,
            "data_type": data_type,
            "subscribed_at": datetime.now()
        }
        
        logger.info(f"已订阅: {symbol} ({data_type})")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        uptime = None
        if self.client_stats['start_time']:
            uptime = str(datetime.now() - self.client_stats['start_time'])
        
        return {
            'client_stats': {
                **self.client_stats,
                'uptime': uptime,
                'is_connected': self.is_connected,
                'subscriptions_count': len(self.subscription_cache),
                'message_cache_size': len(self.message_cache)
            },
            'compression_stats': self.compression_manager.get_compression_stats(),
            'batch_processing_stats': self.batch_processor.get_stats(),
            'memory_stats': self.memory_manager.get_memory_stats(),
            'performance_stats': self.performance_monitor.get_performance_stats()
        }
    
    def plot_performance_metrics(self, minutes: int = 30):
        """绘制性能指标图表"""
        self.performance_monitor.plot_performance_metrics(minutes)


async def demo_basic_optimization():
    """基本优化演示"""
    print("🚀 WebSocket 基本性能优化演示")
    
    # 创建优化配置
    config = OptimizationConfig(
        enable_compression=True,
        compression_threshold=512,
        batch_size=50,
        batch_timeout=0.2,
        max_message_history=5000,
        memory_threshold_mb=256.0
    )
    
    # 创建优化客户端
    client = OptimizedWebSocketClient(
        uri="ws://localhost:8765",
        config=config
    )
    
    try:
        # 启动客户端
        await client.start()
        
        # 订阅数据
        print("📡 订阅实时数据...")
        await client.subscribe("000001.SZ", "quote")
        await client.subscribe("600519.SH", "quote")
        
        # 运行60秒
        print("⏰ 运行60秒，观察优化效果...")
        await asyncio.sleep(60)
        
        # 获取优化统计
        stats = client.get_optimization_stats()
        
        print(f"\n📊 优化统计:")
        print(f"   运行时长: {stats['client_stats']['uptime']}")
        print(f"   接收消息: {stats['client_stats']['messages_received']}")
        print(f"   发送消息: {stats['client_stats']['messages_sent']}")
        print(f"   接收字节: {stats['client_stats']['bytes_received']:,}")
        print(f"   发送字节: {stats['client_stats']['bytes_sent']:,}")
        
        # 压缩统计
        compression_stats = stats['compression_stats']
        print(f"\n🗜️ 压缩统计:")
        print(f"   压缩次数: {compression_stats['total_compressed']}")
        print(f"   压缩比: {compression_stats['compression_ratio']:.1f}%")
        print(f"   平均压缩时间: {compression_stats['avg_compression_time']*1000:.2f}ms")
        
        # 批处理统计
        batch_stats = stats['batch_processing_stats']
        print(f"\n📦 批处理统计:")
        print(f"   处理批次: {batch_stats['total_batches']}")
        print(f"   平均批次大小: {batch_stats['avg_batch_size']:.1f}")
        print(f"   处理时间: {batch_stats['processing_time']*1000:.2f}ms")
        
        # 内存统计
        memory_stats = stats['memory_stats']
        print(f"\n💾 内存统计:")
        print(f"   当前内存: {memory_stats['current_memory_mb']:.1f}MB")
        print(f"   峰值内存: {memory_stats['peak_memory_mb']:.1f}MB")
        print(f"   垃圾回收: {memory_stats['gc_collections']} 次")
        
        # 性能统计
        performance_stats = stats['performance_stats']
        print(f"\n⚡ 性能统计:")
        print(f"   平均CPU: {performance_stats['avg_cpu_percent']:.1f}%")
        print(f"   平均内存: {performance_stats['avg_memory_mb']:.1f}MB")
        print(f"   峰值消息速率: {performance_stats['peak_message_rate']:.1f}/s")
        print(f"   平均延迟: {performance_stats['avg_latency_ms']:.1f}ms")
        
    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
    finally:
        await client.stop()


async def demo_performance_comparison():
    """性能对比演示"""
    print("🎯 WebSocket 性能对比演示")
    
    # 创建两个客户端：优化版和普通版
    optimized_config = OptimizationConfig(
        enable_compression=True,
        batch_size=100,
        batch_timeout=0.1,
        memory_threshold_mb=256.0
    )
    
    basic_config = OptimizationConfig(
        enable_compression=False,
        batch_size=1,  # 不使用批处理
        batch_timeout=1.0,
        memory_threshold_mb=1024.0
    )
    
    optimized_client = OptimizedWebSocketClient(
        uri="ws://localhost:8765",
        config=optimized_config
    )
    
    basic_client = OptimizedWebSocketClient(
        uri="ws://localhost:8765", 
        config=basic_config
    )
    
    try:
        print("🚀 启动两个客户端进行性能对比...")
        
        # 启动客户端
        await optimized_client.start()
        await basic_client.start()
        
        # 订阅相同的数据
        symbols = ["000001.SZ", "600519.SH", "000002.SZ"]
        
        for symbol in symbols:
            await optimized_client.subscribe(symbol, "quote")
            await basic_client.subscribe(symbol, "quote")
        
        # 运行测试
        print("⏰ 运行90秒性能对比测试...")
        await asyncio.sleep(90)
        
        # 获取统计信息
        optimized_stats = optimized_client.get_optimization_stats()
        basic_stats = basic_client.get_optimization_stats()
        
        print(f"\n📊 性能对比结果:")
        print(f"{'指标':<20} {'优化版':<15} {'普通版':<15} {'提升':<10}")
        print("-" * 65)
        
        # 消息处理性能
        opt_msg_rate = optimized_stats['performance_stats']['peak_message_rate']
        basic_msg_rate = basic_stats['performance_stats']['peak_message_rate']
        msg_improvement = (opt_msg_rate / basic_msg_rate - 1) * 100 if basic_msg_rate > 0 else 0
        
        print(f"{'消息速率(/s)':<20} {opt_msg_rate:<15.1f} {basic_msg_rate:<15.1f} {msg_improvement:+.1f}%")
        
        # 内存使用
        opt_memory = optimized_stats['memory_stats']['peak_memory_mb']
        basic_memory = basic_stats['memory_stats']['peak_memory_mb']
        memory_improvement = (1 - opt_memory / basic_memory) * 100 if basic_memory > 0 else 0
        
        print(f"{'峰值内存(MB)':<20} {opt_memory:<15.1f} {basic_memory:<15.1f} {memory_improvement:+.1f}%")
        
        # CPU使用率
        opt_cpu = optimized_stats['performance_stats']['avg_cpu_percent']
        basic_cpu = basic_stats['performance_stats']['avg_cpu_percent']
        cpu_improvement = (1 - opt_cpu / basic_cpu) * 100 if basic_cpu > 0 else 0
        
        print(f"{'平均CPU(%)':<20} {opt_cpu:<15.1f} {basic_cpu:<15.1f} {cpu_improvement:+.1f}%")
        
        # 网络使用
        opt_bytes = optimized_stats['client_stats']['bytes_received']
        basic_bytes = basic_stats['client_stats']['bytes_received']
        bytes_improvement = (1 - opt_bytes / basic_bytes) * 100 if basic_bytes > 0 else 0
        
        print(f"{'网络接收(字节)':<20} {opt_bytes:<15,} {basic_bytes:<15,} {bytes_improvement:+.1f}%")
        
        # 延迟
        opt_latency = optimized_stats['performance_stats']['avg_latency_ms']
        basic_latency = basic_stats['performance_stats']['avg_latency_ms']
        latency_improvement = (1 - opt_latency / basic_latency) * 100 if basic_latency > 0 else 0
        
        print(f"{'平均延迟(ms)':<20} {opt_latency:<15.1f} {basic_latency:<15.1f} {latency_improvement:+.1f}%")
        
        # 压缩效果
        compression_stats = optimized_stats['compression_stats']
        if compression_stats['total_compressed'] > 0:
            print(f"\n🗜️ 压缩效果:")
            print(f"   压缩比: {compression_stats['compression_ratio']:.1f}%")
            print(f"   节省带宽: {compression_stats['total_original_size'] - compression_stats['total_compressed_size']:,} 字节")
        
        # 绘制性能图表
        print(f"\n📈 生成性能对比图表...")
        try:
            optimized_client.plot_performance_metrics(minutes=30)
        except Exception as e:
            print(f"绘制图表失败: {e}")
        
    except Exception as e:
        print(f"❌ 性能对比演示出错: {e}")
    finally:
        await optimized_client.stop()
        await basic_client.stop()


async def main():
    """主函数"""
    print("🎓 WebSocket 性能优化和最佳实践教程")
    print("本教程展示如何优化 WebSocket 实时数据系统的性能")
    
    # 检查WebSocket服务连接
    try:
        test_websocket = await websockets.connect("ws://localhost:8765", ping_timeout=5)
        await test_websocket.close()
        print("✅ WebSocket 服务连接正常")
    except Exception as e:
        print("❌ 无法连接到 WebSocket 服务器")
        print("请确保服务器已启动：python -m src.argus_mcp.websocket_server")
        return
    
    # 设置高性能事件循环（如果可用）
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("✅ 使用 uvloop 高性能事件循环")
    except ImportError:
        print("ℹ️ 未安装 uvloop，使用默认事件循环")
    
    try:
        # 运行基本优化演示
        await demo_basic_optimization()
        
        print("\n" + "="*60)
        input("按 Enter 键继续性能对比演示...")
        
        # 运行性能对比演示
        await demo_performance_comparison()
        
    except KeyboardInterrupt:
        print("\n⏹️ 教程被用户中断")
    except Exception as e:
        print(f"❌ 教程运行出错: {e}")
    
    print("\n🎉 WebSocket 性能优化教程完成！")
    print("\n📚 优化要点总结：")
    print("1. 数据压缩 - 减少网络传输量")
    print("2. 批量处理 - 提高消息处理效率")
    print("3. 内存管理 - 控制内存使用和垃圾回收")
    print("4. 性能监控 - 实时监控系统性能指标")
    print("5. 连接优化 - 优化连接参数和心跳机制")
    print("6. 异步处理 - 充分利用异步IO优势")
    print("\n💡 最佳实践建议：")
    print("- 根据数据特点选择合适的压缩算法")
    print("- 合理设置批处理大小和超时时间")
    print("- 定期监控内存使用和性能指标")
    print("- 实现优雅的错误处理和重连机制")
    print("- 在生产环境中使用高性能事件循环")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 教程结束")
    except Exception as e:
        logger.error(f"教程运行失败: {e}")
        sys.exit(1)