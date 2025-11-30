"""Queue factory for creating queue backends.

Provides automatic detection and creation of queue backends
based on configuration or environment variables.
"""

import logging
import os
from typing import Optional

from .base import QueueBackend, QueueConfig
from .memory_queue import MemoryQueue
from .models import RetryPolicy

logger = logging.getLogger(__name__)


def get_queue_type() -> str:
    """Detect the queue type from environment.

    Priority order:
    1. REDIS_URL -> redis
    2. DATABASE_URL (PostgreSQL) -> postgres
    3. Default -> memory

    Returns:
        Queue type string: 'redis', 'postgres', or 'memory'
    """
    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url:
        return "redis"

    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        return "postgres"

    return "memory"


def create_queue(
    backend_type: Optional[str] = None,
    connection_string: Optional[str] = None,
    visibility_timeout_seconds: int = 300,
    poll_interval_seconds: float = 1.0,
    worker_id: Optional[str] = None,
    max_retries: int = 3,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 300.0,
    exponential_backoff: bool = True,
    **extra: object,
) -> QueueBackend:
    """Create a queue backend instance.

    If backend_type is not specified, auto-detects based on environment:
    - If REDIS_URL is set, uses Redis
    - If DATABASE_URL is set to a PostgreSQL URL, uses PostgreSQL
    - Otherwise, uses in-memory queue

    Args:
        backend_type: Type of queue ('memory', 'postgres', 'redis'). Auto-detected if None.
        connection_string: Connection string for the queue backend.
        visibility_timeout_seconds: How long a job stays locked before timeout.
        poll_interval_seconds: How often to poll for new jobs.
        worker_id: Unique identifier for this worker instance.
        max_retries: Default maximum retry attempts for jobs.
        base_delay_seconds: Initial delay before first retry.
        max_delay_seconds: Maximum delay between retries.
        exponential_backoff: Whether to use exponential backoff for retries.
        **extra: Additional backend-specific configuration.

    Returns:
        QueueBackend instance.

    Raises:
        ValueError: If backend_type is unknown.
        ImportError: If required dependencies are not installed.

    Example:
        # Auto-detect based on environment
        queue = create_queue()

        # Explicit memory queue
        queue = create_queue("memory")

        # Explicit PostgreSQL
        queue = create_queue("postgres", connection_string="postgresql://...")

        # Explicit Redis
        queue = create_queue("redis", connection_string="redis://...")
    """
    if backend_type is None:
        backend_type = get_queue_type()

    # Get connection string from environment if not provided
    if connection_string is None:
        if backend_type == "redis":
            connection_string = os.environ.get("REDIS_URL")
        elif backend_type == "postgres":
            connection_string = os.environ.get("DATABASE_URL")

    retry_policy = RetryPolicy(
        max_retries=max_retries,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        exponential_backoff=exponential_backoff,
    )

    config = QueueConfig(
        backend_type=backend_type,
        connection_string=connection_string,
        default_retry_policy=retry_policy,
        visibility_timeout_seconds=visibility_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        worker_id=worker_id,
        extra=dict(extra),
    )

    if backend_type == "memory":
        logger.info("Creating in-memory queue")
        queue = MemoryQueue(config)
        queue.initialize()
        return queue

    elif backend_type == "postgres":
        try:
            from .postgres_queue import PostgresQueue
        except ImportError as e:
            raise ImportError(
                "psycopg2 is required for PostgreSQL queue. " "Install with: pip install psycopg2-binary"
            ) from e

        logger.info("Creating PostgreSQL queue")
        queue = PostgresQueue(config)
        queue.initialize()
        return queue

    elif backend_type == "redis":
        try:
            from .redis_queue import RedisQueue
        except ImportError as e:
            raise ImportError("redis is required for Redis queue. " "Install with: pip install redis") from e

        logger.info("Creating Redis queue")
        queue = RedisQueue(config)
        queue.initialize()
        return queue

    else:
        raise ValueError(f"Unknown queue backend type: {backend_type}")
