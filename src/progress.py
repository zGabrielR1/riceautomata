import sys
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from threading import Lock
from tqdm import tqdm

@dataclass
class ProgressTask:
    """Represents a task with progress tracking."""
    name: str
    total: int
    current: int = 0
    status: str = "pending"
    message: str = ""
    progress_bar: Any = None
    _lock: Lock = field(default_factory=Lock)

class ProgressTracker:
    """Manages progress tracking for multiple tasks."""
    
    def __init__(self, show_spinner: bool = True):
        self.tasks: Dict[str, ProgressTask] = {}
        self.show_spinner = show_spinner
        self._lock = Lock()
        
    def add_task(self, name: str, total: int = 100) -> str:
        """Add a new task to track."""
        with self._lock:
            task = ProgressTask(
                name=name,
                total=total,
                progress_bar=tqdm(
                    total=total,
                    desc=name,
                    leave=True,
                    file=sys.stdout
                )
            )
            self.tasks[name] = task
            return name
            
    def update(self, task_name: str, advance: int = 1, message: Optional[str] = None):
        """Update task progress."""
        with self._lock:
            if task_name not in self.tasks:
                return
                
            task = self.tasks[task_name]
            with task._lock:
                task.current = min(task.current + advance, task.total)
                if message:
                    task.message = message
                if task.progress_bar:
                    task.progress_bar.update(advance)
                    if message:
                        task.progress_bar.set_description(f"{task.name}: {message}")
                        
    def complete(self, task_name: str, message: Optional[str] = None):
        """Mark a task as complete."""
        with self._lock:
            if task_name not in self.tasks:
                return
                
            task = self.tasks[task_name]
            with task._lock:
                remaining = task.total - task.current
                if remaining > 0:
                    task.progress_bar.update(remaining)
                task.status = "complete"
                if message:
                    task.message = message
                    task.progress_bar.set_description(f"{task.name}: {message}")
                task.progress_bar.close()
                
    def fail(self, task_name: str, message: str):
        """Mark a task as failed."""
        with self._lock:
            if task_name not in self.tasks:
                return
                
            task = self.tasks[task_name]
            with task._lock:
                task.status = "failed"
                task.message = message
                if task.progress_bar:
                    task.progress_bar.set_description(f"{task.name}: {message}")
                    task.progress_bar.close()
                    
    def get_status(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task."""
        with self._lock:
            if task_name not in self.tasks:
                return None
                
            task = self.tasks[task_name]
            with task._lock:
                return {
                    "name": task.name,
                    "total": task.total,
                    "current": task.current,
                    "status": task.status,
                    "message": task.message,
                    "progress": (task.current / task.total) * 100 if task.total > 0 else 0
                }
                
class ProgressContext:
    """Context manager for task progress tracking."""
    
    def __init__(self, tracker: ProgressTracker, task_name: str, total: int = 100):
        self.tracker = tracker
        self.task_name = task_name
        self.total = total
        
    def __enter__(self):
        self.tracker.add_task(self.task_name, self.total)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.tracker.fail(self.task_name, str(exc_val))
        else:
            self.tracker.complete(self.task_name)
            
    def update(self, advance: int = 1, message: Optional[str] = None):
        """Update task progress."""
        self.tracker.update(self.task_name, advance, message)
