import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import {
  ApiError,
  api,
  type MarketRegime,
  type PortfolioAllocationListResponse,
  type PortfolioAllocationResponse,
  type PortfolioTradePlanResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const REGIME_OPTIONS: { value: MarketRegime; label: string }[] = [
  { value: "normal", label: "正常市场" },
  { value: "strong_trend", label: "强趋势" },
  { value: "weak", label: "弱势市场" },
  { value: "extreme_risk", label: "极端风险" },
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "风控组合操作失败，请检查本地服务状态。";
}

function parseInteger(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的整数。`);
  }
  return parsed;
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

function regimeLabel(value: string): string {
  return REGIME_OPTIONS.find((item) => item.value === value)?.label ?? value;
}

function approvalStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    draft_not_generated: "尚未生成信号",
    draft_signals_generated: "已有草稿信号",
    approved_for_simulation: "已模拟审批",
    post_approval_state: "审批后状态",
  };
  return labels[value] || value || "-";
}

function AllocationSummary({
  result,
  plan,
}: {
  result: PortfolioAllocationResponse | null;
  plan: PortfolioTradePlanResponse | null;
}) {
  return (
    <section className="grid gap-3 md:grid-cols-4">
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">模型总仓位</p>
        <p className="mt-2 text-2xl font-semibold">{formatPercent(result?.model_total_exposure)}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">已分配仓位</p>
        <p className="mt-2 text-2xl font-semibold">{formatPercent(result?.allocated_exposure ?? plan?.strategy_allocated_exposure)}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">目标持仓仓位</p>
        <p className="mt-2 text-2xl font-semibold">{formatPercent(plan?.target_total_exposure)}</p>
      </div>
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs text-muted-foreground">现金权重</p>
        <p className="mt-2 text-2xl font-semibold">{formatPercent(plan?.cash_weight ?? result?.cash_weight)}</p>
      </div>
    </section>
  );
}

function AllocationTable({ list }: { list: PortfolioAllocationListResponse | null }) {
  const rows = list?.strategy_allocations ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">策略资金分配</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">共 {list?.allocation_count ?? 0} 条策略权重。</p>
      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[960px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">策略</th>
                <th className="px-3 py-2 font-medium">类型</th>
                <th className="px-3 py-2 font-medium">权重</th>
                <th className="px-3 py-2 font-medium">评分</th>
                <th className="px-3 py-2 font-medium">风险</th>
                <th className="px-3 py-2 font-medium">波动</th>
                <th className="px-3 py-2 font-medium">说明</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.as_of_date}-${row.portfolio_id}-${row.strategy_id}`} className="border-t align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium">{row.strategy_name}</div>
                    <div className="mt-1 text-muted-foreground">{row.strategy_id}</div>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{row.strategy_type}</td>
                  <td className="px-3 py-3 font-medium">{formatPercent(row.allocated_weight)}</td>
                  <td className="px-3 py-3">{formatNumber(row.strategy_score)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{formatNumber(row.risk_score)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{formatPercent(row.volatility)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无策略分配结果。可以先在左侧运行组合风控分配。</p>
      )}
    </section>
  );
}

function TradePlanPanel({ plan }: { plan: PortfolioTradePlanResponse | null }) {
  const rows = plan?.target_positions ?? [];
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">草案目标持仓</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {plan ? `${plan.as_of_date} / ${approvalStatusLabel(plan.approval_status)}` : "等待生成交易计划。"}
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          未审批草案
        </span>
      </div>
      {rows.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[980px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">股票</th>
                <th className="px-3 py-2 font-medium">主题/板块</th>
                <th className="px-3 py-2 font-medium">目标权重</th>
                <th className="px-3 py-2 font-medium">动作</th>
                <th className="px-3 py-2 font-medium">策略来源</th>
                <th className="px-3 py-2 font-medium">风险提示</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.ticker} className="border-t align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium">{row.ticker_name}</div>
                    <div className="mt-1 text-muted-foreground">{row.ticker}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div>{row.theme || "-"}</div>
                    <div className="mt-1 text-muted-foreground">{row.sector_name || row.sector_id || "-"}</div>
                  </td>
                  <td className="px-3 py-3 font-medium">{formatPercent(row.target_weight)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.action}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.strategy_sources.length}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.risk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无草案目标持仓。生成交易计划后会显示单票和板块约束后的目标权重。</p>
      )}
    </section>
  );
}

function RiskRules({ result }: { result: PortfolioAllocationResponse | null }) {
  const rows = result?.risk_rules ?? [];
  if (!rows.length) {
    return null;
  }
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <h2 className="text-sm font-semibold">回撤风控规则</h2>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {rows.map((rule) => (
          <div
            key={`${rule.threshold}-${rule.action}`}
            className={cn(
              "rounded-lg border p-3 text-sm",
              rule.triggered ? "border-warning/30 bg-warning/10" : "bg-background",
            )}
          >
            <div className="font-medium">{rule.action}</div>
            <div className="mt-1 text-xs text-muted-foreground">阈值 {formatPercent(rule.threshold)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RiskPortfolio() {
  const [portfolioId, setPortfolioId] = useState("cn_a_main");
  const [asOfDate, setAsOfDate] = useState("");
  const [topN, setTopN] = useState("5");
  const [marketRegime, setMarketRegime] = useState<MarketRegime>("normal");
  const [currentDrawdown, setCurrentDrawdown] = useState("0");
  const [signalConfidence, setSignalConfidence] = useState("1");
  const [maxStrategyWeight, setMaxStrategyWeight] = useState("0.30");
  const [minStrategyWeight, setMinStrategyWeight] = useState("0.05");
  const [maxTypeWeight, setMaxTypeWeight] = useState("0.50");
  const [minStrategyScore, setMinStrategyScore] = useState("0");
  const [allocationLimit, setAllocationLimit] = useState("100");
  const [maxSingleStockWeight, setMaxSingleStockWeight] = useState("0.12");
  const [maxSectorWeight, setMaxSectorWeight] = useState("0.40");
  const [allocationResult, setAllocationResult] = useState<PortfolioAllocationResponse | null>(null);
  const [allocationList, setAllocationList] = useState<PortfolioAllocationListResponse | null>(null);
  const [tradePlan, setTradePlan] = useState<PortfolioTradePlanResponse | null>(null);
  const [loading, setLoading] = useState<"allocate" | "allocations" | "plan" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const clearFeedback = () => {
    setError(null);
    setNotice(null);
  };

  const listParams = () => ({
    portfolio_id: portfolioId.trim() || null,
    as_of_date: asOfDate.trim() || null,
    limit: parseInteger(allocationLimit, "分配查询上限", 1, 500),
  });

  const runAllocate = async () => {
    clearFeedback();
    setLoading("allocate");
    try {
      const response = await api.allocateRiskPortfolio({
        portfolio_id: portfolioId.trim() || "cn_a_main",
        as_of_date: asOfDate.trim() || null,
        top_n: parseInteger(topN, "策略数量", 3, 5),
        market_regime: marketRegime,
        current_drawdown: parseRatio(currentDrawdown, "当前回撤", -1, 0),
        signal_confidence: parseRatio(signalConfidence, "信号置信度", 0, 1),
        max_strategy_weight: parseRatio(maxStrategyWeight, "单策略上限", 0.05, 0.5),
        min_strategy_weight: parseRatio(minStrategyWeight, "单策略下限", 0, 0.2),
        max_strategy_type_weight: parseRatio(maxTypeWeight, "同类策略上限", 0.1, 1),
        min_strategy_score: parseRatio(minStrategyScore, "最低策略分", 0, 100),
      });
      setAllocationResult(response);
      setAllocationList({
        strategy_allocations: response.strategy_allocations,
        allocation_count: response.allocation_count,
      });
      setNotice(response.status === "risk_off" ? "当前进入风控防守状态，组合保持现金。" : `已生成 ${response.allocation_count} 条策略分配。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const refreshAllocations = async () => {
    clearFeedback();
    setLoading("allocations");
    try {
      const response = await api.listRiskPortfolioAllocations(listParams());
      setAllocationList(response);
      setNotice(`已加载 ${response.allocation_count} 条策略分配。`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const loadTradePlan = async () => {
    clearFeedback();
    setLoading("plan");
    try {
      const response = await api.getRiskTradePlan({
        portfolio_id: portfolioId.trim() || "cn_a_main",
        as_of_date: asOfDate.trim() || null,
        max_single_stock_weight: parseRatio(maxSingleStockWeight, "单票上限", 0.01, 0.3),
        max_sector_weight: parseRatio(maxSectorWeight, "板块上限", 0.05, 0.8),
      });
      setTradePlan(response);
      setAllocationList({
        strategy_allocations: response.strategy_allocations,
        allocation_count: response.strategy_allocations.length,
      });
      setNotice(`已生成 ${response.target_positions.length} 条草案目标持仓。`);
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
          <SlidersHorizontal className="h-3.5 w-3.5 text-primary" />
          多策略统一资金分配
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">风控组合</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              将已排名策略合并为统一组合权重，控制单策略、同类策略、单票和板块暴露，输出仍是人工确认前的研究草案。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            不审批 / 不下单
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">组合参数</h2>
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
                市场状态
                <select
                  value={marketRegime}
                  onChange={(event) => setMarketRegime(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                >
                  {REGIME_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                策略数量
                <input
                  value={topN}
                  onChange={(event) => setTopN(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                当前回撤
                <input
                  value={currentDrawdown}
                  onChange={(event) => setCurrentDrawdown(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                信号置信度
                <input
                  value={signalConfidence}
                  onChange={(event) => setSignalConfidence(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                单策略上限
                <input
                  value={maxStrategyWeight}
                  onChange={(event) => setMaxStrategyWeight(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                单策略下限
                <input
                  value={minStrategyWeight}
                  onChange={(event) => setMinStrategyWeight(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                同类策略上限
                <input
                  value={maxTypeWeight}
                  onChange={(event) => setMaxTypeWeight(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                最低策略分
                <input
                  value={minStrategyScore}
                  onChange={(event) => setMinStrategyScore(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <button
              type="button"
              disabled={loading !== null}
              onClick={runAllocate}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "allocate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <SlidersHorizontal className="h-4 w-4" />}
              运行组合风控
            </button>

            <div className="border-t pt-4">
              <h3 className="text-xs font-semibold text-muted-foreground">查询与交易计划草案</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  分配上限
                  <input
                    value={allocationLimit}
                    onChange={(event) => setAllocationLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  单票上限
                  <input
                    value={maxSingleStockWeight}
                    onChange={(event) => setMaxSingleStockWeight(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
              </div>
              <label className="mt-3 grid gap-1.5 text-xs text-muted-foreground">
                板块上限
                <input
                  value={maxSectorWeight}
                  onChange={(event) => setMaxSectorWeight(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <div className="mt-3 grid gap-2">
                <button
                  type="button"
                  disabled={loading !== null}
                  onClick={refreshAllocations}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading === "allocations" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  刷新策略分配
                </button>
                <button
                  type="button"
                  disabled={loading !== null}
                  onClick={loadTradePlan}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading === "plan" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  生成交易计划草案
                </button>
              </div>
            </div>

            {allocationResult ? (
              <div className="rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
                {regimeLabel(allocationResult.market_regime)}：状态 {allocationResult.status}，需要人工确认。
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
          <AllocationSummary result={allocationResult} plan={tradePlan} />
          <RiskRules result={allocationResult} />
          <AllocationTable list={allocationList} />
          <TradePlanPanel plan={tradePlan} />
        </div>
      </div>
    </div>
  );
}
