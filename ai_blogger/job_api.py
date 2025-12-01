"""Blog Post Job API service.

This module provides the core API for submitting and managing blog post
generation jobs. It is designed to be used by front-end clients or
integrated into web frameworks.
"""

import logging
import uuid
from typing import List, Optional

from .chains import generate_candidates, refine_winner, score_candidates
from .config import SOURCE_DEFAULTS, TOPICS
from .fetchers import fetch_all_articles, get_available_sources
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
from .metrics import (
    get_tracer,
    record_job_status_change,
    record_job_submission,
    track_job_execution,
)

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing blog post generation jobs.

    This service handles job submission, execution, status tracking,
    and result retrieval. It supports correlation IDs for idempotency.

    Attributes:
        store: The job storage backend.
    """

    def __init__(self, storage_dir: str = "./jobs"):
        """Initialize the job service.

        Args:
            storage_dir: Directory for job storage.
        """
        self.store = JobStore(storage_dir)

    def _generate_job_id(self) -> str:
        """Generate a unique job ID.

        Returns:
            A UUID4 string.
        """
        return str(uuid.uuid4())

    def submit_job(self, request: JobRequest) -> JobSubmitResponse:
        """Submit a new blog post generation job.

        If a correlation_id is provided and a job with that ID already
        exists, returns the existing job instead of creating a new one.

        Args:
            request: The job request parameters.

        Returns:
            JobSubmitResponse with job details.
        """
        # Check for existing job with same correlation ID
        if request.correlation_id:
            existing = self.store.get_job_by_correlation_id(request.correlation_id)
            if existing:
                logger.info(f"Returning existing job {existing.id} for correlation_id {request.correlation_id}")
                record_job_submission(is_duplicate=True)
                return JobSubmitResponse(
                    job_id=existing.id,
                    correlation_id=existing.correlation_id,
                    status=existing.status,
                    message="Job already exists with this correlation ID",
                    is_duplicate=True,
                )

        # Create new job
        job_id = self._generate_job_id()
        job = self.store.create_job(job_id, request)

        logger.info(f"Created new job {job_id}")
        record_job_submission(is_duplicate=False)

        return JobSubmitResponse(
            job_id=job.id,
            correlation_id=job.correlation_id,
            status=job.status,
            message="Job submitted successfully",
            is_duplicate=False,
        )

    def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """Get the status of a job.

        Args:
            job_id: The job identifier.

        Returns:
            JobStatusResponse or None if not found.
        """
        job = self.store.get_job(job_id)
        if not job:
            return None

        return JobStatusResponse(
            job_id=job.id,
            correlation_id=job.correlation_id,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            result=job.result,
            error=job.error,
        )

    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[JobStatusResponse]:
        """Get job status by correlation ID.

        Args:
            correlation_id: The correlation ID to look up.

        Returns:
            JobStatusResponse or None if not found.
        """
        job = self.store.get_job_by_correlation_id(correlation_id)
        if not job:
            return None

        return JobStatusResponse(
            job_id=job.id,
            correlation_id=job.correlation_id,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            result=job.result,
            error=job.error,
        )

    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[JobStatusResponse]:
        """List jobs with optional status filter.

        Args:
            status: Optional status to filter by.
            limit: Maximum number of jobs to return.

        Returns:
            List of JobStatusResponse objects.
        """
        jobs = self.store.list_jobs(status=status, limit=limit)

        return [
            JobStatusResponse(
                job_id=job.id,
                correlation_id=job.correlation_id,
                status=job.status,
                created_at=job.created_at,
                updated_at=job.updated_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                result=job.result,
                error=job.error,
            )
            for job in jobs
        ]

    def execute_job(self, job_id: str) -> Optional[Job]:
        """Execute a pending job synchronously.

        This method runs the full blog post generation pipeline for a job.
        It updates job status at each stage and handles errors.

        Args:
            job_id: The job identifier.

        Returns:
            Updated Job or None if not found.
        """
        job = self.store.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return None

        if job.status != JobStatus.PENDING:
            logger.warning(f"Job {job_id} is not pending (status: {job.status})")
            return job

        tracer = get_tracer()
        current_status = job.status.value  # Track for error handling
        try:
            with track_job_execution(job_id, "blog_post"):
                with tracer.start_as_current_span(
                    "job.fetch_articles",
                    attributes={"job.id": job_id},
                ):
                    # Step 1: Fetch articles (started_at is set by update_job_status)
                    prev_status = job.status.value
                    self.store.update_job_status(job_id, JobStatus.FETCHING)
                    record_job_status_change(prev_status, JobStatus.FETCHING.value)
                    current_status = JobStatus.FETCHING.value
                    logger.info(f"Job {job_id}: Fetching articles...")

                    topics = job.request.topics or TOPICS
                    sources = job.request.sources or get_available_sources()
                    max_results = job.request.max_results or SOURCE_DEFAULTS.copy()

                    articles = fetch_all_articles(
                        topics=topics,
                        sources=sources,
                        max_results=max_results,
                    )

                    if not articles:
                        raise ValueError("No articles found for the given topics")

                    articles_count = len(articles)
                    logger.info(f"Job {job_id}: Fetched {articles_count} articles")

                with tracer.start_as_current_span(
                    "job.generate_candidates",
                    attributes={"job.id": job_id},
                ):
                    # Step 2: Generate candidates
                    record_job_status_change(JobStatus.FETCHING.value, JobStatus.GENERATING.value)
                    self.store.update_job_status(job_id, JobStatus.GENERATING)
                    current_status = JobStatus.GENERATING.value
                    logger.info(f"Job {job_id}: Generating candidates...")

                    num_candidates = job.request.num_candidates
                    candidates = generate_candidates(articles, num_candidates=num_candidates)

                    if not candidates:
                        raise ValueError("No candidates were generated")

                    candidates_count = len(candidates)
                    logger.info(f"Job {job_id}: Generated {candidates_count} candidates")

                with tracer.start_as_current_span(
                    "job.score_candidates",
                    attributes={"job.id": job_id},
                ):
                    # Step 3: Score candidates
                    record_job_status_change(JobStatus.GENERATING.value, JobStatus.SCORING.value)
                    self.store.update_job_status(job_id, JobStatus.SCORING)
                    current_status = JobStatus.SCORING.value
                    logger.info(f"Job {job_id}: Scoring candidates...")

                    scored = score_candidates(candidates)

                    if not scored:
                        raise ValueError("No candidates were scored")

                    winner = scored[0]
                    logger.info(f"Job {job_id}: Winner '{winner.candidate.title}' with score {winner.score.total:.2f}")

                with tracer.start_as_current_span(
                    "job.refine_winner",
                    attributes={"job.id": job_id},
                ):
                    # Step 4: Refine winner
                    record_job_status_change(JobStatus.SCORING.value, JobStatus.REFINING.value)
                    self.store.update_job_status(job_id, JobStatus.REFINING)
                    current_status = JobStatus.REFINING.value
                    logger.info(f"Job {job_id}: Refining winner...")

                    final_content = refine_winner(winner)

                # Build result
                word_count = len(final_content.split())

                result = JobResult(
                    markdown_preview=MarkdownPreview(
                        title=winner.candidate.title,
                        content=final_content,
                        word_count=word_count,
                        topic=winner.candidate.topic,
                        sources=winner.candidate.sources,
                    ),
                    scoring=ScoringInfo(
                        relevance=winner.score.relevance,
                        originality=winner.score.originality,
                        depth=winner.score.depth,
                        clarity=winner.score.clarity,
                        engagement=winner.score.engagement,
                        total=winner.score.total,
                        reasoning=winner.score.reasoning,
                    ),
                    articles_fetched=articles_count,
                    candidates_generated=candidates_count,
                )

                # Mark job as completed
                record_job_status_change(JobStatus.REFINING.value, JobStatus.COMPLETED.value)
                job = self.store.update_job_status(job_id, JobStatus.COMPLETED, result=result)

                logger.info(f"Job {job_id}: Completed successfully")
                return job

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")

            error = JobError(
                code="JOB_EXECUTION_ERROR",
                message=str(e),
                details=type(e).__name__,
            )

            record_job_status_change(current_status, JobStatus.FAILED.value)
            job = self.store.update_job_status(job_id, JobStatus.FAILED, error=error)
            return job

    def delete_job(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: The job identifier.

        Returns:
            True if deleted, False if not found.
        """
        return self.store.delete_job(job_id)
