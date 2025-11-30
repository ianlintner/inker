"""API layer for the AI Blogger workflow.

This module provides the RESTful API endpoints for job management,
approval workflow, and frontend integration.
"""

from .app import create_app
from .dependencies import get_job_queue, get_repository
from .routes import router

__all__ = [
    "create_app",
    "router",
    "get_repository",
    "get_job_queue",
]
