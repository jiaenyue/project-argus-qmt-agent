#!/usr/bin/env python3
"""
Test monitor_performance decorator in isolation
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus_mcp.performance_monitor import monitor_performance
from argus_mcp.models import GetTradingDatesInput

# Test original async function
async def original_function(input_data: GetTradingDatesInput):
    """Original async function for testing"""
    return {"success": True, "data": [], "message": "Test"}

# Test with monitor_performance decorator
@monitor_performance
async def decorated_function(input_data: GetTradingDatesInput):
    """Decorated async function for testing"""
    return {"success": True, "data": [], "message": "Decorated"}

async def main():
    input_data = GetTradingDatesInput(market="SH", count=10)
    
    print("=== Testing Original Function ===")
    print(f"Function type: {type(original_function)}")
    print(f"Is coroutine function: {asyncio.iscoroutinefunction(original_function)}")
    
    try:
        result = await original_function(input_data)
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Testing Decorated Function ===")
    print(f"Function type: {type(decorated_function)}")
    print(f"Is coroutine function: {asyncio.iscoroutinefunction(decorated_function)}")
    
    try:
        result = await decorated_function(input_data)
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())