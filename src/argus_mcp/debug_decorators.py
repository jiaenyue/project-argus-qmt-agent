#!/usr/bin/env python3
"""
Debug script to test individual decorators
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus_mcp.decorators import with_cache, with_retry
from argus_mcp.performance_monitor import monitor_performance
from argus_mcp.models import GetTradingDatesInput

# Test original async function
async def original_async_function(input_data: GetTradingDatesInput):
    """Original async function for testing"""
    return {"success": True, "data": [], "message": "Test"}

# Test with individual decorators
@with_cache(ttl=3600)
async def test_cache_only(input_data: GetTradingDatesInput):
    return {"success": True, "data": [], "message": "Cache only"}

@with_retry(max_attempts=3)
async def test_retry_only(input_data: GetTradingDatesInput):
    return {"success": True, "data": [], "message": "Retry only"}

@monitor_performance
async def test_monitor_only(input_data: GetTradingDatesInput):
    return {"success": True, "data": [], "message": "Monitor only"}

# Test with combinations
@with_cache(ttl=3600)
@with_retry(max_attempts=3)
async def test_cache_retry(input_data: GetTradingDatesInput):
    return {"success": True, "data": [], "message": "Cache + Retry"}

@with_retry(max_attempts=3)
@monitor_performance
async def test_retry_monitor(input_data: GetTradingDatesInput):
    return {"success": True, "data": [], "message": "Retry + Monitor"}

@with_cache(ttl=3600)
@with_retry(max_attempts=3)
@monitor_performance
async def test_all_decorators(input_data: GetTradingDatesInput):
    return {"success": True, "data": [], "message": "All decorators"}

async def main():
    input_data = GetTradingDatesInput(market="SH", count=10)
    
    test_functions = [
        ("Original", original_async_function),
        ("Cache only", test_cache_only),
        ("Retry only", test_retry_only),
        ("Monitor only", test_monitor_only),
        ("Cache + Retry", test_cache_retry),
        ("Retry + Monitor", test_retry_monitor),
        ("All decorators", test_all_decorators)
    ]
    
    for name, func in test_functions:
        print(f"\n=== Testing {name} ===")
        print(f"Function type: {type(func)}")
        print(f"Is coroutine function: {asyncio.iscoroutinefunction(func)}")
        
        try:
            result = await func(input_data)
            print(f"Success: {result}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())