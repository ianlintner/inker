"""Base repository interface for job persistence.

This module defines the abstract interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ..job_models import (
    ApprovalRecord,
    BlogPostJob,
    EditorComment,
    JobStats,
    JobStatus,
)


class JobRepository(ABC):
    """Abstract base class for job persistence.

    All storage backends (SQLite, Postgres, etc.) must implement this interface.
    """

    @abstractmethod
    def create_job(self, job: BlogPostJob) -> BlogPostJob:
        """Create a new job in the repository.

        Args:
            job: The job to create.

        Returns:
            The created job with any generated fields populated.
        """
        pass

    @abstractmethod
    def get_job(self, job_id: UUID) -> Optional[BlogPostJob]:
        """Get a job by its ID.

        Args:
            job_id: The UUID of the job to retrieve.

        Returns:
            The job if found, None otherwise.
        """
        pass

    @abstractmethod
    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[BlogPostJob]:
        """Get a job by its correlation ID.

        Args:
            correlation_id: The client-provided correlation ID.

        Returns:
            The job if found, None otherwise.
        """
        pass

    @abstractmethod
    def update_job(self, job: BlogPostJob) -> BlogPostJob:
        """Update an existing job.

        Args:
            job: The job with updated fields.

        Returns:
            The updated job.
        """
        pass

    @abstractmethod
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[BlogPostJob]:
        """List jobs with optional filtering and pagination.

        Args:
            status: Optional status filter.
            page: Page number (1-indexed).
            per_page: Number of items per page.

        Returns:
            List of jobs matching the criteria.
        """
        pass

    @abstractmethod
    def count_jobs(self, status: Optional[JobStatus] = None) -> int:
        """Count jobs with optional status filter.

        Args:
            status: Optional status filter.

        Returns:
            Number of jobs matching the criteria.
        """
        pass

    @abstractmethod
    def get_stats(self) -> JobStats:
        """Get statistics about job statuses.

        Returns:
            JobStats with counts for each status.
        """
        pass

    @abstractmethod
    def add_approval_record(self, record: ApprovalRecord) -> ApprovalRecord:
        """Add an approval record to a job.

        Args:
            record: The approval record to add.

        Returns:
            The created approval record.
        """
        pass

    @abstractmethod
    def add_comment(self, comment: EditorComment) -> EditorComment:
        """Add a comment to a job.

        Args:
            comment: The comment to add.

        Returns:
            The created comment.
        """
        pass

    @abstractmethod
    def get_comments(self, job_id: UUID) -> List[EditorComment]:
        """Get all comments for a job.

        Args:
            job_id: The UUID of the job.

        Returns:
            List of comments for the job.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the repository connection."""
        pass
