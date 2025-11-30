"""Integration tests for article fetchers.

These tests run against live APIs to verify that fetchers work correctly.

For Hacker News:
    No API key required - uses the free Algolia HN Search API.

For Tavily:
    Requires TAVILY_API_KEY (or TAVILY_KEY) environment variable.

Run with:
    pytest tests/test_fetchers_integration.py -v -m integration
"""

import os

import pytest

from ai_blogger.fetchers import get_fetcher

# Skip all tests in this module with integration marker
pytestmark = pytest.mark.integration


def emit_workflow_warning(message: str):
    """Emit a GitHub Actions workflow warning annotation.

    Args:
        message: The warning message to display.
    """
    print(f"::warning::{message}")


def emit_workflow_error(message: str):
    """Emit a GitHub Actions workflow error annotation.

    Args:
        message: The error message to display.
    """
    print(f"::error::{message}")


def get_tavily_api_key():
    """Get the Tavily API key from environment variables.

    Checks for both TAVILY_API_KEY (used by the fetcher) and TAVILY_KEY
    (alternative name that may be used in CI).

    Returns:
        The API key if configured, None otherwise.
    """
    return os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_KEY")


def tavily_api_configured():
    """Check if Tavily API is configured."""
    api_key = get_tavily_api_key()
    return api_key is not None and api_key.strip() != ""


def ensure_tavily_api_key(monkeypatch):
    """Ensure TAVILY_API_KEY is set for the fetcher.

    Maps TAVILY_KEY to TAVILY_API_KEY if only the former is set.
    """
    api_key = get_tavily_api_key()
    if api_key and not os.environ.get("TAVILY_API_KEY"):
        monkeypatch.setenv("TAVILY_API_KEY", api_key)


class TestHackerNewsIntegration:
    """Integration tests for Hacker News fetcher using live Algolia API."""

    @pytest.fixture
    def fetcher(self):
        """Get Hacker News fetcher instance."""
        return get_fetcher("hacker_news")

    def test_can_fetch_articles_for_topic(self, fetcher):
        """Test that we can fetch articles from Hacker News for a real topic."""
        articles = fetcher.fetch("Python programming", max_results=5)

        assert articles is not None
        assert isinstance(articles, list)
        # We should get some results for a common topic
        assert len(articles) > 0

    def test_articles_have_required_fields(self, fetcher):
        """Test that fetched articles have all required fields."""
        articles = fetcher.fetch("JavaScript", max_results=3)

        assert len(articles) > 0
        for article in articles:
            assert article.title is not None
            assert len(article.title) > 0
            assert article.url is not None
            assert str(article.url).startswith("http")
            assert article.source == "hacker_news"
            assert article.topic == "JavaScript"

    def test_respects_max_results_limit(self, fetcher):
        """Test that fetcher respects max_results parameter."""
        max_results = 3
        articles = fetcher.fetch("AI", max_results=max_results)

        # Should return at most max_results
        assert len(articles) <= max_results

    def test_handles_obscure_topic(self, fetcher):
        """Test that fetcher handles topics with few or no results gracefully."""
        # Use a very obscure query that likely returns no results
        articles = fetcher.fetch("xyznonexistent12345topic67890", max_results=5)

        # Should return empty list or few results, not raise an error
        assert isinstance(articles, list)

    def test_multiple_fetch_calls_work(self, fetcher):
        """Test that multiple fetch calls work correctly."""
        articles1 = fetcher.fetch("machine learning", max_results=2)
        articles2 = fetcher.fetch("web development", max_results=2)

        assert isinstance(articles1, list)
        assert isinstance(articles2, list)
        # Both should work independently
        assert len(articles1) > 0 or len(articles2) > 0

    def test_fetcher_availability(self, fetcher):
        """Test that Hacker News fetcher reports as available (no API key needed)."""
        assert fetcher.is_available() is True
        assert fetcher.env_key is None


class TestTavilyIntegration:
    """Integration tests for Tavily web search fetcher using live API."""

    @pytest.fixture
    def fetcher(self, monkeypatch):
        """Get Tavily fetcher instance with API key set."""
        if not tavily_api_configured():
            emit_workflow_warning("Tavily API key not configured - skipping Tavily integration tests")
            pytest.skip("Tavily API key not configured - skipping Tavily integration tests")

        ensure_tavily_api_key(monkeypatch)
        return get_fetcher("web")

    def _fetch_with_error_handling(self, fetcher, topic, max_results):
        """Fetch articles with proper error handling and workflow annotations."""
        try:
            return fetcher.fetch(topic, max_results=max_results)
        except Exception as e:
            emit_workflow_error(f"Tavily API error: {type(e).__name__}: {e}")
            raise

    def test_can_fetch_articles_for_topic(self, fetcher):
        """Test that we can fetch articles from Tavily for a real topic."""
        articles = self._fetch_with_error_handling(fetcher, "Python programming", max_results=5)

        assert articles is not None
        assert isinstance(articles, list)
        # We should get some results for a common topic
        assert len(articles) > 0

    def test_articles_have_required_fields(self, fetcher):
        """Test that fetched articles have all required fields."""
        articles = self._fetch_with_error_handling(fetcher, "software development", max_results=3)

        assert len(articles) > 0
        for article in articles:
            assert article.title is not None
            assert len(article.title) > 0
            assert article.url is not None
            assert str(article.url).startswith("http")
            assert article.source == "web"
            assert article.summary is not None
            assert len(article.summary) > 0

    def test_respects_max_results_limit(self, fetcher):
        """Test that fetcher respects max_results parameter."""
        max_results = 3
        articles = self._fetch_with_error_handling(fetcher, "AI", max_results=max_results)

        # Should return at most max_results
        assert len(articles) <= max_results

    def test_returns_software_engineering_relevant_results(self, fetcher):
        """Test that search results contain software engineering relevant terms."""
        articles = self._fetch_with_error_handling(fetcher, "developer productivity", max_results=5)

        assert len(articles) > 0

        assert len(articles) > 0
        # At least some articles should have software/dev/engineering related content
        all_text = " ".join((article.title + " " + article.summary).lower() for article in articles)
        relevant_terms = ["software", "developer", "development", "engineering", "code", "programming", "tech"]
        has_relevant_content = any(term in all_text for term in relevant_terms)
        assert has_relevant_content

    def test_fetcher_availability_with_key(self, fetcher):
        """Test that Tavily fetcher reports as available when key is set."""
        assert fetcher.is_available() is True


class TestFetcherAvailability:
    """Tests for fetcher availability checks."""

    def test_hacker_news_always_available(self):
        """Test that Hacker News fetcher is always available."""
        fetcher = get_fetcher("hacker_news")
        assert fetcher.is_available() is True

    def test_tavily_availability_depends_on_key(self, monkeypatch):
        """Test that Tavily fetcher availability depends on API key."""
        # Remove API key
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_KEY", raising=False)

        fetcher = get_fetcher("web")
        assert fetcher.is_available() is False

        # Set API key
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        fetcher = get_fetcher("web")
        assert fetcher.is_available() is True


class TestCombinedFetching:
    """Integration tests for fetching from multiple sources."""

    def test_can_fetch_from_hacker_news_and_tavily(self, monkeypatch):
        """Test that we can fetch from both sources in sequence."""
        hn_fetcher = get_fetcher("hacker_news")
        hn_articles = hn_fetcher.fetch("Python", max_results=2)

        assert isinstance(hn_articles, list)
        assert all(a.source == "hacker_news" for a in hn_articles)

        if tavily_api_configured():
            ensure_tavily_api_key(monkeypatch)

            web_fetcher = get_fetcher("web")
            web_articles = web_fetcher.fetch("Python", max_results=2)

            assert isinstance(web_articles, list)
            assert all(a.source == "web" for a in web_articles)
