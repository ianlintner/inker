"""Pydantic models for the AI Blogger."""

from typing import Optional
from pydantic import BaseModel, HttpUrl


class Article(BaseModel):
    """Represents a news article or video from various sources."""

    title: str
    url: HttpUrl
    source: str  # e.g., "hacker_news", "web", "youtube"
    summary: str
    topic: str
    thumbnail: Optional[str] = None  # Optional thumbnail URL for YouTube videos


class CandidatePost(BaseModel):
    """Represents a draft blog post candidate."""

    title: str
    content: str
    sources: list[str]
    topic: str


class PostScore(BaseModel):
    """Scoring breakdown for a candidate post."""

    relevance: float
    originality: float
    depth: float
    clarity: float
    engagement: float
    total: float
    reasoning: str


class ScoredPost(BaseModel):
    """A candidate post with its score."""

    candidate: CandidatePost
    score: PostScore
