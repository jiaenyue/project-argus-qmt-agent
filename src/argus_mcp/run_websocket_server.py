#!/usr/bin/env python3
"""
WebSocket实时数据服务器启动脚本
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from argus_mcp.websocket_server import WebSocketServer
from argus_mcp.config import Config


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/websocket_server.log')
    ]
)

logger = logging.getLogger(__name__)


class WebSocketServerApp:
    """WebSocket服务器应用类"""
    
    def __init__(self):
        self.server = None
        self.should_stop = False
        
    async def start_server(self, config_path: str = None):
        """启动服务器"""
        try:
            # 加载配置
            if config_path and Path(config_path).exists():
                logger.info(f"Loading config from {config_path}")
                config = Config.load_from_file(config_path)
            else:
                logger.info("Using default configuration")
                config = Config()
            
            # 创建服务器
            self.server = WebSocketServer(config)
            
            # 启动服务器
            logger.info(f"Starting WebSocket server on {config.server.host}:{config.server.port}")
            await self.server.start()
            
            logger.info("WebSocket server started successfully")
            
            # 等待停止信号
            while not self.should_stop:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
    
    async def stop_server(self):
        """停止服务器"""
        if self.server and self.server.is_running:
            logger.info("Stopping WebSocket server...")
            await self.server.stop()
            logger.info("WebSocket server stopped")
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.should_stop = True


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="WebSocket实时数据服务器")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/websocket_config.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--host", 
        type=str, 
        help="服务器主机地址"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        help="服务器端口号"
    )
    parser.add_argument(
        "--log-level", 
        type=str, 
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # 创建日志目录
    Path("logs").mkdir(exist_ok=True)
    
    app = WebSocketServerApp()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, app.signal_handler)
    signal.signal(signal.SIGTERM, app.signal_handler)
    
    try:
        await app.start_server(args.config)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        await app.stop_server()


if __name__ == "__main__":
    asyncio.run(main())