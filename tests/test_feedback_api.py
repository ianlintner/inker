"""Tests for the Blog Post Feedback API."""

import shutil
import tempfile
from datetime import datetime

import pytest

from ai_blogger import (
    ApprovalRequest,
    ApprovalStatus,
    BlogPostCreate,
    FeedbackCategory,
    FeedbackEntry,
    FeedbackRating,
    FeedbackResponse,
    FeedbackService,
    FeedbackStats,
    RejectionRequest,
    RevisionRequest,
    SQLiteStorage,
    StorageConfig,
)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


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


class TestFeedbackModels:
    """Tests for feedback models."""

    def test_feedback_category_enum(self):
        """Test FeedbackCategory enum values."""
        assert FeedbackCategory.QUALITY.value == "quality"
        assert FeedbackCategory.RELEVANCE.value == "relevance"
        assert FeedbackCategory.ACCURACY.value == "accuracy"
        assert FeedbackCategory.CLARITY.value == "clarity"
        assert FeedbackCategory.ENGAGEMENT.value == "engagement"
        assert FeedbackCategory.LENGTH.value == "length"
        assert FeedbackCategory.STYLE.value == "style"
        assert FeedbackCategory.SOURCES.value == "sources"
        assert FeedbackCategory.OTHER.value == "other"

    def test_feedback_rating_model(self):
        """Test FeedbackRating model."""
        rating = FeedbackRating(
            category=FeedbackCategory.QUALITY,
            score=4,
            comment="Good overall quality",
        )
        assert rating.category == FeedbackCategory.QUALITY
        assert rating.score == 4
        assert rating.comment == "Good overall quality"

    def test_feedback_rating_validation(self):
        """Test FeedbackRating validation."""
        # Score must be >= 1
        with pytest.raises(ValueError):
            FeedbackRating(category=FeedbackCategory.QUALITY, score=0)

        # Score must be <= 5
        with pytest.raises(ValueError):
            FeedbackRating(category=FeedbackCategory.QUALITY, score=6)

    def test_approval_request_model(self):
        """Test ApprovalRequest model."""
        request = ApprovalRequest(
            post_id="post-123",
            feedback="Excellent content!",
            ratings=[
                FeedbackRating(category=FeedbackCategory.QUALITY, score=5),
                FeedbackRating(category=FeedbackCategory.CLARITY, score=4),
            ],
            actor="reviewer-1",
        )
        assert request.post_id == "post-123"
        assert request.feedback == "Excellent content!"
        assert len(request.ratings) == 2
        assert request.actor == "reviewer-1"

    def test_rejection_request_model(self):
        """Test RejectionRequest model."""
        request = RejectionRequest(
            post_id="post-123",
            feedback="Needs more research",
            categories=[FeedbackCategory.ACCURACY, FeedbackCategory.SOURCES],
            actor="reviewer-1",
        )
        assert request.post_id == "post-123"
        assert request.feedback == "Needs more research"
        assert len(request.categories) == 2
        assert FeedbackCategory.ACCURACY in request.categories

    def test_revision_request_model(self):
        """Test RevisionRequest model."""
        request = RevisionRequest(
            post_id="post-123",
            feedback="Please add more examples",
            categories=[FeedbackCategory.CLARITY],
            actor="reviewer-1",
        )
        assert request.post_id == "post-123"
        assert request.feedback == "Please add more examples"
        assert len(request.categories) == 1

    def test_feedback_entry_model(self):
        """Test FeedbackEntry model."""
        now = datetime.now()
        entry = FeedbackEntry(
            id="entry-123",
            post_id="post-456",
            job_id="job-789",
            action="approved",
            feedback="Good work!",
            categories=[],
            ratings=[FeedbackRating(category=FeedbackCategory.QUALITY, score=5)],
            actor="reviewer-1",
            post_scoring={"total": 8.5},
            post_topic="testing",
            post_word_count=500,
            created_at=now,
        )
        assert entry.id == "entry-123"
        assert entry.action == "approved"
        assert len(entry.ratings) == 1

    def test_feedback_stats_model(self):
        """Test FeedbackStats model."""
        stats = FeedbackStats(
            total_feedback=100,
            approvals=70,
            rejections=20,
            revisions=10,
            approval_rate=70.0,
        )
        assert stats.total_feedback == 100
        assert stats.approvals == 70
        assert stats.approval_rate == 70.0

    def test_feedback_response_model(self):
        """Test FeedbackResponse model."""
        response = FeedbackResponse(
            success=True,
            post_id="post-123",
            new_status="approved",
            feedback_id="feedback-456",
            message="Post approved successfully",
        )
        assert response.success is True
        assert response.post_id == "post-123"
        assert response.new_status == "approved"


class TestFeedbackService:
    """Tests for FeedbackService."""

    def test_approve_post(self, feedback_service, sample_post, sqlite_storage):
        """Test approving a post."""
        request = ApprovalRequest(
            post_id=sample_post.id,
            feedback="Excellent content!",
            ratings=[
                FeedbackRating(category=FeedbackCategory.QUALITY, score=5),
                FeedbackRating(category=FeedbackCategory.CLARITY, score=4),
            ],
            actor="reviewer-1",
        )

        response = feedback_service.approve_post(request)

        assert response.success is True
        assert response.post_id == sample_post.id
        assert response.new_status == "approved"
        assert response.feedback_id is not None
        assert "approved successfully" in response.message

        # Verify post status is updated
        updated_post = sqlite_storage.get_post(sample_post.id)
        assert updated_post is not None
        assert updated_post.approval_status == ApprovalStatus.APPROVED

    def test_approve_nonexistent_post(self, feedback_service):
        """Test approving a non-existent post."""
        request = ApprovalRequest(
            post_id="nonexistent",
            feedback="Good job!",
        )

        response = feedback_service.approve_post(request)

        assert response.success is False
        assert "not found" in response.message

    def test_reject_post(self, feedback_service, sample_post, sqlite_storage):
        """Test rejecting a post."""
        request = RejectionRequest(
            post_id=sample_post.id,
            feedback="Needs more research and better sources",
            categories=[FeedbackCategory.ACCURACY, FeedbackCategory.SOURCES],
            ratings=[
                FeedbackRating(category=FeedbackCategory.ACCURACY, score=2),
            ],
            actor="reviewer-1",
        )

        response = feedback_service.reject_post(request)

        assert response.success is True
        assert response.post_id == sample_post.id
        assert response.new_status == "rejected"
        assert response.feedback_id is not None

        # Verify post status is updated
        updated_post = sqlite_storage.get_post(sample_post.id)
        assert updated_post is not None
        assert updated_post.approval_status == ApprovalStatus.REJECTED
        assert updated_post.approval_feedback == "Needs more research and better sources"

    def test_reject_nonexistent_post(self, feedback_service):
        """Test rejecting a non-existent post."""
        request = RejectionRequest(
            post_id="nonexistent",
            feedback="Not good",
        )

        response = feedback_service.reject_post(request)

        assert response.success is False
        assert "not found" in response.message

    def test_request_revision(self, feedback_service, sample_post, sqlite_storage):
        """Test requesting revision for a post."""
        request = RevisionRequest(
            post_id=sample_post.id,
            feedback="Please add more examples and clarify the introduction",
            categories=[FeedbackCategory.CLARITY, FeedbackCategory.ENGAGEMENT],
            actor="reviewer-1",
        )

        response = feedback_service.request_revision(request)

        assert response.success is True
        assert response.post_id == sample_post.id
        assert response.new_status == "revision_requested"
        assert response.feedback_id is not None

        # Verify post status is updated
        updated_post = sqlite_storage.get_post(sample_post.id)
        assert updated_post is not None
        assert updated_post.approval_status == ApprovalStatus.REVISION_REQUESTED

    def test_request_revision_nonexistent_post(self, feedback_service):
        """Test requesting revision for a non-existent post."""
        request = RevisionRequest(
            post_id="nonexistent",
            feedback="Needs work",
        )

        response = feedback_service.request_revision(request)

        assert response.success is False
        assert "not found" in response.message

    def test_get_post_feedback(self, feedback_service, sample_post):
        """Test getting feedback history for a post."""
        # First, add some feedback through approval
        approval = ApprovalRequest(
            post_id=sample_post.id,
            feedback="Great content!",
            ratings=[FeedbackRating(category=FeedbackCategory.QUALITY, score=5)],
            actor="reviewer-1",
        )
        feedback_service.approve_post(approval)

        # Get feedback
        feedback = feedback_service.get_post_feedback(sample_post.id)

        assert len(feedback) >= 1
        approved_feedback = [f for f in feedback if f.action == "approved"]
        assert len(approved_feedback) == 1
        assert approved_feedback[0].feedback == "Great content!"
        assert approved_feedback[0].actor == "reviewer-1"

    def test_get_feedback_stats(self, feedback_service, sqlite_storage):
        """Test getting feedback statistics."""
        # Create some posts with different statuses
        for i in range(3):
            create = BlogPostCreate(
                title=f"Post {i}",
                content=f"Content {i} with some words",
                topic="testing",
            )
            post = sqlite_storage.create_post(create)

            if i == 0:
                feedback_service.approve_post(ApprovalRequest(post_id=post.id, feedback="Good"))
            elif i == 1:
                feedback_service.reject_post(RejectionRequest(post_id=post.id, feedback="Bad"))
            # Third post stays pending

        stats = feedback_service.get_feedback_stats()

        assert stats.total_feedback == 3
        assert stats.approvals == 1
        assert stats.rejections == 1
        assert stats.approval_rate is not None
        assert "testing" in stats.feedback_by_topic

    def test_get_learning_data(self, feedback_service, sqlite_storage):
        """Test getting learning data."""
        # Create and approve a post
        create = BlogPostCreate(
            title="Learning Post",
            content="Content for learning purposes",
            topic="learning",
            scoring={"total": 8.0},
        )
        post = sqlite_storage.create_post(create)
        feedback_service.approve_post(ApprovalRequest(post_id=post.id, feedback="Excellent for learning"))

        # Create and reject a post
        create2 = BlogPostCreate(
            title="Rejected Post",
            content="Content that needs improvement",
            topic="testing",
            scoring={"total": 5.0},
        )
        post2 = sqlite_storage.create_post(create2)
        feedback_service.reject_post(RejectionRequest(post_id=post2.id, feedback="Needs more research"))

        learning_data = feedback_service.get_learning_data(limit=10)

        assert len(learning_data) == 2
        approved_data = [d for d in learning_data if d["outcome"] == "approved"]
        rejected_data = [d for d in learning_data if d["outcome"] == "rejected"]

        assert len(approved_data) == 1
        assert len(rejected_data) == 1
        assert approved_data[0]["feedback"] == "Excellent for learning"
        assert rejected_data[0]["feedback"] == "Needs more research"


class TestFeedbackAPIImports:
    """Test that all Feedback API components are properly exported."""

    def test_imports(self):
        """Test that all Feedback API components can be imported."""
        from ai_blogger import (
            ApprovalRequest,
            FeedbackCategory,
            FeedbackEntry,
            FeedbackRating,
            FeedbackResponse,
            FeedbackService,
            FeedbackStats,
            RejectionRequest,
            RevisionRequest,
        )

        # All imports should succeed
        assert FeedbackService is not None
        assert ApprovalRequest is not None
        assert RejectionRequest is not None
        assert RevisionRequest is not None
        assert FeedbackCategory is not None
        assert FeedbackRating is not None
        assert FeedbackEntry is not None
        assert FeedbackStats is not None
        assert FeedbackResponse is not None
