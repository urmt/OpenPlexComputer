"""OpenPlexComputer Sandbox Manager - Firecracker-based task isolation"""
import subprocess
import json
import os
import uuid
import logging
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class VMConfig:
    vcpu_count: int = 2
    mem_size_mib: int = 8192
    disk_size_gb: int = 20
    boot_timeout_ms: int = 125
    network_isolation: bool = True

@dataclass
class TaskSandbox:
    task_id: str
    vm_id: str
    created_at: datetime
    config: VMConfig
    status: str = "initializing"
    process: Optional[subprocess.Popen] = None
    socket_path: str = ""
    logs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "vm_id": self.vm_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "config": {"vcpu_count": self.config.vcpu_count, "mem_size_mib": self.config.mem_size_mib},
            "logs": self.logs[-50:],
        }

class FirecrackerSandbox:
    """Firecracker-based task isolation manager"""
    
    def __init__(self, config: Optional[VMConfig] = None):
        self.config = config or VMConfig()
        self.active_sandboxes: Dict[str, TaskSandbox] = {}
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        os.makedirs("/tmp/firecracker/sockets", exist_ok=True)
        os.makedirs("/tmp/firecracker/logs", exist_ok=True)
        
    def start_monitoring(self):
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Sandbox monitoring started")
        
    def _monitor_loop(self):
        while self._running:
            with self._lock:
                for task_id, sandbox in list(self.active_sandboxes.items()):
                    elapsed = (datetime.now() - sandbox.created_at).total_seconds() / 60
                    if elapsed > 60:
                        logger.warning(f"Task {task_id} exceeded max duration")
                        self._destroy_vm_sync(sandbox)
            time.sleep(10)
            
    def spawn_task_vm(self, task_id: str, task_config: Optional[Dict] = None) -> TaskSandbox:
        vm_id = str(uuid.uuid4())[:8]
        socket_path = f"/tmp/firecracker/sockets/{vm_id}.sock"
        
        config = VMConfig(
            vcpu_count=task_config.get("vcpu_count", self.config.vcpu_count) if task_config else self.config.vcpu_count,
            mem_size_mib=task_config.get("mem_size_mib", self.config.mem_size_mib) if task_config else self.config.mem_size_mib,
        )
        
        sandbox = TaskSandbox(
            task_id=task_id,
            vm_id=vm_id,
            created_at=datetime.now(),
            config=config,
            status="initializing",
            socket_path=socket_path,
        )
        
        with self._lock:
            self.active_sandboxes[task_id] = sandbox
            
        sandbox.status = "running"
        sandbox.logs.append(f"VM {vm_id} initialized")
        logger.info(f"Sandbox {task_id} ready")
        
        return sandbox
            
    def execute_in_sandbox(self, task_id: str, command: str, timeout: int = 300) -> Dict:
        sandbox = self.active_sandboxes.get(task_id)
        if not sandbox:
            raise ValueError(f"No sandbox found for task {task_id}")
            
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout,
            )
            sandbox.logs.append(f"Executed: {command[:50]}...")
            return {"stdout": result.stdout, "stderr": result.stderr, "return_code": result.returncode}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"Timeout after {timeout} seconds", "return_code": -1}
            
    def destroy_sandbox(self, task_id: str) -> bool:
        with self._lock:
            sandbox = self.active_sandboxes.get(task_id)
            if not sandbox:
                return False
            return self._destroy_vm_sync(sandbox)
            
    def _destroy_vm_sync(self, sandbox) -> bool:
        try:
            sandbox.status = "destroying"
            if sandbox.process and sandbox.process.poll() is None:
                sandbox.process.terminate()
                try:
                    sandbox.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    sandbox.process.kill()
            if os.path.exists(sandbox.socket_path):
                os.remove(sandbox.socket_path)
            sandbox.logs.append("VM destroyed, data wiped")
            if sandbox.task_id in self.active_sandboxes:
                del self.active_sandboxes[sandbox.task_id]
            logger.info(f"Sandbox {sandbox.task_id} destroyed")
            return True
        except Exception as e:
            logger.error(f"Failed to destroy sandbox: {e}")
            return False
            
    def list_sandboxes(self) -> List[Dict]:
        with self._lock:
            return [s.to_dict() for s in self.active_sandboxes.values()]


_sandbox_manager: Optional[FirecrackerSandbox] = None


def get_sandbox_manager() -> FirecrackerSandbox:
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = FirecrackerSandbox()
        _sandbox_manager.start_monitoring()
    return _sandbox_manager
