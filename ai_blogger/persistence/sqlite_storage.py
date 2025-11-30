"""SQLite storage backend implementation.

Provides a file-based persistence layer using SQLite.
This is the default fallback storage when PostgreSQL is not available.
"""

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

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


class SQLiteStorage(StorageBackend):
    """SQLite-based storage backend.

    Thread-safe implementation using connection pooling via thread-local storage.
    """

    def __init__(self, config: StorageConfig):
        """Initialize SQLite storage.

        Args:
            config: Storage configuration.
        """
        self.config = config
        self.db_path = config.db_path or "./data/inker.db"
        self._local = threading.local()
        self._lock = threading.RLock()
        self._initialized = False

        if config.auto_migrate:
            self.initialize()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            # Ensure directory exists
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database cursor."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def initialize(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            if self._initialized:
                return

            with self._cursor() as cursor:
                # Create schema version table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                """
                )

                # Check current version
                cursor.execute("SELECT MAX(version) FROM schema_version")
                row = cursor.fetchone()
                current_version = row[0] if row and row[0] else 0

                if current_version < SCHEMA_VERSION:
                    self._run_migrations(cursor, current_version)

            self._initialized = True
            logger.info(f"SQLite storage initialized at {self.db_path}")

    def _run_migrations(self, cursor: sqlite3.Cursor, from_version: int) -> None:
        """Run database migrations."""
        if from_version < 1:
            # Initial schema
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS blog_posts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    sources TEXT NOT NULL DEFAULT '[]',
                    job_id TEXT,
                    approval_status TEXT NOT NULL DEFAULT 'pending',
                    approval_feedback TEXT,
                    scoring TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approved_at TEXT,
                    published_at TEXT
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
                CREATE TABLE IF NOT EXISTS job_history (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    post_id TEXT,
                    action TEXT NOT NULL,
                    previous_status TEXT,
                    new_status TEXT,
                    actor TEXT,
                    feedback TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL
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

            # Record migration
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (1, datetime.now().isoformat()),
            )

            logger.info("Applied SQLite migration version 1")

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    def _serialize_json(self, data: Any) -> Optional[str]:
        """Serialize data to JSON string."""
        if data is None:
            return None
        return json.dumps(data)

    def _deserialize_json(self, data: Optional[str]) -> Any:
        """Deserialize JSON string to data."""
        if data is None:
            return None
        return json.loads(data)

    def _row_to_post(self, row: sqlite3.Row) -> BlogPost:
        """Convert a database row to a BlogPost."""
        return BlogPost(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            word_count=row["word_count"],
            topic=row["topic"],
            sources=self._deserialize_json(row["sources"]) or [],
            job_id=row["job_id"],
            approval_status=ApprovalStatus(row["approval_status"]),
            approval_feedback=row["approval_feedback"],
            scoring=self._deserialize_json(row["scoring"]),
            metadata=self._deserialize_json(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
        )

    def _row_to_history(self, row: sqlite3.Row) -> JobHistoryEntry:
        """Convert a database row to a JobHistoryEntry."""
        return JobHistoryEntry(
            id=row["id"],
            job_id=row["job_id"],
            post_id=row["post_id"],
            action=row["action"],
            previous_status=row["previous_status"],
            new_status=row["new_status"],
            actor=row["actor"],
            feedback=row["feedback"],
            metadata=self._deserialize_json(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]),
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    post_id,
                    post.title,
                    post.content,
                    word_count,
                    post.topic,
                    self._serialize_json(post.sources),
                    post.job_id,
                    ApprovalStatus.PENDING.value,
                    self._serialize_json(post.scoring),
                    self._serialize_json(post.metadata),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

        # Log history
        self.add_history_entry(
            job_id=post.job_id or post_id,
            post_id=post_id,
            action="post_created",
            new_status=ApprovalStatus.PENDING.value,
        )

        return self.get_post(post_id)  # type: ignore

    def get_post(self, post_id: str) -> Optional[BlogPost]:
        """Get a blog post by ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM blog_posts WHERE id = ?", (post_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_post(row)
            return None

    def get_post_by_job_id(self, job_id: str) -> Optional[BlogPost]:
        """Get a blog post by its associated job ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM blog_posts WHERE job_id = ?", (job_id,))
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
            updates.append("title = ?")
            params.append(update.title)

        if update.content is not None:
            updates.append("content = ?")
            params.append(update.content)
            updates.append("word_count = ?")
            params.append(len(update.content.split()))

        if update.topic is not None:
            updates.append("topic = ?")
            params.append(update.topic)

        if update.sources is not None:
            updates.append("sources = ?")
            params.append(self._serialize_json(update.sources))

        if update.approval_status is not None:
            updates.append("approval_status = ?")
            params.append(update.approval_status.value)
            if update.approval_status == ApprovalStatus.APPROVED:
                updates.append("approved_at = ?")
                params.append(now.isoformat())

        if update.approval_feedback is not None:
            updates.append("approval_feedback = ?")
            params.append(update.approval_feedback)

        if update.metadata is not None:
            updates.append("metadata = ?")
            params.append(self._serialize_json(update.metadata))

        if updates:
            updates.append("updated_at = ?")
            params.append(now.isoformat())
            params.append(post_id)

            with self._cursor() as cursor:
                cursor.execute(
                    f"UPDATE blog_posts SET {', '.join(updates)} WHERE id = ?",
                    params,
                )

        return self.get_post(post_id)

    def delete_post(self, post_id: str) -> bool:
        """Delete a blog post."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM blog_posts WHERE id = ?", (post_id,))
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
            query += " AND approval_status = ?"
            params.append(approval_status.value)

        if topic:
            query += " AND topic = ?"
            params.append(topic)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
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
                "UPDATE blog_posts SET published_at = ?, updated_at = ? WHERE id = ?",
                (now.isoformat(), now.isoformat(), post_id),
            )

        self.add_history_entry(
            job_id=post.job_id or post_id,
            post_id=post_id,
            action="published",
        )

        return self.get_post(post_id)

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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    self._serialize_json(metadata),
                    now.isoformat(),
                ),
            )

        return JobHistoryEntry(
            id=entry_id,
            job_id=job_id,
            post_id=post_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            actor=actor,
            feedback=feedback,
            metadata=metadata,
            created_at=now,
        )

    def get_job_history(self, job_id: str) -> List[JobHistoryEntry]:
        """Get history entries for a job."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM job_history WHERE job_id = ? ORDER BY created_at ASC",
                (job_id,),
            )
            return [self._row_to_history(row) for row in cursor.fetchall()]

    def get_post_history(self, post_id: str) -> List[JobHistoryEntry]:
        """Get history entries for a blog post."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM job_history WHERE post_id = ? ORDER BY created_at ASC",
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
                SELECT approval_status, COUNT(*) as count
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
            cursor.execute("SELECT COUNT(*) FROM blog_posts WHERE published_at IS NOT NULL")
            published_posts = cursor.fetchone()[0]

            # Calculate approval rate
            approval_rate = None
            if total_posts > 0:
                approval_rate = (approved_posts / total_posts) * 100

            # Calculate average approval time
            cursor.execute(
                """
                SELECT AVG(
                    (julianday(approved_at) - julianday(created_at)) * 24
                ) as avg_hours
                FROM blog_posts
                WHERE approved_at IS NOT NULL
            """
            )
            row = cursor.fetchone()
            avg_approval_time = row[0] if row and row[0] else None

            return JobStats(
                total_jobs=total_posts,  # Using posts as proxy for jobs
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
            logger.error(f"SQLite health check failed: {e}")
            return False
