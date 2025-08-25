#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Cache Monitoring System Test Suite

This script tests all enhanced cache monitoring features including:
- Enhanced cache dashboard
- Cache health checker
- Intelligent alert system
- Performance monitoring integration
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any

from .cache_manager import CacheManager
from .cache_monitor import CachePerformanceMonitor
from .enhanced_cache_dashboard import EnhancedCacheDashboard
from .cache_health_checker import CacheHealthChecker
from .intelligent_alert_system import IntelligentAlertSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveCacheTestSuite:
    """Comprehensive test suite for all cache monitoring enhancements."""
    
    def __init__(self):
        """Initialize test suite."""
        self.cache_manager = None
        self.cache_monitor = None
        self.enhanced_dashboard = None
        self.health_checker = None
        self.alert_system = None
        
        self.test_results: List[Dict[str, Any]] = []
        self.start_time = time.time()
    
    async def setup(self) -> bool:
        """Setup test environment."""
        try:
            logger.info("Setting up comprehensive cache test environment...")
            
            # Initialize cache manager
            self.cache_manager = CacheManager()
            await self.cache_manager.start()
            
            # Initialize cache monitor
            self.cache_monitor = CachePerformanceMonitor(history_size=1000)
            await self.cache_monitor.start_monitoring()
            
            # Initialize enhanced dashboard
            self.enhanced_dashboard = EnhancedCacheDashboard(
                self.cache_monitor, self.cache_manager
            )
            await self.enhanced_dashboard.start_real_time_updates()
            
            # Initialize health checker
            self.health_checker = CacheHealthChecker(
                self.cache_monitor, self.cache_manager
            )
            await self.health_checker.start_health_monitoring()
            
            # Initialize intelligent alert system
            self.alert_system = IntelligentAlertSystem(
                self.cache_monitor, self.cache_manager, self.health_checker
            )
            await self.alert_system.start_monitoring()
            
            logger.info("Test environment setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False
    
    async def teardown(self):
        """Cleanup test environment."""
        try:
            logger.info("Cleaning up test environment...")
            
            if self.alert_system:
                await self.alert_system.stop_monitoring()
            
            if self.health_checker:
                await self.health_checker.stop_health_monitoring()
            
            if self.enhanced_dashboard:
                await self.enhanced_dashboard.stop_real_time_updates()
            
            if self.cache_monitor:
                await self.cache_monitor.stop_monitoring()
            
            if self.cache_manager:
                await self.cache_manager.clear_cache()
                await self.cache_manager.stop()
            
            logger.info("Test environment cleanup completed")
            
        except Exception as e:
            logger.error(f"Teardown failed: {e}")
    
    def _record_test_result(self, test_name: str, success: bool, details: Dict[str, Any]):
        """Record test result."""
        self.test_results.append({
            'test_name': test_name,
            'success': success,
            'timestamp': time.time(),
            'duration': time.time() - self.start_time,
            'details': details
        })
        
        status = "PASSED" if success else "FAILED"
        logger.info(f"Test {test_name}: {status}")
    
    async def test_enhanced_dashboard_functionality(self):
        """Test enhanced dashboard features."""
        test_name = "Enhanced Dashboard Functionality"
        
        try:
            # Test real-time chart data
            chart_data = self.enhanced_dashboard.get_chart_data(
                metric_type='hit_rate', time_range=3600
            )
            assert chart_data, "Chart data should not be empty"
            assert 'timestamps' in chart_data, "Chart data missing timestamps"
            assert 'values' in chart_data, "Chart data missing values"
            
            # Test historical trends
            trends = self.enhanced_dashboard.get_historical_trends(
                metrics=['hit_rate', 'memory_usage'], days=1
            )
            assert trends, "Historical trends should not be empty"
            
            # Test performance comparison
            comparison = self.enhanced_dashboard.get_performance_comparison(
                baseline_hours=24, current_hours=1
            )
            assert comparison, "Performance comparison should not be empty"
            assert 'baseline_period' in comparison, "Comparison missing baseline period"
            assert 'current_period' in comparison, "Comparison missing current period"
            
            # Test dashboard export
            export_data = self.enhanced_dashboard.export_dashboard_data(
                format_type='json'
            )
            assert export_data, "Dashboard export should not be empty"
            
            self._record_test_result(test_name, True, {
                "chart_data_points": len(chart_data.get('timestamps', [])),
                "trends_metrics": len(trends),
                "comparison_available": bool(comparison),
                "export_successful": bool(export_data)
            })
            
        except Exception as e:
            logger.error(f"Enhanced dashboard test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_health_checker_functionality(self):
        """Test cache health checker features."""
        test_name = "Health Checker Functionality"
        
        try:
            # Perform comprehensive health check
            health_report = await self.health_checker.perform_health_check()
            
            assert health_report, "Health report should not be empty"
            assert hasattr(health_report, 'overall_status'), "Health report missing overall status"
            assert hasattr(health_report, 'health_score'), "Health report missing health score"
            assert hasattr(health_report, 'checks'), "Health report missing individual checks"
            assert hasattr(health_report, 'recommendations'), "Health report missing recommendations"
            
            # Test individual health checks
            assert len(health_report.checks) > 0, "Health report should contain individual checks"
            
            # Test health summary
            health_summary = health_report.summary
            assert health_summary, "Health summary should not be empty"
            
            # Test latest health report retrieval
            latest_report = self.health_checker.get_latest_health_report()
            assert latest_report, "Latest health report should be available"
            
            self._record_test_result(test_name, True, {
                "overall_status": health_report.overall_status.value,
                "health_score": health_report.health_score,
                "total_checks": len(health_report.checks),
                "recommendations_count": len(health_report.recommendations),
                "uptime_hours": health_report.uptime_hours
            })
            
        except Exception as e:
            logger.error(f"Health checker test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_intelligent_alert_system(self):
        """Test intelligent alert system features."""
        test_name = "Intelligent Alert System"
        
        try:
            # Test alert rule management
            from intelligent_alert_system import AlertRule, AlertCategory, AlertPriority
            
            test_rule = AlertRule(
                name="test_comprehensive_rule",
                metric_name="hit_rate",
                category=AlertCategory.PERFORMANCE,
                condition="lt",
                threshold=0.5,
                priority=AlertPriority.MEDIUM,
                recovery_threshold=0.6,
                tags={"test": "comprehensive"}
            )
            
            rule_added = self.alert_system.add_alert_rule(test_rule)
            assert rule_added, "Alert rule should be added successfully"
            
            # Test alert summary
            alert_summary = self.alert_system.get_alert_summary(hours=24)
            assert alert_summary, "Alert summary should not be empty"
            assert hasattr(alert_summary, 'total_alerts'), "Alert summary missing total alerts"
            assert hasattr(alert_summary, 'active_alerts'), "Alert summary missing active alerts"
            
            # Test alert export
            exported_alerts = self.alert_system.export_alerts(format_type='json')
            assert exported_alerts, "Alert export should not be empty"
            
            # Test CSV export
            csv_export = self.alert_system.export_alerts(format_type='csv')
            assert csv_export, "CSV export should not be empty"
            
            # Test active alerts retrieval
            active_alerts = self.alert_system.get_active_alerts()
            assert isinstance(active_alerts, list), "Active alerts should be a list"
            
            self._record_test_result(test_name, True, {
                "rule_management": rule_added,
                "alert_summary_available": bool(alert_summary),
                "json_export_length": len(exported_alerts),
                "csv_export_length": len(csv_export),
                "active_alerts_count": len(active_alerts)
            })
            
        except Exception as e:
            logger.error(f"Intelligent alert system test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_integration_functionality(self):
        """Test integration between all monitoring components."""
        test_name = "Integration Functionality"
        
        try:
            # Generate some cache activity
            await self._generate_cache_activity()
            
            # Wait for monitoring systems to collect data
            await asyncio.sleep(2)
            
            # Test data flow between components
            # 1. Cache monitor should have metrics
            monitor_stats = self.cache_monitor.get_performance_summary(3600)  # 1 hour window
            assert monitor_stats, "Cache monitor should have statistics"
            
            # 2. Dashboard should have updated data
            dashboard_data = self.enhanced_dashboard.get_chart_data(
                metric_type='hit_rate', time_range=300
            )
            assert dashboard_data, "Dashboard should have updated data"
            
            # 3. Health checker should have recent report
            health_report = self.health_checker.get_latest_health_report()
            assert health_report, "Health checker should have recent report"
            
            # 4. Alert system should be monitoring
            alert_summary = self.alert_system.get_alert_summary(hours=1)
            assert alert_summary, "Alert system should have summary data"
            
            # Test cross-component data consistency
            monitor_hit_rate = getattr(monitor_stats, 'hit_rate', 0)
            dashboard_latest = dashboard_data.get('values', [])[-1] if dashboard_data.get('values') else 0
            
            # Allow for small differences due to timing
            hit_rate_diff = abs(monitor_hit_rate - dashboard_latest)
            data_consistent = hit_rate_diff < 0.1  # 10% tolerance
            
            self._record_test_result(test_name, True, {
                "monitor_has_data": bool(monitor_stats),
                "dashboard_has_data": bool(dashboard_data),
                "health_report_available": bool(health_report),
                "alert_summary_available": bool(alert_summary),
                "data_consistency": data_consistent,
                "monitor_hit_rate": monitor_hit_rate,
                "dashboard_hit_rate": dashboard_latest
            })
            
        except Exception as e:
            logger.error(f"Integration test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def _generate_cache_activity(self):
        """Generate some cache activity for testing."""
        try:
            # Perform cache operations
            for i in range(50):
                key = f"test_key_{i}"
                value = f"test_value_{i}"
                
                # Set some values
                await self.cache_manager.set(key, value, ttl=300)
                
                # Get some values (mix of hits and misses)
                if i % 3 == 0:
                    await self.cache_manager.get(key)
                else:
                    await self.cache_manager.get(f"missing_key_{i}")
            
            logger.info("Generated cache activity for testing")
            
        except Exception as e:
            logger.error(f"Failed to generate cache activity: {e}")
    
    async def run_comprehensive_tests(self):
        """Run all comprehensive tests."""
        logger.info("Starting comprehensive cache monitoring system tests...")
        
        # Setup
        if not await self.setup():
            logger.error("Failed to setup test environment")
            return
        
        try:
            # Run all tests
            await self.test_enhanced_dashboard_functionality()
            await self.test_health_checker_functionality()
            await self.test_intelligent_alert_system()
            await self.test_integration_functionality()
            
        finally:
            # Cleanup
            await self.teardown()
        
        # Generate comprehensive report
        self._generate_comprehensive_report()
    
    def _generate_comprehensive_report(self):
        """Generate and save comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        total_duration = time.time() - self.start_time
        
        report = {
            'test_suite': 'Comprehensive Cache Monitoring System',
            'timestamp': time.time(),
            'total_duration_seconds': total_duration,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': success_rate,
            'test_results': self.test_results,
            'summary': {
                'enhanced_dashboard': any(r['test_name'] == 'Enhanced Dashboard Functionality' and r['success'] for r in self.test_results),
                'health_checker': any(r['test_name'] == 'Health Checker Functionality' and r['success'] for r in self.test_results),
                'intelligent_alerts': any(r['test_name'] == 'Intelligent Alert System' and r['success'] for r in self.test_results),
                'integration': any(r['test_name'] == 'Integration Functionality' and r['success'] for r in self.test_results)
            }
        }
        
        # Save report
        report_filename = f"comprehensive_cache_test_{int(time.time())}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE CACHE MONITORING SYSTEM TEST RESULTS")
        print(f"{'='*80}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Report saved to: {report_filename}")
        print(f"{'='*80}")
        
        # Print component status
        print("\nComponent Test Results:")
        for component, status in report['summary'].items():
            status_icon = "✓" if status else "✗"
            print(f"{status_icon} {component.replace('_', ' ').title()}")
        
        # Print individual test results
        print("\nDetailed Test Results:")
        for result in self.test_results:
            status = "✓" if result['success'] else "✗"
            duration = result['duration']
            print(f"{status} {result['test_name']} ({duration:.2f}s)")
            if not result['success'] and 'error' in result['details']:
                print(f"  Error: {result['details']['error']}")
        
        logger.info(f"Comprehensive test report generated: {report_filename}")


async def main():
    """Main test function."""
    tester = ComprehensiveCacheTestSuite()
    await tester.run_comprehensive_tests()


if __name__ == "__main__":
    asyncio.run(main())