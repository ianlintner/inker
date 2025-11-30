import { useJobs } from '../hooks/useJobs';
import type { JobStatusResponse, JobStatus } from '../api';
import styles from './JobList.module.css';

interface JobListProps {
  onSelectJob?: (job: JobStatusResponse) => void;
  selectedJobId?: string | null;
}

const STATUS_LABELS: Record<JobStatus, string> = {
  pending: 'Pending',
  fetching: 'Fetching Articles',
  generating: 'Generating',
  scoring: 'Scoring',
  refining: 'Refining',
  completed: 'Completed',
  failed: 'Failed',
};

const STATUS_COLORS: Record<JobStatus, string> = {
  pending: '#6b7280',
  fetching: '#3b82f6',
  generating: '#8b5cf6',
  scoring: '#f59e0b',
  refining: '#10b981',
  completed: '#059669',
  failed: '#ef4444',
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString();
}

function getStatusProgress(status: JobStatus): number {
  const stages: JobStatus[] = [
    'pending',
    'fetching',
    'generating',
    'scoring',
    'refining',
    'completed',
  ];
  const index = stages.indexOf(status);
  if (status === 'failed') return 100;
  return index >= 0 ? Math.round((index / (stages.length - 1)) * 100) : 0;
}

export function JobList({ onSelectJob, selectedJobId }: JobListProps) {
  const { jobs, loading, error, refresh } = useJobs({ pollInterval: 5000 });

  if (loading && jobs.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading jobs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          Error: {error}
          <button onClick={refresh} className={styles.retryButton}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>
          <p>No jobs found</p>
          <p className={styles.emptySubtext}>Submit a new job to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Jobs</h2>
        <button onClick={refresh} className={styles.refreshButton}>
          ↻ Refresh
        </button>
      </div>
      <div className={styles.list}>
        {jobs.map((job) => (
          <div
            key={job.job_id}
            className={`${styles.jobCard} ${selectedJobId === job.job_id ? styles.selected : ''}`}
            onClick={() => onSelectJob?.(job)}
          >
            <div className={styles.jobHeader}>
              <span
                className={styles.statusBadge}
                style={{ backgroundColor: STATUS_COLORS[job.status] }}
              >
                {STATUS_LABELS[job.status]}
              </span>
              <span className={styles.jobId}>{job.job_id.slice(0, 8)}...</span>
            </div>

            {job.status !== 'completed' && job.status !== 'failed' && (
              <div className={styles.progressContainer}>
                <div
                  className={styles.progressBar}
                  style={{
                    width: `${getStatusProgress(job.status)}%`,
                    backgroundColor: STATUS_COLORS[job.status],
                  }}
                />
              </div>
            )}

            <div className={styles.jobInfo}>
              <div className={styles.infoRow}>
                <span className={styles.label}>Created:</span>
                <span className={styles.value}>{formatDate(job.created_at)}</span>
              </div>
              {job.correlation_id && (
                <div className={styles.infoRow}>
                  <span className={styles.label}>Correlation ID:</span>
                  <span className={styles.value}>{job.correlation_id}</span>
                </div>
              )}
              {job.result?.markdown_preview && (
                <div className={styles.postTitle}>
                  "{job.result.markdown_preview.title}"
                </div>
              )}
              {job.error && (
                <div className={styles.errorMessage}>
                  Error: {job.error.message}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
