"""OpenPlexComputer Cost Governor - Credit system with spending controls"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"

@dataclass
class TaskCost:
    task_id: str
    model: str
    estimated_cost_usd: float
    estimated_credits: float
    actual_cost_usd: float = 0.0
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)

class CostGovernor:
    """Credit system with spending controls"""
    
    def __init__(self, monthly_budget_usd: float = 200.0, credit_balance: float = 10000.0):
        self.monthly_budget_usd = monthly_budget_usd
        self.credit_balance = credit_balance
        self.spent_usd = 0.0
        self._task_costs: Dict[str, TaskCost] = {}
        self._lock = threading.RLock()
        self.model_costs = self._load_model_costs()
        logger.info(f"CostGovernor initialized: ${monthly_budget_usd}/month, {credit_balance} credits")
        
    def _load_model_costs(self) -> Dict[str, Dict[str, float]]:
        try:
            from config import MODEL_COSTS
            return MODEL_COSTS
        except ImportError:
            return {"default": {"input": 5.00, "output": 15.00}}
            
    def estimate_task_cost(self, task_type: str, model: str, estimated_input_tokens: int = 1000, estimated_output_tokens: int = 500) -> TaskCost:
        """Estimate cost before task execution"""
        pricing = self.model_costs.get(model, self.model_costs.get("default"))
        input_cost = (estimated_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        credits = total_cost * 100
        
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task_cost = TaskCost(task_id=task_id, model=model, estimated_cost_usd=total_cost, estimated_credits=credits)
        
        with self._lock:
            self._task_costs[task_id] = task_cost
            
        logger.info(f"Task {task_id} estimated cost: ${total_cost:.4f} ({credits:.2f} credits)")
        return task_cost
        
    def approve_spend(self, task_cost: TaskCost) -> Tuple[str, str]:
        """Check budget before allowing task execution"""
        cost = task_cost.estimated_cost_usd
        credits = task_cost.estimated_credits
        
        with self._lock:
            if self.credit_balance < credits:
                task_cost.status = TaskStatus.PAUSED
                return "PAUSE", f"Insufficient credits ({self.credit_balance:.2f} < {credits:.2f})"
                
            projected_spend = self.spent_usd + cost
            if projected_spend > self.monthly_budget_usd:
                task_cost.status = TaskStatus.BLOCKED
                return "BLOCK", f"Monthly budget exceeded (${projected_spend:.2f} > ${self.monthly_budget_usd:.2f})"
                
            task_cost.status = TaskStatus.APPROVED
            self.credit_balance -= credits
            self.spent_usd += cost
                
        logger.info(f"Task {task_cost.task_id} APPROVED: ${cost:.4f} ({credits:.2f} credits)")
        return "APPROVE", f"Approved. Remaining credits: {self.credit_balance:.2f}"
        
    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status"""
        with self._lock:
            return {
                "monthly_budget_usd": self.monthly_budget_usd,
                "spent_usd": round(self.spent_usd, 4),
                "credit_balance": round(self.credit_balance, 2),
                "utilization_percent": round((self.spent_usd / self.monthly_budget_usd) * 100, 2) if self.monthly_budget_usd > 0 else 0,
            }

_cost_governor: Optional[CostGovernor] = None

def get_cost_governor() -> CostGovernor:
    global _cost_governor
    if _cost_governor is None:
        _cost_governor = CostGovernor()
    return _cost_governor
