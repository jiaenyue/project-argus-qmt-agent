#!/usr/bin/env python3
"""
Test decorator chain behavior
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus_mcp.decorators import with_cache, with_retry
from argus_mcp.performance_monitor import monitor_performance

# Test original async function
async def original_async_function():
    """Original async function"""
    await asyncio.sleep(0.1)
    return "original result"

# Test with single decorators
@with_retry(max_attempts=3)
async def retry_decorated_function():
    """Function with retry decorator"""
    await asyncio.sleep(0.1)
    return "retry result"

@with_cache(ttl=300)
async def cache_decorated_function():
    """Function with cache decorator"""
    await asyncio.sleep(0.1)
    return "cache result"

@monitor_performance()
async def monitor_decorated_function():
    """Function with monitor decorator"""
    await asyncio.sleep(0.1)
    return "monitor result"

# Test with decorator chain
@with_cache(ttl=300)
@with_retry(max_attempts=3)
async def cache_retry_function():
    """Function with cache and retry decorators"""
    await asyncio.sleep(0.1)
    return "cache retry result"

@with_retry(max_attempts=3)
@monitor_performance()
async def retry_monitor_function():
    """Function with retry and monitor decorators"""
    await asyncio.sleep(0.1)
    return "retry monitor result"

@with_cache(ttl=300)
@with_retry(max_attempts=3)
@monitor_performance()
async def full_chain_function():
    """Function with full decorator chain"""
    await asyncio.sleep(0.1)
    return "full chain result"

async def main():
    print("=== Decorator Chain Test ===")
    
    functions = [
        ("original_async_function", original_async_function),
        ("retry_decorated_function", retry_decorated_function),
        ("cache_decorated_function", cache_decorated_function),
        ("monitor_decorated_function", monitor_decorated_function),
        ("cache_retry_function", cache_retry_function),
        ("retry_monitor_function", retry_monitor_function),
        ("full_chain_function", full_chain_function),
    ]
    
    for name, func in functions:
        print(f"\n{name}:")
        print(f"  Type: {type(func)}")
        print(f"  Is coroutine function: {asyncio.iscoroutinefunction(func)}")
        
        try:
            result = await func()
            print(f"  Result: {result}")
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())