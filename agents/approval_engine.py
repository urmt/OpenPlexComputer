"""OpenPlexComputer Approval Engine - Mandatory human-in-the-loop for high-risk actions"""
import json
import logging
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    SAFE = 1
    SENSITIVE = 2
    CRITICAL = 3

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

@dataclass
class ApprovalRequest:
    request_id: str
    task_id: str
    action: str
    action_params: Dict[str, Any]
    risk_level: RiskLevel
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    audit_log: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "action": self.action,
            "risk_level": self.risk_level.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "audit_log": self.audit_log,
        }

class ApprovalEngine:
    """Mandatory approval workflow for sensitive actions"""
    
    REQUIRE_APPROVAL = {
        "delete": RiskLevel.CRITICAL,
        "send_email": RiskLevel.SENSITIVE,
        "git_push": RiskLevel.SENSITIVE,
        "execute_code": RiskLevel.CRITICAL,
        "file_write": RiskLevel.SAFE,
        "database_write": RiskLevel.SENSITIVE,
        "api_call_external": RiskLevel.SENSITIVE,
        "payment": RiskLevel.CRITICAL,
    }
    
    def __init__(self, auto_approve_safe: bool = True, approval_timeout_seconds: int = 300):
        self.auto_approve_safe = auto_approve_safe
        self.approval_timeout_seconds = approval_timeout_seconds
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_expirations, daemon=True)
        self._monitor_thread.start()
        logger.info("ApprovalEngine initialized")
        
    def _monitor_expirations(self):
        import time
        while self._running:
            with self._lock:
                now = datetime.now()
                for req_id, request in list(self._pending_requests.items()):
                    if request.status == ApprovalStatus.PENDING and now > request.expires_at:
                        request.status = ApprovalStatus.EXPIRED
                        request.audit_log.append(f"Expired at {now.isoformat()}")
            time.sleep(5)
            
    def check_action(self, action: str, params: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        risk_level = self.REQUIRE_APPROVAL.get(action, RiskLevel.SAFE)
        
        if risk_level == RiskLevel.SAFE and self.auto_approve_safe:
            return {"approved": True, "auto_approved": True, "risk_level": risk_level.name, "request_id": None}
            
        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            task_id=task_id,
            action=action,
            action_params=params,
            risk_level=risk_level,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.approval_timeout_seconds),
            audit_log=[f"Created at {datetime.now().isoformat()}"],
        )
        
        with self._lock:
            self._pending_requests[request.request_id] = request
            
        logger.info(f"Approval required for {action} (risk: {risk_level.name}, request: {request.request_id})")
        
        return {
            "approved": False,
            "auto_approved": False,
            "risk_level": risk_level.name,
            "request_id": request.request_id,
            "requires_approval": True,
            "expires_at": request.expires_at.isoformat(),
        }
        
    def approve_request(self, request_id: str, approved_by: str) -> bool:
        with self._lock:
            request = self._pending_requests.get(request_id)
            if not request or request.status != ApprovalStatus.PENDING:
                return False
            request.status = ApprovalStatus.APPROVED
            request.audit_log.append(f"Approved by {approved_by} at {datetime.now().isoformat()}")
        logger.info(f"Request {request_id} approved by {approved_by}")
        return True
        
    def reject_request(self, request_id: str, rejected_by: str, reason: str) -> bool:
        with self._lock:
            request = self._pending_requests.get(request_id)
            if not request or request.status != ApprovalStatus.PENDING:
                return False
            request.status = ApprovalStatus.REJECTED
            request.audit_log.append(f"Rejected by {rejected_by}: {reason}")
        logger.info(f"Request {request_id} rejected by {rejected_by}: {reason}")
        return True
        
    def get_pending_requests(self) -> List[Dict]:
        with self._lock:
            return [req.to_dict() for req in self._pending_requests.values() if req.status == ApprovalStatus.PENDING]

_approval_engine: Optional[ApprovalEngine] = None

def get_approval_engine() -> ApprovalEngine:
    global _approval_engine
    if _approval_engine is None:
        _approval_engine = ApprovalEngine()
    return _approval_engine
