import { useState, useEffect } from 'react';
import { useJobStatus } from '../hooks/useJobs';
import {
  getPreview,
  approvePost,
  rejectPost,
  requestRevision,
  executeJob,
  deleteJob,
} from '../api';
import type {
  JobStatusResponse,
  MarkdownPreview,
  FeedbackCategory,
} from '../api';
import styles from './PostReview.module.css';

interface PostReviewProps {
  job: JobStatusResponse | null;
  onJobDeleted?: () => void;
  onJobExecuted?: (job: JobStatusResponse) => void;
}

const FEEDBACK_CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: 'quality', label: 'Quality' },
  { value: 'relevance', label: 'Relevance' },
  { value: 'accuracy', label: 'Accuracy' },
  { value: 'clarity', label: 'Clarity' },
  { value: 'engagement', label: 'Engagement' },
  { value: 'length', label: 'Length' },
  { value: 'style', label: 'Style' },
  { value: 'sources', label: 'Sources' },
  { value: 'other', label: 'Other' },
];

export function PostReview({ job: initialJob, onJobDeleted, onJobExecuted }: PostReviewProps) {
  const { job: polledJob } = useJobStatus(initialJob?.job_id ?? null, {
    pollInterval: 2000,
    stopOnComplete: true,
  });

  const job = polledJob ?? initialJob;

  const [preview, setPreview] = useState<MarkdownPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<FeedbackCategory[]>([]);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    async function fetchPreview() {
      if (!job || job.status !== 'completed') {
        setPreview(null);
        return;
      }

      setLoadingPreview(true);
      try {
        const result = await getPreview(job.job_id);
        if (result.success && result.preview) {
          setPreview(result.preview);
        }
      } catch (err) {
        console.error('Failed to load preview:', err);
      } finally {
        setLoadingPreview(false);
      }
    }

    fetchPreview();
    // Intentionally only depend on job_id and status to avoid unnecessary re-fetches
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.job_id, job?.status]);

  if (!job) {
    return (
      <div className={styles.container}>
        <div className={styles.placeholder}>
          <p>Select a job to view details</p>
        </div>
      </div>
    );
  }

  const handleExecute = async () => {
    setActionLoading('execute');
    setActionResult(null);
    try {
      const result = await executeJob(job.job_id);
      setActionResult({ type: 'success', message: 'Job execution started' });
      onJobExecuted?.(result);
    } catch (err) {
      setActionResult({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to execute job',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this job?')) {
      return;
    }

    setActionLoading('delete');
    setActionResult(null);
    try {
      await deleteJob(job.job_id);
      setActionResult({ type: 'success', message: 'Job deleted' });
      onJobDeleted?.();
    } catch (err) {
      setActionResult({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to delete job',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleApprove = async () => {
    setActionLoading('approve');
    setActionResult(null);
    try {
      await approvePost(job.job_id, {
        feedback: feedback || undefined,
        actor: 'web-user',
      });
      setActionResult({ type: 'success', message: 'Post approved successfully!' });
      setFeedback('');
    } catch (err) {
      setActionResult({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to approve post',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async () => {
    if (!feedback.trim()) {
      setActionResult({ type: 'error', message: 'Feedback is required for rejection' });
      return;
    }

    setActionLoading('reject');
    setActionResult(null);
    try {
      await rejectPost(job.job_id, {
        feedback,
        categories: selectedCategories,
        actor: 'web-user',
      });
      setActionResult({ type: 'success', message: 'Post rejected' });
      setFeedback('');
      setSelectedCategories([]);
    } catch (err) {
      setActionResult({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to reject post',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRequestRevision = async () => {
    if (!feedback.trim()) {
      setActionResult({ type: 'error', message: 'Feedback is required for revision request' });
      return;
    }

    setActionLoading('revision');
    setActionResult(null);
    try {
      await requestRevision(job.job_id, {
        feedback,
        categories: selectedCategories,
        actor: 'web-user',
      });
      setActionResult({ type: 'success', message: 'Revision requested' });
      setFeedback('');
      setSelectedCategories([]);
    } catch (err) {
      setActionResult({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to request revision',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const toggleCategory = (category: FeedbackCategory) => {
    setSelectedCategories((prev) =>
      prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
    );
  };

  const isProcessing =
    job.status === 'fetching' ||
    job.status === 'generating' ||
    job.status === 'scoring' ||
    job.status === 'refining';

  return (
    <div className={styles.container}>
      {/* Job Header */}
      <div className={styles.header}>
        <h2 className={styles.title}>Job Details</h2>
        <span className={`${styles.statusBadge} ${styles[job.status]}`}>
          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
        </span>
      </div>

      {/* Job Info */}
      <div className={styles.infoSection}>
        <div className={styles.infoRow}>
          <span className={styles.label}>Job ID:</span>
          <code className={styles.code}>{job.job_id}</code>
        </div>
        {job.correlation_id && (
          <div className={styles.infoRow}>
            <span className={styles.label}>Correlation ID:</span>
            <code className={styles.code}>{job.correlation_id}</code>
          </div>
        )}
        <div className={styles.infoRow}>
          <span className={styles.label}>Created:</span>
          <span>{new Date(job.created_at).toLocaleString()}</span>
        </div>
        {job.started_at && (
          <div className={styles.infoRow}>
            <span className={styles.label}>Started:</span>
            <span>{new Date(job.started_at).toLocaleString()}</span>
          </div>
        )}
        {job.completed_at && (
          <div className={styles.infoRow}>
            <span className={styles.label}>Completed:</span>
            <span>{new Date(job.completed_at).toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Processing Status */}
      {isProcessing && (
        <div className={styles.processingSection}>
          <div className={styles.spinner} />
          <span>Processing: {job.status}</span>
        </div>
      )}

      {/* Error Display */}
      {job.error && (
        <div className={styles.errorSection}>
          <h3>Error</h3>
          <p>
            <strong>{job.error.code}:</strong> {job.error.message}
          </p>
          {job.error.details && <p className={styles.errorDetails}>{job.error.details}</p>}
        </div>
      )}

      {/* Pending Job Actions */}
      {job.status === 'pending' && (
        <div className={styles.actionsSection}>
          <button
            onClick={handleExecute}
            disabled={actionLoading !== null}
            className={styles.executeButton}
          >
            {actionLoading === 'execute' ? 'Executing...' : 'Execute Job'}
          </button>
          <button
            onClick={handleDelete}
            disabled={actionLoading !== null}
            className={styles.deleteButton}
          >
            {actionLoading === 'delete' ? 'Deleting...' : 'Delete Job'}
          </button>
        </div>
      )}

      {/* Preview Section */}
      {job.status === 'completed' && (
        <>
          {loadingPreview ? (
            <div className={styles.loadingPreview}>Loading preview...</div>
          ) : preview ? (
            <div className={styles.previewSection}>
              <h3 className={styles.previewTitle}>{preview.title}</h3>
              <div className={styles.previewMeta}>
                <span>Topic: {preview.topic}</span>
                <span>Words: {preview.word_count}</span>
                <span>Sources: {preview.sources.length}</span>
              </div>

              {job.result?.scoring && (
                <div className={styles.scoringSection}>
                  <h4>Scoring</h4>
                  <div className={styles.scoreGrid}>
                    <ScoreBar label="Relevance" value={job.result.scoring.relevance} max={10} />
                    <ScoreBar label="Originality" value={job.result.scoring.originality} max={10} />
                    <ScoreBar label="Depth" value={job.result.scoring.depth} max={10} />
                    <ScoreBar label="Clarity" value={job.result.scoring.clarity} max={10} />
                    <ScoreBar label="Engagement" value={job.result.scoring.engagement} max={10} />
                  </div>
                  <div className={styles.totalScore}>
                    Total Score: <strong>{job.result.scoring.total.toFixed(2)}</strong>
                  </div>
                </div>
              )}

              <div className={styles.contentPreview}>
                <h4>Content Preview</h4>
                <pre className={styles.markdown}>{preview.content}</pre>
              </div>

              {/* Approval Workflow */}
              <div className={styles.approvalSection}>
                <h4>Review & Approve</h4>

                <div className={styles.feedbackForm}>
                  <label className={styles.feedbackLabel}>
                    Feedback / Comments:
                    <textarea
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      className={styles.feedbackTextarea}
                      placeholder="Add your feedback here..."
                      rows={4}
                    />
                  </label>

                  <div className={styles.categoriesSection}>
                    <span className={styles.categoriesLabel}>
                      Feedback Categories (for rejection/revision):
                    </span>
                    <div className={styles.categoriesGrid}>
                      {FEEDBACK_CATEGORIES.map((cat) => (
                        <label key={cat.value} className={styles.categoryLabel}>
                          <input
                            type="checkbox"
                            checked={selectedCategories.includes(cat.value)}
                            onChange={() => toggleCategory(cat.value)}
                          />
                          {cat.label}
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className={styles.approvalButtons}>
                    <button
                      onClick={handleApprove}
                      disabled={actionLoading !== null}
                      className={styles.approveButton}
                    >
                      {actionLoading === 'approve' ? 'Approving...' : '✓ Approve'}
                    </button>
                    <button
                      onClick={handleRequestRevision}
                      disabled={actionLoading !== null}
                      className={styles.revisionButton}
                    >
                      {actionLoading === 'revision' ? 'Requesting...' : '↻ Request Revision'}
                    </button>
                    <button
                      onClick={handleReject}
                      disabled={actionLoading !== null}
                      className={styles.rejectButton}
                    >
                      {actionLoading === 'reject' ? 'Rejecting...' : '✗ Reject'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className={styles.noPreview}>No preview available</div>
          )}
        </>
      )}

      {/* Action Result */}
      {actionResult && (
        <div className={`${styles.actionResult} ${styles[actionResult.type]}`}>
          {actionResult.message}
        </div>
      )}
    </div>
  );
}

// Helper component for score bars
function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  const percentage = (value / max) * 100;
  return (
    <div className={styles.scoreRow}>
      <span className={styles.scoreLabel}>{label}</span>
      <div className={styles.scoreBarContainer}>
        <div className={styles.scoreBarFill} style={{ width: `${percentage}%` }} />
      </div>
      <span className={styles.scoreValue}>{value.toFixed(1)}</span>
    </div>
  );
}
