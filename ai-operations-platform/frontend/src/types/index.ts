// Shared frontend types. Mirrors the backend response schemas.

export interface DatasetManifest {
  ticket_count: number;
  comment_count: number;
  metric_events: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
  by_locale: Record<string, number>;
  [key: string]: unknown;
}

// --- Workforce optimization (/api/wfm/*) -------------------------------------

export interface ModelScore {
  model: string;
  mae: number;
  rmse: number;
  mape: number;
}

export interface ForecastResult {
  days: number;
  start: string;
  end: string;
  mean_per_day: number;
  noise_floor_mae: number;
  split_index: number;
  chosen_model: string;
  models: ModelScore[];
  weekday_profile: number[];
  series: { date: string; count: number }[];
  backtest: { date: string; actual: number; forecast: number }[];
}

export interface CapacityResult {
  util_target: number;
  scale_factor: number;
  window_days: number;
  handle_min_median: number;
  handle_min_p90: number;
  raw_occupancy_pct: number;
  understaffed_pct: number;
  overstaffed_pct: number;
  peak_hour: number;
  peak_required: number;
  peak_available: number;
  intraday: { hour: number; required: number; available: number }[];
}

export interface SkillGap {
  group_id: number;
  skill: string;
  required: number;
  available: number;
  gap: number;
}

export interface CoverageResult {
  skills: SkillGap[];
  gap_matrix: { hours: number[]; skills: string[]; values: number[][] };
  net_shortage_agent_hours: number;
  understaffed_cells: number;
  total_cells: number;
  client_risk: { organization_id: number; client: string; dedicated: boolean; exposure: number }[];
}

export interface SkillSupply {
  group_id: number;
  skill: string;
  demand: number;
  before: number;
  after: number;
}

export interface Recommendation {
  agent_id: number;
  from_skill: string;
  to_skill: string;
  type: "reassign" | "cross-train";
}

export interface OptimizerResult {
  unmet_before: number;
  unmet_after: number;
  reduction_pct: number;
  moves: number;
  reassign: number;
  cross_train: number;
  moves_into: Record<string, number>;
  skills: SkillSupply[];
  recommendations: Recommendation[];
}

export interface WfmSummary {
  as_of: string;
  window_days: number;
  scale_factor: number;
  forecast: { chosen_model: string; mae: number; mape: number; noise_floor_mae: number; at_noise_floor: boolean };
  capacity: { understaffed_pct: number; overstaffed_pct: number; peak_hour: number };
  coverage: {
    net_shortage_agent_hours: number;
    understaffed_cells: number;
    total_cells: number;
    worst_skill: string;
    worst_gap: number;
  };
  optimizer: {
    unmet_before: number;
    unmet_after: number;
    reduction_pct: number;
    moves: number;
    reassign: number;
    cross_train: number;
  };
}

export interface WfmBundle {
  summary: WfmSummary;
  forecast: ForecastResult;
  capacity: CapacityResult;
  coverage: CoverageResult;
  optimizer: OptimizerResult;
}

export interface UploadMeta {
  source: string;
  roster_modeled: boolean;
  rows_parsed: number;
  tickets_used: number;
  date_start: string;
  date_end: string;
  ndays: number;
  skills: string[];
  agents_modeled: number;
  scale_factor: number;
  columns: Record<string, string>;
  warnings: string[];
}

export interface AnalyzeResult extends WfmBundle {
  meta: UploadMeta;
}

// --- Copilot agent (/api/agent/ask) ------------------------------------------

export interface ToolTraceEntry {
  tool: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface AnalyticsLink {
  label: string;
  href: string;
}

export interface AgentResponse {
  question: string;
  answer: string;
  tool_trace: ToolTraceEntry[];
  analytics_links: AnalyticsLink[];
  caveats: string[];
  models_used: { planner?: string; synthesizer?: string };
  grounding_ok: boolean;
}

// --- Reports bundle (/api/reports) -------------------------------------------

export interface InsightsData {
  headline: string;
  kpis: { name: string; unit: string; current: number; change_pct: number; direction: string; favorable: boolean | null }[];
  anomalies: { metric: string; week: string; value: number; deviation: number }[];
  drivers: { metric: string; dimension: string; segments: { segment: string; contribution: number }[] }[];
}

export interface ClientRow {
  organization_id: number;
  client: string;
  tickets: number;
  share_pct: number;
  per_day: number;
  dedicated: boolean;
  trend_pct: number | null;
}

export interface ClientsData {
  total_tickets: number;
  clients: ClientRow[];
  concentration: { top1_share_pct: number; top3_share_pct: number; is_concentrated: boolean; top1_vs_uniform: number | null };
}

export interface ReportsBundle extends WfmBundle {
  synced_at: string;
  insights: InsightsData;
  clients: ClientsData;
}
