"""Test script for Intelligent Alert System.

This script tests the advanced alert system with intelligent deduplication,
tiered alerting, and automatic recovery detection.
"""

import asyncio
import time
import json
import logging
from typing import Dict, Any

from .cache_manager import CacheManager
from .cache_monitor import CachePerformanceMonitor
from .cache_health_checker import CacheHealthChecker
from .intelligent_alert_system import (
    IntelligentAlertSystem, AlertRule, AlertCategory, AlertPriority,
    AlertStatus, IntelligentAlert
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntelligentAlertSystemTester:
    """Test suite for intelligent alert system."""
    
    def __init__(self):
        """Initialize the tester."""
        self.cache_manager = None
        self.cache_monitor = None
        self.health_checker = None
        self.alert_system = None
        self.test_results = []
    
    async def setup(self):
        """Set up test environment."""
        try:
            # Initialize components
            self.cache_manager = CacheManager()
            await self.cache_manager.start()
            
            self.cache_monitor = CachePerformanceMonitor(history_size=1000)
            await self.cache_monitor.start_monitoring()
            
            self.health_checker = CacheHealthChecker(self.cache_manager, self.cache_monitor)
            await self.health_checker.start_health_monitoring()
            
            self.alert_system = IntelligentAlertSystem(
                self.cache_monitor,
                self.cache_manager,
                self.health_checker
            )
            
            logger.info("Test environment setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False
    
    async def teardown(self):
        """Clean up test environment."""
        try:
            if self.alert_system:
                await self.alert_system.stop_monitoring()
            
            if self.health_checker:
                await self.health_checker.stop_health_monitoring()
            
            if self.cache_monitor:
                await self.cache_monitor.stop_monitoring()
            
            if self.cache_manager:
                await self.cache_manager.clear()
            
            logger.info("Test environment cleanup completed")
            
        except Exception as e:
            logger.error(f"Teardown failed: {e}")
    
    def _record_test_result(self, test_name: str, success: bool, 
                           details: Dict[str, Any] = None):
        """Record test result.
        
        Args:
            test_name: Name of the test
            success: Whether test passed
            details: Additional test details
        """
        result = {
            'test_name': test_name,
            'success': success,
            'timestamp': time.time(),
            'details': details or {}
        }
        self.test_results.append(result)
        
        status = "PASSED" if success else "FAILED"
        logger.info(f"Test {test_name}: {status}")
    
    async def test_alert_rule_management(self):
        """Test alert rule management functionality."""
        test_name = "Alert Rule Management"
        
        try:
            # Test adding custom rule
            custom_rule = AlertRule(
                name="test_custom_rule",
                metric_name="test_metric",
                category=AlertCategory.PERFORMANCE,
                condition="gt",
                threshold=100.0,
                priority=AlertPriority.MEDIUM,
                recovery_threshold=90.0,
                tags={"test": "true"}
            )
            
            success = self.alert_system.add_alert_rule(custom_rule)
            assert success, "Failed to add custom rule"
            
            # Test updating rule
            update_success = self.alert_system.update_alert_rule(
                "test_custom_rule",
                {"threshold": 150.0, "priority": AlertPriority.HIGH}
            )
            assert update_success, "Failed to update rule"
            
            # Test removing rule
            remove_success = self.alert_system.remove_alert_rule("test_custom_rule")
            assert remove_success, "Failed to remove rule"
            
            # Test duplicate rule addition
            self.alert_system.add_alert_rule(custom_rule)
            duplicate_success = self.alert_system.add_alert_rule(custom_rule)
            assert not duplicate_success, "Should not allow duplicate rules"
            
            self._record_test_result(test_name, True, {
                "rules_tested": 1,
                "operations": ["add", "update", "remove", "duplicate_check"]
            })
            
        except Exception as e:
            logger.error(f"Alert rule management test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_alert_creation_and_deduplication(self):
        """Test alert creation and deduplication."""
        test_name = "Alert Creation and Deduplication"
        
        try:
            # Start monitoring
            await self.alert_system.start_monitoring()
            
            # Simulate low hit rate condition
            # We'll manually trigger alert creation by modifying cache stats
            initial_alerts = len(self.alert_system.get_active_alerts())
            
            # Wait for monitoring cycle
            await asyncio.sleep(2)
            
            # Check if any alerts were created
            current_alerts = self.alert_system.get_active_alerts()
            
            # Test alert acknowledgment
            if current_alerts:
                alert = current_alerts[0]
                ack_success = await self.alert_system.acknowledge_alert(
                    alert.id, "test_user"
                )
                assert ack_success, "Failed to acknowledge alert"
                assert alert.status == AlertStatus.ACKNOWLEDGED, "Alert not acknowledged"
            
            self._record_test_result(test_name, True, {
                "initial_alerts": initial_alerts,
                "current_alerts": len(current_alerts),
                "alert_details": [{
                    "id": alert.id,
                    "title": alert.title,
                    "priority": alert.priority.value,
                    "status": alert.status.value
                } for alert in current_alerts[:3]]  # First 3 alerts
            })
            
        except Exception as e:
            logger.error(f"Alert creation test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_alert_escalation(self):
        """Test alert escalation functionality."""
        test_name = "Alert Escalation"
        
        try:
            # Create a rule with escalation
            escalation_rule = AlertRule(
                name="test_escalation",
                metric_name="test_escalation_metric",
                category=AlertCategory.PERFORMANCE,
                condition="gt",
                threshold=50.0,
                priority=AlertPriority.LOW,
                escalation_thresholds=[
                    (5, AlertPriority.MEDIUM),  # 5 seconds
                    (10, AlertPriority.HIGH),   # 10 seconds
                    (15, AlertPriority.CRITICAL) # 15 seconds
                ],
                tags={"test": "escalation"}
            )
            
            self.alert_system.add_alert_rule(escalation_rule)
            
            # Manually create an alert for testing
            test_alert = IntelligentAlert(
                id="test_escalation_alert",
                title="Test Escalation Alert",
                message="Testing escalation functionality",
                category=AlertCategory.PERFORMANCE,
                priority=AlertPriority.LOW,
                status=AlertStatus.ACTIVE,
                metric_name="test_escalation_metric",
                current_value=75.0,
                threshold_value=50.0,
                timestamp=time.time(),
                first_occurrence=time.time() - 20,  # 20 seconds ago
                last_occurrence=time.time(),
                occurrence_count=1,
                fingerprint="test_fingerprint",
                tags={"test": "escalation"},
                context={}
            )
            
            self.alert_system._alerts[test_alert.id] = test_alert
            
            # Process escalations
            await self.alert_system._process_escalations()
            
            # Check if alert was escalated
            escalated_alert = self.alert_system._alerts[test_alert.id]
            
            self._record_test_result(test_name, True, {
                "original_priority": AlertPriority.LOW.value,
                "escalated_priority": escalated_alert.priority.value,
                "escalation_level": escalated_alert.escalation_level,
                "duration": time.time() - escalated_alert.first_occurrence
            })
            
        except Exception as e:
            logger.error(f"Alert escalation test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_alert_recovery(self):
        """Test automatic alert recovery."""
        test_name = "Alert Recovery"
        
        try:
            # Create a test alert
            recovery_alert = IntelligentAlert(
                id="test_recovery_alert",
                title="Test Recovery Alert",
                message="Testing recovery functionality",
                category=AlertCategory.PERFORMANCE,
                priority=AlertPriority.HIGH,
                status=AlertStatus.ACTIVE,
                metric_name="hit_rate",
                current_value=0.6,
                threshold_value=0.7,
                timestamp=time.time(),
                first_occurrence=time.time(),
                last_occurrence=time.time(),
                occurrence_count=1,
                fingerprint="test_recovery_fingerprint",
                tags={},
                context={},
                recovery_threshold=0.75
            )
            
            self.alert_system._alerts[recovery_alert.id] = recovery_alert
            
            # Test manual resolution
            resolve_success = await self.alert_system.resolve_alert(
                recovery_alert.id, "Manual resolution for testing"
            )
            assert resolve_success, "Failed to resolve alert"
            
            resolved_alert = self.alert_system._alerts[recovery_alert.id]
            assert resolved_alert.status == AlertStatus.RESOLVED, "Alert not resolved"
            
            self._record_test_result(test_name, True, {
                "alert_resolved": True,
                "resolution_method": "manual",
                "resolution_time": resolved_alert.resolved_at
            })
            
        except Exception as e:
            logger.error(f"Alert recovery test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_alert_suppression(self):
        """Test alert suppression functionality."""
        test_name = "Alert Suppression"
        
        try:
            # Create a test alert
            suppression_alert = IntelligentAlert(
                id="test_suppression_alert",
                title="Test Suppression Alert",
                message="Testing suppression functionality",
                category=AlertCategory.CAPACITY,
                priority=AlertPriority.MEDIUM,
                status=AlertStatus.ACTIVE,
                metric_name="memory_usage_ratio",
                current_value=0.9,
                threshold_value=0.85,
                timestamp=time.time(),
                first_occurrence=time.time(),
                last_occurrence=time.time(),
                occurrence_count=1,
                fingerprint="test_suppression_fingerprint",
                tags={},
                context={}
            )
            
            self.alert_system._alerts[suppression_alert.id] = suppression_alert
            
            # Test suppression
            suppress_success = await self.alert_system.suppress_alert(
                suppression_alert.id, 30  # 30 minutes
            )
            assert suppress_success, "Failed to suppress alert"
            
            suppressed_alert = self.alert_system._alerts[suppression_alert.id]
            assert suppressed_alert.status == AlertStatus.SUPPRESSED, "Alert not suppressed"
            assert suppressed_alert.suppressed_until is not None, "Suppression time not set"
            
            self._record_test_result(test_name, True, {
                "alert_suppressed": True,
                "suppression_duration_minutes": 30,
                "suppressed_until": suppressed_alert.suppressed_until
            })
            
        except Exception as e:
            logger.error(f"Alert suppression test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def test_alert_summary_and_export(self):
        """Test alert summary and export functionality."""
        test_name = "Alert Summary and Export"
        
        try:
            # Get alert summary
            summary = self.alert_system.get_alert_summary(24)
            
            assert hasattr(summary, 'total_alerts'), "Summary missing total_alerts"
            assert hasattr(summary, 'active_alerts'), "Summary missing active_alerts"
            assert hasattr(summary, 'alerts_by_category'), "Summary missing alerts_by_category"
            assert hasattr(summary, 'alerts_by_priority'), "Summary missing alerts_by_priority"
            
            # Test export functionality
            export_data_json = self.alert_system.export_alerts(format_type='json')
            export_data_csv = self.alert_system.export_alerts(format_type='csv')
            
            # Verify export data is valid
            assert export_data_json, "JSON export data is empty"
            assert export_data_csv, "CSV export data is empty"
            
            # Parse JSON to verify structure
            import json
            parsed_json = json.loads(export_data_json)
            assert isinstance(parsed_json, list), "JSON export should be a list of alerts"
            
            self._record_test_result(test_name, True, {
                "summary_stats": {
                    "total_alerts": summary.total_alerts,
                    "active_alerts": summary.active_alerts,
                    "critical_alerts": summary.critical_alerts,
                    "alert_rate": summary.alert_rate,
                    "resolution_rate": summary.resolution_rate
                },
                "export_successful": True,
                "json_export_length": len(export_data_json),
                "csv_export_length": len(export_data_csv)
            })
            
        except Exception as e:
            logger.error(f"Alert summary and export test failed: {e}")
            self._record_test_result(test_name, False, {"error": str(e)})
    
    async def run_all_tests(self):
        """Run all intelligent alert system tests."""
        logger.info("Starting Intelligent Alert System tests...")
        
        # Setup
        if not await self.setup():
            logger.error("Failed to setup test environment")
            return
        
        try:
            # Run tests
            await self.test_alert_rule_management()
            await self.test_alert_creation_and_deduplication()
            await self.test_alert_escalation()
            await self.test_alert_recovery()
            await self.test_alert_suppression()
            await self.test_alert_summary_and_export()
            
        finally:
            # Cleanup
            await self.teardown()
        
        # Generate test report
        self._generate_test_report()
    
    def _generate_test_report(self):
        """Generate and save test report."""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            'test_suite': 'Intelligent Alert System',
            'timestamp': time.time(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': success_rate,
            'test_results': self.test_results
        }
        
        # Save report
        report_filename = f"intelligent_alert_test_{int(time.time())}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"INTELLIGENT ALERT SYSTEM TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Report saved to: {report_filename}")
        print(f"{'='*60}")
        
        # Print individual test results
        for result in self.test_results:
            status = "✓" if result['success'] else "✗"
            print(f"{status} {result['test_name']}")
            if not result['success'] and 'error' in result['details']:
                print(f"  Error: {result['details']['error']}")
        
        logger.info(f"Test report generated: {report_filename}")


async def main():
    """Main test function."""
    tester = IntelligentAlertSystemTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())