"""Prometheus metrics and OpenTelemetry tracing for AI Blogger.

This module provides observability instrumentation for the AI Blogger system:
- Prometheus metrics for system monitoring
- OpenTelemetry tracing for request correlation and debugging

Usage:
    from ai_blogger.metrics import (
        job_submissions_total,
        job_status_changes_total,
        job_duration_seconds,
        get_tracer,
    )

    # Metrics are automatically updated when using instrumented services
    # Access metrics endpoint at /metrics on the API server
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, Optional

# Prometheus metrics
try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# OpenTelemetry tracing
try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, SpanKind, Status, StatusCode

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# Prometheus Metrics Definitions
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # --- Job Metrics ---
    job_submissions_total = Counter(
        "ai_blogger_job_submissions_total",
        "Total number of job submissions",
        ["is_duplicate"],
    )

    job_status_changes_total = Counter(
        "ai_blogger_job_status_changes_total",
        "Total number of job status changes",
        ["from_status", "to_status"],
    )

    job_duration_seconds = Histogram(
        "ai_blogger_job_duration_seconds",
        "Job execution duration in seconds",
        ["status"],
        buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
    )

    jobs_in_progress = Gauge(
        "ai_blogger_jobs_in_progress",
        "Number of jobs currently being processed",
    )

    job_errors_total = Counter(
        "ai_blogger_job_errors_total",
        "Total number of job execution errors",
        ["error_type"],
    )

    # --- Feedback/Approval Metrics ---
    approvals_total = Counter(
        "ai_blogger_approvals_total",
        "Total number of post approvals",
        ["action"],  # approved, rejected, revision_requested
    )

    feedback_operations_total = Counter(
        "ai_blogger_feedback_operations_total",
        "Total number of feedback operations",
        ["operation"],
    )

    # --- Queue Metrics ---
    queue_enqueue_total = Counter(
        "ai_blogger_queue_enqueue_total",
        "Total number of queue enqueue operations",
        ["job_type"],
    )

    queue_dequeue_total = Counter(
        "ai_blogger_queue_dequeue_total",
        "Total number of queue dequeue operations",
        ["job_type"],
    )

    queue_complete_total = Counter(
        "ai_blogger_queue_complete_total",
        "Total number of queue job completions",
    )

    queue_fail_total = Counter(
        "ai_blogger_queue_fail_total",
        "Total number of queue job failures",
        ["will_retry"],
    )

    queue_size = Gauge(
        "ai_blogger_queue_size",
        "Current size of the job queue",
        ["status"],
    )

    # --- Persistence Metrics ---
    storage_operations_total = Counter(
        "ai_blogger_storage_operations_total",
        "Total number of storage operations",
        ["operation", "entity"],
    )

    storage_operation_duration_seconds = Histogram(
        "ai_blogger_storage_operation_duration_seconds",
        "Storage operation duration in seconds",
        ["operation", "entity"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    )

    # --- API Metrics ---
    api_requests_total = Counter(
        "ai_blogger_api_requests_total",
        "Total number of API requests",
        ["method", "endpoint", "status_code"],
    )

    api_request_duration_seconds = Histogram(
        "ai_blogger_api_request_duration_seconds",
        "API request duration in seconds",
        ["method", "endpoint"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    # --- System Info ---
    system_info = Info(
        "ai_blogger_system",
        "AI Blogger system information",
    )

else:
    # Stub implementations when prometheus_client is not available
    class StubCounter:
        def labels(self, *args: Any, **kwargs: Any) -> "StubCounter":
            return self

        def inc(self, amount: float = 1) -> None:
            pass

    class StubGauge:
        def labels(self, *args: Any, **kwargs: Any) -> "StubGauge":
            return self

        def set(self, value: float) -> None:
            pass

        def inc(self, amount: float = 1) -> None:
            pass

        def dec(self, amount: float = 1) -> None:
            pass

    class StubHistogram:
        def labels(self, *args: Any, **kwargs: Any) -> "StubHistogram":
            return self

        def observe(self, amount: float) -> None:
            pass

    class StubInfo:
        def info(self, val: dict) -> None:
            pass

    job_submissions_total = StubCounter()
    job_status_changes_total = StubCounter()
    job_duration_seconds = StubHistogram()
    jobs_in_progress = StubGauge()
    job_errors_total = StubCounter()
    approvals_total = StubCounter()
    feedback_operations_total = StubCounter()
    queue_enqueue_total = StubCounter()
    queue_dequeue_total = StubCounter()
    queue_complete_total = StubCounter()
    queue_fail_total = StubCounter()
    queue_size = StubGauge()
    storage_operations_total = StubCounter()
    storage_operation_duration_seconds = StubHistogram()
    api_requests_total = StubCounter()
    api_request_duration_seconds = StubHistogram()
    system_info = StubInfo()


# ============================================================================
# OpenTelemetry Tracing
# ============================================================================

_tracer: Optional[Any] = None


def get_tracer(name: str = "ai_blogger") -> Any:
    """Get or create an OpenTelemetry tracer.

    Args:
        name: The name of the tracer (typically the module name).

    Returns:
        An OpenTelemetry tracer or a no-op tracer if OpenTelemetry is not available.
    """
    global _tracer

    if OPENTELEMETRY_AVAILABLE:
        if _tracer is None:
            _tracer = trace.get_tracer(name)
        return _tracer
    else:
        return NoOpTracer()


class NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""

    def __enter__(self) -> "NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def end(self) -> None:
        pass


class NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""

    def start_span(
        self,
        name: str,
        kind: Any = None,
        attributes: Optional[dict] = None,
    ) -> NoOpSpan:
        return NoOpSpan()

    def start_as_current_span(
        self,
        name: str,
        kind: Any = None,
        attributes: Optional[dict] = None,
    ) -> NoOpSpan:
        return NoOpSpan()


# ============================================================================
# Instrumentation Helpers
# ============================================================================


@contextmanager
def track_job_execution(job_id: str, job_type: str = "blog_post") -> Generator[None, None, None]:
    """Context manager to track job execution metrics and tracing.

    Args:
        job_id: The job identifier.
        job_type: The type of job being executed.

    Yields:
        None

    Example:
        with track_job_execution(job.id, "blog_post"):
            # Execute job logic
            pass
    """
    tracer = get_tracer()
    start_time = time.time()

    jobs_in_progress.inc()

    try:
        with tracer.start_as_current_span(
            f"job.execute.{job_type}",
            attributes={"job.id": job_id, "job.type": job_type},
        ) as span:
            yield
            duration = time.time() - start_time
            job_duration_seconds.labels(status="completed").observe(duration)
            if OPENTELEMETRY_AVAILABLE and hasattr(span, "set_attribute"):
                span.set_attribute("job.duration_seconds", duration)
    except Exception as e:
        duration = time.time() - start_time
        job_duration_seconds.labels(status="failed").observe(duration)
        job_errors_total.labels(error_type=type(e).__name__).inc()
        raise
    finally:
        jobs_in_progress.dec()


@contextmanager
def track_storage_operation(
    operation: str, entity: str
) -> Generator[None, None, None]:
    """Context manager to track storage operation metrics.

    Args:
        operation: The operation type (create, read, update, delete).
        entity: The entity type (post, job, history).

    Yields:
        None
    """
    tracer = get_tracer()
    start_time = time.time()

    try:
        with tracer.start_as_current_span(
            f"storage.{operation}.{entity}",
            attributes={"storage.operation": operation, "storage.entity": entity},
        ):
            yield
            duration = time.time() - start_time
            storage_operations_total.labels(operation=operation, entity=entity).inc()
            storage_operation_duration_seconds.labels(operation=operation, entity=entity).observe(duration)
    except Exception:
        storage_operations_total.labels(operation=operation, entity=entity).inc()
        raise


def track_api_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
    """Record API request metrics.

    Args:
        method: HTTP method.
        endpoint: Request endpoint.
        status_code: Response status code.
        duration: Request duration in seconds.
    """
    api_requests_total.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    api_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)


def record_job_submission(is_duplicate: bool = False) -> None:
    """Record a job submission metric.

    Args:
        is_duplicate: Whether this was a duplicate submission.
    """
    job_submissions_total.labels(is_duplicate=str(is_duplicate).lower()).inc()


def record_job_status_change(from_status: str, to_status: str) -> None:
    """Record a job status change metric.

    Args:
        from_status: Previous job status.
        to_status: New job status.
    """
    job_status_changes_total.labels(from_status=from_status, to_status=to_status).inc()


def record_approval_action(action: str) -> None:
    """Record an approval/rejection/revision action.

    Args:
        action: The action taken (approved, rejected, revision_requested).
    """
    approvals_total.labels(action=action).inc()


def record_queue_enqueue(job_type: str = "default") -> None:
    """Record a queue enqueue operation.

    Args:
        job_type: The type of job being enqueued.
    """
    queue_enqueue_total.labels(job_type=job_type).inc()


def record_queue_dequeue(job_type: str = "default") -> None:
    """Record a queue dequeue operation.

    Args:
        job_type: The type of job being dequeued.
    """
    queue_dequeue_total.labels(job_type=job_type).inc()


def record_queue_complete() -> None:
    """Record a queue job completion."""
    queue_complete_total.inc()


def record_queue_fail(will_retry: bool = False) -> None:
    """Record a queue job failure.

    Args:
        will_retry: Whether the job will be retried.
    """
    queue_fail_total.labels(will_retry=str(will_retry).lower()).inc()


def update_queue_size(status: str, size: int) -> None:
    """Update the queue size gauge.

    Args:
        status: The queue status (pending, processing, completed, failed, dead).
        size: The current size.
    """
    queue_size.labels(status=status).set(size)


def set_system_info(version: str = "0.1.0", **kwargs: Any) -> None:
    """Set system information.

    Args:
        version: The application version.
        **kwargs: Additional info to include.
    """
    info = {"version": version}
    info.update(kwargs)
    system_info.info(info)


def traced(
    name: Optional[str] = None,
    attributes: Optional[dict] = None,
) -> Callable:
    """Decorator to add tracing to a function.

    Args:
        name: Span name (defaults to function name).
        attributes: Additional span attributes.

    Returns:
        Decorated function.

    Example:
        @traced("my_operation", {"custom.attr": "value"})
        def my_function():
            pass
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name, attributes=attributes or {}):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Availability flags
    "PROMETHEUS_AVAILABLE",
    "OPENTELEMETRY_AVAILABLE",
    # Prometheus metrics
    "job_submissions_total",
    "job_status_changes_total",
    "job_duration_seconds",
    "jobs_in_progress",
    "job_errors_total",
    "approvals_total",
    "feedback_operations_total",
    "queue_enqueue_total",
    "queue_dequeue_total",
    "queue_complete_total",
    "queue_fail_total",
    "queue_size",
    "storage_operations_total",
    "storage_operation_duration_seconds",
    "api_requests_total",
    "api_request_duration_seconds",
    "system_info",
    # OpenTelemetry
    "get_tracer",
    "NoOpTracer",
    "NoOpSpan",
    # Instrumentation helpers
    "track_job_execution",
    "track_storage_operation",
    "track_api_request",
    "record_job_submission",
    "record_job_status_change",
    "record_approval_action",
    "record_queue_enqueue",
    "record_queue_dequeue",
    "record_queue_complete",
    "record_queue_fail",
    "update_queue_size",
    "set_system_info",
    "traced",
]
