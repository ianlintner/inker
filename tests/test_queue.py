"""Tests for the job queue layer."""

from datetime import datetime, timedelta

import pytest

from ai_blogger.queue import (
    MemoryQueue,
    QueueJob,
    QueueJobCreate,
    QueueJobStatus,
    QueueJobUpdate,
    QueueStats,
    create_queue,
    get_queue_type,
)
from ai_blogger.queue.models import RetryPolicy


@pytest.fixture
def memory_queue():
    """Create a memory queue for testing."""
    queue = create_queue("memory")
    yield queue
    queue.close()


class TestQueueModels:
    """Tests for queue models."""

    def test_queue_job_status_enum(self):
        """Test QueueJobStatus enum values."""
        assert QueueJobStatus.PENDING.value == "pending"
        assert QueueJobStatus.PROCESSING.value == "processing"
        assert QueueJobStatus.COMPLETED.value == "completed"
        assert QueueJobStatus.FAILED.value == "failed"
        assert QueueJobStatus.RETRYING.value == "retrying"
        assert QueueJobStatus.DEAD.value == "dead"

    def test_queue_job_create_defaults(self):
        """Test QueueJobCreate default values."""
        job = QueueJobCreate(job_type="test_job")
        assert job.job_type == "test_job"
        assert job.payload == {}
        assert job.priority == 0
        assert job.max_retries == 3
        assert job.correlation_id is None
        assert job.scheduled_at is None
        assert job.metadata is None

    def test_queue_job_create_with_values(self):
        """Test QueueJobCreate with custom values."""
        job = QueueJobCreate(
            job_type="blog_post_generation",
            payload={"topic": "AI"},
            priority=5,
            max_retries=5,
            correlation_id="unique-123",
            metadata={"source": "api"},
        )
        assert job.job_type == "blog_post_generation"
        assert job.payload == {"topic": "AI"}
        assert job.priority == 5
        assert job.max_retries == 5
        assert job.correlation_id == "unique-123"

    def test_queue_job_create_validation(self):
        """Test QueueJobCreate validation."""
        # Priority must be >= -100
        with pytest.raises(ValueError):
            QueueJobCreate(job_type="test", priority=-101)

        # Priority must be <= 100
        with pytest.raises(ValueError):
            QueueJobCreate(job_type="test", priority=101)

        # max_retries must be >= 0
        with pytest.raises(ValueError):
            QueueJobCreate(job_type="test", max_retries=-1)

    def test_queue_job_model(self):
        """Test QueueJob model."""
        now = datetime.now()
        job = QueueJob(
            id="job-123",
            job_type="test_job",
            payload={"key": "value"},
            status=QueueJobStatus.PENDING,
            priority=5,
            correlation_id="corr-456",
            max_retries=3,
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        assert job.id == "job-123"
        assert job.job_type == "test_job"
        assert job.status == QueueJobStatus.PENDING
        assert job.result is None
        assert job.error_message is None

    def test_queue_stats_model(self):
        """Test QueueStats model defaults."""
        stats = QueueStats()
        assert stats.total_jobs == 0
        assert stats.pending_jobs == 0
        assert stats.processing_jobs == 0
        assert stats.completed_jobs == 0
        assert stats.avg_processing_time_seconds is None

    def test_retry_policy_delay(self):
        """Test RetryPolicy delay calculation."""
        policy = RetryPolicy(
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
            exponential_backoff=True,
            jitter=False,
        )

        # First retry: 1 second
        assert policy.get_delay(0) == 1.0

        # Second retry: 2 seconds
        assert policy.get_delay(1) == 2.0

        # Third retry: 4 seconds
        assert policy.get_delay(2) == 4.0

        # Should cap at max
        assert policy.get_delay(10) == 60.0

    def test_retry_policy_no_exponential(self):
        """Test RetryPolicy without exponential backoff."""
        policy = RetryPolicy(
            base_delay_seconds=5.0,
            exponential_backoff=False,
            jitter=False,
        )

        # All retries should have same delay
        assert policy.get_delay(0) == 5.0
        assert policy.get_delay(1) == 5.0
        assert policy.get_delay(5) == 5.0


class TestQueueFactory:
    """Tests for queue factory."""

    def test_get_queue_type_default(self, monkeypatch):
        """Test queue type detection with no env vars."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert get_queue_type() == "memory"

    def test_get_queue_type_redis(self, monkeypatch):
        """Test queue type detection with Redis URL."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        assert get_queue_type() == "redis"

    def test_get_queue_type_postgres(self, monkeypatch):
        """Test queue type detection with PostgreSQL URL."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        assert get_queue_type() == "postgres"

    def test_create_memory_queue(self):
        """Test creating memory queue explicitly."""
        queue = create_queue("memory")
        assert isinstance(queue, MemoryQueue)
        queue.close()

    def test_create_queue_unknown_backend(self):
        """Test creating queue with unknown backend type."""
        with pytest.raises(ValueError, match="Unknown queue backend"):
            create_queue(backend_type="unknown")


class TestMemoryQueue:
    """Tests for in-memory queue backend."""

    def test_initialize(self, memory_queue):
        """Test queue initialization."""
        assert memory_queue.health_check()

    def test_enqueue_job(self, memory_queue):
        """Test enqueueing a job."""
        job_create = QueueJobCreate(
            job_type="blog_post_generation",
            payload={"topic": "AI"},
        )
        job = memory_queue.enqueue(job_create)

        assert job is not None
        assert job.id is not None
        assert job.job_type == "blog_post_generation"
        assert job.payload == {"topic": "AI"}
        assert job.status == QueueJobStatus.PENDING

    def test_enqueue_with_correlation_id(self, memory_queue):
        """Test enqueueing with correlation ID."""
        job_create = QueueJobCreate(
            job_type="test",
            correlation_id="unique-123",
        )
        job = memory_queue.enqueue(job_create)

        assert job.correlation_id == "unique-123"

        # Duplicate correlation ID should fail
        with pytest.raises(ValueError, match="already exists"):
            memory_queue.enqueue(job_create)

    def test_dequeue_job(self, memory_queue):
        """Test dequeuing a job."""
        job_create = QueueJobCreate(job_type="test")
        enqueued = memory_queue.enqueue(job_create)

        dequeued = memory_queue.dequeue(worker_id="worker-1")

        assert dequeued is not None
        assert dequeued.id == enqueued.id
        assert dequeued.status == QueueJobStatus.PROCESSING
        assert dequeued.started_at is not None
        assert dequeued.locked_by == "worker-1"

    def test_dequeue_empty_queue(self, memory_queue):
        """Test dequeuing from empty queue."""
        result = memory_queue.dequeue()
        assert result is None

    def test_dequeue_with_job_type_filter(self, memory_queue):
        """Test dequeuing with job type filter."""
        memory_queue.enqueue(QueueJobCreate(job_type="type_a"))
        memory_queue.enqueue(QueueJobCreate(job_type="type_b"))

        # Only get type_b
        job = memory_queue.dequeue(job_types=["type_b"])
        assert job is not None
        assert job.job_type == "type_b"

    def test_priority_ordering(self, memory_queue):
        """Test that higher priority jobs are dequeued first."""
        # Enqueue in non-priority order
        memory_queue.enqueue(QueueJobCreate(job_type="low", priority=1))
        memory_queue.enqueue(QueueJobCreate(job_type="high", priority=10))
        memory_queue.enqueue(QueueJobCreate(job_type="medium", priority=5))

        # Should dequeue in priority order
        job1 = memory_queue.dequeue()
        assert job1.job_type == "high"

        job2 = memory_queue.dequeue()
        assert job2.job_type == "medium"

        job3 = memory_queue.dequeue()
        assert job3.job_type == "low"

    def test_scheduled_job(self, memory_queue):
        """Test that scheduled jobs are not dequeued before their time."""
        future = datetime.now() + timedelta(hours=1)
        memory_queue.enqueue(
            QueueJobCreate(
                job_type="scheduled",
                scheduled_at=future,
            )
        )

        # Should not be dequeued yet
        job = memory_queue.dequeue()
        assert job is None

    def test_complete_job(self, memory_queue):
        """Test completing a job."""
        job_create = QueueJobCreate(job_type="test")
        enqueued = memory_queue.enqueue(job_create)
        memory_queue.dequeue()

        result = {"output": "success"}
        completed = memory_queue.complete(enqueued.id, result=result)

        assert completed is not None
        assert completed.status == QueueJobStatus.COMPLETED
        assert completed.result == result
        assert completed.completed_at is not None

    def test_fail_job_with_retry(self, memory_queue):
        """Test failing a job that will be retried."""
        job_create = QueueJobCreate(job_type="test", max_retries=3)
        enqueued = memory_queue.enqueue(job_create)
        memory_queue.dequeue()

        failure_info = memory_queue.fail(enqueued.id, "Test error")

        assert failure_info is not None
        assert failure_info.will_retry is True
        assert failure_info.attempt == 1
        assert failure_info.next_retry_at is not None

        # Job should be back in pending state
        job = memory_queue.get_job(enqueued.id)
        assert job.status == QueueJobStatus.PENDING
        assert job.retry_count == 1

    def test_fail_job_max_retries_exceeded(self, memory_queue):
        """Test failing a job that exceeds max retries."""
        job_create = QueueJobCreate(job_type="test", max_retries=2)
        enqueued = memory_queue.enqueue(job_create)
        memory_queue.dequeue()

        # First failure - will retry (retry_count=1, max_retries=2)
        failure1 = memory_queue.fail(enqueued.id, "Error 1")
        assert failure1.will_retry is True

        # Dequeue the retry
        memory_queue.dequeue()

        # Second failure - max retries exceeded (retry_count=2, max_retries=2)
        failure2 = memory_queue.fail(enqueued.id, "Error 2")
        assert failure2.will_retry is False

        # Job should be dead
        job = memory_queue.get_job(enqueued.id)
        assert job.status == QueueJobStatus.DEAD

    def test_release_job(self, memory_queue):
        """Test releasing a locked job."""
        job_create = QueueJobCreate(job_type="test")
        enqueued = memory_queue.enqueue(job_create)
        memory_queue.dequeue()

        # Verify it's processing
        job = memory_queue.get_job(enqueued.id)
        assert job.status == QueueJobStatus.PROCESSING

        # Release it
        released = memory_queue.release(enqueued.id)
        assert released.status == QueueJobStatus.PENDING

        # Should be dequeue-able again
        dequeued = memory_queue.dequeue()
        assert dequeued is not None

    def test_get_job(self, memory_queue):
        """Test getting a job by ID."""
        job_create = QueueJobCreate(job_type="test")
        enqueued = memory_queue.enqueue(job_create)

        retrieved = memory_queue.get_job(enqueued.id)
        assert retrieved is not None
        assert retrieved.id == enqueued.id

        # Non-existent job
        assert memory_queue.get_job("non-existent") is None

    def test_get_job_by_correlation_id(self, memory_queue):
        """Test getting a job by correlation ID."""
        job_create = QueueJobCreate(
            job_type="test",
            correlation_id="lookup-key",
        )
        enqueued = memory_queue.enqueue(job_create)

        retrieved = memory_queue.get_job_by_correlation_id("lookup-key")
        assert retrieved is not None
        assert retrieved.id == enqueued.id

        # Non-existent correlation ID
        assert memory_queue.get_job_by_correlation_id("missing") is None

    def test_update_job(self, memory_queue):
        """Test updating a job."""
        job_create = QueueJobCreate(job_type="test")
        enqueued = memory_queue.enqueue(job_create)

        update = QueueJobUpdate(
            metadata={"updated": True},
        )
        updated = memory_queue.update_job(enqueued.id, update)

        assert updated is not None
        assert updated.metadata == {"updated": True}

    def test_delete_job(self, memory_queue):
        """Test deleting a job."""
        job_create = QueueJobCreate(job_type="test", correlation_id="delete-test")
        enqueued = memory_queue.enqueue(job_create)

        # Verify job exists
        assert memory_queue.get_job(enqueued.id) is not None

        # Delete
        result = memory_queue.delete_job(enqueued.id)
        assert result is True

        # Verify job is gone
        assert memory_queue.get_job(enqueued.id) is None

        # Correlation ID should also be removed
        assert memory_queue.get_job_by_correlation_id("delete-test") is None

        # Deleting non-existent job returns False
        assert memory_queue.delete_job("non-existent") is False

    def test_list_jobs(self, memory_queue):
        """Test listing jobs."""
        for i in range(5):
            memory_queue.enqueue(QueueJobCreate(job_type=f"type_{i}"))

        jobs = memory_queue.list_jobs()
        assert len(jobs) == 5

        # Test with limit
        limited = memory_queue.list_jobs(limit=3)
        assert len(limited) == 3

    def test_list_jobs_with_status_filter(self, memory_queue):
        """Test listing jobs with status filter."""
        # Create and complete one job
        job1 = memory_queue.enqueue(QueueJobCreate(job_type="test"))
        memory_queue.dequeue()
        memory_queue.complete(job1.id)

        # Create a pending job
        memory_queue.enqueue(QueueJobCreate(job_type="test"))

        pending = memory_queue.list_jobs(status=QueueJobStatus.PENDING)
        assert len(pending) == 1

        completed = memory_queue.list_jobs(status=QueueJobStatus.COMPLETED)
        assert len(completed) == 1

    def test_list_jobs_with_type_filter(self, memory_queue):
        """Test listing jobs with type filter."""
        memory_queue.enqueue(QueueJobCreate(job_type="type_a"))
        memory_queue.enqueue(QueueJobCreate(job_type="type_b"))
        memory_queue.enqueue(QueueJobCreate(job_type="type_a"))

        type_a = memory_queue.list_jobs(job_type="type_a")
        assert len(type_a) == 2

        type_b = memory_queue.list_jobs(job_type="type_b")
        assert len(type_b) == 1

    def test_enqueue_batch(self, memory_queue):
        """Test batch enqueue."""
        jobs = [QueueJobCreate(job_type="batch", payload={"index": i}) for i in range(5)]
        created = memory_queue.enqueue_batch(jobs)

        assert len(created) == 5
        for i, job in enumerate(created):
            assert job.payload["index"] == i

    def test_dequeue_batch(self, memory_queue):
        """Test batch dequeue."""
        for i in range(5):
            memory_queue.enqueue(QueueJobCreate(job_type="test"))

        dequeued = memory_queue.dequeue_batch(3, worker_id="worker-1")

        assert len(dequeued) == 3
        for job in dequeued:
            assert job.status == QueueJobStatus.PROCESSING

    def test_requeue_stale_jobs(self, memory_queue):
        """Test requeuing stale jobs."""
        # Enqueue and dequeue a job
        job_create = QueueJobCreate(job_type="test")
        enqueued = memory_queue.enqueue(job_create)
        memory_queue.dequeue()

        # Manually set locked_at to past
        job = memory_queue.get_job(enqueued.id)
        job.locked_at = datetime.now() - timedelta(minutes=10)

        # Requeue jobs older than 1 second
        count = memory_queue.requeue_stale_jobs(stale_threshold_seconds=1)
        assert count == 1

        # Job should be back to pending
        job = memory_queue.get_job(enqueued.id)
        assert job.status == QueueJobStatus.PENDING

    def test_purge_completed(self, memory_queue):
        """Test purging completed jobs."""
        # Create and complete a job
        job_create = QueueJobCreate(job_type="test")
        enqueued = memory_queue.enqueue(job_create)
        memory_queue.dequeue()
        memory_queue.complete(enqueued.id)

        # Manually set completed_at to past
        job = memory_queue.get_job(enqueued.id)
        job.completed_at = datetime.now() - timedelta(days=2)

        # Purge jobs older than 1 day
        count = memory_queue.purge_completed(older_than_seconds=86400)
        assert count == 1

        # Job should be gone
        assert memory_queue.get_job(enqueued.id) is None

    def test_get_stats(self, memory_queue):
        """Test getting queue statistics."""
        # Create jobs in different states
        job1 = memory_queue.enqueue(QueueJobCreate(job_type="test"))
        memory_queue.enqueue(QueueJobCreate(job_type="test"))
        memory_queue.enqueue(QueueJobCreate(job_type="test"))

        # Complete one
        memory_queue.dequeue()
        memory_queue.complete(job1.id)

        # Leave one processing
        memory_queue.dequeue()

        # Leave one pending

        stats = memory_queue.get_stats()
        assert stats.total_jobs == 3
        assert stats.pending_jobs == 1
        assert stats.processing_jobs == 1
        assert stats.completed_jobs == 1

    def test_health_check(self, memory_queue):
        """Test health check."""
        assert memory_queue.health_check() is True

    def test_process_jobs(self, memory_queue):
        """Test the process_jobs utility method."""
        # Enqueue some jobs
        for i in range(3):
            memory_queue.enqueue(
                QueueJobCreate(
                    job_type="test",
                    payload={"value": i},
                )
            )

        # Define handler
        def handler(job: QueueJob) -> dict:
            return {"processed": job.payload["value"]}

        # Process all jobs
        count = memory_queue.process_jobs(
            handler=handler,
            stop_on_empty=True,
        )

        assert count == 3

        # All jobs should be completed
        stats = memory_queue.get_stats()
        assert stats.completed_jobs == 3
        assert stats.pending_jobs == 0

    def test_process_jobs_with_failure(self, memory_queue):
        """Test process_jobs handles failures."""
        memory_queue.enqueue(
            QueueJobCreate(
                job_type="test",
                max_retries=0,  # No retries
            )
        )

        def failing_handler(job: QueueJob) -> dict:
            raise ValueError("Test error")

        count = memory_queue.process_jobs(
            handler=failing_handler,
            stop_on_empty=True,
        )

        assert count == 1

        # Job should be dead (no retries)
        stats = memory_queue.get_stats()
        assert stats.dead_jobs == 1


class TestQueueImports:
    """Test that all queue components are properly exported."""

    def test_imports(self):
        """Test that all queue components can be imported."""
        from ai_blogger import (
            MemoryQueue,
            QueueBackend,
            QueueConfig,
            QueueJob,
            QueueJobCreate,
            QueueJobStatus,
            QueueJobUpdate,
            QueueStats,
            create_queue,
            get_queue_type,
        )

        # All imports should succeed
        assert QueueBackend is not None
        assert QueueConfig is not None
        assert create_queue is not None
        assert get_queue_type is not None
        assert QueueJob is not None
        assert QueueJobCreate is not None
        assert QueueJobStatus is not None
        assert QueueJobUpdate is not None
        assert QueueStats is not None
        assert MemoryQueue is not None

    def test_queue_submodule_imports(self):
        """Test that queue submodule components can be imported."""
        from ai_blogger.queue import (
            MemoryQueue,
            QueueBackend,
            QueueConfig,
            QueueJob,
            QueueJobCreate,
            QueueJobStatus,
            QueueJobUpdate,
            QueueStats,
            create_queue,
            get_queue_type,
        )

        # All imports should succeed
        assert QueueBackend is not None
        assert MemoryQueue is not None
        assert create_queue is not None
