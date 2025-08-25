#!/usr/bin/env python3
"""Argus MCP Server - Main entry point.

This script starts the Argus MCP server with proper configuration,
logging, and error handling.
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from .config import ServerConfig, config
from .server import ArgusMCPServer
from .performance_monitor import performance_monitor
from .tools import cleanup_tools


def setup_logging(config: ServerConfig) -> None:
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format=config.log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            *([logging.FileHandler(config.log_file)] if config.log_file else [])
        ]
    )
    
    # 设置第三方库的日志级别
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Argus MCP Server - Financial Data Access via Model Context Protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  ARGUS_MCP_HOST              Server host (default: localhost)
  ARGUS_MCP_PORT              Server port (default: 8001)
  ARGUS_DATA_SERVICE_URL      Data service URL (default: http://localhost:8000)
  ARGUS_CACHE_ENABLED         Enable caching (default: true)
  ARGUS_LOG_LEVEL             Log level (default: INFO)
  ARGUS_LOG_FILE              Log file path (optional)

Examples:
  python -m argus_mcp.main
  python -m argus_mcp.main --host 0.0.0.0 --port 8001
  python -m argus_mcp.main --config config.json
        """
    )
    
    parser.add_argument(
        "--host",
        type=str,
        help="Server host address (default: from config)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        help="Server port number (default: from config)"
    )
    
    parser.add_argument(
        "--data-service-url",
        type=str,
        help="Data service URL (default: from config)"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path (JSON format)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: from config)"
    )
    
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log file path (default: stdout only)"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching"
    )
    
    parser.add_argument(
        "--no-performance-monitoring",
        action="store_true",
        help="Disable performance monitoring"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Argus MCP Server 1.0.0"
    )
    
    return parser.parse_args()


def load_config_from_file(config_path: Path) -> ServerConfig:
    """从文件加载配置"""
    import json
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 创建配置实例并更新值
        server_config = ServerConfig.from_env()
        
        # 更新服务器配置
        if "server" in config_data:
            server_data = config_data["server"]
            server_config.host = server_data.get("host", server_config.host)
            server_config.port = server_data.get("port", server_config.port)
            server_config.max_connections = server_data.get("max_connections", server_config.max_connections)
        
        # 更新其他配置部分...
        if "data_service" in config_data:
            ds_data = config_data["data_service"]
            server_config.data_service_url = ds_data.get("url", server_config.data_service_url)
            server_config.data_service_timeout = ds_data.get("timeout", server_config.data_service_timeout)
        
        if "cache" in config_data:
            cache_data = config_data["cache"]
            server_config.cache_enabled = cache_data.get("enabled", server_config.cache_enabled)
            server_config.cache_size = cache_data.get("size", server_config.cache_size)
            server_config.cache_ttl = cache_data.get("ttl", server_config.cache_ttl)
            server_config.cache_policy = cache_data.get("policy", server_config.cache_policy)
        
        if "logging" in config_data:
            log_data = config_data["logging"]
            server_config.log_level = log_data.get("level", server_config.log_level)
            server_config.log_format = log_data.get("format", server_config.log_format)
            server_config.log_file = log_data.get("file", server_config.log_file)
        
        return server_config
        
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}", file=sys.stderr)
        sys.exit(1)


def apply_cli_overrides(server_config: ServerConfig, args: argparse.Namespace) -> ServerConfig:
    """应用命令行参数覆盖"""
    if args.host:
        server_config.host = args.host
    
    if args.port:
        server_config.port = args.port
    
    if args.data_service_url:
        server_config.data_service_url = args.data_service_url
    
    if args.log_level:
        server_config.log_level = args.log_level
    
    if args.log_file:
        server_config.log_file = str(args.log_file)
    
    if args.no_cache:
        server_config.cache_enabled = False
    
    if args.no_performance_monitoring:
        server_config.performance_monitoring = False
    
    return server_config


async def shutdown_handler(server: ArgusMCPServer, logger: logging.Logger) -> None:
    """优雅关闭处理器"""
    logger.info("Shutting down Argus MCP Server...")
    
    try:
        # 关闭服务器
        await server.shutdown()
        
        # 清理工具资源
        await cleanup_tools()
        
        # 停止性能监控
        if performance_monitor:
            await performance_monitor.stop()
        
        logger.info("Server shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        raise


async def main_async() -> None:
    """异步主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 加载配置
    if args.config:
        server_config = load_config_from_file(args.config)
    else:
        server_config = ServerConfig.from_env()
    
    # 应用命令行覆盖
    server_config = apply_cli_overrides(server_config, args)
    
    # 验证配置
    try:
        server_config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 设置日志
    setup_logging(server_config)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Argus MCP Server...")
    logger.info(f"Server configuration: {server_config.host}:{server_config.port}")
    logger.info(f"Data service URL: {server_config.data_service_url}")
    logger.info(f"Cache enabled: {server_config.cache_enabled}")
    logger.info(f"Performance monitoring: {server_config.performance_monitoring}")
    
    # 创建服务器实例
    server = ArgusMCPServer(
        host=server_config.host,
        port=server_config.port,
        max_connections=server_config.max_connections,
        cache_size=server_config.cache_size,
        cache_ttl=server_config.cache_ttl
    )
    
    # 设置信号处理器
    shutdown_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动服务器
        server_task = asyncio.create_task(server.run())
        
        # 等待关闭信号
        await shutdown_event.wait()
        
        # 取消服务器任务
        server_task.cancel()
        
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        
        # 执行优雅关闭
        await shutdown_handler(server, logger)
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    
    logger.info("Argus MCP Server stopped")


def main() -> None:
    """主入口点"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nServer interrupted by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()