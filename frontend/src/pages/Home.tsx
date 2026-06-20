import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  ClipboardList,
  Database,
  Layers,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api, type DailyIntelligenceResponse, type DashboardSectorHeat } from "@/lib/api";
import { cn } from "@/lib/utils";

const fallbackDailyIntelligence: DailyIntelligenceResponse = {
  status: "ok",
  as_of_date: new Date().toISOString().slice(0, 10),
  data_mode: "sample",
  headline: "AI算力处于偏热状态，建议先形成候选策略并送聚宽验证。",
  market_temperature: { score: 74, label: "偏热，适合生成候选策略", heat: 0.78, event_relevance: 0.71 },
  market_metrics: [
    { label: "上证指数", value: "样例", delta: "待采集", tone: "warning" },
    { label: "沪深300", value: "样例", delta: "待采集", tone: "warning" },
    { label: "成交额", value: "样例", delta: "待采集", tone: "warning" },
    { label: "涨停数量", value: "样例", delta: "待采集", tone: "warning" },
  ],
  sector_heat: [
    { sector_id: "theme_ai_compute", sector_name: "AI算力", event_heat: 0.88, market_confirm: 0.72, breadth_score: 0.64, flow_score: 0.8, persistence_score: 0.76, crowding_risk: 0.58, sector_heat_score: 0.88, cycle_stage: "sample" },
    { sector_id: "theme_optical_module", sector_name: "光模块", event_heat: 0.81, market_confirm: 0.68, breadth_score: 0.59, flow_score: 0.72, persistence_score: 0.7, crowding_risk: 0.62, sector_heat_score: 0.81, cycle_stage: "sample" },
    { sector_id: "theme_server", sector_name: "服务器", event_heat: 0.73, market_confirm: 0.61, breadth_score: 0.55, flow_score: 0.67, persistence_score: 0.64, crowding_risk: 0.44, sector_heat_score: 0.73, cycle_stage: "sample" },
    { sector_id: "theme_robotics", sector_name: "机器人", event_heat: 0.58, market_confirm: 0.52, breadth_score: 0.48, flow_score: 0.55, persistence_score: 0.53, crowding_risk: 0.36, sector_heat_score: 0.58, cycle_stage: "sample" },
  ],
  event_timeline: [
    { event_id: "sample_evt_ai_1", theme: "AI算力", summary: "国产算力招标扩容进入市场关注区。", time: "09:45", relevance: 0.88, certainty: 0.72, source_name: "样例事件库", source_type: "sample", source_url: null, verification_status: "样例" },
    { event_id: "sample_evt_ai_2", theme: "光模块", summary: "海外AI芯片需求预期上修带动光模块关注。", time: "10:30", relevance: 0.82, certainty: 0.68, source_name: "样例事件库", source_type: "sample", source_url: null, verification_status: "样例" },
    { event_id: "sample_evt_ai_3", theme: "液冷", summary: "液冷服务器订单线索等待二次核验。", time: "13:15", relevance: 0.64, certainty: 0.52, source_name: "样例事件库", source_type: "sample", source_url: null, verification_status: "待核验" },
  ],
  source_freshness: [
    { source_type: "policy", source_name: "官方政策", enabled_count: 2, source_count: 2, fetched_count: 0, credibility: 1, status: "待采集" },
    { source_type: "market_data", source_name: "行情板块", enabled_count: 3, source_count: 3, fetched_count: 0, credibility: 0.8, status: "待采集" },
    { source_type: "finance_news", source_name: "财经媒体", enabled_count: 2, source_count: 2, fetched_count: 0, credibility: 0.71, status: "待采集" },
  ],
  codex_actions: ["让 Codex 基于今日热点生成候选策略卡", "让 Codex 将候选策略送入聚宽任务中心", "让 Codex 汇总缺失数据源并给出补采建议"],
  warnings: ["当前页面使用样例结构数据；请先完成数据采集后再作为研究依据。"],
  research_only: true,
  live_trading: false,
};

function percent(value: number): string {
  return `${Math.round(value * 100)}`;
}

function toneClass(tone?: string): string {
  if (tone === "success") return "text-success";
  if (tone === "danger") return "text-destructive";
  if (tone === "warning") return "text-warning";
  return "text-info";
}

function HeatBar({ sector }: { sector: DashboardSectorHeat }) {
  const width = `${Math.max(6, Math.min(100, sector.sector_heat_score * 100))}%`;
  return (
    <div className="grid gap-2 sm:grid-cols-[96px_minmax(0,1fr)_40px] sm:items-center">
      <div className="text-sm font-medium">{sector.sector_name}</div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width }} />
      </div>
      <div className="text-sm font-semibold text-muted-foreground">{percent(sector.sector_heat_score)}</div>
    </div>
  );
}

export function Home() {
  const [data, setData] = useState<DailyIntelligenceResponse>(fallbackDailyIntelligence);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.getDailyIntelligence()
      .then((response) => {
        if (active) setData(response);
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : "每日市场情报暂不可用。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const sampleMode = data.data_mode !== "local";

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          统一情报入口
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight">每日市场情报</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              系统每天汇总可信互联网数据、市场表现和热点事件，只把结论、证据和下一步动作呈现给你。
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs text-muted-foreground">
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> : <ShieldCheck className="h-3.5 w-3.5 text-success" />}
            Codex 指挥层
          </div>
        </div>
      </header>

      {loadError ? (
        <section className="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm text-warning">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4" />
            <p>{loadError} 当前显示样例结构，便于确认页面流程。</p>
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <article className="rounded-lg border bg-card p-5">
          <p className="text-sm font-semibold">今日一句话结论</p>
          <h2 className="mt-4 max-w-3xl text-xl font-semibold leading-8">{data.headline}</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">研究模式</span>
            <span className="rounded-md border bg-warning/5 px-2.5 py-1 text-xs text-warning">需聚宽验证</span>
            <span className="rounded-md border bg-info/5 px-2.5 py-1 text-xs text-info">不自动实盘</span>
            {sampleMode ? <span className="rounded-md border bg-muted/40 px-2.5 py-1 text-xs text-muted-foreground">样例/待采集</span> : null}
          </div>
        </article>

        <article className="rounded-lg border bg-card p-5">
          <p className="text-sm font-semibold">市场温度</p>
          <div className="mt-4 flex items-end gap-4">
            <span className="text-5xl font-semibold text-primary">{Math.round(data.market_temperature.score)}</span>
            <span className="pb-2 text-sm font-medium">{data.market_temperature.label}</span>
          </div>
          <div className="mt-4 h-3 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, data.market_temperature.score)}%` }} />
          </div>
        </article>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.market_metrics.map((metric) => (
          <article key={metric.label} className="rounded-lg border bg-card p-4">
            <p className="text-xs text-muted-foreground">{metric.label}</p>
            <p className="mt-2 text-xl font-semibold">{metric.value}</p>
            {metric.delta ? <p className={cn("mt-1 text-xs font-medium", toneClass(metric.tone))}>{metric.delta}</p> : null}
          </article>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">热点板块强度</h2>
          </div>
          <div className="mt-6 grid gap-5">
            {data.sector_heat.slice(0, 6).map((sector) => (
              <HeatBar key={sector.sector_id} sector={sector} />
            ))}
          </div>
          <p className="mt-6 text-xs leading-5 text-muted-foreground">
            展示的是综合热度，不等于买入建议。板块分析会进一步拆到候选股票和策略卡。
          </p>
        </article>

        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">今日关键事件</h2>
          </div>
          <div className="mt-6 grid gap-4">
            {data.event_timeline.slice(0, 5).map((event) => (
              <div key={event.event_id} className="grid grid-cols-[12px_minmax(0,1fr)_76px] gap-3">
                <span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-primary" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{event.summary}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    来源：{event.source_name} / 相关度 {percent(event.relevance)}
                  </p>
                </div>
                <span className="h-fit rounded-md border bg-muted/30 px-2 py-1 text-center text-xs text-muted-foreground">
                  {event.verification_status}
                </span>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">数据源健康度</h2>
          </div>
          <div className="mt-5 grid gap-3">
            {data.source_freshness.slice(0, 5).map((source) => (
              <div key={source.source_type} className="grid gap-2 sm:grid-cols-[92px_minmax(0,1fr)_72px] sm:items-center">
                <span className="text-sm font-medium">{source.source_name}</span>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-info" style={{ width: `${Math.max(8, source.credibility * 100)}%` }} />
                </div>
                <span className="text-xs text-muted-foreground">{source.status}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">Codex 建议动作</h2>
          </div>
          <div className="mt-5 grid gap-3">
            {data.codex_actions.map((action, index) => (
              <div key={action} className="flex items-center justify-between gap-3 rounded-lg border bg-background p-3 text-sm">
                <span>{index + 1}. {action}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </div>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90" to="/sector-stock-analysis">
              进入板块及股票分析
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted" to="/event-records">
              查看事件记录库
            </Link>
          </div>
        </article>
      </section>

      {data.warnings.length ? (
        <section className="rounded-lg border bg-muted/20 p-4">
          <div className="flex items-start gap-3">
            <BarChart3 className="mt-0.5 h-4 w-4 text-primary" />
            <div className="space-y-1 text-sm leading-6 text-muted-foreground">
              {data.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
