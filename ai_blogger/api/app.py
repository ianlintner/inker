"""FastAPI application factory for the AI Blogger API.

This module provides the main application factory with OpenAPI documentation,
CORS configuration, and middleware setup.
"""

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..observability import MetricsMiddleware, TracingMiddleware
from .routes import router

logger = logging.getLogger(__name__)


def create_app(
    title: str = "AI Blogger API",
    description: str = "Goal-driven workflow API for AI-powered blog post generation with editor approval",
    version: str = "0.1.0",
    enable_cors: bool = True,
    cors_origins: Optional[list] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        title: API title for OpenAPI docs.
        description: API description for OpenAPI docs.
        version: API version.
        enable_cors: Whether to enable CORS middleware.
        cors_origins: List of allowed CORS origins.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "jobs",
                "description": "Blog post job management and approval workflow",
            },
        ],
    )

    # Add CORS middleware
    if enable_cors:
        origins = cors_origins or ["*"]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Add observability middleware
    app.add_middleware(TracingMiddleware)
    app.add_middleware(MetricsMiddleware)

    # Include API routes
    app.include_router(router)

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "name": title,
            "version": version,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    # Metrics endpoint
    @app.get("/metrics", tags=["observability"])
    async def metrics() -> dict:
        """Prometheus-style metrics endpoint."""
        from ..observability import get_metrics_registry

        registry = get_metrics_registry()
        return registry.get_all_metrics()

    # Exception handlers
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        """Handle uncaught exceptions."""
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    logger.info(f"Created FastAPI app: {title} v{version}")
    return app
