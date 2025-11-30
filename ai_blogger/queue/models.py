"""Queue job models for the job queue layer.

These models support job enqueuing, dequeuing, status tracking,
retry logic, and transient failure handling.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueueJobStatus(str, Enum):
    """Status of a job in the queue."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"  # Exceeded max retries


class QueueJobCreate(BaseModel):
    """Input model for creating a new queue job.

    Attributes:
        job_type: Type of job (e.g., 'blog_post_generation').
        payload: Job payload data.
        priority: Job priority (higher = more important, default 0).
        max_retries: Maximum number of retry attempts.
        correlation_id: Optional idempotency key for deduplication.
        scheduled_at: Optional future execution time.
        metadata: Additional job metadata.
    """

    job_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=-100, le=100)
    max_retries: int = Field(default=3, ge=0, le=100)
    correlation_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class QueueJobUpdate(BaseModel):
    """Input model for updating a queue job.

    All fields are optional - only provided fields will be updated.
    """

    status: Optional[QueueJobStatus] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class QueueJob(BaseModel):
    """A job in the queue with full state.

    Attributes:
        id: Unique job identifier.
        job_type: Type of job (e.g., 'blog_post_generation').
        payload: Job payload data.
        status: Current job status.
        priority: Job priority.
        correlation_id: Optional idempotency key.
        max_retries: Maximum retry attempts.
        retry_count: Current retry count.
        error_message: Last error message (if failed).
        result: Job result (if completed).
        metadata: Additional job metadata.
        created_at: Job creation timestamp.
        updated_at: Last update timestamp.
        scheduled_at: Scheduled execution time.
        started_at: When job processing started.
        completed_at: When job completed (success or failure).
        locked_at: When job was locked for processing.
        locked_by: Worker ID that locked the job.
    """

    id: str
    job_type: str
    payload: Dict[str, Any]
    status: QueueJobStatus = QueueJobStatus.PENDING
    priority: int = 0
    correlation_id: Optional[str] = None
    max_retries: int = 3
    retry_count: int = 0
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None


class QueueStats(BaseModel):
    """Aggregated queue statistics.

    Attributes:
        total_jobs: Total number of jobs in queue.
        pending_jobs: Jobs waiting to be processed.
        processing_jobs: Jobs currently being processed.
        completed_jobs: Successfully completed jobs.
        failed_jobs: Jobs that failed.
        retrying_jobs: Jobs being retried.
        dead_jobs: Jobs that exceeded max retries.
        avg_processing_time_seconds: Average job processing time.
        oldest_pending_job_age_seconds: Age of oldest pending job.
    """

    total_jobs: int = 0
    pending_jobs: int = 0
    processing_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    retrying_jobs: int = 0
    dead_jobs: int = 0
    avg_processing_time_seconds: Optional[float] = None
    oldest_pending_job_age_seconds: Optional[float] = None


class RetryPolicy(BaseModel):
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        base_delay_seconds: Initial delay before first retry.
        max_delay_seconds: Maximum delay between retries.
        exponential_backoff: Whether to use exponential backoff.
        jitter: Whether to add random jitter to delays.
    """

    max_retries: int = Field(default=3, ge=0, le=100)
    base_delay_seconds: float = Field(default=1.0, ge=0.1)
    max_delay_seconds: float = Field(default=300.0, ge=1.0)
    exponential_backoff: bool = True
    jitter: bool = True

    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for a given retry attempt.

        Args:
            retry_count: Current retry attempt number (0-indexed).

        Returns:
            Delay in seconds before next retry.
        """
        import random

        if self.exponential_backoff:
            delay = self.base_delay_seconds * (2**retry_count)
        else:
            delay = self.base_delay_seconds

        if self.jitter:
            # Add up to 25% jitter
            jitter_amount = delay * 0.25 * random.random()
            delay += jitter_amount

        # Clamp to max_delay_seconds after applying jitter
        delay = min(delay, self.max_delay_seconds)

        return delay


class FailedJobInfo(BaseModel):
    """Information about a failed job attempt.

    Attributes:
        job_id: The job identifier.
        attempt: Attempt number (1-indexed).
        error_message: Error message from this attempt.
        error_type: Type/class of the error.
        failed_at: When this attempt failed.
        will_retry: Whether job will be retried.
        next_retry_at: When next retry will occur (if any).
    """

    job_id: str
    attempt: int
    error_message: str
    error_type: Optional[str] = None
    failed_at: datetime
    will_retry: bool
    next_retry_at: Optional[datetime] = None
