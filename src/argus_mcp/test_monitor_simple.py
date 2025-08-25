#!/usr/bin/env python3
"""
Simple test for monitor_performance decorator
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .performance_monitor import monitor_performance

@monitor_performance()
async def _async_func():
    """Async function under test"""
    await asyncio.sleep(0.1)
    return "async result"

@monitor_performance()
def _sync_func():
    """Sync function under test"""
    return "sync result"

async def _run_async_checks():
    # Validate decorated async function
    assert asyncio.iscoroutinefunction(_async_func)
    result = await _async_func()
    assert result == "async result"

# Pytest entries

def test_async_function():
    # Run async function via asyncio.run so pytest can execute it
    asyncio.run(_run_async_checks())

def test_sync_function():
    # Validate decorated sync function
    assert not asyncio.iscoroutinefunction(_sync_func)
    result = _sync_func()
    assert result == "sync result"

# CLI entry remains for manual run
if __name__ == "__main__":
    asyncio.run(_run_async_checks())
    print("All checks passed")