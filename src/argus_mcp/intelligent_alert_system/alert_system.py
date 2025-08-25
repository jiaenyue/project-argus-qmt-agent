"""Intelligent Alert System Core Implementation.

This module contains the main IntelligentAlertSystem class with all alert management functionality.
"""

import time
import asyncio
import logging
import hashlib
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque

from .alert_types import (
    AlertPriority, AlertStatus, AlertCategory,
    IntelligentAlert, AlertRule, AlertSummary
)

logger = logging.getLogger(__name__)


class IntelligentAlertSystem:
    """Advanced alert system with intelligent features."""
    
    def __init__(self, cache_monitor, cache_manager, health_checker):
        """Initialize intelligent alert system.
        
        Args:
            cache_monitor: Cache performance monitor
            cache_manager: Cache manager
            health_checker: Cache health checker
        """
        self.cache_monitor = cache_monitor
        self.cache_manager = cache_manager
        self.health_checker = health_checker
        
        # Alert storage
        self._alerts: Dict[str, IntelligentAlert] = {}
        self._alert_history: deque = deque(maxlen=10000)
        self._fingerprint_cache: Dict[str, str] = {}
        
        # Alert rules
        self._alert_rules: Dict[str, AlertRule] = {}
        self._initialize_default_rules()
        
        # Deduplication and suppression
        self._suppression_rules: Dict[str, Dict[str, Any]] = {}
        self._alert_groups: Dict[str, Set[str]] = defaultdict(set)
        
        # Rate limiting
        self._rate_limits: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # System state
        self._is_monitoring = False
        self._last_check_time = 0
        
        # Configuration
        self.config = {
            'check_interval': 60,  # seconds
            'deduplication_window': 300,  # 5 minutes
            'auto_resolve_timeout': 3600,  # 1 hour
            'escalation_enabled': True,
            'max_alerts_per_metric': 10,
            'alert_retention_days': 30
        }
    
    def _initialize_default_rules(self):
        """Initialize default alert rules."""
        default_rules = [
            AlertRule(
                name="low_hit_rate",
                metric_name="hit_rate",
                category=AlertCategory.PERFORMANCE,
                condition="lt",
                threshold=0.7,
                priority=AlertPriority.HIGH,
                recovery_threshold=0.75,
                escalation_thresholds=[(300, AlertPriority.CRITICAL)],
                tags={"type": "performance", "component": "cache"}
            ),
            AlertRule(
                name="high_memory_usage",
                metric_name="memory_usage_ratio",
                category=AlertCategory.CAPACITY,
                condition="gt",
                threshold=0.85,
                priority=AlertPriority.HIGH,
                recovery_threshold=0.8,
                escalation_thresholds=[(600, AlertPriority.CRITICAL)],
                tags={"type": "capacity", "component": "memory"}
            ),
            AlertRule(
                name="high_response_time",
                metric_name="avg_response_time",
                category=AlertCategory.PERFORMANCE,
                condition="gt",
                threshold=2.0,
                priority=AlertPriority.MEDIUM,
                recovery_threshold=1.5,
                escalation_thresholds=[(300, AlertPriority.HIGH), (900, AlertPriority.CRITICAL)],
                tags={"type": "performance", "component": "latency"}
            ),
            AlertRule(
                name="high_error_rate",
                metric_name="error_rate",
                category=AlertCategory.HEALTH,
                condition="gt",
                threshold=0.05,
                priority=AlertPriority.HIGH,
                recovery_threshold=0.02,
                escalation_thresholds=[(180, AlertPriority.CRITICAL)],
                tags={"type": "health", "component": "errors"}
            ),
            AlertRule(
                name="cache_connectivity_failure",
                metric_name="connectivity_status",
                category=AlertCategory.CONNECTIVITY,
                condition="eq",
                threshold=0,  # 0 = failed, 1 = success
                priority=AlertPriority.CRITICAL,
                recovery_threshold=1,
                min_duration=30,
                tags={"type": "connectivity", "component": "backend"}
            )
        ]
        
        for rule in default_rules:
            self._alert_rules[rule.name] = rule
    
    async def start_monitoring(self):
        """Start intelligent alert monitoring."""
        if self._is_monitoring:
            logger.warning("Alert monitoring is already running")
            return
        
        self._is_monitoring = True
        asyncio.create_task(self._monitoring_loop())
        logger.info("Started intelligent alert monitoring")
    
    async def stop_monitoring(self):
        """Stop alert monitoring."""
        self._is_monitoring = False
        logger.info("Stopped intelligent alert monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._is_monitoring:
            try:
                await self._check_alerts()
                await self._process_escalations()
                await self._auto_resolve_alerts()
                await self._cleanup_old_alerts()
                await asyncio.sleep(self.config['check_interval'])
            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(self.config['check_interval'])
    
    async def _check_alerts(self):
        """Check for new alerts based on current metrics."""
        try:
            # Get current metrics
            cache_stats = await self.cache_manager.get_cache_statistics()
            health_report = self.health_checker.get_latest_health_report()
            
            current_metrics = {
                'hit_rate': getattr(cache_stats, 'hit_rate', 0.0),
                'memory_usage_ratio': getattr(cache_stats, 'memory_usage', 0) / max(getattr(cache_stats, 'max_memory', 1), 1),
                'avg_response_time': getattr(cache_stats, 'avg_response_time', 0.0),
                'error_rate': 0.0,  # Will be calculated from performance monitor
                'connectivity_status': 1.0  # Will be determined from health checks
            }
            
            # Get error rate from performance monitor
            try:
                perf_summary = self.cache_monitor.get_performance_summary(1)
                total_ops = perf_summary.get('total_operations', 1)
                error_count = perf_summary.get('error_count', 0)
                current_metrics['error_rate'] = error_count / total_ops if total_ops > 0 else 0
            except Exception:
                pass
            
            # Check connectivity from health report
            if health_report:
                for check in health_report.checks:
                    if check.check_name == 'cache_connectivity':
                        current_metrics['connectivity_status'] = 1.0 if check.status.name in ['GOOD', 'EXCELLENT'] else 0.0
                        break
            
            # Evaluate alert rules
            for rule_name, rule in self._alert_rules.items():
                if not rule.enabled:
                    continue
                
                metric_value = current_metrics.get(rule.metric_name)
                if metric_value is None:
                    continue
                
                should_alert = self._evaluate_condition(metric_value, rule.condition, rule.threshold)
                
                if should_alert:
                    await self._create_or_update_alert(rule, metric_value, current_metrics)
                else:
                    await self._check_recovery(rule, metric_value)
        
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition."""
        if condition == 'gt':
            return value > threshold
        elif condition == 'lt':
            return value < threshold
        elif condition == 'eq':
            return abs(value - threshold) < 0.001
        elif condition == 'ne':
            return abs(value - threshold) >= 0.001
        else:
            return False
    
    async def _create_or_update_alert(self, rule: AlertRule, metric_value: float, context: Dict[str, Any]):
        """Create new alert or update existing one."""
        # Generate fingerprint for deduplication
        fingerprint = self._generate_fingerprint(rule, metric_value)
        
        # Check if alert already exists
        existing_alert = None
        for alert in self._alerts.values():
            if alert.fingerprint == fingerprint and alert.status == AlertStatus.ACTIVE:
                existing_alert = alert
                break
        
        current_time = time.time()
        
        if existing_alert:
            # Update existing alert
            existing_alert.last_occurrence = current_time
            existing_alert.occurrence_count += 1
            existing_alert.current_value = metric_value
            existing_alert.context.update(context)
            
            # Check for escalation
            if self.config['escalation_enabled'] and rule.escalation_thresholds:
                duration = current_time - existing_alert.first_occurrence
                for escalation_time, escalation_priority in rule.escalation_thresholds:
                    if duration >= escalation_time and existing_alert.priority.value != escalation_priority.value:
                        existing_alert.priority = escalation_priority
                        existing_alert.escalation_level += 1
                        logger.warning(f"Alert {existing_alert.id} escalated to {escalation_priority.value}")
                        break
        else:
            # Check rate limiting
            if self._is_rate_limited(rule.name):
                logger.debug(f"Alert for rule {rule.name} is rate limited")
                return
            
            # Create new alert
            alert_id = self._generate_alert_id(rule, current_time)
            
            new_alert = IntelligentAlert(
                id=alert_id,
                title=f"{rule.name.replace('_', ' ').title()}",
                message=self._generate_alert_message(rule, metric_value),
                category=rule.category,
                priority=rule.priority,
                status=AlertStatus.ACTIVE,
                metric_name=rule.metric_name,
                current_value=metric_value,
                threshold_value=rule.threshold,
                timestamp=current_time,
                first_occurrence=current_time,
                last_occurrence=current_time,
                occurrence_count=1,
                fingerprint=fingerprint,
                tags=rule.tags or {},
                context=context,
                recovery_threshold=rule.recovery_threshold
            )
            
            self._alerts[alert_id] = new_alert
            self._alert_history.append(new_alert)
            
            # Update rate limiting
            self._rate_limits[rule.name].append(current_time)
            
            logger.warning(f"New alert created: {new_alert.title} - {new_alert.message}")
    
    async def _check_recovery(self, rule: AlertRule, metric_value: float):
        """Check if any alerts for this rule should be resolved."""
        if rule.recovery_threshold is None:
            return
        
        # Find active alerts for this rule
        active_alerts = [
            alert for alert in self._alerts.values()
            if alert.metric_name == rule.metric_name and alert.status == AlertStatus.ACTIVE
        ]
        
        for alert in active_alerts:
            should_recover = self._evaluate_recovery_condition(metric_value, rule.condition, rule.recovery_threshold)
            
            if should_recover:
                await self._resolve_alert(alert.id, "Automatic recovery - metric returned to normal")
    
    def _evaluate_recovery_condition(self, value: float, condition: str, recovery_threshold: float) -> bool:
        """Evaluate recovery condition."""
        # Recovery condition is opposite of alert condition
        if condition == 'gt':
            return value <= recovery_threshold
        elif condition == 'lt':
            return value >= recovery_threshold
        elif condition == 'eq':
            return abs(value - recovery_threshold) >= 0.001
        elif condition == 'ne':
            return abs(value - recovery_threshold) < 0.001
        else:
            return False
    
    async def _process_escalations(self):
        """Process alert escalations."""
        if not self.config['escalation_enabled']:
            return
        
        current_time = time.time()
        
        for alert in self._alerts.values():
            if alert.status != AlertStatus.ACTIVE:
                continue
            
            rule = self._alert_rules.get(alert.metric_name)
            if not rule or not rule.escalation_thresholds:
                continue
            
            duration = current_time - alert.first_occurrence
            
            for escalation_time, escalation_priority in rule.escalation_thresholds:
                if (duration >= escalation_time and 
                    alert.escalation_level < len(rule.escalation_thresholds) and
                    alert.priority != escalation_priority):
                    
                    alert.priority = escalation_priority
                    alert.escalation_level += 1
                    
                    logger.warning(f"Alert {alert.id} escalated to {escalation_priority.value} after {duration:.0f}s")
    
    async def _auto_resolve_alerts(self):
        """Automatically resolve stale alerts."""
        current_time = time.time()
        timeout = self.config['auto_resolve_timeout']
        
        stale_alerts = [
            alert for alert in self._alerts.values()
            if (alert.status == AlertStatus.ACTIVE and 
                current_time - alert.last_occurrence > timeout)
        ]
        
        for alert in stale_alerts:
            await self._resolve_alert(alert.id, "Automatic resolution - no recent occurrences")
    
    async def _cleanup_old_alerts(self):
        """Clean up old resolved alerts."""
        current_time = time.time()
        retention_seconds = self.config['alert_retention_days'] * 24 * 3600
        
        old_alert_ids = [
            alert_id for alert_id, alert in self._alerts.items()
            if (alert.status in [AlertStatus.RESOLVED, AlertStatus.SUPPRESSED] and
                current_time - alert.timestamp > retention_seconds)
        ]
        
        for alert_id in old_alert_ids:
            del self._alerts[alert_id]
        
        if old_alert_ids:
            logger.info(f"Cleaned up {len(old_alert_ids)} old alerts")
    
    def _generate_fingerprint(self, rule: AlertRule, metric_value: float) -> str:
        """Generate unique fingerprint for alert deduplication."""
        fingerprint_data = f"{rule.name}:{rule.metric_name}:{rule.threshold}"
        return hashlib.md5(fingerprint_data.encode()).hexdigest()[:16]
    
    def _generate_alert_id(self, rule: AlertRule, timestamp: float) -> str:
        """Generate unique alert ID."""
        return f"{rule.name}_{int(timestamp)}_{hash(rule.name) % 10000:04d}"
    
    def _generate_alert_message(self, rule: AlertRule, metric_value: float) -> str:
        """Generate alert message."""
        if rule.condition == 'gt':
            return f"{rule.metric_name} is {metric_value:.3f}, above threshold {rule.threshold:.3f}"
        elif rule.condition == 'lt':
            return f"{rule.metric_name} is {metric_value:.3f}, below threshold {rule.threshold:.3f}"
        elif rule.condition == 'eq':
            return f"{rule.metric_name} equals {metric_value:.3f}, matching threshold {rule.threshold:.3f}"
        else:
            return f"{rule.metric_name} is {metric_value:.3f}, threshold {rule.threshold:.3f}"
    
    def _is_rate_limited(self, rule_name: str) -> bool:
        """Check if alert is rate limited."""
        rule = self._alert_rules.get(rule_name)
        if not rule:
            return False
        
        current_time = time.time()
        recent_alerts = [
            timestamp for timestamp in self._rate_limits[rule_name]
            if current_time - timestamp < rule.max_frequency
        ]
        
        return len(recent_alerts) >= self.config['max_alerts_per_metric']
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = time.time()
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True
    
    async def resolve_alert(self, alert_id: str, resolution_note: str = "") -> bool:
        """Manually resolve an alert."""
        return await self._resolve_alert(alert_id, resolution_note)
    
    async def _resolve_alert(self, alert_id: str, resolution_note: str = "") -> bool:
        """Internal method to resolve an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = time.time()
        
        if resolution_note:
            alert.context['resolution_note'] = resolution_note
        
        logger.info(f"Alert {alert_id} resolved: {resolution_note}")
        return True
    
    async def suppress_alert(self, alert_id: str, duration_minutes: int) -> bool:
        """Suppress an alert for a specified duration."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.SUPPRESSED
        alert.suppressed_until = time.time() + (duration_minutes * 60)
        
        logger.info(f"Alert {alert_id} suppressed for {duration_minutes} minutes")
        return True
    
    def get_active_alerts(self, category: Optional[AlertCategory] = None, 
                         priority: Optional[AlertPriority] = None) -> List[IntelligentAlert]:
        """Get active alerts with optional filtering."""
        alerts = [
            alert for alert in self._alerts.values()
            if alert.status == AlertStatus.ACTIVE
        ]
        
        if category:
            alerts = [alert for alert in alerts if alert.category == category]
        
        if priority:
            alerts = [alert for alert in alerts if alert.priority == priority]
        
        # Sort by priority and timestamp
        priority_order = {AlertPriority.CRITICAL: 0, AlertPriority.HIGH: 1, 
                         AlertPriority.MEDIUM: 2, AlertPriority.LOW: 3}
        
        alerts.sort(key=lambda a: (priority_order.get(a.priority, 4), -a.timestamp))
        
        return alerts
    
    def get_alert_summary(self, hours: int = 24) -> AlertSummary:
        """Get alert summary for specified time period."""
        cutoff_time = time.time() - (hours * 3600)
        
        # Filter alerts within time period
        recent_alerts = [
            alert for alert in self._alerts.values()
            if alert.timestamp >= cutoff_time
        ]
        
        # Calculate statistics
        total_alerts = len(recent_alerts)
        active_alerts = len([a for a in recent_alerts if a.status == AlertStatus.ACTIVE])
        critical_alerts = len([a for a in recent_alerts if a.priority == AlertPriority.CRITICAL])
        high_priority_alerts = len([a for a in recent_alerts if a.priority == AlertPriority.HIGH])
        
        # Group by category and priority
        alerts_by_category = defaultdict(int)
        alerts_by_priority = defaultdict(int)
        
        for alert in recent_alerts:
            alerts_by_category[alert.category.value] += 1
            alerts_by_priority[alert.priority.value] += 1
        
        # Top metrics by alert count
        metric_counts = defaultdict(int)
        for alert in recent_alerts:
            metric_counts[alert.metric_name] += 1
        
        top_metrics = sorted(metric_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate rates
        alert_rate = total_alerts / hours if hours > 0 else 0
        resolved_alerts = len([a for a in recent_alerts if a.status == AlertStatus.RESOLVED])
        resolution_rate = (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
        
        # Get most recent alerts
        recent_alerts_sorted = sorted(recent_alerts, key=lambda a: a.timestamp, reverse=True)[:10]
        
        return AlertSummary(
            total_alerts=total_alerts,
            active_alerts=active_alerts,
            critical_alerts=critical_alerts,
            high_priority_alerts=high_priority_alerts,
            alerts_by_category=dict(alerts_by_category),
            alerts_by_priority=dict(alerts_by_priority),
            recent_alerts=recent_alerts_sorted,
            top_metrics=top_metrics,
            alert_rate=alert_rate,
            resolution_rate=resolution_rate
        )
    
    def add_alert_rule(self, rule: AlertRule) -> bool:
        """Add a new alert rule."""
        if rule.name in self._alert_rules:
            logger.warning(f"Alert rule {rule.name} already exists")
            return False
        
        self._alert_rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
        return True
    
    def update_alert_rule(self, rule_name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing alert rule."""
        rule = self._alert_rules.get(rule_name)
        if not rule:
            return False
        
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        logger.info(f"Updated alert rule: {rule_name}")
        return True
    
    def remove_alert_rule(self, rule_name: str) -> bool:
        """Remove an alert rule."""
        if rule_name not in self._alert_rules:
            return False
        
        del self._alert_rules[rule_name]
        logger.info(f"Removed alert rule: {rule_name}")
        return True
    
    def export_alerts(self, format_type: str = 'json', 
                      start_time: Optional[float] = None,
                      end_time: Optional[float] = None) -> str:
        """Export alerts in specified format."""
        alerts = self.get_active_alerts()
        
        if start_time or end_time:
            filtered_alerts = []
            for alert in alerts:
                if start_time and alert.timestamp < start_time:
                    continue
                if end_time and alert.timestamp > end_time:
                    continue
                filtered_alerts.append(alert)
            alerts = filtered_alerts
        
        if format_type == 'json':
            # Convert alerts to dict with enum values as strings
            alert_dicts = []
            for alert in alerts:
                alert_dict = asdict(alert)
                # Convert enum values to strings
                if 'priority' in alert_dict:
                    alert_dict['priority'] = alert_dict['priority'].value if hasattr(alert_dict['priority'], 'value') else str(alert_dict['priority'])
                if 'status' in alert_dict:
                    alert_dict['status'] = alert_dict['status'].value if hasattr(alert_dict['status'], 'value') else str(alert_dict['status'])
                if 'category' in alert_dict:
                    alert_dict['category'] = alert_dict['category'].value if hasattr(alert_dict['category'], 'value') else str(alert_dict['category'])
                alert_dicts.append(alert_dict)
            
            import json
            return json.dumps(alert_dicts, indent=2, default=str)
        elif format_type == 'csv':
            if not alerts:
                return "No alerts to export"
            
            import csv
            import io
            
            output = io.StringIO()
            # Convert first alert to get field names
            first_alert_dict = asdict(alerts[0])
            # Convert enum values to strings for CSV
            for key, value in first_alert_dict.items():
                if hasattr(value, 'value'):
                    first_alert_dict[key] = value.value
            
            writer = csv.DictWriter(output, fieldnames=first_alert_dict.keys())
            writer.writeheader()
            
            for alert in alerts:
                alert_dict = asdict(alert)
                # Convert enum values to strings
                for key, value in alert_dict.items():
                    if hasattr(value, 'value'):
                        alert_dict[key] = value.value
                writer.writerow(alert_dict)
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format_type}")