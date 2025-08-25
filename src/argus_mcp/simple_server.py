#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple MCP Server for testing.

This module provides a simple server that implements the MCP protocol
using standard library components for testing purposes.
"""

import asyncio
import json
import logging
from typing import Dict, Any
import websockets
from websockets.server import serve

from .server import ArgusMCPServer
from .cache_manager import CacheManager
from .connection_manager import ConnectionPool
from .cache_preloader import PreloadScheduler
from .cache_monitor import cache_monitor
from .connection_optimizer import ConnectionPoolOptimizer, PoolConfiguration

logger = logging.getLogger(__name__)

class SimpleMCPServer:
    """Simple MCP server using websockets library."""
    
    def __init__(self, host: str = "localhost", port: int = 3000, config: Dict[str, Any] = None):
        self.host = host
        self.port = port
        self.config = config or {}
        self.mcp_server = ArgusMCPServer()
        
        # Initialize cache manager
        self.cache_manager = CacheManager(
            max_size=self.config.get("cache", {}).get("max_size", 10000),
            max_memory=self.config.get("cache", {}).get("max_memory", 100 * 1024 * 1024),
            default_ttl=self.config.get("cache", {}).get("default_ttl", 3600)
        )
        
        # Initialize connection pool
        self.connection_pool = ConnectionPool(
            max_connections=self.config.get("connection_pool", {}).get("max_connections", 20),
            max_idle_time=self.config.get("connection_pool", {}).get("max_idle_time", 300)
        )
        
        # Initialize cache preloader
        self.cache_preloader = PreloadScheduler(
            cache_manager=self.cache_manager,
            data_service_client=getattr(self.mcp_server, 'data_service_client', None),
            max_workers=self.config.get("cache", {}).get("preloader_workers", 4)
        )
        
        # Initialize connection optimizer
        pool_config = PoolConfiguration(
            min_connections=self.config.get("connection_pool", {}).get("min_connections", 2),
            max_connections=self.config.get("connection_pool", {}).get("max_connections", 20),
            target_utilization=self.config.get("connection_pool", {}).get("target_utilization", 0.7),
            health_check_interval=self.config.get("connection_pool", {}).get("health_check_interval", 30),
            connection_timeout=self.config.get("connection_pool", {}).get("timeout", 10)
        )
        self.connection_optimizer = ConnectionPoolOptimizer(
            connection_pool=self.connection_pool,
            config=pool_config
        )
        
        # Integrate components
        self.cache_manager.set_preloader(self.cache_preloader)
        
    async def handle_client(self, websocket, path):
        """Handle client connections."""
        logger.info(f"Client connected from {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    logger.info(f"Received message: {message}")
                    data = json.loads(message)
                    response = await self.process_mcp_request(data)
                    logger.info(f"Sending response: {response}")
                    await websocket.send(json.dumps(response))
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id") if 'data' in locals() else None,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        }
                    }
                    await websocket.send(json.dumps(error_response))
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Client handler error: {e}")
    
    async def process_mcp_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process MCP request and return response."""
        try:
            # Validate JSON-RPC format
            if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
                return {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request"
                    }
                }
            
            method = data.get("method")
            params = data.get("params", {})
            request_id = data.get("id")
            
            # Handle different MCP methods
            if method == "tools/list":
                tools = await self.mcp_server.handle_list_tools()
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": tools
                    }
                }
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if not tool_name:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": "Invalid params",
                            "data": "Missing tool name"
                        }
                    }
                
                result = await self.mcp_server.handle_call_tool(tool_name, arguments)
                
                # Check if result is an error
                if isinstance(result, dict) and "error" in result:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": "Tool execution failed",
                            "data": result["error"]
                        }
                    }
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }]
                    }
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": f"Unknown method: {method}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error processing MCP request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": data.get("id") if isinstance(data, dict) else None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
    
    async def start(self):
        """Start the WebSocket server."""
        # Start all components
        await self.cache_manager.start()
        await self.connection_pool.start()
        await cache_monitor.start()
        await self.cache_preloader.start()
        await self.connection_optimizer.start()
        
        # Start the MCP server components
        await self.mcp_server.connection_manager.start()
        await self.mcp_server.cache_manager.start()
        
        # Start WebSocket server
        logger.info(f"Starting MCP WebSocket server on ws://{self.host}:{self.port}")
        
        async with serve(self.handle_client, self.host, self.port):
            logger.info(f"MCP WebSocket Server started on ws://{self.host}:{self.port}")
            # Keep server running
            await asyncio.Future()  # run forever
    
    async def shutdown(self):
        """Shutdown the server."""
        # Stop all components
        await self.connection_optimizer.stop()
        await self.cache_preloader.stop()
        await cache_monitor.stop()
        await self.connection_pool.stop()
        await self.cache_manager.stop()
        
        await self.mcp_server.shutdown()


async def main():
    """Main entry point for simple MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple MCP WebSocket Server")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=3000, help="Server port")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    
    server = SimpleMCPServer(host=args.host, port=args.port)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server failed: {e}")
    finally:
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())