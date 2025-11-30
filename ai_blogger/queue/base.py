"""Abstract base class for queue backends.

This module defines the API contract that all queue backends must implement.
"""

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .models import (
    FailedJobInfo,
    QueueJob,
    QueueJobCreate,
    QueueJobStatus,
    QueueJobUpdate,
    QueueStats,
    RetryPolicy,
)


@dataclass
class QueueConfig:
    """Configuration for queue backends.

    Attributes:
        backend_type: Type of queue backend (memory, postgres, redis).
        connection_string: Connection string for the queue backend.
        default_retry_policy: Default retry policy for jobs.
        visibility_timeout_seconds: How long a job stays locked before timeout.
        poll_interval_seconds: How often to poll for new jobs.
        worker_id: Unique identifier for this worker instance.
        extra: Additional backend-specific configuration.
    """

    backend_type: str = "memory"
    connection_string: Optional[str] = None
    default_retry_policy: Optional[RetryPolicy] = None
    visibility_timeout_seconds: int = 300  # 5 minutes
    poll_interval_seconds: float = 1.0
    worker_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.default_retry_policy is None:
            self.default_retry_policy = RetryPolicy()


class QueueBackend(abc.ABC):
    """Abstract base class for queue backends.

    All queue backends must implement this interface to provide
    job queue functionality with enqueue, dequeue, and management operations.

    The interface supports:
    - Enqueue/dequeue operations
    - Job status tracking
    - Retry logic with exponential backoff
    - Transient failure handling
    - Statistics and monitoring
    """

    @abc.abstractmethod
    def initialize(self) -> None:
        """Initialize the queue backend.

        This should create tables/structures if they don't exist.
        """
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """Close the queue backend and release resources."""
        pass

    # === Enqueue Operations ===

    @abc.abstractmethod
    def enqueue(self, job: QueueJobCreate) -> QueueJob:
        """Add a job to the queue.

        Args:
            job: The job to enqueue.

        Returns:
            The created QueueJob with generated ID and timestamps.

        Raises:
            ValueError: If correlation_id already exists.
        """
        pass

    @abc.abstractmethod
    def enqueue_batch(self, jobs: List[QueueJobCreate]) -> List[QueueJob]:
        """Add multiple jobs to the queue atomically.

        Args:
            jobs: List of jobs to enqueue.

        Returns:
            List of created QueueJob objects.
        """
        pass

    # === Dequeue Operations ===

    @abc.abstractmethod
    def dequeue(
        self,
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
    ) -> Optional[QueueJob]:
        """Dequeue and lock the next available job.

        Gets the highest priority pending job that is ready for processing.
        The job is locked to prevent other workers from processing it.

        Args:
            job_types: Optional list of job types to filter by.
            worker_id: Optional worker identifier for tracking.

        Returns:
            QueueJob if available, None if queue is empty.
        """
        pass

    @abc.abstractmethod
    def dequeue_batch(
        self,
        count: int,
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
    ) -> List[QueueJob]:
        """Dequeue and lock multiple jobs at once.

        Args:
            count: Maximum number of jobs to dequeue.
            job_types: Optional list of job types to filter by.
            worker_id: Optional worker identifier for tracking.

        Returns:
            List of QueueJob objects (may be less than count if queue doesn't have enough).
        """
        pass

    # === Job Status Management ===

    @abc.abstractmethod
    def complete(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> Optional[QueueJob]:
        """Mark a job as completed successfully.

        Args:
            job_id: The job identifier.
            result: Optional result data from the job.

        Returns:
            Updated QueueJob or None if not found.
        """
        pass

    @abc.abstractmethod
    def fail(
        self,
        job_id: str,
        error_message: str,
        error_type: Optional[str] = None,
    ) -> Optional[FailedJobInfo]:
        """Mark a job as failed.

        If the job has retries remaining, it will be scheduled for retry.
        If max retries exceeded, job is marked as dead.

        Args:
            job_id: The job identifier.
            error_message: Error description.
            error_type: Optional error type/class name.

        Returns:
            FailedJobInfo with retry information, or None if job not found.
        """
        pass

    @abc.abstractmethod
    def release(self, job_id: str) -> Optional[QueueJob]:
        """Release a locked job back to pending state.

        Use this when a worker cannot complete a job but it shouldn't count
        as a failure (e.g., graceful shutdown).

        Args:
            job_id: The job identifier.

        Returns:
            Updated QueueJob or None if not found.
        """
        pass

    # === Job Lookup ===

    @abc.abstractmethod
    def get_job(self, job_id: str) -> Optional[QueueJob]:
        """Get a job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            QueueJob or None if not found.
        """
        pass

    @abc.abstractmethod
    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[QueueJob]:
        """Get a job by correlation ID.

        Args:
            correlation_id: The correlation ID to look up.

        Returns:
            QueueJob or None if not found.
        """
        pass

    @abc.abstractmethod
    def update_job(self, job_id: str, update: QueueJobUpdate) -> Optional[QueueJob]:
        """Update a job's fields.

        Args:
            job_id: The job identifier.
            update: The fields to update.

        Returns:
            Updated QueueJob or None if not found.
        """
        pass

    @abc.abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the queue.

        Args:
            job_id: The job identifier.

        Returns:
            True if deleted, False if not found.
        """
        pass

    # === Queue Listing ===

    @abc.abstractmethod
    def list_jobs(
        self,
        status: Optional[QueueJobStatus] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[QueueJob]:
        """List jobs with optional filters.

        Args:
            status: Optional status filter.
            job_type: Optional job type filter.
            limit: Maximum results to return.
            offset: Offset for pagination.

        Returns:
            List of QueueJob objects.
        """
        pass

    # === Queue Maintenance ===

    @abc.abstractmethod
    def requeue_stale_jobs(self, stale_threshold_seconds: int = 300) -> int:
        """Requeue jobs that have been locked too long.

        Jobs that have been processing longer than the threshold
        are assumed to be from dead workers and are requeued.

        Args:
            stale_threshold_seconds: How long before a locked job is considered stale.

        Returns:
            Number of jobs requeued.
        """
        pass

    @abc.abstractmethod
    def purge_completed(self, older_than_seconds: int = 86400) -> int:
        """Remove completed jobs older than threshold.

        Args:
            older_than_seconds: Age threshold in seconds.

        Returns:
            Number of jobs purged.
        """
        pass

    @abc.abstractmethod
    def purge_dead(self, older_than_seconds: int = 604800) -> int:
        """Remove dead jobs older than threshold.

        Args:
            older_than_seconds: Age threshold in seconds (default 7 days).

        Returns:
            Number of jobs purged.
        """
        pass

    # === Statistics ===

    @abc.abstractmethod
    def get_stats(self) -> QueueStats:
        """Get queue statistics.

        Returns:
            QueueStats with counts and metrics.
        """
        pass

    # === Health Check ===

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Check if the queue backend is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        pass

    # === Worker Utilities ===

    def process_jobs(
        self,
        handler: Callable[[QueueJob], Optional[Dict[str, Any]]],
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
        max_jobs: Optional[int] = None,
        stop_on_empty: bool = False,
    ) -> int:
        """Process jobs from the queue.

        This is a convenience method for simple job processing loops.
        For more control, use dequeue/complete/fail directly.

        Args:
            handler: Function that processes a job and returns result.
            job_types: Optional job types to process.
            worker_id: Optional worker identifier.
            max_jobs: Maximum jobs to process (None = unlimited).
            stop_on_empty: Stop when queue is empty vs. wait for more.

        Returns:
            Number of jobs processed.
        """
        import time

        jobs_processed = 0

        while True:
            if max_jobs is not None and jobs_processed >= max_jobs:
                break

            job = self.dequeue(job_types=job_types, worker_id=worker_id)

            if job is None:
                if stop_on_empty:
                    break
                time.sleep(1.0)  # Poll interval
                continue

            try:
                result = handler(job)
                self.complete(job.id, result)
                jobs_processed += 1
            except Exception as e:
                self.fail(job.id, str(e), type(e).__name__)
                jobs_processed += 1

        return jobs_processed
