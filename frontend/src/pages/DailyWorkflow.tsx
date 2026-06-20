import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
  ListChecks,
  Loader2,
  Play,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import {
  ApiError,
  api,
  type DailyWorkflowRunRequest,
  type DailyWorkflowRunResponse,
  type DailyWorkflowStepName,
  type DailyWorkflowStepResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const WORKFLOW_STEPS: { name: DailyWorkflowStepName; label: string; hint: string }[] = [
  { name: "collect_documents", label: "采集文档", hint: "本地信息源" },
  { name: "extract_events", label: "抽取事件", hint: "结构化热点" },
  { name: "map_events", label: "事件映射", hint: "主题/板块/股票" },
  { name: "score_sectors", label: "板块评分", hint: "热度与确认" },
  { name: "build_candidates", label: "候选股票", hint: "A 股候选池" },
  { name: "prepare_joinquant_strategy", label: "聚宽策略", hint: "可复制草案" },
  { name: "seed_strategy_specs", label: "策略规格", hint: "本地模板" },
  { name: "run_backtests", label: "本地回测", hint: "可选验证" },
  { name: "rank_backtests", label: "本地排名", hint: "可选评分" },
  { name: "allocate_portfolio", label: "本地组合", hint: "可选权重" },
  { name: "generate_draft_signals", label: "本地信号", hint: "旧链路草稿" },
  { name: "calculate_event_reactions", label: "事件反应", hint: "T+1/T+5/T+20/T+60" },
];

const STEP_ORDER = new Map(WORKFLOW_STEPS.map((step, index) => [step.name, index]));

const DEFAULT_STEPS: DailyWorkflowStepName[] = [
  "collect_documents",
  "extract_events",
  "map_events",
  "score_sectors",
  "build_candidates",
  "prepare_joinquant_strategy",
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function defaultPublishTime(): string {
  return `${today()}T08:30:00+08:00`;
}

function defaultBacktestStart(): string {
  const value = new Date();
  value.setDate(value.getDate() - 30);
  return value.toISOString().slice(0, 10);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "每日工作流运行失败，请检查本地服务状态。";
}

function parseBoundedInteger(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的整数。`);
  }
  return parsed;
}

function stepLabel(name: string): string {
  return WORKFLOW_STEPS.find((step) => step.name === name)?.label ?? name;
}

function sortSteps(steps: DailyWorkflowStepName[]): DailyWorkflowStepName[] {
  return [...steps].sort((a, b) => (STEP_ORDER.get(a) ?? 999) - (STEP_ORDER.get(b) ?? 999));
}

function statusLabel(status: string): string {
  if (status === "ok") return "完成";
  if (status === "skipped") return "跳过";
  if (status === "blocked") return "阻断";
  if (status === "planned") return "计划中";
  return status;
}

function resultTitle(status: string): string {
  if (status === "ok") return "工作流已完成";
  if (status === "dry_run") return "试运行计划已生成";
  if (status === "blocked") return "工作流已阻断";
  return status;
}

function formatMetricKey(key: string): string {
  const labels: Record<string, string> = {
    inserted: "导入文档",
    duplicates: "重复文档",
    extracted: "抽取事件",
    mapped_events: "映射事件",
    scored_sectors: "评分板块",
    candidate_count: "候选股票",
    strategy_specs_written: "新增策略",
    strategy_specs_skipped: "已有策略",
    runs_written: "回测结果",
    ranking_count: "排名数量",
    allocation_count: "权重草案",
    signals_written: "聚宽草案",
    source_count: "信息源",
    document_count: "文档",
    status: "状态",
  };
  return labels[key] ?? key;
}

function formatMetricValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 10000) / 10000);
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function StepStatusIcon({ status }: { status: string }) {
  if (status === "ok") return <CheckCircle2 className="h-4 w-4 text-success" />;
  if (status === "blocked") return <AlertTriangle className="h-4 w-4 text-destructive" />;
  if (status === "skipped") return <Clock3 className="h-4 w-4 text-muted-foreground" />;
  return <Circle className="h-4 w-4 text-primary" />;
}

function StepResultCard({ step }: { step: DailyWorkflowStepResult }) {
  const metricEntries = Object.entries(step.metrics || {}).slice(0, 8);
  return (
    <article className={cn(
      "rounded-lg border bg-card p-4",
      step.status === "blocked" && "border-destructive/40 bg-destructive/5",
      step.status === "ok" && "border-success/30 bg-success/5",
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <StepStatusIcon status={step.status} />
          <div className="min-w-0">
            <h3 className="text-sm font-semibold">{stepLabel(step.name)}</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">{step.message}</p>
          </div>
        </div>
        <span className="shrink-0 rounded-md border bg-background px-2 py-1 text-xs text-muted-foreground">
          {statusLabel(step.status)}
        </span>
      </div>
      {metricEntries.length > 0 ? (
        <dl className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {metricEntries.map(([key, value]) => (
            <div key={key} className="border-l pl-3">
              <dt className="text-[11px] text-muted-foreground">{formatMetricKey(key)}</dt>
              <dd className="mt-0.5 break-words text-xs font-medium">{formatMetricValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </article>
  );
}

function ResultPanel({ result }: { result: DailyWorkflowRunResponse }) {
  const completed = result.completed_step_count;
  const total = result.steps.length || 1;
  const progress = Math.round((completed / total) * 100);

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            {result.status === "blocked" ? (
              <AlertTriangle className="h-4 w-4 text-destructive" />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-success" />
            )}
            <h2 className="text-sm font-semibold">{resultTitle(result.status)}</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {result.workflow_date} / {result.portfolio_id}
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          研究/模拟
        </span>
      </div>

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
          <span>完成 {completed}/{total}</span>
          <span>{result.blocked_step ? `阻断于 ${stepLabel(result.blocked_step)}` : `${progress}%`}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full", result.status === "blocked" ? "bg-destructive" : "bg-success")}
            style={{ width: `${Math.max(progress, result.status === "blocked" ? 8 : 0)}%` }}
          />
        </div>
      </div>

      <div className="mt-5 grid gap-3">
        {result.steps.map((step) => (
          <StepResultCard key={step.name} step={step} />
        ))}
      </div>
    </section>
  );
}

export function DailyWorkflow() {
  const [workflowDate, setWorkflowDate] = useState(today());
  const [portfolioId, setPortfolioId] = useState("cn_a_main");
  const [selectedSteps, setSelectedSteps] = useState<DailyWorkflowStepName[]>(DEFAULT_STEPS);
  const [includeDocument, setIncludeDocument] = useState(true);
  const [sourceId, setSourceId] = useState("gov_policy_cn");
  const [documentTitle, setDocumentTitle] = useState("AI 产业链事件跟踪");
  const [documentContent, setDocumentContent] = useState(
    "政策支持数据中心、光模块、服务器、液冷和半导体产业链建设，A 股 AI 算力板块景气度提升。",
  );
  const [publishTime, setPublishTime] = useState(defaultPublishTime());
  const [eventLimit, setEventLimit] = useState("100");
  const [mapLimit, setMapLimit] = useState("100");
  const [sectorLimit, setSectorLimit] = useState("10");
  const [candidateLimit, setCandidateLimit] = useState("50");
  const [backtestStartDate, setBacktestStartDate] = useState(defaultBacktestStart());
  const [backtestEndDate, setBacktestEndDate] = useState(today());
  const [backtestLimit, setBacktestLimit] = useState("12");
  const [rankingLimit, setRankingLimit] = useState("12");
  const [continueOnError, setContinueOnError] = useState(false);
  const [replaceSignals, setReplaceSignals] = useState(true);
  const [loadingAction, setLoadingAction] = useState<"run" | "dry-run" | null>(null);
  const [result, setResult] = useState<DailyWorkflowRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedStepCount = selectedSteps.length;
  const allSelected = selectedStepCount === WORKFLOW_STEPS.length;
  const usesLocalBacktest = selectedSteps.includes("run_backtests") || selectedSteps.includes("rank_backtests");
  const usesLocalSignalPipeline = selectedSteps.includes("allocate_portfolio") || selectedSteps.includes("generate_draft_signals");
  const showLocalValidationOptions = usesLocalBacktest || usesLocalSignalPipeline;

  const buildPayload = (dryRun: boolean): DailyWorkflowRunRequest => {
    if (!selectedSteps.length) {
      throw new Error("请至少选择一个工作流步骤。");
    }
    if (includeDocument && (!documentTitle.trim() || !documentContent.trim())) {
      throw new Error("文档标题和正文不能为空。");
    }
    return {
      workflow_date: workflowDate || null,
      portfolio_id: portfolioId.trim(),
      steps: selectedSteps,
      documents: includeDocument
        ? [{
            source_id: sourceId.trim(),
            title: documentTitle.trim(),
            content: documentContent.trim(),
            publish_time: publishTime.trim(),
            summary: documentTitle.trim(),
            language: "zh-CN",
          }]
        : [],
      dry_run: dryRun,
      continue_on_error: continueOnError,
      event_limit: parseBoundedInteger(eventLimit, "事件抽取上限", 1, 500),
      map_limit: parseBoundedInteger(mapLimit, "事件映射上限", 1, 500),
      sector_limit: parseBoundedInteger(sectorLimit, "板块评分上限", 1, 50),
      candidate_limit: parseBoundedInteger(candidateLimit, "候选股票上限", 1, 200),
      backtest_start_date: backtestStartDate || null,
      backtest_end_date: backtestEndDate || null,
      backtest_limit: parseBoundedInteger(backtestLimit, "回测数量", 1, 100),
      ranking_limit: parseBoundedInteger(rankingLimit, "排名数量", 1, 500),
      seed_strategy_specs: true,
      replace_signals: replaceSignals,
      event_reaction_windows: ["T+1", "T+5", "T+20", "T+60"],
      event_reaction_target_types: ["sector", "stock"],
      event_reaction_limit: 100,
      replace_event_reactions: true,
    };
  };

  const runWorkflow = async (dryRun: boolean) => {
    setError(null);
    setLoadingAction(dryRun ? "dry-run" : "run");
    try {
      const payload = buildPayload(dryRun);
      const response = await api.dailyWorkflowRun(payload);
      setResult(response);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingAction(null);
    }
  };

  const toggleStep = (step: DailyWorkflowStepName) => {
    setSelectedSteps((current) => (
      current.includes(step)
        ? current.filter((item) => item !== step)
        : sortSteps([...current, step])
    ));
  };

  const selectedLabel = useMemo(() => `${selectedStepCount}/${WORKFLOW_STEPS.length}`, [selectedStepCount]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <ListChecks className="h-3.5 w-3.5 text-primary" />
          本地研究流水线
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">每日研究工作流</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              串联情报采集、板块分析、观察股票池和聚宽策略草案；本地不执行回测，回测与模拟运行在聚宽完成。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            不本地回测 / 不审批 / 不实盘
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">运行参数</h2>
              <p className="mt-1 text-xs text-muted-foreground">已选步骤 {selectedLabel}</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedSteps(allSelected ? [] : WORKFLOW_STEPS.map((step) => step.name))}
              className="rounded-md border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {allSelected ? "清空步骤" : "全选步骤"}
            </button>
          </div>

          <div className="mt-5 grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                工作日期
                <input
                  type="date"
                  value={workflowDate}
                  onChange={(event) => setWorkflowDate(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                组合 ID
                <input
                  value={portfolioId}
                  onChange={(event) => setPortfolioId(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>

            <fieldset className="grid gap-2">
              <legend className="text-xs font-medium text-muted-foreground">工作流步骤</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {WORKFLOW_STEPS.map((step) => (
                  <label
                    key={step.name}
                    className="flex cursor-pointer items-start gap-2 rounded-md border bg-background px-3 py-2 text-sm transition-colors hover:border-primary/50"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSteps.includes(step.name)}
                      onChange={() => toggleStep(step.name)}
                      className="mt-0.5 h-4 w-4 accent-primary"
                    />
                    <span className="min-w-0">
                      <span className="block font-medium">{step.label}</span>
                      <span className="block text-xs text-muted-foreground">{step.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <fieldset className="grid gap-3 border-t pt-4">
              <legend className="text-xs font-medium text-muted-foreground">事件文档</legend>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={includeDocument}
                  onChange={(event) => setIncludeDocument(event.target.checked)}
                  className="h-4 w-4 accent-primary"
                />
                随本次运行导入 AI 产业链文档
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  信息源
                  <input
                    value={sourceId}
                    onChange={(event) => setSourceId(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  发布时间
                  <input
                    value={publishTime}
                    onChange={(event) => setPublishTime(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
              </div>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                标题
                <input
                  value={documentTitle}
                  onChange={(event) => setDocumentTitle(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                正文
                <textarea
                  value={documentContent}
                  onChange={(event) => setDocumentContent(event.target.value)}
                  rows={5}
                  className="resize-none rounded-md border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none focus:border-primary"
                />
              </label>
            </fieldset>

            <fieldset className="grid gap-3 border-t pt-4">
              <legend className="text-xs font-medium text-muted-foreground">批量参数</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  抽取上限
                  <input
                    value={eventLimit}
                    onChange={(event) => setEventLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  映射上限
                  <input
                    value={mapLimit}
                    onChange={(event) => setMapLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  板块上限
                  <input
                    value={sectorLimit}
                    onChange={(event) => setSectorLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  候选上限
                  <input
                    value={candidateLimit}
                    onChange={(event) => setCandidateLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
              </div>
            </fieldset>

            <fieldset className="grid gap-2 border-t pt-4">
              <legend className="text-xs font-medium text-muted-foreground">运行控制</legend>
              <div className="grid gap-2 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={continueOnError}
                    onChange={(event) => setContinueOnError(event.target.checked)}
                    className="h-4 w-4 accent-primary"
                  />
                  单步阻断后继续尝试后续步骤
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={replaceSignals}
                    onChange={(event) => setReplaceSignals(event.target.checked)}
                    className="h-4 w-4 accent-primary"
                  />
                  覆盖同日聚宽策略草案
                </label>
              </div>
            </fieldset>

            {showLocalValidationOptions ? (
              <fieldset className="grid gap-3 border-t pt-4">
                <legend className="text-xs font-medium text-muted-foreground">可选本地验证参数</legend>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    回测开始
                    <input
                      type="date"
                      value={backtestStartDate}
                      onChange={(event) => setBacktestStartDate(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    回测结束
                    <input
                      type="date"
                      value={backtestEndDate}
                      onChange={(event) => setBacktestEndDate(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    回测数量
                    <input
                      value={backtestLimit}
                      onChange={(event) => setBacktestLimit(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    排名数量
                    <input
                      value={rankingLimit}
                      onChange={(event) => setRankingLimit(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                </div>
              </fieldset>
            ) : null}

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                {error}
              </div>
            ) : null}

            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                disabled={loadingAction !== null}
                onClick={() => runWorkflow(false)}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loadingAction === "run" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                运行工作流
              </button>
              <button
                type="button"
                disabled={loadingAction !== null}
                onClick={() => runWorkflow(true)}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loadingAction === "dry-run" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                试运行
              </button>
            </div>
          </div>
        </section>

        <div className="grid content-start gap-5">
          <section className="rounded-lg border bg-muted/20 p-5">
            <div className="flex items-start gap-3">
              <FileText className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <h2 className="text-sm font-semibold">当前任务</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  AI 产业链事件研究：从本地文档进入事件抽取、板块分析、观察股票池和聚宽策略草案。
                </p>
              </div>
            </div>
          </section>

          {result ? (
            <ResultPanel result={result} />
          ) : (
            <section className="rounded-lg border bg-card p-8 text-center">
              <ListChecks className="mx-auto h-8 w-8 text-muted-foreground" />
              <h2 className="mt-4 text-sm font-semibold">等待运行</h2>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                结果区会显示每一步状态、阻断原因和关键指标。
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
