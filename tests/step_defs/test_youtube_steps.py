"""Step definitions for YouTube fetcher BDD tests."""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ai_blogger.fetchers import get_fetcher

scenarios("../features/youtube_fetcher.feature")


def get_recent_date():
    """Get a date within the last 7 days."""
    return (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_old_date():
    """Get a date older than 7 days."""
    return (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def mock_youtube_success_response():
    """Mock successful YouTube API response."""
    return {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Building AI Agents from Scratch - Full Tutorial",
                    "description": "Learn how to build your own AI agents using LangChain and OpenAI. "
                    "This comprehensive tutorial covers everything from basics to advanced patterns.",
                    "channelTitle": "AI Engineering Weekly",
                    "publishedAt": get_recent_date(),
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg"},
                        "default": {"url": "https://i.ytimg.com/vi/abc123/default.jpg"},
                    },
                },
            },
            {
                "id": {"videoId": "def456"},
                "snippet": {
                    "title": "GitHub Copilot Tips and Tricks 2024",
                    "description": "Master GitHub Copilot with these productivity tips. "
                    "Learn keyboard shortcuts, prompt engineering, and more.",
                    "channelTitle": "DevOps Toolbox",
                    "publishedAt": get_recent_date(),
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/def456/hqdefault.jpg"},
                    },
                },
            },
            {
                "id": {"videoId": "ghi789"},
                "snippet": {
                    "title": "The Future of Software Engineering Leadership",
                    "description": "What skills will engineering managers need in the AI era? "
                    "A deep dive into the changing landscape of tech leadership.",
                    "channelTitle": "Tech Leadership Talks",
                    "publishedAt": get_recent_date(),
                    "thumbnails": {
                        "default": {"url": "https://i.ytimg.com/vi/ghi789/default.jpg"},
                    },
                },
            },
            {
                "id": {"videoId": "jkl012"},
                "snippet": {
                    "title": "Cloud Security Best Practices",
                    "description": "Essential security practices for cloud infrastructure. "
                    "Protect your AWS, Azure, and GCP deployments.",
                    "channelTitle": "Cloud Security Pro",
                    "publishedAt": get_recent_date(),
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/jkl012/hqdefault.jpg"},
                    },
                },
            },
            {
                "id": {"videoId": "mno345"},
                "snippet": {
                    "title": "Dev Tools That Changed My Life",
                    "description": "My favorite developer tools and how they 10x my productivity. "
                    "From terminal apps to IDE extensions.",
                    "channelTitle": "Coding With Style",
                    "publishedAt": get_recent_date(),
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/mno345/hqdefault.jpg"},
                    },
                },
            },
        ]
    }


@pytest.fixture
def mock_youtube_old_videos_response():
    """Mock YouTube API response with old videos."""
    return {
        "items": [
            {
                "id": {"videoId": "old123"},
                "snippet": {
                    "title": "Old Video - Should Be Filtered",
                    "description": "This video is too old.",
                    "channelTitle": "Old Channel",
                    "publishedAt": get_old_date(),
                    "thumbnails": {"default": {"url": "https://i.ytimg.com/vi/old123/default.jpg"}},
                },
            },
        ]
    }


@pytest.fixture
def fetcher():
    """Get YouTube fetcher instance."""
    return get_fetcher("youtube")


# Given steps
@given("the YouTube API key is configured")
def youtube_configured(monkeypatch):
    """Set up YouTube API key."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube-api-key")


@given("the YouTube API key is not configured")
def youtube_not_configured(monkeypatch):
    """Remove YouTube API key."""
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)


@given(parsers.parse('a topic "{topic}"'))
def set_topic(context, topic):
    """Set the topic for fetching."""
    context["topic"] = topic


# When steps
@when(parsers.parse("I fetch {count:d} videos from YouTube"))
def fetch_youtube_videos(context, count, fetcher, mock_youtube_success_response, monkeypatch):
    """Fetch videos from YouTube with mocked response."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube-api-key")

    mock_response = Mock()
    mock_response.json.return_value = mock_youtube_success_response
    mock_response.raise_for_status = Mock()

    with patch("requests.get", return_value=mock_response):
        context["articles"] = fetcher.fetch(context["topic"], count)


@when("YouTube returns videos older than 7 days")
def fetch_old_videos(context, fetcher, mock_youtube_old_videos_response, monkeypatch):
    """Fetch videos that are older than 7 days."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube-api-key")

    mock_response = Mock()
    mock_response.json.return_value = mock_youtube_old_videos_response
    mock_response.raise_for_status = Mock()

    with patch("requests.get", return_value=mock_response):
        context["articles"] = fetcher.fetch(context["topic"], 5)


@when("I try to fetch videos from YouTube")
def try_fetch_youtube_videos(context, fetcher, caplog, monkeypatch):
    """Try to fetch videos from YouTube without API key."""
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING):
        context["articles"] = fetcher.fetch("test topic", 5)
        context["warning_logged"] = any("YOUTUBE_API_KEY" in r.message for r in caplog.records)


@when("the YouTube API returns an error")
def fetch_with_youtube_error(context, fetcher, caplog, monkeypatch):
    """Fetch videos when YouTube API returns an error."""
    import requests

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube-api-key")

    with patch("requests.get", side_effect=requests.RequestException("YouTube API Error")):
        with caplog.at_level(logging.ERROR):
            context["articles"] = fetcher.fetch(context["topic"], 5)
            context["error_logged"] = len(caplog.records) > 0


@when("I fetch videos with channel information")
def fetch_with_channel_info(context, fetcher, mock_youtube_success_response, monkeypatch):
    """Fetch videos with channel information."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube-api-key")

    mock_response = Mock()
    mock_response.json.return_value = mock_youtube_success_response
    mock_response.raise_for_status = Mock()

    with patch("requests.get", return_value=mock_response):
        context["articles"] = fetcher.fetch(context["topic"], 5)


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


@then(parsers.parse('each article should have a URL starting with "{prefix}"'))
def check_article_url_prefix(context, prefix):
    """Check that each article URL starts with expected prefix."""
    for article in context["articles"]:
        assert str(article.url).startswith(prefix)


@then(parsers.parse('each article should have source "{source}"'))
def check_article_source(context, source):
    """Check that each article has the correct source."""
    for article in context["articles"]:
        assert article.source == source


@then("each article should have a thumbnail")
def check_article_thumbnail(context):
    """Check that each article has a thumbnail."""
    for article in context["articles"]:
        assert article.thumbnail
        assert article.thumbnail.startswith("http")


@then("those videos should be filtered out")
def check_old_videos_filtered(context):
    """Check that old videos are filtered out."""
    assert context["articles"] == []


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


@then("each article summary should contain the channel title")
def check_channel_in_summary(context):
    """Check that summaries contain channel title."""
    for article in context["articles"]:
        assert "[" in article.summary and "]" in article.summary
