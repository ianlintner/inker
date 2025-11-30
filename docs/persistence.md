# Persistence Layer

This document describes the modular persistence layer for storing jobs, blog posts, approval status, and historical statistics.

## Overview

The persistence layer provides a unified storage interface with support for multiple backends:

- **SQLite**: Default file-based storage for local development and simple deployments
- **PostgreSQL**: Production-ready storage for scalable deployments
- **Vector Storage**: Extensible architecture for future vector database support

```mermaid
flowchart TB
    subgraph Application["Application Layer"]
        JOB[JobService]
        API[REST API]
    end
    
    subgraph Storage["Storage Layer"]
        FACTORY[create_storage]
        BASE[StorageBackend]
        SQLITE[SQLiteStorage]
        PG[PostgresStorage]
        VECTOR[VectorStorage...]
    end
    
    subgraph Data["Data Layer"]
        SQLITE_DB[(SQLite File)]
        PG_DB[(PostgreSQL)]
        VEC_DB[(Vector DB)]
    end
    
    JOB & API --> FACTORY
    FACTORY --> BASE
    BASE --> SQLITE & PG & VECTOR
    SQLITE --> SQLITE_DB
    PG --> PG_DB
    VECTOR --> VEC_DB
```

## Quick Start

### Basic Usage

```python
from ai_blogger.persistence import create_storage, BlogPostCreate

# Auto-detect storage based on environment
storage = create_storage()

# Create a blog post
post = storage.create_post(BlogPostCreate(
    title="Introduction to AI",
    content="# AI Basics\n\nAI is transforming...",
    topic="AI development",
    sources=["https://example.com"],
    job_id="job-123",
))

# Approve the post
storage.approve_post(post.id, feedback="Excellent content!")

# Publish the post
storage.publish_post(post.id)
```

### Environment Configuration

```bash
# Use PostgreSQL (production)
export DATABASE_URL="postgresql://user:pass@localhost/inker"

# Use SQLite (development, default)
export INKER_DB_PATH="./data/inker.db"
```

## Storage Models

### BlogPost

The primary model for storing blog posts with full lifecycle tracking.

```python
class BlogPost(BaseModel):
    id: str                           # Unique identifier
    title: str                        # Blog post title
    content: str                      # Full markdown content
    word_count: int                   # Word count
    topic: str                        # Main topic
    sources: List[str]                # Source URLs
    job_id: Optional[str]             # Associated job ID
    approval_status: ApprovalStatus   # Current approval state
    approval_feedback: Optional[str]  # Reviewer feedback
    scoring: Optional[Dict]           # Scoring data
    metadata: Optional[Dict]          # Additional data
    created_at: datetime              # Creation time
    updated_at: datetime              # Last update time
    approved_at: Optional[datetime]   # Approval time
    published_at: Optional[datetime]  # Publication time
```

### ApprovalStatus

Blog post approval workflow states:

| Status | Description |
|--------|-------------|
| `PENDING` | Awaiting review |
| `APPROVED` | Approved for publication |
| `REJECTED` | Rejected, will not be published |
| `REVISION_REQUESTED` | Needs revision before approval |

### JobHistoryEntry

Tracks all actions on jobs and posts for audit trail.

```python
class JobHistoryEntry(BaseModel):
    id: str                           # Entry ID
    job_id: str                       # Related job
    post_id: Optional[str]            # Related post
    action: str                       # Action type
    previous_status: Optional[str]    # Previous state
    new_status: Optional[str]         # New state
    actor: Optional[str]              # Who performed action
    feedback: Optional[str]           # Action feedback
    metadata: Optional[Dict]          # Additional data
    created_at: datetime              # When action occurred
```

### JobStats

Aggregated statistics for monitoring and reporting.

```python
class JobStats(BaseModel):
    total_jobs: int
    pending_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_posts: int
    pending_approval: int
    approved_posts: int
    rejected_posts: int
    revision_requested: int
    published_posts: int
    avg_approval_time_hours: Optional[float]
    approval_rate: Optional[float]
```

## API Contract

The `StorageBackend` abstract base class defines the contract for all storage implementations:

### Blog Post Operations

```python
class StorageBackend(ABC):
    def create_post(self, post: BlogPostCreate) -> BlogPost: ...
    def get_post(self, post_id: str) -> Optional[BlogPost]: ...
    def get_post_by_job_id(self, job_id: str) -> Optional[BlogPost]: ...
    def update_post(self, post_id: str, update: BlogPostUpdate) -> Optional[BlogPost]: ...
    def delete_post(self, post_id: str) -> bool: ...
    def list_posts(
        self,
        approval_status: Optional[ApprovalStatus] = None,
        topic: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BlogPost]: ...
```

### Approval Workflow

```python
def approve_post(
    self, post_id: str, feedback: Optional[str] = None, actor: Optional[str] = None
) -> Optional[BlogPost]: ...

def reject_post(
    self, post_id: str, feedback: str, actor: Optional[str] = None
) -> Optional[BlogPost]: ...

def request_revision(
    self, post_id: str, feedback: str, actor: Optional[str] = None
) -> Optional[BlogPost]: ...

def publish_post(self, post_id: str) -> Optional[BlogPost]: ...
```

### History Tracking

```python
def add_history_entry(
    self,
    job_id: str,
    action: str,
    post_id: Optional[str] = None,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    actor: Optional[str] = None,
    feedback: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> JobHistoryEntry: ...

def get_job_history(self, job_id: str) -> List[JobHistoryEntry]: ...
def get_post_history(self, post_id: str) -> List[JobHistoryEntry]: ...
```

### Statistics & Health

```python
def get_stats(self) -> JobStats: ...
def health_check(self) -> bool: ...
```

## Storage Backends

### SQLite (Default)

File-based storage, ideal for development and simple deployments.

```python
from ai_blogger.persistence import create_storage

# Explicit configuration
storage = create_storage(
    backend_type="sqlite",
    db_path="./data/inker.db",
)

# Or via environment
# export INKER_DB_PATH="./data/inker.db"
storage = create_storage()
```

**Features:**
- Thread-safe with connection pooling
- Auto-migration on initialization
- No external dependencies

### PostgreSQL

Production-ready storage with connection pooling.

```python
from ai_blogger.persistence import create_storage

# Explicit configuration
storage = create_storage(
    backend_type="postgres",
    connection_string="postgresql://user:pass@localhost/inker",
    pool_size=10,
)

# Or via environment
# export DATABASE_URL="postgresql://user:pass@localhost/inker"
storage = create_storage()
```

**Features:**
- Connection pooling
- Native JSONB support
- Enum types for approval status
- Efficient indexing

**Requirements:**
```bash
pip install psycopg2-binary
```

## Database Schema

### blog_posts Table

| Column | Type | Description |
|--------|------|-------------|
| id | UUID/TEXT | Primary key |
| title | TEXT | Post title |
| content | TEXT | Full content |
| word_count | INTEGER | Word count |
| topic | TEXT | Main topic |
| sources | JSONB/TEXT | Source URLs (JSON) |
| job_id | TEXT | Related job ID |
| approval_status | ENUM/TEXT | Current status |
| approval_feedback | TEXT | Reviewer feedback |
| scoring | JSONB/TEXT | Scoring data |
| metadata | JSONB/TEXT | Additional data |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update |
| approved_at | TIMESTAMP | Approval time |
| published_at | TIMESTAMP | Publication time |

### job_history Table

| Column | Type | Description |
|--------|------|-------------|
| id | UUID/TEXT | Primary key |
| job_id | TEXT | Related job |
| post_id | UUID/TEXT | Related post |
| action | TEXT | Action type |
| previous_status | TEXT | Previous state |
| new_status | TEXT | New state |
| actor | TEXT | Who performed |
| feedback | TEXT | Action notes |
| metadata | JSONB/TEXT | Additional data |
| created_at | TIMESTAMP | When occurred |

## Migrations

Both backends support auto-migration via the `auto_migrate` config option (default: `True`).

### Schema Versioning

```python
# Check/run migrations manually
from ai_blogger.persistence import SQLiteStorage, StorageConfig

config = StorageConfig(
    backend_type="sqlite",
    db_path="./data/inker.db",
    auto_migrate=False,  # Don't auto-migrate
)
storage = SQLiteStorage(config)

# Manual initialization
storage.initialize()
```

Migrations are tracked in the `schema_version` table.

## Extending Storage

To add a new storage backend:

1. Create a new class that inherits from `StorageBackend`
2. Implement all abstract methods
3. Register in the factory

```python
from ai_blogger.persistence import StorageBackend, StorageConfig

class VectorStorage(StorageBackend):
    """Vector database storage backend."""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        # Initialize vector DB connection
        
    def initialize(self) -> None:
        # Create collections/indexes
        pass
        
    def create_post(self, post: BlogPostCreate) -> BlogPost:
        # Store post with embeddings
        pass
    
    # ... implement remaining methods
```

## Example Workflows

### Blog Post Lifecycle

```python
from ai_blogger.persistence import create_storage, BlogPostCreate, ApprovalStatus

storage = create_storage()

# 1. Create post from job result
post = storage.create_post(BlogPostCreate(
    title="AI Trends 2024",
    content="# AI Trends\n\n...",
    topic="AI development",
    job_id="job-abc123",
    scoring={"total": 8.5, "relevance": 9.0},
))

# 2. Review workflow
storage.request_revision(post.id, "Please add more examples", actor="reviewer-1")

# 3. Update post
storage.update_post(post.id, BlogPostUpdate(
    content="# AI Trends\n\n(Updated with examples)..."
))

# 4. Approve
storage.approve_post(post.id, feedback="Excellent revision!", actor="reviewer-1")

# 5. Publish
storage.publish_post(post.id)

# 6. View history
history = storage.get_post_history(post.id)
for entry in history:
    print(f"{entry.action}: {entry.feedback}")
```

### Monitoring Statistics

```python
from ai_blogger.persistence import create_storage

storage = create_storage()
stats = storage.get_stats()

print(f"Total posts: {stats.total_posts}")
print(f"Pending approval: {stats.pending_approval}")
if stats.approval_rate is not None:
    print(f"Approval rate: {stats.approval_rate:.1f}%")
else:
    print("Approval rate: N/A")
if stats.avg_approval_time_hours is not None:
    print(f"Avg approval time: {stats.avg_approval_time_hours:.1f} hours")
else:
    print("Avg approval time: N/A")
```

## See Also

- [Architecture](architecture.md) - System design overview
- [API Reference](api-reference.md) - Detailed module documentation
- [Developer Guide](developer-guide.md) - Extension guide
