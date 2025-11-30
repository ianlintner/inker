"""Tests for the API routes."""

import os
import tempfile
import pytest
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_blogger.api.app import create_app
from ai_blogger.api.dependencies import reset_dependencies, set_repository
from ai_blogger.job_models import ApprovalStatus, BlogPostJob, JobStatus
from ai_blogger.persistence import SQLiteJobRepository


class TestAPIRoutes:
    """Tests for the API routes."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except Exception:
            pass

    @pytest.fixture
    def repository(self, temp_db):
        """Create a repository with temporary database."""
        repo = SQLiteJobRepository(db_path=temp_db)
        set_repository(repo)
        yield repo
        reset_dependencies()

    @pytest.fixture
    def client(self, repository):
        """Create a test client."""
        app = create_app()
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_readiness_check(self, client, repository):
        """Test the readiness check endpoint."""
        response = client.get("/api/v1/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"

    def test_submit_job(self, client):
        """Test submitting a new job."""
        response = client.post(
            "/api/v1/jobs",
            json={
                "topics": ["AI", "ML"],
                "sources": ["hacker_news"],
                "num_candidates": 3,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["topics"] == ["AI", "ML"]
        assert data["status"] == "pending"

    def test_submit_job_with_correlation_id(self, client):
        """Test submitting a job with correlation ID."""
        response = client.post(
            "/api/v1/jobs",
            json={"correlation_id": "test-123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["correlation_id"] == "test-123"

    def test_submit_job_idempotency(self, client):
        """Test that jobs with same correlation ID are idempotent."""
        # First submission
        response1 = client.post(
            "/api/v1/jobs",
            json={"correlation_id": "idempotent-key"},
        )
        assert response1.status_code == 201
        job_id_1 = response1.json()["id"]

        # Second submission with same correlation ID
        response2 = client.post(
            "/api/v1/jobs",
            json={"correlation_id": "idempotent-key"},
        )
        assert response2.status_code == 201
        job_id_2 = response2.json()["id"]

        # Should return the same job
        assert job_id_1 == job_id_2

    def test_submit_job_with_header_correlation_id(self, client):
        """Test submitting a job with correlation ID in header."""
        response = client.post(
            "/api/v1/jobs",
            json={},
            headers={"X-Correlation-ID": "header-test-123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["correlation_id"] == "header-test-123"

    def test_get_job(self, client, repository):
        """Test getting a job by ID."""
        # Create a job first
        job = BlogPostJob(topics=["AI"])
        repository.create_job(job)

        response = client.get(f"/api/v1/jobs/{job.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(job.id)
        assert data["topics"] == ["AI"]

    def test_get_job_not_found(self, client):
        """Test getting a non-existent job."""
        fake_id = uuid4()
        response = client.get(f"/api/v1/jobs/{fake_id}")
        assert response.status_code == 404

    def test_get_job_preview(self, client, repository):
        """Test getting a job preview."""
        job = BlogPostJob(
            title="Test Title",
            content="Test content here",
            score=8.5,
            sources_used=["https://example.com"],
            status=JobStatus.COMPLETED,
        )
        repository.create_job(job)

        response = client.get(f"/api/v1/jobs/{job.id}/preview")
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == "Test Title"
        assert data["content"] == "Test content here"
        assert data["score"] == 8.5

    def test_approve_job(self, client, repository):
        """Test approving a job."""
        job = BlogPostJob(status=JobStatus.COMPLETED)
        repository.create_job(job)

        response = client.post(
            f"/api/v1/jobs/{job.id}/approve",
            json={
                "status": "approved",
                "reviewer": "editor@example.com",
                "reason": "Good article",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["approval_status"] == "approved"

    def test_reject_job(self, client, repository):
        """Test rejecting a job."""
        job = BlogPostJob(status=JobStatus.COMPLETED)
        repository.create_job(job)

        response = client.post(
            f"/api/v1/jobs/{job.id}/approve",
            json={
                "status": "rejected",
                "reviewer": "editor@example.com",
                "reason": "Needs more detail",
                "comments": ["Add examples", "Fix intro"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["approval_status"] == "rejected"

    def test_approve_job_wrong_status(self, client, repository):
        """Test that approving a non-completed job fails."""
        job = BlogPostJob(status=JobStatus.PENDING)
        repository.create_job(job)

        response = client.post(
            f"/api/v1/jobs/{job.id}/approve",
            json={
                "status": "approved",
                "reviewer": "editor@example.com",
            },
        )

        assert response.status_code == 400

    def test_list_jobs_empty(self, client):
        """Test listing jobs when empty."""
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200

        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs(self, client, repository):
        """Test listing jobs."""
        for i in range(5):
            repository.create_job(BlogPostJob(topics=[f"Topic {i}"]))

        response = client.get("/api/v1/jobs")
        assert response.status_code == 200

        data = response.json()
        assert len(data["jobs"]) == 5
        assert data["total"] == 5

    def test_list_jobs_with_status_filter(self, client, repository):
        """Test filtering jobs by status."""
        repository.create_job(BlogPostJob(status=JobStatus.PENDING))
        repository.create_job(BlogPostJob(status=JobStatus.PENDING))
        repository.create_job(BlogPostJob(status=JobStatus.COMPLETED))

        response = client.get("/api/v1/jobs?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert len(data["jobs"]) == 2
        assert all(j["status"] == "pending" for j in data["jobs"])

    def test_list_jobs_pagination(self, client, repository):
        """Test job listing pagination."""
        for i in range(10):
            repository.create_job(BlogPostJob(topics=[f"Topic {i}"]))

        response = client.get("/api/v1/jobs?page=1&per_page=3")
        assert response.status_code == 200

        data = response.json()
        assert len(data["jobs"]) == 3
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert data["total"] == 10

    def test_get_stats(self, client, repository):
        """Test getting job statistics."""
        repository.create_job(BlogPostJob(status=JobStatus.PENDING))
        repository.create_job(BlogPostJob(status=JobStatus.APPROVED))
        repository.create_job(BlogPostJob(status=JobStatus.APPROVED))

        response = client.get("/api/v1/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3
        assert data["pending"] == 1
        assert data["approved"] == 2

    def test_add_comment(self, client, repository):
        """Test adding a comment to a job."""
        job = BlogPostJob()
        repository.create_job(job)

        response = client.post(
            f"/api/v1/jobs/{job.id}/comments",
            params={"author": "editor@example.com", "content": "Great work!"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["author"] == "editor@example.com"
        assert data["content"] == "Great work!"

    def test_get_comments(self, client, repository):
        """Test getting comments for a job."""
        job = BlogPostJob()
        repository.create_job(job)

        # Add a comment via API
        client.post(
            f"/api/v1/jobs/{job.id}/comments",
            params={"author": "editor@example.com", "content": "Comment 1"},
        )

        response = client.get(f"/api/v1/jobs/{job.id}/comments")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Comment 1"

    def test_metrics_endpoint(self, client):
        """Test the metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "counters" in data
        assert "histograms" in data
        assert "gauges" in data

    def test_openapi_endpoint(self, client):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
