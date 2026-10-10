export type Protocol = "openai" | "anthropic" | "gemini";
export type TaskMode = "fixed" | "step" | "open";
export type TaskStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled"
  | "interrupted";
export type RecordStatus = "ok" | "error" | "timeout" | "cancelled";

export interface TaskConfig {
  protocol: Protocol;
  base_url: string;
  api_key: string;
  model: string;
  mode: TaskMode;
  concurrency: number;
  total_requests: number;
  step_levels: number[];
  step_requests: number;
  arrival_rate: number;
  fixed_duration_s: number;
  step_duration_s: number;
  auto_stop: boolean;
  sla_ttft_p95_s: number;
  sla_e2e_p95_s: number;
  sla_error_rate: number;
  input_tokens: number;
  max_output_tokens: number;
  timeout: number;
  with_image: boolean;
  image_id: string;
  questions: string[];
}

export interface ImageMeta {
  id: string;
  name: string;
  source: "builtin" | "upload";
  mime: string;
  url: string;
  credit: string;
  size: number;
}

export interface Stats {
  avg: number;
  p50: number;
  p90: number;
  p95: number;
  p99: number;
  max: number;
}

export type ErrorBreakdown = Record<string, number>;

export interface Snapshot {
  elapsed_s: number;
  planned: number;
  completed: number;
  errors: number;
  in_flight: number;
  tokens_total: number;
  input_tokens_total: number;
  throughput_tps: number;
  output_tps: number;
  input_tps: number;
  window_tps: number;
  rps: number;
  window_rps: number;
  ttft_ms: Stats;
  e2e_ms: Stats;
  tpot_ms: Stats;
  itl_ms: Stats;
  error_rate: number;
  error_breakdown: ErrorBreakdown;
  current_step?: {
    index: number;
    concurrency: number;
    snapshot: Omit<Snapshot, "current_step">;
  } | null;
}

export interface StepSummary {
  concurrency: number;
  planned: number;
  completed: number;
  errors: number;
  ttft_avg: number;
  ttft_p50: number;
  ttft_p95: number;
  ttft_p99: number;
  e2e_avg: number;
  e2e_p50: number;
  e2e_p95: number;
  e2e_p99: number;
  tpot_avg: number;
  tpot_p50: number;
  tpot_p95: number;
  itl_p50: number;
  itl_p95: number;
  throughput_tps: number;
  output_tps: number;
  input_tps: number;
  rps: number;
  error_rate: number;
  error_breakdown: ErrorBreakdown;
}

export interface AnalysisSla {
  ttft_p95_s: number;
  e2e_p95_s: number;
  error_rate: number;
}

export interface Analysis {
  ok: boolean;
  stop_reason: string;
  sla: AnalysisSla;
  single: {
    concurrency: number;
    output_tps: number;
    input_tps: number;
    rps: number;
    ttft_p95_ms: number;
    e2e_p95_ms: number;
    tpot_p95_ms: number;
    itl_p95_ms: number;
  };
  max_throughput: {
    concurrency: number;
    output_tps: number;
    input_tps: number;
    rps: number;
  };
  saturation: { concurrency: number | null; range: number[] | null };
  knee: { concurrency: number | null };
  sla_max_concurrency: number | null;
  recommended_concurrency: number | null;
  max_sustainable_rps: number | null;
  confidence: "high" | "medium" | "low";
}

export interface RecordOut {
  idx: number;
  step: number;
  status: RecordStatus;
  ttft_ms: number | null;
  e2e_ms: number | null;
  tpot_ms: number | null;
  output_tokens: number;
  input_tokens: number;
  tok_per_s: number | null;
  itl_p50_ms: number | null;
  error_class: string;
  error: string;
  t_start: number;
  t_end: number;
}

export interface TaskSummary {
  id: string;
  name: string;
  protocol: string;
  base_url: string;
  model: string;
  status: TaskStatus;
  error: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  config: TaskConfig;
  summary: Partial<Snapshot>;
  steps: StepSummary[];
  analysis: Partial<Analysis>;
}

export interface TaskDetail extends TaskSummary {
  records: RecordOut[];
}

export interface PresetOut {
  id: string;
  name: string;
  config: TaskConfig;
}

export interface ProbeResult {
  ok: boolean;
  ttft_ms: number | null;
  latency_ms: number | null;
  error: string;
  text: string;
}

export interface ModelListResult {
  ok: boolean;
  models: string[];
  error: string;
}

export type SSEEvent =
  | { type: "status"; data: { status: TaskStatus; error?: string } }
  | { type: "records"; data: RecordOut[] }
  | { type: "record"; data: RecordOut }
  | { type: "steps"; data: StepSummary[] }
  | { type: "step_start"; data: { index: number; concurrency: number } }
  | { type: "analysis"; data: Analysis }
  | { type: "auto_stop"; data: { reason: string } }
  | { type: "snapshot"; data: Snapshot };