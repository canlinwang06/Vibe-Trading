import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  BookOpenCheck,
  BriefcaseBusiness,
  CircleAlert,
  Eye,
  Loader2,
  ShieldCheck,
  Target,
} from "lucide-react";
import {
  ApiError,
  api,
  type AdvisorActionItem,
  type AdvisorCandidate,
  type AdvisorDiagnostic,
  type AdvisorExternalValidation,
  type AdvisorHoldingsSnapshot,
  type AdvisorJournalSnapshot,
  type AdvisorRiskItem,
  type AdvisorTodaySnapshot,
  type AdvisorWatchlistSnapshot,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type SnapshotState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

const PORTFOLIO_ID = "cn_a_main";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "投资助手快照读取失败，请确认本地服务正在运行。";
}

function useSnapshot<T>(loader: () => Promise<T>): SnapshotState<T> {
  const [state, setState] = useState<SnapshotState<T>>({ data: null, loading: true, error: null });

  useEffect(() => {
    let active = true;
    setState({ data: null, loading: true, error: null });
    loader()
      .then((data) => {
        if (active) setState({ data, loading: false, error: null });
      })
      .catch((error) => {
        if (active) setState({ data: null, loading: false, error: errorMessage(error) });
      });
    return () => {
      active = false;
    };
  }, []);

  return state;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
  return String(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 1000) / 10}%`;
}

function actionTone(action?: string): string {
  if (action === "exit" || action === "risk_high" || action === "chase_risk") return "border-destructive/40 bg-destructive/5";
  if (action === "reduce" || action === "complete_thesis" || action === "needs_exit_condition") return "border-warning/40 bg-warning/5";
  if (action === "ready_small_probe" || action === "hold") return "border-success/30 bg-success/5";
  return "border-border bg-card";
}

function PageState<T>({
  state,
  children,
}: {
  state: SnapshotState<T>;
  children: (data: T) => ReactNode;
}) {
  if (state.loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在读取投资助手快照
      </div>
    );
  }
  if (state.error) {
    return (
      <div className="mx-auto mt-10 max-w-xl rounded-lg border border-destructive/40 bg-destructive/5 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-destructive">
          <AlertTriangle className="h-4 w-4" />
          快照不可用
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{state.error}</p>
      </div>
    );
  }
  if (!state.data) return null;
  return children(state.data);
}

function AdvisorShell({
  title,
  headline,
  eyebrow,
  icon,
  children,
}: {
  title: string;
  headline: string;
  eyebrow: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-7xl px-6 py-7">
      <header className="mb-6">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1.5 text-xs text-muted-foreground">
          {icon}
          {eyebrow}
        </div>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{headline}</p>
      </header>
      {children}
    </div>
  );
}

function ResearchBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
      <ShieldCheck className="h-3.5 w-3.5" />
      研究/模拟
    </span>
  );
}

function SummaryGrid({ cards }: { cards: { label: string; value: unknown }[] }) {
  return (
    <section className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
      {cards.map((card) => (
        <article key={card.label} className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">{card.label}</p>
          <p className="mt-2 text-2xl font-semibold">{formatValue(card.value)}</p>
        </article>
      ))}
    </section>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-lg border bg-card p-5 text-sm text-muted-foreground">
      {text}
    </div>
  );
}

function ActionCard({ item }: { item: AdvisorActionItem }) {
  return (
    <article className={cn("rounded-lg border p-4", actionTone(item.action))}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{item.label || item.action || "行动建议"}</p>
          {item.ticker ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {item.ticker_name} / {item.ticker}
            </p>
          ) : null}
        </div>
        {item.type ? <span className="rounded-md border bg-background px-2 py-1 text-xs text-muted-foreground">{item.type}</span> : null}
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.reason}</p>
      {item.trigger ? <p className="mt-2 text-xs text-muted-foreground">触发条件：{formatValue(item.trigger)}</p> : null}
    </article>
  );
}

function DiagnosticCard({ item }: { item: AdvisorDiagnostic }) {
  const sellLine = item.sell_line || {};
  return (
    <article className={cn("rounded-lg border p-4", actionTone(item.action))}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{item.action_label}</p>
          <p className="mt-1 text-xs text-muted-foreground">{item.ticker_name} / {item.ticker}</p>
        </div>
        <span className="rounded-md border bg-background px-2 py-1 text-xs">{formatValue(item.current_price)}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.reason}</p>
      <dl className="mt-4 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">硬止损</dt>
          <dd className="mt-1 font-medium">{formatValue(sellLine.hard_stop_price)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">止盈线</dt>
          <dd className="mt-1 font-medium">{formatValue(sellLine.take_profit_price)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">下次复盘</dt>
          <dd className="mt-1 font-medium">{formatValue(item.next_review_date)}</dd>
        </div>
      </dl>
    </article>
  );
}

function CandidateCard({ item }: { item: AdvisorCandidate }) {
  return (
    <article className={cn("rounded-lg border p-4", actionTone(item.suggested_status))}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{item.suggested_status_label}</p>
          <p className="mt-1 text-xs text-muted-foreground">{item.ticker_name} / {item.ticker}</p>
        </div>
        <span className="rounded-md border bg-background px-2 py-1 text-xs">{formatValue(item.buy_trigger_price)}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.reason}</p>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">建议仓位上限</dt>
          <dd className="mt-1 font-medium">{formatPercent(item.max_position_pct)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">观察周期</dt>
          <dd className="mt-1 font-medium">{item.target_holding_days ? `${item.target_holding_days} 天` : "-"}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted-foreground">买入条件：{formatValue(item.buy_trigger_condition)}</p>
      <p className="mt-1 text-xs text-muted-foreground">不买条件：{formatValue(item.not_buy_conditions)}</p>
    </article>
  );
}

function RiskCard({ item }: { item: AdvisorRiskItem }) {
  return (
    <article className="rounded-lg border border-warning/40 bg-warning/5 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{item.rule_label}</p>
          <p className="mt-1 text-xs text-muted-foreground">{item.ticker_name} / {item.ticker}</p>
        </div>
        <span className="rounded-md border bg-background px-2 py-1 text-xs">{item.severity}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.reason}</p>
    </article>
  );
}

function ValidationCard({ item }: { item: AdvisorExternalValidation }) {
  return (
    <article className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{formatValue(item.summary || "外部验证结果")}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {formatValue(item.source)} / {formatValue(item.subject_id || item.source_ref)}
          </p>
        </div>
        <span className="rounded-md border bg-background px-2 py-1 text-xs">{formatValue(item.status)}</span>
      </div>
      <dl className="mt-4 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">年化收益</dt>
          <dd className="mt-1 font-medium">{formatValue(item.metrics.annual_return)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">最大回撤</dt>
          <dd className="mt-1 font-medium">{formatValue(item.metrics.max_drawdown)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">夏普</dt>
          <dd className="mt-1 font-medium">{formatValue(item.metrics.sharpe)}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted-foreground">验证日期：{formatValue(item.validation_date)}</p>
    </article>
  );
}

export function AdvisorToday() {
  const state = useSnapshot<AdvisorTodaySnapshot>(() =>
    api.getAdvisorTodaySnapshot({ portfolio_id: PORTFOLIO_ID, as_of_date: today() }),
  );
  return (
    <PageState state={state}>
      {(data) => (
        <AdvisorShell title={data.title} headline={data.headline} eyebrow="投资助手总览" icon={<BookOpenCheck className="h-3.5 w-3.5" />}>
          <div className="mb-4"><ResearchBadge /></div>
          <SummaryGrid cards={data.summary_cards} />
          <section className="mt-5 grid gap-3 lg:grid-cols-2">
            {data.primary_actions.length ? data.primary_actions.map((item, index) => (
              <ActionCard key={`${item.type}-${item.ticker}-${index}`} item={item} />
            )) : <EmptyState text="当前没有需要优先处理的行动。" />}
          </section>
        </AdvisorShell>
      )}
    </PageState>
  );
}

export function AdvisorHoldings() {
  const state = useSnapshot<AdvisorHoldingsSnapshot>(() =>
    api.getAdvisorHoldingsSnapshot({ portfolio_id: PORTFOLIO_ID, as_of_date: today() }),
  );
  return (
    <PageState state={state}>
      {(data) => (
        <AdvisorShell title={data.title} headline={data.headline} eyebrow="持仓看护" icon={<BriefcaseBusiness className="h-3.5 w-3.5" />}>
          <SummaryGrid cards={[
            { label: "持仓数量", value: data.portfolio_summary.position_count },
            { label: "市值", value: data.portfolio_summary.market_value },
            { label: "浮动盈亏", value: data.portfolio_summary.unrealized_pnl },
            { label: "总盈亏", value: data.portfolio_summary.total_pnl },
          ]} />
          <section className="mt-5 grid gap-3 lg:grid-cols-2">
            {data.diagnostics.length ? data.diagnostics.map((item) => (
              <DiagnosticCard key={item.ticker} item={item} />
            )) : <EmptyState text="当前没有持仓记录。" />}
          </section>
        </AdvisorShell>
      )}
    </PageState>
  );
}

export function AdvisorWatchlist() {
  const state = useSnapshot<AdvisorWatchlistSnapshot>(() =>
    api.getAdvisorWatchlistSnapshot({ portfolio_id: PORTFOLIO_ID, as_of_date: today() }),
  );
  return (
    <PageState state={state}>
      {(data) => (
        <AdvisorShell title={data.title} headline={data.headline} eyebrow="候选看护" icon={<Eye className="h-3.5 w-3.5" />}>
          <SummaryGrid cards={[
            { label: "候选数量", value: data.candidates.length },
            { label: "暂不买条目", value: data.do_not_buy_items.length },
            { label: "可试探", value: data.status_counts.ready_small_probe || 0 },
            { label: "等待买点", value: data.status_counts.waiting_trigger || 0 },
          ]} />
          <section className="mt-5 grid gap-3 lg:grid-cols-2">
            {data.candidates.length ? data.candidates.map((item) => (
              <CandidateCard key={item.ticker} item={item} />
            )) : <EmptyState text="当前没有观察候选。" />}
          </section>
          <section className="mt-6">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <CircleAlert className="h-4 w-4 text-warning" />
              当前阶段暂不买
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {data.do_not_buy_items.length ? data.do_not_buy_items.map((item, index) => (
                <RiskCard key={`${item.ticker}-${item.rule_id}-${index}`} item={item} />
              )) : <EmptyState text="当前没有进入暂不买清单的候选。" />}
            </div>
          </section>
        </AdvisorShell>
      )}
    </PageState>
  );
}

export function AdvisorJournal() {
  const state = useSnapshot<AdvisorJournalSnapshot>(() =>
    api.getAdvisorJournalSnapshot({ portfolio_id: PORTFOLIO_ID, limit: 50 }),
  );
  return (
    <PageState state={state}>
      {(data) => (
        <AdvisorShell title={data.title} headline={data.headline} eyebrow="投资记忆" icon={<Target className="h-3.5 w-3.5" />}>
          <SummaryGrid cards={[
            { label: "指令记录", value: data.commands.length },
            { label: "系统建议", value: data.recommendations.length },
            { label: "外部验证", value: data.external_validations.length },
            { label: "决策复盘", value: data.decision_journals?.length ?? 0 },
            { label: "总记录", value: data.record_count },
          ]} />
          <section className="mt-5 grid gap-3 lg:grid-cols-2">
            {data.recommendations.length ? data.recommendations.slice(0, 8).map((item, index) => (
              <article key={String(item.recommendation_id || index)} className="rounded-lg border bg-card p-4">
                <p className="text-sm font-semibold">{formatValue(item.action_label || item.action_type)}</p>
                <p className="mt-1 text-xs text-muted-foreground">{formatValue(item.ticker_name)} / {formatValue(item.ticker)}</p>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{formatValue(item.reason)}</p>
              </article>
            )) : <EmptyState text="当前没有系统建议记录。" />}
          </section>
          <section className="mt-5 grid gap-3 lg:grid-cols-2">
            {data.external_validations.length ? data.external_validations.slice(0, 6).map((item) => (
              <ValidationCard key={item.validation_id} item={item} />
            )) : <EmptyState text="当前没有外部验证写回记录。" />}
          </section>
        </AdvisorShell>
      )}
    </PageState>
  );
}
