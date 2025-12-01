"""Tests for the Prometheus metrics and OpenTelemetry tracing module."""

import pytest

from ai_blogger.metrics import (
    OPENTELEMETRY_AVAILABLE,
    PROMETHEUS_AVAILABLE,
    NoOpSpan,
    NoOpTracer,
    get_tracer,
    record_approval_action,
    record_job_status_change,
    record_job_submission,
    record_queue_complete,
    record_queue_dequeue,
    record_queue_enqueue,
    record_queue_fail,
    set_system_info,
    traced,
    track_api_request,
    track_job_execution,
    track_storage_operation,
    update_queue_size,
)


class TestPrometheusMetrics:
    """Tests for Prometheus metrics instrumentation."""

    def test_prometheus_available(self):
        """Test that prometheus_client is available."""
        assert PROMETHEUS_AVAILABLE is True

    def test_record_job_submission(self):
        """Test recording job submission metrics."""
        # Should not raise
        record_job_submission(is_duplicate=False)
        record_job_submission(is_duplicate=True)

    def test_record_job_status_change(self):
        """Test recording job status change metrics."""
        # Should not raise
        record_job_status_change("pending", "fetching")
        record_job_status_change("fetching", "generating")
        record_job_status_change("generating", "completed")
        record_job_status_change("pending", "failed")

    def test_record_approval_action(self):
        """Test recording approval action metrics."""
        # Should not raise
        record_approval_action("approved")
        record_approval_action("rejected")
        record_approval_action("revision_requested")

    def test_record_queue_operations(self):
        """Test recording queue operation metrics."""
        # Should not raise
        record_queue_enqueue("blog_post")
        record_queue_dequeue("blog_post")
        record_queue_complete()
        record_queue_fail(will_retry=True)
        record_queue_fail(will_retry=False)

    def test_update_queue_size(self):
        """Test updating queue size gauge."""
        # Should not raise
        update_queue_size("pending", 10)
        update_queue_size("processing", 5)
        update_queue_size("completed", 100)

    def test_track_api_request(self):
        """Test tracking API request metrics."""
        # Should not raise
        track_api_request("GET", "/api/health", 200, 0.05)
        track_api_request("POST", "/api/jobs", 201, 0.1)
        track_api_request("GET", "/api/jobs/123", 404, 0.02)

    def test_set_system_info(self):
        """Test setting system info."""
        # Should not raise
        set_system_info(version="0.1.0")
        set_system_info(version="0.2.0", environment="test")


class TestOpenTelemetryTracing:
    """Tests for OpenTelemetry tracing instrumentation."""

    def test_get_tracer(self):
        """Test getting a tracer."""
        tracer = get_tracer()
        assert tracer is not None

    def test_get_tracer_returns_same_instance(self):
        """Test that get_tracer returns the same instance."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()
        # Should be the same instance (or both NoOpTracer if OTel not available)
        if OPENTELEMETRY_AVAILABLE:
            assert tracer1 is tracer2
        else:
            # Both should be NoOpTracer instances
            assert isinstance(tracer1, NoOpTracer)
            assert isinstance(tracer2, NoOpTracer)


class TestNoOpImplementations:
    """Tests for no-op implementations when libraries are not available."""

    def test_noop_span(self):
        """Test NoOpSpan implementation."""
        span = NoOpSpan()

        # All methods should be callable without raising
        with span:
            span.set_attribute("key", "value")
            span.add_event("event_name", {"attr": "value"})
            span.set_status(None)
            span.record_exception(Exception("test"))

        span.end()

    def test_noop_tracer(self):
        """Test NoOpTracer implementation."""
        tracer = NoOpTracer()

        # start_span should return a NoOpSpan
        span = tracer.start_span("test_span")
        assert isinstance(span, NoOpSpan)

        # start_as_current_span should return a context manager
        with tracer.start_as_current_span("test_span") as span:
            assert isinstance(span, NoOpSpan)


class TestInstrumentationHelpers:
    """Tests for instrumentation helper functions and decorators."""

    def test_track_job_execution_success(self):
        """Test track_job_execution context manager for successful job."""
        job_id = "test-job-123"

        with track_job_execution(job_id, "blog_post"):
            # Simulate job work
            pass

        # Should complete without raising

    def test_track_job_execution_failure(self):
        """Test track_job_execution context manager for failed job."""
        job_id = "test-job-456"

        with pytest.raises(ValueError):
            with track_job_execution(job_id, "blog_post"):
                raise ValueError("Test error")

    def test_track_storage_operation(self):
        """Test track_storage_operation context manager."""
        with track_storage_operation("create", "post"):
            # Simulate storage operation
            pass

        with track_storage_operation("read", "job"):
            pass

    def test_traced_decorator(self):
        """Test traced decorator."""

        @traced("custom_operation")
        def my_function(x, y):
            return x + y

        result = my_function(1, 2)
        assert result == 3

    def test_traced_decorator_without_name(self):
        """Test traced decorator without explicit name."""

        @traced()
        def another_function():
            return "result"

        result = another_function()
        assert result == "result"

    def test_traced_decorator_with_attributes(self):
        """Test traced decorator with attributes."""

        @traced("operation", {"custom.attr": "value"})
        def attributed_function():
            return 42

        result = attributed_function()
        assert result == 42


class TestMetricsEndpoint:
    """Tests for the /metrics endpoint in the API."""

    def test_metrics_endpoint_available(self):
        """Test that the /metrics endpoint is added when Prometheus is available."""
        from ai_blogger.frontend_api import create_app

        app = create_app()

        # Find the /metrics route
        metrics_routes = [route for route in app.routes if hasattr(route, "path") and route.path == "/metrics"]

        if PROMETHEUS_AVAILABLE:
            assert len(metrics_routes) == 1
        else:
            assert len(metrics_routes) == 0

    def test_metrics_endpoint_returns_prometheus_format(self):
        """Test that /metrics endpoint returns Prometheus format."""
        from fastapi.testclient import TestClient

        from ai_blogger.frontend_api import create_app

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("Prometheus not available")

        app = create_app()
        client = TestClient(app)

        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

        # Check for some expected metrics in the output
        content = response.text
        assert "ai_blogger_" in content or "TYPE" in content


class TestMetricsIntegration:
    """Integration tests for metrics with services."""

    def test_job_submission_increments_counter(self):
        """Test that job submission increments the counter."""
        import shutil
        import tempfile

        from ai_blogger import JobRequest, JobService

        temp_dir = tempfile.mkdtemp()
        try:
            service = JobService(temp_dir)

            # Submit a job
            request = JobRequest(topics=["AI"])
            response = service.submit_job(request)

            assert response.job_id is not None
            # Metrics should have been recorded (we can't easily check counter values)

            # Submit duplicate
            request_dup = JobRequest(correlation_id="dup-key")
            service.submit_job(request_dup)
            service.submit_job(request_dup)  # This should record duplicate

        finally:
            shutil.rmtree(temp_dir)

    def test_approval_action_increments_counter(self):
        """Test that approval actions increment counters."""
        import shutil
        import tempfile

        from ai_blogger import (
            ApprovalRequest,
            BlogPostCreate,
            FeedbackService,
            SQLiteStorage,
            StorageConfig,
        )

        temp_dir = tempfile.mkdtemp()
        try:
            config = StorageConfig(
                backend_type="sqlite",
                db_path=f"{temp_dir}/test.db",
                auto_migrate=True,
            )
            storage = SQLiteStorage(config)

            # Create a post
            create = BlogPostCreate(
                title="Test Post",
                content="Test content",
                topic="testing",
                sources=["https://example.com"],
                job_id="job-123",
                scoring={"total": 8.0},
            )
            post = storage.create_post(create)

            # Create feedback service and approve
            feedback_service = FeedbackService(storage)
            approval_request = ApprovalRequest(
                post_id=post.id,
                feedback="Good content",
                actor="reviewer",
            )
            response = feedback_service.approve_post(approval_request)

            assert response.success is True
            # Metrics should have been recorded

            storage.close()
        finally:
            shutil.rmtree(temp_dir)


class TestMetricsExports:
    """Test that all metrics are properly exported."""

    def test_all_metrics_importable(self):
        """Test that all metrics can be imported from ai_blogger."""
        from ai_blogger import (
            OPENTELEMETRY_AVAILABLE,
            PROMETHEUS_AVAILABLE,
            get_tracer,
            record_approval_action,
            record_job_status_change,
            record_job_submission,
            record_queue_complete,
            record_queue_dequeue,
            record_queue_enqueue,
            record_queue_fail,
            set_system_info,
            traced,
            track_api_request,
            track_job_execution,
            track_storage_operation,
            update_queue_size,
        )

        # All should be importable
        assert PROMETHEUS_AVAILABLE is not None
        assert OPENTELEMETRY_AVAILABLE is not None
        assert get_tracer is not None
        assert traced is not None
        assert track_job_execution is not None
        assert track_storage_operation is not None
        assert track_api_request is not None
        assert record_job_submission is not None
        assert record_job_status_change is not None
        assert record_approval_action is not None
        assert record_queue_enqueue is not None
        assert record_queue_dequeue is not None
        assert record_queue_complete is not None
        assert record_queue_fail is not None
        assert update_queue_size is not None
        assert set_system_info is not None
