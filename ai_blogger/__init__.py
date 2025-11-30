"""AI Blogger package.

Requires Python 3.9 or higher.
"""

from .chains import generate_candidates, refine_winner, score_candidates
from .config import LLM_MODEL_NAME, SOURCE_DEFAULTS, TOPICS
from .feedback_api import FeedbackService
from .feedback_models import (
    ApprovalRequest,
    FeedbackCategory,
    FeedbackEntry,
    FeedbackRating,
    FeedbackResponse,
    FeedbackStats,
    RejectionRequest,
    RevisionRequest,
)
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
from .job_api import JobService
from .job_models import (
    Job,
    JobError,
    JobRequest,
    JobResult,
    JobStatus,
    JobStatusResponse,
    JobSubmitResponse,
    MarkdownPreview,
    ScoringInfo,
)
from .job_store import JobStore
from .models import Article, CandidatePost, PostScore, ScoredPost
from .persistence import (
    ApprovalStatus,
    BlogPost,
    BlogPostCreate,
    BlogPostUpdate,
    JobHistoryEntry,
    JobStats,
    SQLiteStorage,
    StorageBackend,
    StorageConfig,
    create_storage,
    get_storage_type,
)
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
    # Job API
    "JobService",
    "JobStore",
    "Job",
    "JobRequest",
    "JobStatus",
    "JobResult",
    "JobError",
    "JobSubmitResponse",
    "JobStatusResponse",
    "MarkdownPreview",
    "ScoringInfo",
    # Persistence Layer
    "StorageBackend",
    "StorageConfig",
    "create_storage",
    "get_storage_type",
    "ApprovalStatus",
    "BlogPost",
    "BlogPostCreate",
    "BlogPostUpdate",
    "JobHistoryEntry",
    "JobStats",
    "SQLiteStorage",
    # Feedback API
    "FeedbackService",
    "ApprovalRequest",
    "RejectionRequest",
    "RevisionRequest",
    "FeedbackCategory",
    "FeedbackRating",
    "FeedbackEntry",
    "FeedbackStats",
    "FeedbackResponse",
    # Utils
    "generate_filename",
    "get_date_string",
    "get_timestamp",
    "slugify",
]
