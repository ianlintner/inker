"""API routes for the AI Blogger workflow.

This module defines the RESTful endpoints for:
- Job submission and management
- Post approval/rejection workflow
- Historical job listing and stats
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from ..job_models import (
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
    BlogPostJob,
    EditorComment,
    HistoricalJobsResponse,
    JobPreview,
    JobResponse,
    JobStats,
    JobStatus,
    JobSubmission,
)
from ..observability import record_job_completion, record_job_start
from ..persistence import JobRepository
from ..queue import JobQueue
from .dependencies import get_job_queue, get_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["jobs"])


def _job_to_response(job: BlogPostJob) -> JobResponse:
    """Convert a BlogPostJob to a JobResponse."""
    return JobResponse(
        id=job.id,
        correlation_id=job.correlation_id,
        status=job.status,
        topics=job.topics,
        sources=job.sources,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        title=job.title,
        score=job.score,
        approval_status=job.approval_status,
    )


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new blog post job",
    description="Submit a new job to generate a blog post. Supports idempotency via correlation_id.",
)
async def submit_job(
    submission: JobSubmission,
    x_correlation_id: Optional[str] = Header(None, description="Correlation ID for idempotency"),
    x_idempotency_key: Optional[str] = Header(None, description="Idempotency key (alias for correlation ID)"),
    repository: JobRepository = Depends(get_repository),
    queue: JobQueue = Depends(get_job_queue),
) -> JobResponse:
    """Submit a new blog post generation job."""
    # Determine correlation ID (header takes precedence over body)
    correlation_id = x_correlation_id or x_idempotency_key or submission.correlation_id

    # Check for existing job with same correlation ID (idempotency)
    if correlation_id:
        existing_job = repository.get_job_by_correlation_id(correlation_id)
        if existing_job:
            logger.info(f"Returning existing job for correlation_id={correlation_id}")
            return _job_to_response(existing_job)

    # Create new job
    job = BlogPostJob(
        correlation_id=correlation_id,
        topics=submission.topics or [],
        sources=submission.sources or [],
        num_candidates=submission.num_candidates,
    )

    # Persist and enqueue
    job = repository.create_job(job)
    queue.enqueue(job.id)

    record_job_start(str(job.id))
    logger.info(f"Created job {job.id} with correlation_id={correlation_id}")

    return _job_to_response(job)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Get the current status and metadata of a job.",
)
async def get_job(
    job_id: UUID,
    repository: JobRepository = Depends(get_repository),
) -> JobResponse:
    """Get the status of a specific job."""
    job = repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _job_to_response(job)


@router.get(
    "/jobs/{job_id}/preview",
    response_model=JobPreview,
    summary="Preview generated content",
    description="Get a preview of the generated blog post content.",
)
async def get_job_preview(
    job_id: UUID,
    repository: JobRepository = Depends(get_repository),
) -> JobPreview:
    """Get a preview of the generated blog post."""
    job = repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobPreview(
        id=job.id,
        title=job.title,
        content=job.content,
        score=job.score,
        sources_used=job.sources_used,
        status=job.status,
        approval_status=job.approval_status,
    )


@router.post(
    "/jobs/{job_id}/approve",
    response_model=JobResponse,
    summary="Approve or reject a blog post",
    description="Submit an approval or rejection decision for a completed blog post.",
)
async def approve_job(
    job_id: UUID,
    approval: ApprovalRequest,
    repository: JobRepository = Depends(get_repository),
) -> JobResponse:
    """Approve or reject a blog post."""
    job = repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status not in [JobStatus.COMPLETED, JobStatus.NEEDS_APPROVAL]:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not ready for approval (status: {job.status})",
        )

    # Create approval record
    record = ApprovalRecord(
        job_id=job_id,
        status=approval.status,
        reviewer=approval.reviewer,
        reason=approval.reason,
    )
    repository.add_approval_record(record)

    # Add comments if provided
    if approval.comments:
        for comment_text in approval.comments:
            comment = EditorComment(
                job_id=job_id,
                author=approval.reviewer,
                content=comment_text,
            )
            repository.add_comment(comment)

    # Update job status based on approval
    job.approval_status = approval.status
    if approval.status == ApprovalStatus.APPROVED:
        job.status = JobStatus.APPROVED
    elif approval.status == ApprovalStatus.REJECTED:
        job.status = JobStatus.REJECTED

    job = repository.update_job(job)

    record_job_completion(str(job_id), approval.status.value)
    logger.info(f"Job {job_id} {approval.status.value} by {approval.reviewer}")

    return _job_to_response(job)


@router.get(
    "/jobs/{job_id}/comments",
    response_model=list,
    summary="Get job comments",
    description="Get all editor comments for a job.",
)
async def get_job_comments(
    job_id: UUID,
    repository: JobRepository = Depends(get_repository),
) -> list:
    """Get all comments for a job."""
    job = repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    comments = repository.get_comments(job_id)
    return [
        {
            "id": str(c.id),
            "author": c.author,
            "content": c.content,
            "created_at": c.created_at.isoformat(),
        }
        for c in comments
    ]


@router.post(
    "/jobs/{job_id}/comments",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment",
    description="Add an editor comment to a job.",
)
async def add_job_comment(
    job_id: UUID,
    author: str,
    content: str,
    repository: JobRepository = Depends(get_repository),
) -> dict:
    """Add a comment to a job."""
    job = repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    comment = EditorComment(
        job_id=job_id,
        author=author,
        content=content,
    )
    comment = repository.add_comment(comment)

    return {
        "id": str(comment.id),
        "author": comment.author,
        "content": comment.content,
        "created_at": comment.created_at.isoformat(),
    }


@router.get(
    "/jobs",
    response_model=HistoricalJobsResponse,
    summary="List jobs",
    description="List jobs with optional filtering by status and pagination.",
)
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    repository: JobRepository = Depends(get_repository),
) -> HistoricalJobsResponse:
    """List jobs with filtering and pagination."""
    jobs = repository.list_jobs(status=status, page=page, per_page=per_page)
    total = repository.count_jobs(status=status)
    stats = repository.get_stats()

    return HistoricalJobsResponse(
        jobs=[_job_to_response(j) for j in jobs],
        total=total,
        page=page,
        per_page=per_page,
        stats=stats,
    )


@router.get(
    "/stats",
    response_model=JobStats,
    summary="Get job statistics",
    description="Get statistics about job statuses.",
)
async def get_stats(
    repository: JobRepository = Depends(get_repository),
) -> JobStats:
    """Get job statistics."""
    return repository.get_stats()


@router.get(
    "/health",
    summary="Health check",
    description="Check if the API is healthy.",
)
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get(
    "/ready",
    summary="Readiness check",
    description="Check if the API is ready to accept requests.",
)
async def readiness_check(
    repository: JobRepository = Depends(get_repository),
) -> dict:
    """Readiness check endpoint."""
    # Check if repository is accessible
    try:
        repository.get_stats()
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"

    return {
        "status": "ready" if db_status == "connected" else "not_ready",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
