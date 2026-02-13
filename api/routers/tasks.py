"""Task polling endpoints for async operations."""

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import verify_api_key
from api.dependencies import get_task_manager
from services.models import TaskStatusResponse, TaskStatus
from services.task_manager import TaskManager

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    tm: TaskManager = Depends(get_task_manager),
):
    """Poll async task status. Returns result when completed."""
    task = tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=TaskStatus(task["status"]),
        result=task["result"],
        error=task["error"],
        created_at=task["created_at"],
        completed_at=task["completed_at"],
    )


@router.get("/tasks")
async def list_tasks(
    limit: int = Query(20, ge=1, le=100),
    tm: TaskManager = Depends(get_task_manager),
):
    """List recent async tasks."""
    return tm.get_tasks(limit=limit)
