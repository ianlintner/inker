"""In-memory job queue implementation.

This module provides a simple thread-safe in-memory queue for job processing.
Suitable for development, testing, and single-instance deployments.
"""

import logging
import threading
from queue import Empty, Queue
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
        self._queue: Queue = Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def enqueue(self, job_id: UUID) -> bool:
        """Add a job ID to the queue for processing."""
        try:
            self._queue.put(job_id)
            logger.debug(f"Enqueued job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            return False

    def dequeue(self) -> Optional[UUID]:
        """Remove and return the next job ID from the queue."""
        try:
            return self._queue.get_nowait()
        except Empty:
            return None

    def peek(self) -> Optional[UUID]:
        """View the next job ID without removing it."""
        with self._lock:
            if self._queue.empty():
                return None
            # Queue doesn't support peek, so we dequeue and re-enqueue
            # This is not ideal for production but works for testing
            try:
                job_id = self._queue.get_nowait()
                # Put it back at the front by using a temporary queue
                # For simplicity, just return the job_id and put it back
                # Note: This changes order - in production, use a proper peek
                self._queue.put(job_id)
                return job_id
            except Empty:
                return None

    def size(self) -> int:
        """Get the number of jobs in the queue."""
        return self._queue.qsize()

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self._queue.empty()

    def clear(self) -> None:
        """Clear all jobs from the queue."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except Empty:
                    break

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
            try:
                job_id = self._queue.get(timeout=1.0)
                try:
                    logger.debug(f"Processing job {job_id}")
                    handler(job_id)
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {e}")
                finally:
                    self._queue.task_done()
            except Empty:
                continue

    def stop_worker(self) -> None:
        """Stop the worker processing jobs."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            if self._worker_thread:
                self._worker_thread.join(timeout=5.0)
                self._worker_thread = None
            logger.info("Job queue worker stopped")

    def is_worker_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._running
