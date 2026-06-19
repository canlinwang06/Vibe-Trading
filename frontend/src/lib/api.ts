import { authHeaders, withAuthQuery } from "@/lib/apiAuth";

const BASE = "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const AUTH_REQUIRED_MESSAGE =
  "Remote API access requires an API key. Add it in Settings, or run the backend on localhost for local-only use.";

export function isAuthRequiredError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

async function errorFromResponse(res: Response): Promise<ApiError> {
  let detail = `HTTP ${res.status}`;
  try {
    const body = await res.json();
    detail = body.detail || body.message || detail;
  } catch { /* ignore */ }
  if (res.status === 401 || res.status === 403) {
    detail = AUTH_REQUIRED_MESSAGE;
  }
  return new ApiError(detail, res.status);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers, ...rest } = options ?? {};
  const mergedHeaders: Record<string, string> = { "Content-Type": "application/json", ...authHeaders() };
  if (headers) {
    new Headers(headers).forEach((value, key) => {
      mergedHeaders[key] = value;
    });
  }
  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: mergedHeaders,
  });
  if (!res.ok) {
    throw await errorFromResponse(res);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}

export interface UploadResult {
  status: string;
  file_path: string;
  filename: string;
}

async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", headers: authHeaders(), body: form });
  if (!res.ok) {
    throw await errorFromResponse(res);
  }
  return res.json();
}

function appendQueryParam(url: string, key: string, value: string): string {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
}

export const api = {
  uploadFile,
  listRuns: () => request<RunListItem[]>("/runs"),
  getRun: (id: string, params: RunDetailParams = {}) => {
    const q = new URLSearchParams();
    if (params.chart_payload) q.set("chart_payload", params.chart_payload);
    if (params.chart_symbol) q.set("chart_symbol", params.chart_symbol);
    const qs = q.toString();
    return request<RunData>(`/runs/${id}${qs ? `?${qs}` : ""}`);
  },
  getRunCode: (id: string) => request<Record<string, string>>(`/runs/${id}/code`),
  getRunPine: (id: string) => request<PineScriptResult>(`/runs/${id}/pine`),
  listSessions: () => request<SessionItem[]>("/sessions"),
  createSession: (title?: string) => request<SessionItem>("/sessions", { method: "POST", body: JSON.stringify({ title: title || "" }) }),
  deleteSession: (sid: string) => request<{ status: string }>(`/sessions/${sid}`, { method: "DELETE" }),
  renameSession: (sid: string, title: string) => request<{ status: string }>(`/sessions/${sid}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  sendMessage: (sid: string, content: string) => request<{ message_id: string; attempt_id: string }>(`/sessions/${sid}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  cancelSession: (sid: string) => request<{ status: string }>(`/sessions/${sid}/cancel`, { method: "POST" }),
  getSessionMessages: (sid: string) => request<MessageItem[]>(`/sessions/${sid}/messages`),
  createGoal: (sid: string, body: CreateGoalRequest) =>
    request<GoalSnapshot>(`/sessions/${sid}/goal`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getGoal: (sid: string) => request<GoalSnapshot>(`/sessions/${sid}/goal`),
  updateGoal: (sid: string, body: UpdateGoalRequest) =>
    request<UpdateGoalResponse>(`/sessions/${sid}/goal`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  addGoalEvidence: (sid: string, body: AddGoalEvidenceRequest) =>
    request<AddGoalEvidenceResponse>(`/sessions/${sid}/goal/evidence`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateGoalStatus: (sid: string, body: UpdateGoalStatusRequest) =>
    request<UpdateGoalStatusResponse>(`/sessions/${sid}/goal/status`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  sseUrl: (sid: string, options?: { replay?: "active" }) => {
    let url = withAuthQuery(`${BASE}/sessions/${sid}/events`);
    if (options?.replay) url = appendQueryParam(url, "replay", options.replay);
    return url;
  },

  // Swarm API
  listSwarmPresets: () => request<SwarmPreset[]>("/swarm/presets"),
  createSwarmRun: (preset_name: string, user_vars: Record<string, string>) =>
    request<{ id: string; status: string }>("/swarm/runs", {
      method: "POST",
      body: JSON.stringify({ preset_name, user_vars }),
    }),
  listSwarmRuns: () => request<SwarmRunSummary[]>("/swarm/runs"),
  getSwarmRun: (id: string) => request<Record<string, unknown>>(`/swarm/runs/${id}`),
  swarmSseUrl: (id: string) => withAuthQuery(`${BASE}/swarm/runs/${id}/events`),
  cancelSwarmRun: (id: string) =>
    request<{ status: string }>(`/swarm/runs/${id}/cancel`, { method: "POST" }),
  retrySwarmRun: (id: string) =>
    request<{ id: string; status: string; preset_name: string }>(`/swarm/runs/${id}/retry`, { method: "POST" }),
  getLLMSettings: () => request<LLMSettings>("/settings/llm"),
  updateLLMSettings: (settings: UpdateLLMSettingsRequest) =>
    request<LLMSettings>("/settings/llm", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  getDataSourceSettings: () => request<DataSourceSettings>("/settings/data-sources"),
  updateDataSourceSettings: (settings: UpdateDataSourceSettingsRequest) =>
    request<DataSourceSettings>("/settings/data-sources", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  joinQuantPreflight: (body: JoinQuantExportRequest) =>
    request<JoinQuantPreflightResponse>("/api/joinquant/export/preflight", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  joinQuantExportStrategyCode: (body: JoinQuantExportRequest) =>
    request<JoinQuantStrategyCodeResponse>("/api/joinquant/export/strategy-code", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  joinQuantExportCopyPackage: (body: JoinQuantExportRequest) =>
    request<JoinQuantCopyPackageResponse>("/api/joinquant/export/copy-package", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  joinQuantImportExecutionReports: (body: JoinQuantExecutionReportImportRequest) =>
    request<JoinQuantExecutionReportImportResponse>("/api/joinquant/execution-reports/import", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  joinQuantListExecutionReports: (params: JoinQuantExecutionReportQuery = {}) => {
    const q = new URLSearchParams();
    if (params.portfolio_id) q.set("portfolio_id", params.portfolio_id);
    if (params.signal_date) q.set("signal_date", params.signal_date);
    if (params.trade_date) q.set("trade_date", params.trade_date);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<JoinQuantExecutionReportListResponse>(`/api/joinquant/execution-reports${qs ? `?${qs}` : ""}`);
  },
  joinQuantExecutionReportSummary: (params: JoinQuantExecutionReportSummaryQuery) => {
    const q = new URLSearchParams();
    q.set("portfolio_id", params.portfolio_id);
    if (params.signal_date) q.set("signal_date", params.signal_date);
    if (params.trade_date) q.set("trade_date", params.trade_date);
    if (params.tolerance !== undefined) q.set("tolerance", String(params.tolerance));
    return request<JoinQuantExecutionReportSummary>(`/api/joinquant/execution-reports/summary?${q.toString()}`);
  },
  joinQuantSimulationReadiness: (params: JoinQuantSimulationReadinessQuery) => {
    const q = new URLSearchParams();
    q.set("portfolio_id", params.portfolio_id);
    if (params.lookback_days !== undefined) q.set("lookback_days", String(params.lookback_days));
    if (params.min_batches !== undefined) q.set("min_batches", String(params.min_batches));
    if (params.tolerance !== undefined) q.set("tolerance", String(params.tolerance));
    if (params.max_failed_rate !== undefined) q.set("max_failed_rate", String(params.max_failed_rate));
    if (params.max_missing_rate !== undefined) q.set("max_missing_rate", String(params.max_missing_rate));
    if (params.max_deviation_rate !== undefined) q.set("max_deviation_rate", String(params.max_deviation_rate));
    if (params.max_signal_delay_days !== undefined) q.set("max_signal_delay_days", String(params.max_signal_delay_days));
    return request<JoinQuantSimulationReadinessReport>(`/api/joinquant/simulation-readiness?${q.toString()}`);
  },
  dailyWorkflowRun: (body: DailyWorkflowRunRequest) =>
    request<DailyWorkflowRunResponse>("/api/daily-workflow/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listStrategyTemplates: () => request<StrategyTemplateListResponse>("/api/strategy-lab/templates"),
  seedStrategySpecs: (body: StrategySpecSeedRequest) =>
    request<StrategySpecSeedResponse>("/api/strategy-lab/specs/seed", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listStrategySpecs: (params: StrategySpecQuery = {}) => {
    const q = new URLSearchParams();
    if (params.strategy_type) q.set("strategy_type", params.strategy_type);
    if (params.enabled !== undefined && params.enabled !== null) q.set("enabled", String(params.enabled));
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<StrategySpecListResponse>(`/api/strategy-lab/specs${qs ? `?${qs}` : ""}`);
  },
  runStrategyBacktestBatch: (body: BacktestBatchRequest) =>
    request<BacktestBatchResponse>("/api/strategy-lab/backtest-batch", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listStrategyBacktestRuns: (params: BacktestRunQuery = {}) => {
    const q = new URLSearchParams();
    if (params.strategy_id) q.set("strategy_id", params.strategy_id);
    if (params.status) q.set("status", params.status);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<BacktestRunListResponse>(`/api/strategy-lab/backtest-runs${qs ? `?${qs}` : ""}`);
  },
  listStrategyBacktestRankings: (params: BacktestRankingQuery = {}) => {
    const q = new URLSearchParams();
    if (params.strategy_type) q.set("strategy_type", params.strategy_type);
    if (params.status) q.set("status", params.status);
    if (params.min_score !== undefined && params.min_score !== null) q.set("min_score", String(params.min_score));
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<BacktestRankingResponse>(`/api/strategy-lab/backtest-rankings${qs ? `?${qs}` : ""}`);
  },
  allocateRiskPortfolio: (body: PortfolioAllocateRequest) =>
    request<PortfolioAllocationResponse>("/api/portfolio-risk/allocate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listRiskPortfolioAllocations: (params: PortfolioAllocationQuery = {}) => {
    const q = new URLSearchParams();
    if (params.portfolio_id) q.set("portfolio_id", params.portfolio_id);
    if (params.as_of_date) q.set("as_of_date", params.as_of_date);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<PortfolioAllocationListResponse>(`/api/portfolio-risk/allocations${qs ? `?${qs}` : ""}`);
  },
  getRiskTradePlan: (params: PortfolioTradePlanQuery = {}) => {
    const q = new URLSearchParams();
    if (params.portfolio_id) q.set("portfolio_id", params.portfolio_id);
    if (params.as_of_date) q.set("as_of_date", params.as_of_date);
    if (params.max_single_stock_weight !== undefined) {
      q.set("max_single_stock_weight", String(params.max_single_stock_weight));
    }
    if (params.max_sector_weight !== undefined) q.set("max_sector_weight", String(params.max_sector_weight));
    const qs = q.toString();
    return request<PortfolioTradePlanResponse>(`/api/portfolio-risk/trade-plan${qs ? `?${qs}` : ""}`);
  },
  listCandidatePool: (params: CandidatePoolQuery = {}) => {
    const q = new URLSearchParams();
    if (params.as_of_date) q.set("as_of_date", params.as_of_date);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    if (params.source) q.set("source", params.source);
    if (params.included !== undefined && params.included !== null) q.set("included", String(params.included));
    if (params.min_score !== undefined) q.set("min_score", String(params.min_score));
    const qs = q.toString();
    return request<CandidatePoolListResponse>(`/api/candidate-pool${qs ? `?${qs}` : ""}`);
  },
  buildCandidatePool: (body: CandidatePoolBuildRequest) =>
    request<CandidatePoolBuildResponse>("/api/candidate-pool/build", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  addUserCandidate: (body: UserCandidateRequest) =>
    request<CandidateRecord>("/api/candidate-pool/user-add", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  includeCandidate: (body: CandidateDecisionRequest) =>
    request<CandidateRecord>("/api/candidate-pool/include", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  excludeCandidate: (body: CandidateDecisionRequest) =>
    request<CandidateRecord>("/api/candidate-pool/exclude", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  eventReactionsCalculate: (body: EventReactionCalculateRequest) =>
    request<EventReactionCalculateResponse>("/api/event-reactions/calculate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listEventReactions: (params: EventReactionQuery = {}) => {
    const q = new URLSearchParams();
    if (params.event_id) q.set("event_id", params.event_id);
    if (params.cluster_id) q.set("cluster_id", params.cluster_id);
    if (params.target_type) q.set("target_type", params.target_type);
    if (params.target_id) q.set("target_id", params.target_id);
    if (params.window) q.set("window", params.window);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<EventReactionListResponse>(`/api/event-reactions${qs ? `?${qs}` : ""}`);
  },
  eventReactionSummary: (params: EventReactionSummaryQuery = {}) => {
    const q = new URLSearchParams();
    if (params.event_subtype) q.set("event_subtype", params.event_subtype);
    if (params.target_type) q.set("target_type", params.target_type);
    if (params.target_id) q.set("target_id", params.target_id);
    if (params.window) q.set("window", params.window);
    const qs = q.toString();
    return request<EventReactionSummaryResponse>(`/api/event-reactions/summary${qs ? `?${qs}` : ""}`);
  },

  // Alpha Zoo API
  listAlphas: (params: AlphaListParams = {}) => {
    const q = new URLSearchParams();
    if (params.zoo) q.set("zoo", params.zoo);
    if (params.theme) q.set("theme", params.theme);
    if (params.universe) q.set("universe", params.universe);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<AlphaListResponse>(`/alpha/list${qs ? `?${qs}` : ""}`);
  },
  getAlpha: (alphaId: string) =>
    request<AlphaDetailResponse>(`/alpha/${encodeURIComponent(alphaId)}`),
  createAlphaBench: (body: AlphaBenchRequest) =>
    request<{ status: string; job_id: string }>("/alpha/bench", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  alphaBenchStreamUrl: (jobId: string) =>
    withAuthQuery(`${BASE}/alpha/bench/${encodeURIComponent(jobId)}/stream`),
  createAlphaCompare: (body: AlphaCompareRequest) =>
    request<{ status: string; job_id: string }>("/alpha/compare", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  alphaCompareStreamUrl: (jobId: string) =>
    withAuthQuery(`${BASE}/alpha/compare/${encodeURIComponent(jobId)}/stream`),

  // Connector runtime channel — privileged surface actions (NOT agent tools).
  // commit is the ONLY action that writes a mandate; halt trips the kill switch.
  commitMandate: (body: CommitMandateRequest) =>
    request<CommitMandateResponse>("/mandate/commit", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  haltLive: (session_id?: string, broker?: string, reason?: string) =>
    request<HaltLiveResponse>("/live/halt", {
      method: "POST",
      body: JSON.stringify({ session_id, broker, reason }),
    }),
  // Read the persistent runtime status across all authorized brokers (SPEC §7.5).
  // Polled by the RunnerStatus panel; a plain authenticated GET, never a chat message.
  getLiveStatus: () => request<LiveStatus>("/live/status"),
  authorizeLive: (broker: string) =>
    request<LiveAuthorizeResponse>("/live/authorize", {
      method: "POST",
      body: JSON.stringify({ broker }),
    }),
  // Start/stop the persistent runner (SPEC §7.5). Privileged surface actions, not agent tools.
  startLiveRunner: (broker: string) =>
    request<LiveRunnerResponse>("/live/runner/start", {
      method: "POST",
      body: JSON.stringify({ broker }),
    }),
  stopLiveRunner: (broker: string) =>
    request<LiveRunnerResponse>("/live/runner/stop", {
      method: "POST",
      body: JSON.stringify({ broker }),
    }),
};

// --- Swarm types ---

export interface SwarmPreset {
  name: string;
  title: string;
  description: string;
  agent_count: number;
  variables: { name: string; description: string; required: boolean }[];
}

export interface SwarmRunSummary {
  id: string;
  preset_name: string;
  status: string;
  created_at: string;
  task_count: number;
  completed_count: number;
}

export interface LLMProviderOption {
  name: string;
  label: string;
  api_key_env?: string | null;
  base_url_env: string;
  default_model: string;
  default_base_url: string;
  api_key_required: boolean;
  auth_type?: string;
  login_command?: string | null;
}

export interface LLMSettings {
  provider: string;
  model_name: string;
  base_url: string;
  api_key_env?: string | null;
  api_key_configured: boolean;
  api_key_hint?: string | null;
  api_key_required: boolean;
  temperature: number;
  timeout_seconds: number;
  max_retries: number;
  reasoning_effort: string;
  sse_timeout_seconds: number;
  env_path: string;
  providers: LLMProviderOption[];
}

export interface UpdateLLMSettingsRequest {
  provider: string;
  model_name: string;
  base_url: string;
  api_key?: string;
  clear_api_key?: boolean;
  temperature: number;
  timeout_seconds: number;
  max_retries: number;
  reasoning_effort?: string;
}

export interface DataSourceSettings {
  tushare_token_configured: boolean;
  tushare_token_hint?: string | null;
  baostock_supported: boolean;
  baostock_installed: boolean;
  baostock_message: string;
  env_path: string;
}

export interface UpdateDataSourceSettingsRequest {
  tushare_token?: string;
  clear_tushare_token?: boolean;
}

export interface JoinQuantExportRequest {
  portfolio_id: string;
  signal_date?: string | null;
  strategy_id?: string | null;
  risk_notice?: string;
  require_approved?: boolean;
}

export interface JoinQuantValidation {
  status: "ok" | "blocked" | string;
  checked_count: number;
  error_count: number;
  warning_count: number;
  errors: string[];
  warnings: string[];
}

export interface JoinQuantPreflightResponse {
  portfolio_id: string;
  signal_date: string;
  validation: JoinQuantValidation;
  copy_ready: boolean;
  research_only: boolean;
  live_trading: boolean;
}

export interface JoinQuantStrategyCodeResponse {
  status: string;
  export_type: string;
  portfolio_id: string;
  signal_date: string;
  strategy_id: string;
  filename: string;
  python_code: string;
  risk_notice: string;
  validation: JoinQuantValidation;
  copy_ready: boolean;
  manual_confirmation_required: boolean;
  research_only: boolean;
  live_trading: boolean;
}

export interface JoinQuantPackageFile {
  filename: string;
  content_type: string;
  content: string;
}

export interface JoinQuantPackageManifestFile {
  filename: string;
  content_type: string;
  size: number;
}

export interface JoinQuantPackageManifest {
  package_type: string;
  strategy_id: string;
  portfolio_id: string;
  signal_date: string;
  valid_for: string;
  target_count: number;
  total_exposure: number;
  files: JoinQuantPackageManifestFile[];
  manual_confirmation_required: boolean;
  live_trading: boolean;
}

export interface JoinQuantCopyPackageResponse {
  status: string;
  export_type: string;
  portfolio_id: string;
  signal_date: string;
  strategy_id: string;
  manifest: JoinQuantPackageManifest;
  files: JoinQuantPackageFile[];
  clipboard_text: string;
  validation: JoinQuantValidation;
  copy_ready: boolean;
  manual_confirmation_required: boolean;
  research_only: boolean;
  live_trading: boolean;
}

export interface JoinQuantExecutionReportImportRequest {
  portfolio_id: string;
  signal_date?: string | null;
  trade_date?: string | null;
  replace?: boolean;
  reports: Record<string, unknown>[];
}

export interface JoinQuantExecutionReportQuery {
  portfolio_id?: string;
  signal_date?: string | null;
  trade_date?: string | null;
  limit?: number;
}

export interface JoinQuantExecutionReportSummaryQuery {
  portfolio_id: string;
  signal_date?: string | null;
  trade_date?: string | null;
  tolerance?: number;
}

export interface JoinQuantExecutionReport {
  report_id: string;
  signal_date: string;
  trade_date: string;
  portfolio_id: string;
  ticker: string;
  planned_weight: number;
  executed_weight: number;
  order_status: string;
  fill_price?: number | null;
  fill_amount?: number | null;
  error_message?: string | null;
  raw_report?: string;
  created_at?: string;
}

export interface JoinQuantExecutionDeviation {
  ticker: string;
  planned_weight: number;
  executed_weight: number;
  abs_weight_diff: number;
  order_status: string;
  matched_signal: boolean;
  needs_review: boolean;
}

export interface JoinQuantExecutionReportSummary {
  status: "ok" | "needs_review" | string;
  portfolio_id: string;
  signal_date: string;
  trade_date: string;
  report_count: number;
  signal_count: number;
  matched_signal_count: number;
  failed_count: number;
  unmatched_report_count: number;
  missing_report_count: number;
  total_planned_weight: number;
  total_executed_weight: number;
  max_abs_weight_diff: number;
  total_abs_weight_diff: number;
  tolerance: number;
  status_counts: Record<string, number>;
  unmatched_reports: string[];
  missing_reports: string[];
  deviations: JoinQuantExecutionDeviation[];
  action_required: boolean;
  research_only: boolean;
  live_trading: boolean;
}

export interface JoinQuantExecutionReportImportResponse {
  status: string;
  imported_count: number;
  portfolio_id: string;
  signal_date: string;
  trade_date: string;
  replace: boolean;
  reports: JoinQuantExecutionReport[];
  summary: JoinQuantExecutionReportSummary;
  research_only: boolean;
  live_trading: boolean;
}

export interface JoinQuantExecutionReportListResponse {
  status: string;
  count: number;
  reports: JoinQuantExecutionReport[];
}

export interface JoinQuantSimulationReadinessQuery {
  portfolio_id: string;
  lookback_days?: number;
  min_batches?: number;
  tolerance?: number;
  max_failed_rate?: number;
  max_missing_rate?: number;
  max_deviation_rate?: number;
  max_signal_delay_days?: number;
}

export interface JoinQuantReadinessCheck {
  name: string;
  status: "pass" | "warning" | "fail" | string;
  observed: number;
  threshold: number;
  message: string;
}

export interface JoinQuantReadinessBacktestRisk {
  status: "ok" | "unknown" | "needs_review" | string;
  run_count: number;
  worst_max_drawdown: number;
  avg_sharpe: number;
  avg_trade_count: number;
  message: string;
}

export interface JoinQuantReadinessDailySummary {
  signal_date: string;
  trade_date: string;
  status: string;
  report_count: number;
  signal_count: number;
  failed_count: number;
  missing_report_count: number;
  unmatched_report_count: number;
  max_abs_weight_diff: number;
  total_abs_weight_diff: number;
  deviation_count: number;
  signal_delay_days: number;
  action_required: boolean;
}

export interface JoinQuantSimulationReadinessReport {
  status: "ready" | "needs_more_data" | "needs_review" | string;
  recommendation: "continue_simulation" | "extend_observation" | "fix_before_live" | string;
  readiness_score: number;
  portfolio_id: string;
  lookback_days: number;
  window_start: string;
  window_end: string;
  tolerance: number;
  min_batches: number;
  observed_batch_count: number;
  signal_batch_count: number;
  missing_signal_batch_count: number;
  totals: {
    report_count: number;
    signal_count: number;
    failed_count: number;
    missing_report_count: number;
    unmatched_report_count: number;
    deviation_count: number;
    limit_or_suspend_issue_count: number;
    total_abs_weight_diff: number;
    max_abs_weight_diff: number;
    avg_signal_delay_days: number;
    max_signal_delay_days: number;
  };
  rates: {
    failed_rate: number;
    missing_report_rate: number;
    unmatched_report_rate: number;
    deviation_rate: number;
  };
  backtest_risk: JoinQuantReadinessBacktestRisk;
  checks: JoinQuantReadinessCheck[];
  findings: string[];
  daily_summaries: JoinQuantReadinessDailySummary[];
  research_only: boolean;
  live_trading: boolean;
}

export type DailyWorkflowStepName =
  | "collect_documents"
  | "extract_events"
  | "map_events"
  | "score_sectors"
  | "build_candidates"
  | "seed_strategy_specs"
  | "run_backtests"
  | "rank_backtests"
  | "allocate_portfolio"
  | "generate_draft_signals"
  | "calculate_event_reactions";

export interface DailyWorkflowDocumentPayload {
  source_id: string;
  title: string;
  content: string;
  publish_time: string;
  summary?: string | null;
  crawl_time?: string | null;
  url?: string | null;
  language?: string;
  author_or_account?: string | null;
  hot_rank?: number | null;
  hot_value?: number | null;
  raw_json?: Record<string, unknown> | null;
}

export interface DailyWorkflowRunRequest {
  workflow_date?: string | null;
  portfolio_id: string;
  steps?: DailyWorkflowStepName[] | null;
  documents?: DailyWorkflowDocumentPayload[];
  dry_run?: boolean;
  continue_on_error?: boolean;
  event_limit?: number;
  min_event_relevance?: number;
  map_limit?: number;
  min_mapping_relevance?: number;
  sector_limit?: number;
  candidate_limit?: number;
  min_sector_score?: number;
  seed_strategy_specs?: boolean;
  backtest_start_date?: string | null;
  backtest_end_date?: string | null;
  backtest_limit?: number;
  ranking_limit?: number;
  top_n?: number;
  market_regime?: string;
  current_drawdown?: number;
  signal_confidence?: number;
  replace_signals?: boolean;
  event_reaction_windows?: EventReactionWindow[] | null;
  event_reaction_target_types?: EventReactionTargetType[] | null;
  event_reaction_limit?: number;
  replace_event_reactions?: boolean;
}

export interface DailyWorkflowStepResult {
  name: DailyWorkflowStepName | string;
  status: "ok" | "skipped" | "blocked" | "planned" | string;
  message: string;
  metrics: Record<string, unknown>;
}

export interface DailyWorkflowRunResponse {
  status: "ok" | "blocked" | "dry_run" | string;
  workflow_date: string;
  portfolio_id: string;
  requested_steps: DailyWorkflowStepName[];
  completed_step_count: number;
  skipped_step_count: number;
  blocked_step?: string | null;
  steps: DailyWorkflowStepResult[];
  research_only: boolean;
  live_trading: boolean;
}

export interface StrategyTemplate {
  strategy_type: string;
  template_name: string;
  description: string;
  signal_rules: string[];
  risk_notes: string[];
  default_rebalance_freq: string;
  default_holding_period: number;
  default_max_position: number;
  default_max_sector_exposure: number;
  default_max_total_exposure: number;
  default_stop_loss: number;
  default_take_profit: number;
}

export interface StrategyTemplateListResponse {
  templates: StrategyTemplate[];
  template_count: number;
}

export interface StrategySpecSeedRequest {
  replace?: boolean;
}

export interface StrategySpecSeedResponse {
  status: string;
  template_count: number;
  variant_count: number;
  strategy_specs_written: number;
  strategy_specs_skipped: number;
  total_expected_specs: number;
}

export interface StrategySpecQuery {
  strategy_type?: string | null;
  enabled?: boolean | null;
  limit?: number;
}

export interface StrategySpec {
  strategy_id: string;
  strategy_name: string;
  market: string;
  strategy_type: string;
  params: Record<string, unknown>;
  rebalance_freq: string;
  holding_period: number;
  max_position: number;
  max_sector_exposure: number;
  max_total_exposure: number;
  stop_loss: number;
  take_profit: number;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface StrategySpecListResponse {
  strategy_specs: StrategySpec[];
  spec_count: number;
}

export interface BacktestBatchRequest {
  start_date: string;
  end_date: string;
  as_of_date?: string | null;
  strategy_ids?: string[] | null;
  limit?: number;
  benchmark?: string;
}

export interface BacktestRun {
  run_id: string;
  strategy_id: string;
  market: string;
  start_date?: string | null;
  end_date?: string | null;
  universe_id?: string | null;
  benchmark: string;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  win_rate: number;
  profit_loss_ratio: number;
  turnover: number;
  trade_count: number;
  avg_holding_days: number;
  excess_return: number;
  information_ratio: number;
  status: string;
  artifacts_path?: string | null;
  created_at?: string | null;
}

export interface BacktestBatchResponse {
  status: string;
  as_of_date: string;
  start_date: string;
  end_date: string;
  runs_written: number;
  top_runs: BacktestRun[];
}

export interface BacktestRunQuery {
  strategy_id?: string | null;
  status?: string | null;
  limit?: number;
}

export interface BacktestRunListResponse {
  backtest_runs: BacktestRun[];
  run_count: number;
}

export interface BacktestRankingQuery {
  strategy_type?: string | null;
  status?: string | null;
  min_score?: number | null;
  limit?: number;
}

export interface BacktestRanking extends BacktestRun {
  strategy_name: string;
  sample_days: number;
  strategy_type: string;
  params: Record<string, unknown>;
  rebalance_freq: string;
  holding_period: number;
  strategy_score: number;
  risk_score: number;
  score_components: Record<string, number>;
  recommendation: string;
  reason: string;
  rank: number;
  research_only: boolean;
  live_trading: boolean;
}

export interface BacktestRankingResponse {
  rankings: BacktestRanking[];
  ranking_count: number;
  scoring_model: Record<string, unknown>;
  research_only: boolean;
  live_trading: boolean;
}

export type MarketRegime = "strong_trend" | "normal" | "weak" | "extreme_risk" | string;

export interface PortfolioAllocateRequest {
  portfolio_id?: string;
  as_of_date?: string | null;
  top_n?: number;
  market_regime?: MarketRegime;
  current_drawdown?: number;
  signal_confidence?: number;
  max_strategy_weight?: number;
  min_strategy_weight?: number;
  max_strategy_type_weight?: number;
  min_strategy_score?: number;
}

export interface PortfolioAllocation {
  as_of_date?: string | null;
  portfolio_id: string;
  strategy_id: string;
  strategy_score: number;
  risk_score: number;
  volatility: number;
  correlation_penalty: number;
  allocated_weight: number;
  reason: string;
  created_at?: string | null;
  strategy_name: string;
  strategy_type: string;
}

export interface PortfolioRiskRule {
  threshold: number;
  action: string;
  triggered: boolean;
}

export interface PortfolioAllocationResponse {
  status: "draft" | "risk_off" | string;
  portfolio_id: string;
  as_of_date: string;
  market_regime: string;
  model_total_exposure: number;
  allocated_exposure: number;
  cash_weight: number;
  allocation_count: number;
  strategy_allocations: PortfolioAllocation[];
  constraints: Record<string, unknown>;
  risk_rules: PortfolioRiskRule[];
  requires_human_confirmation: boolean;
  research_only: boolean;
  live_trading: boolean;
}

export interface PortfolioAllocationQuery {
  portfolio_id?: string | null;
  as_of_date?: string | null;
  limit?: number;
}

export interface PortfolioAllocationListResponse {
  strategy_allocations: PortfolioAllocation[];
  allocation_count: number;
}

export interface PortfolioTradePlanQuery {
  portfolio_id?: string | null;
  as_of_date?: string | null;
  max_single_stock_weight?: number;
  max_sector_weight?: number;
}

export interface PortfolioTargetPosition {
  ticker: string;
  ticker_name: string;
  target_weight: number;
  current_weight: number;
  action: string;
  strategy_sources: string[];
  theme?: string | null;
  sector_id?: string | null;
  sector_name?: string | null;
  reason: string;
  risk: string;
}

export interface PortfolioTradePlanResponse {
  status: string;
  portfolio_id: string;
  as_of_date: string;
  target_total_exposure: number;
  strategy_allocated_exposure: number;
  cash_weight: number;
  strategy_allocations: PortfolioAllocation[];
  target_positions: PortfolioTargetPosition[];
  risk_limits: {
    max_single_stock_weight: number;
    max_sector_weight: number;
  };
  requires_human_confirmation: boolean;
  approval_status: string;
  research_only: boolean;
  live_trading: boolean;
}

export type CandidateIncludedFilter = "all" | "included" | "excluded";

export interface CandidatePoolQuery {
  as_of_date?: string | null;
  limit?: number;
  source?: string | null;
  included?: boolean | null;
  min_score?: number;
}

export interface CandidateRecord {
  as_of_date?: string | null;
  ticker: string;
  ticker_name: string;
  market?: string;
  source: string;
  sector_id?: string | null;
  sector_name?: string | null;
  theme?: string | null;
  event_heat_score: number;
  sector_heat_score: number;
  stock_score: number;
  user_priority?: number;
  risk_flag: string;
  included: boolean;
  reason: string;
  created_at?: string | null;
}

export interface CandidatePoolListResponse {
  candidates: CandidateRecord[];
  candidate_count: number;
}

export interface CandidatePoolBuildRequest {
  as_of_date?: string | null;
  limit?: number;
  min_sector_score?: number;
}

export interface CandidatePoolBuildResponse {
  status: string;
  as_of_date: string;
  rows_written: number;
  candidate_count: number;
  candidates: CandidateRecord[];
}

export interface UserCandidateRequest {
  ticker: string;
  ticker_name?: string | null;
  as_of_date?: string | null;
  theme?: string | null;
  sector_id?: string | null;
  sector_name?: string | null;
  reason?: string | null;
  user_priority?: number;
}

export interface CandidateDecisionRequest {
  ticker: string;
  as_of_date?: string | null;
  reason?: string | null;
}

export type EventReactionWindow = "T+1" | "T+5" | "T+20" | "T+60";
export type EventReactionTargetType = "sector" | "stock";

export interface EventReactionCalculateRequest {
  event_id?: string | null;
  cluster_id?: string | null;
  windows?: EventReactionWindow[] | null;
  target_types?: EventReactionTargetType[] | null;
  limit?: number;
  replace?: boolean;
}

export interface EventReactionCalculateResponse {
  status: string;
  requested_targets: number;
  windows: EventReactionWindow[];
  target_types: EventReactionTargetType[];
  reactions_written: number;
  skipped_existing: number;
  skipped_insufficient_data: number;
  research_only: boolean;
  live_trading: boolean;
}

export interface EventReactionQuery {
  event_id?: string | null;
  cluster_id?: string | null;
  target_type?: EventReactionTargetType | string | null;
  target_id?: string | null;
  window?: EventReactionWindow | string | null;
  limit?: number;
}

export interface EventReactionRecord {
  reaction_id: string;
  cluster_id: string;
  event_id: string;
  target_type: EventReactionTargetType | string;
  target_id: string;
  target_name: string;
  window: EventReactionWindow | string;
  raw_return: number | null;
  benchmark_return: number | null;
  sector_return: number | null;
  abnormal_return: number | null;
  max_drawdown: number | null;
  volume_change: number | null;
  breadth_change: number | null;
  calculated_at?: string | null;
}

export interface EventReactionListResponse {
  status: string;
  reactions: EventReactionRecord[];
  reaction_count: number;
}

export interface EventReactionSummaryQuery {
  event_subtype?: string | null;
  target_type?: EventReactionTargetType | string | null;
  target_id?: string | null;
  window?: EventReactionWindow | string | null;
}

export interface EventReactionSummaryRow {
  target_type: EventReactionTargetType | string;
  window: EventReactionWindow | string;
  reaction_count: number;
  avg_raw_return: number | null;
  avg_benchmark_return: number | null;
  avg_sector_return: number | null;
  avg_abnormal_return: number | null;
  avg_max_drawdown: number | null;
  avg_volume_change: number | null;
  avg_breadth_change: number | null;
}

export interface EventReactionSummaryResponse {
  status: string;
  event_subtype?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  window: EventReactionWindow | string;
  summaries: EventReactionSummaryRow[];
  summary_count: number;
  research_only: boolean;
  live_trading: boolean;
}

// --- Types matching backend API contracts ---

export interface RunListItem {
  run_id: string;
  status: string;
  created_at: string;
  prompt?: string;
  total_return?: number;
  sharpe?: number;
  codes?: string[];
  start_date?: string;
  end_date?: string;
}

export interface RunDetailParams {
  chart_payload?: "summary";
  chart_symbol?: string;
}

export interface PriceBar {
  time: string;
  timestamp?: string;
  code?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeMarker {
  time: string;
  timestamp?: string;
  code?: string;
  side: "BUY" | "SELL";
  price: number;
  qty?: number;
  reason?: string;
  text?: string;
}

export interface EquityPoint {
  time: string;
  equity: string | number;
  drawdown: string | number;
}

export interface ValidationData {
  monte_carlo?: {
    actual_sharpe: number;
    actual_max_dd: number;
    p_value_sharpe: number;
    p_value_max_dd: number;
    simulated_sharpe_mean: number;
    simulated_sharpe_std: number;
    simulated_sharpe_p5: number;
    simulated_sharpe_p95: number;
    n_simulations: number;
    n_trades: number;
    error?: string;
  };
  bootstrap?: {
    observed_sharpe: number;
    ci_lower: number;
    ci_upper: number;
    median_sharpe: number;
    prob_positive: number;
    confidence: number;
    n_bootstrap: number;
    error?: string;
  };
  walk_forward?: {
    n_windows: number;
    windows: Array<{
      window: number;
      start: string;
      end: string;
      return: number;
      sharpe: number;
      max_dd: number;
      trades: number;
      win_rate: number;
    }>;
    profitable_windows: number;
    consistency_rate: number;
    return_mean: number;
    return_std: number;
    sharpe_mean: number;
    sharpe_std: number;
    error?: string;
  };
}

export interface RunData {
  status: string;
  run_id: string;
  prompt?: string;
  elapsed_seconds?: number;
  run_directory?: string;
  run_stage?: string;
  run_context?: Record<string, unknown>;

  metrics?: BacktestMetrics;
  artifacts?: ArtifactInfo[];
  run_card?: RunCard;
  validation?: ValidationData;

  chart_symbols?: string[];
  price_series?: Record<string, PriceBar[]>;
  indicator_series?: Record<string, Record<string, IndicatorPoint[]>>;
  trade_markers?: TradeMarker[];
  equity_curve?: EquityPoint[];
  trade_log?: Array<Record<string, string>>;
  run_logs?: Array<{ source?: string; line_number?: number; message?: string }>;
}

export interface RunCard {
  schema_version?: string;
  generated_at?: string;
  run_dir?: string;
  backtest?: Record<string, unknown>;
  reproducibility?: Record<string, unknown>;
  data_sources?: string[];
  metrics?: Record<string, unknown>;
  validation?: unknown;
  warnings?: string[];
  artifacts?: RunCardArtifact[];
  [key: string]: unknown;
}

export interface RunCardArtifact {
  path: string;
  size_bytes: number;
  sha256: string;
}

export interface BacktestMetrics {
  final_value: number;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe: number;
  win_rate: number;
  trade_count: number;
  [key: string]: number;
}


export interface IndicatorPoint {
  time: string;
  value: number;
}

export interface ArtifactInfo {
  name: string;
  path: string;
  type: string;
  size: number;
  exists: boolean;
}

export interface PineScriptResult {
  exists: boolean;
  content: string | null;
}

export interface SessionItem {
  session_id: string;
  title?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  last_attempt_id?: string;
}

// --- Goal types ---

export type GoalStatus =
  | "active"
  | "paused"
  | "waiting_user"
  | "needs_refresh"
  | "insufficient_evidence"
  | "compliance_blocked"
  | "blocked"
  | "budget_limited"
  | "usage_limited"
  | "complete"
  | "cancelled"
  | "superseded";

export type GoalRiskTier =
  | "research_general"
  | "market_specific_short_term"
  | "personalized_advice_or_position_sizing";

export interface GoalRecord {
  goal_id: string;
  session_id: string;
  status: GoalStatus;
  objective: string;
  ui_summary: string;
  source: string;
  protocol: string;
  risk_tier: GoalRiskTier;
  token_budget?: number | null;
  tokens_used: number;
  turn_budget?: number | null;
  turns_used: number;
  time_budget_seconds?: number | null;
  time_used_seconds: number;
  budget_wrapup_sent: boolean;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  recap?: string | null;
}

export interface GoalClaim {
  claim_id: string;
  goal_id: string;
  session_id: string;
  claim_type: string;
  text: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GoalCriterion {
  criterion_id: string;
  goal_id: string;
  session_id: string;
  text: string;
  required: boolean;
  status: string;
  freshness_requirement?: string | null;
  protocol_step?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GoalEvidence {
  evidence_id: string;
  goal_id: string;
  session_id: string;
  text: string;
  criterion_id?: string | null;
  claim_id?: string | null;
  evidence_type: string;
  tool_call_id?: string | null;
  run_id?: string | null;
  source_provider?: string | null;
  source_type?: string | null;
  source_uri?: string | null;
  symbol_universe: string[];
  benchmark: string[];
  timeframe?: string | null;
  method?: string | null;
  assumptions: Record<string, unknown>;
  artifact_path?: string | null;
  artifact_hash?: string | null;
  retrieved_at: string;
  data_as_of?: string | null;
  freshness_status: string;
  verification_status: string;
  confidence?: string | null;
  caveat?: string | null;
  contradicts_claim_ids: string[];
  created_at: string;
}

export interface GoalSnapshot {
  goal: GoalRecord;
  claims: GoalClaim[];
  criteria: GoalCriterion[];
  evidence: GoalEvidence[];
  evidence_count: number;
}

export interface CreateGoalRequest {
  objective: string;
  criteria?: string[];
  ui_summary?: string;
  protocol?: string;
  risk_tier?: GoalRiskTier;
  token_budget?: number;
  turn_budget?: number;
  time_budget_seconds?: number;
}

export interface AddGoalEvidenceRequest {
  goal_id: string;
  expected_goal_id: string;
  text: string;
  criterion_id?: string | null;
  claim_id?: string | null;
  evidence_type?: string;
  tool_call_id?: string | null;
  run_id?: string | null;
  source_provider?: string | null;
  source_type?: string | null;
  source_uri?: string | null;
  symbol_universe?: string[];
  benchmark?: string[];
  timeframe?: string | null;
  method?: string | null;
  assumptions?: Record<string, unknown>;
  artifact_path?: string | null;
  artifact_hash?: string | null;
  data_as_of?: string | null;
  confidence?: string | null;
  caveat?: string | null;
  contradicts_claim_ids?: string[];
}

export interface UpdateGoalRequest {
  goal_id: string;
  expected_goal_id: string;
  objective?: string;
  ui_summary?: string;
}

export interface UpdateGoalResponse {
  goal: GoalRecord;
  snapshot: GoalSnapshot;
}

export interface AddGoalEvidenceResponse {
  evidence: GoalEvidence;
  snapshot: GoalSnapshot;
}

export interface GoalAuditRowRequest {
  criterion_id: string;
  result: string;
  evidence_ids?: string[];
  notes?: string;
}

export interface UpdateGoalStatusRequest {
  goal_id: string;
  expected_goal_id: string;
  status: GoalStatus;
  audit?: GoalAuditRowRequest[];
  recap?: string | null;
}

export interface UpdateGoalStatusResponse {
  goal: GoalRecord;
  snapshot: GoalSnapshot;
}

// --- Alpha Zoo types ---

export interface AlphaListParams {
  zoo?: string;
  theme?: string;
  universe?: string;
  limit?: number;
}

export interface AlphaSummary {
  id: string;
  zoo: string;
  theme: string[];
  universe: string[];
  nickname?: string;
  decay_horizon?: number | null;
  min_warmup_bars?: number | null;
  requires_sector?: boolean;
}

export interface AlphaListResponse {
  status: string;
  alphas: AlphaSummary[];
  total: number;
  returned: number;
  truncated: boolean;
}

export interface AlphaDetail {
  id: string;
  zoo: string;
  module_path?: string;
  meta: Record<string, unknown>;
}

export interface AlphaDetailResponse {
  status: string;
  alpha: AlphaDetail;
  source_code: string;
}

export interface AlphaBenchRequest {
  zoo: string;
  universe: string;
  period: string;
  top?: number;
}

export interface AlphaBenchTopRow {
  id: string;
  ic_mean: number;
  ir: number;
  theme: string[];
  formula_latex: string;
  category: "alive" | "reversed" | "dead";
}

export interface AlphaBenchResult {
  alive: number;
  reversed: number;
  dead: number;
  skipped?: number;
  top5_by_ir: AlphaBenchTopRow[];
  dead_examples: AlphaBenchTopRow[];
  by_theme: Record<string, { alive: number; reversed: number; dead: number }>;
}

export interface AlphaCompareRequest {
  alpha_ids: string[];
  universe: string;
  period: string;
  /** One of: ir | ic_mean | ic_positive_ratio | ic_count (default ir). */
  sort?: string;
}

export interface AlphaCompareRow {
  rank: number;
  id: string;
  zoo: string;
  ic_mean: number;
  ic_std: number;
  ir: number;
  ic_positive_ratio: number;
  ic_count: number;
  /** `delta_<sort>_vs_best` — gap to the top-ranked alpha on the active metric. */
  [deltaKey: string]: number | string;
}

export interface AlphaCompareSkip {
  id: string;
  reason: string;
}

export interface AlphaCompareResult {
  universe: string;
  period: string;
  sort: string;
  n_compared: number;
  n_skipped: number;
  winner: string;
  ranking: AlphaCompareRow[];
  skipped: AlphaCompareSkip[];
}

// --- Connector runtime channel types ---

/** One mandate profile inside a `mandate.proposal` event (SPEC Consent §1). */
export interface MandateProfile {
  ordinal: number;
  label: string;
  /** Concrete ticker list, or a structural universe descriptor (e.g. "tech_sector"). */
  universe: string[] | string;
  max_order_usd: number;
  daily_trade_cap: number;
  /** "none" for cash-only, otherwise a leverage descriptor/multiple. */
  leverage: string | number;
  instruments: string[];
  notes?: string;
}

/** Account block of a `mandate.proposal` event. */
export interface MandateProposalAccount {
  broker: string;
  type: string;
  funded_by: string;
}

/** Payload of the `mandate.proposal` SSE event (SPEC Consent §1). */
export interface MandateProposal {
  type?: string;
  proposal_id: string;
  session_id?: string;
  intent_normalized?: string;
  account?: MandateProposalAccount;
  ceilings_ref?: string;
  profiles: MandateProfile[];
  funding_note?: string;
  halt_note?: string;
  /** Present only when this proposal was triggered by a mandate breach (SPEC Consent §3). */
  reauth_for?: { breach_id?: string } | null;
}

/** Payload of the `mandate.committed` SSE event (SPEC Consent §1 COMMIT). */
export interface MandateCommitted {
  proposal_id?: string;
  mandate_id?: string;
  consent_record_id?: string;
  selected_ordinal?: number;
  broker?: string;
  /** Resolved limits, surfaced for the compact active-mandate badge. */
  max_order_usd?: number;
  daily_trade_cap?: number;
  expires_at?: string;
}

/** Payload of the `live.halted` SSE event (SPEC Consent §4). */
export interface LiveHalted {
  broker?: string | null;
  tripped_at?: string;
  by?: string;
  reason?: string;
}

/** Payload of the `live.action` SSE event (SPEC Consent §5 audit notify). */
export interface LiveAction {
  audit_id?: string;
  ts?: string;
  kind: string;
  intent_normalized?: string;
  outcome?: string;
  broker?: string;
  remote_tool?: string;
  error?: string | null;
}

export interface CommitMandateRequest {
  broker: string;
  proposal_id: string;
  selected_ordinal: number;
  /** Present only on the adjust path (SPEC Consent §3); null otherwise. */
  adjustments?: Record<string, unknown> | null;
  /** Explicit affirmative consent; the surface sets it on the user's click. */
  consent_ack: boolean;
  session_id?: string;
  account_ref?: string;
  lifetime_days?: number;
}

export interface CommitMandateResponse {
  mandate_id: string;
  consent_record_id: string;
  selected_ordinal?: number;
  broker?: string;
  max_order_usd?: number;
  daily_trade_cap?: number;
  expires_at?: string;
}

export interface HaltLiveResponse {
  halted: boolean;
  broker?: string | null;
  reason: string;
  sentinel: string;
}

export interface LiveAuthorizeRequest {
  broker: string;
}

export interface LiveAuthorizeResponse {
  broker: string;
  connector_profile: string;
  oauth_token_present: boolean;
  instruction: string;
  note?: string;
}

/** Mandate limits surfaced inside a `GET /live/status` broker entry (SPEC §7.5). */
export interface LiveMandateLimits {
  max_order_notional_usd?: number;
  max_total_exposure_usd?: number;
  max_leverage?: number;
  max_trades_per_day?: number;
  allowed_instruments?: string[];
  account_funding_usd?: number;
  [key: string]: unknown;
}

/** Active mandate block of a `GET /live/status` broker entry. */
export interface LiveMandateStatus {
  broker?: string;
  mandate_id?: string;
  account_ref?: string;
  created_at?: string;
  limits?: LiveMandateLimits;
  /** ISO timestamp the mandate auto-expires (SPEC §7.5 #7 proactive expiry). */
  expires_at?: string;
  expires_in_seconds?: number | null;
  expired?: boolean;
}

/** Runner liveness block of a `GET /live/status` broker entry (SPEC §7.5 #3). */
export interface LiveRunnerLiveness {
  broker?: string;
  alive: boolean;
  /** Unix epoch seconds of the last heartbeat tick; null if the runner never started. */
  last_tick?: number | string | null;
  last_tick_age_seconds?: number | null;
}

export interface LiveBrokerAuthStatus {
  broker: string;
  oauth_token_present: boolean;
  is_live_broker: boolean;
}

/** One broker entry in the `GET /live/status` response. */
export interface LiveBrokerStatus {
  auth: LiveBrokerAuthStatus;
  mandate?: LiveMandateStatus | null;
  runner: LiveRunnerLiveness;
  halted: boolean;
}

/** Response of `GET /live/status` (SPEC §7.5 runner status panel + C2). */
export interface LiveStatus {
  brokers: LiveBrokerStatus[];
  global_halted: boolean;
}

/** Response of `POST /live/runner/start|stop`. */
export interface LiveRunnerResponse {
  broker: string;
  started?: boolean;
  already_running?: boolean;
  stopped?: boolean;
  was_running?: boolean;
}

export interface MessageItem {
  message_id: string;
  session_id: string;
  role: string;
  content: string;
  created_at: string;
  linked_attempt_id?: string;
  metadata?: Record<string, unknown>;
}
