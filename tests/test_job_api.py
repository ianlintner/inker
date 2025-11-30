"""Tests for the Blog Post Job API."""

import os
import shutil
import tempfile
from datetime import datetime

import pytest

from ai_blogger import (
    Job,
    JobError,
    JobRequest,
    JobResult,
    JobService,
    JobStatus,
    JobStatusResponse,
    JobStore,
    JobSubmitResponse,
    MarkdownPreview,
    ScoringInfo,
)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for job storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def job_store(temp_storage_dir):
    """Create a JobStore with temporary storage."""
    return JobStore(temp_storage_dir)


@pytest.fixture
def job_service(temp_storage_dir):
    """Create a JobService with temporary storage."""
    return JobService(temp_storage_dir)


class TestJobModels:
    """Tests for job models."""

    def test_job_request_defaults(self):
        """Test JobRequest default values."""
        request = JobRequest()
        assert request.topics is None
        assert request.sources is None
        assert request.num_candidates == 3
        assert request.max_results is None
        assert request.correlation_id is None

    def test_job_request_with_values(self):
        """Test JobRequest with custom values."""
        request = JobRequest(
            topics=["AI", "ML"],
            sources=["hacker_news"],
            num_candidates=5,
            correlation_id="test-123",
        )
        assert request.topics == ["AI", "ML"]
        assert request.sources == ["hacker_news"]
        assert request.num_candidates == 5
        assert request.correlation_id == "test-123"

    def test_job_request_validation(self):
        """Test JobRequest validation."""
        # num_candidates must be >= 1
        with pytest.raises(ValueError):
            JobRequest(num_candidates=0)

        # num_candidates must be <= 10
        with pytest.raises(ValueError):
            JobRequest(num_candidates=11)

    def test_job_status_enum(self):
        """Test JobStatus enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.FETCHING.value == "fetching"
        assert JobStatus.GENERATING.value == "generating"
        assert JobStatus.SCORING.value == "scoring"
        assert JobStatus.REFINING.value == "refining"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"

    def test_job_error_model(self):
        """Test JobError model."""
        error = JobError(
            code="TEST_ERROR",
            message="Test error message",
            details="Additional details",
        )
        assert error.code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.details == "Additional details"

    def test_markdown_preview_model(self):
        """Test MarkdownPreview model."""
        preview = MarkdownPreview(
            title="Test Post",
            content="# Test\n\nContent here",
            word_count=100,
            topic="testing",
            sources=["https://example.com"],
        )
        assert preview.title == "Test Post"
        assert preview.word_count == 100

    def test_scoring_info_model(self):
        """Test ScoringInfo model."""
        scoring = ScoringInfo(
            relevance=8.0,
            originality=7.5,
            depth=8.5,
            clarity=9.0,
            engagement=7.0,
            total=8.0,
            reasoning="Good overall quality",
        )
        assert scoring.total == 8.0
        assert scoring.relevance == 8.0

    def test_job_result_model(self):
        """Test JobResult model."""
        preview = MarkdownPreview(
            title="Test",
            content="# Test",
            word_count=50,
            topic="test",
            sources=[],
        )
        scoring = ScoringInfo(
            relevance=8.0,
            originality=7.5,
            depth=8.5,
            clarity=9.0,
            engagement=7.0,
            total=8.0,
            reasoning="Good",
        )
        result = JobResult(
            markdown_preview=preview,
            scoring=scoring,
            articles_fetched=10,
            candidates_generated=3,
        )
        assert result.articles_fetched == 10
        assert result.candidates_generated == 3

    def test_job_model(self):
        """Test Job model."""
        now = datetime.now()
        request = JobRequest(topics=["AI"])
        job = Job(
            id="test-job-id",
            correlation_id="corr-123",
            status=JobStatus.PENDING,
            request=request,
            created_at=now,
            updated_at=now,
        )
        assert job.id == "test-job-id"
        assert job.correlation_id == "corr-123"
        assert job.status == JobStatus.PENDING
        assert job.result is None
        assert job.error is None


class TestJobStore:
    """Tests for JobStore."""

    def test_create_job(self, job_store):
        """Test creating a new job."""
        request = JobRequest(topics=["AI"])
        job = job_store.create_job("test-123", request)

        assert job.id == "test-123"
        assert job.status == JobStatus.PENDING
        assert job.request.topics == ["AI"]

    def test_get_job(self, job_store):
        """Test getting a job by ID."""
        request = JobRequest(topics=["AI"])
        job_store.create_job("test-123", request)

        retrieved = job_store.get_job("test-123")
        assert retrieved is not None
        assert retrieved.id == "test-123"

        # Non-existent job
        assert job_store.get_job("non-existent") is None

    def test_correlation_id_lookup(self, job_store):
        """Test getting a job by correlation ID."""
        request = JobRequest(
            topics=["AI"],
            correlation_id="corr-456",
        )
        job_store.create_job("test-789", request)

        retrieved = job_store.get_job_by_correlation_id("corr-456")
        assert retrieved is not None
        assert retrieved.id == "test-789"

        # Non-existent correlation ID
        assert job_store.get_job_by_correlation_id("non-existent") is None

    def test_duplicate_correlation_id(self, job_store):
        """Test that duplicate correlation IDs are rejected."""
        request = JobRequest(correlation_id="unique-123")
        job_store.create_job("job-1", request)

        # Trying to create another job with same correlation ID should fail
        with pytest.raises(ValueError, match="already exists"):
            job_store.create_job("job-2", request)

    def test_update_job_status(self, job_store):
        """Test updating job status."""
        request = JobRequest()
        job_store.create_job("test-123", request)

        updated = job_store.update_job_status("test-123", JobStatus.FETCHING)
        assert updated is not None
        assert updated.status == JobStatus.FETCHING

        # Update to completed should set completed_at
        completed = job_store.update_job_status("test-123", JobStatus.COMPLETED)
        assert completed is not None
        assert completed.status == JobStatus.COMPLETED
        assert completed.completed_at is not None

    def test_list_jobs(self, job_store):
        """Test listing jobs."""
        for i in range(5):
            request = JobRequest(topics=[f"topic-{i}"])
            job_store.create_job(f"job-{i}", request)

        jobs = job_store.list_jobs()
        assert len(jobs) == 5

        # Test with limit
        limited = job_store.list_jobs(limit=3)
        assert len(limited) == 3

    def test_list_jobs_with_status_filter(self, job_store):
        """Test listing jobs with status filter."""
        request = JobRequest()

        job_store.create_job("job-1", request)
        job_store.create_job("job-2", request)
        job_store.update_job_status("job-2", JobStatus.COMPLETED)

        pending = job_store.list_jobs(status=JobStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].id == "job-1"

        completed = job_store.list_jobs(status=JobStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].id == "job-2"

    def test_delete_job(self, job_store):
        """Test deleting a job."""
        request = JobRequest(correlation_id="corr-123")
        job_store.create_job("test-123", request)

        # Verify job exists
        assert job_store.get_job("test-123") is not None

        # Delete
        result = job_store.delete_job("test-123")
        assert result is True

        # Verify job is gone
        assert job_store.get_job("test-123") is None

        # Correlation ID should also be removed
        assert job_store.get_job_by_correlation_id("corr-123") is None

        # Deleting non-existent job returns False
        assert job_store.delete_job("non-existent") is False


class TestJobService:
    """Tests for JobService."""

    def test_submit_job(self, job_service):
        """Test submitting a new job."""
        request = JobRequest(topics=["AI"])
        response = job_service.submit_job(request)

        assert response.job_id is not None
        assert response.status == JobStatus.PENDING
        assert response.is_duplicate is False
        assert "submitted successfully" in response.message

    def test_submit_job_with_correlation_id(self, job_service):
        """Test submitting a job with correlation ID."""
        request = JobRequest(correlation_id="unique-key")
        response = job_service.submit_job(request)

        assert response.correlation_id == "unique-key"
        assert response.is_duplicate is False

    def test_idempotency(self, job_service):
        """Test that duplicate correlation IDs return existing job."""
        request = JobRequest(correlation_id="idempotent-key")

        # First submission
        response1 = job_service.submit_job(request)
        assert response1.is_duplicate is False

        # Second submission with same correlation ID
        response2 = job_service.submit_job(request)
        assert response2.is_duplicate is True
        assert response2.job_id == response1.job_id
        assert "already exists" in response2.message

    def test_get_job_status(self, job_service):
        """Test getting job status."""
        request = JobRequest(topics=["testing"])
        submit_response = job_service.submit_job(request)

        status_response = job_service.get_job_status(submit_response.job_id)
        assert status_response is not None
        assert status_response.job_id == submit_response.job_id
        assert status_response.status == JobStatus.PENDING

        # Non-existent job
        assert job_service.get_job_status("non-existent") is None

    def test_get_job_by_correlation_id(self, job_service):
        """Test getting job by correlation ID."""
        request = JobRequest(correlation_id="lookup-key")
        submit_response = job_service.submit_job(request)

        status_response = job_service.get_job_by_correlation_id("lookup-key")
        assert status_response is not None
        assert status_response.job_id == submit_response.job_id

        # Non-existent correlation ID
        assert job_service.get_job_by_correlation_id("missing") is None

    def test_list_jobs(self, job_service):
        """Test listing jobs."""
        # Submit several jobs
        for i in range(3):
            request = JobRequest(topics=[f"topic-{i}"])
            job_service.submit_job(request)

        jobs = job_service.list_jobs()
        assert len(jobs) == 3

    def test_delete_job(self, job_service):
        """Test deleting a job."""
        request = JobRequest()
        response = job_service.submit_job(request)

        # Verify job exists
        assert job_service.get_job_status(response.job_id) is not None

        # Delete
        result = job_service.delete_job(response.job_id)
        assert result is True

        # Verify job is gone
        assert job_service.get_job_status(response.job_id) is None


class TestJobAPIImports:
    """Test that all Job API components are properly exported."""

    def test_imports(self):
        """Test that all Job API components can be imported."""
        from ai_blogger import (
            Job,
            JobError,
            JobRequest,
            JobResult,
            JobService,
            JobStatus,
            JobStatusResponse,
            JobStore,
            JobSubmitResponse,
            MarkdownPreview,
            ScoringInfo,
        )

        # All imports should succeed
        assert JobService is not None
        assert JobStore is not None
        assert Job is not None
        assert JobRequest is not None
        assert JobStatus is not None
        assert JobResult is not None
        assert JobError is not None
        assert JobSubmitResponse is not None
        assert JobStatusResponse is not None
        assert MarkdownPreview is not None
        assert ScoringInfo is not None
