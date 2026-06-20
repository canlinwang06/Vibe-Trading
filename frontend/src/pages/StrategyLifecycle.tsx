import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  History,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  ApiError,
  api,
  type StrategyLifecycleOverviewResponse,
  type StrategyLifecycleStrategy,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const sampleOverview: StrategyLifecycleOverviewResponse = {
  status: "ok",
  data_mode: "sample",
  funnel: [
    { state: "idea", label: "想法", count: 3 },
    { state: "candidate", label: "候选", count: 4 },
    { state: "backtesting", label: "回测中", count: 1 },
    { state: "backtested", label: "已回测", count: 2 },
    { state: "qualified", label: "合格", count: 2 },
    { state: "paper_trading", label: "模拟盘", count: 1 },
    { state: "paused", label: "暂停", count: 1 },
    { state: "rejected", label: "淘汰", count: 0 },
    { state: "retired", label: "退役", count: 0 },
  ],
  health_distribution: [
    { label: "稳定观察", count: 2, min_score: 70, max_score: 100 },
    { label: "继续小样本", count: 3, min_score: 55, max_score: 69.999 },
    { label: "拥挤风险", count: 1, min_score: 40, max_score: 54.999 },
    { label: "建议暂停", count: 1, min_score: 0, max_score: 39.999 },
  ],
  strategies: [
    {
      strategy_id: "sample_ai_momentum",
      idea_id: "sample_hot_momentum",
      strategy_name: "AI算力热点动量",
      theme: "AI算力",
      lifecycle_state: "paper_trading",
      health_score: 78,
      recommendation: "继续观察",
      reason: "模拟盘观察第 3 周，仍需控制仓位。",
      first_seen_date: "2026-06-02",
      last_review_date: "2026-06-20",
      paper_days: 15,
      signal_count: 6,
      backtest_count: 3,
      best_annual_return: 0.186,
      worst_max_drawdown: -0.098,
      avg_sharpe: 1.42,
      win_rate: 0.54,
      evidence: {},
      research_only: true,
      live_trading: false,
    },
    {
      strategy_id: "sample_optical_event",
      idea_id: "sample_event_confirm",
      strategy_name: "光模块事件确认",
      theme: "光模块",
      lifecycle_state: "qualified",
      health_score: 71,
      recommendation: "降权观察",
      reason: "最近拥挤度升高，建议降低观察权重。",
      first_seen_date: "2026-06-04",
      last_review_date: "2026-06-20",
      paper_days: 0,
      signal_count: 4,
      backtest_count: 2,
      best_annual_return: 0.142,
      worst_max_drawdown: -0.12,
      avg_sharpe: 1.18,
      win_rate: 0.51,
      evidence: {},
      research_only: true,
      live_trading: false,
    },
  ],
  events: [
    {
      event_id: "sample_evt_life_1",
      strategy_id: "sample_ai_momentum",
      event_time: "2026-06-02T09:30:00",
      from_state: null,
      to_state: "candidate",
      reason: "Codex 基于热点生成策略卡",
      evidence: {},
      created_by: "sample",
      research_only: true,
      live_trading: false,
    },
  ],
  recommendations: [
    {
      strategy_id: "sample_ai_momentum",
      strategy_name: "AI算力热点动量",
      recommendation: "继续观察",
      reason: "模拟盘观察第 3 周，仍需控制仓位。",
      health_score: 78,
    },
  ],
  research_only: true,
  live_trading: false,
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "策略生命周期加载失败，请检查本地服务状态。";
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 1000) / 10}%`;
}

function stateClass(state: string): string {
  if (state === "paper_trading" || state === "qualified") return "border-success/30 bg-success/5 text-success";
  if (state === "paused" || state === "rejected" || state === "retired") return "border-destructive/30 bg-destructive/5 text-destructive";
  if (state === "backtesting" || state === "backtested") return "border-primary/30 bg-primary/5 text-primary";
  return "border-warning/30 bg-warning/5 text-warning";
}

function stateText(state: string): string {
  return {
    idea: "想法",
    candidate: "候选",
    backtesting: "回测中",
    backtested: "已回测",
    qualified: "合格",
    paper_trading: "模拟盘",
    paused: "暂停",
    rejected: "淘汰",
    retired: "退役",
  }[state] || state;
}

function StrategyCard({ strategy }: { strategy: StrategyLifecycleStrategy }) {
  const metrics = [
    { label: "健康分", value: String(Math.round(strategy.health_score)) },
    { label: "回测次数", value: String(strategy.backtest_count) },
    { label: "模拟天数", value: `${strategy.paper_days} 天` },
    { label: "最大回撤", value: formatPercent(strategy.worst_max_drawdown) },
  ];

  return (
    <article className="rounded-lg border bg-background p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2">
            <span className={cn("rounded-md border px-2.5 py-1 text-xs", stateClass(strategy.lifecycle_state))}>
              {stateText(strategy.lifecycle_state)}
            </span>
            <span className="rounded-md border bg-muted/20 px-2.5 py-1 text-xs text-muted-foreground">{strategy.theme}</span>
          </div>
          <h3 className="mt-3 text-base font-semibold">{strategy.strategy_name}</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{strategy.reason}</p>
        </div>
        <div className="shrink-0 rounded-lg border bg-card px-3 py-2 text-center">
          <p className="text-[11px] text-muted-foreground">建议</p>
          <p className="mt-1 text-sm font-semibold">{strategy.recommendation}</p>
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-md border bg-card p-3">
            <dt className="text-muted-foreground">{metric.label}</dt>
            <dd className="mt-1 font-medium">{metric.value}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export function StrategyLifecycle() {
  const [overview, setOverview] = useState<StrategyLifecycleOverviewResponse>(sampleOverview);
  const [loading, setLoading] = useState<"load" | "refresh" | null>("load");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadOverview(refresh = true) {
    setLoading(refresh ? "refresh" : "load");
    setError("");
    try {
      const response = await api.getStrategyLifecycleOverview({ refresh, limit: 50 });
      setOverview(response);
      setNotice("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  }

  async function refreshLifecycle() {
    setLoading("refresh");
    setError("");
    try {
      const response = await api.refreshStrategyLifecycle();
      await loadOverview(false);
      setNotice(`已刷新 ${response.strategy_count} 条策略生命周期。`);
    } catch (err) {
      setError(errorMessage(err));
      setLoading(null);
    }
  }

  useEffect(() => {
    void loadOverview(true);
  }, []);

  const maxFunnel = useMemo(
    () => Math.max(1, ...overview.funnel.map((item) => item.count)),
    [overview.funnel],
  );
  const maxHealth = useMemo(
    () => Math.max(1, ...overview.health_distribution.map((item) => item.count)),
    [overview.health_distribution],
  );
  const topStrategies = overview.strategies.slice(0, 6);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Activity className="h-3.5 w-3.5 text-primary" />
          策略从想法到模拟盘
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight">策略生命周期</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              汇总策略卡、聚宽任务、回测结果和模拟观察状态，帮助判断策略应该继续观察、复测、降权还是暂停。
            </p>
          </div>
          <button
            type="button"
            disabled={loading !== null}
            onClick={refreshLifecycle}
            className="inline-flex h-9 w-fit items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading === "refresh" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            刷新生命周期
          </button>
        </div>
      </header>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>
      ) : null}
      {notice ? (
        <div className="flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 p-3 text-sm text-success">
          <CheckCircle2 className="mt-0.5 h-4 w-4" />
          {notice}
        </div>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">策略漏斗</h2>
          </div>
          <div className="mt-5 grid gap-4">
            {overview.funnel.map((item) => (
              <div key={item.state} className="grid grid-cols-[72px_minmax(0,1fr)_36px] items-center gap-3">
                <span className="text-sm font-medium">{item.label}</span>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(6, (item.count / maxFunnel) * 100)}%` }} />
                </div>
                <span className="text-xs font-semibold text-muted-foreground">{item.count}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">健康度分布</h2>
          </div>
          <div className="mt-5 grid gap-4">
            {overview.health_distribution.map((bucket) => (
              <div key={bucket.label} className="grid grid-cols-[88px_minmax(0,1fr)_36px] items-center gap-3">
                <span className="text-sm font-medium">{bucket.label}</span>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-success" style={{ width: `${Math.max(6, (bucket.count / maxHealth) * 100)}%` }} />
                </div>
                <span className="text-xs font-semibold text-muted-foreground">{bucket.count}</span>
              </div>
            ))}
          </div>
          <p className="mt-5 text-xs leading-5 text-muted-foreground">
            健康分不是实盘建议，只用于排序候选策略和安排复测优先级。
          </p>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">重点策略观察</h2>
          </div>
          <div className="mt-5 grid gap-4">
            {topStrategies.map((strategy) => (
              <StrategyCard key={strategy.strategy_id} strategy={strategy} />
            ))}
          </div>
        </article>

        <aside className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-warning" />
            <h2 className="text-sm font-semibold">下一步建议</h2>
          </div>
          <div className="mt-4 grid gap-3">
            {overview.recommendations.slice(0, 5).map((item) => (
              <div key={item.strategy_id} className="rounded-md border bg-background p-3">
                <p className="text-sm font-semibold">{item.strategy_name}</p>
                <p className="mt-1 text-xs text-primary">{item.recommendation} / {Math.round(item.health_score)} 分</p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">{item.reason}</p>
              </div>
            ))}
          </div>
        </aside>
      </section>

      <section className="rounded-lg border bg-card p-5">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold">状态变更记录</h2>
        </div>
        <div className="mt-5 overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">时间</th>
                <th className="px-3 py-2 font-medium">策略</th>
                <th className="px-3 py-2 font-medium">状态</th>
                <th className="px-3 py-2 font-medium">原因</th>
              </tr>
            </thead>
            <tbody>
              {overview.events.slice(0, 12).map((event) => (
                <tr key={event.event_id} className="border-t">
                  <td className="px-3 py-2 text-muted-foreground">{event.event_time?.slice(0, 10) || "-"}</td>
                  <td className="px-3 py-2 font-medium">{event.strategy_id}</td>
                  <td className="px-3 py-2 text-muted-foreground">{event.from_state ? `${stateText(event.from_state)} -> ` : ""}{stateText(event.to_state)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{event.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
