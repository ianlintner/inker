"""Storage factory for creating storage backends.

Provides automatic detection and creation of storage backends
based on configuration or environment variables.
"""

import logging
import os
from typing import Optional

from .base import StorageBackend, StorageConfig
from .sqlite_storage import SQLiteStorage

logger = logging.getLogger(__name__)


def get_storage_type() -> str:
    """Detect the storage type from environment.

    Checks DATABASE_URL to determine if PostgreSQL is configured.
    Falls back to SQLite if not.

    Returns:
        Storage type string: 'postgres' or 'sqlite'
    """
    database_url = os.environ.get("DATABASE_URL", "")

    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        return "postgres"

    return "sqlite"


def create_storage(
    backend_type: Optional[str] = None,
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    pool_size: int = 5,
    auto_migrate: bool = True,
    **extra: object,
) -> StorageBackend:
    """Create a storage backend instance.

    If backend_type is not specified, auto-detects based on environment:
    - If DATABASE_URL is set to a PostgreSQL URL, uses PostgreSQL
    - Otherwise, uses SQLite

    Args:
        backend_type: Type of storage ('sqlite', 'postgres'). Auto-detected if None.
        connection_string: Database connection string for PostgreSQL.
        db_path: File path for SQLite database.
        pool_size: Connection pool size for PostgreSQL.
        auto_migrate: Whether to run migrations on initialization.
        **extra: Additional backend-specific configuration.

    Returns:
        StorageBackend instance.

    Raises:
        ValueError: If backend_type is unknown.
        ImportError: If required dependencies are not installed.

    Example:
        # Auto-detect based on environment
        storage = create_storage()

        # Explicit SQLite
        storage = create_storage("sqlite", db_path="./data/jobs.db")

        # Explicit PostgreSQL
        storage = create_storage("postgres", connection_string="postgresql://...")
    """
    if backend_type is None:
        backend_type = get_storage_type()

    # Get connection string from environment if not provided
    if connection_string is None:
        connection_string = os.environ.get("DATABASE_URL")

    # Get db_path from environment if not provided
    if db_path is None:
        db_path = os.environ.get("INKER_DB_PATH", "./data/inker.db")

    config = StorageConfig(
        backend_type=backend_type,
        connection_string=connection_string,
        db_path=db_path,
        pool_size=pool_size,
        auto_migrate=auto_migrate,
        extra=dict(extra),
    )

    if backend_type == "sqlite":
        logger.info(f"Creating SQLite storage at {db_path}")
        return SQLiteStorage(config)

    elif backend_type == "postgres":
        try:
            from .postgres_storage import PostgresStorage
        except ImportError as e:
            raise ImportError(
                "psycopg2 is required for PostgreSQL storage. " "Install with: pip install psycopg2-binary"
            ) from e

        logger.info("Creating PostgreSQL storage")
        return PostgresStorage(config)

    else:
        raise ValueError(f"Unknown storage backend type: {backend_type}")
