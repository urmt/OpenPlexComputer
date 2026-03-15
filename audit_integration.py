"""OpenPlexComputer - Integration Audit Script"""
import os
import sys
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("/home/student/OpenPlexComputer")

class IntegrationAuditor:
    def __init__(self):
        self.findings = []
        self.passed = 0
        self.failed = 0
        
    def log(self, check, status, details=""):
        self.findings.append({"check": check, "status": status, "details": details})
        if status == "PASS":
            self.passed += 1
            print(f"  OK {check}")
        else:
            self.failed += 1
            print(f"  FAIL {check}: {details}")
            
    def audit_creds(self):
        print("\n[CREDENTIAL AUDIT]")
        patterns = [r'sk-or-v1-\w+', r'ghp_\w+', r'xoxb-\w+']
        for f in PROJECT_ROOT.rglob("*.py"):
            try:
                content = f.read_text()
                for p in patterns:
                    if re.search(p, content):
                        self.log("Credential Check", "FAIL", f"Found in {f}")
                        return False
            except: pass
        env_files = list(PROJECT_ROOT.rglob(".env"))
        if env_files:
            self.log("Credential Check", "FAIL", f".env files found")
            return False
        self.log("Credential Check", "PASS", "No exposed credentials")
        return True
        
    def audit_isolation(self):
        print("\n[ISOLATION AUDIT]")
        sandbox = PROJECT_ROOT / "core" / "sandbox.py"
        if not sandbox.exists():
            self.log("Sandbox", "FAIL", "Missing")
            return False
        content = sandbox.read_text()
        checks = [
            ("PrivateCable Isolation", "PrivateCable" in content),
            ("Vault Storage", "SecureVault" in content),
            (".env Blocking", ".env" in content)
        ]
        passed = 0
        for name, result in checks:
            if result:
                self.log(name, "PASS", "OK")
                passed += 1
            else:
                self.log(name, "FAIL", "Missing")
        return passed >= 2
        
    def audit_git(self):
        print("\n[GIT AUDIT]")
        git_dir = PROJECT_ROOT / ".git"
        if not git_dir.exists():
            self.log("Git Repository", "FAIL", ".git not found")
            return False
        try:
            result = subprocess.run(["git", "-C", str(PROJECT_ROOT), "status", "--short"],
                capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.log("Git Repository", "PASS", "Active")
                return True
        except: pass
        self.log("Git Repository", "FAIL", "Git error")
        return False
        
    def audit_modules(self):
        print("\n[MODULE AUDIT]")
        sys.path.insert(0, str(PROJECT_ROOT))
        modules = [
            ("core.sandbox", "SecureVault"),
            ("core.orchestrator", "ModelRouter"),
            ("core.governance", "KillSwitch"),
            ("connectors.github_connector", "GitHubConnector"),
            ("connectors.slack_connector", "SlackConnector"),
        ]
        passed = 0
        for mod, cls in modules:
            try:
                module = __import__(mod, fromlist=[cls])
                getattr(module, cls)
                self.log(f"Import {mod}.{cls}", "PASS", "OK")
                passed += 1
            except Exception as e:
                self.log(f"Import {mod}.{cls}", "FAIL", str(e)[:40])
        return passed >= len(modules) - 1

def main():
    print("=" * 70)
    print("OpenPlexComputer - Integration Security Audit")
    print("=" * 70)
    
    auditor = IntegrationAuditor()
    
    cred = auditor.audit_creds()
    iso = auditor.audit_isolation()
    git = auditor.audit_git()
    mod = auditor.audit_modules()
    
    print("\n" + "=" * 70)
    print(f"Total: {auditor.passed + auditor.failed}, Passed: {auditor.passed}, Failed: {auditor.failed}")
    all_pass = cred and iso and git and mod
    print("PASS" if all_pass else "FAIL")
    print("=" * 70)
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
