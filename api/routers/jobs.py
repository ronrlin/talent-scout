"""Jobs endpoints — CRUD and pipeline operations."""

from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from api.dependencies import get_job_service
from services import JobService
from services.models import (
    JobSummary,
    JobDetail,
    PipelineEntryResponse,
    HistoryEntry,
    ApplyRequest,
    StatusUpdateRequest,
    CloseRequest,
    NoteRequest,
    DeleteJobRequest,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/jobs", response_model=list[JobSummary])
async def get_jobs(
    location: str | None = Query(None, description="Filter by location"),
    company: str | None = Query(None, description="Filter by company"),
    source: str | None = Query(None, description="Filter by source (imported/discovered)"),
    stage: str | None = Query(None, description="Filter by pipeline stage"),
    svc: JobService = Depends(get_job_service),
):
    """List jobs with optional filters, sorted by match score."""
    return svc.get_jobs(location=location, company=company, source=source, stage=stage)


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: str,
    svc: JobService = Depends(get_job_service),
):
    """Get full job details including pipeline entry."""
    return svc.get_job(job_id)


@router.delete("/jobs/{job_id}", response_model=JobDetail)
async def delete_job(
    job_id: str,
    body: DeleteJobRequest | None = None,
    svc: JobService = Depends(get_job_service),
):
    """Delete a job and record for negative learning."""
    reason = body.reason if body else None
    return svc.delete_job(job_id, reason=reason)


@router.post("/jobs/{job_id}/apply", response_model=PipelineEntryResponse)
async def apply_to_job(
    job_id: str,
    body: ApplyRequest | None = None,
    svc: JobService = Depends(get_job_service),
):
    """Record that you submitted an application."""
    if body:
        return svc.apply(job_id, via=body.via, notes=body.notes, date=body.date)
    return svc.apply(job_id)


@router.put("/jobs/{job_id}/status", response_model=PipelineEntryResponse)
async def set_status(
    job_id: str,
    body: StatusUpdateRequest,
    svc: JobService = Depends(get_job_service),
):
    """Set pipeline stage for a job."""
    return svc.set_status(job_id, body.stage.value)


@router.post("/jobs/{job_id}/close", response_model=PipelineEntryResponse)
async def close_job(
    job_id: str,
    body: CloseRequest,
    svc: JobService = Depends(get_job_service),
):
    """Close an application with an outcome."""
    return svc.close(job_id, body.outcome.value)


@router.get("/jobs/{job_id}/history", response_model=list[HistoryEntry])
async def get_history(
    job_id: str,
    svc: JobService = Depends(get_job_service),
):
    """Get pipeline history for a job."""
    return svc.get_history(job_id)


@router.post("/jobs/{job_id}/notes", status_code=201)
async def add_note(
    job_id: str,
    body: NoteRequest,
    svc: JobService = Depends(get_job_service),
):
    """Add a note to a pipeline entry."""
    svc.add_note(job_id, body.text)
    return {"ok": True}
