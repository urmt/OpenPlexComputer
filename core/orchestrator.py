"""OpenPlexComputer - Orchestration Engine: Multi-Model Router

Routes tasks between frontier models (Claude Opus 4.6, GPT-5 series, Gemini)
based on task complexity and type, using OpenRouter for unified API access.
"""

import os
import sys
import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

sys.path.insert(0, str(Path(__file__).parent))
from sandbox import get_vault, SecureVault, AuditLogger

logger = logging.getLogger("openplex.orchestrator")


class TaskType(Enum):
    """Classification of task types for model routing."""
    ORCHESTRATION = "orchestration"
    CODING = "coding"
    RESEARCH = "research"
    FAST = "fast"
    IMAGE = "image"
    VIDEO = "video"
    LOCAL = "local"


class ModelTier(Enum):
    """Model capability tiers for cost/quality tradeoffs."""
    FRONTIER = "frontier"
    PREMIUM = "premium"
    STANDARD = "standard"
    ECONOMY = "economy"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    model_id: str
    provider: str
    task_types: List[TaskType]
    tier: ModelTier
    cost_input_per_1k: float
    cost_output_per_1k: float
    context_window: int
    supports_streaming: bool = True
    supports_tools: bool = False
    fallback_models: List[str] = field(default_factory=list)


# Model routing configuration based on task type
MODEL_ROUTING_TABLE: Dict[TaskType, List[Tuple[str, float]]] = {
    TaskType.ORCHESTRATION: [
        ("anthropic/claude-opus-4.6", 0.40),
        ("openai/o3", 0.30),
        ("google/gemini-2.0-flash-thinking", 0.20),
        ("deepseek/r1", 0.10),
    ],
    TaskType.CODING: [
        ("openai/gpt-5.3-codex", 0.50),
        ("anthropic/claude-sonnet-4.6", 0.30),
        ("qwen/qwen-2.5-coder-32b", 0.20),
    ],
    TaskType.RESEARCH: [
        ("google/gemini-3.1-pro", 0.40),
        ("perplexity/sonar-pro", 0.40),
        ("anthropic/claude-sonnet-4.6", 0.20),
    ],
    TaskType.FAST: [
        ("x-ai/grok-3", 0.40),
        ("openai/gpt-5.1-mini", 0.30),
        ("google/gemini-3.0-flash", 0.30),
    ],
    TaskType.IMAGE: [
        ("google/imagen-4", 0.40),
        ("black-forest-labs/flux-1.1-pro", 0.30),
        ("openai/dall-e-4", 0.20),
        ("stability-ai/sd-3.5-large", 0.10),
    ],
    TaskType.VIDEO: [
        ("google/veo-3.1", 0.50),
        ("runway/gen-4", 0.30),
        ("openai/sora-2-pro", 0.20),
    ],
    TaskType.LOCAL: [
        ("local/deepseek-r1-distill-70b", 0.40),
        ("local/qwen-2.5-coder-32b", 0.30),
        ("local/llama-3.3-70b", 0.20),
        ("local/llava-v1.7-34b", 0.10),
    ],
}

# Cost per 1K tokens (input, output)
MODEL_COSTS: Dict[str, Tuple[float, float]] = {
    "anthropic/claude-opus-4.6": (15.00, 75.00),
    "openai/o3": (10.00, 40.00),
    "google/gemini-2.0-flash-thinking": (3.50, 10.50),
    "deepseek/r1": (0.55, 2.19),
    "openai/gpt-5.3-codex": (10.00, 30.00),
    "anthropic/claude-sonnet-4.6": (3.00, 15.00),
    "qwen/qwen-2.5-coder-32b": (0.90, 0.90),
    "google/gemini-3.1-pro": (5.00, 15.00),
    "perplexity/sonar-pro": (3.00, 10.00),
    "x-ai/grok-3": (5.00, 15.00),
    "openai/gpt-5.1-mini": (1.00, 3.00),
    "google/gemini-3.0-flash": (0.50, 1.50),
    "google/imagen-4": (5.00, 15.00),
    "black-forest-labs/flux-1.1-pro": (2.00, 6.00),
    "openai/dall-e-4": (5.00, 15.00),
    "stability-ai/sd-3.5-large": (1.00, 3.00),
    "google/veo-3.1": (10.00, 30.00),
    "runway/gen-4": (5.00, 15.00),
    "openai/sora-2-pro": (10.00, 30.00),
    "local/deepseek-r1-distill-70b": (0.00, 0.00),
    "local/qwen-2.5-coder-32b": (0.00, 0.00),
    "local/llama-3.3-70b": (0.00, 0.00),
    "local/llava-v1.7-34b": (0.00, 0.00),
}


@dataclass
class CostTracker:
    """Tracks API costs and enforces budget limits."""
    daily_budget_usd: float = 100.0
    _daily_spend: float = field(default=0.0)
    _request_count: int = field(default=0)
    _token_count: int = field(default=0)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def can_execute(self, estimated_cost: float = 0.0) -> bool:
        """Check if execution is within budget."""
        with self._lock:
            return (self._daily_spend + estimated_cost) <= self.daily_budget_usd
            
    def record_usage(self, model: str, input_tokens: int, output_tokens: int) -> Dict:
        """Record token usage and calculate cost."""
        with self._lock:
            if model in MODEL_COSTS:
                input_cost = (input_tokens / 1000) * MODEL_COSTS[model][0]
                output_cost = (output_tokens / 1000) * MODEL_COSTS[model][1]
                total_cost = input_cost + output_cost
            else:
                total_cost = 0.0
                
            self._daily_spend += total_cost
            self._request_count += 1
            self._token_count += input_tokens + output_tokens
            
            return {
                "cost_usd": total_cost,
                "daily_total": self._daily_spend,
                "budget_remaining": self.daily_budget_usd - self._daily_spend,
                "percentage_used": (self._daily_spend / self.daily_budget_usd) * 100
            }
            
    def get_stats(self) -> Dict:
        """Get current cost tracking statistics."""
        with self._lock:
            return {
                "daily_budget": self.daily_budget_usd,
                "daily_spend": self._daily_spend,
                "remaining": self.daily_budget_usd - self._daily_spend,
                "percentage_used": (self._daily_spend / self.daily_budget_usd) * 100,
                "request_count": self._request_count,
                "total_tokens": self._token_count
            }


class ModelRouter:
    """Routes tasks to appropriate models based on task classification."""
    
    def __init__(self, vault: Optional[SecureVault] = None):
        self.vault = vault or get_vault()
        self.cost_tracker = CostTracker()
        self._audit = AuditLogger()
        
    def classify_task(self, prompt: str) -> TaskType:
        """Classify a task to determine the appropriate model type."""
        prompt_lower = prompt.lower()
        
        # Image generation keywords
        image_keywords = ['image', 'picture', 'photo', 'generate image', 'draw', 'create image', 
                         'illustration', 'artwork', 'render']
        if any(kw in prompt_lower for kw in image_keywords):
            return TaskType.IMAGE
            
        # Video generation keywords
        video_keywords = ['video', 'animation', 'movie', 'generate video', 'create video',
                         'motion', 'clip']
        if any(kw in prompt_lower for kw in video_keywords):
            return TaskType.VIDEO
            
        # Coding keywords
        code_keywords = ['code', 'function', 'program', 'script', 'debug', 'implement',
                        'algorithm', 'class', 'module', 'api', 'refactor']
        if any(kw in prompt_lower for kw in code_keywords):
            return TaskType.CODING
            
        # Research keywords
        research_keywords = ['research', 'analyze', 'investigate', 'study', 'compare',
                            'evaluate', 'assess', 'review', 'synthesize']
        if any(kw in prompt_lower for kw in research_keywords):
            return TaskType.RESEARCH
            
        # Orchestration keywords (complex multi-step)
        orchestration_keywords = ['orchestrate', 'coordinate', 'plan', 'strategy',
                                 'workflow', 'pipeline', 'multi-step', 'complex']
        if any(kw in prompt_lower for kw in orchestration_keywords):
            return TaskType.ORCHESTRATION
            
        # Default to fast for simple queries
        return TaskType.FAST
        
    def select_model(self, task_type: TaskType, complexity: str = "medium") -> str:
        """Select the best model for a given task type."""
        routing = MODEL_ROUTING_TABLE.get(task_type, MODEL_ROUTING_TABLE[TaskType.FAST])
        
        # Adjust based on complexity
        if complexity == "critical":
            return routing[0][0]
        elif complexity == "high":
            return routing[0][0] if routing else routing[0][0]
        elif complexity == "low":
            return routing[-1][0] if len(routing) > 1 else routing[0][0]
        else:  # medium
            return routing[0][0] if routing else routing[0][0]
            
    def route_task(self, prompt: str, complexity: str = "auto") -> Dict[str, Any]:
        """Route a task to the appropriate model.
        
        Args:
            prompt: The task prompt
            complexity: low, medium, high, critical, or auto
            
        Returns:
            Dict with routing decision and metadata
        """
        # Classify the task
        task_type = self.classify_task(prompt)
        
        # Auto-determine complexity if needed
        if complexity == "auto":
            complexity = self._estimate_complexity(prompt)
            
        # Select model
        model = self.select_model(task_type, complexity)
        
        # Check budget
        estimated_cost = self._estimate_cost(model, prompt)
        can_execute = self.cost_tracker.can_execute(estimated_cost)
        
        routing_decision = {
            "task_type": task_type.value,
            "complexity": complexity,
            "selected_model": model,
            "budget_available": can_execute,
            "estimated_cost": estimated_cost,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        self._audit.log_event(
            event_type="ORCHESTRATION",
            actor="model_router",
            resource=f"task:{task_type.value}",
            action="route",
            status="success" if can_execute else "budget_exceeded",
            details=routing_decision
        )
        
        return routing_decision
        
    def _estimate_complexity(self, prompt: str) -> str:
        """Estimate task complexity based on prompt characteristics."""
        length = len(prompt)
        word_count = len(prompt.split())
        
        # Check for complex indicators
        complex_indicators = [
            'architecture', 'design', 'system', 'integrate', 'multiple',
            'complex', 'advanced', 'sophisticated', 'comprehensive'
        ]
        
        simple_indicators = [
            'simple', 'quick', 'brief', 'short', 'basic', 'hello'
        ]
        
        prompt_lower = prompt.lower()
        complex_score = sum(1 for ind in complex_indicators if ind in prompt_lower)
        simple_score = sum(1 for ind in simple_indicators if ind in prompt_lower)
        
        if complex_score >= 2 or word_count > 100 or length > 500:
            return "high"
        elif simple_score >= 1 or word_count < 20:
            return "low"
        else:
            return "medium"
            
    def _estimate_cost(self, model: str, prompt: str) -> float:
        """Estimate the cost of a request."""
        if model not in MODEL_COSTS:
            return 0.0
            
        # Rough estimate: assume output is 2x input length
        input_tokens = len(prompt) // 4  # Rough token estimate
        output_tokens = input_tokens * 2
        
        input_cost = (input_tokens / 1000) * MODEL_COSTS[model][0]
        output_cost = (output_tokens / 1000) * MODEL_COSTS[model][1]
        
        return round(input_cost + output_cost, 4)


class OpenRouterClient:
    """Client for OpenRouter API with cost tracking and security controls."""
    
    API_BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, vault: Optional[SecureVault] = None):
        self.vault = vault or get_vault()
        self.cost_tracker = CostTracker()
        self._audit = AuditLogger()
        self._api_key: Optional[str] = None
        
    def _get_api_key(self) -> str:
        """Retrieve API key from vault (never from .env)."""
        if self._api_key is None:
            self._api_key = self.vault.retrieve("openrouter_api_key", requester="openrouter_client")
            if self._api_key is None:
                raise RuntimeError("OpenRouter API key not found in vault")
        return self._api_key
        
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://openplex.local",
            "X-Title": "OpenPlexComputer"
        }
        
    def chat_completion(self, model: str, messages: List[Dict[str, str]],
                       temperature: float = 0.7, max_tokens: Optional[int] = None,
                       tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send a chat completion request."""
        import requests
        
        # Check budget before execution
        if not self.cost_tracker.can_execute():
            raise RuntimeError("Daily budget exceeded")
            
        # Log request
        self._audit.log_event(
            event_type="OPENROUTER_REQUEST",
            actor="orchestrator",
            resource=f"model:{model}",
            action="chat_completion",
            status="started",
            details={"message_count": len(messages), "has_tools": tools is not None}
        )
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        if tools:
            payload["tools"] = tools
            
        try:
            response = requests.post(
                f"{self.API_BASE_URL}/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            
            # Record usage
            usage = data.get("usage", {})
            cost_info = self.cost_tracker.record_usage(
                model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0)
            )
            
            # Log success
            self._audit.log_event(
                event_type="OPENROUTER_REQUEST",
                actor="orchestrator",
                resource=f"model:{model}",
                action="chat_completion",
                status="success",
                details={
                    "cost_usd": cost_info["cost_usd"],
                    "tokens_used": usage.get("total_tokens", 0)
                }
            )
            
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model", model),
                "usage": usage,
                "cost": cost_info,
                "finish_reason": data["choices"][0].get("finish_reason")
            }
            
        except Exception as e:
            self._audit.log_event(
                event_type="OPENROUTER_REQUEST",
                actor="orchestrator",
                resource=f"model:{model}",
                action="chat_completion",
                status="error",
                details={"error": str(e)}
            )
            raise RuntimeError(f"OpenRouter request failed: {e}")
            
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from OpenRouter."""
        import requests
        
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/models",
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.warning(f"Could not fetch models: {e}")
            return []


class OrchestratorEngine:
    """Main orchestration engine for routing tasks to appropriate models."""
    
    def __init__(self, daily_budget: float = 100.0):
        self.router = ModelRouter()
        self.client = OpenRouterClient()
        self.cost_tracker = CostTracker(daily_budget_usd=daily_budget)
        self._audit = AuditLogger()
        self._approval_required = True
        
    def route_and_execute(self, prompt: str, complexity: str = "auto",
                         approved: bool = False) -> Dict[str, Any]:
        """Route a task to the best model and execute.
        
        Args:
            prompt: The task prompt
            complexity: low, medium, high, critical, or auto
            approved: Whether the task has been approved
            
        Returns:
            Execution result with content and metadata
        """
        # Get routing decision
        routing = self.router.route_task(prompt, complexity)
        
        # Check if approval is required
        if self._approval_required and not approved:
            self._audit.log_event(
                event_type="ORCHESTRATION",
                actor="orchestrator",
                resource=f"task:{routing['task_type']}",
                action="request_approval",
                status="pending",
                details=routing
            )
            return {
                "status": "approval_required",
                "routing": routing,
                "message": "Task requires approval before execution"
            }
            
        # Check budget
        if not self.cost_tracker.can_execute(routing["estimated_cost"]):
            return {
                "status": "budget_exceeded",
                "routing": routing,
                "message": "Daily budget exceeded"
            }
            
        # Execute the task
        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = self.client.chat_completion(
                model=routing["selected_model"],
                messages=messages
            )
            
            # Update cost tracker
            self.cost_tracker.record_usage(
                routing["selected_model"],
                result["usage"].get("prompt_tokens", 0),
                result["usage"].get("completion_tokens", 0)
            )
            
            return {
                "status": "success",
                "routing": routing,
                "result": result
            }
            
        except Exception as e:
            return {
                "status": "error",
                "routing": routing,
                "error": str(e)
            }
            
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestration statistics."""
        return {
            "cost": self.cost_tracker.get_stats(),
            "approval_required": self._approval_required
        }


class ModelRouter:
    """Routes tasks to appropriate models based on task classification."""
    
    def __init__(self, vault: Optional[SecureVault] = None):
        self.vault = vault or get_vault()
        self.cost_tracker = CostTracker()
        self._audit = AuditLogger()
        
    def classify_task(self, prompt: str) -> TaskType:
        """Classify a task to determine the appropriate model type."""
        prompt_lower = prompt.lower()
        
        # Image generation keywords
        image_keywords = ['image', 'picture', 'photo', 'generate image', 'draw', 'create image', 
                         'illustration', 'artwork', 'render']
        if any(kw in prompt_lower for kw in image_keywords):
            return TaskType.IMAGE
            
        # Video generation keywords
        video_keywords = ['video', 'animation', 'movie', 'generate video', 'create video',
                         'motion', 'clip']
        if any(kw in prompt_lower for kw in video_keywords):
            return TaskType.VIDEO
            
        # Coding keywords
        code_keywords = ['code', 'function', 'program', 'script', 'debug', 'implement',
                        'algorithm', 'class', 'module', 'api', 'refactor']
        if any(kw in prompt_lower for kw in code_keywords):
            return TaskType.CODING
            
        # Research keywords
        research_keywords = ['research', 'analyze', 'investigate', 'study', 'compare',
                            'evaluate', 'assess', 'review', 'synthesize']
        if any(kw in prompt_lower for kw in research_keywords):
            return TaskType.RESEARCH
            
        # Orchestration keywords (complex multi-step)
        orchestration_keywords = ['orchestrate', 'coordinate', 'plan', 'strategy',
                                 'workflow', 'pipeline', 'multi-step', 'complex']
        if any(kw in prompt_lower for kw in orchestration_keywords):
            return TaskType.ORCHESTRATION
            
        # Default to fast for simple queries
        return TaskType.FAST
        
    def select_model(self, task_type: TaskType, complexity: str = "medium") -> str:
        """Select the best model for a given task type."""
        routing = MODEL_ROUTING_TABLE.get(task_type, MODEL_ROUTING_TABLE[TaskType.FAST])
        
        # Adjust based on complexity
        if complexity == "critical":
            return routing[0][0]
        elif complexity == "high":
            return routing[0][0] if routing else routing[0][0]
        elif complexity == "low":
            return routing[-1][0] if len(routing) > 1 else routing[0][0]
        else:  # medium
            return routing[0][0] if routing else routing[0][0]
            
    def route_task(self, prompt: str, complexity: str = "auto") -> Dict[str, Any]:
        """Route a task to the appropriate model."""
        # Classify the task
        task_type = self.classify_task(prompt)
        
        # Auto-determine complexity if needed
        if complexity == "auto":
            complexity = self._estimate_complexity(prompt)
            
        # Select model
        model = self.select_model(task_type, complexity)
        
        # Check budget
        estimated_cost = self._estimate_cost(model, prompt)
        can_execute = self.cost_tracker.can_execute(estimated_cost)
        
        routing_decision = {
            "task_type": task_type.value,
            "complexity": complexity,
            "selected_model": model,
            "budget_available": can_execute,
            "estimated_cost": estimated_cost,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        self._audit.log_event(
            event_type="ORCHESTRATION",
            actor="model_router",
            resource=f"task:{task_type.value}",
            action="route",
            status="success" if can_execute else "budget_exceeded",
            details=routing_decision
        )
        
        return routing_decision
        
    def _estimate_complexity(self, prompt: str) -> str:
        """Estimate task complexity based on prompt characteristics."""
        length = len(prompt)
        word_count = len(prompt.split())
        
        # Check for complex indicators
        complex_indicators = [
            'architecture', 'design', 'system', 'integrate', 'multiple',
            'complex', 'advanced', 'sophisticated', 'comprehensive'
        ]
        
        simple_indicators = [
            'simple', 'quick', 'brief', 'short', 'basic', 'hello'
        ]
        
        prompt_lower = prompt.lower()
        complex_score = sum(1 for ind in complex_indicators if ind in prompt_lower)
        simple_score = sum(1 for ind in simple_indicators if ind in prompt_lower)
        
        if complex_score >= 2 or word_count > 100 or length > 500:
            return "high"
        elif simple_score >= 1 or word_count < 20:
            return "low"
        else:
            return "medium"
            
    def _estimate_cost(self, model: str, prompt: str) -> float:
        """Estimate the cost of a request."""
        if model not in MODEL_COSTS:
            return 0.0
            
        # Rough estimate: assume output is 2x input length
        input_tokens = len(prompt) // 4  # Rough token estimate
        output_tokens = input_tokens * 2
        
        input_cost = (input_tokens / 1000) * MODEL_COSTS[model][0]
        output_cost = (output_tokens / 1000) * MODEL_COSTS[model][1]
        
        return round(input_cost + output_cost, 4)


# Convenience functions
def route_task(prompt: str, complexity: str = "auto") -> Dict[str, Any]:
    """Route a task to the appropriate model."""
    router = ModelRouter()
    return router.route_task(prompt, complexity)


if __name__ == "__main__":
    # Self-test
    print("OpenPlexComputer Orchestration Engine")
    print("=" * 50)
    
    # Test task classification
    print("\nTask Classification Test:")
    router = ModelRouter()
    
    test_prompts = [
        "Write a Python function to sort a list",
        "Generate an image of a sunset",
        "Research the latest AI developments",
        "Quick hello",
        "Design a complex microservices architecture"
    ]
    
    for prompt in test_prompts:
        task_type = router.classify_task(prompt)
        routing = router.route_task(prompt)
        print(f"  '{prompt[:30]}...' -> {task_type.value} -> {routing['selected_model']}")
    
    # Test cost tracking
    print("\nCost Tracking Test:")
    tracker = CostTracker(daily_budget_usd=50.0)
    stats = tracker.get_stats()
    print(f"  Daily budget: ${stats['daily_budget']}")
    print(f"  Remaining: ${stats['remaining']:.2f}")
    
    # Test model costs
    print("\nModel Cost Examples:")
    for model in ["anthropic/claude-opus-4.6", "openai/gpt-5.3-codex", "deepseek/r1"]:
        if model in MODEL_COSTS:
            costs = MODEL_COSTS[model]
            print(f"  {model}: ${costs[0]}/1K in, ${costs[1]}/1K out")
    
    print("\n✓ Orchestration Engine test complete")
