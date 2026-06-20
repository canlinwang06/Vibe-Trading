import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Target,
  XCircle,
} from "lucide-react";
import {
  ApiError,
  api,
  type CandidateIncludedFilter,
  type CandidatePoolBuildResponse,
  type CandidatePoolListResponse,
  type CandidateRecord,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const SOURCE_OPTIONS = [
  { value: "", label: "全部来源" },
  { value: "sector_radar", label: "板块雷达" },
  { value: "user_added", label: "手动加入" },
];

const INCLUDED_OPTIONS: { value: CandidateIncludedFilter; label: string }[] = [
  { value: "all", label: "全部状态" },
  { value: "included", label: "已纳入" },
  { value: "excluded", label: "已排除" },
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "候选池操作失败，请检查本地服务状态。";
}

function parseInteger(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的整数。`);
  }
  return parsed;
}

function parseScore(value: string, label: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
    throw new Error(`${label}必须是 0 到 1 之间的小数。`);
  }
  return parsed;
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 1000) / 10}`;
}

function sourceLabel(value: string): string {
  if (value === "sector_radar") return "板块雷达";
  if (value === "user_added") return "手动加入";
  return value || "-";
}

function riskLabel(value: string): string {
  const labels: Record<string, string> = {
    normal: "正常",
    st_or_delisting_risk: "ST/退市风险",
    suspended: "停牌",
    short_term_extreme_gain: "短期涨幅过高",
    limit_up_crowding: "涨停拥挤",
  };
  return labels[value] || value || "-";
}

function CandidateTable({
  list,
  loading,
  onInclude,
  onExclude,
}: {
  list: CandidatePoolListResponse | null;
  loading: boolean;
  onInclude: (candidate: CandidateRecord) => void;
  onExclude: (candidate: CandidateRecord) => void;
}) {
  const rows = list?.candidates ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold">候选股票</h2>
          <p className="mt-1 text-xs text-muted-foreground">共 {list?.candidate_count ?? 0} 条，默认按纳入状态和评分排序。</p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          研究/模拟
        </span>
      </div>

      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[1040px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">股票</th>
                <th className="px-3 py-2 font-medium">主题/板块</th>
                <th className="px-3 py-2 font-medium">来源</th>
                <th className="px-3 py-2 font-medium">事件热度</th>
                <th className="px-3 py-2 font-medium">板块热度</th>
                <th className="px-3 py-2 font-medium">股票评分</th>
                <th className="px-3 py-2 font-medium">风险</th>
                <th className="px-3 py-2 font-medium">状态</th>
                <th className="px-3 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((candidate) => (
                <tr key={`${candidate.as_of_date}-${candidate.ticker}`} className="border-t align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium">{candidate.ticker_name}</div>
                    <div className="mt-1 text-muted-foreground">{candidate.ticker}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div>{candidate.theme || "-"}</div>
                    <div className="mt-1 text-muted-foreground">{candidate.sector_name || candidate.sector_id || "-"}</div>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{sourceLabel(candidate.source)}</td>
                  <td className="px-3 py-3">{formatScore(candidate.event_heat_score)}</td>
                  <td className="px-3 py-3">{formatScore(candidate.sector_heat_score)}</td>
                  <td className="px-3 py-3 font-medium">{formatScore(candidate.stock_score)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{riskLabel(candidate.risk_flag)}</td>
                  <td className="px-3 py-3">
                    <span
                      className={cn(
                        "inline-flex rounded-md px-2 py-1 text-xs",
                        candidate.included ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
                      )}
                    >
                      {candidate.included ? "已纳入" : "已排除"}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={loading || candidate.included}
                        onClick={() => onInclude(candidate)}
                        className="inline-flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-xs font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        纳入
                      </button>
                      <button
                        type="button"
                        disabled={loading || !candidate.included}
                        onClick={() => onExclude(candidate)}
                        className="inline-flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-xs font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        排除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-dashed p-8 text-center">
          <AlertTriangle className="mx-auto h-8 w-8 text-muted-foreground" />
          <h3 className="mt-4 text-sm font-semibold">暂无候选股票</h3>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            可以先运行每日工作流，或在左侧根据已有板块评分生成候选池，也可以手动加入一只 A 股观察。
          </p>
        </div>
      )}
    </section>
  );
}

export function CandidatePool() {
  const [asOfDate, setAsOfDate] = useState("");
  const [limit, setLimit] = useState("100");
  const [buildLimit, setBuildLimit] = useState("50");
  const [source, setSource] = useState("");
  const [includedFilter, setIncludedFilter] = useState<CandidateIncludedFilter>("all");
  const [minScore, setMinScore] = useState("0");
  const [minSectorScore, setMinSectorScore] = useState("0");
  const [ticker, setTicker] = useState("300308.SZ");
  const [tickerName, setTickerName] = useState("中际旭创");
  const [theme, setTheme] = useState("AI算力");
  const [sectorName, setSectorName] = useState("光模块");
  const [reason, setReason] = useState("AI 产业链事件观察，加入候选池跟踪。");
  const [list, setList] = useState<CandidatePoolListResponse | null>(null);
  const [buildResult, setBuildResult] = useState<CandidatePoolBuildResponse | null>(null);
  const [loading, setLoading] = useState<"list" | "build" | "add" | "decision" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const listParams = () => ({
    as_of_date: asOfDate.trim() || null,
    limit: parseInteger(limit, "查询上限", 1, 500),
    source: source || null,
    included: includedFilter === "all" ? null : includedFilter === "included",
    min_score: parseScore(minScore, "最低股票评分"),
  });

  const refreshList = async () => {
    setError(null);
    setNotice(null);
    setLoading("list");
    try {
      const response = await api.listCandidatePool(listParams());
      setList(response);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  useEffect(() => {
    void refreshList();
  }, []);

  const buildPool = async () => {
    setError(null);
    setNotice(null);
    setLoading("build");
    try {
      const response = await api.buildCandidatePool({
        as_of_date: asOfDate.trim() || null,
        limit: parseInteger(buildLimit, "生成上限", 1, 200),
        min_sector_score: parseScore(minSectorScore, "最低板块热度"),
      });
      setBuildResult(response);
      setList({ candidates: response.candidates, candidate_count: response.candidate_count });
      setNotice(`已生成 ${response.rows_written} 条候选股票。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const addCandidate = async () => {
    setError(null);
    setNotice(null);
    setLoading("add");
    try {
      const candidate = await api.addUserCandidate({
        ticker: ticker.trim(),
        ticker_name: tickerName.trim() || null,
        as_of_date: asOfDate.trim() || null,
        theme: theme.trim() || null,
        sector_name: sectorName.trim() || null,
        reason: reason.trim() || null,
        user_priority: 100,
      });
      setNotice(`已加入 ${candidate.ticker_name}。`);
      const response = await api.listCandidatePool(listParams());
      setList(response);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const decideCandidate = async (candidate: CandidateRecord, included: boolean) => {
    setError(null);
    setNotice(null);
    setLoading("decision");
    try {
      const response = included
        ? await api.includeCandidate({
          ticker: candidate.ticker,
          as_of_date: candidate.as_of_date || asOfDate.trim() || null,
          reason: "用户在候选池页面重新纳入。",
        })
        : await api.excludeCandidate({
          ticker: candidate.ticker,
          as_of_date: candidate.as_of_date || asOfDate.trim() || null,
          reason: "用户在候选池页面排除观察。",
        });
      setNotice(`${response.ticker_name} 已${included ? "纳入" : "排除"}候选池。`);
      const next = await api.listCandidatePool(listParams());
      setList(next);
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
          <Target className="h-3.5 w-3.5 text-primary" />
          事件到股票的人工确认区
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">候选股票池</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              承接事件映射和板块热度，查看系统推荐股票，手动加入自选股，并在进入策略实验室前完成纳入或排除确认。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            不生成交易信号
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">筛选与操作</h2>
          <div className="mt-5 grid gap-4">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              日期
              <input
                value={asOfDate}
                onChange={(event) => setAsOfDate(event.target.value)}
                placeholder="留空使用最新候选池日期"
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                来源
                <select
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                >
                  {SOURCE_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                状态
                <select
                  value={includedFilter}
                  onChange={(event) => setIncludedFilter(event.target.value as CandidateIncludedFilter)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                >
                  {INCLUDED_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                查询上限
                <input
                  value={limit}
                  onChange={(event) => setLimit(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                最低股票评分
                <input
                  value={minScore}
                  onChange={(event) => setMinScore(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <button
              type="button"
              disabled={loading !== null}
              onClick={refreshList}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "list" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新候选
            </button>

            <div className="border-t pt-4">
              <h3 className="text-xs font-semibold text-muted-foreground">从板块雷达生成</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  生成上限
                  <input
                    value={buildLimit}
                    onChange={(event) => setBuildLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  最低板块热度
                  <input
                    value={minSectorScore}
                    onChange={(event) => setMinSectorScore(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
              </div>
              <button
                type="button"
                disabled={loading !== null}
                onClick={buildPool}
                className="mt-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "build" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
                生成候选池
              </button>
            </div>

            <div className="border-t pt-4">
              <h3 className="text-xs font-semibold text-muted-foreground">手动加入自选股</h3>
              <div className="mt-3 grid gap-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    股票代码
                    <input
                      value={ticker}
                      onChange={(event) => setTicker(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    股票名称
                    <input
                      value={tickerName}
                      onChange={(event) => setTickerName(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    主题
                    <input
                      value={theme}
                      onChange={(event) => setTheme(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-muted-foreground">
                    板块
                    <input
                      value={sectorName}
                      onChange={(event) => setSectorName(event.target.value)}
                      className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                    />
                  </label>
                </div>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  加入理由
                  <textarea
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    rows={3}
                    className="rounded-md border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <button
                  type="button"
                  disabled={loading !== null}
                  onClick={addCandidate}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading === "add" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  加入候选池
                </button>
              </div>
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
          {buildResult ? (
            <section className="rounded-lg border border-success/30 bg-success/5 p-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <h2 className="text-sm font-semibold">生成完成</h2>
              </div>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted-foreground">日期</dt>
                  <dd className="mt-1 font-medium">{buildResult.as_of_date}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">写入候选</dt>
                  <dd className="mt-1 font-medium">{buildResult.rows_written}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">总数</dt>
                  <dd className="mt-1 font-medium">{buildResult.candidate_count}</dd>
                </div>
              </dl>
            </section>
          ) : null}
          <CandidateTable
            list={list}
            loading={loading !== null}
            onInclude={(candidate) => decideCandidate(candidate, true)}
            onExclude={(candidate) => decideCandidate(candidate, false)}
          />
        </div>
      </div>
    </div>
  );
}
