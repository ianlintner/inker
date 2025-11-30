"""Redis queue backend implementation.

Provides a high-performance, distributed job queue using Redis.
Uses sorted sets for priority queuing and atomic operations for reliability.

Requires: redis
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    import redis as redis_lib

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis_lib = None  # type: ignore

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


class RedisQueue(QueueBackend):
    """Redis-based queue backend.

    Uses sorted sets for priority-based queuing with efficient
    O(log N) operations.
    """

    def __init__(self, config: QueueConfig):
        """Initialize Redis queue.

        Args:
            config: Queue configuration with connection_string.

        Raises:
            ImportError: If redis is not installed.
            ValueError: If connection_string is not provided.
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis is required for Redis queue. Install with: pip install redis")

        if not config.connection_string:
            raise ValueError("connection_string is required for Redis queue")

        self.config = config
        self._client: Optional[Any] = None
        self._initialized = False

        # Key prefixes for different data types
        self._prefix = config.extra.get("key_prefix", "inker:queue")
        self._job_key = f"{self._prefix}:job"
        self._pending_key = f"{self._prefix}:pending"
        self._processing_key = f"{self._prefix}:processing"
        self._correlation_key = f"{self._prefix}:correlation"

    def _get_client(self) -> Any:
        """Get or create the Redis client."""
        if self._client is None:
            self._client = redis_lib.from_url(
                self.config.connection_string,
                decode_responses=True,
            )
        return self._client

    def initialize(self) -> None:
        """Initialize the Redis queue."""
        if self._initialized:
            return

        # Test connection
        client = self._get_client()
        client.ping()

        self._initialized = True
        logger.info("Redis queue initialized")

    def close(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _job_to_dict(self, job: QueueJob) -> Dict[str, Any]:
        """Convert a QueueJob to a dict for storage."""
        return {
            "id": job.id,
            "job_type": job.job_type,
            "payload": json.dumps(job.payload),
            "status": job.status.value,
            "priority": job.priority,
            "correlation_id": job.correlation_id or "",
            "max_retries": job.max_retries,
            "retry_count": job.retry_count,
            "error_message": job.error_message or "",
            "result": json.dumps(job.result) if job.result else "",
            "metadata": json.dumps(job.metadata) if job.metadata else "",
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else "",
            "started_at": job.started_at.isoformat() if job.started_at else "",
            "completed_at": job.completed_at.isoformat() if job.completed_at else "",
            "locked_at": job.locked_at.isoformat() if job.locked_at else "",
            "locked_by": job.locked_by or "",
        }

    def _dict_to_job(self, data: Dict[str, Any]) -> QueueJob:
        """Convert a stored dict back to a QueueJob."""
        return QueueJob(
            id=data["id"],
            job_type=data["job_type"],
            payload=json.loads(data["payload"]) if data["payload"] else {},
            status=QueueJobStatus(data["status"]),
            priority=int(data["priority"]),
            correlation_id=data["correlation_id"] or None,
            max_retries=int(data["max_retries"]),
            retry_count=int(data["retry_count"]),
            error_message=data["error_message"] or None,
            result=json.loads(data["result"]) if data["result"] else None,
            metadata=json.loads(data["metadata"]) if data["metadata"] else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data["scheduled_at"] else None,
            started_at=datetime.fromisoformat(data["started_at"]) if data["started_at"] else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data["completed_at"] else None,
            locked_at=datetime.fromisoformat(data["locked_at"]) if data["locked_at"] else None,
            locked_by=data["locked_by"] or None,
        )

    def _get_score(self, priority: int, created_at: datetime) -> float:
        """Calculate score for sorted set ordering.

        Higher priority = lower score (dequeued first).
        For same priority, earlier created = lower score (FIFO).
        """
        # Priority is negated so higher priority = lower score
        # Timestamp is added as fraction to break ties
        timestamp = created_at.timestamp()
        return (-priority * 1e10) + timestamp

    # === Enqueue Operations ===

    def enqueue(self, job_create: QueueJobCreate) -> QueueJob:
        """Add a job to the queue."""
        client = self._get_client()
        job_id = str(uuid.uuid4())
        now = datetime.now()

        # Check for duplicate correlation ID
        if job_create.correlation_id:
            existing = client.get(f"{self._correlation_key}:{job_create.correlation_id}")
            if existing:
                raise ValueError(f"Job with correlation_id '{job_create.correlation_id}' already exists: {existing}")

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

        # Store job data
        job_data = self._job_to_dict(job)
        pipe = client.pipeline()
        pipe.hset(f"{self._job_key}:{job_id}", mapping=job_data)

        # Add to pending sorted set
        score = self._get_score(job.priority, job.created_at)
        pipe.zadd(self._pending_key, {job_id: score})

        # Store correlation ID mapping if provided
        if job_create.correlation_id:
            pipe.set(f"{self._correlation_key}:{job_create.correlation_id}", job_id)

        pipe.execute()

        logger.debug(f"Enqueued job {job_id} ({job_create.job_type})")
        return job

    def enqueue_batch(self, jobs: List[QueueJobCreate]) -> List[QueueJob]:
        """Add multiple jobs to the queue atomically."""
        client = self._get_client()
        result = []
        now = datetime.now()
        pipe = client.pipeline()

        for job_create in jobs:
            job_id = str(uuid.uuid4())

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

            job_data = self._job_to_dict(job)
            pipe.hset(f"{self._job_key}:{job_id}", mapping=job_data)

            score = self._get_score(job.priority, job.created_at)
            pipe.zadd(self._pending_key, {job_id: score})

            if job_create.correlation_id:
                pipe.set(f"{self._correlation_key}:{job_create.correlation_id}", job_id)

            result.append(job)

        pipe.execute()
        return result

    # === Dequeue Operations ===

    def dequeue(
        self,
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
    ) -> Optional[QueueJob]:
        """Dequeue and lock the next available job."""
        client = self._get_client()
        now = datetime.now()

        # Get candidates from pending queue (lowest score first)
        candidates = client.zrange(self._pending_key, 0, 9)  # Check first 10

        for job_id in candidates:
            job_data = client.hgetall(f"{self._job_key}:{job_id}")
            if not job_data:
                # Job was deleted, remove from queue
                client.zrem(self._pending_key, job_id)
                continue

            job = self._dict_to_job(job_data)

            # Skip if scheduled for future
            if job.scheduled_at and job.scheduled_at > now:
                continue

            # Skip if job type doesn't match filter
            if job_types and job.job_type not in job_types:
                continue

            # Try to atomically move from pending to processing
            pipe = client.pipeline()
            pipe.zrem(self._pending_key, job_id)
            pipe.zadd(self._processing_key, {job_id: now.timestamp()})

            # Update job status
            job.status = QueueJobStatus.PROCESSING
            job.started_at = now
            job.locked_at = now
            job.locked_by = worker_id
            job.updated_at = now

            pipe.hset(f"{self._job_key}:{job_id}", mapping=self._job_to_dict(job))
            results = pipe.execute()

            if results[0] > 0:  # Successfully removed from pending
                logger.debug(f"Dequeued job {job_id} for worker {worker_id}")
                return job

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
        client = self._get_client()
        now = datetime.now()

        job_data = client.hgetall(f"{self._job_key}:{job_id}")
        if not job_data:
            return None

        job = self._dict_to_job(job_data)
        job.status = QueueJobStatus.COMPLETED
        job.result = result
        job.completed_at = now
        job.updated_at = now
        job.locked_at = None
        job.locked_by = None

        pipe = client.pipeline()
        pipe.hset(f"{self._job_key}:{job_id}", mapping=self._job_to_dict(job))
        pipe.zrem(self._processing_key, job_id)
        pipe.execute()

        logger.debug(f"Completed job {job_id}")
        return job

    def fail(
        self,
        job_id: str,
        error_message: str,
        error_type: Optional[str] = None,
    ) -> Optional[FailedJobInfo]:
        """Mark a job as failed."""
        client = self._get_client()
        now = datetime.now()

        job_data = client.hgetall(f"{self._job_key}:{job_id}")
        if not job_data:
            return None

        job = self._dict_to_job(job_data)
        job.retry_count += 1
        job.error_message = error_message
        job.updated_at = now
        job.locked_at = None
        job.locked_by = None

        will_retry = job.retry_count < job.max_retries
        next_retry_at = None

        pipe = client.pipeline()
        pipe.zrem(self._processing_key, job_id)

        if will_retry:
            retry_policy = self.config.default_retry_policy
            if retry_policy:
                delay = retry_policy.get_delay(job.retry_count - 1)
                next_retry_at = now + timedelta(seconds=delay)
                job.scheduled_at = next_retry_at

            job.status = QueueJobStatus.PENDING
            score = self._get_score(job.priority, job.created_at)
            pipe.zadd(self._pending_key, {job_id: score})
            logger.debug(f"Job {job_id} will retry at {next_retry_at}")
        else:
            job.status = QueueJobStatus.DEAD
            job.completed_at = now
            logger.debug(f"Job {job_id} exceeded max retries, marked as dead")

        pipe.hset(f"{self._job_key}:{job_id}", mapping=self._job_to_dict(job))
        pipe.execute()

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
        client = self._get_client()
        now = datetime.now()

        job_data = client.hgetall(f"{self._job_key}:{job_id}")
        if not job_data:
            return None

        job = self._dict_to_job(job_data)
        job.status = QueueJobStatus.PENDING
        job.updated_at = now
        job.locked_at = None
        job.locked_by = None
        job.started_at = None

        pipe = client.pipeline()
        pipe.hset(f"{self._job_key}:{job_id}", mapping=self._job_to_dict(job))
        pipe.zrem(self._processing_key, job_id)
        score = self._get_score(job.priority, job.created_at)
        pipe.zadd(self._pending_key, {job_id: score})
        pipe.execute()

        logger.debug(f"Released job {job_id}")
        return job

    # === Job Lookup ===

    def get_job(self, job_id: str) -> Optional[QueueJob]:
        """Get a job by ID."""
        client = self._get_client()
        job_data = client.hgetall(f"{self._job_key}:{job_id}")
        if job_data:
            return self._dict_to_job(job_data)
        return None

    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[QueueJob]:
        """Get a job by correlation ID."""
        client = self._get_client()
        job_id = client.get(f"{self._correlation_key}:{correlation_id}")
        if job_id:
            return self.get_job(job_id)
        return None

    def update_job(self, job_id: str, update: QueueJobUpdate) -> Optional[QueueJob]:
        """Update a job's fields."""
        client = self._get_client()

        job_data = client.hgetall(f"{self._job_key}:{job_id}")
        if not job_data:
            return None

        job = self._dict_to_job(job_data)

        if update.status is not None:
            job.status = update.status
        if update.error_message is not None:
            job.error_message = update.error_message
        if update.result is not None:
            job.result = update.result
        if update.metadata is not None:
            job.metadata = update.metadata

        job.updated_at = datetime.now()

        client.hset(f"{self._job_key}:{job_id}", mapping=self._job_to_dict(job))
        return job

    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the queue."""
        client = self._get_client()

        job_data = client.hgetall(f"{self._job_key}:{job_id}")
        if not job_data:
            return False

        job = self._dict_to_job(job_data)

        pipe = client.pipeline()
        pipe.delete(f"{self._job_key}:{job_id}")
        pipe.zrem(self._pending_key, job_id)
        pipe.zrem(self._processing_key, job_id)

        if job.correlation_id:
            pipe.delete(f"{self._correlation_key}:{job.correlation_id}")

        pipe.execute()

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
        client = self._get_client()

        # Get all job IDs from both queues
        pending_ids = client.zrange(self._pending_key, 0, -1)
        processing_ids = client.zrange(self._processing_key, 0, -1)
        all_ids = set(pending_ids) | set(processing_ids)

        # Also get completed/dead jobs by scanning (less efficient but complete)
        # For production, consider maintaining additional sets
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=f"{self._job_key}:*", count=100)
            for key in keys:
                job_id = key.replace(f"{self._job_key}:", "")
                all_ids.add(job_id)
            if cursor == 0:
                break

        jobs = []
        for job_id in all_ids:
            job_data = client.hgetall(f"{self._job_key}:{job_id}")
            if job_data:
                job = self._dict_to_job(job_data)

                # Apply filters
                if status is not None and job.status != status:
                    continue
                if job_type is not None and job.job_type != job_type:
                    continue

                jobs.append(job)

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        # Apply pagination
        return jobs[offset : offset + limit]

    # === Queue Maintenance ===

    def requeue_stale_jobs(self, stale_threshold_seconds: int = 300) -> int:
        """Requeue jobs that have been locked too long."""
        client = self._get_client()
        threshold = time.time() - stale_threshold_seconds

        # Get jobs from processing set that are older than threshold
        stale_ids = client.zrangebyscore(self._processing_key, "-inf", threshold)

        count = 0
        for job_id in stale_ids:
            job = self.release(job_id)
            if job:
                count += 1
                logger.debug(f"Requeued stale job {job_id}")

        if count > 0:
            logger.info(f"Requeued {count} stale jobs")
        return count

    def purge_completed(self, older_than_seconds: int = 86400) -> int:
        """Remove completed jobs older than threshold."""
        client = self._get_client()
        threshold = datetime.now() - timedelta(seconds=older_than_seconds)

        count = 0
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=f"{self._job_key}:*", count=100)
            for key in keys:
                job_data = client.hgetall(key)
                if job_data:
                    job = self._dict_to_job(job_data)
                    if job.status == QueueJobStatus.COMPLETED and job.completed_at and job.completed_at < threshold:
                        self.delete_job(job.id)
                        count += 1
            if cursor == 0:
                break

        if count > 0:
            logger.info(f"Purged {count} completed jobs")
        return count

    def purge_dead(self, older_than_seconds: int = 604800) -> int:
        """Remove dead jobs older than threshold."""
        client = self._get_client()
        threshold = datetime.now() - timedelta(seconds=older_than_seconds)

        count = 0
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=f"{self._job_key}:*", count=100)
            for key in keys:
                job_data = client.hgetall(key)
                if job_data:
                    job = self._dict_to_job(job_data)
                    if job.status == QueueJobStatus.DEAD and job.completed_at and job.completed_at < threshold:
                        self.delete_job(job.id)
                        count += 1
            if cursor == 0:
                break

        if count > 0:
            logger.info(f"Purged {count} dead jobs")
        return count

    # === Statistics ===

    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        client = self._get_client()

        pending_count = client.zcard(self._pending_key)
        processing_count = client.zcard(self._processing_key)

        # Count other statuses by scanning
        status_counts: Dict[QueueJobStatus, int] = {
            QueueJobStatus.PENDING: pending_count,
            QueueJobStatus.PROCESSING: processing_count,
            QueueJobStatus.COMPLETED: 0,
            QueueJobStatus.FAILED: 0,
            QueueJobStatus.RETRYING: 0,
            QueueJobStatus.DEAD: 0,
        }

        processing_times = []
        oldest_pending_age = None
        now = datetime.now()

        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=f"{self._job_key}:*", count=100)
            for key in keys:
                job_data = client.hgetall(key)
                if job_data:
                    job = self._dict_to_job(job_data)

                    if job.status in (QueueJobStatus.COMPLETED, QueueJobStatus.DEAD):
                        status_counts[job.status] += 1

                    if job.status == QueueJobStatus.COMPLETED and job.started_at and job.completed_at:
                        duration = (job.completed_at - job.started_at).total_seconds()
                        processing_times.append(duration)

                    if job.status == QueueJobStatus.PENDING:
                        age = (now - job.created_at).total_seconds()
                        if oldest_pending_age is None or age > oldest_pending_age:
                            oldest_pending_age = age
            if cursor == 0:
                break

        total_jobs = sum(status_counts.values())
        avg_processing_time = None
        if processing_times:
            avg_processing_time = sum(processing_times) / len(processing_times)

        return QueueStats(
            total_jobs=total_jobs,
            pending_jobs=status_counts[QueueJobStatus.PENDING],
            processing_jobs=status_counts[QueueJobStatus.PROCESSING],
            completed_jobs=status_counts[QueueJobStatus.COMPLETED],
            failed_jobs=status_counts[QueueJobStatus.FAILED],
            retrying_jobs=status_counts[QueueJobStatus.RETRYING],
            dead_jobs=status_counts[QueueJobStatus.DEAD],
            avg_processing_time_seconds=avg_processing_time,
            oldest_pending_job_age_seconds=oldest_pending_age,
        )

    # === Health Check ===

    def health_check(self) -> bool:
        """Check if the queue backend is healthy."""
        try:
            client = self._get_client()
            client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis queue health check failed: {e}")
            return False
