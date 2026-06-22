import { useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import {
  ApiError,
  api,
  type EventReactionCalculateResponse,
  type EventReactionListResponse,
  type EventReactionSummaryResponse,
  type EventReactionTargetType,
  type EventReactionWindow,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const WINDOW_OPTIONS: EventReactionWindow[] = ["T+1", "T+5", "T+20", "T+60"];
const TARGET_TYPES: { value: EventReactionTargetType; label: string }[] = [
  { value: "stock", label: "股票" },
  { value: "sector", label: "板块" },
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "事件反应操作失败，请检查本地服务状态。";
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 10000) / 100}%`;
}

function targetTypeLabel(value: string): string {
  if (value === "stock") return "股票";
  if (value === "sector") return "板块";
  return value;
}

function SummaryPanel({ summary }: { summary: EventReactionSummaryResponse }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">反应摘要</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {summary.event_subtype || "全部事件"} / {summary.window}
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          研究/模拟
        </span>
      </div>

      {summary.summaries.length ? (
        <div className="mt-4 overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">对象</th>
                <th className="px-3 py-2 font-medium">样本</th>
                <th className="px-3 py-2 font-medium">平均收益</th>
                <th className="px-3 py-2 font-medium">基准</th>
                <th className="px-3 py-2 font-medium">超额</th>
                <th className="px-3 py-2 font-medium">最大回撤</th>
              </tr>
            </thead>
            <tbody>
              {summary.summaries.map((row) => (
                <tr key={`${row.target_type}-${row.window}`} className="border-t">
                  <td className="px-3 py-2 font-medium">{targetTypeLabel(row.target_type)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.reaction_count}</td>
                  <td className="px-3 py-2">{formatPercent(row.avg_raw_return)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.avg_benchmark_return)}</td>
                  <td className={cn("px-3 py-2 font-medium", (row.avg_abnormal_return || 0) >= 0 ? "text-success" : "text-destructive")}>
                    {formatPercent(row.avg_abnormal_return)}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.avg_max_drawdown)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无摘要结果。</p>
      )}
    </section>
  );
}

function CalculationPanel({ result }: { result: EventReactionCalculateResponse }) {
  return (
    <section className="rounded-lg border border-success/30 bg-success/5 p-4">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-success" />
        <h2 className="text-sm font-semibold">计算完成</h2>
      </div>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div>
          <dt className="text-xs text-muted-foreground">写入反应</dt>
          <dd className="mt-1 font-medium">{result.reactions_written}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">目标数</dt>
          <dd className="mt-1 font-medium">{result.requested_targets}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">窗口</dt>
          <dd className="mt-1 font-medium">{result.windows.join(" / ")}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">数据不足跳过</dt>
          <dd className="mt-1 font-medium">{result.skipped_insufficient_data}</dd>
        </div>
      </dl>
    </section>
  );
}

function ReactionTable({ list }: { list: EventReactionListResponse }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">反应明细</h2>
          <p className="mt-1 text-xs text-muted-foreground">共 {list.reaction_count} 条</p>
        </div>
      </div>

      {list.reactions.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[900px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">窗口</th>
                <th className="px-3 py-2 font-medium">对象</th>
                <th className="px-3 py-2 font-medium">名称</th>
                <th className="px-3 py-2 font-medium">收益</th>
                <th className="px-3 py-2 font-medium">基准</th>
                <th className="px-3 py-2 font-medium">板块</th>
                <th className="px-3 py-2 font-medium">超额</th>
                <th className="px-3 py-2 font-medium">最大回撤</th>
              </tr>
            </thead>
            <tbody>
              {list.reactions.map((row) => (
                <tr key={row.reaction_id} className="border-t">
                  <td className="px-3 py-2 font-medium">{row.window}</td>
                  <td className="px-3 py-2 text-muted-foreground">{targetTypeLabel(row.target_type)}</td>
                  <td className="px-3 py-2">
                    <span className="font-medium">{row.target_name}</span>
                    <span className="ml-2 text-muted-foreground">{row.target_id}</span>
                  </td>
                  <td className="px-3 py-2">{formatPercent(row.raw_return)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.benchmark_return)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.sector_return)}</td>
                  <td className={cn("px-3 py-2 font-medium", (row.abnormal_return || 0) >= 0 ? "text-success" : "text-destructive")}>
                    {formatPercent(row.abnormal_return)}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.max_drawdown)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无反应明细。</p>
      )}
    </section>
  );
}

export function EventReactions() {
  const [eventSubtype, setEventSubtype] = useState("AI算力");
  const [targetType, setTargetType] = useState<EventReactionTargetType>("stock");
  const [targetId, setTargetId] = useState("");
  const [window, setWindow] = useState<EventReactionWindow>("T+5");
  const [limit, setLimit] = useState("100");
  const [replace, setReplace] = useState(true);
  const [calculation, setCalculation] = useState<EventReactionCalculateResponse | null>(null);
  const [summary, setSummary] = useState<EventReactionSummaryResponse | null>(null);
  const [list, setList] = useState<EventReactionListResponse | null>(null);
  const [loading, setLoading] = useState<"calculate" | "summary" | "list" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const numericLimit = () => {
    const parsed = Number(limit);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 500) {
      throw new Error("查询上限必须是 1 到 500 之间的整数。");
    }
    return parsed;
  };

  const runCalculate = async () => {
    setError(null);
    setLoading("calculate");
    try {
      const response = await api.eventReactionsCalculate({
        windows: WINDOW_OPTIONS,
        target_types: ["sector", "stock"],
        limit: numericLimit(),
        replace,
      });
      setCalculation(response);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const runSummary = async () => {
    setError(null);
    setLoading("summary");
    try {
      const response = await api.eventReactionSummary({
        event_subtype: eventSubtype.trim() || null,
        target_type: targetType,
        target_id: targetId.trim() || null,
        window,
      });
      setSummary(response);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const runList = async () => {
    setError(null);
    setLoading("list");
    try {
      const response = await api.listEventReactions({
        target_type: targetType,
        target_id: targetId.trim() || null,
        window,
        limit: numericLimit(),
      });
      setList(response);
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
          事件后表现复盘
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">事件反应研究</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              查看事件发生后股票和板块在 T+1、T+5、T+20、T+60 的收益、超额收益、回撤和量能变化。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            只读研究结果
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">筛选与计算</h2>
          <div className="mt-5 grid gap-4">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              事件子类型
              <input
                value={eventSubtype}
                onChange={(event) => setEventSubtype(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                对象
                <select
                  value={targetType}
                  onChange={(event) => setTargetType(event.target.value as EventReactionTargetType)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                >
                  {TARGET_TYPES.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                窗口
                <select
                  value={window}
                  onChange={(event) => setWindow(event.target.value as EventReactionWindow)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                >
                  {WINDOW_OPTIONS.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              对象代码
              <input
                value={targetId}
                onChange={(event) => setTargetId(event.target.value)}
                placeholder="可留空"
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              查询上限
              <input
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={replace}
                onChange={(event) => setReplace(event.target.checked)}
                className="h-4 w-4 accent-primary"
              />
              重新计算并覆盖已有反应
            </label>

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                {error}
              </div>
            ) : null}

            <div className="grid gap-2">
              <button
                type="button"
                disabled={loading !== null}
                onClick={runCalculate}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "calculate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                计算事件反应
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={runSummary}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "summary" ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
                生成摘要
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={runList}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "list" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                刷新明细
              </button>
            </div>
          </div>
        </section>

        <div className="grid content-start gap-5">
          {calculation ? <CalculationPanel result={calculation} /> : null}
          {summary ? <SummaryPanel summary={summary} /> : null}
          {list ? (
            <ReactionTable list={list} />
          ) : (
            <section className="rounded-lg border bg-card p-8 text-center">
              <AlertTriangle className="mx-auto h-8 w-8 text-muted-foreground" />
              <h2 className="mt-4 text-sm font-semibold">等待结果</h2>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                摘要和明细会显示本地 `event_reactions` 中已经计算过的结果。
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
