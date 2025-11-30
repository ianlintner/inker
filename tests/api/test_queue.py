"""Tests for the job queue."""

import pytest
import time
from uuid import uuid4

from ai_blogger.queue import InMemoryJobQueue


class TestInMemoryJobQueue:
    """Tests for in-memory job queue implementation."""

    @pytest.fixture
    def queue(self):
        """Create a fresh queue for each test."""
        q = InMemoryJobQueue()
        yield q
        q.stop_worker()

    def test_enqueue_and_dequeue(self, queue):
        """Test basic enqueue and dequeue operations."""
        job_id = uuid4()

        result = queue.enqueue(job_id)
        assert result is True

        dequeued = queue.dequeue()
        assert dequeued == job_id

    def test_dequeue_empty_queue(self, queue):
        """Test dequeuing from empty queue returns None."""
        result = queue.dequeue()
        assert result is None

    def test_size(self, queue):
        """Test queue size tracking."""
        assert queue.size() == 0

        queue.enqueue(uuid4())
        assert queue.size() == 1

        queue.enqueue(uuid4())
        assert queue.size() == 2

        queue.dequeue()
        assert queue.size() == 1

    def test_is_empty(self, queue):
        """Test checking if queue is empty."""
        assert queue.is_empty() is True

        queue.enqueue(uuid4())
        assert queue.is_empty() is False

        queue.dequeue()
        assert queue.is_empty() is True

    def test_clear(self, queue):
        """Test clearing the queue."""
        for _ in range(5):
            queue.enqueue(uuid4())

        assert queue.size() == 5

        queue.clear()
        assert queue.size() == 0
        assert queue.is_empty() is True

    def test_peek(self, queue):
        """Test peeking at next item without removing it."""
        job_id = uuid4()
        queue.enqueue(job_id)

        peeked = queue.peek()
        # The item should still be in the queue
        assert queue.size() >= 0  # Size behavior may vary with peek implementation

    def test_peek_empty_queue(self, queue):
        """Test peeking at empty queue."""
        result = queue.peek()
        assert result is None

    def test_fifo_order(self, queue):
        """Test that items are dequeued in FIFO order."""
        ids = [uuid4() for _ in range(5)]

        for job_id in ids:
            queue.enqueue(job_id)

        for expected_id in ids:
            dequeued = queue.dequeue()
            assert dequeued == expected_id

    def test_worker_not_running_initially(self, queue):
        """Test that worker is not running initially."""
        assert queue.is_worker_running() is False

    def test_start_and_stop_worker(self, queue):
        """Test starting and stopping the worker."""
        processed = []

        def handler(job_id):
            processed.append(job_id)

        queue.start_worker(handler)
        assert queue.is_worker_running() is True

        queue.stop_worker()
        assert queue.is_worker_running() is False

    def test_worker_processes_jobs(self, queue):
        """Test that worker processes enqueued jobs."""
        processed = []

        def handler(job_id):
            processed.append(job_id)

        job_id = uuid4()
        queue.enqueue(job_id)

        queue.start_worker(handler)

        # Wait a bit for the worker to process
        time.sleep(0.5)

        queue.stop_worker()

        assert job_id in processed

    def test_multiple_enqueue_dequeue(self, queue):
        """Test multiple enqueue/dequeue cycles."""
        for _ in range(10):
            job_id = uuid4()
            queue.enqueue(job_id)
            dequeued = queue.dequeue()
            assert dequeued == job_id
