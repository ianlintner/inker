"""AI Blogger package.

Requires Python 3.9 or higher.
"""

from .chains import generate_candidates, refine_winner, score_candidates
from .config import LLM_MODEL_NAME, SOURCE_DEFAULTS, TOPICS
from .fetchers import (
    BaseFetcher,
    fetch_all_articles,
    fetch_hacker_news_articles,
    fetch_web_search_articles,
    fetch_youtube_trending_videos,
    get_available_sources,
    get_fetcher,
    register_fetcher,
)
from .models import Article, CandidatePost, PostScore, ScoredPost
from .utils import generate_filename, get_date_string, get_timestamp, slugify

__all__ = [
    # Chains
    "generate_candidates",
    "refine_winner",
    "score_candidates",
    # Config
    "LLM_MODEL_NAME",
    "SOURCE_DEFAULTS",
    "TOPICS",
    # Fetchers (modular API)
    "BaseFetcher",
    "register_fetcher",
    "get_fetcher",
    "get_available_sources",
    # Fetchers (legacy functions)
    "fetch_all_articles",
    "fetch_hacker_news_articles",
    "fetch_web_search_articles",
    "fetch_youtube_trending_videos",
    # Models
    "Article",
    "CandidatePost",
    "PostScore",
    "ScoredPost",
    # Utils
    "generate_filename",
    "get_date_string",
    "get_timestamp",
    "slugify",
]
