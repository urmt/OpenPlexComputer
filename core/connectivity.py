"""OpenPlexComputer - Connectivity Layer: Multi-Tool Coordination

Coordinates with external tools (GitHub, Slack, etc.) with mandatory
approval workflows and comprehensive audit trails.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

sys.path.insert(0, str(Path(__file__).parent))
from sandbox import get_vault, SecureVault, AuditLogger

logger = logging.getLogger("openplex.connectivity")


class ActionType(Enum):
    """Types of actions requiring approval."""
    GITHUB_READ = "github_read"
    GITHUB_WRITE = "github_write"
    GITHUB_DELETE = "github_delete"
    SLACK_SEND = "slack_send"
    SLACK_READ = "slack_read"
    EMAIL_SEND = "email_send"
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    API_CALL = "api_call"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"


class ApprovalStatus(Enum):
    """Status of approval requests."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class ApprovalRequest:
    """Represents an approval request for a sensitive action."""
    request_id: str
    action_type: ActionType
    resource: str
    description: str
    requester: str
    timestamp: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: Optional[str] = None
    approval_timestamp: Optional[str] = None
    denial_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_type": self.action_type.value,
            "resource": self.resource,
            "description": self.description,
            "requester": self.requester,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "approver": self.approver,
            "approval_timestamp": self.approval_timestamp,
            "denial_reason": self.denial_reason,
            "metadata": self.metadata
        }


class ApprovalWorkflow:
    """Manages approval workflows for sensitive actions."""
    
    SENSITIVE_ACTIONS: Set[ActionType] = {
        ActionType.GITHUB_WRITE,
        ActionType.GITHUB_DELETE,
        ActionType.SLACK_SEND,
        ActionType.EMAIL_SEND,
        ActionType.DATABASE_WRITE,
        ActionType.FILE_UPLOAD,
        ActionType.FILE_DOWNLOAD,
    }
    
    def __init__(self, auto_approve: bool = False):
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._approved_actions: Dict[str, ApprovalRequest] = {}
        self._audit = AuditLogger()
        self._auto_approve = auto_approve
        self._lock = threading.Lock()
        
    def requires_approval(self, action_type: ActionType) -> bool:
        """Check if an action type requires approval."""
        return action_type in self.SENSITIVE_ACTIONS
        
    def request_approval(self, action_type: ActionType, resource: str,
                        description: str, requester: str = "system",
                        metadata: Optional[Dict] = None) -> str:
        """Request approval for a sensitive action."""
        import uuid
        
        request_id = str(uuid.uuid4())[:12]
        
        request = ApprovalRequest(
            request_id=request_id,
            action_type=action_type,
            resource=resource,
            description=description,
            requester=requester,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata=metadata or {}
        )
        
        with self._lock:
            self._pending_approvals[request_id] = request
            
        self._audit.log_event(
            event_type="APPROVAL",
            actor=requester,
            resource=f"action:{action_type.value}",
            action="request",
            status="pending",
            details={"request_id": request_id, "resource": resource}
        )
        
        logger.info(f"Approval requested: {request_id} for {action_type.value} on {resource}")
        
        if self._auto_approve:
            self.approve_request(request_id, "auto_approver")
            
        return request_id
        
    def approve_request(self, request_id: str, approver: str) -> bool:
        """Approve a pending request."""
        with self._lock:
            if request_id not in self._pending_approvals:
                return False
                
            request = self._pending_approvals[request_id]
            request.status = ApprovalStatus.APPROVED
            request.approver = approver
            request.approval_timestamp = datetime.utcnow().isoformat() + "Z"
            
            self._approved_actions[request_id] = request
            del self._pending_approvals[request_id]
            
        self._audit.log_event(
            event_type="APPROVAL",
            actor=approver,
            resource=f"request:{request_id}",
            action="approve",
            status="success"
        )
        
        logger.info(f"Request approved: {request_id} by {approver}")
        return True
        
    def deny_request(self, request_id: str, approver: str, reason: str) -> bool:
        """Deny a pending request."""
        with self._lock:
            if request_id not in self._pending_approvals:
                return False
                
            request = self._pending_approvals[request_id]
            request.status = ApprovalStatus.DENIED
            request.approver = approver
            request.denial_reason = reason
            
            del self._pending_approvals[request_id]
            
        self._audit.log_event(
            event_type="APPROVAL",
            actor=approver,
            resource=f"request:{request_id}",
            action="deny",
            status="denied",
            details={"reason": reason}
        )
        
        logger.info(f"Request denied: {request_id} by {approver}: {reason}")
        return True
        
    def is_approved(self, request_id: str) -> bool:
        """Check if a request has been approved."""
        with self._lock:
            return request_id in self._approved_actions
            
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """Get all pending approval requests."""
        with self._lock:
            return [req.to_dict() for req in self._pending_approvals.values()]
            
    def get_approved_requests(self) -> List[Dict[str, Any]]:
        """Get all approved requests."""
        with self._lock:
            return [req.to_dict() for req in self._approved_actions.values()]


# Convenience functions
def request_action_approval(action_type: str, resource: str, description: str) -> str:
    """Request approval for a sensitive action."""
    workflow = ApprovalWorkflow()
    return workflow.request_approval(
        ActionType(action_type),
        resource,
        description,
        requester="system"
    )


if __name__ == "__main__":
    # Self-test
    print("OpenPlexComputer Connectivity Layer")
    print("=" * 50)
    
    # Test approval workflow
    print("\nApproval Workflow Test:")
    workflow = ApprovalWorkflow()
    
    # Test that sensitive actions require approval
    print("  Sensitive actions requiring approval:")
    for action in ApprovalWorkflow.SENSITIVE_ACTIONS:
        print(f"    - {action.value}")
    
    # Test approval request
    request_id = workflow.request_approval(
        ActionType.GITHUB_WRITE,
        "repo:openplex/main",
        "Push changes to main branch",
        requester="developer"
    )
    print(f"\n  Created approval request: {request_id}")
    print(f"  Pending requests: {len(workflow.get_pending_requests())}")
    
    # Test approval
    workflow.approve_request(request_id, "admin")
    print(f"  Approved request: {request_id}")
    print(f"  Is approved: {workflow.is_approved(request_id)}")
    print(f"  Pending requests: {len(workflow.get_pending_requests())}")
    
    # Test denial
    request_id2 = workflow.request_approval(
        ActionType.SLACK_SEND,
        "channel:general",
        "Send message to general channel",
        requester="bot"
    )
    workflow.deny_request(request_id2, "admin", "Unauthorized channel")
    print(f"\n  Denied request: {request_id2}")
    
    print("\n✓ Connectivity Layer test complete")
