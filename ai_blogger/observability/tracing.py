"""OpenTelemetry tracing for the AI Blogger workflow.

This module provides distributed tracing capabilities for monitoring
the flow of requests and jobs through the system.
"""

import logging
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class Span:
    """Simple span implementation for tracing.

    This is a lightweight implementation that can be extended to integrate
    with OpenTelemetry in production.
    """

    def __init__(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a span.

        Args:
            name: Name of the span (operation name).
            trace_id: Optional trace ID for distributed tracing.
            parent_id: Optional parent span ID.
            attributes: Optional initial attributes.
        """
        self.name = name
        self.trace_id = trace_id or self._generate_id()
        self.span_id = self._generate_id()
        self.parent_id = parent_id
        self.attributes = attributes or {}
        self.events: list = []
        self.status: str = "ok"
        self.error: Optional[str] = None

    def _generate_id(self) -> str:
        """Generate a simple span/trace ID."""
        import uuid

        return uuid.uuid4().hex[:16]

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append({"name": name, "attributes": attributes or {}})

    def set_status(self, status: str, error: Optional[str] = None) -> None:
        """Set the status of the span."""
        self.status = status
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for logging/export."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error": self.error,
        }


class Tracer:
    """Simple tracer implementation.

    This is a lightweight implementation that can be extended to integrate
    with OpenTelemetry in production.
    """

    def __init__(self, name: str):
        """Initialize a tracer.

        Args:
            name: Name of the tracer (typically service name).
        """
        self.name = name
        self._current_span: Optional[Span] = None

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """Start a new span as a context manager.

        Args:
            name: Name of the span.
            attributes: Optional initial attributes.

        Yields:
            The created span.
        """
        parent_id = self._current_span.span_id if self._current_span else None
        trace_id = self._current_span.trace_id if self._current_span else None

        span = Span(
            name=name,
            trace_id=trace_id,
            parent_id=parent_id,
            attributes=attributes,
        )

        previous_span = self._current_span
        self._current_span = span

        try:
            logger.debug(f"Started span: {name} (trace_id={span.trace_id})")
            yield span
        except Exception as e:
            span.set_status("error", str(e))
            raise
        finally:
            self._current_span = previous_span
            logger.debug(f"Ended span: {name} (status={span.status})")


# Global tracer instance
_tracer: Optional[Tracer] = None


def get_tracer(name: str = "ai_blogger") -> Tracer:
    """Get or create the global tracer instance.

    Args:
        name: Name of the tracer.

    Returns:
        The tracer instance.
    """
    global _tracer
    if _tracer is None:
        _tracer = Tracer(name)
    return _tracer


@contextmanager
def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> Generator[Span, None, None]:
    """Convenience function to create a span using the global tracer.

    Args:
        name: Name of the span.
        attributes: Optional initial attributes.

    Yields:
        The created span.
    """
    tracer = get_tracer()
    with tracer.start_span(name, attributes) as span:
        yield span


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware for adding tracing to HTTP requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with tracing."""
        tracer = get_tracer()

        # Extract trace ID from headers if present
        trace_id = request.headers.get("X-Trace-ID")
        correlation_id = request.headers.get("X-Correlation-ID")

        with tracer.start_span(
            f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.route": request.url.path,
                "correlation_id": correlation_id,
            },
        ) as span:
            if trace_id:
                span.trace_id = trace_id

            response = await call_next(request)

            span.set_attribute("http.status_code", response.status_code)

            if response.status_code >= 400:
                span.set_status("error")
            else:
                span.set_status("ok")

            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = span.trace_id

            return response
