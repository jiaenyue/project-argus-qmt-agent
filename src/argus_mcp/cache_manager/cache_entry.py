"""Cache Entry Module.

This module defines the cache entry data structure and related functionality.
"""

import json
import time
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: Optional[int] = None
    size: int = 0
    priority: int = 5
    
    def __post_init__(self):
        """Calculate entry size after initialization."""
        self.size = self._calculate_size()
    
    def _calculate_size(self) -> int:
        """Calculate approximate size of the cache entry."""
        try:
            # Rough estimation of memory usage
            if isinstance(self.value, (str, bytes)):
                return len(self.value)
            elif isinstance(self.value, (list, tuple)):
                return sum(len(str(item)) for item in self.value)
            elif isinstance(self.value, dict):
                return len(json.dumps(self.value, default=str))
            else:
                return len(str(self.value))
        except Exception:
            return 1024  # Default size if calculation fails
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        """Update access metadata."""
        self.last_accessed = time.time()
        self.access_count += 1