"""Cache Manager Module - Backward Compatibility Interface.

This module provides backward compatibility for the refactored cache manager.
All functionality has been moved to the cache_manager package.
"""

# Import all components from the new modular structure
from .cache_manager import (
    CacheStats,
    CachePolicy,
    CacheEntry,
    CacheManager,
    CacheDecorator
)

# Re-export for backward compatibility
__all__ = [
    "CacheStats",
    "CachePolicy",
    "CacheEntry", 
    "CacheManager",
    "CacheDecorator"
]