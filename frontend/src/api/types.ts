/**
 * TypeScript types matching the backend API models.
 * These mirror the Pydantic models from the Python backend.
 */

// Job-related types
export type JobStatus =
  | 'pending'
  | 'fetching'
  | 'generating'
  | 'scoring'
  | 'refining'
  | 'completed'
  | 'failed';

export interface JobSubmitRequest {
  topics?: string[];
  sources?: string[];
  num_candidates?: number;
  max_results?: Record<string, number>;
  correlation_id?: string;
}

export interface JobSubmitResponse {
  job_id: string;
  correlation_id?: string;
  status: JobStatus;
  message: string;
  is_duplicate: boolean;
}

export interface MarkdownPreview {
  title: string;
  content: string;
  word_count: number;
  topic: string;
  sources: string[];
}

export interface ScoringInfo {
  relevance: number;
  originality: number;
  depth: number;
  clarity: number;
  engagement: number;
  total: number;
  reasoning: string;
}

export interface JobResult {
  markdown_preview: MarkdownPreview;
  scoring: ScoringInfo;
  articles_fetched: number;
  candidates_generated: number;
}

export interface JobError {
  code: string;
  message: string;
  details?: string;
}

export interface JobStatusResponse {
  job_id: string;
  correlation_id?: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
  result?: JobResult;
  error?: JobError;
}

export interface JobListResponse {
  jobs: JobStatusResponse[];
  total: number;
}

export interface PreviewResponse {
  success: boolean;
  preview?: MarkdownPreview;
  message: string;
}

// Feedback-related types
export type FeedbackCategory =
  | 'quality'
  | 'relevance'
  | 'accuracy'
  | 'clarity'
  | 'engagement'
  | 'length'
  | 'style'
  | 'sources'
  | 'other';

export interface FeedbackRating {
  category: FeedbackCategory;
  score: number; // 1-5
  comment?: string;
}

export interface ApprovePostRequest {
  feedback?: string;
  ratings?: FeedbackRating[];
  actor?: string;
}

export interface RejectPostRequest {
  feedback: string;
  categories?: FeedbackCategory[];
  ratings?: FeedbackRating[];
  actor?: string;
}

export interface RevisionPostRequest {
  feedback: string;
  categories?: FeedbackCategory[];
  ratings?: FeedbackRating[];
  actor?: string;
}

export interface FeedbackResponse {
  success: boolean;
  post_id: string;
  new_status: string;
  feedback_id: string;
  message: string;
}

export interface FeedbackEntry {
  id: string;
  post_id: string;
  job_id?: string;
  action: string;
  feedback?: string;
  categories: FeedbackCategory[];
  ratings: FeedbackRating[];
  actor?: string;
  post_scoring?: Record<string, unknown>;
  post_topic?: string;
  post_word_count?: number;
  created_at: string;
}

export interface FeedbackStats {
  total_feedback: number;
  approvals: number;
  rejections: number;
  revisions: number;
  approval_rate?: number;
  avg_quality_score?: number;
  avg_relevance_score?: number;
  avg_clarity_score?: number;
  avg_engagement_score?: number;
  common_rejection_categories: string[];
  avg_time_to_decision_hours?: number;
  feedback_by_topic: Record<string, Record<string, unknown>>;
}

// Health check
export interface HealthResponse {
  status: string;
  job_service: boolean;
  feedback_service: boolean;
  storage: boolean;
}
