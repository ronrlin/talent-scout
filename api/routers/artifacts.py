"""Artifact download endpoint — serves generated files."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from api.auth import verify_api_key
from api.dependencies import get_composer_service, get_job_service
from services import ComposerService, JobService

router = APIRouter(dependencies=[Depends(verify_api_key)])

# Map artifact types to document lookup types
ARTIFACT_TYPE_MAP = {
    "resume": "resume",
    "cover_letter": "cover-letter",
    "cover-letter": "cover-letter",
    "interview_prep": "interview-prep",
    "interview-prep": "interview-prep",
}

CONTENT_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".json": "application/json",
}


@router.get("/jobs/{job_id}/artifacts/{artifact_type}")
async def download_artifact(
    job_id: str,
    artifact_type: str,
    format: str = Query("pdf", description="File format: pdf, docx, or md"),
    svc: JobService = Depends(get_job_service),
    composer: ComposerService = Depends(get_composer_service),
):
    """Download a generated artifact for a job.

    Artifact types: resume, cover_letter, interview_prep, analysis.
    Formats: pdf, docx, md (analysis always returns json).
    """
    # Validate artifact type
    if artifact_type == "analysis":
        # Analysis is always JSON
        analysis_path = composer.output_dir / "analysis" / f"{job_id}-analysis.json"
        if not analysis_path.exists():
            raise HTTPException(status_code=404, detail="Analysis not found")
        return FileResponse(
            analysis_path,
            media_type="application/json",
            filename=analysis_path.name,
        )

    doc_type = ARTIFACT_TYPE_MAP.get(artifact_type)
    if not doc_type:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid artifact type: {artifact_type}. "
            f"Valid: {', '.join(ARTIFACT_TYPE_MAP.keys())}, analysis",
        )

    # Find the markdown file first
    md_path = composer.find_document_by_job_id(job_id, doc_type)
    if not md_path:
        raise HTTPException(
            status_code=404,
            detail=f"No {artifact_type} found for job {job_id}",
        )

    if format == "md":
        return FileResponse(
            md_path,
            media_type="text/markdown",
            filename=md_path.name,
        )

    # Look for the formatted file next to the markdown
    ext = f".{format}"
    formatted_path = md_path.with_suffix(ext)

    if not formatted_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No {format.upper()} file found. Generate it first or use format=md.",
        )

    content_type = CONTENT_TYPE_MAP.get(ext, "application/octet-stream")
    return FileResponse(
        formatted_path,
        media_type=content_type,
        filename=formatted_path.name,
    )
