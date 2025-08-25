#!/usr/bin/env python3
"""Start HTTP MCP Server for testing.

This script starts the HTTP MCP server for testing purposes.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from argus_mcp.http_server import MCPHTTPServer

# 导入统一配置
try:
    from config.app_config import app_config
    DEFAULT_HOST = app_config.MCP_SERVICE_HOST
    DEFAULT_PORT = app_config.MCP_SERVICE_PORT
except ImportError:
    # 如果配置文件不存在，使用默认值
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8001

async def main():
    """Main entry point."""
    print("Starting HTTP MCP Server for testing...")
    print(f"Host: {DEFAULT_HOST}")
    print(f"Port: {DEFAULT_PORT}")
    
    # Create and start server
    server = MCPHTTPServer(host=DEFAULT_HOST, port=DEFAULT_PORT)
    runner = await server.start()
    
    try:
        # Keep server running
        print("Server is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())