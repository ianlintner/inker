"""Job models for the Blog Post Job API.

These models support job submission, status tracking, and result retrieval
for blog post generation jobs.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of a blog post generation job."""

    PENDING = "pending"
    FETCHING = "fetching"
    GENERATING = "generating"
    SCORING = "scoring"
    REFINING = "refining"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRequest(BaseModel):
    """Request to create a new blog post generation job.

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


class JobError(BaseModel):
    """Error information for a failed job.

    Attributes:
        code: Error code identifier.
        message: Human-readable error message.
        details: Additional error context.
    """

    code: str
    message: str
    details: Optional[str] = None


class MarkdownPreview(BaseModel):
    """Preview of generated markdown content.

    Attributes:
        title: Blog post title.
        content: Full markdown content.
        word_count: Approximate word count.
        topic: Main topic of the post.
        sources: List of source URLs used.
    """

    title: str
    content: str
    word_count: int
    topic: str
    sources: List[str]


class ScoringInfo(BaseModel):
    """Scoring information for the generated post.

    Attributes:
        relevance: Relevance score (0-10).
        originality: Originality score (0-10).
        depth: Depth score (0-10).
        clarity: Clarity score (0-10).
        engagement: Engagement score (0-10).
        total: Total weighted score.
        reasoning: Explanation of scores.
    """

    relevance: float
    originality: float
    depth: float
    clarity: float
    engagement: float
    total: float
    reasoning: str


class JobResult(BaseModel):
    """Result of a completed blog post generation job.

    Attributes:
        markdown_preview: Preview of the generated markdown.
        scoring: Scoring information for the post.
        articles_fetched: Number of articles fetched.
        candidates_generated: Number of candidate posts generated.
    """

    markdown_preview: MarkdownPreview
    scoring: ScoringInfo
    articles_fetched: int
    candidates_generated: int


class Job(BaseModel):
    """A blog post generation job with full state.

    Attributes:
        id: Unique job identifier.
        correlation_id: Optional idempotency key for deduplication.
        status: Current job status.
        request: Original job request.
        result: Job result (when completed).
        error: Error info (when failed).
        created_at: Job creation timestamp.
        updated_at: Last update timestamp.
        started_at: Job start timestamp.
        completed_at: Job completion timestamp.
    """

    id: str
    correlation_id: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    request: JobRequest
    result: Optional[JobResult] = None
    error: Optional[JobError] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobSubmitResponse(BaseModel):
    """Response when a job is submitted.

    Attributes:
        job_id: Unique identifier for the job.
        correlation_id: The correlation ID (if provided).
        status: Initial job status.
        message: Status message.
        is_duplicate: Whether this is a duplicate request.
    """

    job_id: str
    correlation_id: Optional[str] = None
    status: JobStatus
    message: str
    is_duplicate: bool = False


class JobStatusResponse(BaseModel):
    """Response for job status queries.

    Attributes:
        job_id: Unique identifier for the job.
        correlation_id: The correlation ID (if provided).
        status: Current job status.
        created_at: Job creation timestamp.
        updated_at: Last update timestamp.
        started_at: Job start timestamp.
        completed_at: Job completion timestamp.
        result: Job result (when completed).
        error: Error info (when failed).
    """

    job_id: str
    correlation_id: Optional[str] = None
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[JobResult] = None
    error: Optional[JobError] = None
