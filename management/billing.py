"""Billing Module."""
import sqlite3, json, os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

@dataclass
class UsageRecord:
    record_id: str
    session_id: str
    agent_id: str
    model_id: str
    provider: str
    request_type: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class CostTracker:
    DEFAULT_PRICING = {
        "anthropic/claude-opus-4.6": {"input": 15.00, "output": 75.00},
        "openai/o3": {"input": 10.00, "output": 40.00},
        "deepseek/r1": {"input": 0.55, "output": 2.19},
    }
    
    def __init__(self, db_path=None, monthly_budget=200.0):
        self.db_path = db_path or os.path.expanduser("~/.openplex/billing.db")
        self.monthly_budget = monthly_budget
        self.pricing = self.DEFAULT_PRICING.copy()
        self._init_database()
    
    def _init_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_records (
                record_id TEXT PRIMARY KEY, session_id TEXT, agent_id TEXT,
                model_id TEXT, provider TEXT, request_type TEXT,
                input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, created_at TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def calculate_cost(self, model_id, input_tokens, output_tokens):
        pricing = self.pricing.get(model_id, {"input": 0.0, "output": 0.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)
    
    def log_usage(self, record):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO usage_records (record_id, session_id, agent_id, model_id, provider,
            request_type, input_tokens, output_tokens, cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (record.record_id, record.session_id, record.agent_id, record.model_id,
              record.provider, record.request_type, record.input_tokens, record.output_tokens,
              record.cost_usd, record.created_at))
        conn.commit()
        conn.close()
        return True

class BillingManager:
    def __init__(self, cost_tracker=None):
        self.cost_tracker = cost_tracker or CostTracker()
    
    def estimate_cost(self, model_id, input_tokens, output_tokens):
        cost = self.cost_tracker.calculate_cost(model_id, input_tokens, output_tokens)
        return {"model_id": model_id, "estimated_cost_usd": cost}
    
    def get_monthly_report(self):
        return {"period": "2024-03", "total_cost": 0.0, "budget_remaining": 200.0}
