#!/usr/bin/env python3
"""
Debug decorator flow to understand what's happening
"""

import asyncio
import sys
import os
from functools import wraps
import time
from typing import Callable, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus_mcp.models import GetTradingDatesInput

# Simple test decorator that mimics monitor_performance structure
def test_monitor_performance(operation_name: Optional[str] = None):
    """Test decorator for monitoring function performance."""
    print(f"Creating decorator with operation_name: {operation_name}")
    
    def decorator(func: Callable) -> Callable:
        print(f"Decorator called with func: {func}")
        print(f"Is coroutine function: {asyncio.iscoroutinefunction(func)}")
        
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        print(f"Operation name: {op_name}")
        
        if asyncio.iscoroutinefunction(func):
            print("Creating async wrapper")
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                print(f"Async wrapper called with args: {len(args)}, kwargs: {len(kwargs)}")
                start_time = time.time()
                success = True
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start_time
                    print(f"Operation {op_name} took {duration:.4f}s, success: {success}")
            
            print(f"Returning async_wrapper: {async_wrapper}")
            print(f"async_wrapper is coroutine function: {asyncio.iscoroutinefunction(async_wrapper)}")
            return async_wrapper
        else:
            print("Creating sync wrapper")
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                print(f"Sync wrapper called with args: {len(args)}, kwargs: {len(kwargs)}")
                start_time = time.time()
                success = True
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start_time
                    print(f"Operation {op_name} took {duration:.4f}s, success: {success}")
            
            print(f"Returning sync_wrapper: {sync_wrapper}")
            return sync_wrapper
    
    print(f"Returning decorator: {decorator}")
    return decorator

# Test with our test decorator
print("=== Creating decorated function ===")

@test_monitor_performance()
async def test_function(input_data: GetTradingDatesInput):
    """Test async function"""
    return {"success": True, "data": [], "message": "Test"}

print(f"\n=== Final function info ===")
print(f"Function: {test_function}")
print(f"Function type: {type(test_function)}")
print(f"Is coroutine function: {asyncio.iscoroutinefunction(test_function)}")

async def main():
    input_data = GetTradingDatesInput(market="SH", count=10)
    
    print("\n=== Testing function call ===")
    try:
        result = await test_function(input_data)
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())