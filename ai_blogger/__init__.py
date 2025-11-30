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
from .job_models import (
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
    BlogPostJob,
    EditorComment,
    HistoricalJobsResponse,
    JobPreview,
    JobResponse,
    JobStats,
    JobStatus,
    JobSubmission,
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
    # Job models (Phase 2)
    "BlogPostJob",
    "JobStatus",
    "ApprovalStatus",
    "JobSubmission",
    "JobResponse",
    "JobPreview",
    "ApprovalRequest",
    "ApprovalRecord",
    "EditorComment",
    "JobStats",
    "HistoricalJobsResponse",
    # Utils
    "generate_filename",
    "get_date_string",
    "get_timestamp",
    "slugify",
]
