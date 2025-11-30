"""SQLite repository implementation for job persistence.

This module provides a SQLite-based storage backend as the default/fallback option.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from ..job_models import (
    ApprovalRecord,
    ApprovalStatus,
    BlogPostJob,
    EditorComment,
    JobStats,
    JobStatus,
)
from .base import JobRepository

logger = logging.getLogger(__name__)


class SQLiteJobRepository(JobRepository):
    """SQLite-based job repository implementation.

    This provides a lightweight, file-based storage option suitable for
    development, testing, and small deployments.
    """

    def __init__(self, db_path: str = "ai_blogger_jobs.db"):
        """Initialize the SQLite repository.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = self._conn
        cursor = conn.cursor()

        # Create jobs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                correlation_id TEXT UNIQUE,
                status TEXT NOT NULL,
                topics TEXT NOT NULL,
                sources TEXT NOT NULL,
                num_candidates INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                title TEXT,
                content TEXT,
                score REAL,
                sources_used TEXT NOT NULL,
                approval_status TEXT NOT NULL
            )
        """
        )

        # Create approval_records table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_records (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """
        )

        # Create comments table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """
        )

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_correlation_id ON jobs(correlation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_approval_records_job_id ON approval_records(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_job_id ON comments(job_id)")

        conn.commit()

    def _job_to_row(self, job: BlogPostJob) -> dict:
        """Convert a BlogPostJob to a database row."""
        return {
            "id": str(job.id),
            "correlation_id": job.correlation_id,
            "status": job.status.value,
            "topics": json.dumps(job.topics),
            "sources": json.dumps(job.sources),
            "num_candidates": job.num_candidates,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "title": job.title,
            "content": job.content,
            "score": job.score,
            "sources_used": json.dumps(job.sources_used),
            "approval_status": job.approval_status.value,
        }

    def _row_to_job(self, row: sqlite3.Row) -> BlogPostJob:
        """Convert a database row to a BlogPostJob."""
        return BlogPostJob(
            id=UUID(row["id"]),
            correlation_id=row["correlation_id"],
            status=JobStatus(row["status"]),
            topics=json.loads(row["topics"]),
            sources=json.loads(row["sources"]),
            num_candidates=row["num_candidates"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            error_message=row["error_message"],
            title=row["title"],
            content=row["content"],
            score=row["score"],
            sources_used=json.loads(row["sources_used"]),
            approval_status=ApprovalStatus(row["approval_status"]),
            approval_records=[],  # Loaded separately if needed
        )

    def create_job(self, job: BlogPostJob) -> BlogPostJob:
        """Create a new job in the repository."""
        conn = self._conn
        cursor = conn.cursor()
        row = self._job_to_row(job)

        cursor.execute(
            """
            INSERT INTO jobs (
                id, correlation_id, status, topics, sources, num_candidates,
                created_at, updated_at, started_at, completed_at, error_message,
                title, content, score, sources_used, approval_status
            ) VALUES (
                :id, :correlation_id, :status, :topics, :sources, :num_candidates,
                :created_at, :updated_at, :started_at, :completed_at, :error_message,
                :title, :content, :score, :sources_used, :approval_status
            )
        """,
            row,
        )
        conn.commit()
        return job

    def get_job(self, job_id: UUID) -> Optional[BlogPostJob]:
        """Get a job by its ID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (str(job_id),))
        row = cursor.fetchone()
        return self._row_to_job(row) if row else None

    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[BlogPostJob]:
        """Get a job by its correlation ID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE correlation_id = ?", (correlation_id,))
        row = cursor.fetchone()
        return self._row_to_job(row) if row else None

    def update_job(self, job: BlogPostJob) -> BlogPostJob:
        """Update an existing job."""
        conn = self._conn
        cursor = conn.cursor()
        job.updated_at = datetime.now(timezone.utc)
        row = self._job_to_row(job)

        cursor.execute(
            """
            UPDATE jobs SET
                correlation_id = :correlation_id,
                status = :status,
                topics = :topics,
                sources = :sources,
                num_candidates = :num_candidates,
                updated_at = :updated_at,
                started_at = :started_at,
                completed_at = :completed_at,
                error_message = :error_message,
                title = :title,
                content = :content,
                score = :score,
                sources_used = :sources_used,
                approval_status = :approval_status
            WHERE id = :id
        """,
            row,
        )
        conn.commit()
        return job

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[BlogPostJob]:
        """List jobs with optional filtering and pagination."""
        cursor = self._conn.cursor()
        offset = (page - 1) * per_page

        if status:
            cursor.execute(
                """
                SELECT * FROM jobs WHERE status = ?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
                (status.value, per_page, offset),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
                (per_page, offset),
            )

        return [self._row_to_job(row) for row in cursor.fetchall()]

    def count_jobs(self, status: Optional[JobStatus] = None) -> int:
        """Count jobs with optional status filter."""
        cursor = self._conn.cursor()

        if status:
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = ?", (status.value,))
        else:
            cursor.execute("SELECT COUNT(*) FROM jobs")

        return cursor.fetchone()[0]

    def get_stats(self) -> JobStats:
        """Get statistics about job statuses."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT status, COUNT(*) as count FROM jobs GROUP BY status
        """
        )

        stats = JobStats()
        for row in cursor.fetchall():
            status = row["status"]
            count = row["count"]
            stats.total += count
            if status == JobStatus.PENDING.value:
                stats.pending = count
            elif status == JobStatus.IN_PROGRESS.value:
                stats.in_progress = count
            elif status == JobStatus.COMPLETED.value:
                stats.completed = count
            elif status == JobStatus.NEEDS_APPROVAL.value:
                stats.needs_approval = count
            elif status == JobStatus.APPROVED.value:
                stats.approved = count
            elif status == JobStatus.REJECTED.value:
                stats.rejected = count
            elif status == JobStatus.FAILED.value:
                stats.failed = count

        return stats

    def add_approval_record(self, record: ApprovalRecord) -> ApprovalRecord:
        """Add an approval record to a job."""
        conn = self._conn
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO approval_records (id, job_id, status, reviewer, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                str(record.id),
                str(record.job_id),
                record.status.value,
                record.reviewer,
                record.reason,
                record.created_at.isoformat(),
            ),
        )
        conn.commit()
        return record

    def add_comment(self, comment: EditorComment) -> EditorComment:
        """Add a comment to a job."""
        conn = self._conn
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO comments (id, job_id, author, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                str(comment.id),
                str(comment.job_id),
                comment.author,
                comment.content,
                comment.created_at.isoformat(),
            ),
        )
        conn.commit()
        return comment

    def get_comments(self, job_id: UUID) -> List[EditorComment]:
        """Get all comments for a job."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM comments WHERE job_id = ? ORDER BY created_at ASC
        """,
            (str(job_id),),
        )

        return [
            EditorComment(
                id=UUID(row["id"]),
                job_id=UUID(row["job_id"]),
                author=row["author"],
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in cursor.fetchall()
        ]

    def close(self) -> None:
        """Close the repository connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
