import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ExternalLink,
  Layers,
  Lightbulb,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
  Target,
} from "lucide-react";
import {
  ApiError,
  api,
  type CandidateRecord,
  type SectorStockDashboardResponse,
  type StrategyIdea,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const sampleCandidates: CandidateRecord[] = [
  { ticker: "300308.SZ", ticker_name: "中际旭创", market: "CN_A", source: "sample", sector_id: "theme_optical_module", sector_name: "光模块", theme: "AI算力", event_heat_score: 0.88, sector_heat_score: 0.81, stock_score: 0.91, risk_flag: "normal", included: true, reason: "光模块龙头，AI算力链高相关。" },
  { ticker: "300502.SZ", ticker_name: "新易盛", market: "CN_A", source: "sample", sector_id: "theme_optical_module", sector_name: "光模块", theme: "AI算力", event_heat_score: 0.84, sector_heat_score: 0.8, stock_score: 0.88, risk_flag: "normal", included: true, reason: "业绩弹性与光模块景气相关。" },
  { ticker: "000977.SZ", ticker_name: "浪潮信息", market: "CN_A", source: "sample", sector_id: "theme_server", sector_name: "服务器", theme: "AI算力", event_heat_score: 0.76, sector_heat_score: 0.73, stock_score: 0.82, risk_flag: "normal", included: true, reason: "服务器产业链代表性标的。" },
  { ticker: "601138.SH", ticker_name: "工业富联", market: "CN_A", source: "sample", sector_id: "theme_server", sector_name: "服务器", theme: "AI算力", event_heat_score: 0.72, sector_heat_score: 0.7, stock_score: 0.78, risk_flag: "normal", included: true, reason: "AI服务器链条关注度较高。" },
  { ticker: "688256.SH", ticker_name: "寒武纪", market: "CN_A", source: "sample", sector_id: "theme_ai_compute", sector_name: "AI算力", theme: "AI算力", event_heat_score: 0.82, sector_heat_score: 0.88, stock_score: 0.74, risk_flag: "high_volatility", included: true, reason: "算力芯片弹性高，波动也高。" },
];

const sampleIdeas: StrategyIdea[] = [
  {
    idea_id: "sample_hot_momentum",
    as_of_date: new Date().toISOString().slice(0, 10),
    theme: "AI算力",
    strategy_type: "hot_sector_momentum",
    strategy_name: "AI算力热点板块动量",
    strategy_family: "板块轮动",
    idea_category: "热点板块动量",
    risk_preference: "balanced",
    holding_period: 5,
    rebalance_freq: "weekly",
    idea_score: 82,
    status: "candidate",
    thesis: "高热板块内选择强势股，严格控制仓位。",
    candidate_tickers: sampleCandidates.slice(0, 3).map((item) => ({ ticker: item.ticker, ticker_name: item.ticker_name, stock_score: item.stock_score })),
    sector_ids: ["theme_ai_compute"],
    source_event_ids: ["sample_evt_ai_1"],
    entry_rules: ["板块热度排名前 3", "股票强度排名前 5"],
    exit_rules: ["持有 5 个交易日后复评"],
    risk_controls: ["单股不超过 8%", "高拥挤时暂停新增"],
    params: {},
    evidence: {},
    research_only: true,
    live_trading: false,
  },
];

const fallbackDashboard: SectorStockDashboardResponse = {
  status: "ok",
  as_of_date: new Date().toISOString().slice(0, 10),
  theme: "AI算力",
  data_mode: "sample",
  sector_score: {
    theme: "AI算力",
    score: 82,
    summary: "AI算力热度较高，适合先生成候选策略卡，再通过聚宽验证规则。",
    badges: ["事件驱动强", "板块扩散中", "需防追高"],
  },
  sector_rankings: [
    { sector_id: "theme_ai_compute", sector_name: "AI算力", event_heat: 0.88, market_confirm: 0.72, breadth_score: 0.64, flow_score: 0.8, persistence_score: 0.76, crowding_risk: 0.58, sector_heat_score: 0.88, cycle_stage: "sample" },
    { sector_id: "theme_optical_module", sector_name: "光模块", event_heat: 0.81, market_confirm: 0.68, breadth_score: 0.59, flow_score: 0.72, persistence_score: 0.7, crowding_risk: 0.62, sector_heat_score: 0.81, cycle_stage: "sample" },
    { sector_id: "theme_server", sector_name: "服务器", event_heat: 0.73, market_confirm: 0.61, breadth_score: 0.55, flow_score: 0.67, persistence_score: 0.64, crowding_risk: 0.44, sector_heat_score: 0.73, cycle_stage: "sample" },
  ],
  candidate_matrix: sampleCandidates.map((item) => ({ ticker: item.ticker, ticker_name: item.ticker_name, sector_name: item.sector_name || "综合", leader_score: item.stock_score, order_score: item.event_heat_score, catch_up_score: 1 - item.stock_score, crowding_flag: item.risk_flag !== "normal" })),
  candidate_pool: sampleCandidates,
  strategy_ideas: sampleIdeas,
  codex_actions: ["让 Codex 生成多类型候选策略", "让 Codex 选择 3 张策略卡创建聚宽任务", "让 Codex 解释候选股票进入观察池的证据链"],
  research_only: true,
  live_trading: false,
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "策略想法操作失败，请检查本地服务状态。";
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function scoreText(value: number): string {
  return `${Math.round(value * 100)}`;
}

function statusText(status: string): string {
  if (status === "saved_to_strategy_lab") return "已进入策略实验室";
  if (status === "candidate") return "候选";
  if (status === "generated") return "待保存";
  return status;
}

function StrategyIdeaCard({
  idea,
  saving,
  creatingTask,
  onSave,
  onCreateTask,
}: {
  idea: StrategyIdea;
  saving: boolean;
  creatingTask: boolean;
  onSave: (ideaId: string) => void;
  onCreateTask: (idea: StrategyIdea) => void;
}) {
  return (
    <article className="rounded-lg border bg-background p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2">
            <span className="rounded-md border bg-primary/5 px-2 py-1 text-xs text-primary">{idea.idea_category}</span>
            <span className="rounded-md border bg-muted/30 px-2 py-1 text-xs text-muted-foreground">{idea.strategy_family}</span>
          </div>
          <h3 className="mt-3 text-base font-semibold">{idea.strategy_name}</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{idea.thesis}</p>
        </div>
        <div className="shrink-0 rounded-lg border bg-card px-3 py-2 text-center">
          <p className="text-[11px] text-muted-foreground">策略评分</p>
          <p className="mt-1 text-lg font-semibold">{Math.round(idea.idea_score)}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-xs md:grid-cols-3">
        <div className="rounded-md border bg-card p-3">
          <p className="text-muted-foreground">候选股票</p>
          <p className="mt-2 leading-5">
            {idea.candidate_tickers.slice(0, 4).map((item) => `${item.ticker_name} ${item.ticker}`).join(" / ") || "-"}
          </p>
        </div>
        <div className="rounded-md border bg-card p-3">
          <p className="text-muted-foreground">入场规则</p>
          <p className="mt-2 leading-5">{idea.entry_rules.slice(0, 2).join(" / ") || "-"}</p>
        </div>
        <div className="rounded-md border bg-card p-3">
          <p className="text-muted-foreground">风险控制</p>
          <p className="mt-2 leading-5">{idea.risk_controls.slice(0, 2).join(" / ") || "-"}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">状态：{statusText(idea.status)}</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={saving || idea.status === "saved_to_strategy_lab"}
            onClick={() => onSave(idea.idea_id)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-card px-3 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
            保存到策略实验室
          </button>
          <button
            type="button"
            disabled={creatingTask}
            onClick={() => onCreateTask(idea)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {creatingTask ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            创建聚宽任务
          </button>
        </div>
      </div>
    </article>
  );
}

export function SectorStockAnalysis() {
  const [theme, setTheme] = useState("AI算力");
  const [asOfDate, setAsOfDate] = useState(today());
  const [riskPreference, setRiskPreference] = useState("balanced");
  const [dashboard, setDashboard] = useState<SectorStockDashboardResponse>(fallbackDashboard);
  const [ideas, setIdeas] = useState<StrategyIdea[]>(fallbackDashboard.strategy_ideas);
  const [loading, setLoading] = useState<"dashboard" | "generate" | "refresh" | null>("dashboard");
  const [savingIdeaId, setSavingIdeaId] = useState<string | null>(null);
  const [creatingTaskId, setCreatingTaskId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async (nextTheme = theme) => {
    setLoading("dashboard");
    try {
      const response = await api.getSectorStockDashboard({ theme: nextTheme, as_of_date: asOfDate });
      setDashboard(response);
      setIdeas(response.strategy_ideas.length ? response.strategy_ideas : fallbackDashboard.strategy_ideas);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  useEffect(() => {
    void loadDashboard("AI算力");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clearFeedback = () => {
    setNotice(null);
    setError(null);
  };

  const generateIdeas = async () => {
    clearFeedback();
    setLoading("generate");
    try {
      const response = await api.generateStrategyIdeas({
        theme: theme.trim() || null,
        as_of_date: asOfDate.trim() || null,
        risk_preference: riskPreference,
        max_ideas: 8,
      });
      setIdeas(response.ideas);
      setNotice(`已生成 ${response.idea_count} 张策略卡。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const refreshIdeas = async () => {
    clearFeedback();
    setLoading("refresh");
    try {
      await loadDashboard(theme);
      const response = await api.listStrategyIdeas({
        theme: theme.trim() || null,
        as_of_date: asOfDate.trim() || null,
        limit: 20,
      });
      if (response.ideas.length) setIdeas(response.ideas);
      setNotice(`已加载 ${response.idea_count} 张策略卡。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const saveIdea = async (ideaId: string) => {
    clearFeedback();
    setSavingIdeaId(ideaId);
    try {
      const response = await api.saveStrategyIdeaSpec(ideaId, { enabled: true });
      setIdeas((current) =>
        current.map((idea) =>
          idea.idea_id === ideaId ? { ...idea, status: "saved_to_strategy_lab" } : idea,
        ),
      );
      setNotice(`已保存为策略规格：${response.strategy_spec.strategy_name}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSavingIdeaId(null);
    }
  };

  const createJoinQuantTask = async (idea: StrategyIdea) => {
    clearFeedback();
    setCreatingTaskId(idea.idea_id);
    try {
      const response = await api.joinQuantCreateTask({
        source_idea_id: idea.idea_id,
        source_strategy_id: idea.status === "saved_to_strategy_lab" ? idea.idea_id : null,
        portfolio_id: "cn_a_main",
        signal_date: asOfDate,
        task_type: "backtest",
      });
      setNotice(`已创建聚宽任务：${response.task.task_id}，状态为 ${response.task.status}。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCreatingTaskId(null);
    }
  };

  const sampleMode = dashboard.data_mode !== "local";
  const matrixRows = useMemo(() => dashboard.candidate_matrix.slice(0, 8), [dashboard.candidate_matrix]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Layers className="h-3.5 w-3.5 text-primary" />
          热点到股票池
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight">板块及股票分析</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              从历史事件影响、当日市场热度和板块内部强弱，生成候选股票池和策略想法。
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs text-muted-foreground">
            {loading === "dashboard" ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> : <ShieldCheck className="h-3.5 w-3.5 text-success" />}
            Codex 指挥层
          </div>
        </div>
      </header>

      <section className="rounded-lg border bg-card p-5">
        <p className="text-sm font-semibold">{dashboard.sector_score.theme}板块综合判断</p>
        <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-center">
          <span className="text-5xl font-semibold text-primary">{Math.round(dashboard.sector_score.score)}</span>
          <div className="min-w-0">
            <h2 className="text-xl font-semibold leading-8">{dashboard.sector_score.summary}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {dashboard.sector_score.badges.map((badge) => (
                <span key={badge} className="rounded-md border bg-primary/5 px-2.5 py-1 text-xs text-primary">{badge}</span>
              ))}
              {sampleMode ? <span className="rounded-md border bg-muted/40 px-2.5 py-1 text-xs text-muted-foreground">样例/待采集</span> : null}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">热点板块排行</h2>
          </div>
          <div className="mt-6 grid gap-5">
            {dashboard.sector_rankings.slice(0, 6).map((sector) => (
              <div key={sector.sector_id} className="grid grid-cols-[96px_minmax(0,1fr)_38px] items-center gap-3">
                <span className="text-sm font-medium">{sector.sector_name}</span>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(8, sector.sector_heat_score * 100)}%` }} />
                </div>
                <span className="text-xs font-semibold text-muted-foreground">{Math.round(sector.sector_heat_score * 100)}</span>
              </div>
            ))}
          </div>
          <p className="mt-6 text-xs leading-5 text-muted-foreground">排序由事件热度、价格确认、扩散程度和持续性共同决定。</p>
        </article>

        <article className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">板块到股票候选矩阵</h2>
          <div className="mt-5 overflow-hidden rounded-lg border">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/30 text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">股票</th>
                  <th className="px-3 py-2 font-medium">板块</th>
                  <th className="px-3 py-2 font-medium">龙头确认</th>
                  <th className="px-3 py-2 font-medium">订单兑现</th>
                  <th className="px-3 py-2 font-medium">低位补涨</th>
                  <th className="px-3 py-2 font-medium">拥挤</th>
                </tr>
              </thead>
              <tbody>
                {matrixRows.map((row) => (
                  <tr key={row.ticker} className="border-t">
                    <td className="px-3 py-2 font-medium">{row.ticker_name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{row.sector_name}</td>
                    <td className="px-3 py-2">{scoreText(row.leader_score)}</td>
                    <td className="px-3 py-2">{scoreText(row.order_score)}</td>
                    <td className="px-3 py-2">{scoreText(row.catch_up_score)}</td>
                    <td className={cn("px-3 py-2", row.crowding_flag ? "text-warning" : "text-success")}>{row.crowding_flag ? "慎" : "可"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">候选股票池</h2>
          </div>
          <div className="mt-5 grid gap-4">
            {dashboard.candidate_pool.slice(0, 8).map((candidate) => (
              <div key={candidate.ticker} className="grid gap-2 sm:grid-cols-[96px_minmax(0,1fr)_96px] sm:items-center">
                <div>
                  <p className="text-sm font-semibold">{candidate.ticker_name}</p>
                  <p className="text-xs text-muted-foreground">{candidate.ticker}</p>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(8, candidate.stock_score * 100)}%` }} />
                </div>
                <p className="text-xs text-muted-foreground">{candidate.reason || candidate.sector_name}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-lg border bg-card p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold">候选策略想法</h2>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                基于热点板块、候选股票池和事件记录生成可回测策略卡。
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-[120px_130px_120px]">
              <input
                aria-label="主题"
                value={theme}
                onChange={(event) => setTheme(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              />
              <input
                aria-label="日期"
                value={asOfDate}
                onChange={(event) => setAsOfDate(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              />
              <select
                aria-label="风险偏好"
                value={riskPreference}
                onChange={(event) => setRiskPreference(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              >
                <option value="conservative">保守</option>
                <option value="balanced">均衡</option>
                <option value="aggressive">进攻</option>
              </select>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading !== null}
              onClick={generateIdeas}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "generate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lightbulb className="h-4 w-4" />}
              生成策略卡
            </button>
            <button
              type="button"
              disabled={loading !== null}
              onClick={refreshIdeas}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "refresh" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新
            </button>
            <Link className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium hover:bg-muted" to="/joinquant-export">
              聚宽任务中心
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          {notice ? (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 p-3 text-sm text-success">
              <CheckCircle2 className="mt-0.5 h-4 w-4" />
              {notice}
            </div>
          ) : null}
          {error ? (
            <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>
          ) : null}

          <div className="mt-5 grid gap-4">
            {ideas.map((idea) => (
              <StrategyIdeaCard
                key={idea.idea_id}
                idea={idea}
                saving={savingIdeaId === idea.idea_id}
                creatingTask={creatingTaskId === idea.idea_id}
                onSave={saveIdea}
                onCreateTask={createJoinQuantTask}
              />
            ))}
          </div>
        </article>
      </section>

      <section className="rounded-lg border bg-card p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-sm font-semibold">页面交互原则</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              用户主要通过 Codex 发话：生成股票池、生成策略卡、送聚宽回测、写回结果。页面只保留少量确认动作和清晰呈现。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted" to="/event-records">
              事件记录库
              <ExternalLink className="h-3.5 w-3.5" />
            </Link>
            <Link className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted" to="/strategy-lifecycle">
              策略生命周期
              <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
