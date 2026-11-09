// Types mirroring the Python backend API contracts (backend/app/schemas + routers).

export type DataSourceLabel = "LIVE DATA" | "SYNTHETIC DEMO DATA" | "MODEL PREDICTION" | "INFERENCE" | "USER INPUT";

export interface Health {
  status: string;
  app: string;
  version: string;
  database: string;
  youtube: { configured: boolean; quota_used_process: number };
  google_ads: {
    configured: boolean;
    missing: string[];
    customer_id: string;
    note: string;
  };
  google_oauth: { configured: boolean };
  llm: { engine: string; model: string | null };
  task_queue: string;
}

export interface StepState {
  key: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  detail: string;
}

export interface AnalysisJob {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  current_step: number;
  steps: StepState[];
  progress: number;
  error: string;
  analysis_id: number | null;
}

export interface AudienceSegment {
  key: string;
  label: string;
  age_bands: string[];
  interests: string[];
  note: string;
}

export interface Audience {
  age_weights: Record<string, number>;
  gender_skew: Record<string, number>;
  interests: string[];
  geo: { primary_market: string; priority_cities: string[]; note: string };
  segments: AudienceSegment[];
  intent: string;
  aov_estimate?: number;
  objective_bias?: string;
  disclaimer: string;
  inference_method: string;
}

export interface ResearchVideo {
  video_id: string;
  title: string;
  channel_title: string;
  channel_id: string;
  views: number;
  likes: number;
  comments: number;
  duration_seconds: number;
  engagement_rate: number;
  published_at: string;
  thumbnail_url: string;
  data_source_label: string;
  url?: string;
}

export interface FormatSuitability {
  format_key: string;
  label: string;
  affinity: number;
  verdict: string;
  rationale: string;
}

export interface Analysis {
  id: number;
  product: {
    id: number;
    name: string;
    description: string;
    total_budget: number;
    currency: string;
    market: string;
  };
  category: string;
  product_type: string;
  features: string[];
  value_proposition: string;
  problems_solved: string[];
  audience: Audience;
  objective: string;
  objective_rationale: string;
  competitor_summary: Record<string, unknown>;
  suitable_formats: FormatSuitability[];
  videos: ResearchVideo[];
  inference_method: string;
  data_source_label: DataSourceLabel;
  youtube_research_status: string;
  ads_history_status: string;
  confidence: number;
  created_at: string;
}

export interface Allocation {
  format_key: string;
  label: string;
  share: number;
  amount: number;
  predicted: {
    impressions: number;
    clicks: number;
    video_views: number;
    conversions: number;
    revenue: number;
    cpa: number | null;
    roas: number | null;
  };
  confidence: number;
  reason: string;
  fit_factors?: {
    audience: number;
    objective: number;
    category: number;
    research: number;
  };
}

export interface Recommendation {
  id: number;
  analysis_id: number;
  total_budget: number;
  currency: string;
  objective: string;
  allocations: Allocation[];
  predicted_totals: {
    impressions: number;
    clicks: number;
    video_views: number;
    conversions: number;
    revenue: number;
    cost: number;
    cpa: number | null;
    roas: number | null;
    ctr: number | null;
    conversion_rate: number | null;
  };
  methodology: string;
  algorithm: string;
  optimizer_meta: Record<string, unknown>;
  cold_start: boolean;
  confidence: number;
  data_source_label: string;
  created_at: string;
}

export interface AnalyticsPoint {
  date: string;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  conversion_value: number;
  video_views: number;
  ctr: number | null;
  cpc: number | null;
  cpa: number | null;
  roas: number | null;
}

export interface Analytics {
  days: number;
  data_source_label: string;
  totals: Record<string, number | null>;
  series: AnalyticsPoint[];
  by_format: Array<Record<string, number | string | null> & { format_key: string }>;
  by_device?: Array<Record<string, number | string | null> & { device: string }>;
  by_city?: Array<Record<string, number | string | null> & { city: string }>;
  by_age?: Array<Record<string, number | string | null> & { age_group: string }>;
  campaigns: Array<{
    campaign_id: number;
    name: string;
    format_key: string;
    status: string;
    data_source_label: string;
    metrics: Record<string, number | null>;
  }>;
}

/* ----------------------------- duration intelligence ---------------------- */
export interface DurationOptionScore {
  duration_key: string;
  label: string;
  seconds: number;
  seconds_label: string;
  non_skippable: boolean;
  note: string;
  score: number;
  expected_hold_rate: number;
  live_adjustment: string;
}

export interface DurationRec {
  format_key: string;
  format_label: string;
  best: DurationOptionScore;
  alternatives: DurationOptionScore[];
  all: DurationOptionScore[];
}

export interface RetentionCurve {
  format_key: string;
  format_label: string;
  duration_key: string;
  label: string;
  seconds: number;
  points: Array<{ t: number; held: number }>;
}

export interface DurationPlan {
  analysis_id: number;
  objective: string;
  data_source_label: string;
  recommendations: DurationRec[];
  overall_best: (DurationOptionScore & { format_key: string; format_label: string; reason: string }) | null;
  retention_curves: RetentionCurve[];
  live_research: {
    label: string;
    videos_used: number;
    note: string;
    buckets: Array<{
      bucket: string;
      count: number;
      median_views: number;
      median_engagement: number;
      engagement_index: number | null;
    }>;
    scatter: Array<{ seconds: number; engagement_rate: number; views: number; title: string }>;
  };
  methodology: string;
}

export interface MlModelInfo {
  target: string;
  best_model: string;
  metrics: Record<string, { mae?: number; rmse?: number; r2?: number; error?: string }>;
  train_seconds?: number;
}

export interface MlModels {
  available: boolean;
  trained_on: string;
  rows_train: number | null;
  rows_test: number | null;
  targets: MlModelInfo[];
  note: string;
}

export interface BenchmarkRow {
  id: number;
  engine: string;
  rows: number;
  dataset_size_mb: number;
  generate_seconds: number;
  pipeline_seconds: number;
  peak_memory_mb: number;
  status: string;
  error: string;
  equivalence_ok: boolean;
  created_at: string;
}

export interface BigDataJob {
  job_id: string;
  status: string;
  rows: number;
  engines: string[];
  current_step: string;
  progress: number;
  error: string;
}

export interface ReportRow {
  id: number;
  analysis_id: number;
  format: string;
  size_bytes: number;
  created_at: string;
  download: string;
}

export interface SettingsInfo {
  currency: string;
  market: string;
  supported_currencies: string[];
  supported_markets: string[];
  google_ads: { configured: boolean; missing: string[]; note: string };
  youtube: { configured: boolean };
  oauth: { configured: boolean; redirect_uri: string };
}

export interface OAuthStatus {
  connected: boolean;
  status: string;
  google_email?: string;
  scopes?: string[];
  refresh_token_in_env: boolean;
  ads: { configured: boolean; missing: string[]; note: string };
  note?: string;
}
