"""
Access pattern analysis for intelligent cache preloading.

This module provides sophisticated access pattern tracking and analysis
to predict future cache access patterns and optimize preloading strategies.
"""

import time
import math
from dataclasses import dataclass, field
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class AccessPattern:
    """Tracks access patterns for intelligent cache preloading."""
    
    key: str
    access_times: List[float] = field(default_factory=list)
    access_count: int = 0
    last_access: float = 0
    average_interval: float = 0
    access_velocity: float = 0  # accesses per minute
    trend_score: float = 0  # positive = increasing frequency
    seasonality_score: float = 0  # 0-1, higher = more predictable
    prediction_confidence: float = 0  # 0-1, confidence in next access prediction
    next_predicted_access: float = 0
    
    def add_access(self, timestamp: float):
        """Add a new access record and update metrics."""
        self.access_times.append(timestamp)
        self.access_count += 1
        self.last_access = timestamp
        
        # Keep only recent access times (last 100 accesses or 24 hours)
        cutoff_time = timestamp - 86400  # 24 hours
        self.access_times = [
            t for t in self.access_times[-100:] 
            if t > cutoff_time
        ]
        
        self._update_metrics()
    
    def _update_metrics(self):
        """Update all access pattern metrics."""
        if len(self.access_times) < 2:
            return
        
        self._calculate_intervals()
        self._calculate_velocity()
        self._calculate_trend()
        self._calculate_seasonality()
        self._predict_next_access()
    
    def _calculate_intervals(self):
        """Calculate average interval between accesses."""
        if len(self.access_times) < 2:
            return
        
        intervals = [
            self.access_times[i] - self.access_times[i-1]
            for i in range(1, len(self.access_times))
        ]
        
        self.average_interval = sum(intervals) / len(intervals)
    
    def _calculate_velocity(self):
        """Calculate access velocity (accesses per minute)."""
        if len(self.access_times) < 2:
            self.access_velocity = 0
            return
        
        time_span = self.access_times[-1] - self.access_times[0]
        if time_span > 0:
            self.access_velocity = (len(self.access_times) - 1) / (time_span / 60)
        else:
            self.access_velocity = 0
    
    def _calculate_trend(self):
        """Calculate trend score indicating if access frequency is increasing."""
        if len(self.access_times) < 4:
            self.trend_score = 0
            return
        
        # Split into two halves and compare velocities
        mid_point = len(self.access_times) // 2
        first_half = self.access_times[:mid_point]
        second_half = self.access_times[mid_point:]
        
        # Calculate velocity for each half
        first_velocity = self._calculate_velocity_for_period(first_half)
        second_velocity = self._calculate_velocity_for_period(second_half)
        
        if first_velocity > 0:
            self.trend_score = (second_velocity - first_velocity) / first_velocity
        else:
            self.trend_score = 1 if second_velocity > 0 else 0
        
        # Normalize to [-1, 1]
        self.trend_score = max(-1, min(1, self.trend_score))
    
    def _calculate_velocity_for_period(self, access_times: List[float]) -> float:
        """Calculate velocity for a specific time period."""
        if len(access_times) < 2:
            return 0
        
        time_span = access_times[-1] - access_times[0]
        if time_span > 0:
            return (len(access_times) - 1) / (time_span / 60)
        return 0
    
    def _calculate_seasonality(self):
        """Calculate seasonality score based on access pattern regularity."""
        if len(self.access_times) < 5:
            self.seasonality_score = 0
            return
        
        intervals = [
            self.access_times[i] - self.access_times[i-1]
            for i in range(1, len(self.access_times))
        ]
        
        if not intervals:
            self.seasonality_score = 0
            return
        
        # Calculate coefficient of variation (lower = more regular)
        mean_interval = sum(intervals) / len(intervals)
        if mean_interval == 0:
            self.seasonality_score = 0
            return
        
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_interval
        
        # Convert to seasonality score (0-1, higher = more regular)
        self.seasonality_score = max(0, 1 - min(cv, 2) / 2)
    
    def _predict_next_access(self):
        """Predict the next access time and confidence."""
        if len(self.access_times) < 2:
            self.next_predicted_access = self.last_access + 3600  # Default 1 hour
            self.prediction_confidence = 0.1
            return
        
        # Base prediction on average interval
        base_prediction = self.last_access + self.average_interval
        
        # Adjust based on trend
        if self.trend_score > 0:
            # Increasing frequency, predict sooner
            adjustment = self.average_interval * self.trend_score * 0.3
            base_prediction -= adjustment
        elif self.trend_score < 0:
            # Decreasing frequency, predict later
            adjustment = self.average_interval * abs(self.trend_score) * 0.3
            base_prediction += adjustment
        
        self.next_predicted_access = base_prediction
        
        # Calculate confidence based on seasonality and access count
        base_confidence = min(self.access_count / 10, 1.0)  # More accesses = higher confidence
        seasonality_boost = self.seasonality_score * 0.5
        
        self.prediction_confidence = min(base_confidence + seasonality_boost, 1.0)
    
    def should_preload(self, current_time: float, threshold: float = 0.6) -> bool:
        """Determine if this pattern suggests preloading is beneficial."""
        if self.access_count < 3:
            return False
        
        # Check if predicted access is soon
        time_to_predicted = self.next_predicted_access - current_time
        
        # Preload if:
        # 1. Predicted access is within next 5 minutes
        # 2. High confidence and good velocity
        # 3. Strong trend indicating increasing usage
        
        soon_access = 0 < time_to_predicted <= 300  # Next 5 minutes
        high_confidence = self.prediction_confidence >= threshold
        good_velocity = self.access_velocity >= 0.5  # At least 0.5 accesses per minute
        strong_trend = self.trend_score >= 0.3
        
        return (soon_access and high_confidence) or (good_velocity and strong_trend)
    
    def get_priority_score(self) -> float:
        """Calculate priority score for preloading (0-1, higher = more important)."""
        # Combine multiple factors
        velocity_factor = min(self.access_velocity / 2.0, 1.0)  # Normalize to max 2/min
        trend_factor = max(0, self.trend_score)  # Only positive trends
        seasonality_factor = self.seasonality_score
        confidence_factor = self.prediction_confidence
        
        # Weighted combination
        priority = (
            velocity_factor * 0.3 +
            trend_factor * 0.25 +
            seasonality_factor * 0.25 +
            confidence_factor * 0.2
        )
        
        return min(priority, 1.0)


class AccessPatternAnalyzer:
    """Analyzes access patterns across multiple cache keys."""
    
    def __init__(self):
        self.patterns = {}
        self.data_type_patterns = {}
        self.popular_keys = set()
        
        # Analysis configuration
        self.min_accesses_for_analysis = 3
        self.popularity_threshold = 5
        self.pattern_cleanup_interval = 100  # Clean up every N accesses
        self.pattern_retention_hours = 2
        
        self._access_counter = 0
    
    def record_access(self, key: str, data_type: str, timestamp: Optional[float] = None):
        """Record a cache access for pattern analysis."""
        if timestamp is None:
            timestamp = time.time()
        
        self._access_counter += 1
        
        # Update key-specific pattern
        if key not in self.patterns:
            self.patterns[key] = AccessPattern(key=key)
        
        self.patterns[key].add_access(timestamp)
        
        # Update data type pattern
        if data_type not in self.data_type_patterns:
            self.data_type_patterns[data_type] = AccessPattern(key=f"type:{data_type}")
        
        self.data_type_patterns[data_type].add_access(timestamp)
        
        # Update popular keys
        if self.patterns[key].access_count >= self.popularity_threshold:
            self.popular_keys.add(key)
        
        # Periodic cleanup
        if self._access_counter % self.pattern_cleanup_interval == 0:
            self._cleanup_old_patterns(timestamp)
    
    def get_preload_candidates(self, current_time: Optional[float] = None) -> List[tuple]:
        """Get list of keys that should be preloaded.
        
        Returns:
            List of (key, data_type, priority_score) tuples
        """
        if current_time is None:
            current_time = time.time()
        
        candidates = []
        
        # Analyze individual key patterns
        for key, pattern in self.patterns.items():
            if pattern.should_preload(current_time):
                data_type = self._extract_data_type_from_key(key)
                priority = pattern.get_priority_score()
                candidates.append((key, data_type, priority))
        
        # Sort by priority (highest first)
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        return candidates
    
    def get_pattern_stats(self) -> dict:
        """Get statistics about access patterns."""
        total_patterns = len(self.patterns)
        active_patterns = sum(
            1 for p in self.patterns.values() 
            if p.access_count >= self.min_accesses_for_analysis
        )
        
        high_confidence_patterns = sum(
            1 for p in self.patterns.values()
            if p.prediction_confidence >= 0.7
        )
        
        return {
            'total_patterns': total_patterns,
            'active_patterns': active_patterns,
            'high_confidence_patterns': high_confidence_patterns,
            'popular_keys': len(self.popular_keys),
            'data_type_patterns': len(self.data_type_patterns),
            'average_confidence': (
                sum(p.prediction_confidence for p in self.patterns.values()) / 
                max(total_patterns, 1)
            )
        }
    
    def _extract_data_type_from_key(self, key: str) -> str:
        """Extract data type from cache key."""
        # Simple extraction based on key prefix
        if ':' in key:
            return key.split(':', 1)[0]
        return 'unknown'
    
    def _cleanup_old_patterns(self, current_time: float):
        """Clean up old access patterns to prevent memory bloat."""
        cutoff_time = current_time - (self.pattern_retention_hours * 3600)
        
        keys_to_remove = [
            key for key, pattern in self.patterns.items()
            if (pattern.last_access < cutoff_time and 
                pattern.access_count < self.popularity_threshold)
        ]
        
        for key in keys_to_remove:
            del self.patterns[key]
            self.popular_keys.discard(key)
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old access patterns")