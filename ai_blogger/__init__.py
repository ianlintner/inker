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
from .queue import (
    MemoryQueue,
    QueueBackend,
    QueueConfig,
    QueueJob,
    QueueJobCreate,
    QueueJobStatus,
    QueueJobUpdate,
    QueueStats,
    create_queue,
    get_queue_type,
)
from .utils import generate_filename, get_date_string, get_timestamp, slugify

# Metrics and Observability
from .metrics import (
    OPENTELEMETRY_AVAILABLE,
    PROMETHEUS_AVAILABLE,
    get_tracer,
    record_approval_action,
    record_job_status_change,
    record_job_submission,
    record_queue_complete,
    record_queue_dequeue,
    record_queue_enqueue,
    record_queue_fail,
    set_system_info,
    track_api_request,
    track_job_execution,
    track_storage_operation,
    traced,
    update_queue_size,
)

# Conditional import for Frontend API (requires fastapi)
try:
    from .frontend_api import (
        configure_services,
        create_app,
        reset_services,
        router,
    )

    _FRONTEND_API_AVAILABLE = True
except ImportError:
    # FastAPI not installed
    configure_services = None  # type: ignore
    create_app = None  # type: ignore
    reset_services = None  # type: ignore
    router = None  # type: ignore
    _FRONTEND_API_AVAILABLE = False

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
    # Queue Layer
    "QueueBackend",
    "QueueConfig",
    "create_queue",
    "get_queue_type",
    "QueueJob",
    "QueueJobCreate",
    "QueueJobStatus",
    "QueueJobUpdate",
    "QueueStats",
    "MemoryQueue",
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
    # Frontend API (optional - requires fastapi)
    "create_app",
    "router",
    "configure_services",
    "reset_services",
    # Utils
    "generate_filename",
    "get_date_string",
    "get_timestamp",
    "slugify",
    # Metrics and Observability
    "PROMETHEUS_AVAILABLE",
    "OPENTELEMETRY_AVAILABLE",
    "get_tracer",
    "traced",
    "track_job_execution",
    "track_storage_operation",
    "track_api_request",
    "record_job_submission",
    "record_job_status_change",
    "record_approval_action",
    "record_queue_enqueue",
    "record_queue_dequeue",
    "record_queue_complete",
    "record_queue_fail",
    "update_queue_size",
    "set_system_info",
]
