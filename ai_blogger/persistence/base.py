"""Abstract base class for storage backends.

This module defines the API contract that all storage backends must implement.
"""

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import (
    ApprovalStatus,
    BlogPost,
    BlogPostCreate,
    BlogPostUpdate,
    JobHistoryEntry,
    JobStats,
)


@dataclass
class StorageConfig:
    """Configuration for storage backends.

    Attributes:
        backend_type: Type of storage backend (sqlite, postgres, etc).
        connection_string: Database connection string (for SQL backends).
        db_path: File path for file-based backends (SQLite).
        pool_size: Connection pool size (for connection-pooled backends).
        auto_migrate: Whether to auto-run migrations on init.
        extra: Additional backend-specific configuration.
    """

    backend_type: str = "sqlite"
    connection_string: Optional[str] = None
    db_path: Optional[str] = None
    pool_size: int = 5
    auto_migrate: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)


class StorageBackend(abc.ABC):
    """Abstract base class for storage backends.

    All storage backends must implement this interface to provide
    persistence for jobs, blog posts, and historical stats.

    The interface supports:
    - Job storage (delegates to job models)
    - Blog post CRUD with approval workflow
    - Historical tracking
    - Statistics aggregation
    """

    @abc.abstractmethod
    def initialize(self) -> None:
        """Initialize the storage backend.

        This should create tables/schemas if they don't exist
        and run any pending migrations.
        """
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """Close the storage backend and release resources."""
        pass

    # === Blog Post Operations ===

    @abc.abstractmethod
    def create_post(self, post: BlogPostCreate) -> BlogPost:
        """Create a new blog post.

        Args:
            post: The blog post data to create.

        Returns:
            The created BlogPost with generated ID and timestamps.
        """
        pass

    @abc.abstractmethod
    def get_post(self, post_id: str) -> Optional[BlogPost]:
        """Get a blog post by ID.

        Args:
            post_id: The post identifier.

        Returns:
            BlogPost or None if not found.
        """
        pass

    @abc.abstractmethod
    def get_post_by_job_id(self, job_id: str) -> Optional[BlogPost]:
        """Get a blog post by its associated job ID.

        Args:
            job_id: The job identifier.

        Returns:
            BlogPost or None if not found.
        """
        pass

    @abc.abstractmethod
    def update_post(self, post_id: str, update: BlogPostUpdate) -> Optional[BlogPost]:
        """Update an existing blog post.

        Args:
            post_id: The post identifier.
            update: The fields to update.

        Returns:
            Updated BlogPost or None if not found.
        """
        pass

    @abc.abstractmethod
    def delete_post(self, post_id: str) -> bool:
        """Delete a blog post.

        Args:
            post_id: The post identifier.

        Returns:
            True if deleted, False if not found.
        """
        pass

    @abc.abstractmethod
    def list_posts(
        self,
        approval_status: Optional[ApprovalStatus] = None,
        topic: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BlogPost]:
        """List blog posts with optional filters.

        Args:
            approval_status: Optional filter by approval status.
            topic: Optional filter by topic.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of BlogPost objects.
        """
        pass

    # === Approval Workflow ===

    @abc.abstractmethod
    def approve_post(
        self, post_id: str, feedback: Optional[str] = None, actor: Optional[str] = None
    ) -> Optional[BlogPost]:
        """Approve a blog post.

        Args:
            post_id: The post identifier.
            feedback: Optional approval feedback.
            actor: Optional identifier for who approved.

        Returns:
            Updated BlogPost or None if not found.
        """
        pass

    @abc.abstractmethod
    def reject_post(self, post_id: str, feedback: str, actor: Optional[str] = None) -> Optional[BlogPost]:
        """Reject a blog post.

        Args:
            post_id: The post identifier.
            feedback: Rejection reason (required).
            actor: Optional identifier for who rejected.

        Returns:
            Updated BlogPost or None if not found.
        """
        pass

    @abc.abstractmethod
    def request_revision(self, post_id: str, feedback: str, actor: Optional[str] = None) -> Optional[BlogPost]:
        """Request revision for a blog post.

        Args:
            post_id: The post identifier.
            feedback: Revision feedback (required).
            actor: Optional identifier for who requested revision.

        Returns:
            Updated BlogPost or None if not found.
        """
        pass

    @abc.abstractmethod
    def publish_post(self, post_id: str) -> Optional[BlogPost]:
        """Mark a blog post as published.

        Args:
            post_id: The post identifier.

        Returns:
            Updated BlogPost or None if not found or not approved.
        """
        pass

    # === History Operations ===

    @abc.abstractmethod
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
        """Add a history entry for job/post tracking.

        Args:
            job_id: The job ID this entry relates to.
            action: The action that occurred.
            post_id: Optional blog post ID.
            previous_status: Previous status before action.
            new_status: New status after action.
            actor: Who performed the action.
            feedback: Optional feedback or notes.
            metadata: Additional context.

        Returns:
            The created history entry.
        """
        pass

    @abc.abstractmethod
    def get_job_history(self, job_id: str) -> List[JobHistoryEntry]:
        """Get history entries for a job.

        Args:
            job_id: The job identifier.

        Returns:
            List of history entries, ordered by creation time.
        """
        pass

    @abc.abstractmethod
    def get_post_history(self, post_id: str) -> List[JobHistoryEntry]:
        """Get history entries for a blog post.

        Args:
            post_id: The post identifier.

        Returns:
            List of history entries, ordered by creation time.
        """
        pass

    # === Statistics ===

    @abc.abstractmethod
    def get_stats(self) -> JobStats:
        """Get aggregated job and post statistics.

        Returns:
            JobStats with counts and metrics.
        """
        pass

    # === Health Check ===

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Check if the storage backend is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        pass
