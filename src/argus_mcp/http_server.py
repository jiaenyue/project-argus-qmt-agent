"""HTTP MCP Server implementation for testing.

This module provides a simple HTTP server that implements the MCP protocol
for testing purposes.
"""

import asyncio
import json
import logging
from aiohttp import web, WSMsgType
from typing import Dict, Any

from .server import ArgusMCPServer

logger = logging.getLogger(__name__)

class MCPHTTPServer:
    """HTTP server that implements MCP protocol."""
    
    def __init__(self, host: str = "localhost", port: int = 3000):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.mcp_server = ArgusMCPServer()
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_post('/mcp', self.handle_mcp_request)
        self.app.router.add_get('/ws', self.handle_websocket)
        
    async def handle_mcp_request(self, request):
        """Handle MCP HTTP requests."""
        try:
            data = await request.json()
            response = await self.process_mcp_request(data)
            return web.json_response(response)
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }, status=500)
    
    async def handle_websocket(self, request):
        """Handle WebSocket connections."""
        logger.info("WebSocket connection attempt")
        
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        logger.info("WebSocket connection established")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        logger.info(f"Received WebSocket message: {msg.data}")
                        data = json.loads(msg.data)
                        response = await self.process_mcp_request(data)
                        logger.info(f"Sending WebSocket response: {response}")
                        await ws.send_str(json.dumps(response))
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": data.get("id") if 'data' in locals() else None,
                            "error": {
                                "code": -32603,
                                "message": "Internal error",
                                "data": str(e)
                            }
                        }
                        await ws.send_str(json.dumps(error_response))
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
                elif msg.type == WSMsgType.CLOSE:
                    logger.info("WebSocket connection closed by client")
                    break
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            logger.info("WebSocket connection closed")
        
        return ws
    
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
        """Start the HTTP server."""
        # Start the MCP server components
        await self.mcp_server.connection_manager.start()
        await self.mcp_server.cache_manager.start()
        
        # Start HTTP server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"MCP HTTP Server started on http://{self.host}:{self.port}")
        logger.info(f"WebSocket endpoint: ws://{self.host}:{self.port}/ws")
        
        return runner
    
    async def stop(self, runner):
        """Stop the HTTP server."""
        await runner.cleanup()
        await self.mcp_server.shutdown()


async def main():
    """Main entry point for HTTP MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP HTTP Server")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=3000, help="Server port")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    
    server = MCPHTTPServer(host=args.host, port=args.port)
    
    try:
        runner = await server.start()
        
        # Keep server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server failed: {e}")
    finally:
        if 'runner' in locals():
            await server.stop(runner)


if __name__ == "__main__":
    asyncio.run(main())