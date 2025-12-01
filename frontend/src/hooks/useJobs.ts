import { useState, useEffect, useCallback, useRef } from 'react';
import { listJobs, getJobStatus } from '../api';
import type { JobStatusResponse, JobStatus } from '../api';

interface UseJobsOptions {
  pollInterval?: number;
  statusFilter?: JobStatus;
  limit?: number;
}

interface UseJobsResult {
  jobs: JobStatusResponse[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Hook to fetch and poll jobs list with automatic refresh.
 */
export function useJobs(options: UseJobsOptions = {}): UseJobsResult {
  const { pollInterval = 5000, statusFilter, limit = 100 } = options;
  const [jobs, setJobs] = useState<JobStatusResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<number | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const result = await listJobs(statusFilter, limit);
      setJobs(result.jobs);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch jobs');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, limit]);

  useEffect(() => {
    fetchJobs();

    // Set up polling
    if (pollInterval > 0) {
      intervalRef.current = window.setInterval(fetchJobs, pollInterval);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchJobs, pollInterval]);

  return { jobs, loading, error, refresh: fetchJobs };
}

interface UseJobStatusOptions {
  pollInterval?: number;
  stopOnComplete?: boolean;
}

interface UseJobStatusResult {
  job: JobStatusResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Hook to fetch and poll a single job status.
 */
export function useJobStatus(
  jobId: string | null,
  options: UseJobStatusOptions = {}
): UseJobStatusResult {
  const { pollInterval = 2000, stopOnComplete = true } = options;
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<number | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId) {
      setJob(null);
      setLoading(false);
      return;
    }

    try {
      const result = await getJobStatus(jobId);
      setJob(result);
      setError(null);

      // Stop polling if job is complete and option is set
      if (
        stopOnComplete &&
        (result.status === 'completed' || result.status === 'failed') &&
        intervalRef.current
      ) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch job');
    } finally {
      setLoading(false);
    }
  }, [jobId, stopOnComplete]);

  useEffect(() => {
    setLoading(true);
    fetchJob();

    // Set up polling
    if (jobId && pollInterval > 0) {
      intervalRef.current = window.setInterval(fetchJob, pollInterval);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchJob, jobId, pollInterval]);

  return { job, loading, error, refresh: fetchJob };
}
