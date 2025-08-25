#!/usr/bin/env python3
"""
Enhanced Cache Preloader Test Script

This script tests the enhanced intelligent cache preloading mechanism
with advanced access pattern analysis and predictive preloading.
"""

import asyncio
import time
import json
from datetime import datetime
from typing import Dict, Any

from .cache_manager import CacheManager
from .cache_preloader import PreloadScheduler
from .cache_config import cache_config


class EnhancedPreloaderTester:
    """Test enhanced cache preloader functionality."""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        # Mock data service client for testing
        self.mock_data_service = None
        self.preloader = PreloadScheduler(self.cache_manager, self.mock_data_service)
        self.test_results = {}
        self.test_start_time = time.time()
    
    async def setup(self):
        """Setup test environment."""
        print("Setting up enhanced preloader test environment...")
        
        # Start cache manager
        await self.cache_manager.start()
        
        # Start preloader
        await self.preloader.start()
        
        print("✓ Test environment ready")
    
    async def test_access_pattern_analysis(self):
        """Test advanced access pattern analysis."""
        print("\n=== Testing Access Pattern Analysis ===")
        
        test_keys = [
            ('stock:000001:price', 'price_data'),
            ('market:status', 'market_status'),
            ('trading:dates:2024', 'trading_dates'),
            ('instrument:000001:detail', 'instrument_detail')
        ]
        
        # Simulate access patterns with different frequencies
        for key, data_type in test_keys:
            print(f"Simulating access pattern for {key}...")
            
            # Create varied access patterns
            if 'price' in key:
                # High frequency pattern (every 30 seconds)
                intervals = [30, 25, 35, 28, 32, 30, 29]
            elif 'status' in key:
                # Medium frequency pattern (every 2 minutes)
                intervals = [120, 115, 125, 118, 122, 120]
            elif 'dates' in key:
                # Low frequency pattern (every 30 minutes)
                intervals = [1800, 1750, 1850, 1780, 1820]
            else:
                # Irregular pattern
                intervals = [60, 300, 45, 180, 90, 240]
            
            # Record access pattern
            current_time = time.time()
            for i, interval in enumerate(intervals):
                access_time = current_time - sum(intervals[i:])
                self.preloader.record_cache_access(key, data_type, hit=True)
                
                # Simulate time passage
                await asyncio.sleep(0.1)
        
        # Analyze patterns
        await self.preloader._update_access_patterns()
        
        # Check pattern analysis results
        pattern_results = {}
        for key, pattern in self.preloader._access_patterns.items():
            pattern_results[key] = {
                'access_count': pattern.access_count,
                'access_velocity': pattern.access_velocity,
                'trend_score': pattern.trend_score,
                'seasonality_score': pattern.seasonality_score,
                'prediction_confidence': pattern.prediction_confidence,
                'next_predicted_access': pattern.next_predicted_access
            }
        
        self.test_results['pattern_analysis'] = pattern_results
        
        print(f"✓ Analyzed {len(pattern_results)} access patterns")
        for key, stats in pattern_results.items():
            print(f"  {key}: velocity={stats['access_velocity']:.4f}, "
                  f"trend={stats['trend_score']:.2f}, "
                  f"confidence={stats['prediction_confidence']:.2f}")
    
    async def test_predictive_preloading(self):
        """Test predictive preloading functionality."""
        print("\n=== Testing Predictive Preloading ===")
        
        # Clear cache to test preloading
        await self.cache_manager.clear()
        
        # Create high-confidence access pattern
        key = 'stock:600000:price'
        data_type = 'price_data'
        
        # Record consistent access pattern
        current_time = time.time()
        for i in range(10):
            self.preloader.record_cache_access(key, data_type, hit=True)
            await asyncio.sleep(0.05)
        
        # Update patterns and trigger predictive preloading
        await self.preloader._update_access_patterns()
        
        # Check if data was preloaded
        preloaded_data = await self.cache_manager.get(key)
        
        self.test_results['predictive_preloading'] = {
            'key_tested': key,
            'data_preloaded': preloaded_data is not None,
            'preload_timestamp': time.time()
        }
        
        print(f"✓ Predictive preloading test completed")
        print(f"  Key: {key}")
        print(f"  Data preloaded: {preloaded_data is not None}")
    
    async def test_data_type_bulk_preloading(self):
        """Test data type level bulk preloading."""
        print("\n=== Testing Data Type Bulk Preloading ===")
        
        # Clear cache
        await self.cache_manager.clear()
        
        # Create strong data type pattern
        data_type = 'market_data'
        keys = ['market:indices', 'market:volume', 'market:turnover']
        
        # Record multiple accesses for this data type
        for key in keys:
            for _ in range(5):
                self.preloader.record_cache_access(key, data_type, hit=True)
                await asyncio.sleep(0.02)
        
        # Trigger bulk preloading
        await self.preloader._update_access_patterns()
        
        # Check preloaded data
        preloaded_keys = []
        for key in ['market:indices', 'market:volume']:
            cached_data = await self.cache_manager.get(key)
            if cached_data is not None:
                preloaded_keys.append(key)
        
        self.test_results['bulk_preloading'] = {
            'data_type': data_type,
            'preloaded_keys': preloaded_keys,
            'preload_count': len(preloaded_keys)
        }
        
        print(f"✓ Bulk preloading test completed")
        print(f"  Data type: {data_type}")
        print(f"  Preloaded keys: {len(preloaded_keys)}")
    
    async def test_adaptive_thresholds(self):
        """Test adaptive threshold functionality."""
        print("\n=== Testing Adaptive Thresholds ===")
        
        # Test different threshold configurations
        threshold_configs = [
            {
                'name': 'conservative',
                'thresholds': {
                    'velocity_threshold': 0.01,
                    'trend_threshold': 0.5,
                    'min_confidence': 0.7,
                    'preload_window': 600
                }
            },
            {
                'name': 'aggressive',
                'thresholds': {
                    'velocity_threshold': 0.001,
                    'trend_threshold': 0.1,
                    'min_confidence': 0.2,
                    'preload_window': 300
                }
            }
        ]
        
        threshold_results = {}
        
        for config in threshold_configs:
            print(f"Testing {config['name']} thresholds...")
            
            # Update preloader thresholds
            self.preloader._adaptive_thresholds.update(config['thresholds'])
            
            # Clear cache and create test pattern
            await self.cache_manager.clear()
            
            test_key = f"test:{config['name']}:data"
            for _ in range(8):
                self.preloader.record_cache_access(test_key, 'test_data', hit=True)
                await asyncio.sleep(0.03)
            
            # Check preloading behavior
            await self.preloader._update_access_patterns()
            
            pattern = self.preloader._access_patterns.get(test_key)
            should_preload = pattern.should_preload(time.time(), config['thresholds']) if pattern else False
            
            threshold_results[config['name']] = {
                'should_preload': should_preload,
                'pattern_exists': pattern is not None,
                'access_count': pattern.access_count if pattern else 0,
                'confidence': pattern.prediction_confidence if pattern else 0
            }
        
        self.test_results['adaptive_thresholds'] = threshold_results
        
        print("✓ Adaptive thresholds test completed")
        for name, result in threshold_results.items():
            print(f"  {name}: should_preload={result['should_preload']}, "
                  f"confidence={result['confidence']:.2f}")
    
    async def test_performance_metrics(self):
        """Test performance metrics and statistics."""
        print("\n=== Testing Performance Metrics ===")
        
        # Get preloader statistics
        stats = self.preloader.get_preload_stats()
        
        # Test cache hit rate improvement
        initial_stats = self.cache_manager.get_stats()
        
        # Simulate cache usage with preloading
        test_keys = ['perf:test:1', 'perf:test:2', 'perf:test:3']
        
        for key in test_keys:
            # Record access pattern
            for _ in range(5):
                self.preloader.record_cache_access(key, 'performance_test', hit=True)
                await asyncio.sleep(0.02)
            
            # Try to get data (should trigger preloading)
            await self.cache_manager.get(key)
        
        # Update patterns
        await self.preloader._update_access_patterns()
        
        final_stats = self.cache_manager.get_stats()
        
        self.test_results['performance_metrics'] = {
            'initial_stats': {
                'hit_rate': initial_stats.hit_rate,
                'hits': initial_stats.hits,
                'misses': initial_stats.misses,
                'entry_count': initial_stats.entry_count,
                'memory_usage': initial_stats.memory_usage
            },
            'final_stats': {
                'hit_rate': final_stats.hit_rate,
                'hits': final_stats.hits,
                'misses': final_stats.misses,
                'entry_count': final_stats.entry_count,
                'memory_usage': final_stats.memory_usage
            },
            'preloader_stats': stats,
            'improvement': {
                 'hit_rate_change': final_stats.hit_rate - initial_stats.hit_rate,
                 'total_requests_change': (final_stats.hits + final_stats.misses) - (initial_stats.hits + initial_stats.misses)
             },
             'pattern_count': len(self.preloader._access_patterns),
             'data_type_patterns': len(self.preloader._data_type_patterns)
        }
        
        print("✓ Performance metrics test completed")
        print(f"  Preloader uptime: {stats['uptime_hours']:.2f} hours")
        print(f"  Total preload tasks: {stats['total_tasks']}")
        print(f"  Success rate: {stats['success_rate']:.2%}")
        print(f"  Access patterns tracked: {len(self.preloader._access_patterns)}")
    
    async def cleanup(self):
        """Cleanup test environment."""
        print("\nCleaning up test environment...")
        
        # Stop preloader
        await self.preloader.stop()
        
        # Stop cache manager
        await self.cache_manager.stop()
        
        print("✓ Cleanup completed")
    
    def export_results(self):
        """Export test results to JSON file."""
        timestamp = int(time.time())
        filename = f"enhanced_preloader_test_{timestamp}.json"
        
        test_summary = {
            'test_timestamp': datetime.now().isoformat(),
            'test_duration': time.time() - self.test_start_time,
            'results': self.test_results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(test_summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Test results exported to {filename}")
        return filename


async def main():
    """Run enhanced preloader tests."""
    print("Enhanced Cache Preloader Test Suite")
    print("=" * 50)
    
    tester = EnhancedPreloaderTester()
    
    try:
        # Setup
        await tester.setup()
        
        # Run tests
        await tester.test_access_pattern_analysis()
        await tester.test_predictive_preloading()
        await tester.test_data_type_bulk_preloading()
        await tester.test_adaptive_thresholds()
        await tester.test_performance_metrics()
        
        # Export results
        results_file = tester.export_results()
        
        print("\n" + "=" * 50)
        print("Enhanced Preloader Test Suite Completed Successfully!")
        print(f"Results saved to: {results_file}")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())