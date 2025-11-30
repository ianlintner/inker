"""Persistence models for blog posts, jobs, and historical stats.

These models extend the job models to support approval workflows,
blog post persistence, and historical tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """Approval status for a blog post."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class BlogPostCreate(BaseModel):
    """Input model for creating a new blog post.

    Attributes:
        title: Blog post title.
        content: Full markdown content.
        topic: Main topic of the post.
        sources: List of source URLs used.
        job_id: Optional associated job ID.
        scoring: Optional scoring data.
        metadata: Optional additional metadata.
    """

    title: str
    content: str
    topic: str
    sources: List[str] = Field(default_factory=list)
    job_id: Optional[str] = None
    scoring: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class BlogPostUpdate(BaseModel):
    """Input model for updating an existing blog post.

    All fields are optional - only provided fields will be updated.
    """

    title: Optional[str] = None
    content: Optional[str] = None
    topic: Optional[str] = None
    sources: Optional[List[str]] = None
    approval_status: Optional[ApprovalStatus] = None
    approval_feedback: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BlogPost(BaseModel):
    """A persisted blog post with full state.

    Attributes:
        id: Unique identifier for the blog post.
        title: Blog post title.
        content: Full markdown content.
        word_count: Word count of the content.
        topic: Main topic of the post.
        sources: List of source URLs used.
        job_id: Optional associated job ID.
        approval_status: Current approval status.
        approval_feedback: Feedback from approval/rejection.
        scoring: Scoring data from generation.
        metadata: Additional metadata.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        approved_at: Approval timestamp.
        published_at: Publication timestamp.
    """

    id: str
    title: str
    content: str
    word_count: int
    topic: str
    sources: List[str] = Field(default_factory=list)
    job_id: Optional[str] = None
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_feedback: Optional[str] = None
    scoring: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None


class JobHistoryEntry(BaseModel):
    """A historical entry for job status changes and actions.

    Used for tracking the history of actions on jobs and blog posts.

    Attributes:
        id: Unique identifier for the history entry.
        job_id: The job ID this entry relates to.
        post_id: Optional blog post ID this entry relates to.
        action: The action that occurred (status_change, approved, rejected, etc).
        previous_status: Previous status before the action.
        new_status: New status after the action.
        actor: Optional identifier for who performed the action.
        feedback: Optional feedback or notes.
        metadata: Additional context.
        created_at: When this action occurred.
    """

    id: str
    job_id: str
    post_id: Optional[str] = None
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    actor: Optional[str] = None
    feedback: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class JobStats(BaseModel):
    """Aggregated statistics for jobs and blog posts.

    Attributes:
        total_jobs: Total number of jobs.
        pending_jobs: Jobs in pending state.
        completed_jobs: Successfully completed jobs.
        failed_jobs: Failed jobs.
        total_posts: Total blog posts generated.
        pending_approval: Posts awaiting approval.
        approved_posts: Approved posts.
        rejected_posts: Rejected posts.
        revision_requested: Posts with revision requests.
        published_posts: Published posts.
        avg_approval_time_hours: Average time to approval in hours.
        approval_rate: Percentage of posts approved.
    """

    total_jobs: int = 0
    pending_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    total_posts: int = 0
    pending_approval: int = 0
    approved_posts: int = 0
    rejected_posts: int = 0
    revision_requested: int = 0
    published_posts: int = 0
    avg_approval_time_hours: Optional[float] = None
    approval_rate: Optional[float] = None
