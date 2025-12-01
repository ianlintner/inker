"""Frontend API endpoints for the AI Blogger.

This module provides RESTful API endpoints for frontend clients to:
- Submit job requests
- View job status and results
- Preview blog post markdown
- Approve/reject workflow hooks
- Prometheus metrics endpoint (/metrics)

Designed for extensibility and connection with backend services.

Usage:
    from ai_blogger.frontend_api import create_app, router

    # Use the router in an existing FastAPI app
    app = FastAPI()
    app.include_router(router, prefix="/api")

    # Or create a standalone app
    app = create_app()

    # Run with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .feedback_api import FeedbackService
from .feedback_models import (
    ApprovalRequest,
    FeedbackCategory,
    FeedbackEntry,
    FeedbackRating,
    FeedbackResponse,
    FeedbackStats,
    RejectionRequest,
    RevisionRequest,
)
from .job_api import JobService
from .job_models import (
    JobRequest,
    JobStatus,
    JobStatusResponse,
    JobSubmitResponse,
    MarkdownPreview,
)
from .metrics import (
    PROMETHEUS_AVAILABLE,
    set_system_info,
    track_api_request,
)
from .persistence import StorageBackend, create_storage

logger = logging.getLogger(__name__)

# Global service instances (can be overridden with dependency injection)
_job_service: Optional[JobService] = None
_feedback_service: Optional[FeedbackService] = None
_storage: Optional[StorageBackend] = None


# ============================================================================
# Request/Response Models for the API
# ============================================================================


class JobSubmitRequest(BaseModel):
    """Request body for submitting a new job.

    Attributes:
        topics: List of topics to search for articles.
        sources: List of source names to fetch from.
        num_candidates: Number of candidate posts to generate.
        max_results: Dict mapping source names to max results.
        correlation_id: Optional idempotency key for deduplication.
    """

    topics: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    num_candidates: int = Field(default=3, ge=1, le=10)
    max_results: Optional[dict] = None
    correlation_id: Optional[str] = None


class JobListResponse(BaseModel):
    """Response for job list endpoint.

    Attributes:
        jobs: List of job status responses.
        total: Total number of jobs matching the filter.
    """

    jobs: List[JobStatusResponse]
    total: int


class PreviewResponse(BaseModel):
    """Response for markdown preview endpoint.

    Attributes:
        success: Whether the preview is available.
        preview: The markdown preview data.
        message: Status message.
    """

    success: bool
    preview: Optional[MarkdownPreview] = None
    message: str


class ApprovePostRequest(BaseModel):
    """Request body for approving a post.

    Attributes:
        feedback: Optional general feedback comment.
        ratings: Optional structured ratings for different aspects.
        actor: Optional identifier for who is approving.
    """

    feedback: Optional[str] = None
    ratings: List[FeedbackRating] = Field(default_factory=list)
    actor: Optional[str] = None


class RejectPostRequest(BaseModel):
    """Request body for rejecting a post.

    Attributes:
        feedback: Required feedback explaining rejection reason.
        categories: Categories of issues identified.
        ratings: Optional structured ratings for different aspects.
        actor: Optional identifier for who is rejecting.
    """

    feedback: str
    categories: List[FeedbackCategory] = Field(default_factory=list)
    ratings: List[FeedbackRating] = Field(default_factory=list)
    actor: Optional[str] = None


class RevisionPostRequest(BaseModel):
    """Request body for requesting revision.

    Attributes:
        feedback: Required feedback explaining what needs revision.
        categories: Categories of issues to address.
        ratings: Optional structured ratings for different aspects.
        actor: Optional identifier for who is requesting revision.
    """

    feedback: str
    categories: List[FeedbackCategory] = Field(default_factory=list)
    ratings: List[FeedbackRating] = Field(default_factory=list)
    actor: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Health status (healthy/unhealthy).
        job_service: Job service availability.
        feedback_service: Feedback service availability.
        storage: Storage backend availability.
    """

    status: str
    job_service: bool
    feedback_service: bool
    storage: bool


# ============================================================================
# Dependency Injection Functions
# ============================================================================


def get_job_service() -> JobService:
    """Get or create the job service instance.

    Returns:
        The JobService instance.
    """
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service


def get_storage() -> StorageBackend:
    """Get or create the storage backend instance.

    Returns:
        The StorageBackend instance.
    """
    global _storage
    if _storage is None:
        _storage = create_storage()
    return _storage


def get_feedback_service(storage: StorageBackend = Depends(get_storage)) -> FeedbackService:
    """Get or create the feedback service instance.

    Args:
        storage: The storage backend (injected).

    Returns:
        The FeedbackService instance.
    """
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService(storage)
    return _feedback_service


def configure_services(
    job_service: Optional[JobService] = None,
    feedback_service: Optional[FeedbackService] = None,
    storage: Optional[StorageBackend] = None,
) -> None:
    """Configure service instances for dependency injection.

    This allows customizing the services used by the API, useful for
    testing or custom configurations.

    Args:
        job_service: Custom JobService instance.
        feedback_service: Custom FeedbackService instance.
        storage: Custom StorageBackend instance.
    """
    global _job_service, _feedback_service, _storage
    if job_service is not None:
        _job_service = job_service
    if feedback_service is not None:
        _feedback_service = feedback_service
    if storage is not None:
        _storage = storage


def reset_services() -> None:
    """Reset all service instances to None.

    Useful for testing to ensure fresh instances.
    """
    global _job_service, _feedback_service, _storage
    _job_service = None
    _feedback_service = None
    _storage = None


# ============================================================================
# API Router
# ============================================================================

router = APIRouter(tags=["Frontend API"])


# --- Health Check ---


@router.get("/health", response_model=HealthResponse)
async def health_check(
    job_service: JobService = Depends(get_job_service),
    storage: StorageBackend = Depends(get_storage),
) -> HealthResponse:
    """Check the health of the API and its dependencies.

    Returns:
        Health status of all components.
    """
    job_ok = job_service is not None
    storage_ok = storage is not None and storage.health_check()
    feedback_ok = True  # FeedbackService depends on storage

    all_ok = job_ok and storage_ok and feedback_ok

    return HealthResponse(
        status="healthy" if all_ok else "unhealthy",
        job_service=job_ok,
        feedback_service=feedback_ok,
        storage=storage_ok,
    )


# --- Job Endpoints ---


@router.post("/jobs", response_model=JobSubmitResponse, status_code=201)
async def submit_job(
    request: JobSubmitRequest,
    job_service: JobService = Depends(get_job_service),
) -> JobSubmitResponse:
    """Submit a new blog post generation job.

    If a correlation_id is provided and a job with that ID already exists,
    returns the existing job instead of creating a new one.

    Args:
        request: The job submission request.

    Returns:
        Job submission response with job details.
    """
    # Log only non-sensitive metadata
    logger.info(
        f"Submitting job: num_candidates={request.num_candidates}, "
        f"correlation_id={request.correlation_id}, "
        f"sources={request.sources}"
    )

    job_request = JobRequest(
        topics=request.topics,
        sources=request.sources,
        num_candidates=request.num_candidates,
        max_results=request.max_results,
        correlation_id=request.correlation_id,
    )

    response = job_service.submit_job(job_request)
    return response


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    job_service: JobService = Depends(get_job_service),
) -> JobListResponse:
    """List jobs with optional status filter.

    Args:
        status: Optional status filter.
        limit: Maximum number of jobs to return.

    Returns:
        List of job status responses.
    """
    jobs = job_service.list_jobs(status=status, limit=limit)
    return JobListResponse(jobs=jobs, total=len(jobs))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobStatusResponse:
    """Get the status of a job by ID.

    Args:
        job_id: The job identifier.

    Returns:
        Job status response.

    Raises:
        HTTPException: 404 if job not found.
    """
    response = job_service.get_job_status(job_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return response


@router.get("/jobs/correlation/{correlation_id}", response_model=JobStatusResponse)
async def get_job_by_correlation_id(
    correlation_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobStatusResponse:
    """Get job status by correlation ID.

    Args:
        correlation_id: The correlation ID to look up.

    Returns:
        Job status response.

    Raises:
        HTTPException: 404 if job not found.
    """
    response = job_service.get_job_by_correlation_id(correlation_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Job with correlation_id {correlation_id} not found")
    return response


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> None:
    """Delete a job.

    Args:
        job_id: The job identifier.

    Raises:
        HTTPException: 404 if job not found.
    """
    result = job_service.delete_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.post("/jobs/{job_id}/execute", response_model=JobStatusResponse)
async def execute_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobStatusResponse:
    """Execute a pending job synchronously.

    This runs the full blog post generation pipeline for a job.
    Only works for jobs in PENDING status.

    Args:
        job_id: The job identifier.

    Returns:
        Updated job status response.

    Raises:
        HTTPException: 404 if job not found, 400 if job not pending.
    """
    job = job_service.execute_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Get the full status response
    status = job_service.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found after execution")

    return status


# --- Preview Endpoints ---


@router.get("/jobs/{job_id}/preview", response_model=PreviewResponse)
async def get_markdown_preview(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> PreviewResponse:
    """Get the markdown preview for a completed job.

    Args:
        job_id: The job identifier.

    Returns:
        Preview response with markdown content.

    Raises:
        HTTPException: 404 if job not found.
    """
    status = job_service.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if status.status != JobStatus.COMPLETED:
        return PreviewResponse(
            success=False,
            preview=None,
            message=f"Job is not completed (status: {status.status.value})",
        )

    if status.result is None or status.result.markdown_preview is None:
        return PreviewResponse(
            success=False,
            preview=None,
            message="No preview available for this job",
        )

    return PreviewResponse(
        success=True,
        preview=status.result.markdown_preview,
        message="Preview available",
    )


# --- Approval Workflow Endpoints ---


@router.post("/posts/{post_id}/approve", response_model=FeedbackResponse)
async def approve_post(
    post_id: str,
    request: ApprovePostRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    """Approve a blog post.

    Args:
        post_id: The post identifier.
        request: Approval request with optional feedback.

    Returns:
        Feedback response with result.
    """
    approval_request = ApprovalRequest(
        post_id=post_id,
        feedback=request.feedback,
        ratings=request.ratings,
        actor=request.actor,
    )

    response = feedback_service.approve_post(approval_request)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


@router.post("/posts/{post_id}/reject", response_model=FeedbackResponse)
async def reject_post(
    post_id: str,
    request: RejectPostRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    """Reject a blog post.

    Args:
        post_id: The post identifier.
        request: Rejection request with required feedback.

    Returns:
        Feedback response with result.
    """
    rejection_request = RejectionRequest(
        post_id=post_id,
        feedback=request.feedback,
        categories=request.categories,
        ratings=request.ratings,
        actor=request.actor,
    )

    response = feedback_service.reject_post(rejection_request)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


@router.post("/posts/{post_id}/revision", response_model=FeedbackResponse)
async def request_revision(
    post_id: str,
    request: RevisionPostRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    """Request revision for a blog post.

    Args:
        post_id: The post identifier.
        request: Revision request with required feedback.

    Returns:
        Feedback response with result.
    """
    revision_request = RevisionRequest(
        post_id=post_id,
        feedback=request.feedback,
        categories=request.categories,
        ratings=request.ratings,
        actor=request.actor,
    )

    response = feedback_service.request_revision(revision_request)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


@router.get("/posts/{post_id}/feedback", response_model=List[FeedbackEntry])
async def get_post_feedback(
    post_id: str,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> List[FeedbackEntry]:
    """Get all feedback entries for a post.

    Args:
        post_id: The post identifier.

    Returns:
        List of feedback entries.
    """
    return feedback_service.get_post_feedback(post_id)


@router.get("/feedback/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackStats:
    """Get aggregated feedback statistics.

    Returns:
        Feedback statistics for learning and analysis.
    """
    return feedback_service.get_feedback_stats()


@router.get("/feedback/learning")
async def get_learning_data(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of entries"),
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> List[dict]:
    """Get structured data for feedback-based learning.

    Returns data suitable for training or refining content generation.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of learning data entries.
    """
    return feedback_service.get_learning_data(limit=limit)


# ============================================================================
# Application Factory
# ============================================================================


def create_app(
    title: str = "AI Blogger Frontend API",
    description: str = "RESTful API for AI Blogger job management and content workflow",
    version: str = "1.0.0",
    cors_origins: Optional[List[str]] = None,
    serve_frontend: bool = True,
    frontend_dir: Optional[str] = None,
) -> FastAPI:
    """Create a FastAPI application with the frontend API router.

    Args:
        title: API title.
        description: API description.
        version: API version.
        cors_origins: List of allowed CORS origins. Defaults to ["*"] for
            development convenience. For production, specify explicit origins
            like ["https://myapp.example.com"].
        serve_frontend: Whether to serve the frontend static files.
        frontend_dir: Path to the frontend build directory. If None, looks for
            'frontend/dist' relative to this file or the current directory.

    Returns:
        Configured FastAPI application.

    Warning:
        The default CORS configuration allows all origins, which is suitable
        for development but should be restricted in production environments.
    """
    import os
    from pathlib import Path

    app = FastAPI(
        title=title,
        description=description,
        version=version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Set system info for metrics
    set_system_info(version=version)

    # Configure CORS - defaults to permissive for development
    # Production deployments should specify explicit origins
    if cors_origins is None:
        cors_origins = ["*"]
        logger.warning("CORS configured with wildcard origin '*'. " "For production, specify explicit cors_origins.")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add metrics middleware for request tracking
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Middleware to track API request metrics."""
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Track metrics for API endpoints (exclude /metrics itself)
        if not request.url.path.startswith("/metrics"):
            track_api_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration=duration,
            )

        return response

    # Add Prometheus metrics endpoint
    if PROMETHEUS_AVAILABLE:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        @app.get("/metrics", include_in_schema=False)
        async def metrics():
            """Expose Prometheus metrics."""
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

    # Include the router
    app.include_router(router, prefix="/api")

    # Serve frontend static files if enabled
    if serve_frontend:
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        # Find the frontend directory
        if frontend_dir is None:
            # Look for frontend/dist relative to this file
            this_dir = Path(__file__).parent
            possible_paths = [
                this_dir.parent / "frontend" / "dist",  # Development: project_root/frontend/dist
                this_dir / "frontend" / "dist",  # Installed: package/frontend/dist
                Path.cwd() / "frontend" / "dist",  # Current directory
            ]
            for path in possible_paths:
                if path.exists() and (path / "index.html").exists():
                    frontend_dir = str(path)
                    break

        if frontend_dir and os.path.exists(frontend_dir):
            frontend_path = Path(frontend_dir)

            # Serve static assets
            if (frontend_path / "assets").exists():
                app.mount("/assets", StaticFiles(directory=str(frontend_path / "assets")), name="assets")

            # Serve other static files (favicon, etc.)
            @app.get("/vite.svg")
            async def serve_vite_svg():
                svg_path = frontend_path / "vite.svg"
                if svg_path.exists():
                    return FileResponse(str(svg_path), media_type="image/svg+xml")
                return FileResponse(str(frontend_path / "index.html"))

            # Serve index.html for SPA routing (catch-all for non-API routes)
            @app.get("/{full_path:path}")
            async def serve_spa(full_path: str):
                # Don't serve index.html for API routes or docs
                if full_path.startswith("api/") or full_path in ["docs", "redoc", "openapi.json"]:
                    return None
                return FileResponse(str(frontend_path / "index.html"))

            logger.info(f"Serving frontend from: {frontend_dir}")
        else:
            logger.warning(
                "Frontend directory not found. Run 'npm run build' in the frontend directory to build the frontend."
            )

    return app


# ============================================================================
# CLI Entry Point (for running standalone)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
