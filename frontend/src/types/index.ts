export type IssueCategory =
  | 'water'
  | 'medical'
  | 'food'
  | 'infrastructure'
  | 'sanitation'
  | 'electricity'
  | 'education'
  | 'other';

export type IssueSeverity = 'critical' | 'high' | 'medium' | 'low';
export type IssueStatus = 'open' | 'assigned' | 'completed';
export type AssignmentStatus =
  | 'applied'
  | 'assigned'
  | 'in_progress'
  | 'submitted'
  | 'verified'
  | 'completed'
  | 'rejected';
export type ActorRole = 'admin' | 'volunteer';
export type LeaderboardCategory = 'points' | 'trust_score';
export type LeaderboardTimeframe = 'all_time' | 'month' | 'week';
export type VerificationVerdict = 'pass' | 'fail' | 'suspicious';

export interface VolunteerLocation {
  city: string;
  district: string;
  state: string;
}

export interface Issue {
  issue_id: string;
  title: string;
  category: IssueCategory;
  location: string;
  severity: IssueSeverity;
  description: string;
  report_count: number;
  priority_score: number;
  status: IssueStatus;
  created_at: string;
  updated_at: string;
}

export interface Volunteer {
  volunteer_id: string;
  name: string;
  email: string;
  skills: string;
  location: VolunteerLocation;
  trust_score: number;
  tasks_completed: number;
  tasks_failed: number;
  total_images_submitted: number;
  failed_verifications: number;
  average_rating: number;
  points: number;
  badges: string[];
  rank: number;
  created_at: string;
  is_active: boolean;
}

export interface AssignmentSubmissionData {
  images: string[];
  notes?: string | null;
  before_images: string[];
  after_images: string[];
}

export interface Assignment {
  id?: string;
  assignment_id: string;
  issue_id: string;
  volunteer_id: string;
  status: AssignmentStatus;
  applied_at: string;
  assigned_at: string | null;
  started_at?: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  submission_data: AssignmentSubmissionData | null;
  admin_notes: string | null;
  application_message?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface VolunteerMatchBreakdown {
  skill_similarity: number;
  location_match: number;
  performance_boost: number;
}

export interface VolunteerMatch {
  volunteer_id: string;
  name: string;
  match_score: number;
  breakdown: VolunteerMatchBreakdown;
  skills: string;
  trust_score: number;
  tasks_completed: number;
}

export interface LeaderboardEntry {
  rank: number;
  volunteer_id: string;
  name: string;
  points: number;
  trust_score: number;
  tasks_completed: number;
  badges: string[];
}

export interface DashboardStats {
  active_issues: number;
  pending_assignments: number;
  volunteers_active: number;
  avg_trust_score: number;
  issues_resolved_today: number;
  high_priority_open: number;
}

export interface IngestionData {
  content: string;
  source_type: 'form' | 'image' | 'audio';
  metadata?: Record<string, unknown>;
  location?: string;
  timestamp?: string;
}

export interface IngestResponse {
  success?: boolean;
  data: IngestionData;
}

export interface IssueUpsertResponse {
  matched_existing: boolean;
  similarity?: number | null;
  data: Issue;
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface VolunteerActivity {
  volunteer_id: string;
  name: string;
  tasks_completed: number;
}

export interface WeeklyImpactStats {
  total_issues_reported: number;
  issues_resolved: number;
  average_resolution_time_hours: number;
  top_categories: CategoryCount[];
  most_active_volunteers: VolunteerActivity[];
  trust_score_distribution: Record<string, number>;
}

export interface WeeklyImpactReport {
  date_range: string;
  report_markdown: string;
  stats: WeeklyImpactStats;
}

export interface TrendChartData {
  dates: string[];
  counts: number[];
}

export interface IssueTrend {
  trend: 'increasing' | 'decreasing' | 'stable';
  percentage_change: number;
  summary: string;
  chart_data: TrendChartData;
}

export interface VolunteerPerformanceStats {
  tasks_completed: number;
  average_rating: number;
  trust_score: number;
  response_time_avg: number;
  top_categories: string[];
}

export interface VolunteerRecentTask {
  assignment_id: string;
  issue_id: string;
  issue_title: string;
  category: string;
  status: string;
  completed_at: string | null;
}

export interface VolunteerPerformanceReport {
  volunteer_name: string;
  summary: string;
  stats: VolunteerPerformanceStats;
  recent_tasks: VolunteerRecentTask[];
  badges: string[];
}

export interface VerificationLayerResult {
  passed: boolean | null;
  confidence: number;
  notes: string;
  found_urls?: string[];
  indicators?: string[];
  similar_images?: string[];
}

export interface VerificationChecks {
  reverse_search: VerificationLayerResult;
  ai_generated: VerificationLayerResult;
  duplicate_check: VerificationLayerResult;
}

export interface VerificationImageResult {
  image_path: string;
  checks: VerificationChecks;
  overall_verdict: VerificationVerdict;
  final_confidence: number;
}

export interface VerificationSummary {
  total_images: number;
  passed: number;
  failed: number;
  suspicious: number;
}

export interface VerificationResponse {
  results: VerificationImageResult[];
  summary: VerificationSummary;
}

export interface RatingResponse {
  success: boolean;
  data: {
    rating_id: string;
    assignment_id: string;
    volunteer_id: string;
    admin_id: string;
    stars: number;
    review?: string | null;
    created_at: string;
  };
  awarded_points: number;
  trust_score: number;
}
