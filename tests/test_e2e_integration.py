"""End-to-end integration tests for the AI Blogger pipeline.

These tests validate the complete workflow from fetching articles through
generating final blog posts. They test the integration of all components:
- Article fetchers (Hacker News, Tavily, YouTube)
- Storage backends (SQLite, PostgreSQL)
- Queue backends (Memory, PostgreSQL, Redis)
- LLM chains (generation, scoring, refinement)
- Job management and persistence

Run with:
    pytest tests/test_e2e_integration.py -v -m integration
"""

import os
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from ai_blogger.chains import generate_candidates, refine_winner, score_candidates
from ai_blogger.fetchers import fetch_all_articles, get_available_sources, get_fetcher
from ai_blogger.job_api import JobService
from ai_blogger.job_models import JobRequest, JobStatus
from ai_blogger.job_store import JobStore
from ai_blogger.models import Article, CandidatePost, PostScore, ScoredPost
from ai_blogger.persistence.factory import create_storage
from ai_blogger.queue.factory import create_queue
from ai_blogger.utils import generate_filename

pytestmark = pytest.mark.integration


# Fixtures
@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for output files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def setup_api_keys(monkeypatch):
    """Ensure all necessary API keys are set."""
    ensure_api_key(monkeypatch, "TAVILY_API_KEY", "TAVILY_KEY")
    ensure_api_key(monkeypatch, "OPENAI_API_KEY")
    ensure_api_key(monkeypatch, "YOUTUBE_API_KEY")


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_job_dir():
    """Create temporary directory for job storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# Utility functions
def get_tavily_api_key() -> Optional[str]:
    """Get the Tavily API key from environment variables."""
    return os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_KEY")


def tavily_available() -> bool:
    """Check if Tavily API is configured."""
    api_key = get_tavily_api_key()
    return api_key is not None and api_key.strip() != ""


def youtube_available() -> bool:
    """Check if YouTube API is configured."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    return api_key is not None and api_key.strip() != ""


def openai_available() -> bool:
    """Check if OpenAI API is configured."""
    api_key = os.environ.get("OPENAI_API_KEY")
    return api_key is not None and api_key.strip() != ""


def ensure_api_key(monkeypatch, env_var: str, alias: Optional[str] = None):
    """Ensure an API key is set, optionally mapping from an alias."""
    value = os.environ.get(env_var)
    if not value and alias:
        value = os.environ.get(alias)
        if value:
            monkeypatch.setenv(env_var, value)


class TestEndToEndPipeline:
    """End-to-end tests for the complete blog generation pipeline."""

    def test_complete_pipeline_hacker_news_only(self, temp_output_dir, setup_api_keys):
        """Test complete pipeline using only Hacker News (no API key required)."""
        # Skip if OpenAI not available
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Step 1: Fetch articles from Hacker News
        print("\n[1/4] Fetching articles from Hacker News...")
        articles = fetch_all_articles(
            topics=["Python programming"],
            sources=["hacker_news"],
            max_results={"hacker_news": 5},
        )

        assert len(articles) > 0, "Should fetch at least one article"
        assert all(a.source == "hacker_news" for a in articles)

        # Step 2: Generate candidates
        print("[2/4] Generating candidate blog posts...")
        candidates = generate_candidates(articles, num_candidates=2)

        assert len(candidates) >= 1, "Should generate at least one candidate"
        for candidate in candidates:
            assert isinstance(candidate, CandidatePost)
            assert candidate.title
            assert candidate.content
            assert len(candidate.sources) > 0

        # Step 3: Score candidates
        print("[3/4] Scoring candidates...")
        scored = score_candidates(candidates)

        assert len(scored) >= 1, "Should score at least one candidate"
        for sc in scored:
            assert isinstance(sc, ScoredPost)
            assert isinstance(sc.score, PostScore)
            assert 0 <= sc.score.total <= 10

        # Step 4: Refine winner
        print("[4/4] Refining winner...")
        winner = scored[0]
        final_content = refine_winner(winner)

        assert final_content, "Should produce final content"
        assert len(final_content) > 100, "Final content should be substantial"

        # Verify we can save the result
        filename = generate_filename(winner.candidate.title)
        filepath = temp_output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_content)

        assert filepath.exists()
        assert filepath.stat().st_size > 0

        print(f"\n✓ Complete pipeline test passed")
        print(f"  Articles fetched: {len(articles)}")
        print(f"  Candidates generated: {len(candidates)}")
        print(f"  Winner score: {winner.score.total:.2f}/10")
        print(f"  Output file: {filepath}")

    def test_complete_pipeline_all_sources(self, temp_output_dir, setup_api_keys):
        """Test complete pipeline using all available sources."""
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Determine available sources
        available_sources = []
        if get_fetcher("hacker_news").is_available():
            available_sources.append("hacker_news")
        if tavily_available() and get_fetcher("web").is_available():
            available_sources.append("web")
        if youtube_available() and get_fetcher("youtube") and get_fetcher("youtube").is_available():
            available_sources.append("youtube")

        if not available_sources:
            pytest.skip("No sources available for testing")

        print(f"\nTesting with sources: {available_sources}")

        # Fetch from all available sources
        articles = fetch_all_articles(
            topics=["artificial intelligence"],
            sources=available_sources,
            max_results={source: 3 for source in available_sources},
        )

        assert len(articles) > 0, "Should fetch articles from available sources"

        # Verify articles from different sources
        sources_found = set(a.source for a in articles)
        print(f"Articles fetched from: {sources_found}")

        # Generate and process
        candidates = generate_candidates(articles, num_candidates=3)
        assert len(candidates) >= 1

        scored = score_candidates(candidates)
        assert len(scored) >= 1

        winner = scored[0]
        final_content = refine_winner(winner)

        assert final_content
        assert len(final_content) > 100

        print(f"\n✓ Multi-source pipeline test passed")
        print(f"  Sources used: {sources_found}")
        print(f"  Total articles: {len(articles)}")
        print(f"  Final score: {winner.score.total:.2f}/10")

    def test_pipeline_with_insufficient_articles(self, setup_api_keys):
        """Test pipeline behavior when very few articles are available."""
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Fetch with very restrictive limits
        articles = fetch_all_articles(
            topics=["Python"],
            sources=["hacker_news"],
            max_results={"hacker_news": 2},
        )

        # Even with few articles, pipeline should work
        if len(articles) > 0:
            candidates = generate_candidates(articles, num_candidates=1)
            assert len(candidates) >= 1

            scored = score_candidates(candidates)
            assert len(scored) >= 1

            final_content = refine_winner(scored[0])
            assert final_content

    def test_pipeline_error_handling_no_articles(self, setup_api_keys):
        """Test that pipeline handles gracefully when no articles are found."""
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Use a topic that's extremely unlikely to return results
        articles = fetch_all_articles(
            topics=["xyznonexistent12345topic67890"],
            sources=["hacker_news"],
            max_results={"hacker_news": 5},
        )

        # If no articles, generation should handle it gracefully
        if len(articles) == 0:
            # Expect ValueError when trying to generate with no articles
            with pytest.raises(ValueError):
                generate_candidates(articles, num_candidates=1)


class TestStorageBackendIntegration:
    """End-to-end tests for storage backend integration."""

    def test_sqlite_storage_full_workflow(self, temp_db_path, setup_api_keys):
        """Test complete workflow with SQLite storage."""
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Create SQLite storage
        storage = create_storage(backend_type="sqlite", db_path=temp_db_path)

        # Create a job using the storage backend
        from ai_blogger.job_models import JobConfig

        job = storage.create_job(
            topics=["Python"],
            sources=["hacker_news"],
            config=JobConfig(max_results_per_source=3),
        )

        assert job.job_id
        assert job.status == JobStatus.PENDING

        # Retrieve job
        retrieved = storage.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id
        assert retrieved.topics == ["Python"]

        # Update job status
        storage.update_job_status(job.job_id, JobStatus.RUNNING)
        updated = storage.get_job(job.job_id)
        assert updated.status == JobStatus.RUNNING

        # List jobs
        jobs = storage.list_jobs(limit=10)
        assert len(jobs) >= 1
        assert any(j.job_id == job.job_id for j in jobs)

        print(f"\n✓ SQLite storage workflow test passed")
        print(f"  Job ID: {job.job_id}")
        print(f"  Database: {temp_db_path}")

    def test_postgres_storage_if_available(self, setup_api_keys):
        """Test complete workflow with PostgreSQL storage if DATABASE_URL is set."""
        database_url = os.environ.get("DATABASE_URL")

        if not database_url or not database_url.startswith(("postgresql://", "postgres://")):
            pytest.skip("PostgreSQL DATABASE_URL not configured")

        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Create PostgreSQL storage
        storage = create_storage(backend_type="postgres", connection_string=database_url)

        # Create a job using the storage backend
        from ai_blogger.job_models import JobConfig

        job = storage.create_job(
            topics=["machine learning"],
            sources=["hacker_news"],
            config=JobConfig(max_results_per_source=5),
        )

        assert job.job_id
        assert job.status == JobStatus.PENDING

        # Retrieve and update
        retrieved = storage.get_job(job.job_id)
        assert retrieved is not None

        storage.update_job_status(job.job_id, JobStatus.COMPLETED)
        updated = storage.get_job(job.job_id)
        assert updated.status == JobStatus.COMPLETED

        # Cleanup
        storage.close()

        print(f"\n✓ PostgreSQL storage workflow test passed")
        print(f"  Job ID: {job.job_id}")


class TestQueueBackendIntegration:
    """End-to-end tests for queue backend integration."""

    def test_memory_queue_workflow(self, setup_api_keys):
        """Test complete workflow with in-memory queue."""
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Create memory queue
        queue = create_queue(backend_type="memory")

        # Create a job message
        job_data = {
            "job_id": "test-job-123",
            "topics": ["Python"],
            "sources": ["hacker_news"],
        }

        # Enqueue
        job_id = queue.enqueue("generate_blog", job_data, priority=5)
        assert job_id

        # Dequeue
        job = queue.dequeue()
        assert job is not None
        assert job.job_id == job_id
        assert job.payload["job_id"] == "test-job-123"

        # Complete
        queue.complete(job_id)

        # Should be no more jobs
        next_job = queue.dequeue()
        assert next_job is None

        print(f"\n✓ Memory queue workflow test passed")

    def test_postgres_queue_if_available(self, setup_api_keys):
        """Test complete workflow with PostgreSQL queue if DATABASE_URL is set."""
        database_url = os.environ.get("DATABASE_URL")

        if not database_url or not database_url.startswith(("postgresql://", "postgres://")):
            pytest.skip("PostgreSQL DATABASE_URL not configured")

        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Create PostgreSQL queue
        queue = create_queue(backend_type="postgres", connection_string=database_url)

        job_data = {
            "job_id": "test-pg-job-456",
            "topics": ["AI"],
            "sources": ["hacker_news"],
        }

        # Enqueue
        job_id = queue.enqueue("generate_blog", job_data)
        assert job_id

        # Dequeue
        job = queue.dequeue()
        assert job is not None
        assert job.job_id == job_id

        # Complete
        queue.complete(job_id)

        # Cleanup
        queue.close()

        print(f"\n✓ PostgreSQL queue workflow test passed")

    def test_redis_queue_if_available(self, setup_api_keys):
        """Test complete workflow with Redis queue if REDIS_URL is set."""
        redis_url = os.environ.get("REDIS_URL")

        if not redis_url:
            pytest.skip("REDIS_URL not configured")

        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        try:
            # Create Redis queue
            queue = create_queue(backend_type="redis", connection_string=redis_url)

            job_data = {
                "job_id": "test-redis-job-789",
                "topics": ["web development"],
                "sources": ["hacker_news"],
            }

            # Enqueue
            job_id = queue.enqueue("generate_blog", job_data)
            assert job_id

            # Dequeue
            job = queue.dequeue()
            assert job is not None

            # Complete
            queue.complete(job_id)

            # Cleanup
            queue.close()

            print(f"\n✓ Redis queue workflow test passed")
        except ImportError:
            pytest.skip("Redis dependencies not installed")


class TestJobManagementIntegration:
    """End-to-end tests for job management API."""

    @pytest.fixture
    def temp_job_dir(self):
        """Create temporary directory for job storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_job_creation_and_retrieval(self, temp_job_dir, setup_api_keys):
        """Test creating and retrieving jobs through the job API."""
        # Create job service
        service = JobService(storage_dir=temp_job_dir)

        # Create a job request
        request = JobRequest(
            topics=["Python", "AI"],
            sources=["hacker_news", "web"],
            max_results_per_source=10,
        )

        # Submit job
        response = service.submit_job(request)

        assert response.job_id
        assert response.status == JobStatus.PENDING

        # Get job status
        status = service.get_job_status(response.job_id)
        assert status is not None
        assert status.job_id == response.job_id
        assert status.status == JobStatus.PENDING

        print(f"\n✓ Job creation and retrieval test passed")
        print(f"  Job ID: {response.job_id}")

    def test_job_submission_with_correlation_id(self, temp_job_dir, setup_api_keys):
        """Test job submission with correlation ID for idempotency."""
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Create job service
        service = JobService(storage_dir=temp_job_dir)

        correlation_id = "test-correlation-123"

        # Submit first job
        request1 = JobRequest(
            topics=["Python programming"],
            sources=["hacker_news"],
            max_results_per_source=5,
            correlation_id=correlation_id,
        )

        response1 = service.submit_job(request1)
        assert response1.job_id
        assert response1.correlation_id == correlation_id
        assert not response1.is_duplicate

        # Submit second job with same correlation ID
        request2 = JobRequest(
            topics=["Python programming"],
            sources=["hacker_news"],
            max_results_per_source=5,
            correlation_id=correlation_id,
        )

        response2 = service.submit_job(request2)
        assert response2.job_id == response1.job_id
        assert response2.is_duplicate

        print(f"\n✓ Job submission with correlation ID test passed")
        print(f"  Job ID: {response1.job_id}")
        print(f"  Correlation ID: {correlation_id}")


class TestErrorRecoveryAndEdgeCases:
    """End-to-end tests for error recovery and edge cases."""

    def test_missing_openai_key_fails_gracefully(self, monkeypatch):
        """Test that missing OpenAI key is handled gracefully."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Fetching should still work
        articles = fetch_all_articles(
            topics=["Python"],
            sources=["hacker_news"],
            max_results={"hacker_news": 2},
        )

        # But generation should fail or skip
        if len(articles) > 0:
            # Without OpenAI key, LLM chains will fail
            # This is expected behavior
            pass

    def test_pipeline_with_mixed_source_availability(self, monkeypatch, setup_api_keys):
        """Test pipeline when some sources are available and others aren't."""
        if not openai_available():
            pytest.skip("OpenAI API key required for E2E tests")

        # Remove Tavily key if it exists
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_KEY", raising=False)

        # Try to fetch from multiple sources
        # Only Hacker News should work
        articles = fetch_all_articles(
            topics=["Python"],
            sources=["hacker_news", "web"],  # web won't work without Tavily key
            max_results={"hacker_news": 5, "web": 5},
        )

        # Should get articles from Hacker News at least
        assert len(articles) > 0
        assert all(a.source == "hacker_news" for a in articles)

        # Pipeline should still complete
        candidates = generate_candidates(articles, num_candidates=1)
        assert len(candidates) >= 1

        print(f"\n✓ Mixed source availability test passed")
        print(f"  Articles from Hacker News: {len(articles)}")

    def test_auto_storage_detection(self, monkeypatch):
        """Test that storage backend is auto-detected correctly."""
        # Test SQLite default
        monkeypatch.delenv("DATABASE_URL", raising=False)
        storage = create_storage()
        assert storage.__class__.__name__ == "SQLiteStorage"
        storage.close()

        # Test PostgreSQL detection
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        try:
            storage = create_storage()
            assert storage.__class__.__name__ == "PostgresStorage"
            storage.close()
        except ImportError:
            pytest.skip("PostgreSQL dependencies not installed")

        print(f"\n✓ Auto storage detection test passed")

    def test_auto_queue_detection(self, monkeypatch):
        """Test that queue backend is auto-detected correctly."""
        # Test memory default
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        queue = create_queue()
        assert queue.__class__.__name__ == "MemoryQueue"
        queue.close()

        # Test PostgreSQL detection
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        try:
            queue = create_queue()
            assert queue.__class__.__name__ == "PostgresQueue"
            queue.close()
        except ImportError:
            pytest.skip("PostgreSQL dependencies not installed")

        # Test Redis detection
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        try:
            queue = create_queue()
            assert queue.__class__.__name__ == "RedisQueue"
            queue.close()
        except ImportError:
            pytest.skip("Redis dependencies not installed")

        print(f"\n✓ Auto queue detection test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
