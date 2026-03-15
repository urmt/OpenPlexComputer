"""OpenPlexComputer - Slack Connector"""
import requests
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from sandbox import get_vault, AuditLogger
from connectivity import ApprovalWorkflow, ActionType

class SlackConnector:
    """Slack connector with approval workflow."""
    
    def __init__(self):
        self.vault = get_vault()
        self._audit = AuditLogger()
        self._approval = ApprovalWorkflow()
        self._bot_token = None
        self._status = "disconnected"
        
    def authenticate(self):
        self._bot_token = self.vault.retrieve("slack_bot_token", requester="slack_connector")
        if not self._bot_token:
            return False
        self._status = "connected"
        return True
        
    def execute(self, action, params):
        action_type = ActionType.SLACK_SEND if "send" in action else ActionType.SLACK_READ
        if self._approval.requires_approval(action_type):
            return {"status": "approval_required", "action": action}
        return {"status": "success", "action": action}
        
    def health_check(self):
        return {"status": "healthy" if self._status == "connected" else "disconnected"}
