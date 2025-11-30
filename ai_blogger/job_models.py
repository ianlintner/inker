"""Data models for the job management and approval workflow.

This module defines the core data structures for:
- Blog post jobs (submission, tracking, status)
- Editor approval/rejection workflow
- Feedback and comments tracking
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Get current datetime in UTC with timezone info."""
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    """Status of a blog post generation job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NEEDS_APPROVAL = "needs_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    """Status of editorial approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EditorComment(BaseModel):
    """An editor comment on a blog post."""

    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    author: str
    content: str
    created_at: datetime = Field(default_factory=utc_now)


class ApprovalRecord(BaseModel):
    """Record of an approval or rejection decision."""

    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    status: ApprovalStatus
    reviewer: str
    reason: Optional[str] = None
    comments: List[EditorComment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class BlogPostJob(BaseModel):
    """A job for generating a blog post."""

    id: UUID = Field(default_factory=uuid4)
    correlation_id: Optional[str] = Field(
        default=None, description="Client-provided correlation ID for idempotency and tracing"
    )
    status: JobStatus = JobStatus.PENDING
    topics: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    num_candidates: int = 3
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    # Generated content
    title: Optional[str] = None
    content: Optional[str] = None
    score: Optional[float] = None
    sources_used: List[str] = Field(default_factory=list)
    # Approval tracking
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_records: List[ApprovalRecord] = Field(default_factory=list)


class JobSubmission(BaseModel):
    """Request model for submitting a new blog post job."""

    topics: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    num_candidates: int = 3
    correlation_id: Optional[str] = Field(default=None, description="Client-provided correlation ID for idempotency")


class JobResponse(BaseModel):
    """Response model for job operations."""

    id: UUID
    correlation_id: Optional[str] = None
    status: JobStatus
    topics: List[str]
    sources: List[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    title: Optional[str] = None
    score: Optional[float] = None
    approval_status: ApprovalStatus


class JobPreview(BaseModel):
    """Preview model for viewing generated blog post content."""

    id: UUID
    title: Optional[str] = None
    content: Optional[str] = None
    score: Optional[float] = None
    sources_used: List[str] = Field(default_factory=list)
    status: JobStatus
    approval_status: ApprovalStatus


class ApprovalRequest(BaseModel):
    """Request model for approving or rejecting a blog post."""

    status: ApprovalStatus
    reviewer: str
    reason: Optional[str] = None
    comments: Optional[List[str]] = None


class JobStats(BaseModel):
    """Statistics about job statuses."""

    total: int = 0
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    needs_approval: int = 0
    approved: int = 0
    rejected: int = 0
    failed: int = 0


class HistoricalJobsResponse(BaseModel):
    """Response model for historical jobs listing."""

    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    stats: JobStats
