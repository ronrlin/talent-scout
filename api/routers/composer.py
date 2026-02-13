"""Composer endpoints — analyze, resume, cover letter, interview prep."""

from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.dependencies import get_composer_service, get_task_manager
from services import ComposerService
from services.models import GenerateRequest, TaskCreatedResponse, OutputFormat
from services.task_manager import TaskManager

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post(
    "/jobs/{job_id}/analyze",
    response_model=TaskCreatedResponse,
    status_code=202,
)
async def analyze_job(
    job_id: str,
    svc: ComposerService = Depends(get_composer_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Analyze job requirements and match against profile (async)."""
    task_id = await tm.submit(svc.analyze_job, job_id)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post(
    "/jobs/{job_id}/resume",
    response_model=TaskCreatedResponse,
    status_code=202,
)
async def generate_resume(
    job_id: str,
    body: GenerateRequest | None = None,
    svc: ComposerService = Depends(get_composer_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Generate a customized resume (async)."""
    fmt = body.output_format.value if body else "pdf"
    task_id = await tm.submit(svc.generate_resume, job_id, fmt)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post(
    "/jobs/{job_id}/resume/improve",
    response_model=TaskCreatedResponse,
    status_code=202,
)
async def improve_resume(
    job_id: str,
    body: GenerateRequest | None = None,
    svc: ComposerService = Depends(get_composer_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Iteratively improve an existing resume (async — 3-phase pipeline)."""
    fmt = body.output_format.value if body else "pdf"
    task_id = await tm.submit(svc.improve_resume, job_id, fmt)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post(
    "/jobs/{job_id}/cover-letter",
    response_model=TaskCreatedResponse,
    status_code=202,
)
async def generate_cover_letter(
    job_id: str,
    body: GenerateRequest | None = None,
    svc: ComposerService = Depends(get_composer_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Generate a tailored cover letter (async)."""
    fmt = body.output_format.value if body else "pdf"
    task_id = await tm.submit(svc.generate_cover_letter, job_id, fmt)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post(
    "/jobs/{job_id}/interview-prep",
    response_model=TaskCreatedResponse,
    status_code=202,
)
async def generate_interview_prep(
    job_id: str,
    svc: ComposerService = Depends(get_composer_service),
    tm: TaskManager = Depends(get_task_manager),
):
    """Generate screening interview talking points (async)."""
    task_id = await tm.submit(svc.generate_interview_prep, job_id)
    return TaskCreatedResponse(task_id=task_id, status="running")


@router.post("/jobs/{job_id}/resume/regenerate")
async def regenerate_resume(
    job_id: str,
    body: GenerateRequest | None = None,
    svc: ComposerService = Depends(get_composer_service),
):
    """Regenerate resume output from existing markdown (sync)."""
    fmt = body.output_format.value if body else "pdf"
    md_path = svc.find_document_by_job_id(job_id, "resume")
    if not md_path:
        from services.exceptions import ResumeNotFoundError
        raise ResumeNotFoundError(f"No resume markdown found for {job_id}")

    results = svc.regenerate_output(md_path, "resume", fmt)
    return {
        fmt_key: str(path) if path else None
        for fmt_key, path in results.items()
    }


@router.post("/jobs/{job_id}/cover-letter/regenerate")
async def regenerate_cover_letter(
    job_id: str,
    body: GenerateRequest | None = None,
    svc: ComposerService = Depends(get_composer_service),
):
    """Regenerate cover letter output from existing markdown (sync)."""
    fmt = body.output_format.value if body else "pdf"
    md_path = svc.find_document_by_job_id(job_id, "cover-letter")
    if not md_path:
        from services.exceptions import ResumeNotFoundError
        raise ResumeNotFoundError(f"No cover letter markdown found for {job_id}")

    results = svc.regenerate_output(md_path, "cover-letter", fmt)
    return {
        fmt_key: str(path) if path else None
        for fmt_key, path in results.items()
    }
