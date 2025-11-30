"""Base queue interface for job processing.

This module defines the abstract interface that all queue backends must implement.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional
from uuid import UUID


class JobQueue(ABC):
    """Abstract base class for job queue implementations.

    All queue backends (in-memory, Redis, Postgres, etc.) must implement this interface.
    """

    @abstractmethod
    def enqueue(self, job_id: UUID) -> bool:
        """Add a job ID to the queue for processing.

        Args:
            job_id: The UUID of the job to enqueue.

        Returns:
            True if the job was successfully enqueued.
        """
        pass

    @abstractmethod
    def dequeue(self) -> Optional[UUID]:
        """Remove and return the next job ID from the queue.

        Returns:
            The UUID of the next job, or None if the queue is empty.
        """
        pass

    @abstractmethod
    def peek(self) -> Optional[UUID]:
        """View the next job ID without removing it.

        Returns:
            The UUID of the next job, or None if the queue is empty.
        """
        pass

    @abstractmethod
    def size(self) -> int:
        """Get the number of jobs in the queue.

        Returns:
            Number of jobs waiting in the queue.
        """
        pass

    @abstractmethod
    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True if the queue has no jobs.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all jobs from the queue."""
        pass

    @abstractmethod
    def start_worker(self, handler: Callable[[UUID], None]) -> None:
        """Start a worker to process jobs from the queue.

        Args:
            handler: Callback function to handle each job.
        """
        pass

    @abstractmethod
    def stop_worker(self) -> None:
        """Stop the worker processing jobs."""
        pass

    @abstractmethod
    def is_worker_running(self) -> bool:
        """Check if the worker is currently running.

        Returns:
            True if the worker is running.
        """
        pass
