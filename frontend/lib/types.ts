// 全局类型定义（与后端 schemas.py 对齐）

export interface ResumeHeader {
  name: string;
  phone: string;
  email: string;
  location: string;
  target_role: string;
}

export interface EducationEntry {
  school: string;
  college: string;
  degree: string;
  major: string;
  start_date: string;
  end_date: string;
  gpa: string;
  courses: string[];
  honors: string[];
}

export interface ExperienceEntry {
  company: string;
  role: string;
  start_date: string;
  end_date: string;
  items: string[];
}

export interface ParsedResume {
  header: ResumeHeader;
  education: EducationEntry[];
  experience: ExperienceEntry[];
  skills: Record<string, string>;
  raw_markdown: string;
}

export interface JDAnalysis {
  role: string;
  company: string;
  archetype: string;
  core_requirements: string[];
  preferred_requirements: string[];
  keywords: string[];
  soft_skills: string[];
  industry_terms: string[];
  legitimacy_score: number;
  legitimacy_flags: string[];
  ranking: Record<string, string[]>;
}

export interface MatchDimension {
  name: string;
  score: number;
  max: number;
}

export interface GapItem {
  requirement: string;
  status: "match" | "partial" | "missing";
  detail: string;
}

export interface MatchResult {
  overall_score: number;
  dimensions: MatchDimension[];
  gap_analysis: GapItem[];
}

export type SuggestionType = "wording" | "star" | "keyword" | "structure" | "delete";
export type SuggestionStatus = "pending" | "accepted" | "rejected" | "adjusted";

export interface Suggestion {
  id: string;
  section: string;
  type: SuggestionType;
  original_text: string;
  suggested_text: string;
  reason: string;
  jd_match_points: string[];
  line_range: [number, number];
  status: SuggestionStatus;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface ApplicationStats {
  total: number;
  by_status: Record<string, number>;
  applied_count: number;
  interview_count: number;
  offer_count: number;
  rejected_count?: number;
  reply_rate?: number;
  written_test_rate?: number;
  interview_rate?: number;
  offer_rate?: number;
}

export interface ApplicationRecord {
  id: string;
  company: string;
  role: string;
  channel: string;
  jd_text: string;
  jd_url?: string;
  match_score: number;
  decision_level: string;
  status: string;
  session_id: string;
  notes: string;
  deadline?: string;
  created_at: string;
  updated_at: string;
  status_history?: { status: string; at: string }[];
}

export interface JobPosting {
  id: string;
  company: string;
  role: string;
  source: string;
  jd_text: string;
  jd_url?: string;
  location?: string;
  deadline?: string;
  channel?: string;
  tags?: string[];
  city?: string;
  locations?: string[];
  crawled_at?: string;
  published_at?: string;
  job_type?: string;
  source_site?: string;
  validation_status?: "ok" | "weak" | "invalid" | "pending";
  validation_issues?: string[];
  ai_summary?: string;
  ai_tags?: string[];
  status?: string;
  referral_code?: string;
  legitimacy?: "trusted" | "likely" | "suspect" | "";
  graduation_cohort?: string;
  cohort_confidence?: "explicit" | "inferred" | "unknown" | "";
  cross_verified?: boolean;
  verification_score?: number;
  verification_source_count?: number;
  source_attestations?: SourceAttestation[];
  alternate_jd_urls?: string[];
}

export interface SourceAttestation {
  source: string;
  channel?: string;
  jd_url?: string;
  legitimacy?: string;
  crawled_at?: string;
  source_site?: string;
  graduation_cohort?: string;
  cohort_confidence?: string;
}

export interface JobFeedMeta {
  total: number;
  job_types: Record<string, number>;
  sources: Record<string, number>;
  work_cities: Record<string, number>;
  graduation_cohorts?: Record<string, number>;
  cross_verified_count?: number;
  last_crawled_at: string;
}

export interface JobPreferences {
  target_roles: string[];
  target_cities: string[];
  job_types: string[];
  target_cohort: string;
  include_unknown_cohort: boolean;
  company_wishlist: string[];
  company_blocklist: string[];
  extra_notes: string;
}

export interface JobPriorityItem {
  job_id: string;
  company: string;
  role: string;
  job_type?: string;
  locations?: string[];
  priority: "P0" | "P1" | "P2" | string;
  score: number;
  reasons: string[];
  is_new?: boolean;
  jd_url?: string;
  ai_summary?: string;
}

export interface JobDigest {
  headline: string;
  summary: string;
  action_tips: string[];
  new_count: number;
  priority_jobs: JobPriorityItem[];
  generated_at?: string;
  used_llm?: boolean;
}

export interface CompareRow {
  job_id: string;
  company: string;
  role: string;
  deadline: string;
  source: string;
  match: MatchResult;
  score_breakdown?: {
    bm25: number;
    skill: number;
    jaccard: number;
    preference: number;
  };
  decision: {
    match_score: number;
    legitimacy_score: number;
    level: "strong" | "moderate" | "weak" | "risk";
    label: string;
    recommend_apply: boolean;
    top_gaps: string[];
  };
}

/** 声明式 GenUI 块（对标 A2UI 轻量实现） */
export type GenUiBlock =
  | { type: "job_cards"; jobs: CopilotJobCard[] }
  | {
      type: "match_summary";
      headline: string;
      summary?: string;
      algorithm?: string;
      top_scores: Array<{ company: string; role: string; score?: number; priority?: string }>;
    }
  | { type: "filter_chips"; chips: Array<{ label: string; key: string; value: string }> }
  | {
      type: "actions";
      buttons: Array<{ label: string; action: string; payload?: Record<string, unknown> }>;
    };

export interface CopilotJobCard {
  id: string;
  company: string;
  role: string;
  job_type?: string;
  location?: string;
  deadline?: string;
  jd_url?: string;
  source?: string;
  match_score?: number | null;
}

export type CareerCopilotEvent =
  | { type: "thinking"; content?: string }
  | { type: "text"; content: string }
  | { type: "gen_ui"; block: GenUiBlock }
  | { type: "done"; reply?: string; blocks?: GenUiBlock[]; intent?: string }
  | { type: "error"; message: string };

export interface CrawlHealth {
  last_run_at?: string;
  summary?: string;
  new_count?: number;
  total?: number;
  providers?: Record<
    string,
    { status: string; fetched?: number; health?: string; error?: string; last_run_at?: string }
  >;
}

export interface CrawlRun {
  run_at: string;
  new_count: number;
  total: number;
  summary: string;
  providers: Record<string, { status: string; fetched?: number; duration_ms?: number; error?: string; health?: string }>;
}

export interface SessionArchive {
  session_id: string;
  title: string;
  company: string;
  role: string;
  status: string;
  finalize_status: "draft" | "finalized" | "stale";
  pending_suggestions: number;
  suggestions_total: number;
  has_finalized: boolean;
  updated_at: string;
  created_at: string;
}

export interface InterviewPrepPack {
  company: string;
  role: string;
  stories: Array<{
    id: string;
    title: string;
    situation: string;
    task: string;
    action: string;
    result: string;
    relevance: number;
  }>;
  questions: Record<
    string,
    Array<{
      question: string;
      category: string;
      story_fit: string;
      suggested_story_title: string;
      tips: string;
    }>
  >;
  interviews?: InterviewBankItem[];
  real_questions?: string[];
}

export interface InterviewBankItem {
  title: string;
  author?: string;
  summary?: string;
  source?: string;
  source_url?: string;
  category?: string;
  tags?: string[];
  questions?: string[];
}

export interface InterviewBankResult {
  total: number;
  interviews: InterviewBankItem[];
  common_questions: string[];
}

export interface Reminder {
  type: string;
  app_id?: string;
  job_id?: string;
  company: string;
  role: string;
  message: string;
  urgency: string;
  due_at?: string;
  action?: string;
}

export interface TodayPick {
  job_id?: string;
  company: string;
  role: string;
  readiness_score?: number;
  match_score?: number;
  deadline?: string;
  jd_url?: string;
  referral_code?: string;
  reasons?: string[];
  next_action?: string;
  days_left?: number;
  message?: string;
}

export interface TodayBriefing {
  headline: string;
  personalization_note?: string;
  has_resume: boolean;
  feed_total: number;
  top_picks: TodayPick[];
  urgent_deadlines: TodayPick[];
  digest_headline?: string;
  generated_at?: string;
}

export interface AhaSnapshot {
  headline: string;
  top_picks: TodayPick[];
  summary: string;
}

export interface JobReadiness {
  readiness_score: number;
  match_score: number;
  days_to_deadline?: number | null;
  reasons: string[];
  blockers: string[];
  next_action: string;
  components?: Record<string, number>;
}

export interface AtsReadbackResult {
  ats_score: number;
  readable: boolean;
  char_extracted: number;
  keyword_retention: number;
  issues: string[];
  missing_keywords: string[];
}

export interface BatchTailorItem {
  job_id: string;
  company: string;
  role: string;
  readiness_score: number;
  match_score: number;
  top_gaps: string[];
  reasons: string[];
  action_label: string;
  jd_url?: string;
}

export interface PatternInsights {
  total: number;
  rejection_rate: number;
  insights: string[];
  recommendations: string[];
  by_channel: Record<string, { total: number; rejected: number; interview: number }>;
}

export interface UserProfile {
  client_id: string;
  display_name: string;
  email: string;
  school: string;
  major: string;
  graduation_year: string;
  target_roles: string[];
  weekly_apply_limit: number;
  min_match_score: number;
}

export interface PendingKnowledgeItem {
  id: string;
  source: string;
  new_text: string;
  original_text: string;
  facts?: Array<{ field: string; value: string }>;
  target_title?: string;
  status: string;
  created_at: string;
}
