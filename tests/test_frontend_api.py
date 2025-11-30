"""Tests for the Frontend API endpoints."""

import shutil
import tempfile
from datetime import datetime

import pytest

# Import FastAPI test client
from fastapi.testclient import TestClient

from ai_blogger import (
    ApprovalRequest,
    ApprovalStatus,
    BlogPostCreate,
    FeedbackService,
    JobRequest,
    JobService,
    JobStatus,
    SQLiteStorage,
    StorageConfig,
)
from ai_blogger.frontend_api import (
    ApprovePostRequest,
    HealthResponse,
    JobListResponse,
    JobSubmitRequest,
    PreviewResponse,
    RejectPostRequest,
    RevisionPostRequest,
    configure_services,
    create_app,
    reset_services,
    router,
)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def job_service(temp_storage_dir):
    """Create a JobService with temporary storage."""
    return JobService(temp_storage_dir)


@pytest.fixture
def sqlite_storage(temp_storage_dir):
    """Create a SQLite storage with temporary directory."""
    config = StorageConfig(
        backend_type="sqlite",
        db_path=f"{temp_storage_dir}/test.db",
        auto_migrate=True,
    )
    storage = SQLiteStorage(config)
    yield storage
    storage.close()


@pytest.fixture
def feedback_service(sqlite_storage):
    """Create a FeedbackService with SQLite storage."""
    return FeedbackService(sqlite_storage)


@pytest.fixture
def test_client(job_service, feedback_service, sqlite_storage):
    """Create a test client with configured services."""
    # Reset and configure services before each test
    reset_services()
    configure_services(
        job_service=job_service,
        feedback_service=feedback_service,
        storage=sqlite_storage,
    )

    app = create_app()
    client = TestClient(app)
    yield client

    # Cleanup
    reset_services()


@pytest.fixture
def sample_post(sqlite_storage):
    """Create a sample blog post for testing."""
    create = BlogPostCreate(
        title="Test Post",
        content="This is test content for the blog post.",
        topic="testing",
        sources=["https://example.com"],
        job_id="job-123",
        scoring={"total": 8.5, "relevance": 8.0, "clarity": 9.0},
    )
    return sqlite_storage.create_post(create)


class TestRequestModels:
    """Tests for API request/response models."""

    def test_job_submit_request_defaults(self):
        """Test JobSubmitRequest default values."""
        request = JobSubmitRequest()
        assert request.topics is None
        assert request.sources is None
        assert request.num_candidates == 3
        assert request.max_results is None
        assert request.correlation_id is None

    def test_job_submit_request_with_values(self):
        """Test JobSubmitRequest with custom values."""
        request = JobSubmitRequest(
            topics=["AI", "ML"],
            sources=["hacker_news"],
            num_candidates=5,
            correlation_id="test-123",
        )
        assert request.topics == ["AI", "ML"]
        assert request.sources == ["hacker_news"]
        assert request.num_candidates == 5
        assert request.correlation_id == "test-123"

    def test_job_list_response_model(self):
        """Test JobListResponse model."""
        response = JobListResponse(jobs=[], total=0)
        assert response.jobs == []
        assert response.total == 0

    def test_preview_response_model(self):
        """Test PreviewResponse model."""
        response = PreviewResponse(
            success=True,
            preview=None,
            message="No preview available",
        )
        assert response.success is True
        assert response.preview is None
        assert response.message == "No preview available"

    def test_approve_post_request_model(self):
        """Test ApprovePostRequest model."""
        request = ApprovePostRequest(
            feedback="Excellent content!",
            actor="reviewer-1",
        )
        assert request.feedback == "Excellent content!"
        assert request.actor == "reviewer-1"
        assert request.ratings == []

    def test_reject_post_request_model(self):
        """Test RejectPostRequest model."""
        request = RejectPostRequest(
            feedback="Needs more research",
        )
        assert request.feedback == "Needs more research"
        assert request.categories == []

    def test_revision_post_request_model(self):
        """Test RevisionPostRequest model."""
        request = RevisionPostRequest(
            feedback="Please add more examples",
        )
        assert request.feedback == "Please add more examples"
        assert request.categories == []

    def test_health_response_model(self):
        """Test HealthResponse model."""
        response = HealthResponse(
            status="healthy",
            job_service=True,
            feedback_service=True,
            storage=True,
        )
        assert response.status == "healthy"
        assert response.job_service is True


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["job_service"] is True
        assert data["storage"] is True


class TestJobEndpoints:
    """Tests for job API endpoints."""

    def test_submit_job(self, test_client):
        """Test submitting a new job."""
        response = test_client.post(
            "/api/jobs",
            json={"topics": ["AI"], "num_candidates": 3},
        )
        assert response.status_code == 201

        data = response.json()
        assert data["job_id"] is not None
        assert data["status"] == "pending"
        assert data["is_duplicate"] is False

    def test_submit_job_with_correlation_id(self, test_client):
        """Test submitting a job with correlation ID."""
        response = test_client.post(
            "/api/jobs",
            json={"correlation_id": "unique-key"},
        )
        assert response.status_code == 201

        data = response.json()
        assert data["correlation_id"] == "unique-key"
        assert data["is_duplicate"] is False

    def test_submit_duplicate_job(self, test_client):
        """Test that duplicate correlation IDs return existing job."""
        # First submission
        response1 = test_client.post(
            "/api/jobs",
            json={"correlation_id": "idempotent-key"},
        )
        assert response1.status_code == 201
        job_id1 = response1.json()["job_id"]

        # Second submission with same correlation ID
        response2 = test_client.post(
            "/api/jobs",
            json={"correlation_id": "idempotent-key"},
        )
        assert response2.status_code == 201

        data = response2.json()
        assert data["is_duplicate"] is True
        assert data["job_id"] == job_id1

    def test_list_jobs(self, test_client):
        """Test listing jobs."""
        # Submit several jobs
        for i in range(3):
            test_client.post(
                "/api/jobs",
                json={"topics": [f"topic-{i}"]},
            )

        response = test_client.get("/api/jobs")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3
        assert len(data["jobs"]) == 3

    def test_list_jobs_with_limit(self, test_client):
        """Test listing jobs with limit."""
        # Submit several jobs
        for i in range(5):
            test_client.post(
                "/api/jobs",
                json={"topics": [f"topic-{i}"]},
            )

        response = test_client.get("/api/jobs?limit=2")
        assert response.status_code == 200

        data = response.json()
        assert len(data["jobs"]) == 2

    def test_get_job_status(self, test_client):
        """Test getting job status."""
        # Submit a job
        submit_response = test_client.post(
            "/api/jobs",
            json={"topics": ["testing"]},
        )
        job_id = submit_response.json()["job_id"]

        # Get status
        response = test_client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "pending"

    def test_get_job_status_not_found(self, test_client):
        """Test getting status of non-existent job."""
        response = test_client.get("/api/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_get_job_by_correlation_id(self, test_client):
        """Test getting job by correlation ID."""
        # Submit a job with correlation ID
        test_client.post(
            "/api/jobs",
            json={"correlation_id": "lookup-key"},
        )

        # Look up by correlation ID
        response = test_client.get("/api/jobs/correlation/lookup-key")
        assert response.status_code == 200

        data = response.json()
        assert data["correlation_id"] == "lookup-key"

    def test_get_job_by_correlation_id_not_found(self, test_client):
        """Test looking up non-existent correlation ID."""
        response = test_client.get("/api/jobs/correlation/missing-key")
        assert response.status_code == 404

    def test_delete_job(self, test_client):
        """Test deleting a job."""
        # Submit a job
        submit_response = test_client.post(
            "/api/jobs",
            json={"topics": ["testing"]},
        )
        job_id = submit_response.json()["job_id"]

        # Delete
        response = test_client.delete(f"/api/jobs/{job_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = test_client.get(f"/api/jobs/{job_id}")
        assert get_response.status_code == 404

    def test_delete_job_not_found(self, test_client):
        """Test deleting non-existent job."""
        response = test_client.delete("/api/jobs/nonexistent-id")
        assert response.status_code == 404


class TestPreviewEndpoints:
    """Tests for preview API endpoints."""

    def test_get_preview_job_not_found(self, test_client):
        """Test getting preview for non-existent job."""
        response = test_client.get("/api/jobs/nonexistent-id/preview")
        assert response.status_code == 404

    def test_get_preview_job_not_completed(self, test_client):
        """Test getting preview for pending job."""
        # Submit a job (will be in pending status)
        submit_response = test_client.post(
            "/api/jobs",
            json={"topics": ["testing"]},
        )
        job_id = submit_response.json()["job_id"]

        # Try to get preview
        response = test_client.get(f"/api/jobs/{job_id}/preview")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert "not completed" in data["message"]


class TestApprovalWorkflowEndpoints:
    """Tests for approval workflow API endpoints."""

    def test_approve_post(self, test_client, sample_post, sqlite_storage):
        """Test approving a post."""
        response = test_client.post(
            f"/api/posts/{sample_post.id}/approve",
            json={"feedback": "Excellent content!", "actor": "reviewer-1"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "approved"

        # Verify post status is updated
        updated_post = sqlite_storage.get_post(sample_post.id)
        assert updated_post.approval_status == ApprovalStatus.APPROVED

    def test_approve_post_not_found(self, test_client):
        """Test approving non-existent post."""
        response = test_client.post(
            "/api/posts/nonexistent/approve",
            json={"feedback": "Good"},
        )
        assert response.status_code == 404

    def test_reject_post(self, test_client, sample_post, sqlite_storage):
        """Test rejecting a post."""
        response = test_client.post(
            f"/api/posts/{sample_post.id}/reject",
            json={"feedback": "Needs more research", "actor": "reviewer-1"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "rejected"

        # Verify post status is updated
        updated_post = sqlite_storage.get_post(sample_post.id)
        assert updated_post.approval_status == ApprovalStatus.REJECTED

    def test_reject_post_not_found(self, test_client):
        """Test rejecting non-existent post."""
        response = test_client.post(
            "/api/posts/nonexistent/reject",
            json={"feedback": "Bad content"},
        )
        assert response.status_code == 404

    def test_request_revision(self, test_client, sample_post, sqlite_storage):
        """Test requesting revision for a post."""
        response = test_client.post(
            f"/api/posts/{sample_post.id}/revision",
            json={"feedback": "Please add more examples", "actor": "reviewer-1"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "revision_requested"

        # Verify post status is updated
        updated_post = sqlite_storage.get_post(sample_post.id)
        assert updated_post.approval_status == ApprovalStatus.REVISION_REQUESTED

    def test_request_revision_not_found(self, test_client):
        """Test requesting revision for non-existent post."""
        response = test_client.post(
            "/api/posts/nonexistent/revision",
            json={"feedback": "Needs work"},
        )
        assert response.status_code == 404

    def test_get_post_feedback(self, test_client, sample_post):
        """Test getting feedback history for a post."""
        # First approve the post
        test_client.post(
            f"/api/posts/{sample_post.id}/approve",
            json={"feedback": "Great content!", "actor": "reviewer-1"},
        )

        # Get feedback
        response = test_client.get(f"/api/posts/{sample_post.id}/feedback")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        approved_feedback = [f for f in data if f["action"] == "approved"]
        assert len(approved_feedback) == 1
        assert approved_feedback[0]["feedback"] == "Great content!"


class TestFeedbackStatsEndpoints:
    """Tests for feedback stats endpoints."""

    def test_get_feedback_stats(self, test_client):
        """Test getting feedback statistics."""
        response = test_client.get("/api/feedback/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_feedback" in data
        assert "approvals" in data
        assert "rejections" in data

    def test_get_learning_data(self, test_client):
        """Test getting learning data."""
        response = test_client.get("/api/feedback/learning")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_get_learning_data_with_limit(self, test_client):
        """Test getting learning data with limit."""
        response = test_client.get("/api/feedback/learning?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)


class TestFrontendAPIImports:
    """Test that all Frontend API components are properly exported."""

    def test_imports(self):
        """Test that all Frontend API components can be imported."""
        from ai_blogger import (
            configure_services,
            create_app,
            reset_services,
            router,
        )

        # All imports should succeed (may be None if FastAPI not installed)
        assert create_app is not None
        assert router is not None
        assert configure_services is not None
        assert reset_services is not None

    def test_router_is_api_router(self):
        """Test that router is a FastAPI APIRouter."""
        from fastapi import APIRouter

        assert isinstance(router, APIRouter)

    def test_create_app_returns_fastapi(self):
        """Test that create_app returns a FastAPI application."""
        from fastapi import FastAPI

        app = create_app()
        assert isinstance(app, FastAPI)


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_default(self):
        """Test creating app with defaults."""
        app = create_app()

        assert app.title == "AI Blogger Frontend API"
        assert app.version == "1.0.0"

    def test_create_app_custom(self):
        """Test creating app with custom settings."""
        app = create_app(
            title="Custom API",
            description="Custom description",
            version="2.0.0",
            cors_origins=["http://localhost:3000"],
        )

        assert app.title == "Custom API"
        assert app.version == "2.0.0"
