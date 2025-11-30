"""Dependency injection for the API layer.

This module provides dependency injection for repositories and queues.
"""

from typing import Generator, Optional

from ..persistence import JobRepository, SQLiteJobRepository
from ..queue import InMemoryJobQueue, JobQueue

# Global instances (can be replaced for testing)
_repository: Optional[JobRepository] = None
_job_queue: Optional[JobQueue] = None


def get_repository() -> Generator[JobRepository, None, None]:
    """Get the job repository instance.

    This is a FastAPI dependency that provides the repository.
    """
    global _repository
    if _repository is None:
        _repository = SQLiteJobRepository()
    yield _repository


def get_job_queue() -> Generator[JobQueue, None, None]:
    """Get the job queue instance.

    This is a FastAPI dependency that provides the queue.
    """
    global _job_queue
    if _job_queue is None:
        _job_queue = InMemoryJobQueue()
    yield _job_queue


def set_repository(repository: JobRepository) -> None:
    """Set the repository instance (for testing)."""
    global _repository
    _repository = repository


def set_job_queue(queue: JobQueue) -> None:
    """Set the job queue instance (for testing)."""
    global _job_queue
    _job_queue = queue


def reset_dependencies() -> None:
    """Reset all dependencies to None (for testing)."""
    global _repository, _job_queue
    if _repository:
        _repository.close()
        _repository = None
    if _job_queue:
        _job_queue.stop_worker()
        _job_queue = None
