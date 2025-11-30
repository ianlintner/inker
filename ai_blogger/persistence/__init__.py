"""Persistence layer for the AI Blogger.

This module provides a modular persistence architecture supporting:
- PostgreSQL as primary database
- SQLite as local fallback
- Vector storage extension capability

Usage:
    from ai_blogger.persistence import create_storage, StorageBackend

    # Create SQLite storage (default)
    storage = create_storage("sqlite", db_path="./data/jobs.db")

    # Create PostgreSQL storage
    storage = create_storage("postgres", connection_string="postgresql://...")

    # Use environment-based auto-detection
    storage = create_storage()  # Uses DATABASE_URL or falls back to SQLite
"""

from .base import StorageBackend, StorageConfig
from .factory import create_storage, get_storage_type
from .models import (
    ApprovalStatus,
    BlogPost,
    BlogPostCreate,
    BlogPostUpdate,
    JobHistoryEntry,
    JobStats,
)
from .sqlite_storage import SQLiteStorage

__all__ = [
    # Base classes
    "StorageBackend",
    "StorageConfig",
    # Factory
    "create_storage",
    "get_storage_type",
    # Models
    "ApprovalStatus",
    "BlogPost",
    "BlogPostCreate",
    "BlogPostUpdate",
    "JobHistoryEntry",
    "JobStats",
    # Implementations
    "SQLiteStorage",
]

# Conditional import for PostgreSQL (requires psycopg2)
try:
    from .postgres_storage import PostgresStorage

    __all__.append("PostgresStorage")
except ImportError:
    PostgresStorage = None  # type: ignore
