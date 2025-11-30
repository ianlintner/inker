"""Prometheus metrics for the AI Blogger workflow.

This module provides metrics for monitoring job processing,
API requests, and system health.
"""

import logging
import time
from typing import Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """Simple metrics registry for tracking counters and histograms.

    This is a lightweight implementation that can be extended to integrate
    with Prometheus client libraries in production.
    """

    def __init__(self):
        self._counters: Dict[str, Dict[str, int]] = {}
        self._histograms: Dict[str, Dict[str, list]] = {}
        self._gauges: Dict[str, Dict[str, float]] = {}

    def counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: int = 1) -> None:
        """Increment a counter metric."""
        label_key = self._label_key(labels)
        if name not in self._counters:
            self._counters[name] = {}
        if label_key not in self._counters[name]:
            self._counters[name][label_key] = 0
        self._counters[name][label_key] += value

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation."""
        label_key = self._label_key(labels)
        if name not in self._histograms:
            self._histograms[name] = {}
        if label_key not in self._histograms[name]:
            self._histograms[name][label_key] = []
        self._histograms[name][label_key].append(value)

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        label_key = self._label_key(labels)
        if name not in self._gauges:
            self._gauges[name] = {}
        self._gauges[name][label_key] = value

    def _label_key(self, labels: Optional[Dict[str, str]]) -> str:
        """Create a string key from labels dict."""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Get current counter value."""
        label_key = self._label_key(labels)
        return self._counters.get(name, {}).get(label_key, 0)

    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics (count, sum, avg)."""
        label_key = self._label_key(labels)
        values = self._histograms.get(name, {}).get(label_key, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0}
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
        }

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        label_key = self._label_key(labels)
        return self._gauges.get(name, {}).get(label_key, 0)

    def get_all_metrics(self) -> Dict[str, Dict]:
        """Get all metrics for export."""
        return {
            "counters": self._counters,
            "histograms": {
                name: {k: self.get_histogram_stats(name, None) for k in v.keys()}
                for name, v in self._histograms.items()
            },
            "gauges": self._gauges,
        }


# Global metrics registry
_registry = MetricsRegistry()


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    return _registry


def record_job_start(job_id: str, status: str = "started") -> None:
    """Record that a job has started processing."""
    _registry.counter("ai_blogger_jobs_total", {"status": status})
    logger.debug(f"Recorded job start: {job_id}")


def record_job_completion(job_id: str, status: str) -> None:
    """Record that a job has completed with a specific status."""
    _registry.counter("ai_blogger_jobs_completed_total", {"status": status})
    logger.debug(f"Recorded job completion: {job_id} with status {status}")


def record_job_duration(job_id: str, duration_seconds: float) -> None:
    """Record the duration of a job in seconds."""
    _registry.histogram("ai_blogger_job_duration_seconds", duration_seconds)
    logger.debug(f"Recorded job duration: {job_id} took {duration_seconds:.2f}s")


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for recording HTTP request metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and record metrics."""
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        labels = {
            "method": request.method,
            "path": request.url.path,
            "status": str(response.status_code),
        }

        _registry.counter("ai_blogger_http_requests_total", labels)
        _registry.histogram("ai_blogger_http_request_duration_seconds", duration, labels)

        return response
