"""Fetchers for various news sources.

This module provides a modular, extensible architecture for fetching articles
from multiple sources. New sources can be added by:

1. Creating a new fetcher class that inherits from BaseFetcher
2. Registering it with the @register_fetcher decorator

Example:
    @register_fetcher("my_source")
    class MySourceFetcher(BaseFetcher):
        name = "my_source"
        env_key = "MY_SOURCE_API_KEY"  # Optional

        def fetch(self, topic: str, max_results: int) -> List[Article]:
            # Implementation here
            pass

Note:
    API keys should be properly secured. For services like YouTube Data API,
    consider restricting API keys in the Google Cloud Console by:
    - IP address restrictions for server-side use
    - HTTP referrer restrictions for client-side use
    This prevents unauthorized use if keys are accidentally exposed in logs.

    Be mindful of API quotas when fetching from multiple topics and sources.
    YouTube Data API has a default quota of 10,000 units/day. Each search
    request costs 100 units.
"""

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Type

import requests
from tavily import TavilyClient

from .config import (
    DEFAULT_MAX_RESULTS,
    SOURCE_DEFAULTS,
    TOPICS,
    YOUTUBE_MAX_AGE_DAYS,
)
from .models import Article

logger = logging.getLogger(__name__)


# Registry for fetcher classes
_FETCHER_REGISTRY: Dict[str, Type["BaseFetcher"]] = {}


def register_fetcher(name: str) -> Callable[[Type["BaseFetcher"]], Type["BaseFetcher"]]:
    """Decorator to register a fetcher class.

    Args:
        name: The unique identifier for this fetcher.

    Returns:
        Decorator function that registers the class.

    Example:
        @register_fetcher("my_source")
        class MySourceFetcher(BaseFetcher):
            ...
    """
    def decorator(cls: Type["BaseFetcher"]) -> Type["BaseFetcher"]:
        _FETCHER_REGISTRY[name] = cls
        return cls
    return decorator


def get_available_sources() -> List[str]:
    """Get list of all registered source names.

    Returns:
        List of registered fetcher names.
    """
    return list(_FETCHER_REGISTRY.keys())


def get_fetcher(name: str) -> Optional["BaseFetcher"]:
    """Get a fetcher instance by name.

    Args:
        name: The fetcher name to retrieve.

    Returns:
        Fetcher instance or None if not found.
    """
    fetcher_cls = _FETCHER_REGISTRY.get(name)
    if fetcher_cls:
        return fetcher_cls()
    return None


class BaseFetcher(ABC):
    """Base class for all article fetchers.

    Subclasses must implement the `fetch` method and set the `name` attribute.
    Optionally set `env_key` for API key validation.
    """

    name: str = ""
    env_key: Optional[str] = None
    description: str = ""

    def is_available(self) -> bool:
        """Check if this fetcher is available (has required API key).

        Returns:
            True if fetcher can be used, False otherwise.
        """
        if self.env_key is None:
            return True
        return bool(os.environ.get(self.env_key))

    def get_missing_key_message(self) -> str:
        """Get a warning message for missing API key.

        Returns:
            Warning message string.
        """
        if self.env_key:
            return f"Warning: {self.env_key} not set, skipping {self.name}"
        return ""

    def _validate_inputs(self, topic: str, max_results: int) -> None:
        """Validate input parameters for fetch operations.

        Args:
            topic: The topic to search for.
            max_results: Maximum number of results to return.

        Raises:
            ValueError: If topic is empty or max_results is not positive.
        """
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty")
        if max_results < 1:
            raise ValueError(f"max_results must be positive, got {max_results}")

    @abstractmethod
    def fetch(self, topic: str, max_results: int) -> List[Article]:
        """Fetch articles for a given topic.

        Args:
            topic: The topic to search for (must not be empty).
            max_results: Maximum number of results to return (must be positive).

        Returns:
            List of Article objects.

        Raises:
            ValueError: If topic is empty or max_results is not positive.
        """
        pass


@register_fetcher("hacker_news")
class HackerNewsFetcher(BaseFetcher):
    """Fetcher for Hacker News articles via Algolia API."""

    name = "hacker_news"
    env_key = None  # No API key required
    description = "Fetch articles from Hacker News"

    def fetch(self, topic: str, max_results: int) -> List[Article]:
        """Fetch articles from Hacker News related to a topic.

        Args:
            topic: The topic to search for.
            max_results: Maximum number of results to return.

        Returns:
            List of Article objects from Hacker News.
        """
        self._validate_inputs(topic, max_results)
        articles = []

        url = "https://hn.algolia.com/api/v1/search"
        params = {"query": topic, "hitsPerPage": max_results, "tags": "story"}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for hit in data.get("hits", []):
                title = hit.get("title", "")
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

                if not title:
                    continue

                article = Article(
                    title=title,
                    url=story_url,
                    source="hacker_news",
                    summary=hit.get("story_text", "") or f"Discussion on Hacker News about: {title}",
                    topic=topic,
                )
                articles.append(article)
        except requests.RequestException as e:
            logger.error(f"Error fetching Hacker News articles: {e}")

        return articles


@register_fetcher("web")
class WebSearchFetcher(BaseFetcher):
    """Fetcher for web search results via Tavily API."""

    name = "web"
    env_key = "TAVILY_API_KEY"
    description = "Fetch articles from web search (Tavily)"

    def fetch(self, topic: str, max_results: int) -> List[Article]:
        """Fetch articles from web search using Tavily.

        Args:
            topic: The topic to search for.
            max_results: Maximum number of results to return.

        Returns:
            List of Article objects from web search.
        """
        self._validate_inputs(topic, max_results)
        articles = []
        api_key = os.environ.get(self.env_key)

        if not api_key:
            logger.warning(self.get_missing_key_message())
            return articles

        try:
            client = TavilyClient(api_key=api_key)
            search_query = f"{topic} software engineering news"
            response = client.search(query=search_query, max_results=max_results)

            for result in response.get("results", []):
                article = Article(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    source="web",
                    summary=result.get("content", "")[:500],
                    topic=topic,
                )
                articles.append(article)
        except (requests.RequestException, ConnectionError, TimeoutError) as e:
            logger.error(f"Error fetching web search articles (network): {e}")
        except ValueError as e:
            logger.error(f"Error fetching web search articles (invalid response): {e}")
        except Exception as e:
            # Log unexpected errors but don't crash - allow other sources to continue
            logger.error(f"Unexpected error fetching web search articles: {type(e).__name__}: {e}")

        return articles


@register_fetcher("youtube")
class YouTubeFetcher(BaseFetcher):
    """Fetcher for trending YouTube videos via YouTube Data API v3."""

    name = "youtube"
    env_key = "YOUTUBE_API_KEY"
    description = "Fetch trending YouTube videos"

    def fetch(self, topic: str, max_results: int) -> List[Article]:
        """Fetch trending YouTube videos related to a topic.

        Uses the YouTube Data API v3 to search for recent videos.
        Filters out videos older than 7 days.

        Note:
            The YouTube API key is passed as a URL parameter, which is standard
            for the YouTube Data API. Ensure your API key is properly restricted
            in the Google Cloud Console (by IP or referrer) to prevent unauthorized
            use if logs containing URLs are exposed.

        Args:
            topic: The search query (topic).
            max_results: Maximum number of results to return.

        Returns:
            List of Article objects representing YouTube videos.
        """
        self._validate_inputs(topic, max_results)
        articles = []
        api_key = os.environ.get(self.env_key)

        if not api_key:
            logger.warning(self.get_missing_key_message())
            return articles

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=YOUTUBE_MAX_AGE_DAYS)

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": f"{topic} software engineering",
            "key": api_key,
            "type": "video",
            "order": "date",
            "maxResults": max_results,
            "relevanceLanguage": "en",
            "publishedAfter": cutoff_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")

                if not video_id:
                    continue

                published_at_str = snippet.get("publishedAt", "")
                if published_at_str:
                    try:
                        published_at = datetime.fromisoformat(
                            published_at_str.replace("Z", "+00:00")
                        )
                        if published_at < cutoff_date:
                            continue
                    except ValueError as e:
                        logger.warning(f"Could not parse date '{published_at_str}': {e}")

                title = snippet.get("title", "")
                description = snippet.get("description", "")[:500]
                channel_title = snippet.get("channelTitle", "")
                thumbnail = (
                    snippet.get("thumbnails", {}).get("high", {}).get("url")
                    or snippet.get("thumbnails", {}).get("default", {}).get("url")
                )

                if not title:
                    continue

                summary = f"[{channel_title}] {description}"

                article = Article(
                    title=title,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    source="youtube",
                    summary=summary,
                    topic=topic,
                    thumbnail=thumbnail,
                )
                articles.append(article)
        except requests.RequestException as e:
            logger.error(f"Error fetching YouTube videos: {e}")

        return articles


# Legacy function wrappers for backward compatibility
def fetch_hacker_news_articles(topic: str, max_results: int = SOURCE_DEFAULTS.get("hacker_news", DEFAULT_MAX_RESULTS)) -> List[Article]:
    """Fetch articles from Hacker News (legacy wrapper)."""
    fetcher = get_fetcher("hacker_news")
    return fetcher.fetch(topic, max_results) if fetcher else []


def fetch_web_search_articles(topic: str, max_results: int = SOURCE_DEFAULTS.get("web", DEFAULT_MAX_RESULTS)) -> List[Article]:
    """Fetch articles from web search (legacy wrapper)."""
    fetcher = get_fetcher("web")
    return fetcher.fetch(topic, max_results) if fetcher else []


def fetch_youtube_trending_videos(query: str, max_results: int = SOURCE_DEFAULTS.get("youtube", DEFAULT_MAX_RESULTS)) -> List[Article]:
    """Fetch trending YouTube videos (legacy wrapper)."""
    fetcher = get_fetcher("youtube")
    return fetcher.fetch(query, max_results) if fetcher else []


def fetch_all_articles(
    topics: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    max_results: Optional[Dict[str, int]] = None,
) -> List[Article]:
    """Fetch articles from specified sources for the given topics.

    Note:
        Be mindful of API quotas when using multiple topics and sources.
        - YouTube Data API: 10,000 units/day default, 100 units per search
        - Tavily: Check your plan limits

        For example, 9 topics × 5 results from YouTube = 9 API calls = 900 units.

    Args:
        topics: List of topics to search for. Defaults to config topics.
        sources: List of source names to use. Defaults to all registered sources.
        max_results: Dict mapping source names to max results.
                    Defaults to SOURCE_DEFAULTS.

    Returns:
        Combined list of Article objects from all sources.
    """
    if topics is None:
        topics = TOPICS

    if sources is None:
        sources = get_available_sources()

    if max_results is None:
        max_results = SOURCE_DEFAULTS.copy()

    all_articles: List[Article] = []

    for topic in topics:
        print(f"Fetching articles for topic: {topic}")

        for source_name in sources:
            fetcher = get_fetcher(source_name)
            if fetcher is None:
                print(f"  - {source_name}: Unknown source, skipping")
                continue

            if not fetcher.is_available():
                missing_msg = fetcher.get_missing_key_message()
                if missing_msg:
                    print(f"  - {source_name}: {missing_msg}")
                else:
                    print(f"  - {source_name}: Not available")
                continue

            result_count = max_results.get(source_name, DEFAULT_MAX_RESULTS)
            articles = fetcher.fetch(topic, result_count)
            print(f"  - {source_name}: {len(articles)} articles")
            all_articles.extend(articles)

    print(f"Total articles fetched: {len(all_articles)}")
    return all_articles
