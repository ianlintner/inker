"""PostgreSQL queue backend implementation.

Provides a distributed, persistent job queue using PostgreSQL.
Uses SKIP LOCKED for efficient concurrent job dequeuing.

Requires: psycopg2-binary or psycopg2
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None  # type: ignore

if TYPE_CHECKING:
    import psycopg2.extensions
    import psycopg2.pool

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


# Schema version for migrations
SCHEMA_VERSION = 1


class PostgresQueue(QueueBackend):
    """PostgreSQL-based queue backend.

    Uses connection pooling and SKIP LOCKED for efficient,
    concurrent job processing.
    """

    def __init__(self, config: QueueConfig):
        """Initialize PostgreSQL queue.

        Args:
            config: Queue configuration with connection_string.

        Raises:
            ImportError: If psycopg2 is not installed.
            ValueError: If connection_string is not provided.
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgreSQL queue. Install with: pip install psycopg2-binary")

        if not config.connection_string:
            raise ValueError("connection_string is required for PostgreSQL queue")

        self.config = config
        self._pool: Optional[Any] = None
        self._pool_lock = threading.RLock()
        self._initialized = False

    def _get_pool(self) -> Any:
        """Get or create the connection pool."""
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    pool_size = self.config.extra.get("pool_size", 5)
                    self._pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=1,
                        maxconn=pool_size,
                        dsn=self.config.connection_string,
                    )
        return self._pool

    @contextmanager
    def _connection(self) -> Generator[Any, None, None]:
        """Context manager for database connection from pool."""
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            yield conn
        finally:
            pool.putconn(conn)

    @contextmanager
    def _cursor(self, commit: bool = True) -> Generator[Any, None, None]:
        """Context manager for database cursor with auto-commit."""
        with self._connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def initialize(self) -> None:
        """Initialize the database schema."""
        with self._pool_lock:
            if self._initialized:
                return

            with self._cursor() as cursor:
                # Create schema version table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queue_schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL
                    )
                """
                )

                # Check current version
                cursor.execute("SELECT MAX(version) FROM queue_schema_version")
                row = cursor.fetchone()
                current_version = row["max"] if row and row["max"] else 0

                if current_version < SCHEMA_VERSION:
                    self._run_migrations(cursor, current_version)

            self._initialized = True
            logger.info("PostgreSQL queue initialized")

    def _run_migrations(self, cursor: Any, from_version: int) -> None:
        """Run database migrations."""
        if from_version < 1:
            # Create enum type for job status
            cursor.execute(
                """
                DO $$ BEGIN
                    CREATE TYPE queue_job_status AS ENUM (
                        'pending', 'processing', 'completed', 'failed', 'retrying', 'dead'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """
            )

            # Queue jobs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS queue_jobs (
                    id UUID PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status queue_job_status NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 0,
                    correlation_id TEXT UNIQUE,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    result JSONB,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    scheduled_at TIMESTAMPTZ,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    locked_at TIMESTAMPTZ,
                    locked_by TEXT
                )
            """
            )

            # Indexes for efficient dequeuing
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_jobs_dequeue
                ON queue_jobs (priority DESC, created_at ASC)
                WHERE status = 'pending'
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_jobs_status
                ON queue_jobs (status)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_jobs_job_type
                ON queue_jobs (job_type)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_jobs_scheduled
                ON queue_jobs (scheduled_at)
                WHERE scheduled_at IS NOT NULL AND status = 'pending'
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_jobs_locked
                ON queue_jobs (locked_at)
                WHERE status = 'processing'
            """
            )

            # Record migration
            cursor.execute(
                "INSERT INTO queue_schema_version (version, applied_at) VALUES (%s, %s)",
                (1, datetime.now()),
            )

            logger.info("Applied PostgreSQL queue migration version 1")

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    def _row_to_job(self, row: Dict[str, Any]) -> QueueJob:
        """Convert a database row to a QueueJob."""
        return QueueJob(
            id=str(row["id"]),
            job_type=row["job_type"],
            payload=row["payload"] or {},
            status=QueueJobStatus(row["status"]),
            priority=row["priority"],
            correlation_id=row["correlation_id"],
            max_retries=row["max_retries"],
            retry_count=row["retry_count"],
            error_message=row["error_message"],
            result=row["result"],
            metadata=row["metadata"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            scheduled_at=row["scheduled_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            locked_at=row["locked_at"],
            locked_by=row["locked_by"],
        )

    # === Enqueue Operations ===

    def enqueue(self, job_create: QueueJobCreate) -> QueueJob:
        """Add a job to the queue."""
        job_id = str(uuid.uuid4())
        now = datetime.now()

        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO queue_jobs (
                    id, job_type, payload, status, priority, correlation_id,
                    max_retries, metadata, created_at, updated_at, scheduled_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """,
                (
                    job_id,
                    job_create.job_type,
                    json.dumps(job_create.payload),
                    QueueJobStatus.PENDING.value,
                    job_create.priority,
                    job_create.correlation_id,
                    job_create.max_retries,
                    json.dumps(job_create.metadata) if job_create.metadata else None,
                    now,
                    now,
                    job_create.scheduled_at,
                ),
            )
            row = cursor.fetchone()

        logger.debug(f"Enqueued job {job_id} ({job_create.job_type})")
        return self._row_to_job(row)

    def enqueue_batch(self, jobs: List[QueueJobCreate]) -> List[QueueJob]:
        """Add multiple jobs to the queue atomically."""
        result = []
        now = datetime.now()

        with self._cursor() as cursor:
            for job_create in jobs:
                job_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO queue_jobs (
                        id, job_type, payload, status, priority, correlation_id,
                        max_retries, metadata, created_at, updated_at, scheduled_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """,
                    (
                        job_id,
                        job_create.job_type,
                        json.dumps(job_create.payload),
                        QueueJobStatus.PENDING.value,
                        job_create.priority,
                        job_create.correlation_id,
                        job_create.max_retries,
                        json.dumps(job_create.metadata) if job_create.metadata else None,
                        now,
                        now,
                        job_create.scheduled_at,
                    ),
                )
                row = cursor.fetchone()
                result.append(self._row_to_job(row))

        return result

    # === Dequeue Operations ===

    def dequeue(
        self,
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
    ) -> Optional[QueueJob]:
        """Dequeue and lock the next available job using SKIP LOCKED."""
        now = datetime.now()

        # Build the query with optional job type filter
        query = """
            UPDATE queue_jobs
            SET status = %s,
                started_at = %s,
                locked_at = %s,
                locked_by = %s,
                updated_at = %s
            WHERE id = (
                SELECT id FROM queue_jobs
                WHERE status = 'pending'
                AND (scheduled_at IS NULL OR scheduled_at <= %s)
        """
        params: List[Any] = [
            QueueJobStatus.PROCESSING.value,
            now,
            now,
            worker_id,
            now,
            now,
        ]

        if job_types:
            placeholders = ", ".join(["%s"] * len(job_types))
            query += f" AND job_type IN ({placeholders})"
            params.extend(job_types)

        query += """
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        """

        with self._cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()

        if row:
            logger.debug(f"Dequeued job {row['id']} for worker {worker_id}")
            return self._row_to_job(row)
        return None

    def dequeue_batch(
        self,
        count: int,
        job_types: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
    ) -> List[QueueJob]:
        """Dequeue and lock multiple jobs at once using SKIP LOCKED."""
        now = datetime.now()

        # Build the query with optional job type filter
        query = """
            UPDATE queue_jobs
            SET status = %s,
                started_at = %s,
                locked_at = %s,
                locked_by = %s,
                updated_at = %s
            WHERE id IN (
                SELECT id FROM queue_jobs
                WHERE status = 'pending'
                AND (scheduled_at IS NULL OR scheduled_at <= %s)
        """
        params: List[Any] = [
            QueueJobStatus.PROCESSING.value,
            now,
            now,
            worker_id,
            now,
            now,
        ]

        if job_types:
            placeholders = ", ".join(["%s"] * len(job_types))
            query += f" AND job_type IN ({placeholders})"
            params.extend(job_types)

        query += """
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        """
        params.append(count)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_job(row) for row in rows]

    # === Job Status Management ===

    def complete(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> Optional[QueueJob]:
        """Mark a job as completed successfully."""
        now = datetime.now()

        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE queue_jobs
                SET status = %s,
                    result = %s,
                    completed_at = %s,
                    updated_at = %s,
                    locked_at = NULL,
                    locked_by = NULL
                WHERE id = %s
                RETURNING *
            """,
                (
                    QueueJobStatus.COMPLETED.value,
                    json.dumps(result) if result else None,
                    now,
                    now,
                    job_id,
                ),
            )
            row = cursor.fetchone()

        if row:
            logger.debug(f"Completed job {job_id}")
            return self._row_to_job(row)
        return None

    def fail(
        self,
        job_id: str,
        error_message: str,
        error_type: Optional[str] = None,
    ) -> Optional[FailedJobInfo]:
        """Mark a job as failed."""
        now = datetime.now()

        # First get the job to check retry count
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM queue_jobs WHERE id = %s FOR UPDATE", (job_id,))
            row = cursor.fetchone()

            if not row:
                return None

            new_retry_count = row["retry_count"] + 1
            will_retry = new_retry_count < row["max_retries"]
            next_retry_at = None

            if will_retry:
                # Calculate retry delay
                retry_policy = self.config.default_retry_policy
                if retry_policy:
                    delay = retry_policy.get_delay(new_retry_count - 1)
                    next_retry_at = now + timedelta(seconds=delay)

                cursor.execute(
                    """
                    UPDATE queue_jobs
                    SET status = %s,
                        retry_count = %s,
                        error_message = %s,
                        scheduled_at = %s,
                        updated_at = %s,
                        locked_at = NULL,
                        locked_by = NULL
                    WHERE id = %s
                """,
                    (
                        QueueJobStatus.PENDING.value,
                        new_retry_count,
                        error_message,
                        next_retry_at,
                        now,
                        job_id,
                    ),
                )
                logger.debug(f"Job {job_id} will retry at {next_retry_at}")
            else:
                cursor.execute(
                    """
                    UPDATE queue_jobs
                    SET status = %s,
                        retry_count = %s,
                        error_message = %s,
                        completed_at = %s,
                        updated_at = %s,
                        locked_at = NULL,
                        locked_by = NULL
                    WHERE id = %s
                """,
                    (
                        QueueJobStatus.DEAD.value,
                        new_retry_count,
                        error_message,
                        now,
                        now,
                        job_id,
                    ),
                )
                logger.debug(f"Job {job_id} exceeded max retries, marked as dead")

        return FailedJobInfo(
            job_id=job_id,
            attempt=new_retry_count,
            error_message=error_message,
            error_type=error_type,
            failed_at=now,
            will_retry=will_retry,
            next_retry_at=next_retry_at,
        )

    def release(self, job_id: str) -> Optional[QueueJob]:
        """Release a locked job back to pending state."""
        now = datetime.now()

        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE queue_jobs
                SET status = %s,
                    started_at = NULL,
                    locked_at = NULL,
                    locked_by = NULL,
                    updated_at = %s
                WHERE id = %s
                RETURNING *
            """,
                (QueueJobStatus.PENDING.value, now, job_id),
            )
            row = cursor.fetchone()

        if row:
            logger.debug(f"Released job {job_id}")
            return self._row_to_job(row)
        return None

    # === Job Lookup ===

    def get_job(self, job_id: str) -> Optional[QueueJob]:
        """Get a job by ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM queue_jobs WHERE id = %s", (job_id,))
            row = cursor.fetchone()

        if row:
            return self._row_to_job(row)
        return None

    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[QueueJob]:
        """Get a job by correlation ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM queue_jobs WHERE correlation_id = %s", (correlation_id,))
            row = cursor.fetchone()

        if row:
            return self._row_to_job(row)
        return None

    def update_job(self, job_id: str, update: QueueJobUpdate) -> Optional[QueueJob]:
        """Update a job's fields."""
        now = datetime.now()
        # Column names are hard-coded below - NOT derived from user input
        updates: List[str] = []
        params: List[Any] = []

        if update.status is not None:
            updates.append("status = %s")
            params.append(update.status.value)
        if update.error_message is not None:
            updates.append("error_message = %s")
            params.append(update.error_message)
        if update.result is not None:
            updates.append("result = %s")
            params.append(json.dumps(update.result))
        if update.metadata is not None:
            updates.append("metadata = %s")
            params.append(json.dumps(update.metadata))

        if updates:
            updates.append("updated_at = %s")
            params.append(now)
            params.append(job_id)

            with self._cursor() as cursor:
                cursor.execute(
                    f"UPDATE queue_jobs SET {', '.join(updates)} WHERE id = %s RETURNING *",
                    params,
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_job(row)

        return self.get_job(job_id)

    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the queue."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM queue_jobs WHERE id = %s", (job_id,))
            return cursor.rowcount > 0

    # === Queue Listing ===

    def list_jobs(
        self,
        status: Optional[QueueJobStatus] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[QueueJob]:
        """List jobs with optional filters."""
        query = "SELECT * FROM queue_jobs WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = %s"
            params.append(status.value)
        if job_type:
            query += " AND job_type = %s"
            params.append(job_type)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self._cursor() as cursor:
            cursor.execute(query, params)
            return [self._row_to_job(row) for row in cursor.fetchall()]

    # === Queue Maintenance ===

    def requeue_stale_jobs(self, stale_threshold_seconds: int = 300) -> int:
        """Requeue jobs that have been locked too long."""
        threshold = datetime.now() - timedelta(seconds=stale_threshold_seconds)

        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE queue_jobs
                SET status = 'pending',
                    started_at = NULL,
                    locked_at = NULL,
                    locked_by = NULL,
                    updated_at = NOW()
                WHERE status = 'processing'
                AND locked_at < %s
            """,
                (threshold,),
            )
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Requeued {count} stale jobs")
        return count

    def purge_completed(self, older_than_seconds: int = 86400) -> int:
        """Remove completed jobs older than threshold."""
        threshold = datetime.now() - timedelta(seconds=older_than_seconds)

        with self._cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM queue_jobs
                WHERE status = 'completed'
                AND completed_at < %s
            """,
                (threshold,),
            )
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Purged {count} completed jobs")
        return count

    def purge_dead(self, older_than_seconds: int = 604800) -> int:
        """Remove dead jobs older than threshold."""
        threshold = datetime.now() - timedelta(seconds=older_than_seconds)

        with self._cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM queue_jobs
                WHERE status = 'dead'
                AND completed_at < %s
            """,
                (threshold,),
            )
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Purged {count} dead jobs")
        return count

    # === Statistics ===

    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        with self._cursor() as cursor:
            # Status counts
            cursor.execute(
                """
                SELECT status::text, COUNT(*) as count
                FROM queue_jobs
                GROUP BY status
            """
            )
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            total_jobs = sum(status_counts.values())

            # Average processing time
            cursor.execute(
                """
                SELECT AVG(
                    EXTRACT(EPOCH FROM (completed_at - started_at))
                ) as avg_seconds
                FROM queue_jobs
                WHERE status = 'completed'
                AND started_at IS NOT NULL
                AND completed_at IS NOT NULL
            """
            )
            row = cursor.fetchone()
            avg_processing_time = row["avg_seconds"] if row and row["avg_seconds"] else None

            # Oldest pending job age
            cursor.execute(
                """
                SELECT EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) as age_seconds
                FROM queue_jobs
                WHERE status = 'pending'
            """
            )
            row = cursor.fetchone()
            oldest_pending_age = row["age_seconds"] if row and row["age_seconds"] else None

            return QueueStats(
                total_jobs=total_jobs,
                pending_jobs=status_counts.get(QueueJobStatus.PENDING.value, 0),
                processing_jobs=status_counts.get(QueueJobStatus.PROCESSING.value, 0),
                completed_jobs=status_counts.get(QueueJobStatus.COMPLETED.value, 0),
                failed_jobs=status_counts.get(QueueJobStatus.FAILED.value, 0),
                retrying_jobs=status_counts.get(QueueJobStatus.RETRYING.value, 0),
                dead_jobs=status_counts.get(QueueJobStatus.DEAD.value, 0),
                avg_processing_time_seconds=avg_processing_time,
                oldest_pending_job_age_seconds=oldest_pending_age,
            )

    # === Health Check ===

    def health_check(self) -> bool:
        """Check if the queue backend is healthy."""
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"PostgreSQL queue health check failed: {e}")
            return False
