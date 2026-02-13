"""Discovery endpoints — company scouting, research, job import, learning."""

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from api.auth import verify_api_key
from api.dependencies import get_discovery_service, get_task_manager
from services import DiscoveryService
from services.models import (
    ScoutCompaniesRequest,
    ResearchRequest,
    ImportUrlRequest,
    ImportMarkdownRequest,
    CompanySummary,
    TaskCreatedResponse,
)
from services.task_manager import TaskManager

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/companies/scout", response_model=TaskCreatedResponse, status_code=202)
async def scout_companies(
    body: ScoutCompaniesRequest,
    svc: DiscoveryService = Depends(get_discovery_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Scout target companies for a location (async)."""
    task_id = await tm.submit(svc.scout_companies, body.location, body.count)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.get("/companies", response_model=list[CompanySummary])
async def get_companies(
    location_slug: str = "all",
    svc: DiscoveryService = Depends(get_discovery_service),
):
    """Get previously scouted companies."""
    return svc.get_companies(location_slug)


@router.post("/research", response_model=TaskCreatedResponse, status_code=202)
async def research_company(
    body: ResearchRequest,
    svc: DiscoveryService = Depends(get_discovery_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Research a company and discover jobs (async)."""
    task_id = await tm.submit(svc.research_company, body.company_name)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post("/jobs/import/url", response_model=TaskCreatedResponse, status_code=202)
async def import_job_from_url(
    body: ImportUrlRequest,
    svc: DiscoveryService = Depends(get_discovery_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Import a job posting from a URL (async)."""
    task_id = await tm.submit(svc.import_job_from_url, body.url)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post("/jobs/import/markdown", response_model=TaskCreatedResponse, status_code=202)
async def import_job_from_markdown(
    body: ImportMarkdownRequest,
    svc: DiscoveryService = Depends(get_discovery_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Import a job posting from markdown content (async)."""
    task_id = await tm.submit(svc.import_job_from_markdown, body.content, body.filename)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post("/learn", response_model=TaskCreatedResponse, status_code=202)
async def learn_from_feedback(
    svc: DiscoveryService = Depends(get_discovery_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Analyze imported/deleted jobs to improve targeting (async)."""
    task_id = await tm.submit(svc.learn_from_feedback)
    return TaskCreatedResponse(task_id=task_id, status="running")
