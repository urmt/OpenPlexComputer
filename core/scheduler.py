"""Async Execution Framework."""
import asyncio, json, logging, uuid, threading, time, os
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

@dataclass
class TaskResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0

@dataclass
class Task:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    result: Optional[TaskResult] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300

class TaskRegistry:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
    
    def register(self, task_type: str, handler: Callable):
        self._handlers[task_type] = handler
    
    def get_handler(self, task_type: str):
        return self._handlers.get(task_type)

class AsyncTaskScheduler:
    def __init__(self, max_workers: int = 4, db_path: Optional[str] = None):
        self.max_workers = max_workers
        self.db_path = db_path or os.path.expanduser("~/.openplex/scheduler.db")
        self.registry = TaskRegistry()
        self._queues: Dict[TaskPriority, Queue] = {priority: Queue() for priority in TaskPriority}
        self._active_tasks: Dict[str, Task] = {}
        self._task_history: List[Task] = []
        self._workers: List[threading.Thread] = []
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown_event = threading.Event()
        self._lock = threading.RLock()
    
    def start(self):
        with self._lock:
            if self._workers:
                return
            self._shutdown_event.clear()
            for i in range(self.max_workers):
                worker = threading.Thread(target=self._worker_loop, args=(i,), daemon=True, name=f"TaskWorker-{i}")
                worker.start()
                self._workers.append(worker)
    
    def stop(self, wait: bool = True, timeout: float = 30.0):
        self._shutdown_event.set()
        if wait and self._workers:
            for worker in self._workers:
                worker.join(timeout=timeout / len(self._workers))
        self._executor.shutdown(wait=wait)
        self._workers.clear()
    
    def _worker_loop(self, worker_id: int):
        worker_name = f"worker-{worker_id}"
        while not self._shutdown_event.is_set():
            task = None
            for priority in TaskPriority:
                try:
                    task = self._queues[priority].get(timeout=0.1)
                    break
                except Empty:
                    continue
            if task is None:
                continue
            self._process_task(task, worker_name)
    
    def _process_task(self, task: Task, worker_id: str):
        task.worker_id = worker_id
        task.started_at = datetime.utcnow()
        task.status = TaskStatus.RUNNING
        with self._lock:
            self._active_tasks[task.task_id] = task
        start_time = time.time()
        try:
            handler = self.registry.get_handler(task.task_type)
            if handler is None:
                raise ValueError(f"No handler for task type: {task.task_type}")
            result_data = handler(**task.payload)
            execution_time = (time.time() - start_time) * 1000
            task.result = TaskResult(success=True, output=result_data, execution_time_ms=execution_time)
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            task.result = TaskResult(success=False, error=str(e), execution_time_ms=execution_time)
            task.status = TaskStatus.FAILED
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                self._queues[task.priority].put(task)
        finally:
            task.completed_at = datetime.utcnow()
            with self._lock:
                if task.task_id in self._active_tasks:
                    del self._active_tasks[task.task_id]
                self._task_history.append(task)
    
    def submit_task(self, task_type: str, payload: Dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL, timeout_seconds: int = 300, max_retries: int = 3) -> str:
        task = Task(task_id=str(uuid.uuid4()), task_type=task_type, payload=payload, priority=priority, timeout_seconds=timeout_seconds, max_retries=max_retries)
        self._queues[priority].put(task)
        return task.task_id
    
    def get_task_status(self, task_id: str):
        with self._lock:
            if task_id in self._active_tasks:
                return self._active_tasks[task_id].to_dict()
            for task in reversed(self._task_history):
                if task.task_id == task_id:
                    return task.to_dict()
        return None
    
    def get_stats(self):
        with self._lock:
            return {"active_tasks": len(self._active_tasks), "history_size": len(self._task_history)}

def get_scheduler():
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AsyncTaskScheduler()
    return _scheduler_instance

def init_scheduler(max_workers=4):
    global _scheduler_instance
    _scheduler_instance = AsyncTaskScheduler(max_workers=max_workers)
    _scheduler_instance.start()
    return _scheduler_instance

_scheduler_instance = None
