"""Blog Post Feedback API service.

This module provides the API for submitting editorial feedback,
approving/rejecting blog posts, and learning from outcomes.
It integrates with the persistence layer and job history.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

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
from .persistence import (
    ApprovalStatus,
    BlogPost,
    StorageBackend,
)

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing blog post feedback and approvals.

    This service handles the approval workflow, stores editorial feedback,
    and provides learning data for future improvements.

    Attributes:
        storage: The storage backend for persistence.
    """

    def __init__(self, storage: StorageBackend):
        """Initialize the feedback service.

        Args:
            storage: The storage backend for persistence.
        """
        self.storage = storage

    def _create_feedback_entry(
        self,
        post: BlogPost,
        action: str,
        feedback: Optional[str] = None,
        categories: Optional[List[FeedbackCategory]] = None,
        ratings: Optional[List[FeedbackRating]] = None,
        actor: Optional[str] = None,
    ) -> FeedbackEntry:
        """Create a feedback entry for learning.

        Args:
            post: The blog post being reviewed.
            action: The action taken (approved, rejected, revision_requested).
            feedback: General feedback comment.
            categories: Categories of feedback.
            ratings: Structured ratings.
            actor: Who provided the feedback.

        Returns:
            The created FeedbackEntry.
        """
        feedback_id = str(uuid.uuid4())
        now = datetime.now()

        entry = FeedbackEntry(
            id=feedback_id,
            post_id=post.id,
            job_id=post.job_id,
            action=action,
            feedback=feedback,
            categories=categories or [],
            ratings=ratings or [],
            actor=actor,
            post_scoring=post.scoring,
            post_topic=post.topic,
            post_word_count=post.word_count,
            created_at=now,
        )

        # Store feedback in history with metadata
        metadata = {
            "feedback_id": feedback_id,
            "categories": [c.value for c in (categories or [])],
            "ratings": [r.model_dump() for r in (ratings or [])],
        }

        self.storage.add_history_entry(
            job_id=post.job_id or post.id,
            post_id=post.id,
            action=f"feedback_{action}",
            previous_status=post.approval_status.value,
            new_status=action,
            actor=actor,
            feedback=feedback,
            metadata=metadata,
        )

        return entry

    def approve_post(self, request: ApprovalRequest) -> FeedbackResponse:
        """Approve a blog post.

        Args:
            request: The approval request.

        Returns:
            FeedbackResponse with the result.
        """
        post = self.storage.get_post(request.post_id)
        if not post:
            logger.warning(f"Post {request.post_id} not found for approval")
            return FeedbackResponse(
                success=False,
                post_id=request.post_id,
                new_status="",
                feedback_id="",
                message=f"Post {request.post_id} not found",
            )

        # Create feedback entry for learning
        entry = self._create_feedback_entry(
            post=post,
            action="approved",
            feedback=request.feedback,
            ratings=request.ratings,
            actor=request.actor,
        )

        # Perform the approval
        updated = self.storage.approve_post(
            request.post_id,
            feedback=request.feedback,
            actor=request.actor,
        )

        if not updated:
            return FeedbackResponse(
                success=False,
                post_id=request.post_id,
                new_status=post.approval_status.value,
                feedback_id=entry.id,
                message="Failed to approve post",
            )

        logger.info(f"Post {request.post_id} approved by {request.actor or 'unknown'}")

        return FeedbackResponse(
            success=True,
            post_id=request.post_id,
            new_status=ApprovalStatus.APPROVED.value,
            feedback_id=entry.id,
            message="Post approved successfully",
        )

    def reject_post(self, request: RejectionRequest) -> FeedbackResponse:
        """Reject a blog post.

        Args:
            request: The rejection request.

        Returns:
            FeedbackResponse with the result.
        """
        post = self.storage.get_post(request.post_id)
        if not post:
            logger.warning(f"Post {request.post_id} not found for rejection")
            return FeedbackResponse(
                success=False,
                post_id=request.post_id,
                new_status="",
                feedback_id="",
                message=f"Post {request.post_id} not found",
            )

        # Create feedback entry for learning
        entry = self._create_feedback_entry(
            post=post,
            action="rejected",
            feedback=request.feedback,
            categories=request.categories,
            ratings=request.ratings,
            actor=request.actor,
        )

        # Perform the rejection
        updated = self.storage.reject_post(
            request.post_id,
            feedback=request.feedback,
            actor=request.actor,
        )

        if not updated:
            return FeedbackResponse(
                success=False,
                post_id=request.post_id,
                new_status=post.approval_status.value,
                feedback_id=entry.id,
                message="Failed to reject post",
            )

        logger.info(f"Post {request.post_id} rejected by {request.actor or 'unknown'}")

        return FeedbackResponse(
            success=True,
            post_id=request.post_id,
            new_status=ApprovalStatus.REJECTED.value,
            feedback_id=entry.id,
            message="Post rejected successfully",
        )

    def request_revision(self, request: RevisionRequest) -> FeedbackResponse:
        """Request revision for a blog post.

        Args:
            request: The revision request.

        Returns:
            FeedbackResponse with the result.
        """
        post = self.storage.get_post(request.post_id)
        if not post:
            logger.warning(f"Post {request.post_id} not found for revision request")
            return FeedbackResponse(
                success=False,
                post_id=request.post_id,
                new_status="",
                feedback_id="",
                message=f"Post {request.post_id} not found",
            )

        # Create feedback entry for learning
        entry = self._create_feedback_entry(
            post=post,
            action="revision_requested",
            feedback=request.feedback,
            categories=request.categories,
            ratings=request.ratings,
            actor=request.actor,
        )

        # Perform the revision request
        updated = self.storage.request_revision(
            request.post_id,
            feedback=request.feedback,
            actor=request.actor,
        )

        if not updated:
            return FeedbackResponse(
                success=False,
                post_id=request.post_id,
                new_status=post.approval_status.value,
                feedback_id=entry.id,
                message="Failed to request revision",
            )

        logger.info(f"Revision requested for post {request.post_id} by {request.actor or 'unknown'}")

        return FeedbackResponse(
            success=True,
            post_id=request.post_id,
            new_status=ApprovalStatus.REVISION_REQUESTED.value,
            feedback_id=entry.id,
            message="Revision requested successfully",
        )

    def get_post_feedback(self, post_id: str) -> List[FeedbackEntry]:
        """Get all feedback entries for a post.

        Args:
            post_id: The post identifier.

        Returns:
            List of FeedbackEntry objects.
        """
        history = self.storage.get_post_history(post_id)

        entries = []
        for h in history:
            if h.action.startswith("feedback_"):
                action = h.action.replace("feedback_", "")
                metadata = h.metadata or {}

                # Reconstruct ratings from metadata
                ratings = []
                for r in metadata.get("ratings", []):
                    try:
                        ratings.append(FeedbackRating(**r))
                    except (TypeError, ValueError):
                        pass

                # Reconstruct categories from metadata
                categories = []
                for c in metadata.get("categories", []):
                    try:
                        categories.append(FeedbackCategory(c))
                    except ValueError:
                        pass

                entry = FeedbackEntry(
                    id=metadata.get("feedback_id", h.id),
                    post_id=post_id,
                    job_id=h.job_id,
                    action=action,
                    feedback=h.feedback,
                    categories=categories,
                    ratings=ratings,
                    actor=h.actor,
                    created_at=h.created_at,
                )
                entries.append(entry)

        return entries

    def get_feedback_stats(self) -> FeedbackStats:
        """Get aggregated feedback statistics for learning.

        Analyzes feedback patterns to inform future content generation.

        Returns:
            FeedbackStats with aggregated data.
        """
        # Get base stats from storage
        storage_stats = self.storage.get_stats()

        # Get all posts for detailed analysis
        posts = self.storage.list_posts(limit=1000)

        # Calculate topic-based stats
        feedback_by_topic: Dict[str, Dict[str, int]] = {}
        for post in posts:
            topic = post.topic
            if topic not in feedback_by_topic:
                feedback_by_topic[topic] = {"total": 0, "approved": 0, "rejected": 0, "revision": 0}

            feedback_by_topic[topic]["total"] += 1
            if post.approval_status == ApprovalStatus.APPROVED:
                feedback_by_topic[topic]["approved"] += 1
            elif post.approval_status == ApprovalStatus.REJECTED:
                feedback_by_topic[topic]["rejected"] += 1
            elif post.approval_status == ApprovalStatus.REVISION_REQUESTED:
                feedback_by_topic[topic]["revision"] += 1

        # Calculate approval rates per topic
        for topic, counts in feedback_by_topic.items():
            if counts["total"] > 0:
                counts["approval_rate"] = round(counts["approved"] / counts["total"] * 100, 2)

        return FeedbackStats(
            total_feedback=storage_stats.total_posts,
            approvals=storage_stats.approved_posts,
            rejections=storage_stats.rejected_posts,
            revisions=storage_stats.revision_requested,
            approval_rate=storage_stats.approval_rate,
            avg_time_to_decision_hours=storage_stats.avg_approval_time_hours,
            feedback_by_topic=feedback_by_topic,
        )

    def get_learning_data(self, limit: int = 100) -> List[dict]:
        """Get structured data for feedback-based learning.

        Returns data suitable for training or refining content generation.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of dictionaries with learning data.
        """
        posts = self.storage.list_posts(limit=limit)
        learning_data = []

        for post in posts:
            # Only include posts with final decisions
            if post.approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
                data = {
                    "post_id": post.id,
                    "job_id": post.job_id,
                    "topic": post.topic,
                    "title": post.title,
                    "word_count": post.word_count,
                    "scoring": post.scoring,
                    "outcome": post.approval_status.value,
                    "feedback": post.approval_feedback,
                    "created_at": post.created_at.isoformat(),
                    "decided_at": post.approved_at.isoformat() if post.approved_at else None,
                }
                learning_data.append(data)

        return learning_data
