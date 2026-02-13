"""Corpus endpoints — build, update, stats."""

from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.dependencies import get_corpus_service, get_task_manager
from services import CorpusService
from services.models import CorpusStats, TaskCreatedResponse
from services.task_manager import TaskManager

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/corpus/build", response_model=TaskCreatedResponse, status_code=202)
async def build_corpus(
    svc: CorpusService = Depends(get_corpus_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Build experience bullet corpus from existing resumes (async)."""
    task_id = await tm.submit(svc.build)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post("/corpus/update", response_model=TaskCreatedResponse, status_code=202)
async def update_corpus(
    svc: CorpusService = Depends(get_corpus_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Update corpus with new bullets from recent resumes (async)."""
    task_id = await tm.submit(svc.update)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.get("/corpus/stats", response_model=CorpusStats)
async def get_corpus_stats(
    svc: CorpusService = Depends(get_corpus_service),
):
    """Get corpus statistics."""
    return svc.get_stats()
