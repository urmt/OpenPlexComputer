"""OpenPlexComputer - GitHub Connector"""
import requests
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from sandbox import get_vault, AuditLogger
from connectivity import ApprovalWorkflow, ActionType

class GitHubConnector:
    """GitHub connector with approval workflow."""
    
    def __init__(self):
        self.vault = get_vault()
        self._audit = AuditLogger()
        self._approval = ApprovalWorkflow()
        self._session = None
        self._status = "disconnected"
        
    def authenticate(self):
        token = self.vault.retrieve("github_token", requester="github_connector")
        if not token:
            return False
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        })
        self._status = "connected"
        return True
        
    def execute(self, action, params):
        action_type = ActionType.GITHUB_WRITE if "write" in action else ActionType.GITHUB_READ
        if self._approval.requires_approval(action_type):
            return {"status": "approval_required", "action": action}
        return {"status": "success", "action": action}
        
    def health_check(self):
        return {"status": "healthy" if self._status == "connected" else "disconnected"}
