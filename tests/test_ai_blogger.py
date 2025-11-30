"""Tests for the AI Blogger package."""

import pytest


def test_imports():
    """Test that all modules can be imported."""
    from ai_blogger import (
        Article,
        BaseFetcher,
        CandidatePost,
        PostScore,
        ScoredPost,
        TOPICS,
        fetch_all_articles,
        generate_filename,
        get_available_sources,
        get_date_string,
        get_fetcher,
        get_timestamp,
        register_fetcher,
        slugify,
    )
    assert True


def test_get_available_sources():
    """Test that get_available_sources returns expected sources."""
    from ai_blogger import get_available_sources

    sources = get_available_sources()
    assert isinstance(sources, list)
    assert "hacker_news" in sources
    assert "web" in sources
    assert "youtube" in sources


def test_get_fetcher():
    """Test that get_fetcher returns correct fetcher instances."""
    from ai_blogger import get_fetcher

    hn_fetcher = get_fetcher("hacker_news")
    assert hn_fetcher is not None
    assert hn_fetcher.name == "hacker_news"

    web_fetcher = get_fetcher("web")
    assert web_fetcher is not None
    assert web_fetcher.name == "web"

    youtube_fetcher = get_fetcher("youtube")
    assert youtube_fetcher is not None
    assert youtube_fetcher.name == "youtube"

    unknown_fetcher = get_fetcher("unknown_source")
    assert unknown_fetcher is None


def test_slugify():
    """Test slugify function."""
    from ai_blogger import slugify

    assert slugify("Hello World") == "hello-world"
    assert slugify("Hello World! 123") == "hello-world-123"
    assert slugify("AI & Machine Learning") == "ai-machine-learning"


def test_generate_filename():
    """Test filename generation."""
    from ai_blogger import generate_filename

    filename = generate_filename("My Blog Post Title")
    assert filename.endswith(".md")
    assert "my-blog-post-title" in filename
    # Should have date prefix
    assert len(filename.split("-")) >= 4  # YYYY-MM-DD-slug.md


def test_get_date_string():
    """Test date string format."""
    from ai_blogger import get_date_string
    import re

    date_str = get_date_string()
    # Should match YYYY-MM-DD format
    assert re.match(r"\d{4}-\d{2}-\d{2}", date_str)


def test_get_timestamp():
    """Test timestamp format."""
    from ai_blogger import get_timestamp

    timestamp = get_timestamp()
    assert "T" in timestamp  # ISO format has T separator


def test_article_model():
    """Test Article model creation."""
    from ai_blogger import Article

    article = Article(
        title="Test Article",
        url="https://example.com/article",
        source="test",
        summary="This is a test summary",
        topic="testing",
    )
    assert article.title == "Test Article"
    assert article.source == "test"
    assert article.topic == "testing"


def test_candidate_post_model():
    """Test CandidatePost model creation."""
    from ai_blogger import CandidatePost

    post = CandidatePost(
        title="Test Post",
        content="Test content",
        sources=["https://example.com"],
        topic="testing",
    )
    assert post.title == "Test Post"
    assert len(post.sources) == 1


def test_post_score_model():
    """Test PostScore model creation."""
    from ai_blogger import PostScore

    score = PostScore(
        relevance=8.0,
        originality=7.0,
        depth=9.0,
        clarity=8.5,
        engagement=7.5,
        total=8.0,
        reasoning="Good post",
    )
    assert score.total == 8.0
    assert score.relevance == 8.0


def test_scored_post_model():
    """Test ScoredPost model creation."""
    from ai_blogger import CandidatePost, PostScore, ScoredPost

    candidate = CandidatePost(
        title="Test",
        content="Content",
        sources=[],
        topic="test",
    )
    score = PostScore(
        relevance=8.0,
        originality=7.0,
        depth=9.0,
        clarity=8.5,
        engagement=7.5,
        total=8.0,
        reasoning="Good",
    )
    scored = ScoredPost(candidate=candidate, score=score)
    assert scored.candidate.title == "Test"
    assert scored.score.total == 8.0


def test_fetcher_input_validation():
    """Test that fetchers validate inputs."""
    from ai_blogger import get_fetcher

    fetcher = get_fetcher("hacker_news")

    with pytest.raises(ValueError, match="Topic cannot be empty"):
        fetcher._validate_inputs("", 5)

    with pytest.raises(ValueError, match="max_results must be positive"):
        fetcher._validate_inputs("test", 0)

    with pytest.raises(ValueError, match="max_results must be positive"):
        fetcher._validate_inputs("test", -1)

    # Valid inputs should not raise
    fetcher._validate_inputs("test topic", 10)


def test_topics_configuration():
    """Test that TOPICS is configured correctly."""
    from ai_blogger import TOPICS

    assert isinstance(TOPICS, list)
    assert len(TOPICS) > 0
    assert all(isinstance(topic, str) for topic in TOPICS)
