"""Persistence layer for the AI Blogger workflow.

This module provides a modular storage abstraction for job management,
with SQLite as the default/fallback implementation.
"""

from .base import JobRepository
from .sqlite_repository import SQLiteJobRepository

__all__ = [
    "JobRepository",
    "SQLiteJobRepository",
]
