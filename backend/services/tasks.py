"""
Background task manager with WebSocket progress broadcasting.
Tracks download and sync tasks, provides real-time progress updates.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskProgress:
    """Tracks a single background task."""
    task_id: str
    task_type: str  # "download", "sync"
    title: str
    status: str = "pending"  # pending, running, completed, failed
    progress: int = 0
    downloaded: int = 0
    total: int = 0
    speed: float = 0.0
    eta: float = 0.0
    message: str = ""
    started_at: float = field(default_factory=time.time)
    _last_update: float = field(default=0.0, repr=False)
    _last_bytes: int = field(default=0, repr=False)


class TaskManager:
    """Manages background tasks and broadcasts progress to WebSocket clients."""

    def __init__(self):
        self._tasks: dict[str, TaskProgress] = {}
        self._ws_clients: set[asyncio.Queue] = set()
        self._counter = 0

    def create_task(self, task_type: str, title: str) -> str:
        self._counter += 1
        task_id = f"{task_type}-{self._counter}-{int(time.time())}"
        task = TaskProgress(task_id=task_id, task_type=task_type, title=title)
        self._tasks[task_id] = task
        return task_id

    def update_progress(self, task_id: str, downloaded: int, total: int, message: str = ""):
        task = self._tasks.get(task_id)
        if not task:
            return

        now = time.time()
        task.status = "running"
        task.downloaded = downloaded
        task.total = total
        task.progress = int((downloaded / total) * 100) if total > 0 else 0
        if message:
            task.message = message

        # Calculate speed (bytes/sec) using a rolling window
        elapsed_since_update = now - task._last_update if task._last_update else 0
        if elapsed_since_update > 0.5:
            bytes_delta = downloaded - task._last_bytes
            task.speed = bytes_delta / elapsed_since_update
            if task.speed > 0 and total > downloaded:
                task.eta = (total - downloaded) / task.speed
            else:
                task.eta = 0
            task._last_update = now
            task._last_bytes = downloaded
            # Broadcast on speed calculation intervals
            self._broadcast(task)
        elif task._last_update == 0:
            task._last_update = now
            task._last_bytes = downloaded

    def complete_task(self, task_id: str, message: str = ""):
        task = self._tasks.get(task_id)
        if task:
            task.status = "completed"
            task.progress = 100
            task.message = message
            task.speed = 0
            task.eta = 0
            self._broadcast(task)

    def fail_task(self, task_id: str, message: str = ""):
        task = self._tasks.get(task_id)
        if task:
            task.status = "failed"
            task.message = message
            task.speed = 0
            task.eta = 0
            self._broadcast(task)

    def get_active_tasks(self) -> list[dict]:
        return [self._task_dict(t) for t in self._tasks.values()
                if t.status in ("pending", "running")]

    def get_task(self, task_id: str) -> Optional[dict]:
        task = self._tasks.get(task_id)
        return self._task_dict(task) if task else None

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=50)
        self._ws_clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._ws_clients.discard(queue)

    def _broadcast(self, task: TaskProgress):
        msg = self._task_dict(task)
        dead = set()
        for q in self._ws_clients:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.add(q)
        for q in dead:
            self._ws_clients.discard(q)

    @staticmethod
    def _task_dict(task: TaskProgress) -> dict:
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "title": task.title,
            "status": task.status,
            "progress": task.progress,
            "downloaded": task.downloaded,
            "total": task.total,
            "speed": task.speed,
            "eta": task.eta,
            "message": task.message,
        }

    def cleanup_old(self, max_age: float = 300):
        """Remove completed/failed tasks older than max_age seconds."""
        now = time.time()
        to_remove = [
            tid for tid, t in self._tasks.items()
            if t.status in ("completed", "failed") and (now - t.started_at) > max_age
        ]
        for tid in to_remove:
            del self._tasks[tid]


# Singleton instance
task_manager = TaskManager()
