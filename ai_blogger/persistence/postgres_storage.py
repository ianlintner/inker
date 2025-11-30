"""PostgreSQL storage backend implementation.

Provides a robust persistence layer using PostgreSQL.
This is the recommended storage backend for production use.

Requires: psycopg2-binary or psycopg2
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
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

from .base import StorageBackend, StorageConfig
from .models import (
    ApprovalStatus,
    BlogPost,
    BlogPostCreate,
    BlogPostUpdate,
    JobHistoryEntry,
    JobStats,
)

logger = logging.getLogger(__name__)


# Schema version for migrations
SCHEMA_VERSION = 1


class PostgresStorage(StorageBackend):
    """PostgreSQL-based storage backend.

    Uses connection pooling for efficient resource usage.
    """

    def __init__(self, config: StorageConfig):
        """Initialize PostgreSQL storage.

        Args:
            config: Storage configuration with connection_string.

        Raises:
            ImportError: If psycopg2 is not installed.
            ValueError: If connection_string is not provided.
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgreSQL storage. Install with: pip install psycopg2-binary")

        if not config.connection_string:
            raise ValueError("connection_string is required for PostgreSQL storage")

        self.config = config
        self._pool: Optional[Any] = None
        self._initialized = False

        if config.auto_migrate:
            self.initialize()

    def _get_pool(self) -> Any:
        """Get or create the connection pool."""
        if self._pool is None:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self.config.pool_size,
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
        if self._initialized:
            return

        with self._cursor() as cursor:
            # Create schema version table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL
                )
            """
            )

            # Check current version
            cursor.execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            current_version = row["max"] if row and row["max"] else 0

            if current_version < SCHEMA_VERSION:
                self._run_migrations(cursor, current_version)

        self._initialized = True
        logger.info("PostgreSQL storage initialized")

    def _run_migrations(self, cursor: Any, from_version: int) -> None:
        """Run database migrations."""
        if from_version < 1:
            # Create enum type for approval status
            cursor.execute(
                """
                DO $$ BEGIN
                    CREATE TYPE approval_status AS ENUM (
                        'pending', 'approved', 'rejected', 'revision_requested'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """
            )

            # Blog posts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS blog_posts (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    job_id TEXT,
                    approval_status approval_status NOT NULL DEFAULT 'pending',
                    approval_feedback TEXT,
                    scoring JSONB,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    approved_at TIMESTAMPTZ,
                    published_at TIMESTAMPTZ
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_job_id
                ON blog_posts(job_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_approval_status
                ON blog_posts(approval_status)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_topic
                ON blog_posts(topic)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_created_at
                ON blog_posts(created_at DESC)
            """
            )

            # Job history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS job_history (
                    id UUID PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    post_id UUID,
                    action TEXT NOT NULL,
                    previous_status TEXT,
                    new_status TEXT,
                    actor TEXT,
                    feedback TEXT,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_job_id
                ON job_history(job_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_post_id
                ON job_history(post_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_created_at
                ON job_history(created_at)
            """
            )

            # Record migration
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (%s, %s)",
                (1, datetime.now()),
            )

            logger.info("Applied PostgreSQL migration version 1")

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    def _row_to_post(self, row: Dict[str, Any]) -> BlogPost:
        """Convert a database row to a BlogPost."""
        return BlogPost(
            id=str(row["id"]),
            title=row["title"],
            content=row["content"],
            word_count=row["word_count"],
            topic=row["topic"],
            sources=row["sources"] or [],
            job_id=row["job_id"],
            approval_status=ApprovalStatus(row["approval_status"]),
            approval_feedback=row["approval_feedback"],
            scoring=row["scoring"],
            metadata=row["metadata"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
            published_at=row["published_at"],
        )

    def _row_to_history(self, row: Dict[str, Any]) -> JobHistoryEntry:
        """Convert a database row to a JobHistoryEntry."""
        return JobHistoryEntry(
            id=str(row["id"]),
            job_id=row["job_id"],
            post_id=str(row["post_id"]) if row["post_id"] else None,
            action=row["action"],
            previous_status=row["previous_status"],
            new_status=row["new_status"],
            actor=row["actor"],
            feedback=row["feedback"],
            metadata=row["metadata"],
            created_at=row["created_at"],
        )

    # === Blog Post Operations ===

    def create_post(self, post: BlogPostCreate) -> BlogPost:
        """Create a new blog post."""
        post_id = str(uuid.uuid4())
        now = datetime.now()
        word_count = len(post.content.split())

        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO blog_posts (
                    id, title, content, word_count, topic, sources, job_id,
                    approval_status, scoring, metadata, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """,
                (
                    post_id,
                    post.title,
                    post.content,
                    word_count,
                    post.topic,
                    json.dumps(post.sources),
                    post.job_id,
                    ApprovalStatus.PENDING.value,
                    json.dumps(post.scoring) if post.scoring else None,
                    json.dumps(post.metadata) if post.metadata else None,
                    now,
                    now,
                ),
            )
            row = cursor.fetchone()

        # Log history
        self.add_history_entry(
            job_id=post.job_id or post_id,
            post_id=post_id,
            action="post_created",
            new_status=ApprovalStatus.PENDING.value,
        )

        return self._row_to_post(row)

    def get_post(self, post_id: str) -> Optional[BlogPost]:
        """Get a blog post by ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM blog_posts WHERE id = %s", (post_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_post(row)
            return None

    def get_post_by_job_id(self, job_id: str) -> Optional[BlogPost]:
        """Get a blog post by its associated job ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM blog_posts WHERE job_id = %s", (job_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_post(row)
            return None

    def update_post(self, post_id: str, update: BlogPostUpdate) -> Optional[BlogPost]:
        """Update an existing blog post."""
        post = self.get_post(post_id)
        if not post:
            return None

        now = datetime.now()
        # Column names are hard-coded below - NOT derived from user input
        # This is safe from SQL injection as only values are parameterized
        updates: List[str] = []
        params: List[Any] = []

        if update.title is not None:
            updates.append("title = %s")
            params.append(update.title)

        if update.content is not None:
            updates.append("content = %s")
            params.append(update.content)
            updates.append("word_count = %s")
            params.append(len(update.content.split()))

        if update.topic is not None:
            updates.append("topic = %s")
            params.append(update.topic)

        if update.sources is not None:
            updates.append("sources = %s")
            params.append(json.dumps(update.sources))

        if update.approval_status is not None:
            updates.append("approval_status = %s")
            params.append(update.approval_status.value)
            if update.approval_status == ApprovalStatus.APPROVED:
                updates.append("approved_at = %s")
                params.append(now)

        if update.approval_feedback is not None:
            updates.append("approval_feedback = %s")
            params.append(update.approval_feedback)

        if update.metadata is not None:
            updates.append("metadata = %s")
            params.append(json.dumps(update.metadata))

        if updates:
            updates.append("updated_at = %s")
            params.append(now)
            params.append(post_id)

            with self._cursor() as cursor:
                cursor.execute(
                    f"UPDATE blog_posts SET {', '.join(updates)} WHERE id = %s RETURNING *",
                    params,
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_post(row)

        return self.get_post(post_id)

    def delete_post(self, post_id: str) -> bool:
        """Delete a blog post."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM blog_posts WHERE id = %s", (post_id,))
            return cursor.rowcount > 0

    def list_posts(
        self,
        approval_status: Optional[ApprovalStatus] = None,
        topic: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BlogPost]:
        """List blog posts with optional filters."""
        query = "SELECT * FROM blog_posts WHERE 1=1"
        params: List[Any] = []

        if approval_status:
            query += " AND approval_status = %s"
            params.append(approval_status.value)

        if topic:
            query += " AND topic = %s"
            params.append(topic)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self._cursor() as cursor:
            cursor.execute(query, params)
            return [self._row_to_post(row) for row in cursor.fetchall()]

    # === Approval Workflow ===

    def approve_post(
        self, post_id: str, feedback: Optional[str] = None, actor: Optional[str] = None
    ) -> Optional[BlogPost]:
        """Approve a blog post."""
        post = self.get_post(post_id)
        if not post:
            return None

        previous_status = post.approval_status.value
        update = BlogPostUpdate(
            approval_status=ApprovalStatus.APPROVED,
            approval_feedback=feedback,
        )

        result = self.update_post(post_id, update)

        self.add_history_entry(
            job_id=post.job_id or post_id,
            post_id=post_id,
            action="approved",
            previous_status=previous_status,
            new_status=ApprovalStatus.APPROVED.value,
            actor=actor,
            feedback=feedback,
        )

        return result

    def reject_post(self, post_id: str, feedback: str, actor: Optional[str] = None) -> Optional[BlogPost]:
        """Reject a blog post."""
        post = self.get_post(post_id)
        if not post:
            return None

        previous_status = post.approval_status.value
        update = BlogPostUpdate(
            approval_status=ApprovalStatus.REJECTED,
            approval_feedback=feedback,
        )

        result = self.update_post(post_id, update)

        self.add_history_entry(
            job_id=post.job_id or post_id,
            post_id=post_id,
            action="rejected",
            previous_status=previous_status,
            new_status=ApprovalStatus.REJECTED.value,
            actor=actor,
            feedback=feedback,
        )

        return result

    def request_revision(self, post_id: str, feedback: str, actor: Optional[str] = None) -> Optional[BlogPost]:
        """Request revision for a blog post."""
        post = self.get_post(post_id)
        if not post:
            return None

        previous_status = post.approval_status.value
        update = BlogPostUpdate(
            approval_status=ApprovalStatus.REVISION_REQUESTED,
            approval_feedback=feedback,
        )

        result = self.update_post(post_id, update)

        self.add_history_entry(
            job_id=post.job_id or post_id,
            post_id=post_id,
            action="revision_requested",
            previous_status=previous_status,
            new_status=ApprovalStatus.REVISION_REQUESTED.value,
            actor=actor,
            feedback=feedback,
        )

        return result

    def publish_post(self, post_id: str) -> Optional[BlogPost]:
        """Mark a blog post as published."""
        post = self.get_post(post_id)
        if not post:
            return None

        if post.approval_status != ApprovalStatus.APPROVED:
            logger.warning(f"Cannot publish post {post_id}: not approved")
            return None

        now = datetime.now()
        with self._cursor() as cursor:
            cursor.execute(
                "UPDATE blog_posts SET published_at = %s, updated_at = %s WHERE id = %s RETURNING *",
                (now, now, post_id),
            )
            row = cursor.fetchone()

        self.add_history_entry(
            job_id=post.job_id or post_id,
            post_id=post_id,
            action="published",
        )

        return self._row_to_post(row) if row else None

    # === History Operations ===

    def add_history_entry(
        self,
        job_id: str,
        action: str,
        post_id: Optional[str] = None,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        actor: Optional[str] = None,
        feedback: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JobHistoryEntry:
        """Add a history entry for job/post tracking."""
        entry_id = str(uuid.uuid4())
        now = datetime.now()

        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO job_history (
                    id, job_id, post_id, action, previous_status, new_status,
                    actor, feedback, metadata, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """,
                (
                    entry_id,
                    job_id,
                    post_id,
                    action,
                    previous_status,
                    new_status,
                    actor,
                    feedback,
                    json.dumps(metadata) if metadata else None,
                    now,
                ),
            )
            row = cursor.fetchone()

        return self._row_to_history(row)

    def get_job_history(self, job_id: str) -> List[JobHistoryEntry]:
        """Get history entries for a job."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM job_history WHERE job_id = %s ORDER BY created_at ASC",
                (job_id,),
            )
            return [self._row_to_history(row) for row in cursor.fetchall()]

    def get_post_history(self, post_id: str) -> List[JobHistoryEntry]:
        """Get history entries for a blog post."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM job_history WHERE post_id = %s ORDER BY created_at ASC",
                (post_id,),
            )
            return [self._row_to_history(row) for row in cursor.fetchall()]

    # === Statistics ===

    def get_stats(self) -> JobStats:
        """Get aggregated job and post statistics."""
        with self._cursor() as cursor:
            # Post counts by approval status
            cursor.execute(
                """
                SELECT approval_status::text, COUNT(*) as count
                FROM blog_posts
                GROUP BY approval_status
            """
            )

            status_counts = {row["approval_status"]: row["count"] for row in cursor.fetchall()}

            total_posts = sum(status_counts.values())
            pending_approval = status_counts.get(ApprovalStatus.PENDING.value, 0)
            approved_posts = status_counts.get(ApprovalStatus.APPROVED.value, 0)
            rejected_posts = status_counts.get(ApprovalStatus.REJECTED.value, 0)
            revision_requested = status_counts.get(ApprovalStatus.REVISION_REQUESTED.value, 0)

            # Published count
            cursor.execute("SELECT COUNT(*) as count FROM blog_posts WHERE published_at IS NOT NULL")
            published_posts = cursor.fetchone()["count"]

            # Calculate approval rate
            approval_rate = None
            if total_posts > 0:
                approval_rate = (approved_posts / total_posts) * 100

            # Calculate average approval time
            cursor.execute(
                """
                SELECT AVG(
                    EXTRACT(EPOCH FROM (approved_at - created_at)) / 3600
                ) as avg_hours
                FROM blog_posts
                WHERE approved_at IS NOT NULL
            """
            )
            row = cursor.fetchone()
            avg_approval_time = row["avg_hours"] if row and row["avg_hours"] else None

            return JobStats(
                total_jobs=total_posts,
                pending_jobs=pending_approval,
                completed_jobs=approved_posts + published_posts,
                failed_jobs=rejected_posts,
                total_posts=total_posts,
                pending_approval=pending_approval,
                approved_posts=approved_posts,
                rejected_posts=rejected_posts,
                revision_requested=revision_requested,
                published_posts=published_posts,
                avg_approval_time_hours=avg_approval_time,
                approval_rate=approval_rate,
            )

    # === Health Check ===

    def health_check(self) -> bool:
        """Check if the storage backend is healthy."""
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False
