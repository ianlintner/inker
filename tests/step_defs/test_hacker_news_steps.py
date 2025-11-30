"""Step definitions for Hacker News fetcher BDD tests."""

import logging
from unittest.mock import Mock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ai_blogger.fetchers import HackerNewsFetcher, get_fetcher
from ai_blogger.models import Article

scenarios("../features/hacker_news_fetcher.feature")


# Fixtures for mocked responses
@pytest.fixture
def mock_hn_success_response():
    """Mock successful Hacker News API response."""
    return {
        "hits": [
            {
                "title": "GPT-4 Changes Everything for Software Engineering",
                "url": "https://example.com/gpt4-engineering",
                "objectID": "12345",
                "story_text": "A deep dive into how GPT-4 is transforming development workflows.",
            },
            {
                "title": "The Rise of AI Coding Assistants",
                "url": "https://techblog.com/ai-coding",
                "objectID": "12346",
                "story_text": "Exploring GitHub Copilot and alternatives.",
            },
            {
                "title": "Developer Productivity in 2024",
                "url": "https://devnews.com/productivity",
                "objectID": "12347",
                "story_text": None,
            },
            {
                "title": "New Trends in Software Architecture",
                "url": None,
                "objectID": "12348",
                "story_text": "Modern architecture patterns for scalable systems.",
            },
            {
                "title": "Building Agentic AI Systems",
                "url": "https://ai-systems.io/agentic",
                "objectID": "12349",
                "story_text": "How to build AI agents that can take actions.",
            },
        ]
    }


@pytest.fixture
def mock_hn_empty_response():
    """Mock empty Hacker News API response."""
    return {"hits": []}


@pytest.fixture
def fetcher():
    """Get Hacker News fetcher instance."""
    return get_fetcher("hacker_news")


@pytest.fixture
def context():
    """Shared test context."""
    return {}


# Given steps
@given("the Hacker News API is available")
def hn_api_available():
    """Hacker News API is available."""
    pass


@given(parsers.parse('a topic "{topic}"'))
def set_topic(context, topic):
    """Set the topic for fetching."""
    context["topic"] = topic


@given("an empty topic")
def set_empty_topic(context):
    """Set an empty topic."""
    context["topic"] = ""


# When steps
@when(parsers.parse("I fetch {count:d} articles from Hacker News"))
def fetch_articles(context, count, fetcher, mock_hn_success_response):
    """Fetch articles from Hacker News with mocked response."""
    mock_response = Mock()
    mock_response.json.return_value = mock_hn_success_response
    mock_response.raise_for_status = Mock()

    with patch("requests.get", return_value=mock_response):
        context["articles"] = fetcher.fetch(context["topic"], count)


@when(parsers.parse("I fetch {count:d} articles from Hacker News with empty results"))
def fetch_articles_empty(context, count, fetcher, mock_hn_empty_response):
    """Fetch articles when API returns empty results."""
    mock_response = Mock()
    mock_response.json.return_value = mock_hn_empty_response
    mock_response.raise_for_status = Mock()

    with patch("requests.get", return_value=mock_response):
        context["articles"] = fetcher.fetch(context["topic"], count)


@when("the Hacker News API returns an error")
def fetch_with_error(context, fetcher, caplog):
    """Fetch articles when API returns an error."""
    import requests

    with patch("requests.get", side_effect=requests.RequestException("API Error")):
        with caplog.at_level(logging.ERROR):
            context["articles"] = fetcher.fetch(context["topic"], 5)
            context["error_logged"] = len(caplog.records) > 0


@when("I try to fetch articles from Hacker News")
def try_fetch_invalid(context, fetcher):
    """Try to fetch articles with invalid parameters."""
    try:
        fetcher.fetch(context["topic"], 5)
    except ValueError as e:
        context["error"] = e


@when(parsers.parse("I try to fetch with max_results {count:d}"))
def try_fetch_invalid_count(context, count, fetcher):
    """Try to fetch with invalid max_results."""
    try:
        fetcher.fetch(context["topic"], count)
    except ValueError as e:
        context["error"] = e


# Then steps
@then("I should receive a list of articles")
def check_articles_list(context):
    """Check that articles is a list."""
    assert isinstance(context["articles"], list)
    assert len(context["articles"]) > 0


@then("each article should have a title")
def check_article_titles(context):
    """Check that each article has a title."""
    for article in context["articles"]:
        assert article.title
        assert len(article.title) > 0


@then("each article should have a URL")
def check_article_urls(context):
    """Check that each article has a URL."""
    for article in context["articles"]:
        assert article.url
        assert str(article.url).startswith("http")


@then(parsers.parse('each article should have source "{source}"'))
def check_article_source(context, source):
    """Check that each article has the correct source."""
    for article in context["articles"]:
        assert article.source == source


@then("I should receive an empty list")
def check_empty_list(context):
    """Check that articles list is empty."""
    assert context["articles"] == []


@then("an error should be logged")
def check_error_logged(context):
    """Check that an error was logged."""
    assert context.get("error_logged", False) or "error" in context


@then(parsers.parse('a ValueError should be raised with message "{message}"'))
def check_value_error(context, message):
    """Check that a ValueError was raised with the expected message."""
    assert "error" in context
    assert isinstance(context["error"], ValueError)
    assert message in str(context["error"])
