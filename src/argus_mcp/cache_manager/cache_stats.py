"""Cache Statistics Module.

This module defines the cache statistics data structure and related functionality.
"""

from dataclasses import dataclass


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    expired: int = 0
    evictions: int = 0
    memory_usage: int = 0
    entry_count: int = 0
    hit_rate: float = 0.0
    
    def __getitem__(self, key: str) -> int:
        """Allow dict-like access to stats."""
        return getattr(self, key, 0)
    
    def __setitem__(self, key: str, value: int):
        """Allow dict-like assignment to stats."""
        if hasattr(self, key):
            setattr(self, key, value)
    
    def get(self, key: str, default=0):
        """Get stat value with default."""
        return getattr(self, key, default)
    
    def keys(self):
        """Return available stat keys."""
        return ['hits', 'misses', 'expired', 'evictions', 'memory_usage', 'entry_count', 'hit_rate']
    
    def items(self):
        """Return stat items."""
        return [(key, getattr(self, key)) for key in self.keys()]
    
    def values(self):
        """Return stat values."""
        return [getattr(self, key) for key in self.keys()]
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in stats."""
        return hasattr(self, key)
    
    def calculate_hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0