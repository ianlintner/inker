"""Tests for the persistence layer."""

import shutil
import tempfile
from datetime import datetime

import pytest

from ai_blogger.persistence import (
    ApprovalStatus,
    BlogPost,
    BlogPostCreate,
    BlogPostUpdate,
    JobHistoryEntry,
    JobStats,
    SQLiteStorage,
    StorageConfig,
    create_storage,
    get_storage_type,
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


class TestPersistenceModels:
    """Tests for persistence models."""

    def test_approval_status_enum(self):
        """Test ApprovalStatus enum values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.REVISION_REQUESTED.value == "revision_requested"

    def test_blog_post_create_defaults(self):
        """Test BlogPostCreate default values."""
        post = BlogPostCreate(
            title="Test Post",
            content="Test content",
            topic="testing",
        )
        assert post.title == "Test Post"
        assert post.content == "Test content"
        assert post.topic == "testing"
        assert post.sources == []
        assert post.job_id is None
        assert post.scoring is None
        assert post.metadata is None

    def test_blog_post_create_with_values(self):
        """Test BlogPostCreate with custom values."""
        post = BlogPostCreate(
            title="Test Post",
            content="Test content",
            topic="testing",
            sources=["https://example.com"],
            job_id="job-123",
            scoring={"total": 8.5},
            metadata={"author": "test"},
        )
        assert post.sources == ["https://example.com"]
        assert post.job_id == "job-123"
        assert post.scoring == {"total": 8.5}
        assert post.metadata == {"author": "test"}

    def test_blog_post_update_optional(self):
        """Test BlogPostUpdate all optional fields."""
        update = BlogPostUpdate()
        assert update.title is None
        assert update.content is None
        assert update.topic is None
        assert update.sources is None
        assert update.approval_status is None
        assert update.approval_feedback is None
        assert update.metadata is None

    def test_blog_post_model(self):
        """Test BlogPost model."""
        now = datetime.now()
        post = BlogPost(
            id="post-123",
            title="Test Post",
            content="Test content",
            word_count=100,
            topic="testing",
            sources=["https://example.com"],
            job_id="job-456",
            approval_status=ApprovalStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        assert post.id == "post-123"
        assert post.title == "Test Post"
        assert post.word_count == 100
        assert post.approval_status == ApprovalStatus.PENDING
        assert post.approved_at is None
        assert post.published_at is None

    def test_job_history_entry_model(self):
        """Test JobHistoryEntry model."""
        now = datetime.now()
        entry = JobHistoryEntry(
            id="entry-123",
            job_id="job-456",
            post_id="post-789",
            action="approved",
            previous_status="pending",
            new_status="approved",
            actor="user-1",
            feedback="Looks good!",
            created_at=now,
        )
        assert entry.id == "entry-123"
        assert entry.job_id == "job-456"
        assert entry.action == "approved"

    def test_job_stats_model(self):
        """Test JobStats model defaults."""
        stats = JobStats()
        assert stats.total_jobs == 0
        assert stats.pending_jobs == 0
        assert stats.completed_jobs == 0
        assert stats.failed_jobs == 0
        assert stats.total_posts == 0
        assert stats.approval_rate is None


class TestStorageFactory:
    """Tests for storage factory."""

    def test_get_storage_type_default(self, monkeypatch):
        """Test storage type detection with no env vars."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert get_storage_type() == "sqlite"

    def test_get_storage_type_postgres(self, monkeypatch):
        """Test storage type detection with PostgreSQL URL."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        assert get_storage_type() == "postgres"

    def test_get_storage_type_postgres_alt(self, monkeypatch):
        """Test storage type detection with alternate PostgreSQL URL."""
        monkeypatch.setenv("DATABASE_URL", "postgres://localhost/test")
        assert get_storage_type() == "postgres"

    def test_create_sqlite_storage(self, temp_storage_dir):
        """Test creating SQLite storage explicitly."""
        storage = create_storage(
            backend_type="sqlite",
            db_path=f"{temp_storage_dir}/test.db",
        )
        assert isinstance(storage, SQLiteStorage)
        storage.close()

    def test_create_storage_unknown_backend(self):
        """Test creating storage with unknown backend type."""
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_storage(backend_type="unknown")


class TestSQLiteStorage:
    """Tests for SQLite storage backend."""

    def test_initialize(self, sqlite_storage):
        """Test storage initialization."""
        assert sqlite_storage.health_check()

    def test_create_post(self, sqlite_storage):
        """Test creating a blog post."""
        create = BlogPostCreate(
            title="Test Post",
            content="This is test content for the blog post.",
            topic="testing",
            sources=["https://example.com"],
            job_id="job-123",
        )
        post = sqlite_storage.create_post(create)

        assert post is not None
        assert post.id is not None
        assert post.title == "Test Post"
        assert post.content == "This is test content for the blog post."
        assert post.topic == "testing"
        assert post.sources == ["https://example.com"]
        assert post.job_id == "job-123"
        assert post.approval_status == ApprovalStatus.PENDING
        # Word count is calculated dynamically from content
        assert post.word_count == len(create.content.split())

    def test_get_post(self, sqlite_storage):
        """Test getting a post by ID."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
        )
        created = sqlite_storage.create_post(create)

        retrieved = sqlite_storage.get_post(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Test Post"

        # Non-existent post
        assert sqlite_storage.get_post("non-existent") is None

    def test_get_post_by_job_id(self, sqlite_storage):
        """Test getting a post by job ID."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
            job_id="job-456",
        )
        sqlite_storage.create_post(create)

        retrieved = sqlite_storage.get_post_by_job_id("job-456")
        assert retrieved is not None
        assert retrieved.job_id == "job-456"

        # Non-existent job ID
        assert sqlite_storage.get_post_by_job_id("non-existent") is None

    def test_update_post(self, sqlite_storage):
        """Test updating a post."""
        create = BlogPostCreate(
            title="Original Title",
            content="Original content",
            topic="testing",
        )
        created = sqlite_storage.create_post(create)

        update = BlogPostUpdate(
            title="Updated Title",
            content="Updated content here",
        )
        updated = sqlite_storage.update_post(created.id, update)

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.content == "Updated content here"
        # Word count is calculated dynamically from updated content
        assert updated.word_count == len(update.content.split())

    def test_delete_post(self, sqlite_storage):
        """Test deleting a post."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
        )
        created = sqlite_storage.create_post(create)

        # Verify exists
        assert sqlite_storage.get_post(created.id) is not None

        # Delete
        assert sqlite_storage.delete_post(created.id)

        # Verify deleted
        assert sqlite_storage.get_post(created.id) is None

        # Delete non-existent
        assert not sqlite_storage.delete_post("non-existent")

    def test_list_posts(self, sqlite_storage):
        """Test listing posts."""
        for i in range(5):
            create = BlogPostCreate(
                title=f"Post {i}",
                content=f"Content {i}",
                topic="testing",
            )
            sqlite_storage.create_post(create)

        posts = sqlite_storage.list_posts()
        assert len(posts) == 5

        # Test with limit
        limited = sqlite_storage.list_posts(limit=3)
        assert len(limited) == 3

    def test_list_posts_with_status_filter(self, sqlite_storage):
        """Test listing posts with status filter."""
        # Create pending posts
        for i in range(3):
            create = BlogPostCreate(
                title=f"Pending {i}",
                content=f"Content {i}",
                topic="testing",
            )
            sqlite_storage.create_post(create)

        # Approve one
        posts = sqlite_storage.list_posts()
        sqlite_storage.approve_post(posts[0].id)

        pending = sqlite_storage.list_posts(approval_status=ApprovalStatus.PENDING)
        assert len(pending) == 2

        approved = sqlite_storage.list_posts(approval_status=ApprovalStatus.APPROVED)
        assert len(approved) == 1

    def test_approve_post(self, sqlite_storage):
        """Test approving a post."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
            job_id="job-123",
        )
        created = sqlite_storage.create_post(create)

        approved = sqlite_storage.approve_post(
            created.id,
            feedback="Excellent content!",
            actor="reviewer-1",
        )

        assert approved is not None
        assert approved.approval_status == ApprovalStatus.APPROVED
        assert approved.approval_feedback == "Excellent content!"
        assert approved.approved_at is not None

        # Check history
        history = sqlite_storage.get_post_history(created.id)
        assert len(history) >= 1
        approved_entry = [h for h in history if h.action == "approved"][0]
        assert approved_entry.actor == "reviewer-1"
        assert approved_entry.new_status == "approved"

    def test_reject_post(self, sqlite_storage):
        """Test rejecting a post."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
            job_id="job-123",
        )
        created = sqlite_storage.create_post(create)

        rejected = sqlite_storage.reject_post(
            created.id,
            feedback="Needs more research",
            actor="reviewer-1",
        )

        assert rejected is not None
        assert rejected.approval_status == ApprovalStatus.REJECTED
        assert rejected.approval_feedback == "Needs more research"

    def test_request_revision(self, sqlite_storage):
        """Test requesting revision for a post."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
            job_id="job-123",
        )
        created = sqlite_storage.create_post(create)

        revision = sqlite_storage.request_revision(
            created.id,
            feedback="Please add more examples",
            actor="reviewer-1",
        )

        assert revision is not None
        assert revision.approval_status == ApprovalStatus.REVISION_REQUESTED
        assert revision.approval_feedback == "Please add more examples"

    def test_publish_post(self, sqlite_storage):
        """Test publishing an approved post."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
            job_id="job-123",
        )
        created = sqlite_storage.create_post(create)

        # Cannot publish unapproved post
        assert sqlite_storage.publish_post(created.id) is None

        # Approve first
        sqlite_storage.approve_post(created.id)

        # Now can publish
        published = sqlite_storage.publish_post(created.id)
        assert published is not None
        assert published.published_at is not None

    def test_get_job_history(self, sqlite_storage):
        """Test getting job history."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
            job_id="job-123",
        )
        created = sqlite_storage.create_post(create)
        sqlite_storage.approve_post(created.id)
        sqlite_storage.publish_post(created.id)

        history = sqlite_storage.get_job_history("job-123")
        assert len(history) >= 3  # created, approved, published

        # Verify order (ascending by created_at)
        actions = [h.action for h in history]
        assert "post_created" in actions
        assert "approved" in actions
        assert "published" in actions

    def test_get_post_history(self, sqlite_storage):
        """Test getting post history."""
        create = BlogPostCreate(
            title="Test Post",
            content="Content",
            topic="testing",
            job_id="job-123",
        )
        created = sqlite_storage.create_post(create)
        sqlite_storage.reject_post(created.id, "Not good enough")
        sqlite_storage.request_revision(created.id, "Add more info")

        history = sqlite_storage.get_post_history(created.id)
        assert len(history) >= 3  # created, rejected, revision_requested

    def test_get_stats(self, sqlite_storage):
        """Test getting statistics."""
        # Create some posts in different states
        for i in range(3):
            create = BlogPostCreate(
                title=f"Pending {i}",
                content=f"Content {i}",
                topic="testing",
            )
            sqlite_storage.create_post(create)

        posts = sqlite_storage.list_posts()
        sqlite_storage.approve_post(posts[0].id)
        sqlite_storage.reject_post(posts[1].id, "Not good")

        stats = sqlite_storage.get_stats()
        assert stats.total_posts == 3
        assert stats.pending_approval == 1
        assert stats.approved_posts == 1
        assert stats.rejected_posts == 1

    def test_health_check(self, sqlite_storage):
        """Test health check."""
        assert sqlite_storage.health_check()


class TestPersistenceImports:
    """Test that all persistence components are properly exported."""

    def test_imports(self):
        """Test that all persistence components can be imported."""
        from ai_blogger import (
            ApprovalStatus,
            BlogPost,
            BlogPostCreate,
            BlogPostUpdate,
            JobHistoryEntry,
            JobStats,
            SQLiteStorage,
            StorageBackend,
            StorageConfig,
            create_storage,
            get_storage_type,
        )

        # All imports should succeed
        assert StorageBackend is not None
        assert StorageConfig is not None
        assert create_storage is not None
        assert get_storage_type is not None
        assert ApprovalStatus is not None
        assert BlogPost is not None
        assert BlogPostCreate is not None
        assert BlogPostUpdate is not None
        assert JobHistoryEntry is not None
        assert JobStats is not None
        assert SQLiteStorage is not None
