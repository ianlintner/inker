"""Observability layer for the AI Blogger workflow.

This module provides Prometheus metrics and OpenTelemetry tracing.
"""

from .metrics import (
    MetricsMiddleware,
    get_metrics_registry,
    record_job_completion,
    record_job_duration,
    record_job_start,
)
from .tracing import TracingMiddleware, create_span, get_tracer

__all__ = [
    # Metrics
    "MetricsMiddleware",
    "get_metrics_registry",
    "record_job_start",
    "record_job_completion",
    "record_job_duration",
    # Tracing
    "TracingMiddleware",
    "get_tracer",
    "create_span",
]
