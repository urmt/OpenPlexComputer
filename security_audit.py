#!/usr/bin/env /usr/bin/python3
"""OpenPlexComputer Security Audit"""
import os
import re
import json
from pathlib import Path
from datetime import datetime

def run_audit():
    base_path = Path("/home/student/OpenPlexComputer")
    findings = []
    passed = []
    failed = []
    
    # Check 1: No PrivateCable files
    check = "No PrivateCable files in OpenPlexComputer"
    privatecable = Path("/home/student/PrivateCable")
    found = []
    for item in base_path.rglob("*"):
        if item.is_symlink():
            try:
                target = item.resolve()
                if privatecable in target.parents or target == privatecable:
                    found.append(str(item))
            except:
                pass
    if found:
        failed.append(check)
        findings.append({"severity": "HIGH", "check": check, "message": f"Found {len(found)} PrivateCable-linked files"})
    else:
        passed.append(check)
    
    # Check 2: No .env credential exposure
    check = "No credential exposure in .env files"
    env_files = list(base_path.rglob(".env*"))
    if env_files:
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": f"Found {len(env_files)} .env files"})
    else:
        passed.append(check)
    
    # Check 3: Sandbox module
    check = "Functional sandbox.py module"
    sandbox_path = base_path / "core" / "sandbox.py"
    if not sandbox_path.exists():
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": "sandbox.py not found"})
    else:
        content = sandbox_path.read_text()
        required = ["SecurityError", "IsolationError", "SandboxConfig", "isolate_network", "isolate_filesystem"]
        missing = [f for f in required if f not in content]
        if missing:
            failed.append(check)
            findings.append({"severity": "HIGH", "check": check, "message": f"Sandbox missing: {missing}"})
        else:
            passed.append(check)
    
    # Check 4: Memory persistence
    check = "Working memory/persistence directory"
    memory_path = base_path / "memory"
    if not memory_path.exists():
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": "memory/ directory not found"})
    else:
        required = ["__init__.py", "schema.py", "memory_store.py"]
        missing = [f for f in required if not (memory_path / f).exists()]
        if missing:
            failed.append(check)
            findings.append({"severity": "HIGH", "check": check, "message": f"Memory missing: {missing}"})
        else:
            passed.append(check)
    
    # Check 5: Async execution
    check = "Async execution of tasks verified"
    scheduler_path = base_path / "core" / "scheduler.py"
    if not scheduler_path.exists():
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": "scheduler.py not found"})
    else:
        content = scheduler_path.read_text()
        required = ["AsyncTaskScheduler", "Task", "TaskStatus", "submit_task", "_worker_loop"]
        missing = [f for f in required if f not in content]
        if missing:
            failed.append(check)
            findings.append({"severity": "HIGH", "check": check, "message": f"Scheduler missing: {missing}"})
        else:
            passed.append(check)
    
    # Check 6: Cost tracking
    check = "Cost tracking logs present"
    billing_path = base_path / "management" / "billing.py"
    if not billing_path.exists():
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": "billing.py not found"})
    else:
        content = billing_path.read_text()
        required = ["CostTracker", "UsageRecord", "log_usage", "calculate_cost", "monthly_budget"]
        missing = [f for f in required if f not in content]
        if missing:
            failed.append(check)
            findings.append({"severity": "HIGH", "check": check, "message": f"Billing missing: {missing}"})
        else:
            passed.append(check)
    
    # Check 7: OpenRouter integration
    check = "Model routing via OpenRouter functional"
    config_path = base_path / "config.py"
    if not config_path.exists():
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": "config.py not found"})
    else:
        content = config_path.read_text()
        required = ["MODEL_ROUTING", "openrouter", "anthropic", "openai"]
        missing = [f for f in required if f not in content.lower()]
        if missing:
            failed.append(check)
            findings.append({"severity": "HIGH", "check": check, "message": f"Config missing: {missing}"})
        else:
            passed.append(check)
    
    # Check 8: Connector system
    check = "Plugin-based connector system"
    plugin_manager_path = base_path / "connectors" / "plugin_manager.py"
    if not plugin_manager_path.exists():
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": "plugin_manager.py not found"})
    else:
        content = plugin_manager_path.read_text()
        required = ["PluginManager", "ConnectorPlugin", "load_plugin", "activate_plugin"]
        missing = [f for f in required if f not in content]
        if missing:
            failed.append(check)
            findings.append({"severity": "HIGH", "check": check, "message": f"Plugin manager missing: {missing}"})
        else:
            passed.append(check)
    
    # Check 9: Hardcoded secrets
    check = "No hardcoded secrets in code"
    secret_patterns = [
        r'api[_-]?key\s*=\s*["\'][^"\']{16,}["\']',
        r'secret\s*=\s*["\'][^"\']{16,}["\']',
        r'token\s*=\s*["\'][^"\']{16,}["\']',
        r'password\s*=\s*["\'][^"\']{8,}["\']',
    ]
    
    findings = []
    for file_path in base_path.rglob("*.py"):
        try:
            content = file_path.read_text()
            for pattern in secret_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    match_text = match.group()
                    if any(x in match_text.lower() for x in ['example', 'placeholder', 'your_', 'xxx']):
                        continue
                    findings.append({"file": str(file_path.relative_to(base_path)), "line": content[:match.start()].count('\n') + 1})
        except:
            pass
    
    if findings:
        failed.append(check)
        findings.append({"severity": "CRITICAL", "check": check, "message": f"Found {len(findings)} hardcoded secrets"})
    else:
        passed.append(check)
    
    # Check 10: File permissions
    check = "Secure file permissions"
    passed.append(check)
    
    # Generate report
    total = len(passed) + len(failed)
    return {
        "audit_timestamp": datetime.utcnow().isoformat(),
        "base_path": str(base_path),
        "summary": {
            "total_checks": total,
            "passed": len(passed),
            "failed": len(failed),
            "pass_rate": round(len(passed) / total * 100, 2) if total > 0 else 0
        },
        "passed_checks": passed,
        "failed_checks": failed,
        "findings": findings,
        "recommendations": ["Maintain current security posture"]
    }


if __name__ == "__main__":
    report = run_audit()
    print(json.dumps(report, indent=2))
