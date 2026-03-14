"""OpenPlexComputer Configuration - Multi-tier model routing with cost optimization"""
import os
from enum import Enum

class RiskLevel(Enum):
    SAFE = 1
    SENSITIVE = 2
    CRITICAL = 3

MODEL_ROUTING = {
    "orchestration": [("anthropic/claude-opus-4.6", 0.40), ("openai/o3", 0.30), ("google/gemini-2.0-flash-thinking", 0.20), ("deepseek/r1", 0.10)],
    "coding": [("openai/gpt-5.3-codex", 0.50), ("anthropic/claude-sonnet-4.6", 0.30), ("qwen/qwen-2.5-coder-32b", 0.20)],
    "research": [("google/gemini-3.1-pro", 0.40), ("perplexity/sonar-pro", 0.40), ("anthropic/claude-sonnet-4.6", 0.20)],
    "fast": [("x-ai/grok-3", 0.40), ("openai/gpt-5.1-mini", 0.30), ("google/gemini-3.0-flash", 0.30)],
    "image": [("google/imagen-4", 0.40), ("black-forest-labs/flux-1.1-pro", 0.30), ("openai/dall-e-4", 0.20), ("stability-ai/sd-3.5-large", 0.10)],
    "video": [("google/veo-3.1", 0.50), ("runway/gen-4", 0.30), ("openai/sora-2-pro", 0.20)],
    "local": [("local/deepseek-r1-distill-70b", 0.40), ("local/qwen-2.5-coder-32b", 0.30), ("local/llama-3.3-70b", 0.20), ("local/llava-v1.7-34b", 0.10)],
}

MODEL_COSTS = {
    "anthropic/claude-opus-4.6": {"input": 15.00, "output": 75.00},
    "openai/o3": {"input": 10.00, "output": 40.00},
    "google/gemini-2.0-flash-thinking": {"input": 3.50, "output": 10.50},
    "deepseek/r1": {"input": 0.55, "output": 2.19},
    "openai/gpt-5.3-codex": {"input": 10.00, "output": 30.00},
    "anthropic/claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "qwen/qwen-2.5-coder-32b": {"input": 0.90, "output": 0.90},
    "google/gemini-3.1-pro": {"input": 5.00, "output": 15.00},
    "perplexity/sonar-pro": {"input": 3.00, "output": 10.00},
    "x-ai/grok-3": {"input": 5.00, "output": 15.00},
    "openai/gpt-5.1-mini": {"input": 0.15, "output": 0.60},
    "google/gemini-3.0-flash": {"input": 0.15, "output": 0.60},
    "local/deepseek-r1-distill-70b": {"input": 0.0, "output": 0.0},
    "local/qwen-2.5-coder-32b": {"input": 0.0, "output": 0.0},
    "local/llama-3.3-70b": {"input": 0.0, "output": 0.0},
    "local/llava-v1.7-34b": {"input": 0.0, "output": 0.0},
}

APPROVAL_CONFIG = {
    "REQUIRE_APPROVAL": {
        "delete": RiskLevel.CRITICAL,
        "send_email": RiskLevel.SENSITIVE,
        "git_push": RiskLevel.SENSITIVE,
        "execute_code": RiskLevel.CRITICAL,
        "file_write": RiskLevel.SAFE,
        "database_write": RiskLevel.SENSITIVE,
        "api_call_external": RiskLevel.SENSITIVE,
        "payment": RiskLevel.CRITICAL,
        "user_data_access": RiskLevel.SENSITIVE,
    },
    "AUTO_APPROVE_SAFE": True,
    "NOTIFICATION_CHANNELS": ["ui", "email", "slack"],
    "APPROVAL_TIMEOUT_SECONDS": 300,
}

SANDBOX_CONFIG = {
    "vcpu_count": 2,
    "mem_size_mib": 8192,
    "disk_size_gb": 20,
    "boot_timeout_ms": 125,
    "max_task_duration_minutes": 60,
    "auto_destroy_on_complete": True,
    "network_isolation": True,
}

VAULT_CONFIG = {
    "provider": "hashicorp",
    "address": os.getenv("VAULT_ADDR", "http://localhost:8200"),
    "token_path": os.getenv("VAULT_TOKEN_PATH", "/etc/vault/token"),
    "encryption": "aes-256-gcm",
    "key_rotation_days": 90,
}

MCP_CONFIG = {
    "protocol_version": "1.0",
    "registry_url": "https://registry.modelcontext.io",
    "supported_connectors": 400,
    "timeout_seconds": 30,
    "retry_attempts": 3,
    "batch_size": 100,
}

LOCAL_MODE_CONFIG = {
    "enabled": True,
    "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    "lm_studio_host": os.getenv("LM_STUDIO_HOST", "http://localhost:1234"),
    "default_local_model": "llama-3.3-70b",
    "fallback_to_cloud": True,
    "max_local_tokens": 8192,
}

HYBRID_CONFIG = {
    "enabled": True,
    "privacy_classifier_model": "local/privacy-classifier",
    "sensitivity_threshold": 0.7,
    "auto_route_sensitive_to_local": True,
    "pii_patterns": [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    ],
}

COST_GOVERNOR_CONFIG = {
    "enabled": True,
    "monthly_budget_usd": float(os.getenv("MONTHLY_BUDGET", "200")),
    "credit_balance": 10000,
    "auto_refill": False,
    "hard_cap": True,
    "alert_threshold_percent": 80,
    "per_task_estimate": True,
}

AUDIT_CONFIG = {
    "enabled": True,
    "log_level": "INFO",
    "storage_backend": "sqlite",
    "retention_days": 365,
    "encrypt_logs": True,
    "include_stack_trace": True,
    "sensitive_fields_masked": ["password", "token", "api_key", "secret"],
}

SKILLS_CONFIG = {
    "enabled": True,
    "storage_path": "./data/skills",
    "max_skills_per_user": 100,
    "community_sharing": True,
    "federated_learning": True,
    "differential_privacy_epsilon": 1.0,
}

PROACTIVE_CONFIG = {
    "enabled": True,
    "check_interval_seconds": 60,
    "max_triggers": 100,
    "supported_trigger_types": [
        "time_based",
        "event_based",
        "condition_based",
        "file_based",
        "api_based",
    ],
}

KILL_SWITCH_CONFIG = {
    "enabled": True,
    "emergency_contact": os.getenv("EMERGENCY_CONTACT"),
    "auto_shutdown_triggers": [
        "credential_exposure_detected",
        "unauthorized_access_attempt",
        "budget_exceeded_500_percent",
        "sandbox_escape_attempt",
    ],
}


def get_config():
    """Return complete configuration dictionary"""
    return {
        "models": MODEL_ROUTING,
        "costs": MODEL_COSTS,
        "approval": APPROVAL_CONFIG,
        "sandbox": SANDBOX_CONFIG,
        "vault": VAULT_CONFIG,
        "mcp": MCP_CONFIG,
        "local": LOCAL_MODE_CONFIG,
        "hybrid": HYBRID_CONFIG,
        "cost_governor": COST_GOVERNOR_CONFIG,
        "audit": AUDIT_CONFIG,
        "skills": SKILLS_CONFIG,
        "proactive": PROACTIVE_CONFIG,
        "kill_switch": KILL_SWITCH_CONFIG,
    }
