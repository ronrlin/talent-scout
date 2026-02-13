"""Profile endpoints."""

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from api.auth import verify_api_key
from api.dependencies import get_profile_service, get_task_manager
from services import ProfileService
from services.models import ProfileResponse, TaskCreatedResponse
from services.task_manager import TaskManager

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    svc: ProfileService = Depends(get_profile_service),
):
    """Get the current candidate profile."""
    return svc.get_profile()


@router.post("/profile/refresh", response_model=TaskCreatedResponse, status_code=202)
async def refresh_profile(
    svc: ProfileService = Depends(get_profile_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Re-parse profile from base resume (async — poll /tasks/{task_id})."""
    task_id = await tm.submit(svc.refresh_profile)
    return TaskCreatedResponse(task_id=task_id, status="running")
