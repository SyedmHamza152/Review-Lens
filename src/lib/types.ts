// Types mirroring the Python backend API contracts (app/schemas.py).

export type SentimentLabel = "positive" | "negative" | "neutral" | "mixed";

export interface PlatformInfo {
  key: string;
  name: string;
  type: "marketplace" | "social";
  status: string;
  live_capability: "live" | "requires_credentials" | "not_available";
  has_credentials: boolean;
  required_env: string[];
  access_mode: string;
  notes: string;
  docs_url: string;
}

export interface PlatformStatus {
  platform: string;
  platform_name: string;
  status:
    | "pending"
    | "searching"
    | "success"
    | "success_sample"
    | "no_results"
    | "needs_credentials"
    | "blocked"
    | "unsupported"
    | "error";
  message: string;
  items_collected: number;
  is_sample: boolean;
  requires_credentials: string[];
  collected_at: string | null;
}

export interface JobStatus {
  job_id: string;
  product_name: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string;
  progress: number;
  data_mode: string;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  platforms: PlatformStatus[];
  totals: { collected: number } | null;
}

export interface Verdict {
  score: number;
  label: string;
  positive_pct: number;
  negative_pct: number;
  neutral_pct: number;
  mixed_pct: number;
  avg_confidence: number;
  methodology_note: string;
}

export interface DistributionItem {
  label: SentimentLabel;
  count: number;
  pct: number;
}

export interface AspectStat {
  aspect: string;
  label: string;
  scope: "product" | "seller" | "marketplace";
  mentions: number;
  positive: number;
  negative: number;
  neutral: number;
  mixed: number;
  avg_polarity: number;
}

export interface ComparisonRow {
  platform: string;
  platform_name: string;
  total: number;
  positive_pct: number;
  negative_pct: number;
  neutral_pct: number;
  mixed_pct: number;
  avg_rating: number | null;
  low_sample: boolean;
  is_sample: boolean;
  rank_by_positive: number | null;
  top_positive_aspect: string | null;
  top_complaint_aspect: string | null;
  top_drivers: string[];
  status: string;
  message: string;
  collected_at: string | null;
}

export interface LanguageRow {
  language: string;
  count: number;
  pct: number;
  positive: number;
  negative: number;
  neutral: number;
  mixed: number;
}

export interface TrendPoint {
  period: string;
  score: number;
  count: number;
}

export interface MarketplaceListingGroup {
  platform: string;
  platform_name: string;
  listing_count: number;
  avg_rating: number | null;
  total_review_count: number;
  data_source: string;
  note: string;
  items: {
    name: string;
    rating: number | null;
    review_count: number;
    price_text: string | null;
    seller: string | null;
    sold_count_text: string | null;
    url: string | null;
  }[];
}

export interface PhraseCount {
  phrase: string;
  count: number;
  detail: string;
}

export interface Report {
  job: {
    id: string;
    product_name: string;
    description: string | null;
    created_at: string;
    completed_at: string | null;
    data_mode: string;
  };
  platform_statuses: PlatformStatus[];
  totals: {
    collected: number;
    analyzed: number;
    spam_filtered: number;
    low_relevance_excluded: number;
    platforms_with_data: number;
    platforms_requested: number;
    avg_confidence: number;
  };
  verdict: Verdict;
  distribution: DistributionItem[];
  summary: string;
  aspects: AspectStat[];
  advantages: PhraseCount[];
  complaints: PhraseCount[];
  comparison: ComparisonRow[];
  languages: LanguageRow[];
  trends: TrendPoint[];
  marketplace_listings: MarketplaceListingGroup[];
  methodology: {
    nlp_pipeline: string;
    scoring: string;
    mixed_rule: string;
    min_sample_for_verdict: number;
    low_sample_platform_threshold: number;
    confidence: string;
    disclaimers: string[];
  };
}

export interface ReviewRow {
  id: number;
  platform: string;
  platform_name: string;
  text_original: string;
  translation: string | null;
  language: string;
  language_confidence: number;
  language_uncertain: boolean;
  sentiment: SentimentLabel;
  sentiment_score: number;
  sentiment_confidence: number;
  sentiment_uncertain: boolean;
  sarcasm_suspect: boolean;
  complaint_scope: string;
  aspects: { aspect: string; label: string; polarity: number }[];
  drivers: string[];
  rating: number | null;
  review_date: string | null;
  variant: string | null;
  source_url: string | null;
  is_spam: boolean;
  relevance: number;
  data_source: string;
}

export interface PaginatedReviews {
  total: number;
  page: number;
  page_size: number;
  items: ReviewRow[];
}
