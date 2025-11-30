"""Job queue service for blog post generation.

This module provides a modular queue abstraction for job processing,
with an in-memory implementation as the default option.
"""

from .base import JobQueue
from .memory_queue import InMemoryJobQueue

__all__ = [
    "JobQueue",
    "InMemoryJobQueue",
]
