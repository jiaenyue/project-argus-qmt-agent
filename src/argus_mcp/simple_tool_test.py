#!/usr/bin/env python3
"""
Simple test script to diagnose tool function issues
"""

import asyncio
import inspect
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus_mcp.tools import get_trading_dates_tool, TOOL_REGISTRY

async def _test_direct_call_async():
    """Test calling tool function directly"""
    print("Testing direct call to get_trading_dates_tool...")
    try:
        print(f"Function type: {type(get_trading_dates_tool)}")
        print(f"Is coroutine function: {inspect.iscoroutinefunction(get_trading_dates_tool)}")
        
        # Try to call it
        from argus_mcp.models import GetTradingDatesInput
        input_data = GetTradingDatesInput(start_date="2024-01-01", end_date="2024-01-31")
        result = await get_trading_dates_tool(input_data)
        print(f"Direct call result: {result}")
    except Exception as e:
        print(f"Direct call failed: {e}")
        import traceback
        traceback.print_exc()
        raise

async def _test_registry_call_async():
    """Test calling tool function from registry"""
    print("\nTesting call from TOOL_REGISTRY...")
    try:
        tool_info = TOOL_REGISTRY.get("get_trading_dates")
        if tool_info:
            tool_func = tool_info["function"]
            print(f"Registry function type: {type(tool_func)}")
            print(f"Is coroutine function: {inspect.iscoroutinefunction(tool_func)}")
            
            # Try to call it
            from argus_mcp.models import GetTradingDatesInput
            input_data = GetTradingDatesInput(start_date="2024-01-01", end_date="2024-01-31")
            result = await tool_func(input_data)
            print(f"Registry call result: {result}")
        else:
            print("Tool not found in registry")
    except Exception as e:
        print(f"Registry call failed: {e}")
        import traceback
        traceback.print_exc()
        raise

async def _run_simple_tool_tests():
    print("=== Simple Tool Function Test ===")
    await _test_direct_call_async()
    await _test_registry_call_async()
    print("\n=== Test Complete ===")

# Pytest entry - sync wrapper

def test_simple_tool_calls():
    """Run async tool tests via asyncio.run so pytest can execute them."""
    asyncio.run(_run_simple_tool_tests())

# CLI entry
if __name__ == "__main__":
    asyncio.run(_run_simple_tool_tests())