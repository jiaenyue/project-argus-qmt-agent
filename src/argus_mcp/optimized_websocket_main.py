"""
WebSocket 实时数据服务优化版主入口
集成性能优化、部署配置管理和生产环境支持
"""

import asyncio
import logging
import signal
import sys
import os
from typing import Optional
from pathlib import Path

from .websocket_server import WebSocketServer
from .websocket_models import DataSourceConfig, WebSocketConfig
from .performance_optimizer import PerformanceOptimizer, PerformanceConfig
from .deployment_config import DeploymentConfigManager, get_deployment_config
from .websocket_monitor import WebSocketMonitor, AlertConfig

logger = logging.getLogger(__name__)


class OptimizedWebSocketService:
    """优化的WebSocket服务"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.deployment_config = None
        self.websocket_server = None
        self.performance_optimizer = None
        self.monitor = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """初始化服务"""
        logger.info("初始化WebSocket服务...")
        
        # 加载部署配置
        config_manager = DeploymentConfigManager(self.config_path)
        self.deployment_config = config_manager.load_config()
        
        # 配置日志
        self._setup_logging()
        
        # 创建WebSocket配置
        websocket_config = WebSocketConfig(
            host=self.deployment_config.websocket.host,
            port=self.deployment_config.websocket.port,
            max_connections=self.deployment_config.websocket.max_connections,
            max_subscriptions_per_client=self.deployment_config.websocket.max_subscriptions_per_client,
            heartbeat_interval=self.deployment_config.websocket.heartbeat_interval,
            max_message_size=self.deployment_config.websocket.max_message_size,
            ping_interval=self.deployment_config.websocket.ping_interval,
            ping_timeout=self.deployment_config.websocket.ping_timeout,
            close_timeout=self.deployment_config.websocket.close_timeout,
            max_queue=self.deployment_config.websocket.max_queue
        )
        
        # 创建数据源配置
        data_source_config = DataSourceConfig(
            source_type="mock",  # 可以根据配置调整
            update_interval=1.0,
            batch_size=100
        )
        
        # 创建WebSocket服务器
        self.websocket_server = WebSocketServer(
            host=websocket_config.host,
            port=websocket_config.port,
            max_connections=websocket_config.max_connections,
            max_subscriptions_per_client=websocket_config.max_subscriptions_per_client,
            websocket_config=websocket_config,
            data_source_config=data_source_config
        )
        
        # 创建性能优化器
        perf_config = PerformanceConfig(
            memory_threshold_mb=400.0,
            cpu_threshold_percent=self.deployment_config.scaling.target_cpu_utilization,
            batch_size=100,
            batch_timeout=0.1,
            monitoring_interval=10.0
        )
        
        self.performance_optimizer = PerformanceOptimizer(perf_config)
        
        # 创建监控器
        alert_config = AlertConfig(
            max_connections=self.deployment_config.websocket.max_connections,
            max_latency_ms=100.0,
            max_error_rate=0.05,
            max_memory_mb=500.0,
            max_cpu_percent=self.deployment_config.scaling.target_cpu_utilization,
            monitoring_interval=self.deployment_config.scaling.evaluation_interval
        )
        
        self.monitor = WebSocketMonitor(alert_config)
        
        # 注册性能回调
        self.performance_optimizer.register_performance_callback(
            self._on_performance_metrics
        )
        
        # 注册告警回调
        self.monitor.register_alert_callback(self._on_alert)
        
        logger.info("WebSocket服务初始化完成")
    
    def _setup_logging(self):
        """设置日志配置"""
        log_config = self.deployment_config.logging
        
        # 设置日志级别
        log_level = getattr(logging, log_config.level.upper(), logging.INFO)
        
        # 创建日志格式器
        formatter = logging.Formatter(log_config.format)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加控制台处理器
        if log_config.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # 添加文件处理器
        if log_config.file_path:
            # 确保日志目录存在
            log_file = Path(log_config.file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_config.file_path,
                maxBytes=log_config.max_file_size,
                backupCount=log_config.backup_count
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        logger.info(f"日志配置完成: 级别={log_config.level}, 文件={log_config.file_path}")
    
    async def start(self):
        """启动服务"""
        logger.info("启动WebSocket服务...")
        
        try:
            # 启动性能优化器
            await self.performance_optimizer.start()
            logger.info("性能优化器已启动")
            
            # 启动监控器
            self.monitor.start_monitoring()
            logger.info("监控器已启动")
            
            # 启动WebSocket服务器
            server_task = asyncio.create_task(self.websocket_server.start())
            logger.info(f"WebSocket服务器已启动: {self.deployment_config.websocket.host}:{self.deployment_config.websocket.port}")
            
            # 等待关闭信号
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            raise
    
    async def stop(self):
        """停止服务"""
        logger.info("停止WebSocket服务...")
        
        try:
            # 停止WebSocket服务器
            if self.websocket_server:
                await self.websocket_server.stop()
                logger.info("WebSocket服务器已停止")
            
            # 停止监控器
            if self.monitor:
                self.monitor.stop_monitoring()
                logger.info("监控器已停止")
            
            # 停止性能优化器
            if self.performance_optimizer:
                await self.performance_optimizer.stop()
                logger.info("性能优化器已停止")
            
            # 设置关闭事件
            self.shutdown_event.set()
            
            logger.info("WebSocket服务已完全停止")
            
        except Exception as e:
            logger.error(f"停止服务时出错: {e}")
    
    async def _on_performance_metrics(self, metrics):
        """性能指标回调"""
        # 更新监控器
        if self.monitor:
            # 这里可以将性能指标传递给监控器
            pass
        
        # 记录性能指标
        if metrics.memory_usage_mb > 400:
            logger.warning(f"内存使用过高: {metrics.memory_usage_mb:.2f}MB")
        
        if metrics.cpu_usage_percent > 80:
            logger.warning(f"CPU使用率过高: {metrics.cpu_usage_percent:.2f}%")
    
    async def _on_alert(self, alert):
        """告警回调"""
        logger.warning(f"收到告警: {alert['level']} - {alert['message']}")
        
        # 这里可以实现告警通知逻辑
        # 例如发送到监控系统、邮件、短信等
        
        # 根据告警类型执行自动化响应
        if alert['level'] == 'critical':
            if 'memory' in alert['message'].lower():
                # 内存告警 - 触发垃圾回收
                if self.performance_optimizer:
                    self.performance_optimizer.memory_optimizer.force_gc()
                    logger.info("触发垃圾回收响应内存告警")
    
    def get_service_status(self) -> dict:
        """获取服务状态"""
        status = {
            "service": "websocket-server",
            "environment": self.deployment_config.environment.value if self.deployment_config else "unknown",
            "status": "running" if self.websocket_server and self.websocket_server.is_running else "stopped",
            "timestamp": asyncio.get_event_loop().time()
        }
        
        if self.websocket_server:
            server_stats = asyncio.create_task(self.websocket_server.get_server_stats())
            # 注意: 这里需要在异步上下文中调用
            
        if self.performance_optimizer:
            perf_summary = self.performance_optimizer.get_optimization_summary()
            status["performance"] = perf_summary
        
        if self.monitor:
            monitor_summary = self.monitor.get_metrics_summary()
            status["monitoring"] = monitor_summary
        
        return status


def setup_signal_handlers(service: OptimizedWebSocketService):
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，开始优雅关闭...")
        asyncio.create_task(service.stop())
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Unix系统支持更多信号
    if hasattr(signal, 'SIGHUP'):
        def reload_handler(signum, frame):
            logger.info("收到SIGHUP信号，重新加载配置...")
            # 这里可以实现配置重载逻辑
        
        signal.signal(signal.SIGHUP, reload_handler)


async def main():
    """主函数"""
    # 获取配置文件路径
    config_path = os.getenv('WEBSOCKET_CONFIG_PATH', 'config/deployment.yaml')
    
    # 根据环境选择配置文件
    environment = os.getenv('ENVIRONMENT', 'development')
    if environment == 'production':
        config_path = 'config/deployment-production.yaml'
    elif environment == 'development':
        config_path = 'config/deployment-development.yaml'
    
    # 创建服务实例
    service = OptimizedWebSocketService(config_path)
    
    try:
        # 初始化服务
        await service.initialize()
        
        # 设置信号处理器
        setup_signal_handlers(service)
        
        # 启动服务
        await service.start()
        
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    except Exception as e:
        logger.error(f"服务运行出错: {e}")
        sys.exit(1)
    finally:
        # 确保服务正确关闭
        await service.stop()


if __name__ == "__main__":
    # 设置基础日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行服务
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务已停止")
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        sys.exit(1)