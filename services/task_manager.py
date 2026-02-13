"""In-process async task manager for long-running operations.

Runs sync service methods in a thread pool via asyncio.run_in_executor().
No external broker (Redis/Celery) needed for single-user v1.
"""

import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TaskInfo:
    """Internal task tracking state."""

    __slots__ = ("task_id", "status", "result", "error", "created_at", "completed_at")

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = "running"
        self.result: Any = None
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class TaskManager:
    """In-process task manager using thread pool executor.

    Submits sync functions to run in background threads, tracks their
    status, and stores results for polling via the /tasks endpoint.
    """

    def __init__(self, max_workers: int = 4):
        self._tasks: dict[str, TaskInfo] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def submit(self, func: Callable, *args, **kwargs) -> str:
        """Submit a sync function to run in background.

        Args:
            func: Synchronous callable to execute.
            *args, **kwargs: Arguments to pass to func.

        Returns:
            Task ID for polling status.
        """
        task_id = uuid.uuid4().hex[:12]
        task_info = TaskInfo(task_id)
        self._tasks[task_id] = task_info

        loop = asyncio.get_event_loop()
        asyncio.ensure_future(self._run(task_info, func, args, kwargs, loop))

        logger.info("Task %s submitted", task_id)
        return task_id

    async def _run(
        self,
        task_info: TaskInfo,
        func: Callable,
        args: tuple,
        kwargs: dict,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Execute the function in thread pool and capture result/error."""
        try:
            result = await loop.run_in_executor(
                self._executor, lambda: func(*args, **kwargs)
            )

            # Convert Pydantic models to dicts for JSON serialization
            if isinstance(result, BaseModel):
                result = result.model_dump()

            task_info.status = "completed"
            task_info.result = result
            logger.info("Task %s completed", task_info.task_id)
        except Exception as e:
            task_info.status = "failed"
            task_info.error = str(e)
            logger.error("Task %s failed: %s", task_info.task_id, e)
        finally:
            task_info.completed_at = datetime.now(timezone.utc).isoformat()

    def get_task(self, task_id: str) -> dict | None:
        """Get task status by ID.

        Returns:
            Task info dict or None if not found.
        """
        task_info = self._tasks.get(task_id)
        if not task_info:
            return None
        return task_info.to_dict()

    def get_tasks(self, limit: int = 20) -> list[dict]:
        """Get recent tasks sorted by creation time.

        Args:
            limit: Max number of tasks to return.

        Returns:
            List of task info dicts, newest first.
        """
        sorted_tasks = sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )[:limit]
        return [t.to_dict() for t in sorted_tasks]
