/**
 * API client for communicating with the AI Blogger backend.
 */

import type {
  JobSubmitRequest,
  JobSubmitResponse,
  JobStatusResponse,
  JobListResponse,
  PreviewResponse,
  ApprovePostRequest,
  RejectPostRequest,
  RevisionPostRequest,
  FeedbackResponse,
  FeedbackEntry,
  FeedbackStats,
  HealthResponse,
  JobStatus,
} from './types';

const API_BASE = '/api';

class ApiError extends Error {
  status: number;
  statusText: string;
  detail?: string;

  constructor(status: number, statusText: string, detail?: string) {
    super(detail ?? statusText);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const errorData = await response.json();
      detail = errorData.detail;
    } catch {
      // Ignore JSON parse errors
    }
    throw new ApiError(response.status, response.statusText, detail);
  }
  
  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }
  
  return response.json();
}

// Health Check
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  return handleResponse<HealthResponse>(response);
}

// Job Management
export async function submitJob(request: JobSubmitRequest): Promise<JobSubmitResponse> {
  const response = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<JobSubmitResponse>(response);
}

export async function listJobs(
  status?: JobStatus,
  limit: number = 100
): Promise<JobListResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('limit', limit.toString());
  
  const response = await fetch(`${API_BASE}/jobs?${params}`);
  return handleResponse<JobListResponse>(response);
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  return handleResponse<JobStatusResponse>(response);
}

export async function getJobByCorrelationId(correlationId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${API_BASE}/jobs/correlation/${encodeURIComponent(correlationId)}`);
  return handleResponse<JobStatusResponse>(response);
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
  });
  return handleResponse<void>(response);
}

export async function executeJob(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/execute`, {
    method: 'POST',
  });
  return handleResponse<JobStatusResponse>(response);
}

// Preview
export async function getPreview(jobId: string): Promise<PreviewResponse> {
  const response = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/preview`);
  return handleResponse<PreviewResponse>(response);
}

// Approval Workflow
export async function approvePost(
  postId: string,
  request: ApprovePostRequest
): Promise<FeedbackResponse> {
  const response = await fetch(`${API_BASE}/posts/${encodeURIComponent(postId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<FeedbackResponse>(response);
}

export async function rejectPost(
  postId: string,
  request: RejectPostRequest
): Promise<FeedbackResponse> {
  const response = await fetch(`${API_BASE}/posts/${encodeURIComponent(postId)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<FeedbackResponse>(response);
}

export async function requestRevision(
  postId: string,
  request: RevisionPostRequest
): Promise<FeedbackResponse> {
  const response = await fetch(`${API_BASE}/posts/${encodeURIComponent(postId)}/revision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<FeedbackResponse>(response);
}

export async function getPostFeedback(postId: string): Promise<FeedbackEntry[]> {
  const response = await fetch(`${API_BASE}/posts/${encodeURIComponent(postId)}/feedback`);
  return handleResponse<FeedbackEntry[]>(response);
}

// Feedback Stats
export async function getFeedbackStats(): Promise<FeedbackStats> {
  const response = await fetch(`${API_BASE}/feedback/stats`);
  return handleResponse<FeedbackStats>(response);
}

export async function getLearningData(limit: number = 100): Promise<Record<string, unknown>[]> {
  const response = await fetch(`${API_BASE}/feedback/learning?limit=${limit}`);
  return handleResponse<Record<string, unknown>[]>(response);
}

export { ApiError };
