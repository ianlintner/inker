"""Feedback models for the Blog Post Approval/Rejection API.

These models support editor feedback, approval workflows, and learning
from editorial outcomes to improve future blog post generation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FeedbackCategory(str, Enum):
    """Categories for editorial feedback.

    Used to classify the nature of feedback for learning purposes.
    """

    QUALITY = "quality"  # Overall quality issues
    RELEVANCE = "relevance"  # Topic/content relevance
    ACCURACY = "accuracy"  # Factual accuracy concerns
    CLARITY = "clarity"  # Writing clarity issues
    ENGAGEMENT = "engagement"  # Reader engagement concerns
    LENGTH = "length"  # Content length issues
    STYLE = "style"  # Writing style feedback
    SOURCES = "sources"  # Source quality/citation issues
    OTHER = "other"  # Miscellaneous feedback


class FeedbackRating(BaseModel):
    """Structured rating for a specific aspect of a blog post.

    Attributes:
        category: The aspect being rated.
        score: Rating score (1-5 scale).
        comment: Optional comment explaining the rating.
    """

    category: FeedbackCategory
    score: int = Field(ge=1, le=5, description="Rating score from 1 (poor) to 5 (excellent)")
    comment: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request to approve a blog post.

    Attributes:
        post_id: The blog post identifier.
        feedback: Optional general feedback comment.
        ratings: Optional structured ratings for different aspects.
        actor: Optional identifier for who is approving.
    """

    post_id: str
    feedback: Optional[str] = None
    ratings: List[FeedbackRating] = Field(default_factory=list)
    actor: Optional[str] = None


class RejectionRequest(BaseModel):
    """Request to reject a blog post.

    Attributes:
        post_id: The blog post identifier.
        feedback: Required feedback explaining rejection reason.
        categories: Categories of issues identified.
        ratings: Optional structured ratings for different aspects.
        actor: Optional identifier for who is rejecting.
    """

    post_id: str
    feedback: str
    categories: List[FeedbackCategory] = Field(default_factory=list)
    ratings: List[FeedbackRating] = Field(default_factory=list)
    actor: Optional[str] = None


class RevisionRequest(BaseModel):
    """Request for revision of a blog post.

    Attributes:
        post_id: The blog post identifier.
        feedback: Required feedback explaining what needs revision.
        categories: Categories of issues to address.
        ratings: Optional structured ratings for different aspects.
        actor: Optional identifier for who is requesting revision.
    """

    post_id: str
    feedback: str
    categories: List[FeedbackCategory] = Field(default_factory=list)
    ratings: List[FeedbackRating] = Field(default_factory=list)
    actor: Optional[str] = None


class FeedbackEntry(BaseModel):
    """A feedback entry capturing editorial input for learning.

    This model captures detailed feedback to enable learning from
    what gets approved/rejected and why.

    Attributes:
        id: Unique identifier for the feedback entry.
        post_id: The blog post this feedback is for.
        job_id: The associated job ID.
        action: The action taken (approved, rejected, revision_requested).
        feedback: General feedback comment.
        categories: Categories of feedback (for rejected/revision posts).
        ratings: Structured ratings for different aspects.
        actor: Who provided the feedback.
        post_scoring: Original post scoring from generation.
        post_topic: Topic of the post (for learning patterns).
        post_word_count: Word count of the post.
        created_at: When the feedback was created.
    """

    id: str
    post_id: str
    job_id: Optional[str] = None
    action: str
    feedback: Optional[str] = None
    categories: List[FeedbackCategory] = Field(default_factory=list)
    ratings: List[FeedbackRating] = Field(default_factory=list)
    actor: Optional[str] = None
    post_scoring: Optional[Dict[str, Any]] = None
    post_topic: Optional[str] = None
    post_word_count: Optional[int] = None
    created_at: datetime


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics for learning.

    Provides insights into approval patterns to inform future
    content generation improvements.

    Attributes:
        total_feedback: Total number of feedback entries.
        approvals: Number of approvals.
        rejections: Number of rejections.
        revisions: Number of revision requests.
        approval_rate: Percentage of posts approved.
        avg_quality_score: Average quality rating.
        avg_relevance_score: Average relevance rating.
        avg_clarity_score: Average clarity rating.
        avg_engagement_score: Average engagement rating.
        common_rejection_categories: Most common rejection categories.
        avg_time_to_decision_hours: Average time from post creation to decision.
        feedback_by_topic: Breakdown of approval rates by topic.
    """

    total_feedback: int = 0
    approvals: int = 0
    rejections: int = 0
    revisions: int = 0
    approval_rate: Optional[float] = None
    avg_quality_score: Optional[float] = None
    avg_relevance_score: Optional[float] = None
    avg_clarity_score: Optional[float] = None
    avg_engagement_score: Optional[float] = None
    common_rejection_categories: List[str] = Field(default_factory=list)
    avg_time_to_decision_hours: Optional[float] = None
    feedback_by_topic: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    """Response after providing feedback on a blog post.

    Attributes:
        success: Whether the operation succeeded.
        post_id: The blog post identifier.
        new_status: The new approval status of the post.
        feedback_id: The ID of the created feedback entry.
        message: Status message.
    """

    success: bool
    post_id: str
    new_status: str
    feedback_id: str
    message: str
