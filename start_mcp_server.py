#!/usr/bin/env python3
"""Argus MCP Server - Quick start script.

This script provides a simple way to start the Argus MCP server
with default or custom configurations.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from argus_mcp.main import main

# 导入统一配置
try:
    from config.app_config import app_config
    DEFAULT_DATA_SERVICE_URL = f"http://{app_config.DATA_AGENT_SERVICE_HOST}:{app_config.DATA_AGENT_SERVICE_PORT}"
    DEFAULT_MCP_HOST = app_config.MCP_SERVICE_HOST
    DEFAULT_MCP_PORT = str(app_config.MCP_SERVICE_PORT)
except ImportError:
    # 如果配置文件不存在，使用默认值
    DEFAULT_DATA_SERVICE_URL = "http://localhost:8002"
    DEFAULT_MCP_HOST = "localhost"
    DEFAULT_MCP_PORT = "8001"

if __name__ == "__main__":
    # Set default environment variables if not already set
    os.environ.setdefault("ARGUS_MCP_HOST", DEFAULT_MCP_HOST)
    os.environ.setdefault("ARGUS_MCP_PORT", DEFAULT_MCP_PORT)
    os.environ.setdefault("ARGUS_DATA_SERVICE_URL", DEFAULT_DATA_SERVICE_URL)
    os.environ.setdefault("ARGUS_LOG_LEVEL", "INFO")
    
    print("Starting Argus MCP Server...")
    print(f"Host: {os.environ.get('ARGUS_MCP_HOST')}")
    print(f"Port: {os.environ.get('ARGUS_MCP_PORT')}")
    print(f"Data Service URL: {os.environ.get('ARGUS_DATA_SERVICE_URL')}")
    
    # Start the MCP server
    main()