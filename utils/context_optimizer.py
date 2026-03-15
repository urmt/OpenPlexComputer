"""
Context optimizer that delegates to Context Mode when available,
falls back to standard execution otherwise.
"""
import subprocess
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("openplex.context_optimizer")


class ContextOptimizer:
    """Smart code execution wrapper with Context Mode support."""
    
    def __init__(self, mcp_client=None):
        self.config = self._load_config()
        self.mcp_client = mcp_client
        self.plugin = None
        
        if self.config.get("enabled"):
            try:
                from agents.plugins.context_mode_plugin import ContextModePlugin
                self.plugin = ContextModePlugin(mcp_client)
                if not self.plugin.is_available():
                    self.plugin = None
            except Exception as e:
                logger.debug(f"Context Mode plugin not available: {e}")
                self.plugin = None
        
        self.metrics = {
            "total_executions": 0,
            "context_mode_executions": 0,
            "fallback_executions": 0,
            "total_context_saved": 0,
        }
    
    def _load_config(self) -> Dict[str, Any]:
        enabled = os.getenv("CONTEXT_MODE_ENABLED", "false").lower() == "true"
        return {
            "enabled": enabled,
            "max_output_size": 5000,
            "supported_languages": ["/usr/bin/python3", "javascript", "shell"],
            "fallback_enabled": True,
        }
    
    def execute_code(self, language: str, code: str, intent: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        self.metrics["total_executions"] += 1
        
        if self.plugin and self.plugin.is_available():
            try:
                result = self.plugin.execute_code(language=language, code=code, intent=intent)
                if result.success:
                    self.metrics["context_mode_executions"] += 1
                    saved = len(result.full_output) - result.context_size
                    self.metrics["total_context_saved"] += saved
                    return {
                        "success": result.success,
                        "output": result.output,
                        "full_output": result.full_output,
                        "error": result.error,
                        "context_size": result.context_size,
                        "indexed": result.indexed,
                        "search_terms": result.search_terms,
                        "execution_time_ms": result.execution_time_ms,
                        "metadata": result.metadata
                    }
            except Exception as e:
                logger.warning(f"Context Mode plugin failed: {e}")
                if not self.config.get("fallback_enabled"):
                    raise
        
        return self._standard_execute(language, code, timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        total = self.metrics["total_executions"]
        ctx_mode = self.metrics["context_mode_executions"]
        return {
            "total_executions": total,
            "context_mode_executions": ctx_mode,
            "fallback_executions": self.metrics["fallback_executions"],
            "context_mode_percentage": (ctx_mode / total * 100) if total > 0 else 0,
            "total_context_saved_bytes": self.metrics["total_context_saved"],
            "plugin_available": self.plugin is not None and self.plugin.is_available(),
        }
    
    def _standard_execute(self, language: str, code: str, timeout: int) -> Dict[str, Any]:
        self.metrics["fallback_executions"] += 1
        
        commands = {
            "/usr/bin/python3": ["/usr/bin/python3", "-c", code],
            "javascript": ["node", "-e", code],
            "shell": ["sh", "-c", code],
        }
        
        cmd = commands.get(language)
        if not cmd:
            return {"success": False, "output": "", "full_output": "", "error": f"Unsupported: {language}", "context_size": 0, "indexed": False, "search_terms": [], "execution_time_ms": 0, "metadata": {}}
        
        import time
        start_time = time.time()
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = result.stdout if result.returncode == 0 else result.stderr
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "success": result.returncode == 0,
                "output": output,
                "full_output": output,
                "error": result.stderr if result.returncode != 0 else "",
                "context_size": len(output),
                "indexed": False,
                "search_terms": [],
                "execution_time_ms": execution_time,
                "metadata": {"fallback": True}
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "full_output": "", "error": f"Timeout after {timeout}s", "context_size": 0, "indexed": False, "search_terms": [], "execution_time_ms": (time.time() - start_time) * 1000, "metadata": {"fallback": True}}
        except Exception as e:
            return {"success": False, "output": "", "full_output": "", "error": str(e), "context_size": 0, "indexed": False, "search_terms": [], "execution_time_ms": (time.time() - start_time) * 1000, "metadata": {"fallback": True}}
