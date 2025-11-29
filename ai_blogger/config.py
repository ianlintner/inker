"""Configuration settings for the AI Blogger."""

from typing import List

# Topics to search for
TOPICS: List[str] = [
    "AI software engineering",
    "agentic AI development",
    "Copilot coding assistants",
    "developer productivity",
    "software engineering leadership",
    "cybersecurity",
    "AI security",
    "dev tools",
    "cloud infrastructure",
]

# Scoring weights for candidate posts
SCORING_WEIGHTS = {
    "relevance": 0.3,
    "originality": 0.25,
    "depth": 0.2,
    "clarity": 0.15,
    "engagement": 0.1,
}

# Maximum age for YouTube videos (in days)
YOUTUBE_MAX_AGE_DAYS: int = 7

# Default number of results per source
DEFAULT_HN_RESULTS: int = 10
DEFAULT_WEB_RESULTS: int = 5
DEFAULT_YOUTUBE_RESULTS: int = 5

# Number of candidate posts to generate
DEFAULT_NUM_CANDIDATES: int = 3

# Output directory for blog posts
DEFAULT_OUTPUT_DIR: str = "./posts"
