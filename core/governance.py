"""OpenPlexComputer - Governance Framework: Kill Switch & Cost Control

This module implements the governance framework including:
- Global kill switch for emergency shutdown
- Automated cost-control monitoring
- Budget enforcement and alerts
- Compliance reporting
"""

import os
import sys
import json
import logging
import signal
import threading
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))
from sandbox import get_sandbox, SecureVault, AuditLogger
from orchestrator import CostTracker

logger = logging.getLogger("openplex.governance")


class KillSwitchState(Enum):
    """States of the kill switch."""
    ACTIVE = "active"           # Normal operation
    TRIGGERED = "triggered"       # Kill switch activated
    SHUTDOWN = "shutdown"         # System shutdown complete


class AlertLevel(Enum):
    """Alert levels for cost monitoring."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class BudgetAlert:
    """Budget alert notification."""
    alert_id: str
    level: AlertLevel
    message: str
    current_spend: float
    budget_limit: float
    percentage_used: float
    timestamp: str
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "message": self.message,
            "current_spend": self.current_spend,
            "budget_limit": self.budget_limit,
            "percentage_used": self.percentage_used,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged
        }


class KillSwitch:
    """Global kill switch for emergency system shutdown.
    
    The kill switch provides an immediate mechanism to halt all operations
    in case of security breaches, runaway costs, or other emergencies.
    """
    
    _instance: Optional['KillSwitch'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self._state = KillSwitchState.ACTIVE
        self._triggered_at: Optional[str] = None
        self._reason: Optional[str] = None
        self._audit = AuditLogger()
        self._callbacks: List[Callable] = []
        self._initialized = True
        
    @property
    def state(self) -> KillSwitchState:
        """Current state of the kill switch."""
        return self._state
        
    @property
    def is_active(self) -> bool:
        """Check if system is in active (non-killed) state."""
        return self._state == KillSwitchState.ACTIVE
        
    def register_callback(self, callback: Callable) -> None:
        """Register a callback to be called when kill switch is triggered."""
        self._callbacks.append(callback)
        
    def trigger(self, reason: str, triggered_by: str = "system") -> bool:
        """Trigger the kill switch to shut down all operations.
        
        Args:
            reason: Reason for triggering the kill switch
            triggered_by: Who/what triggered the kill switch
            
        Returns:
            True if successfully triggered, False if already triggered
        """
        if self._state != KillSwitchState.ACTIVE:
            logger.warning(f"Kill switch already triggered: {self._state.value}")
            return False
            
        self._state = KillSwitchState.TRIGGERED
        self._triggered_at = datetime.utcnow().isoformat() + "Z"
        self._reason = reason
        
        # Log the kill switch trigger
        self._audit.log_event(
            event_type="KILLSWITCH",
            actor=triggered_by,
            resource="system",
            action="trigger",
            status="triggered",
            details={"reason": reason, "timestamp": self._triggered_at}
        )
        
        logger.critical(f"KILL SWITCH TRIGGERED: {reason}")
        logger.critical(f"Triggered at: {self._triggered_at}")
        logger.critical(f"Triggered by: {triggered_by}")
        
        # Execute all registered callbacks
        for callback in self._callbacks:
            try:
                callback(reason)
            except Exception as e:
                logger.error(f"Kill switch callback failed: {e}")
                
        return True
        
    def reset(self, reset_by: str = "system") -> bool:
        """Reset the kill switch to active state.
        
        WARNING: Only use this after resolving the issue that triggered
        the kill switch. Requires explicit authorization.
        
        Args:
            reset_by: Who is resetting the kill switch
            
        Returns:
            True if successfully reset
        """
        if self._state == KillSwitchState.ACTIVE:
            logger.warning("Kill switch already in active state")
            return False
            
        previous_state = self._state
        self._state = KillSwitchState.ACTIVE
        
        self._audit.log_event(
            event_type="KILLSWITCH",
            actor=reset_by,
            resource="system",
            action="reset",
            status="reset",
            details={
                "previous_state": previous_state.value,
                "previous_reason": self._reason
            }
        )
        
        logger.info(f"Kill switch reset by {reset_by}")
        
        # Clear trigger info
        self._triggered_at = None
        self._reason = None
        
        return True
        
    def get_status(self) -> Dict[str, Any]:
        """Get current kill switch status."""
        return {
            "state": self._state.value,
            "is_active": self.is_active,
            "triggered_at": self._triggered_at,
            "reason": self._reason,
            "pending_approvals": len(self._pending_approvals) if hasattr(self, '_pending_approvals') else 0
        }


class CostControlMonitor:
    """Monitors and controls API costs with automated safeguards.
    
    Features:
    - Real-time cost tracking
    - Budget threshold alerts
    - Automatic kill switch on budget exceeded
    - Daily/weekly/monthly reporting
    """
    
    # Alert thresholds (percentage of budget)
    ALERT_THRESHOLDS = {
        50: AlertLevel.INFO,
        75: AlertLevel.WARNING,
        90: AlertLevel.CRITICAL,
        100: AlertLevel.EMERGENCY
    }
    
    def __init__(self, daily_budget: float = 100.0, 
                 enable_killswitch: bool = True):
        self.cost_tracker = CostTracker(daily_budget=daily_budget)
        self._killswitch = KillSwitch() if enable_killswitch else None
        self._audit = AuditLogger()
        self._alerts: List[BudgetAlert] = []
        self._last_alert_level: Optional[AlertLevel] = None
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
    def start_monitoring(self, interval_seconds: int = 60) -> None:
        """Start the cost monitoring loop."""
        if self._monitoring:
            return
            
        self._monitoring = True
        
        def monitor_loop():
            while self._monitoring:
                self._check_budget_thresholds()
                time.sleep(interval_seconds)
                
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info(f"Cost monitoring started (interval: {interval_seconds}s)")
        
    def stop_monitoring(self) -> None:
        """Stop the cost monitoring loop."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Cost monitoring stopped")
        
    def _check_budget_thresholds(self) -> None:
        """Check if any budget thresholds have been crossed."""
        stats = self.cost_tracker.get_stats()
        percentage = stats["percentage_used"]
        
        # Find the highest crossed threshold
        current_level = None
        for threshold, level in sorted(self.ALERT_THRESHOLDS.items(), reverse=True):
            if percentage >= threshold:
                current_level = level
                break
                
        # Only alert if level changed
        if current_level and current_level != self._last_alert_level:
            self._last_alert_level = current_level
            self._send_alert(current_level, stats)
            
    def _send_alert(self, level: AlertLevel, stats: Dict) -> None:
        """Send a budget alert."""
        import uuid
        
        messages = {
            AlertLevel.INFO: f"Budget at {stats['percentage_used']:.1f}%",
            AlertLevel.WARNING: f"Budget at {stats['percentage_used']:.1f}% - Consider reducing usage",
            AlertLevel.CRITICAL: f"Budget at {stats['percentage_used']:.1f}% - Approaching limit!",
            AlertLevel.EMERGENCY: f"BUDGET EXCEEDED: {stats['percentage_used']:.1f}% - Operations halted!"
        }
        
        alert = BudgetAlert(
            alert_id=str(uuid.uuid4())[:12],
            level=level,
            message=messages[level],
            current_spend=stats["daily_spend"],
            budget_limit=stats["daily_budget"],
            percentage_used=stats["percentage_used"],
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        
        self._alerts.append(alert)
        
        # Log alert
        self._audit.log_event(
            event_type="BUDGET_ALERT",
            actor="cost_monitor",
            resource="budget",
            action="alert",
            status=level.value,
            details={
                "percentage": stats["percentage_used"],
                "spend": stats["daily_spend"],
                "alert_id": alert.alert_id
            }
        )
        
        # Trigger kill switch on emergency
        if level == AlertLevel.EMERGENCY and self._killswitch:
            self._killswitch.trigger(
                f"Budget exceeded: {stats['percentage_used']:.1f}%",
                triggered_by="cost_monitor"
            )
            
        logger.warning(f"BUDGET ALERT [{level.value.upper()}]: {alert.message}")
        
    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get all budget alerts."""
        return [alert.to_dict() for alert in self._alerts]
        
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge a budget alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                self._audit.log_event(
                    event_type="BUDGET_ALERT",
                    actor="admin",
                    resource=f"alert:{alert_id}",
                    action="acknowledge",
                    status="acknowledged"
                )
                return True
        return False


# Convenience functions
def get_killswitch() -> KillSwitch:
    """Get the global kill switch instance."""
    return KillSwitch()


def trigger_emergency_shutdown(reason: str) -> bool:
    """Trigger emergency shutdown via kill switch."""
    killswitch = get_killswitch()
    return killswitch.trigger(reason, triggered_by="manual_trigger")


def get_cost_monitor(daily_budget: float = 100.0) -> CostControlMonitor:
    """Get a cost control monitor instance."""
    return CostControlMonitor(daily_budget=daily_budget)


if __name__ == "__main__":
    # Self-test
    print("OpenPlexComputer Governance Framework")
    print("=" * 50)
    
    # Test kill switch
    print("\nKill Switch Test:")
    killswitch = get_killswitch()
    print(f"  Initial state: {killswitch.state.value}")
    print(f"  Is active: {killswitch.is_active}")
    
    # Trigger kill switch
    killswitch.trigger("Test emergency", "test_suite")
    print(f"  After trigger: {killswitch.state.value}")
    print(f"  Is active: {killswitch.is_active}")
    print(f"  Reason: {killswitch.get_status()['reason']}")
    
    # Reset kill switch
    killswitch.reset("test_suite")
    print(f"  After reset: {killswitch.state.value}")
    print(f"  Is active: {killswitch.is_active}")
    
    # Test cost control monitor
    print("\nCost Control Monitor Test:")
    monitor = get_cost_monitor(daily_budget=50.0)
    print(f"  Daily budget: $50.00")
    print(f"  Alert thresholds: 50%, 75%, 90%, 100%")
    
    # Simulate budget usage
    monitor.cost_tracker.record_usage("anthropic/claude-opus-4.6", 1000, 2000)
    stats = monitor.cost_tracker.get_stats()
    print(f"  After simulated usage: ${stats['daily_spend']:.2f}")
    print(f"  Remaining: ${stats['remaining']:.2f}")
    
    print("\n✓ Governance Framework test complete")
