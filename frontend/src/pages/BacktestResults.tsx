import { useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  ApiError,
  api,
  type BacktestRankingResponse,
  type BacktestRun,
  type BacktestRunListResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "回测结果操作失败，请检查本地服务状态。";
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

function bestRun(runs: BacktestRun[]): BacktestRun | null {
  if (!runs.length) return null;
  return [...runs].sort((a, b) => b.sharpe - a.sharpe || b.total_return - a.total_return)[0];
}

function BacktestSummary({
  runs,
  rankings,
}: {
  runs: BacktestRunListResponse | null;
  rankings: BacktestRankingResponse | null;
}) {
  const topRun = bestRun(runs?.backtest_runs ?? []);
  const topRanking = rankings?.rankings?.[0] ?? null;
  return (
    <section className="grid gap-3 md:grid-cols-4">
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">回测数量</p>
        <p className="mt-2 text-2xl font-semibold">{runs?.run_count ?? 0}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">最佳 Sharpe</p>
        <p className="mt-2 text-2xl font-semibold">{topRun ? formatNumber(topRun.sharpe) : "-"}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">最高排名分</p>
        <p className="mt-2 text-2xl font-semibold">{topRanking ? formatNumber(topRanking.strategy_score) : "-"}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">当前建议</p>
        <p className="mt-2 text-lg font-semibold">{topRanking?.recommendation ?? "-"}</p>
      </div>
    </section>
  );
}

function RunTable({ runs }: { runs: BacktestRunListResponse | null }) {
  const rows = runs?.backtest_runs ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">回测结果</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">共 {runs?.run_count ?? 0} 条，按后端最新排序返回。</p>
      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[1000px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">运行</th>
                <th className="px-3 py-2 font-medium">区间</th>
                <th className="px-3 py-2 font-medium">基准</th>
                <th className="px-3 py-2 font-medium">总收益</th>
                <th className="px-3 py-2 font-medium">超额</th>
                <th className="px-3 py-2 font-medium">最大回撤</th>
                <th className="px-3 py-2 font-medium">Sharpe</th>
                <th className="px-3 py-2 font-medium">胜率</th>
                <th className="px-3 py-2 font-medium">交易数</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.run_id} className="border-t">
                  <td className="px-3 py-3">
                    <div className="font-medium">{run.run_id}</div>
                    <div className="mt-1 text-muted-foreground">{run.strategy_id}</div>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{run.start_date} 至 {run.end_date}</td>
                  <td className="px-3 py-3">{run.benchmark}</td>
                  <td className={cn("px-3 py-3 font-medium", run.total_return >= 0 ? "text-success" : "text-destructive")}>
                    {formatPercent(run.total_return)}
                  </td>
                  <td className={cn("px-3 py-3", run.excess_return >= 0 ? "text-success" : "text-destructive")}>
                    {formatPercent(run.excess_return)}
                  </td>
                  <td className="px-3 py-3 text-destructive">{formatPercent(run.max_drawdown)}</td>
                  <td className="px-3 py-3">{formatNumber(run.sharpe)}</td>
                  <td className="px-3 py-3">{formatPercent(run.win_rate)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{run.trade_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无回测结果。可以先在策略实验室运行批量回测。</p>
      )}
    </section>
  );
}

function RankingTable({ rankings }: { rankings: BacktestRankingResponse | null }) {
  const rows = rankings?.rankings ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">策略排名</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">共 {rankings?.ranking_count ?? 0} 条，仅用于研究筛选。</p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          不触发交易
        </span>
      </div>
      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[1040px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">排名</th>
                <th className="px-3 py-2 font-medium">策略</th>
                <th className="px-3 py-2 font-medium">评分</th>
                <th className="px-3 py-2 font-medium">风险</th>
                <th className="px-3 py-2 font-medium">建议</th>
                <th className="px-3 py-2 font-medium">收益</th>
                <th className="px-3 py-2 font-medium">回撤</th>
                <th className="px-3 py-2 font-medium">说明</th>
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
                  <td className={cn("px-3 py-3", row.total_return >= 0 ? "text-success" : "text-destructive")}>
                    {formatPercent(row.total_return)}
                  </td>
                  <td className="px-3 py-3 text-destructive">{formatPercent(row.max_drawdown)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无排名。可以刷新策略排名，或先运行批量回测。</p>
      )}
    </section>
  );
}

export function BacktestResults() {
  const [strategyId, setStrategyId] = useState("");
  const [strategyType, setStrategyType] = useState("");
  const [status, setStatus] = useState("completed");
  const [runLimit, setRunLimit] = useState("50");
  const [rankingLimit, setRankingLimit] = useState("20");
  const [minScore, setMinScore] = useState("");
  const [runs, setRuns] = useState<BacktestRunListResponse | null>(null);
  const [rankings, setRankings] = useState<BacktestRankingResponse | null>(null);
  const [loading, setLoading] = useState<"runs" | "rankings" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshRuns = async () => {
    setError(null);
    setNotice(null);
    setLoading("runs");
    try {
      const response = await api.listStrategyBacktestRuns({
        strategy_id: strategyId.trim() || null,
        status: status.trim() || null,
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
    setError(null);
    setNotice(null);
    setLoading("rankings");
    try {
      const response = await api.listStrategyBacktestRankings({
        strategy_type: strategyType.trim() || null,
        status: status.trim() || "completed",
        min_score: parseScore(minScore, "最低策略评分"),
        limit: parseInteger(rankingLimit, "排名上限", 1, 500),
      });
      setRankings(response);
      setNotice(`已加载 ${response.ranking_count} 条策略排名。`);
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
          <BarChart3 className="h-3.5 w-3.5 text-primary" />
          批量回测与结果验收
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">回测结果</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              查看策略实验室生成的本地回测结果、收益风险指标和策略排名，用于进入风控组合前的人工验收。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            只读验收页
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">筛选</h2>
          <div className="mt-5 grid gap-4">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              策略 ID
              <input
                value={strategyId}
                onChange={(event) => setStrategyId(event.target.value)}
                placeholder="可留空"
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              策略类型
              <input
                value={strategyType}
                onChange={(event) => setStrategyType(event.target.value)}
                placeholder="可留空"
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              状态
              <input
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                回测上限
                <input
                  value={runLimit}
                  onChange={(event) => setRunLimit(event.target.value)}
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
              <button
                type="button"
                disabled={loading !== null}
                onClick={refreshRuns}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "runs" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                刷新回测结果
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={refreshRankings}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "rankings" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                刷新策略排名
              </button>
            </div>

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
          <BacktestSummary runs={runs} rankings={rankings} />
          <RunTable runs={runs} />
          <RankingTable rankings={rankings} />
        </div>
      </div>
    </div>
  );
}
