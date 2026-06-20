import { Link } from "react-router-dom";
import { useState } from "react";
import {
  BarChart3,
  ExternalLink,
  Layers,
  Lightbulb,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Target,
} from "lucide-react";
import { ApiError, api, type StrategyIdea } from "@/lib/api";

const SUMMARY_CARDS = [
  { label: "热点板块", value: "由事件沉淀得出", desc: "综合历史事件密度、持续性、市场确认和拥挤风险。" },
  { label: "候选股票", value: "建议观察", desc: "从热点板块和事件映射中筛出可复核的股票池。" },
  { label: "推荐理由", value: "可解释", desc: "每只股票都需要能回溯到板块、事件和风险约束。" },
  { label: "策略衔接", value: "可复制", desc: "把确认后的观察池送入策略实验室，再输出聚宽草稿。" },
];

const RESPONSIBILITIES = [
  "基于事件记录库沉淀的数据，判断当前哪些板块正在升温。",
  "在热点板块内筛选建议观察股票，并说明为什么值得进入观察池。",
  "只输出研究和模拟准备结果，不替代你的最终投资判断。",
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "策略想法操作失败，请检查本地服务状态。";
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function scoreLabel(value: number): string {
  return `${Math.round(value * 10) / 10}`;
}

function StrategyIdeaCard({
  idea,
  saving,
  onSave,
}: {
  idea: StrategyIdea;
  saving: boolean;
  onSave: (ideaId: string) => void;
}) {
  return (
    <article className="rounded-lg border bg-card p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md border bg-primary/5 px-2 py-1 text-xs text-primary">
              {idea.idea_category}
            </span>
            <span className="rounded-md border bg-muted/30 px-2 py-1 text-xs text-muted-foreground">
              {idea.strategy_family}
            </span>
          </div>
          <h3 className="mt-3 text-base font-semibold">{idea.strategy_name}</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{idea.thesis}</p>
        </div>
        <div className="shrink-0 rounded-lg border bg-background px-3 py-2 text-center">
          <p className="text-[11px] text-muted-foreground">策略评分</p>
          <p className="mt-1 text-lg font-semibold">{scoreLabel(idea.idea_score)}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-xs md:grid-cols-3">
        <div className="rounded-md border bg-background p-3">
          <p className="text-muted-foreground">候选股票</p>
          <p className="mt-2 leading-5">
            {idea.candidate_tickers.slice(0, 4).map((item) => `${item.ticker_name} ${item.ticker}`).join(" / ") || "-"}
          </p>
        </div>
        <div className="rounded-md border bg-background p-3">
          <p className="text-muted-foreground">入场规则</p>
          <p className="mt-2 leading-5">{idea.entry_rules.slice(0, 2).join(" / ")}</p>
        </div>
        <div className="rounded-md border bg-background p-3">
          <p className="text-muted-foreground">风险控制</p>
          <p className="mt-2 leading-5">{idea.risk_controls.slice(0, 2).join(" / ")}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">
          状态：{idea.status === "saved_to_strategy_lab" ? "已进入策略实验室" : "待保存"}
        </p>
        <button
          type="button"
          disabled={saving || idea.status === "saved_to_strategy_lab"}
          onClick={() => onSave(idea.idea_id)}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
          保存到策略实验室
        </button>
      </div>
    </article>
  );
}

export function SectorStockAnalysis() {
  const [theme, setTheme] = useState("AI算力");
  const [asOfDate, setAsOfDate] = useState(today());
  const [riskPreference, setRiskPreference] = useState("balanced");
  const [ideas, setIdeas] = useState<StrategyIdea[]>([]);
  const [loading, setLoading] = useState<"generate" | "refresh" | null>(null);
  const [savingIdeaId, setSavingIdeaId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      const response = await api.listStrategyIdeas({
        theme: theme.trim() || null,
        as_of_date: asOfDate.trim() || null,
        limit: 20,
      });
      setIdeas(response.ideas);
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

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Layers className="h-3.5 w-3.5 text-primary" />
          分析决策层
        </div>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
          <div className="space-y-3">
            <h1 className="text-2xl font-semibold tracking-tight">板块及股票分析</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              从历史事件影响中提炼当前热点板块，再结合板块成分和事件映射生成建议观察股票池与策略想法卡。
            </p>
          </div>
          <div className="rounded-lg border bg-muted/20 p-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <p className="text-sm font-medium">使用边界</p>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  本页负责研究排序和股票观察池，不在本地执行回测，也不直接连接聚宽账户。
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {SUMMARY_CARDS.map((card) => (
          <article key={card.label} className="rounded-lg border bg-card p-4">
            <p className="text-xs text-muted-foreground">{card.label}</p>
            <h2 className="mt-2 text-lg font-semibold">{card.value}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{card.desc}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">页面职责</h2>
          </div>
          <div className="mt-4 grid gap-3">
            {RESPONSIBILITIES.map((item) => (
              <div key={item} className="rounded-md border bg-background p-3 text-sm leading-6 text-muted-foreground">
                {item}
              </div>
            ))}
          </div>
        </div>

        <aside className="rounded-lg border bg-muted/20 p-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">兼容入口</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            原有分析页面保留给细节检查，后续会作为本页的数据来源和钻取视图。
          </p>
          <div className="mt-4 grid gap-2">
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/sector-radar">
              板块雷达
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/candidate-pool">
              候选股票池
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/strategy-lab">
              策略实验室
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
          </div>
        </aside>
      </section>

      <section className="rounded-lg border bg-card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">策略想法工厂</h2>
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              基于热点板块、候选股票池和事件记录生成可回测策略卡，再送入策略实验室。
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-[160px_160px_150px_auto_auto]">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              主题
              <input
                value={theme}
                onChange={(event) => setTheme(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              日期
              <input
                value={asOfDate}
                onChange={(event) => setAsOfDate(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              风险偏好
              <select
                value={riskPreference}
                onChange={(event) => setRiskPreference(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              >
                <option value="conservative">保守</option>
                <option value="balanced">均衡</option>
                <option value="aggressive">进攻</option>
              </select>
            </label>
            <button
              type="button"
              disabled={loading !== null}
              onClick={generateIdeas}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "generate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lightbulb className="h-4 w-4" />}
              生成策略卡
            </button>
            <button
              type="button"
              disabled={loading !== null}
              onClick={refreshIdeas}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "refresh" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新
            </button>
          </div>
        </div>

        {notice ? (
          <div className="mt-4 rounded-lg border border-success/30 bg-success/5 p-3 text-sm text-success">{notice}</div>
        ) : null}
        {error ? (
          <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>
        ) : null}

        <div className="mt-5 grid gap-4">
          {ideas.length ? (
            ideas.map((idea) => (
              <StrategyIdeaCard
                key={idea.idea_id}
                idea={idea}
                saving={savingIdeaId === idea.idea_id}
                onSave={saveIdea}
              />
            ))
          ) : (
            <div className="rounded-lg border bg-muted/20 p-6 text-sm text-muted-foreground">
              暂无策略卡。生成后会在这里显示策略逻辑、候选股票、规则和风险控制。
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
