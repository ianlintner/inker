"""Job queue layer for the AI Blogger.

This module provides a modular job queue architecture supporting:
- PostgreSQL for persistent, distributed queues
- Redis for high-performance in-memory queues
- In-memory queue for testing and local development

Usage:
    from ai_blogger.queue import create_queue, QueueBackend

    # Create PostgreSQL-backed queue (requires DATABASE_URL)
    queue = create_queue("postgres", connection_string="postgresql://...")

    # Create Redis-backed queue (requires REDIS_URL)
    queue = create_queue("redis", connection_string="redis://...")

    # Create in-memory queue (for testing)
    queue = create_queue("memory")

    # Use environment-based auto-detection
    queue = create_queue()  # Checks REDIS_URL, DATABASE_URL, or falls back to memory
"""

from .base import QueueBackend, QueueConfig
from .factory import create_queue, get_queue_type
from .memory_queue import MemoryQueue
from .models import (
    QueueJob,
    QueueJobCreate,
    QueueJobStatus,
    QueueJobUpdate,
    QueueStats,
)

__all__ = [
    # Base classes
    "QueueBackend",
    "QueueConfig",
    # Factory
    "create_queue",
    "get_queue_type",
    # Models
    "QueueJob",
    "QueueJobCreate",
    "QueueJobStatus",
    "QueueJobUpdate",
    "QueueStats",
    # Implementations
    "MemoryQueue",
]

# Conditional imports for optional backends
try:
    from .postgres_queue import PostgresQueue

    __all__.append("PostgresQueue")
except ImportError:
    PostgresQueue = None  # type: ignore

try:
    from .redis_queue import RedisQueue

    __all__.append("RedisQueue")
except ImportError:
    RedisQueue = None  # type: ignore
