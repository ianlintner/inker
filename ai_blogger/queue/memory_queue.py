"""In-memory job queue implementation.

This module provides a simple thread-safe in-memory queue for job processing.
Suitable for development, testing, and single-instance deployments.
"""

import logging
import threading
from collections import deque
from typing import Callable, Optional
from uuid import UUID

from .base import JobQueue

logger = logging.getLogger(__name__)


class InMemoryJobQueue(JobQueue):
    """In-memory job queue implementation.

    This provides a simple, thread-safe queue suitable for development,
    testing, and single-instance deployments. Jobs are lost on restart.
    """

    def __init__(self):
        """Initialize the in-memory queue."""
        self._queue: deque = deque()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    def enqueue(self, job_id: UUID) -> bool:
        """Add a job ID to the queue for processing."""
        try:
            with self._lock:
                self._queue.append(job_id)
                self._condition.notify()
            logger.debug(f"Enqueued job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            return False

    def dequeue(self) -> Optional[UUID]:
        """Remove and return the next job ID from the queue."""
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def peek(self) -> Optional[UUID]:
        """View the next job ID without removing it."""
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def size(self) -> int:
        """Get the number of jobs in the queue."""
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        with self._lock:
            return len(self._queue) == 0

    def clear(self) -> None:
        """Clear all jobs from the queue."""
        with self._lock:
            self._queue.clear()

    def start_worker(self, handler: Callable[[UUID], None]) -> None:
        """Start a worker to process jobs from the queue."""
        with self._lock:
            if self._running:
                logger.warning("Worker is already running")
                return

            self._running = True
            self._worker_thread = threading.Thread(target=self._worker_loop, args=(handler,), daemon=True)
            self._worker_thread.start()
            logger.info("Job queue worker started")

    def _worker_loop(self, handler: Callable[[UUID], None]) -> None:
        """Internal worker loop that processes jobs."""
        while self._running:
            job_id = None
            with self._condition:
                # Wait for items or timeout
                while not self._queue and self._running:
                    self._condition.wait(timeout=1.0)
                if self._queue:
                    job_id = self._queue.popleft()

            if job_id:
                try:
                    logger.debug(f"Processing job {job_id}")
                    handler(job_id)
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {e}")

    def stop_worker(self) -> None:
        """Stop the worker processing jobs."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            self._condition.notify_all()

        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
            self._worker_thread = None
        logger.info("Job queue worker stopped")

    def is_worker_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._running
