"""FastAPI application factory.

Creates the app with CORS, routers, error handlers, and OpenAPI metadata.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.exceptions import (
    TalentScoutError,
    JobNotFoundError,
    CompanyNotFoundError,
    ProfileNotFoundError,
    ResumeNotFoundError,
    AnalysisNotFoundError,
    GenerationFailedError,
    ValidationError,
    PipelineError,
)

from .auth import get_or_create_api_key
from .routers import (
    profile,
    discovery,
    jobs,
    pipeline,
    composer,
    corpus,
    tasks,
    artifacts,
)

logger = logging.getLogger(__name__)

# Map service exceptions to HTTP status codes
EXCEPTION_STATUS_MAP = {
    JobNotFoundError: 404,
    CompanyNotFoundError: 404,
    ProfileNotFoundError: 404,
    ResumeNotFoundError: 404,
    AnalysisNotFoundError: 404,
    ValidationError: 422,
    PipelineError: 409,
    GenerationFailedError: 502,
}


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        api_key = get_or_create_api_key()
        logger.info("Talent Scout API starting")
        print(f"\n  API Key: {api_key}")
        print(f"  Docs:    http://localhost:8000/docs\n")
        yield
        # Shutdown (nothing to clean up)

    app = FastAPI(
        title="Talent Scout API",
        description="AI-powered job search automation — REST API",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow localhost on any port
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://localhost(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers under /api/v1
    prefix = "/api/v1"
    app.include_router(profile.router, prefix=prefix, tags=["Profile"])
    app.include_router(discovery.router, prefix=prefix, tags=["Discovery"])
    app.include_router(jobs.router, prefix=prefix, tags=["Jobs"])
    app.include_router(pipeline.router, prefix=prefix, tags=["Pipeline"])
    app.include_router(composer.router, prefix=prefix, tags=["Composer"])
    app.include_router(corpus.router, prefix=prefix, tags=["Corpus"])
    app.include_router(tasks.router, prefix=prefix, tags=["Tasks"])
    app.include_router(artifacts.router, prefix=prefix, tags=["Artifacts"])

    # Global exception handler for service-layer errors
    @app.exception_handler(TalentScoutError)
    async def talent_scout_error_handler(request: Request, exc: TalentScoutError):
        status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc)},
        )

    # Health check (no auth)
    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok"}

    return app
