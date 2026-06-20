import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Layers,
  Loader2,
  Map,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import {
  ApiError,
  api,
  type EventRadarThemeMapRecord,
  type EventSectorMapping,
  type SectorScoreRecord,
  type SectorScoreRunResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type LoadingAction = "refresh" | "score";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "板块雷达操作失败，请检查本地服务状态。";
}

function parseBoundedInteger(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的整数。`);
  }
  return parsed;
}

function parseBoundedNumber(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的数字。`);
  }
  return parsed;
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 1000) / 10}`;
}

function cycleStageLabel(value: string): string {
  const labels: Record<string, string> = {
    climax: "高位拥挤",
    accelerating: "加速",
    confirmed: "确认",
    warming: "升温",
    fading: "退潮",
    cold: "冷却",
  };
  return labels[value] ?? value;
}

function stageTone(value: string): string {
  if (value === "accelerating" || value === "confirmed") return "border-success/40 bg-success/5 text-success";
  if (value === "climax") return "border-destructive/40 bg-destructive/5 text-destructive";
  if (value === "warming") return "border-primary/40 bg-primary/5 text-primary";
  return "border-border bg-muted/30 text-muted-foreground";
}

function ResultNotice({
  type,
  children,
}: {
  type: "success" | "warning";
  children: ReactNode;
}) {
  const Icon = type === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg border p-3 text-sm",
        type === "success" ? "border-success/30 bg-success/5 text-success" : "border-destructive/30 bg-destructive/5 text-destructive",
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 leading-6">{children}</div>
    </div>
  );
}

function ScoreCards({ scores }: { scores: SectorScoreRecord[] }) {
  return (
    <section className="grid gap-3 lg:grid-cols-3">
      {scores.slice(0, 3).map((score, index) => (
        <article key={`${score.trade_date}-${score.sector_id}`} className="rounded-lg border bg-card p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">排名 {index + 1}</p>
              <h2 className="mt-1 truncate text-base font-semibold">{score.sector_name}</h2>
            </div>
            <span className={cn("rounded-md border px-2 py-1 text-xs", stageTone(score.cycle_stage))}>
              {cycleStageLabel(score.cycle_stage)}
            </span>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-muted-foreground">综合热度</dt>
              <dd className="mt-1 text-lg font-semibold">{formatScore(score.sector_heat_score)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">事件热度</dt>
              <dd className="mt-1 text-lg font-semibold">{formatScore(score.event_heat)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">市场确认</dt>
              <dd className="mt-1 font-medium">{formatScore(score.market_confirm)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">拥挤风险</dt>
              <dd className="mt-1 font-medium">{formatScore(score.crowding_risk)}</dd>
            </div>
          </dl>
        </article>
      ))}
      {!scores.length ? (
        <section className="rounded-lg border bg-card p-8 text-center lg:col-span-3">
          <Layers className="mx-auto h-8 w-8 text-muted-foreground" />
          <h2 className="mt-4 text-sm font-semibold">暂无板块评分数据</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            板块评分会在事件完成映射后生成，仍保持研究与模拟边界。
          </p>
        </section>
      ) : null}
    </section>
  );
}

function ScoreTable({ scores }: { scores: SectorScoreRecord[] }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">板块评分明细</h2>
          <p className="mt-1 text-xs text-muted-foreground">共 {scores.length} 条</p>
        </div>
        <BarChart3 className="h-4 w-4 text-primary" />
      </div>
      {scores.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[920px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">板块</th>
                <th className="px-3 py-2 font-medium">综合</th>
                <th className="px-3 py-2 font-medium">事件</th>
                <th className="px-3 py-2 font-medium">市场确认</th>
                <th className="px-3 py-2 font-medium">广度</th>
                <th className="px-3 py-2 font-medium">资金</th>
                <th className="px-3 py-2 font-medium">持续性</th>
                <th className="px-3 py-2 font-medium">拥挤</th>
                <th className="px-3 py-2 font-medium">阶段</th>
              </tr>
            </thead>
            <tbody>
              {scores.map((score) => (
                <tr key={`${score.trade_date}-${score.sector_id}`} className="border-t">
                  <td className="px-3 py-2">
                    <span className="font-medium">{score.sector_name}</span>
                    <span className="ml-2 text-muted-foreground">{score.sector_id}</span>
                  </td>
                  <td className="px-3 py-2 font-semibold">{formatScore(score.sector_heat_score)}</td>
                  <td className="px-3 py-2">{formatScore(score.event_heat)}</td>
                  <td className="px-3 py-2">{formatScore(score.market_confirm)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatScore(score.breadth_score)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatScore(score.flow_score)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatScore(score.persistence_score)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatScore(score.crowding_risk)}</td>
                  <td className="px-3 py-2">
                    <span className={cn("rounded-md border px-2 py-1", stageTone(score.cycle_stage))}>
                      {cycleStageLabel(score.cycle_stage)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无评分明细。</p>
      )}
    </section>
  );
}

function MappingContext({
  sectorMappings,
  themeMap,
}: {
  sectorMappings: EventSectorMapping[];
  themeMap: EventRadarThemeMapRecord[];
}) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">板块映射上下文</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            事件映射 {sectorMappings.length} 条 / 主题映射 {themeMap.length} 条
          </p>
        </div>
        <Map className="h-4 w-4 text-primary" />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">事件板块</th>
                <th className="px-3 py-2 font-medium">主题</th>
                <th className="px-3 py-2 font-medium">相关度</th>
              </tr>
            </thead>
            <tbody>
              {sectorMappings.slice(0, 8).map((row) => (
                <tr key={`${row.event_id}-${row.sector_id}-${row.sub_theme}`} className="border-t">
                  <td className="px-3 py-2 font-medium">{row.sector_name}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.theme}</td>
                  <td className="px-3 py-2">{formatScore(row.relevance)}</td>
                </tr>
              ))}
              {!sectorMappings.length ? (
                <tr>
                  <td className="px-3 py-4 text-sm text-muted-foreground" colSpan={3}>暂无事件板块映射。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">主题</th>
                <th className="px-3 py-2 font-medium">股票</th>
                <th className="px-3 py-2 font-medium">证据</th>
              </tr>
            </thead>
            <tbody>
              {themeMap.slice(0, 8).map((row) => (
                <tr key={`${row.theme}-${row.sub_theme}-${row.ticker}`} className="border-t">
                  <td className="px-3 py-2 font-medium">{row.theme}</td>
                  <td className="px-3 py-2">
                    <span>{row.ticker_name}</span>
                    <span className="ml-2 text-muted-foreground">{row.ticker}</span>
                  </td>
                  <td className="max-w-[320px] px-3 py-2 text-muted-foreground">
                    <span className="line-clamp-2">{row.evidence}</span>
                  </td>
                </tr>
              ))}
              {!themeMap.length ? (
                <tr>
                  <td className="px-3 py-4 text-sm text-muted-foreground" colSpan={3}>暂无主题映射。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export function SectorRadar() {
  const [tradeDate, setTradeDate] = useState("");
  const [limit, setLimit] = useState("10");
  const [minRelevance, setMinRelevance] = useState("0.45");
  const [minScore, setMinScore] = useState("0");
  const [scores, setScores] = useState<SectorScoreRecord[]>([]);
  const [sectorMappings, setSectorMappings] = useState<EventSectorMapping[]>([]);
  const [themeMap, setThemeMap] = useState<EventRadarThemeMapRecord[]>([]);
  const [runResult, setRunResult] = useState<SectorScoreRunResponse | null>(null);
  const [loading, setLoading] = useState<LoadingAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const initialLoadStarted = useRef(false);

  const summary = useMemo(() => {
    const top = scores[0];
    return {
      scoreCount: scores.length,
      topSector: top?.sector_name ?? "-",
      topScore: top ? formatScore(top.sector_heat_score) : "-",
      contextRows: sectorMappings.length,
    };
  }, [scores, sectorMappings.length]);

  const loadOverview = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading("refresh");
    setError(null);
    try {
      const queryLimit = parseBoundedInteger(limit, "查询上限", 1, 50);
      const queryMinScore = parseBoundedNumber(minScore, "最低热度", 0, 1);
      const scoreResponse = await api.listSectorScores({
        trade_date: tradeDate || null,
        limit: queryLimit,
        min_score: queryMinScore,
      });
      const sectorMapResponse = await api.listEventSectorMappings({ limit: 100 });
      const themeMapResponse = await api.listEventRadarThemeMap();
      setScores(scoreResponse.sector_scores);
      setSectorMappings(sectorMapResponse.sector_mappings);
      setThemeMap(themeMapResponse.theme_map);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      if (showLoading) setLoading(null);
    }
  }, [limit, minScore, tradeDate]);

  useEffect(() => {
    if (initialLoadStarted.current) return;
    initialLoadStarted.current = true;
    void loadOverview();
  }, [loadOverview]);

  const runScoring = async () => {
    setError(null);
    setLoading("score");
    try {
      const response = await api.runSectorScoring({
        trade_date: tradeDate || null,
        limit: parseBoundedInteger(limit, "评分上限", 1, 50),
        min_relevance: parseBoundedNumber(minRelevance, "事件映射相关度", 0, 1),
      });
      setRunResult(response);
      await loadOverview(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const isBusy = loading !== null;

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Layers className="h-3.5 w-3.5 text-primary" />
          板块热度与轮动观察
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">板块雷达</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              汇总事件热度、市场确认、广度、资金、持续性和拥挤风险，形成 A 股板块层面的研究入口。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            研究/模拟，不展示实时行情
          </div>
        </div>
      </header>

      <section className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">评分板块</p>
          <p className="mt-1 text-xl font-semibold">{summary.scoreCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">最高热度</p>
          <p className="mt-1 truncate text-xl font-semibold">{summary.topSector}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">最高分</p>
          <p className="mt-1 text-xl font-semibold">{summary.topScore}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">事件映射</p>
          <p className="mt-1 text-xl font-semibold">{summary.contextRows}</p>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">评分参数</h2>
              <p className="mt-1 text-xs text-muted-foreground">从事件映射生成板块热度，日期留空时使用最新可评分日</p>
            </div>
            <TrendingUp className="h-4 w-4 text-primary" />
          </div>

          <div className="mt-5 grid gap-4">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              交易日期
              <input
                type="date"
                value={tradeDate}
                onChange={(event) => setTradeDate(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                评分上限
                <input
                  value={limit}
                  onChange={(event) => setLimit(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                事件映射相关度
                <input
                  value={minRelevance}
                  onChange={(event) => setMinRelevance(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                最低热度
                <input
                  value={minScore}
                  onChange={(event) => setMinScore(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <div className="grid gap-2">
              <button
                type="button"
                disabled={isBusy}
                onClick={runScoring}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "score" ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
                生成板块评分
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => loadOverview()}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "refresh" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                刷新评分
              </button>
            </div>

            {error ? <ResultNotice type="warning">{error}</ResultNotice> : null}
            {runResult ? (
              <ResultNotice type="success">
                已在 {runResult.trade_date} 写入 {runResult.rows_written} 条板块评分。
              </ResultNotice>
            ) : null}
          </div>
        </section>

        <div className="grid content-start gap-5">
          <ScoreCards scores={scores} />
          <ScoreTable scores={scores} />
          <MappingContext sectorMappings={sectorMappings} themeMap={themeMap} />
        </div>
      </div>
    </div>
  );
}
