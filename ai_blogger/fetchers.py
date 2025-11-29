"""Fetchers for various news sources."""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from tavily import TavilyClient

from .config import (
    DEFAULT_HN_RESULTS,
    DEFAULT_WEB_RESULTS,
    DEFAULT_YOUTUBE_RESULTS,
    TOPICS,
    YOUTUBE_MAX_AGE_DAYS,
)
from .models import Article


def fetch_hacker_news_articles(
    topic: str, max_results: int = DEFAULT_HN_RESULTS
) -> List[Article]:
    """Fetch articles from Hacker News related to a topic.

    Args:
        topic: The topic to search for.
        max_results: Maximum number of results to return.

    Returns:
        List of Article objects from Hacker News.
    """
    articles = []

    # Use Hacker News Algolia API for search
    url = "https://hn.algolia.com/api/v1/search"
    params = {"query": topic, "hitsPerPage": max_results, "tags": "story"}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        for hit in data.get("hits", []):
            title = hit.get("title", "")
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

            # Skip if no title
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
        print(f"Error fetching Hacker News articles: {e}")

    return articles


def fetch_web_search_articles(
    topic: str, max_results: int = DEFAULT_WEB_RESULTS
) -> List[Article]:
    """Fetch articles from web search using Tavily.

    Args:
        topic: The topic to search for.
        max_results: Maximum number of results to return.

    Returns:
        List of Article objects from web search.
    """
    articles = []
    api_key = os.environ.get("TAVILY_API_KEY")

    if not api_key:
        print("Warning: TAVILY_API_KEY not set, skipping web search")
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
    except Exception as e:
        print(f"Error fetching web search articles: {e}")

    return articles


def fetch_youtube_trending_videos(
    query: str, max_results: int = DEFAULT_YOUTUBE_RESULTS
) -> List[Article]:
    """Fetch trending YouTube videos related to a topic.

    Uses the YouTube Data API v3 to search for recent videos.
    Filters out videos older than 7 days.

    Args:
        query: The search query (topic).
        max_results: Maximum number of results to return.

    Returns:
        List of Article objects representing YouTube videos.
    """
    articles = []
    api_key = os.environ.get("YOUTUBE_API_KEY")

    if not api_key:
        print("Warning: YOUTUBE_API_KEY not set, skipping YouTube search")
        return articles

    # Calculate date threshold for filtering
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=YOUTUBE_MAX_AGE_DAYS)

    # YouTube Data API v3 search endpoint
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{query} software engineering",
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

            # Parse published date
            published_at_str = snippet.get("publishedAt", "")
            if published_at_str:
                try:
                    published_at = datetime.fromisoformat(
                        published_at_str.replace("Z", "+00:00")
                    )
                    # Double-check the video is within the allowed age
                    if published_at < cutoff_date:
                        continue
                except ValueError as e:
                    print(f"Warning: Could not parse date '{published_at_str}': {e}")

            title = snippet.get("title", "")
            description = snippet.get("description", "")[:500]
            channel_title = snippet.get("channelTitle", "")
            thumbnail = (
                snippet.get("thumbnails", {}).get("high", {}).get("url")
                or snippet.get("thumbnails", {}).get("default", {}).get("url")
            )

            # Skip if title is empty
            if not title:
                continue

            # Create summary with channel info
            summary = f"[{channel_title}] {description}"

            article = Article(
                title=title,
                url=f"https://www.youtube.com/watch?v={video_id}",
                source="youtube",
                summary=summary,
                topic=query,
                thumbnail=thumbnail,
            )
            articles.append(article)
    except requests.RequestException as e:
        print(f"Error fetching YouTube videos: {e}")

    return articles


def fetch_all_articles(
    topics: Optional[List[str]] = None,
    hn_results: int = DEFAULT_HN_RESULTS,
    web_results: int = DEFAULT_WEB_RESULTS,
    youtube_results: int = DEFAULT_YOUTUBE_RESULTS,
) -> List[Article]:
    """Fetch articles from all sources for the given topics.

    Args:
        topics: List of topics to search for. Defaults to config topics.
        hn_results: Max results per topic from Hacker News.
        web_results: Max results per topic from web search.
        youtube_results: Max results per topic from YouTube.

    Returns:
        Combined list of Article objects from all sources.
    """
    if topics is None:
        topics = TOPICS

    all_articles: List[Article] = []

    for topic in topics:
        print(f"Fetching articles for topic: {topic}")

        # Fetch from Hacker News
        hn = fetch_hacker_news_articles(topic, max_results=hn_results)
        print(f"  - Hacker News: {len(hn)} articles")

        # Fetch from web search
        web = fetch_web_search_articles(topic, max_results=web_results)
        print(f"  - Web search: {len(web)} articles")

        # Fetch from YouTube
        youtube = fetch_youtube_trending_videos(topic, max_results=youtube_results)
        print(f"  - YouTube: {len(youtube)} videos")

        # Combine all articles
        all_articles.extend(hn + web + youtube)

    print(f"Total articles fetched: {len(all_articles)}")
    return all_articles
