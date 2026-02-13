"""Pipeline endpoints — overview, next actions, stats."""

from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from api.dependencies import get_job_service
from services import JobService
from services.models import PipelineOverview, ActionableResponse, PipelineStats

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/pipeline", response_model=PipelineOverview)
async def get_pipeline_overview(
    stage: str | None = Query(None, description="Filter to a single stage"),
    svc: JobService = Depends(get_job_service),
):
    """Kanban-style pipeline overview grouped by stage."""
    return svc.get_pipeline_overview(filter_stage=stage)


@router.get("/pipeline/next", response_model=ActionableResponse)
async def get_next_actions(
    svc: JobService = Depends(get_job_service),
):
    """Prioritized action dashboard — what to do next."""
    return svc.get_actionable()


@router.get("/pipeline/stats", response_model=PipelineStats)
async def get_pipeline_stats(
    svc: JobService = Depends(get_job_service),
):
    """Pipeline conversion stats by stage and outcome."""
    return svc.get_pipeline_stats()
