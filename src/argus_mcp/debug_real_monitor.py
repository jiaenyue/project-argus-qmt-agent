#!/usr/bin/env python3
"""
Debug real monitor_performance decorator
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus_mcp.models import GetTradingDatesInput

# Import the real decorator
from argus_mcp.performance_monitor import monitor_performance

# Test original async function
async def original_function(input_data: GetTradingDatesInput):
    """Original async function for testing"""
    return {"success": True, "data": [], "message": "Test"}

print("=== Before decoration ===")
print(f"Original function: {original_function}")
print(f"Is coroutine function: {asyncio.iscoroutinefunction(original_function)}")

# Apply decorator manually to see what happens
print("\n=== Applying decorator ===")
decorator_func = monitor_performance()
print(f"Decorator function: {decorator_func}")

decorated_function = decorator_func(original_function)
print(f"Decorated function: {decorated_function}")
print(f"Is coroutine function: {asyncio.iscoroutinefunction(decorated_function)}")

# Also test with @ syntax
print("\n=== Testing @ syntax ===")

@monitor_performance()
async def at_syntax_function(input_data: GetTradingDatesInput):
    """Function decorated with @ syntax"""
    return {"success": True, "data": [], "message": "At syntax"}

print(f"At syntax function: {at_syntax_function}")
print(f"Is coroutine function: {asyncio.iscoroutinefunction(at_syntax_function)}")

async def main():
    input_data = GetTradingDatesInput(market="SH", count=10)
    
    print("\n=== Testing manually decorated function ===")
    try:
        result = await decorated_function(input_data)
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Testing @ syntax function ===")
    try:
        result = await at_syntax_function(input_data)
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())