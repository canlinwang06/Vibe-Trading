import { useState } from "react";
import {
  AlertTriangle,
  ClipboardList,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Target,
} from "lucide-react";
import {
  ApiError,
  api,
  type PortfolioAllocation,
  type PortfolioTargetPosition,
  type PortfolioTradePlanResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "交易计划加载失败，请检查本地服务状态。";
}

function parseRatio(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的小数。`);
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

function approvalStatusLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    draft_not_generated: "尚未生成执行信号",
    draft_signals_generated: "已有草稿执行信号",
    approved_for_simulation: "已模拟审批",
    post_approval_state: "审批后状态",
  };
  return labels[value ?? ""] || value || "-";
}

function actionLabel(value: string): string {
  const labels: Record<string, string> = {
    draft_target: "草案目标",
    buy: "买入",
    trim: "减仓",
    hold: "持有",
    exit: "清仓",
  };
  return labels[value] || value || "-";
}

function positionDelta(position: PortfolioTargetPosition): number {
  return position.target_weight - position.current_weight;
}

function TradePlanSummary({ plan }: { plan: PortfolioTradePlanResponse | null }) {
  return (
    <section className="grid gap-3 md:grid-cols-4">
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">目标总仓位</p>
        <p className="mt-2 text-2xl font-semibold">{formatPercent(plan?.target_total_exposure)}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">策略分配仓位</p>
        <p className="mt-2 text-2xl font-semibold">{formatPercent(plan?.strategy_allocated_exposure)}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">现金比例</p>
        <p className="mt-2 text-2xl font-semibold">{formatPercent(plan?.cash_weight)}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">目标股票数</p>
        <p className="mt-2 text-2xl font-semibold">{plan?.target_positions.length ?? 0}</p>
      </div>
    </section>
  );
}

function PlanStatus({ plan }: { plan: PortfolioTradePlanResponse | null }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">计划状态</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {plan ? `${plan.portfolio_id} / ${plan.as_of_date}` : "等待加载交易计划。"}
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          草稿审阅 / 不审批不下单
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border bg-background p-3">
          <p className="text-xs text-muted-foreground">审批状态</p>
          <p className="mt-1 text-sm font-medium">{approvalStatusLabel(plan?.approval_status)}</p>
        </div>
        <div className="rounded-lg border bg-background p-3">
          <p className="text-xs text-muted-foreground">人工确认</p>
          <p className="mt-1 text-sm font-medium">{plan?.requires_human_confirmation ? "需要" : "-"}</p>
        </div>
        <div className="rounded-lg border bg-background p-3">
          <p className="text-xs text-muted-foreground">执行边界</p>
          <p className="mt-1 text-sm font-medium">{plan?.live_trading === false ? "研究 / 模拟准备" : "-"}</p>
        </div>
      </div>
    </section>
  );
}

function RiskLimitPanel({ plan }: { plan: PortfolioTradePlanResponse | null }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <h2 className="text-sm font-semibold">约束检查</h2>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border bg-background p-3">
          <p className="text-xs text-muted-foreground">单票上限</p>
          <p className="mt-1 text-sm font-medium">{formatPercent(plan?.risk_limits.max_single_stock_weight)}</p>
        </div>
        <div className="rounded-lg border bg-background p-3">
          <p className="text-xs text-muted-foreground">板块上限</p>
          <p className="mt-1 text-sm font-medium">{formatPercent(plan?.risk_limits.max_sector_weight)}</p>
        </div>
      </div>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        该页面只展示后端返回的草案目标持仓和约束结果，不写入审批状态，也不触发任何外部执行。
      </p>
    </section>
  );
}

function TargetPositionTable({ positions }: { positions: PortfolioTargetPosition[] }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <Target className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">目标持仓</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">按目标权重展示股票级交易计划草案。</p>
      {positions.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[1120px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">股票</th>
                <th className="px-3 py-2 font-medium">主题/板块</th>
                <th className="px-3 py-2 font-medium">目标权重</th>
                <th className="px-3 py-2 font-medium">当前权重</th>
                <th className="px-3 py-2 font-medium">差额</th>
                <th className="px-3 py-2 font-medium">动作</th>
                <th className="px-3 py-2 font-medium">策略来源</th>
                <th className="px-3 py-2 font-medium">理由</th>
                <th className="px-3 py-2 font-medium">风险提示</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => {
                const delta = positionDelta(position);
                return (
                  <tr key={position.ticker} className="border-t align-top">
                    <td className="px-3 py-3">
                      <div className="font-medium">{position.ticker_name}</div>
                      <div className="mt-1 text-muted-foreground">{position.ticker}</div>
                    </td>
                    <td className="px-3 py-3">
                      <div>{position.theme || "-"}</div>
                      <div className="mt-1 text-muted-foreground">{position.sector_name || position.sector_id || "-"}</div>
                    </td>
                    <td className="px-3 py-3 font-medium">{formatPercent(position.target_weight)}</td>
                    <td className="px-3 py-3 text-muted-foreground">{formatPercent(position.current_weight)}</td>
                    <td className={cn("px-3 py-3", delta >= 0 ? "text-success" : "text-destructive")}>
                      {formatPercent(delta)}
                    </td>
                    <td className="px-3 py-3">{actionLabel(position.action)}</td>
                    <td className="px-3 py-3 text-muted-foreground">{position.strategy_sources.join(", ") || "-"}</td>
                    <td className="px-3 py-3 text-muted-foreground">{position.reason}</td>
                    <td className="px-3 py-3 text-muted-foreground">{position.risk}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无目标持仓。请先在风控组合页面完成策略资金分配。</p>
      )}
    </section>
  );
}

function StrategyAllocationTable({ allocations }: { allocations: PortfolioAllocation[] }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <ClipboardList className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">策略来源</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">展示生成目标持仓时使用的策略权重。</p>
      {allocations.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[960px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">策略</th>
                <th className="px-3 py-2 font-medium">类型</th>
                <th className="px-3 py-2 font-medium">权重</th>
                <th className="px-3 py-2 font-medium">评分</th>
                <th className="px-3 py-2 font-medium">风险</th>
                <th className="px-3 py-2 font-medium">说明</th>
              </tr>
            </thead>
            <tbody>
              {allocations.map((allocation) => (
                <tr key={`${allocation.portfolio_id}-${allocation.strategy_id}`} className="border-t align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium">{allocation.strategy_name}</div>
                    <div className="mt-1 text-muted-foreground">{allocation.strategy_id}</div>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{allocation.strategy_type}</td>
                  <td className="px-3 py-3 font-medium">{formatPercent(allocation.allocated_weight)}</td>
                  <td className="px-3 py-3">{formatNumber(allocation.strategy_score)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{formatNumber(allocation.risk_score)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{allocation.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无策略来源。</p>
      )}
    </section>
  );
}

export function TradePlan() {
  const [portfolioId, setPortfolioId] = useState("cn_a_main");
  const [asOfDate, setAsOfDate] = useState("");
  const [maxSingleStockWeight, setMaxSingleStockWeight] = useState("0.12");
  const [maxSectorWeight, setMaxSectorWeight] = useState("0.40");
  const [plan, setPlan] = useState<PortfolioTradePlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadPlan = async () => {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const response = await api.getRiskTradePlan({
        portfolio_id: portfolioId.trim() || "cn_a_main",
        as_of_date: asOfDate.trim() || null,
        max_single_stock_weight: parseRatio(maxSingleStockWeight, "单票上限", 0.01, 0.3),
        max_sector_weight: parseRatio(maxSectorWeight, "板块上限", 0.05, 0.8),
      });
      setPlan(response);
      setNotice(`已加载 ${response.target_positions.length} 条目标持仓。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <ClipboardList className="h-3.5 w-3.5 text-primary" />
          目标持仓与人工确认前审阅
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">交易计划</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              汇总组合风控输出的策略权重和股票目标权重，帮助人工复核调仓理由、风险提示和计划状态。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            草稿审阅 / 不审批不下单
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">查询参数</h2>
          <div className="mt-5 grid gap-4">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              组合 ID
              <input
                value={portfolioId}
                onChange={(event) => setPortfolioId(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              日期
              <input
                value={asOfDate}
                onChange={(event) => setAsOfDate(event.target.value)}
                placeholder="留空使用最新"
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                单票上限
                <input
                  value={maxSingleStockWeight}
                  onChange={(event) => setMaxSingleStockWeight(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                板块上限
                <input
                  value={maxSectorWeight}
                  onChange={(event) => setMaxSectorWeight(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <button
              type="button"
              disabled={loading}
              onClick={loadPlan}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新交易计划
            </button>
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
            <div className="rounded-lg border bg-muted/20 p-3 text-xs leading-5 text-muted-foreground">
              所有内容保持草稿状态。需要人工确认后，后续 PR 才能进入聚宽模拟导出流程。
            </div>
          </div>
        </section>

        <div className="grid content-start gap-5">
          <TradePlanSummary plan={plan} />
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <PlanStatus plan={plan} />
            <RiskLimitPanel plan={plan} />
          </div>
          <TargetPositionTable positions={plan?.target_positions ?? []} />
          <StrategyAllocationTable allocations={plan?.strategy_allocations ?? []} />
        </div>
      </div>
    </div>
  );
}
