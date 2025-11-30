"""Tests for the job models."""

import pytest
from uuid import UUID
from datetime import datetime

from ai_blogger.job_models import (
    JobStatus,
    ApprovalStatus,
    BlogPostJob,
    JobSubmission,
    JobResponse,
    JobPreview,
    ApprovalRequest,
    ApprovalRecord,
    EditorComment,
    JobStats,
    HistoricalJobsResponse,
)


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_all_statuses_defined(self):
        """Test that all expected statuses are defined."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.IN_PROGRESS == "in_progress"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.NEEDS_APPROVAL == "needs_approval"
        assert JobStatus.APPROVED == "approved"
        assert JobStatus.REJECTED == "rejected"
        assert JobStatus.FAILED == "failed"


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_all_statuses_defined(self):
        """Test that all approval statuses are defined."""
        assert ApprovalStatus.PENDING == "pending"
        assert ApprovalStatus.APPROVED == "approved"
        assert ApprovalStatus.REJECTED == "rejected"


class TestBlogPostJob:
    """Tests for BlogPostJob model."""

    def test_create_job_with_defaults(self):
        """Test creating a job with default values."""
        job = BlogPostJob()

        assert isinstance(job.id, UUID)
        assert job.status == JobStatus.PENDING
        assert job.topics == []
        assert job.sources == []
        assert job.num_candidates == 3
        assert isinstance(job.created_at, datetime)
        assert job.approval_status == ApprovalStatus.PENDING
        assert job.title is None
        assert job.content is None

    def test_create_job_with_values(self):
        """Test creating a job with specific values."""
        job = BlogPostJob(
            correlation_id="test-123",
            topics=["AI", "ML"],
            sources=["hacker_news", "youtube"],
            num_candidates=5,
        )

        assert job.correlation_id == "test-123"
        assert job.topics == ["AI", "ML"]
        assert job.sources == ["hacker_news", "youtube"]
        assert job.num_candidates == 5


class TestJobSubmission:
    """Tests for JobSubmission model."""

    def test_create_submission_minimal(self):
        """Test creating a minimal submission."""
        submission = JobSubmission()

        assert submission.topics is None
        assert submission.sources is None
        assert submission.num_candidates == 3
        assert submission.correlation_id is None

    def test_create_submission_full(self):
        """Test creating a full submission."""
        submission = JobSubmission(
            topics=["AI"],
            sources=["web"],
            num_candidates=5,
            correlation_id="idempotency-key-123",
        )

        assert submission.topics == ["AI"]
        assert submission.sources == ["web"]
        assert submission.num_candidates == 5
        assert submission.correlation_id == "idempotency-key-123"


class TestApprovalRequest:
    """Tests for ApprovalRequest model."""

    def test_create_approval(self):
        """Test creating an approval request."""
        request = ApprovalRequest(
            status=ApprovalStatus.APPROVED,
            reviewer="editor@example.com",
            reason="Good article",
        )

        assert request.status == ApprovalStatus.APPROVED
        assert request.reviewer == "editor@example.com"
        assert request.reason == "Good article"

    def test_create_rejection(self):
        """Test creating a rejection request."""
        request = ApprovalRequest(
            status=ApprovalStatus.REJECTED,
            reviewer="editor@example.com",
            reason="Needs more detail",
            comments=["Add more examples", "Fix grammar in intro"],
        )

        assert request.status == ApprovalStatus.REJECTED
        assert len(request.comments) == 2


class TestEditorComment:
    """Tests for EditorComment model."""

    def test_create_comment(self):
        """Test creating an editor comment."""
        from uuid import uuid4

        job_id = uuid4()
        comment = EditorComment(
            job_id=job_id,
            author="editor@example.com",
            content="Please add more examples.",
        )

        assert comment.job_id == job_id
        assert comment.author == "editor@example.com"
        assert comment.content == "Please add more examples."
        assert isinstance(comment.created_at, datetime)


class TestJobStats:
    """Tests for JobStats model."""

    def test_default_stats(self):
        """Test default job stats."""
        stats = JobStats()

        assert stats.total == 0
        assert stats.pending == 0
        assert stats.approved == 0
        assert stats.rejected == 0

    def test_stats_with_values(self):
        """Test job stats with values."""
        stats = JobStats(
            total=100,
            pending=10,
            in_progress=5,
            completed=50,
            approved=30,
            rejected=5,
        )

        assert stats.total == 100
        assert stats.pending == 10
        assert stats.approved == 30
