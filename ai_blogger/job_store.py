"""Job storage layer for the Blog Post Job API.

Provides a simple file-based persistence layer for job data with support
for correlation ID lookups and concurrent access.
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .job_models import Job, JobRequest, JobStatus

logger = logging.getLogger(__name__)


class JobStore:
    """File-based job storage with thread-safe operations.

    Stores jobs as individual JSON files in a configurable directory.
    Supports correlation ID lookups for idempotency.

    Attributes:
        storage_dir: Directory path for job storage.
    """

    def __init__(self, storage_dir: str = "./jobs"):
        """Initialize the job store.

        Args:
            storage_dir: Directory to store job files.
        """
        self.storage_dir = Path(storage_dir)
        self._lock = threading.RLock()
        self._correlation_index: Dict[str, str] = {}
        self._ensure_storage_dir()
        self._rebuild_correlation_index()

    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_job_path(self, job_id: str) -> Path:
        """Get the file path for a job.

        Args:
            job_id: The job identifier.

        Returns:
            Path to the job file.
        """
        return self.storage_dir / f"{job_id}.json"

    def _rebuild_correlation_index(self) -> None:
        """Rebuild the correlation ID index from stored jobs."""
        with self._lock:
            self._correlation_index.clear()
            for job_file in self.storage_dir.glob("*.json"):
                try:
                    job = self._load_job_from_file(job_file)
                    if job and job.correlation_id:
                        self._correlation_index[job.correlation_id] = job.id
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to load job {job_file}: {e}")

    def _load_job_from_file(self, path: Path) -> Optional[Job]:
        """Load a job from a file.

        Args:
            path: Path to the job file.

        Returns:
            Job object or None if file doesn't exist.
        """
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Job.model_validate(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error loading job from {path}: {e}")
            return None

    def _save_job_to_file(self, job: Job) -> None:
        """Save a job to a file.

        Args:
            job: The job to save.
        """
        path = self._get_job_path(job.id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(job.model_dump(mode="json"), f, indent=2, default=str)
        except (OSError, TypeError) as e:
            logger.error(f"Error saving job {job.id} to {path}: {e}")
            raise

    def create_job(self, job_id: str, request: JobRequest) -> Job:
        """Create a new job.

        Args:
            job_id: Unique identifier for the job.
            request: The job request.

        Returns:
            The created Job object.

        Raises:
            ValueError: If correlation_id already exists.
        """
        now = datetime.now()

        with self._lock:
            # Check for duplicate correlation ID
            if request.correlation_id:
                existing_job_id = self._correlation_index.get(request.correlation_id)
                if existing_job_id:
                    raise ValueError(
                        f"Job with correlation_id '{request.correlation_id}' already exists: {existing_job_id}"
                    )

            job = Job(
                id=job_id,
                correlation_id=request.correlation_id,
                status=JobStatus.PENDING,
                request=request,
                created_at=now,
                updated_at=now,
            )

            self._save_job_to_file(job)

            if request.correlation_id:
                self._correlation_index[request.correlation_id] = job_id

            return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            Job object or None if not found.
        """
        with self._lock:
            return self._load_job_from_file(self._get_job_path(job_id))

    def get_job_by_correlation_id(self, correlation_id: str) -> Optional[Job]:
        """Get a job by correlation ID.

        Args:
            correlation_id: The correlation ID to look up.

        Returns:
            Job object or None if not found.
        """
        with self._lock:
            job_id = self._correlation_index.get(correlation_id)
            if job_id:
                return self.get_job(job_id)
            return None

    def update_job(self, job: Job) -> Job:
        """Update an existing job.

        Args:
            job: The job to update.

        Returns:
            The updated Job object.
        """
        job.updated_at = datetime.now()

        with self._lock:
            self._save_job_to_file(job)
            return job

    def update_job_status(self, job_id: str, status: JobStatus, **kwargs) -> Optional[Job]:
        """Update a job's status and optional fields.

        Args:
            job_id: The job identifier.
            status: The new status.
            **kwargs: Additional fields to update.

        Returns:
            Updated Job or None if not found.
        """
        with self._lock:
            job = self.get_job(job_id)
            if not job:
                return None

            # Set started_at when transitioning from PENDING to an active status
            if job.status == JobStatus.PENDING and status != JobStatus.PENDING and job.started_at is None:
                job.started_at = datetime.now()

            job.status = status
            job.updated_at = datetime.now()

            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.completed_at = datetime.now()

            # Update additional fields
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            self._save_job_to_file(job)
            return job

    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[Job]:
        """List jobs with optional status filter.

        Args:
            status: Optional status filter.
            limit: Maximum number of jobs to return.

        Returns:
            List of Job objects.
        """
        jobs = []

        with self._lock:
            for job_file in self.storage_dir.glob("*.json"):
                if len(jobs) >= limit:
                    break

                job = self._load_job_from_file(job_file)
                if job:
                    if status is None or job.status == status:
                        jobs.append(job)

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: The job identifier.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            job = self.get_job(job_id)
            if not job:
                return False

            path = self._get_job_path(job_id)
            try:
                os.remove(path)
            except OSError as e:
                logger.error(f"Error deleting job {job_id}: {e}")
                return False

            if job.correlation_id:
                self._correlation_index.pop(job.correlation_id, None)

            return True
