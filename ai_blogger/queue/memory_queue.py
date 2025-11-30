"""In-memory queue backend implementation.

Provides a thread-safe in-memory queue for testing and local development.
This is the default fallback when no external queue is configured.
"""

import heapq
import logging
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .base import QueueBackend, QueueConfig
from .models import (
    FailedJobInfo,
    QueueJob,
    QueueJobCreate,
    QueueJobStatus,
    QueueJobUpdate,
    QueueStats,
)

logger = logging.getLogger(__name__)


class MemoryQueue(QueueBackend):
    """In-memory queue backend.

    Thread-safe implementation using a priority queue (heap).
    Suitable for testing and single-process local development.

    Note: Data is not persisted and will be lost on restart.
    """

    def __init__(self, config: Optional[QueueConfig] = None):
        """Initialize in-memory queue.

        Args:
            config: Optional queue configuration.
        """
        self.config = config or QueueConfig(backend_type="memory")
        self._lock = threading.RLock()

        # Job storage by ID
        self._jobs: Dict[str, QueueJob] = {}

        # Priority queue: (priority * -1, created_at, job_id)
        # We negate priority so higher priority = smaller number = dequeued first
        self._pending_queue: List[Tuple[int, datetime, str]] = []

        # Correlation ID index
        self._correlation_index: Dict[str, str] = {}

        self._initialized = False

    def initialize(self) -> None:
        """Initialize the in-memory queue."""
        with self._lock:
            if self._initialized:
                return
            self._initialized = True
            logger.info("In-memory queue initialized")

    def close(self) -> None:
        """Close the queue (no-op for memory backend)."""
        pass

    def _add_to_pending_queue(self, job: QueueJob) -> None:
        """Add a job to the pending priority queue."""
        heapq.heappush(
            self._pending_queue,
            (-job.priority, job.created_at, job.id),
        )

    def _remove_from_pending_queue(self, job_id: str) -> None:
        """Remove a job from the pending queue (lazy deletion)."""
        # We use lazy deletion - jobs are removed when dequeued if status changed
        pass

    # === Enqueue Operations ===

    def enqueue(self, job_create: QueueJobCreate) -> QueueJob:
        """Add a job to the queue."""
        with self._lock:
            # Check for duplicate correlation ID
            if job_create.correlation_id:
                if job_create.correlation_id in self._correlation_index:
                    existing_id = self._correlation_index[job_create.correlation_id]
                    existing = self._jobs.get(existing_id)
                    if existing:
                        raise ValueError(
                            f"Job with correlation_id '{job_create.correlation_id}' " f"already exists: {existing_id}"
                        )

            job_id = str(uuid.uuid4())
            now = datetime.now()

            job = QueueJob(
                id=job_id,
                job_type=job_create.job_type,
                payload=job_create.payload,
                status=QueueJobStatus.PENDING,
                priority=job_create.priority,
                correlation_id=job_create.correlation_id,
                max_retries=job_create.max_retries,
                retry_count=0,
                metadata=job_create.metadata,
                created_at=now,
                updated_at=now,
                scheduled_at=job_create.scheduled_at,
            )

            self._jobs[job_id] = job
            self._add_to_pending_queue(job)

            if job_create.correlation_id:
                self._correlation_index[job_create.correlation_id] = job_id

            logger.debug(f"Enqueued job {job_id} ({job_create.job_type})")
            return job

    def enqueue_batch(self, jobs: List[QueueJobCreate]) -> List[QueueJob]:
        """Add multiple jobs to the queue atomically."""
        result = []
        with self._lock:
            for job_create in jobs:
                result.append(self.enqueue(job_create))
        return result

    # === Dequeue Operations ===

    def dequeue(
        self,
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
    ) -> Optional[QueueJob]:
        """Dequeue and lock the next available job."""
        with self._lock:
            now = datetime.now()

            # Collect jobs that don't match filter to re-add later
            skipped_jobs = []

            # Try to find a suitable job from the priority queue
            while self._pending_queue:
                _, _, job_id = self._pending_queue[0]
                job = self._jobs.get(job_id)

                # Skip if job was deleted or status changed
                if job is None or job.status != QueueJobStatus.PENDING:
                    heapq.heappop(self._pending_queue)
                    continue

                # Skip if scheduled for future
                if job.scheduled_at and job.scheduled_at > now:
                    heapq.heappop(self._pending_queue)
                    skipped_jobs.append(job)
                    continue

                # Skip if job type doesn't match filter
                if job_types and job.job_type not in job_types:
                    heapq.heappop(self._pending_queue)
                    skipped_jobs.append(job)
                    continue

                # Found a suitable job - lock it
                heapq.heappop(self._pending_queue)
                job.status = QueueJobStatus.PROCESSING
                job.started_at = now
                job.locked_at = now
                job.locked_by = worker_id
                job.updated_at = now

                # Re-add skipped jobs back to queue
                for skipped in skipped_jobs:
                    self._add_to_pending_queue(skipped)

                logger.debug(f"Dequeued job {job_id} for worker {worker_id}")
                return job

            # Re-add skipped jobs back to queue if no job was found
            for skipped in skipped_jobs:
                self._add_to_pending_queue(skipped)

            return None

    def dequeue_batch(
        self,
        count: int,
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
    ) -> List[QueueJob]:
        """Dequeue and lock multiple jobs at once."""
        result = []
        for _ in range(count):
            job = self.dequeue(job_types=job_types, worker_id=worker_id)
            if job is None:
                break
            result.append(job)
        return result

    # === Job Status Management ===

    def complete(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> Optional[QueueJob]:
        """Mark a job as completed successfully."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            now = datetime.now()
            job.status = QueueJobStatus.COMPLETED
            job.result = result
            job.completed_at = now
            job.updated_at = now
            job.locked_at = None
            job.locked_by = None

            logger.debug(f"Completed job {job_id}")
            return job

    def fail(
        self,
        job_id: str,
        error_message: str,
        error_type: Optional[str] = None,
    ) -> Optional[FailedJobInfo]:
        """Mark a job as failed."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            now = datetime.now()
            job.retry_count += 1
            job.error_message = error_message
            job.updated_at = now
            job.locked_at = None
            job.locked_by = None

            will_retry = job.retry_count < job.max_retries
            next_retry_at = None

            if will_retry:
                # Calculate retry delay using retry policy
                retry_policy = self.config.default_retry_policy
                if retry_policy:
                    delay = retry_policy.get_delay(job.retry_count - 1)
                    next_retry_at = now + timedelta(seconds=delay)
                    job.scheduled_at = next_retry_at
                job.status = QueueJobStatus.RETRYING
                # Add back to queue for retry
                self._add_to_pending_queue(job)
                # Mark as pending after adding to queue
                job.status = QueueJobStatus.PENDING
                logger.debug(f"Job {job_id} will retry at {next_retry_at}")
            else:
                job.status = QueueJobStatus.DEAD
                job.completed_at = now
                logger.debug(f"Job {job_id} exceeded max retries, marked as dead")

            return FailedJobInfo(
                job_id=job_id,
                attempt=job.retry_count,
                error_message=error_message,
                error_type=error_type,
                failed_at=now,
                will_retry=will_retry,
                next_retry_at=next_retry_at,
            )

    def release(self, job_id: str) -> Optional[QueueJob]:
        """Release a locked job back to pending state."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            now = datetime.now()
            job.status = QueueJobStatus.PENDING
            job.updated_at = now
            job.locked_at = None
            job.locked_by = None
            job.started_at = None

            # Add back to queue
            self._add_to_pending_queue(job)

            logger.debug(f"Released job {job_id}")
            return job

    # === Job Lookup ===

    def get_job(self, job_id: str) -> Optional[QueueJob]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[QueueJob]:
        """Get a job by correlation ID."""
        with self._lock:
            job_id = self._correlation_index.get(correlation_id)
            if job_id:
                return self._jobs.get(job_id)
            return None

    def update_job(self, job_id: str, update: QueueJobUpdate) -> Optional[QueueJob]:
        """Update a job's fields."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            if update.status is not None:
                job.status = update.status
            if update.error_message is not None:
                job.error_message = update.error_message
            if update.result is not None:
                job.result = update.result
            if update.metadata is not None:
                job.metadata = update.metadata

            job.updated_at = datetime.now()
            return job

    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the queue."""
        with self._lock:
            job = self._jobs.pop(job_id, None)
            if job is None:
                return False

            if job.correlation_id:
                self._correlation_index.pop(job.correlation_id, None)

            logger.debug(f"Deleted job {job_id}")
            return True

    # === Queue Listing ===

    def list_jobs(
        self,
        status: Optional[QueueJobStatus] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[QueueJob]:
        """List jobs with optional filters."""
        with self._lock:
            jobs = list(self._jobs.values())

            # Apply filters
            if status is not None:
                jobs = [j for j in jobs if j.status == status]
            if job_type is not None:
                jobs = [j for j in jobs if j.job_type == job_type]

            # Sort by created_at descending
            jobs.sort(key=lambda j: j.created_at, reverse=True)

            # Apply pagination
            return jobs[offset : offset + limit]

    # === Queue Maintenance ===

    def requeue_stale_jobs(self, stale_threshold_seconds: int = 300) -> int:
        """Requeue jobs that have been locked too long."""
        with self._lock:
            now = datetime.now()
            threshold = now - timedelta(seconds=stale_threshold_seconds)
            count = 0

            for job in self._jobs.values():
                if job.status == QueueJobStatus.PROCESSING and job.locked_at and job.locked_at < threshold:
                    job.status = QueueJobStatus.PENDING
                    job.locked_at = None
                    job.locked_by = None
                    job.started_at = None
                    job.updated_at = now
                    self._add_to_pending_queue(job)
                    count += 1
                    logger.debug(f"Requeued stale job {job.id}")

            return count

    def purge_completed(self, older_than_seconds: int = 86400) -> int:
        """Remove completed jobs older than threshold."""
        with self._lock:
            now = datetime.now()
            threshold = now - timedelta(seconds=older_than_seconds)
            to_delete = []

            for job_id, job in self._jobs.items():
                if job.status == QueueJobStatus.COMPLETED and job.completed_at and job.completed_at < threshold:
                    to_delete.append(job_id)

            for job_id in to_delete:
                job = self._jobs.pop(job_id)
                if job.correlation_id:
                    self._correlation_index.pop(job.correlation_id, None)

            return len(to_delete)

    def purge_dead(self, older_than_seconds: int = 604800) -> int:
        """Remove dead jobs older than threshold."""
        with self._lock:
            now = datetime.now()
            threshold = now - timedelta(seconds=older_than_seconds)
            to_delete = []

            for job_id, job in self._jobs.items():
                if job.status == QueueJobStatus.DEAD and job.completed_at and job.completed_at < threshold:
                    to_delete.append(job_id)

            for job_id in to_delete:
                job = self._jobs.pop(job_id)
                if job.correlation_id:
                    self._correlation_index.pop(job.correlation_id, None)

            return len(to_delete)

    # === Statistics ===

    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        with self._lock:
            status_counts: Dict[QueueJobStatus, int] = {}
            processing_times = []
            oldest_pending_age = None
            now = datetime.now()

            for job in self._jobs.values():
                status_counts[job.status] = status_counts.get(job.status, 0) + 1

                # Calculate processing time for completed jobs
                if job.status == QueueJobStatus.COMPLETED and job.started_at and job.completed_at:
                    duration = (job.completed_at - job.started_at).total_seconds()
                    processing_times.append(duration)

                # Track oldest pending job
                if job.status == QueueJobStatus.PENDING:
                    age = (now - job.created_at).total_seconds()
                    if oldest_pending_age is None or age > oldest_pending_age:
                        oldest_pending_age = age

            avg_processing_time = None
            if processing_times:
                avg_processing_time = sum(processing_times) / len(processing_times)

            return QueueStats(
                total_jobs=len(self._jobs),
                pending_jobs=status_counts.get(QueueJobStatus.PENDING, 0),
                processing_jobs=status_counts.get(QueueJobStatus.PROCESSING, 0),
                completed_jobs=status_counts.get(QueueJobStatus.COMPLETED, 0),
                failed_jobs=status_counts.get(QueueJobStatus.FAILED, 0),
                retrying_jobs=status_counts.get(QueueJobStatus.RETRYING, 0),
                dead_jobs=status_counts.get(QueueJobStatus.DEAD, 0),
                avg_processing_time_seconds=avg_processing_time,
                oldest_pending_job_age_seconds=oldest_pending_age,
            )

    # === Health Check ===

    def health_check(self) -> bool:
        """Check if the queue backend is healthy."""
        return True
