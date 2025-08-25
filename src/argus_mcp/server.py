"""Argus MCP Server - Main server implementation.

This module implements the core MCP server functionality,
including protocol handlers, tool registration, and error handling.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

from .models import (
    GetTradingDatesInput,
    GetStockListInput,
    GetInstrumentDetailInput,
    GetHistoryMarketDataInput,
    GetLatestMarketDataInput,
    GetFullMarketDataInput,
    ToolResponse,
)
from .tools import TOOL_REGISTRY, cleanup_tools
from .connection_manager import ConnectionManager
from .cache_manager import CacheManager
from .cache_optimizer import get_cache_optimizer
from .cache_warmup_service import get_warmup_service
from .data_service import DataService
from .utils import format_error_response, format_success_response, performance_monitor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArgusMCPServer:
    """Main MCP server class for Argus data services."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3000,
        max_connections: int = 10,
        cache_size: int = 1000,
        cache_ttl: int = 300,
        enable_cache_optimization: bool = True,
        enable_cache_warmup: bool = True
    ):
        """Initialize the MCP server."""
        self.host = host
        self.port = port
        self.server = None
        
        # Initialize managers
        self.connection_manager = ConnectionManager(max_connections=max_connections)
        self.cache_manager = CacheManager(
            max_size=cache_size,
            default_ttl=cache_ttl
        )
        
        # Initialize data service
        self.data_service = DataService()
        
        # Initialize cache optimization and warmup services
        self.cache_optimizer = None
        self.warmup_service = None
        self.enable_cache_optimization = enable_cache_optimization
        self.enable_cache_warmup = enable_cache_warmup
        
        # Tool registry
        self.tools = {}
        self._register_tools()
        
        # Server state
        self._running = False
    
    def _register_tools(self):
        """Register all available tools."""
        for tool_name, tool_info in TOOL_REGISTRY.items():
            self.tools[tool_name] = {
                "name": tool_name,
                "description": tool_info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": tool_info["parameters"],
                    "required": list(tool_info["parameters"].keys())
                }
            }
        logger.info(f"Registered {len(self.tools)} tools")
    
    @performance_monitor
    async def handle_list_tools(self) -> List[Dict[str, Any]]:
        """Handle list_tools request."""
        try:
            logger.info("Listing available tools")
            return list(self.tools.values())
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []
    
    @performance_monitor
    async def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle call_tool request."""
        try:
            if name not in self.tools:
                logger.warning(f"Unknown tool requested: {name}")
                return format_error_response(f"Unknown tool: {name}")
            
            # Check cache first
            cache_key = f"{name}:{hash(str(sorted(arguments.items())))}"
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for tool {name}")
                return format_success_response(cached_result)
            
            # Execute tool
            logger.info(f"Executing tool: {name} with arguments: {arguments}")
            result = await self._execute_tool(name, arguments)
            
            # Cache result
            await self.cache_manager.set(cache_key, result)
            
            return format_success_response(result)
            
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return format_error_response(f"Tool execution failed: {str(e)}")
    
    async def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments."""
        if name not in TOOL_REGISTRY:
            raise ValueError(f"Tool {name} not found in registry")
        
        tool_info = TOOL_REGISTRY[name]
        tool_func = tool_info["function"]
        input_model = tool_info["input_model"]
        
        # Validate and parse input using the tool's input model
        try:
            input_data = input_model(**arguments)
        except Exception as e:
            raise ValueError(f"Invalid input parameters for {name}: {str(e)}")
        
        # Execute tool function
        result = await tool_func(input_data)
        
        # Convert result to dict if it's a Pydantic model
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        return result
    
    async def run(self):
        """Run the MCP server."""
        try:
            logger.info(f"Starting Argus MCP Server on {self.host}:{self.port}")
            self._running = True
            
            # Start managers
            await self.connection_manager.start()
            await self.cache_manager.start()
            
            # Initialize and start cache optimization service
            if self.enable_cache_optimization:
                self.cache_optimizer = get_cache_optimizer(self.cache_manager)
                if self.cache_optimizer:
                    logger.info("Starting cache optimization service")
                    asyncio.create_task(self.cache_optimizer.start_optimization_loop())
            
            # Initialize and start cache warmup service
            if self.enable_cache_warmup:
                self.warmup_service = get_warmup_service(self.cache_manager, self.data_service)
                if self.warmup_service:
                    logger.info("Starting cache warmup service")
                    await self.warmup_service.start()
            
            # Keep server running
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the server and cleanup resources."""
        logger.info("Shutting down Argus MCP Server")
        self._running = False
        
        try:
            # Stop cache services
            if self.warmup_service:
                await self.warmup_service.stop()
            
            # Note: cache_optimizer doesn't have a stop method in the current implementation
            # It will stop when the optimization loop detects _running = False
            
            # Cleanup tools
            await cleanup_tools()
            
            # Cleanup managers
            if self.cache_manager:
                await self.cache_manager.stop()
            
            if self.connection_manager:
                await self.connection_manager.shutdown()
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information and statistics."""
        return {
            "name": "Argus MCP Server",
            "version": "1.0.0",
            "host": self.host,
            "port": self.port,
            "running": self._running,
            "tools_count": len(self.tools),
            "connection_stats": self.connection_manager.get_stats() if self.connection_manager else {},
            "cache_stats": self.cache_manager.get_stats() if self.cache_manager else {}
        }


async def main():
    """Main entry point for the Argus MCP Server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Argus MCP Server")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=3000, help="Server port")
    parser.add_argument("--max-connections", type=int, default=10, help="Maximum connections")
    parser.add_argument("--cache-size", type=int, default=1000, help="Cache size")
    parser.add_argument("--cache-ttl", type=int, default=300, help="Cache TTL in seconds")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    server = ArgusMCPServer(
        host=args.host,
        port=args.port,
        max_connections=args.max_connections,
        cache_size=args.cache_size,
        cache_ttl=args.cache_ttl
    )
    
    try:
        logger.info(f"Server info: {server.get_server_info()}")
        await server.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())