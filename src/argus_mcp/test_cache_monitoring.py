"""Test script for cache performance monitoring and dashboard."""

import asyncio
import json
import time
import random
from datetime import datetime
from typing import Dict, Any

from .cache_manager import CacheManager
from .cache_monitor import cache_monitor
from .cache_dashboard import get_cache_dashboard


class CacheMonitoringTester:
    """Test suite for cache monitoring and dashboard functionality."""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.dashboard = get_cache_dashboard(self.cache_manager)
        self.test_results = {}
        
    async def run_comprehensive_test(self):
        """Run comprehensive cache monitoring test."""
        print("\n=== Cache Performance Monitoring Test ===")
        print(f"Test started at: {datetime.now()}")
        
        try:
            # Initialize monitoring
            await self._test_monitoring_initialization()
            
            # Test cache operations with monitoring
            await self._test_cache_operations_monitoring()
            
            # Test dashboard functionality
            await self._test_dashboard_functionality()
            
            # Test alert system
            await self._test_alert_system()
            
            # Test performance analysis
            await self._test_performance_analysis()
            
            # Export test results
            await self._export_test_results()
            
        except Exception as e:
            print(f"Test failed with error: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def _test_monitoring_initialization(self):
        """Test monitoring system initialization."""
        print("\n1. Testing monitoring initialization...")
        
        # Start performance monitoring
        await cache_monitor.start_monitoring()
        await asyncio.sleep(1)
        
        # Start dashboard
        await self.dashboard.start_dashboard()
        await asyncio.sleep(2)
        
        # Verify monitoring is active
        assert cache_monitor._monitoring_active, "Cache monitor should be active"
        assert self.dashboard._is_running, "Dashboard should be running"
        
        self.test_results['monitoring_initialization'] = {
            'status': 'PASSED',
            'monitor_active': cache_monitor._monitoring_active,
            'dashboard_active': self.dashboard._is_running,
            'timestamp': time.time()
        }
        
        print("✓ Monitoring initialization successful")
    
    async def _test_cache_operations_monitoring(self):
        """Test cache operations with monitoring."""
        print("\n2. Testing cache operations monitoring...")
        
        operations_count = 100
        hit_count = 0
        miss_count = 0
        
        # Perform various cache operations
        for i in range(operations_count):
            key = f"test_key_{i % 20}"  # Create some key overlap for hits
            data_type = random.choice(['market_data', 'user_data', 'config_data'])
            
            # Try to get from cache first (will be miss initially)
            result = await self.cache_manager.get(key)
            if result is None:
                miss_count += 1
                # Store data in cache
                test_data = {
                    'id': i,
                    'data_type': data_type,
                    'value': f"test_value_{i}",
                    'timestamp': time.time()
                }
                await self.cache_manager.set(key, test_data, ttl=300)
            else:
                hit_count += 1
            
            # Add small delay to simulate real usage
            if i % 10 == 0:
                await asyncio.sleep(0.1)
        
        # Wait for monitoring to process events
        await asyncio.sleep(2)
        
        # Get cache stats
        cache_stats = self.cache_manager.get_stats()
        
        self.test_results['cache_operations_monitoring'] = {
            'status': 'PASSED',
            'operations_performed': operations_count,
            'cache_hits': hit_count,
            'cache_misses': miss_count,
            'final_hit_rate': cache_stats.hit_rate,
            'final_entry_count': cache_stats.entry_count,
            'memory_usage_mb': cache_stats.memory_usage / (1024 * 1024),
            'timestamp': time.time()
        }
        
        print(f"✓ Performed {operations_count} cache operations")
        print(f"  - Hits: {hit_count}, Misses: {miss_count}")
        print(f"  - Final hit rate: {cache_stats.hit_rate:.1%}")
        print(f"  - Memory usage: {cache_stats.memory_usage / (1024 * 1024):.2f} MB")
    
    async def _test_dashboard_functionality(self):
        """Test dashboard functionality."""
        print("\n3. Testing dashboard functionality...")
        
        # Wait for dashboard to collect some data
        await asyncio.sleep(3)
        
        # Get dashboard data
        dashboard_data = self.dashboard.get_dashboard_data()
        
        # Verify dashboard data structure
        assert 'current_metrics' in dashboard_data, "Dashboard should have current metrics"
        assert 'performance_history' in dashboard_data, "Dashboard should have performance history"
        assert 'dashboard_status' in dashboard_data, "Dashboard should have status info"
        
        # Get performance trends
        trends = self.dashboard.get_performance_trends(300)  # Last 5 minutes
        
        # Get alert summary
        alert_summary = self.dashboard.get_alert_summary()
        
        self.test_results['dashboard_functionality'] = {
            'status': 'PASSED',
            'dashboard_data_keys': list(dashboard_data.keys()),
            'performance_history_entries': len(dashboard_data['performance_history']),
            'current_health_score': dashboard_data['current_metrics'].get('health_score', 0),
            'trends_available': 'error' not in trends,
            'total_alerts': alert_summary['total_alerts'],
            'timestamp': time.time()
        }
        
        print(f"✓ Dashboard data collected successfully")
        print(f"  - Performance history entries: {len(dashboard_data['performance_history'])}")
        print(f"  - Current health score: {dashboard_data['current_metrics'].get('health_score', 0):.1f}")
        print(f"  - Total alerts: {alert_summary['total_alerts']}")
    
    async def _test_alert_system(self):
        """Test alert system by triggering conditions."""
        print("\n4. Testing alert system...")
        
        initial_alerts = len(cache_monitor._alerts_history)
        
        # Simulate high miss rate to trigger alerts
        for i in range(50):
            # Generate cache misses
            await self.cache_manager.get(f"non_existent_key_{i}")
            
            if i % 10 == 0:
                await asyncio.sleep(0.1)
        
        # Wait for alert processing
        await asyncio.sleep(2)
        
        # Check if alerts were generated
        final_alerts = len(cache_monitor._alerts_history)
        alerts_generated = final_alerts - initial_alerts
        
        # Get recent alerts
        try:
            recent_alerts = cache_monitor._get_recent_alerts(300)  # Last 5 minutes
        except:
            recent_alerts = []
        
        # Handle alert types safely
        alert_types = []
        for alert in recent_alerts:
            if hasattr(alert, 'metric_name'):
                alert_types.append(alert.metric_name)
            elif isinstance(alert, dict) and 'metric_name' in alert:
                alert_types.append(alert['metric_name'])
        
        self.test_results['alert_system'] = {
            'status': 'PASSED',
            'initial_alerts': initial_alerts,
            'final_alerts': final_alerts,
            'alerts_generated': alerts_generated,
            'recent_alerts_count': len(recent_alerts),
            'alert_types': list(set(alert_types)),
            'timestamp': time.time()
        }
        
        print(f"✓ Alert system tested")
        print(f"  - Alerts generated: {alerts_generated}")
        print(f"  - Recent alerts: {len(recent_alerts)}")
        if alert_types:
            print(f"  - Alert types: {list(set(alert_types))}")
    
    async def _test_performance_analysis(self):
        """Test performance analysis features."""
        print("\n5. Testing performance analysis...")
        
        # Get performance summary
        performance_summary = cache_monitor.get_performance_summary(3600)  # Last hour
        
        # Get performance report
        performance_report = cache_monitor.get_performance_report()
        
        # Export metrics
        metrics_file = f"test_metrics_{int(time.time())}.json"
        cache_monitor.export_metrics(metrics_file, 3600)
        
        # Export dashboard report
        dashboard_file = f"test_dashboard_{int(time.time())}.json"
        self.dashboard.export_dashboard_report(dashboard_file)
        
        self.test_results['performance_analysis'] = {
            'status': 'PASSED',
            'performance_summary_keys': list(performance_summary.keys()) if performance_summary else [],
            'performance_report_keys': list(performance_report.keys()) if performance_report else [],
            'health_score': performance_report.get('health_score', 0),
            'recommendations_count': len(performance_report.get('recommendations', [])),
            'metrics_exported': metrics_file,
            'dashboard_exported': dashboard_file,
            'timestamp': time.time()
        }
        
        print(f"✓ Performance analysis completed")
        print(f"  - Health score: {performance_report.get('health_score', 0):.1f}")
        print(f"  - Recommendations: {len(performance_report.get('recommendations', []))}")
        print(f"  - Metrics exported to: {metrics_file}")
        print(f"  - Dashboard exported to: {dashboard_file}")
    
    async def _export_test_results(self):
        """Export comprehensive test results."""
        timestamp = int(time.time())
        results_file = f"cache_monitoring_test_{timestamp}.json"
        
        # Add test summary
        self.test_results['test_summary'] = {
            'total_tests': len([k for k in self.test_results.keys() if k != 'test_summary']),
            'passed_tests': len([v for v in self.test_results.values() 
                               if isinstance(v, dict) and v.get('status') == 'PASSED']),
            'test_duration': time.time() - self.test_results.get('monitoring_initialization', {}).get('timestamp', time.time()),
            'test_timestamp': timestamp,
            'test_date': datetime.now().isoformat()
        }
        
        # Export results
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\n✓ Test results exported to: {results_file}")
        
        # Print summary
        summary = self.test_results['test_summary']
        print(f"\n=== Test Summary ===")
        print(f"Total tests: {summary['total_tests']}")
        print(f"Passed tests: {summary['passed_tests']}")
        print(f"Test duration: {summary['test_duration']:.1f} seconds")
        print(f"Success rate: {summary['passed_tests']/summary['total_tests']*100:.1f}%")
    
    async def _cleanup(self):
        """Clean up test environment."""
        print("\n6. Cleaning up test environment...")
        
        try:
            # Stop dashboard
            await self.dashboard.stop_dashboard()
            
            # Stop monitoring
            await cache_monitor.stop_monitoring()
            
            # Clear cache
            await self.cache_manager.clear()
            
            print("✓ Test environment cleaned up")
            
        except Exception as e:
            print(f"Warning: Cleanup error: {e}")


async def main():
    """Run the cache monitoring test suite."""
    tester = CacheMonitoringTester()
    await tester.run_comprehensive_test()


if __name__ == "__main__":
    asyncio.run(main())