"""Tests for the persistence layer."""

import os
import tempfile
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from ai_blogger.job_models import (
    ApprovalRecord,
    ApprovalStatus,
    BlogPostJob,
    EditorComment,
    JobStatus,
)
from ai_blogger.persistence import SQLiteJobRepository


class TestSQLiteJobRepository:
    """Tests for SQLite repository implementation."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def repository(self, temp_db):
        """Create a repository with temporary database."""
        repo = SQLiteJobRepository(db_path=temp_db)
        yield repo
        repo.close()

    def test_create_and_get_job(self, repository):
        """Test creating and retrieving a job."""
        job = BlogPostJob(
            topics=["AI", "ML"],
            sources=["hacker_news"],
            num_candidates=3,
        )

        created = repository.create_job(job)
        assert created.id == job.id

        retrieved = repository.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.topics == ["AI", "ML"]
        assert retrieved.sources == ["hacker_news"]

    def test_get_nonexistent_job(self, repository):
        """Test getting a job that doesn't exist."""
        result = repository.get_job(uuid4())
        assert result is None

    def test_get_job_by_correlation_id(self, repository):
        """Test getting a job by correlation ID."""
        job = BlogPostJob(
            correlation_id="test-correlation-123",
            topics=["AI"],
        )
        repository.create_job(job)

        retrieved = repository.get_job_by_correlation_id("test-correlation-123")
        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.correlation_id == "test-correlation-123"

    def test_get_job_by_nonexistent_correlation_id(self, repository):
        """Test getting a job by correlation ID that doesn't exist."""
        result = repository.get_job_by_correlation_id("nonexistent")
        assert result is None

    def test_update_job(self, repository):
        """Test updating a job."""
        job = BlogPostJob(topics=["AI"])
        repository.create_job(job)

        # Update the job
        job.status = JobStatus.IN_PROGRESS
        job.title = "Test Title"
        job.started_at = datetime.now(timezone.utc)

        updated = repository.update_job(job)
        assert updated.status == JobStatus.IN_PROGRESS
        assert updated.title == "Test Title"
        assert updated.started_at is not None

        # Verify persisted
        retrieved = repository.get_job(job.id)
        assert retrieved.status == JobStatus.IN_PROGRESS
        assert retrieved.title == "Test Title"

    def test_list_jobs_empty(self, repository):
        """Test listing jobs when repository is empty."""
        jobs = repository.list_jobs()
        assert jobs == []

    def test_list_jobs_with_data(self, repository):
        """Test listing jobs with data."""
        for i in range(3):
            job = BlogPostJob(topics=[f"Topic {i}"])
            repository.create_job(job)

        jobs = repository.list_jobs()
        assert len(jobs) == 3

    def test_list_jobs_with_status_filter(self, repository):
        """Test filtering jobs by status."""
        # Create jobs with different statuses
        pending_job = BlogPostJob(status=JobStatus.PENDING)
        completed_job = BlogPostJob(status=JobStatus.COMPLETED)
        approved_job = BlogPostJob(status=JobStatus.APPROVED)

        repository.create_job(pending_job)
        repository.create_job(completed_job)
        repository.create_job(approved_job)

        # Filter by status
        pending_jobs = repository.list_jobs(status=JobStatus.PENDING)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].status == JobStatus.PENDING

        completed_jobs = repository.list_jobs(status=JobStatus.COMPLETED)
        assert len(completed_jobs) == 1

    def test_list_jobs_pagination(self, repository):
        """Test job listing pagination."""
        for i in range(10):
            job = BlogPostJob(topics=[f"Topic {i}"])
            repository.create_job(job)

        page1 = repository.list_jobs(page=1, per_page=3)
        page2 = repository.list_jobs(page=2, per_page=3)

        assert len(page1) == 3
        assert len(page2) == 3

        # Verify different jobs
        page1_ids = {j.id for j in page1}
        page2_ids = {j.id for j in page2}
        assert not page1_ids.intersection(page2_ids)

    def test_count_jobs(self, repository):
        """Test counting jobs."""
        assert repository.count_jobs() == 0

        for _ in range(5):
            repository.create_job(BlogPostJob())

        assert repository.count_jobs() == 5

    def test_count_jobs_by_status(self, repository):
        """Test counting jobs by status."""
        for _ in range(3):
            repository.create_job(BlogPostJob(status=JobStatus.PENDING))
        for _ in range(2):
            repository.create_job(BlogPostJob(status=JobStatus.COMPLETED))

        assert repository.count_jobs(status=JobStatus.PENDING) == 3
        assert repository.count_jobs(status=JobStatus.COMPLETED) == 2
        assert repository.count_jobs(status=JobStatus.APPROVED) == 0

    def test_get_stats(self, repository):
        """Test getting job statistics."""
        # Empty stats
        stats = repository.get_stats()
        assert stats.total == 0

        # Add some jobs
        repository.create_job(BlogPostJob(status=JobStatus.PENDING))
        repository.create_job(BlogPostJob(status=JobStatus.PENDING))
        repository.create_job(BlogPostJob(status=JobStatus.COMPLETED))
        repository.create_job(BlogPostJob(status=JobStatus.APPROVED))

        stats = repository.get_stats()
        assert stats.total == 4
        assert stats.pending == 2
        assert stats.completed == 1
        assert stats.approved == 1

    def test_add_approval_record(self, repository):
        """Test adding an approval record."""
        job = BlogPostJob()
        repository.create_job(job)

        record = ApprovalRecord(
            job_id=job.id,
            status=ApprovalStatus.APPROVED,
            reviewer="editor@example.com",
            reason="Good article",
        )

        created = repository.add_approval_record(record)
        assert created.id == record.id

    def test_add_and_get_comments(self, repository):
        """Test adding and retrieving comments."""
        job = BlogPostJob()
        repository.create_job(job)

        # Add comments
        comment1 = EditorComment(
            job_id=job.id,
            author="editor1@example.com",
            content="First comment",
        )
        comment2 = EditorComment(
            job_id=job.id,
            author="editor2@example.com",
            content="Second comment",
        )

        repository.add_comment(comment1)
        repository.add_comment(comment2)

        # Retrieve comments
        comments = repository.get_comments(job.id)
        assert len(comments) == 2
        assert comments[0].content == "First comment"
        assert comments[1].content == "Second comment"

    def test_get_comments_for_job_with_no_comments(self, repository):
        """Test getting comments for a job without comments."""
        job = BlogPostJob()
        repository.create_job(job)

        comments = repository.get_comments(job.id)
        assert comments == []
