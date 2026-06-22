import { useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  FlaskConical,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  ApiError,
  api,
  type BacktestBatchResponse,
  type BacktestRankingResponse,
  type BacktestRunListResponse,
  type StrategySpecListResponse,
  type StrategySpecSeedResponse,
  type StrategyTemplateListResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function defaultStartDate(): string {
  const current = new Date();
  current.setFullYear(current.getFullYear() - 1);
  return current.toISOString().slice(0, 10);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "策略实验室操作失败，请检查本地服务状态。";
}

function parseInteger(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的整数。`);
  }
  return parsed;
}

function parseScore(value: string, label: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) {
    throw new Error(`${label}必须是 0 到 100 之间的数字。`);
  }
  return parsed;
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 10000) / 100}%`;
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "-";
  return value.toFixed(digits);
}

function freqLabel(value: string): string {
  if (value === "daily") return "每日";
  if (value === "weekly") return "每周";
  return value || "-";
}

function TemplatePanel({ templates }: { templates: StrategyTemplateListResponse | null }) {
  const rows = templates?.templates ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <Layers className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">策略模板</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">共 {templates?.template_count ?? 0} 个标准模板。</p>
      {rows.length ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {rows.slice(0, 8).map((template) => (
            <article key={template.strategy_type} className="rounded-lg border bg-background p-4">
              <h3 className="text-sm font-semibold">{template.template_name}</h3>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{template.description}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span className="rounded-md bg-muted px-2 py-1">{freqLabel(template.default_rebalance_freq)}</span>
                <span className="rounded-md bg-muted px-2 py-1">持有 {template.default_holding_period} 日</span>
                <span className="rounded-md bg-muted px-2 py-1">总仓 {formatPercent(template.default_max_total_exposure)}</span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">点击左侧“加载模板”查看内置策略模板。</p>
      )}
    </section>
  );
}

function SpecPanel({ specs }: { specs: StrategySpecListResponse | null }) {
  const rows = specs?.strategy_specs ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <FlaskConical className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">策略规格</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">共 {specs?.spec_count ?? 0} 条，可用于批量回测。</p>
      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[860px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">策略</th>
                <th className="px-3 py-2 font-medium">类型</th>
                <th className="px-3 py-2 font-medium">调仓</th>
                <th className="px-3 py-2 font-medium">持有期</th>
                <th className="px-3 py-2 font-medium">单票上限</th>
                <th className="px-3 py-2 font-medium">总仓位</th>
                <th className="px-3 py-2 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((spec) => (
                <tr key={spec.strategy_id} className="border-t">
                  <td className="px-3 py-3">
                    <div className="font-medium">{spec.strategy_name}</div>
                    <div className="mt-1 text-muted-foreground">{spec.strategy_id}</div>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{spec.strategy_type}</td>
                  <td className="px-3 py-3">{freqLabel(spec.rebalance_freq)}</td>
                  <td className="px-3 py-3">{spec.holding_period} 日</td>
                  <td className="px-3 py-3">{formatPercent(spec.max_position)}</td>
                  <td className="px-3 py-3">{formatPercent(spec.max_total_exposure)}</td>
                  <td className="px-3 py-3">
                    <span
                      className={cn(
                        "inline-flex rounded-md px-2 py-1 text-xs",
                        spec.enabled ? "bg-success/10 text-success" : "bg-muted text-muted-foreground",
                      )}
                    >
                      {spec.enabled ? "启用" : "停用"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无策略规格。可以先生成标准规格。</p>
      )}
    </section>
  );
}

function BacktestPanel({
  batch,
  runs,
}: {
  batch: BacktestBatchResponse | null;
  runs: BacktestRunListResponse | null;
}) {
  const rows = runs?.backtest_runs ?? batch?.top_runs ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">批量回测</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {batch ? `最近写入 ${batch.runs_written} 条，区间 ${batch.start_date} 至 ${batch.end_date}` : `共 ${runs?.run_count ?? 0} 条回测。`}
      </p>
      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[900px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">运行</th>
                <th className="px-3 py-2 font-medium">收益</th>
                <th className="px-3 py-2 font-medium">年化</th>
                <th className="px-3 py-2 font-medium">最大回撤</th>
                <th className="px-3 py-2 font-medium">Sharpe</th>
                <th className="px-3 py-2 font-medium">胜率</th>
                <th className="px-3 py-2 font-medium">换手</th>
                <th className="px-3 py-2 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.run_id} className="border-t">
                  <td className="px-3 py-3">
                    <div className="font-medium">{run.run_id}</div>
                    <div className="mt-1 text-muted-foreground">{run.strategy_id}</div>
                  </td>
                  <td className="px-3 py-3 font-medium">{formatPercent(run.total_return)}</td>
                  <td className="px-3 py-3">{formatPercent(run.annual_return)}</td>
                  <td className="px-3 py-3 text-destructive">{formatPercent(run.max_drawdown)}</td>
                  <td className="px-3 py-3">{formatNumber(run.sharpe)}</td>
                  <td className="px-3 py-3">{formatPercent(run.win_rate)}</td>
                  <td className="px-3 py-3">{formatNumber(run.turnover)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{run.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无回测结果。需要先有候选池、策略规格和本地行情。</p>
      )}
    </section>
  );
}

function RankingPanel({ rankings }: { rankings: BacktestRankingResponse | null }) {
  const rows = rankings?.rankings ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">策略排名</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">共 {rankings?.ranking_count ?? 0} 条研究排名。</p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          研究/模拟
        </span>
      </div>
      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[960px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">排名</th>
                <th className="px-3 py-2 font-medium">策略</th>
                <th className="px-3 py-2 font-medium">评分</th>
                <th className="px-3 py-2 font-medium">风险</th>
                <th className="px-3 py-2 font-medium">建议</th>
                <th className="px-3 py-2 font-medium">收益</th>
                <th className="px-3 py-2 font-medium">回撤</th>
                <th className="px-3 py-2 font-medium">理由</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.run_id} className="border-t align-top">
                  <td className="px-3 py-3 font-medium">#{row.rank}</td>
                  <td className="px-3 py-3">
                    <div className="font-medium">{row.strategy_name}</div>
                    <div className="mt-1 text-muted-foreground">{row.strategy_type}</div>
                  </td>
                  <td className="px-3 py-3 font-medium">{formatNumber(row.strategy_score)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{formatNumber(row.risk_score)}</td>
                  <td className="px-3 py-3">{row.recommendation}</td>
                  <td className="px-3 py-3">{formatPercent(row.total_return)}</td>
                  <td className="px-3 py-3 text-destructive">{formatPercent(row.max_drawdown)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无排名结果。运行批量回测后可刷新排名。</p>
      )}
    </section>
  );
}

export function StrategyLab() {
  const [templates, setTemplates] = useState<StrategyTemplateListResponse | null>(null);
  const [specs, setSpecs] = useState<StrategySpecListResponse | null>(null);
  const [seedResult, setSeedResult] = useState<StrategySpecSeedResponse | null>(null);
  const [batchResult, setBatchResult] = useState<BacktestBatchResponse | null>(null);
  const [runs, setRuns] = useState<BacktestRunListResponse | null>(null);
  const [rankings, setRankings] = useState<BacktestRankingResponse | null>(null);
  const [strategyType, setStrategyType] = useState("");
  const [enabledOnly, setEnabledOnly] = useState(true);
  const [replaceSpecs, setReplaceSpecs] = useState(false);
  const [asOfDate, setAsOfDate] = useState("");
  const [startDate, setStartDate] = useState(defaultStartDate());
  const [endDate, setEndDate] = useState(today());
  const [benchmark, setBenchmark] = useState("000300.SH");
  const [specLimit, setSpecLimit] = useState("24");
  const [runLimit, setRunLimit] = useState("50");
  const [rankingLimit, setRankingLimit] = useState("20");
  const [minScore, setMinScore] = useState("");
  const [loading, setLoading] = useState<
    "templates" | "seed" | "specs" | "batch" | "runs" | "rankings" | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const clearFeedback = () => {
    setError(null);
    setNotice(null);
  };

  const loadTemplates = async () => {
    clearFeedback();
    setLoading("templates");
    try {
      const response = await api.listStrategyTemplates();
      setTemplates(response);
      setNotice(`已加载 ${response.template_count} 个策略模板。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const seedSpecs = async () => {
    clearFeedback();
    setLoading("seed");
    try {
      const response = await api.seedStrategySpecs({ replace: replaceSpecs });
      setSeedResult(response);
      setNotice(`已写入 ${response.strategy_specs_written} 条策略规格。`);
      const specResponse = await api.listStrategySpecs({
        strategy_type: strategyType.trim() || null,
        enabled: enabledOnly ? true : null,
        limit: parseInteger(specLimit, "规格上限", 1, 500),
      });
      setSpecs(specResponse);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const refreshSpecs = async () => {
    clearFeedback();
    setLoading("specs");
    try {
      const response = await api.listStrategySpecs({
        strategy_type: strategyType.trim() || null,
        enabled: enabledOnly ? true : null,
        limit: parseInteger(specLimit, "规格上限", 1, 500),
      });
      setSpecs(response);
      setNotice(`已加载 ${response.spec_count} 条策略规格。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const runBatch = async () => {
    clearFeedback();
    setLoading("batch");
    try {
      const response = await api.runStrategyBacktestBatch({
        start_date: startDate,
        end_date: endDate,
        as_of_date: asOfDate.trim() || null,
        limit: parseInteger(specLimit, "回测策略数量", 1, 100),
        benchmark: benchmark.trim() || "000300.SH",
      });
      setBatchResult(response);
      setRuns({ backtest_runs: response.top_runs, run_count: response.runs_written });
      setNotice(`已完成 ${response.runs_written} 条策略回测。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const refreshRuns = async () => {
    clearFeedback();
    setLoading("runs");
    try {
      const response = await api.listStrategyBacktestRuns({
        status: "completed",
        limit: parseInteger(runLimit, "回测上限", 1, 500),
      });
      setRuns(response);
      setNotice(`已加载 ${response.run_count} 条回测结果。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const refreshRankings = async () => {
    clearFeedback();
    setLoading("rankings");
    try {
      const response = await api.listStrategyBacktestRankings({
        strategy_type: strategyType.trim() || null,
        status: "completed",
        min_score: parseScore(minScore, "最低策略评分"),
        limit: parseInteger(rankingLimit, "排名上限", 1, 500),
      });
      setRankings(response);
      setNotice(`已生成 ${response.ranking_count} 条策略排名。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <FlaskConical className="h-3.5 w-3.5 text-primary" />
          模板化策略与参数管理
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">策略实验室</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              使用可审计模板生成策略规格，基于本地候选池和行情批量回测，再用策略排名挑选后续风控组合候选。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            研究回测，不下单
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">策略操作</h2>
          <div className="mt-5 grid gap-4">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              策略类型
              <input
                value={strategyType}
                onChange={(event) => setStrategyType(event.target.value)}
                placeholder="可留空，例如 hot_sector_equal_weight"
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                规格上限
                <input
                  value={specLimit}
                  onChange={(event) => setSpecLimit(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                排名上限
                <input
                  value={rankingLimit}
                  onChange={(event) => setRankingLimit(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              最低策略评分
              <input
                value={minScore}
                onChange={(event) => setMinScore(event.target.value)}
                placeholder="可留空"
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={enabledOnly}
                  onChange={(event) => setEnabledOnly(event.target.checked)}
                  className="h-4 w-4 accent-primary"
                />
                只看启用策略
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={replaceSpecs}
                  onChange={(event) => setReplaceSpecs(event.target.checked)}
                  className="h-4 w-4 accent-primary"
                />
                重新生成并覆盖标准规格
              </label>
            </div>
            <div className="grid gap-2">
              <button
                type="button"
                disabled={loading !== null}
                onClick={loadTemplates}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "templates" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Layers className="h-4 w-4" />}
                加载模板
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={seedSpecs}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "seed" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
                生成策略规格
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={refreshSpecs}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "specs" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                刷新规格
              </button>
            </div>

            <div className="border-t pt-4">
              <h3 className="text-xs font-semibold text-muted-foreground">批量回测</h3>
              <div className="mt-3 grid gap-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    开始日期
                    <input
                      value={startDate}
                      onChange={(event) => setStartDate(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    结束日期
                    <input
                      value={endDate}
                      onChange={(event) => setEndDate(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    候选池日期
                    <input
                      value={asOfDate}
                      onChange={(event) => setAsOfDate(event.target.value)}
                      placeholder="留空使用最新"
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    基准
                    <input
                      value={benchmark}
                      onChange={(event) => setBenchmark(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                </div>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  回测结果上限
                  <input
                    value={runLimit}
                    onChange={(event) => setRunLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <div className="grid gap-2">
                  <button
                    type="button"
                    disabled={loading !== null}
                    onClick={runBatch}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loading === "batch" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    运行批量回测
                  </button>
                  <button
                    type="button"
                    disabled={loading !== null}
                    onClick={refreshRuns}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loading === "runs" ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
                    刷新回测
                  </button>
                  <button
                    type="button"
                    disabled={loading !== null}
                    onClick={refreshRankings}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loading === "rankings" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                    刷新排名
                  </button>
                </div>
              </div>
            </div>

            {seedResult ? (
              <div className="rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
                标准规格：写入 {seedResult.strategy_specs_written}，跳过 {seedResult.strategy_specs_skipped}，预期 {seedResult.total_expected_specs}。
              </div>
            ) : null}
            {notice ? (
              <div className="rounded-lg border border-success/30 bg-success/5 p-3 text-sm text-success">
                {notice}
              </div>
            ) : null}
            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                {error}
              </div>
            ) : null}
          </div>
        </section>

        <div className="grid content-start gap-5">
          <TemplatePanel templates={templates} />
          <SpecPanel specs={specs} />
          <BacktestPanel batch={batchResult} runs={runs} />
          <RankingPanel rankings={rankings} />
        </div>
      </div>
    </div>
  );
}
