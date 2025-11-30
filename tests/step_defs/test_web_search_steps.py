"""Step definitions for Web Search (Tavily) fetcher BDD tests."""

import logging
import os
from unittest.mock import Mock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ai_blogger.fetchers import WebSearchFetcher, get_fetcher
from ai_blogger.models import Article

scenarios("../features/web_search_fetcher.feature")


@pytest.fixture
def mock_tavily_success_response():
    """Mock successful Tavily API response."""
    return {
        "results": [
            {
                "title": "Top 10 Developer Productivity Tools in 2024",
                "url": "https://devtools.com/productivity-2024",
                "content": "A comprehensive guide to the best tools for developers including IDEs, "
                "code assistants, and workflow automation. These tools can significantly "
                "improve your coding efficiency and reduce time spent on repetitive tasks.",
            },
            {
                "title": "How AI is Transforming Software Development",
                "url": "https://ai-dev.io/transformation",
                "content": "Exploring the impact of artificial intelligence on modern software "
                "engineering practices. From automated testing to intelligent code review, "
                "AI is revolutionizing how we build software.",
            },
            {
                "title": "The Future of Code Review",
                "url": "https://engineering-blog.com/code-review-future",
                "content": "Machine learning models are now capable of providing insightful "
                "code review comments. This article explores how teams are adopting "
                "AI-powered code review tools.",
            },
            {
                "title": "Agile Development in the Age of AI",
                "url": "https://agileworld.org/ai-agile",
                "content": "How AI assistants are changing agile methodologies and sprint planning. "
                "Teams report 30% improvement in velocity when using AI tools effectively.",
            },
            {
                "title": "Security Best Practices for Modern Applications",
                "url": "https://security-first.io/best-practices",
                "content": "Essential security practices every developer should follow. "
                "From input validation to secure authentication, protect your applications "
                "from common vulnerabilities.",
            },
        ]
    }


@pytest.fixture
def fetcher():
    """Get Web Search fetcher instance."""
    return get_fetcher("web")


@pytest.fixture
def context():
    """Shared test context."""
    return {}


# Given steps
@given("the Tavily API key is configured")
def tavily_configured(monkeypatch):
    """Set up Tavily API key."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-api-key")


@given("the Tavily API key is not configured")
def tavily_not_configured(monkeypatch):
    """Remove Tavily API key."""
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)


@given(parsers.parse('a topic "{topic}"'))
def set_topic(context, topic):
    """Set the topic for fetching."""
    context["topic"] = topic


@given("an empty topic")
def set_empty_topic(context):
    """Set an empty topic."""
    context["topic"] = ""


# When steps
@when(parsers.parse("I fetch {count:d} articles from web search"))
def fetch_web_articles(context, count, fetcher, mock_tavily_success_response, monkeypatch):
    """Fetch articles from web search with mocked response."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-api-key")

    mock_client = Mock()
    mock_client.search.return_value = mock_tavily_success_response

    with patch("ai_blogger.fetchers.TavilyClient", return_value=mock_client):
        context["articles"] = fetcher.fetch(context["topic"], count)


@when("I try to fetch articles from web search")
def try_fetch_web_articles(context, fetcher, caplog, monkeypatch):
    """Try to fetch articles from web search."""
    # Check if topic is empty (validation test) vs missing API key test
    if context.get("topic") == "":
        try:
            fetcher.fetch(context["topic"], 5)
        except ValueError as e:
            context["error"] = e
    else:
        # API key not configured test
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        with caplog.at_level(logging.WARNING):
            context["articles"] = fetcher.fetch("test topic", 5)
            context["warning_logged"] = any("TAVILY_API_KEY" in r.message for r in caplog.records)


@when("the Tavily API returns an error")
def fetch_with_tavily_error(context, fetcher, caplog, monkeypatch):
    """Fetch articles when Tavily API returns an error."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-api-key")

    mock_client = Mock()
    mock_client.search.side_effect = Exception("Tavily API Error")

    with patch("ai_blogger.fetchers.TavilyClient", return_value=mock_client):
        with caplog.at_level(logging.ERROR):
            context["articles"] = fetcher.fetch(context["topic"], 5)
            context["error_logged"] = len(caplog.records) > 0


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


@then("each article should have a summary")
def check_article_summary(context):
    """Check that each article has a summary."""
    for article in context["articles"]:
        assert article.summary
        assert len(article.summary) > 0


@then("I should receive an empty list")
def check_empty_list(context):
    """Check that articles list is empty."""
    assert context["articles"] == []


@then("a warning should be logged")
def check_warning_logged(context):
    """Check that a warning was logged."""
    assert context.get("warning_logged", False)


@then("an error should be logged")
def check_error_logged(context):
    """Check that an error was logged."""
    assert context.get("error_logged", False)


@then(parsers.parse('a ValueError should be raised with message "{message}"'))
def check_value_error(context, message):
    """Check that a ValueError was raised with the expected message."""
    assert "error" in context
    assert isinstance(context["error"], ValueError)
    assert message in str(context["error"])
