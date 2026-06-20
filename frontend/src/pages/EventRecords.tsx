import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3, CalendarDays, ExternalLink, FileText, Loader2, ShieldCheck } from "lucide-react";
import { api, type EventRecord, type EventRecordListResponse } from "@/lib/api";

const fallbackRecords: EventRecord[] = [
  {
    event_id: "sample_evt_ai_1",
    cluster_id: "sample_cluster_ai",
    doc_id: "sample_doc_ai_1",
    event_type: "industry",
    event_subtype: "AI算力",
    summary: "国产算力招标扩容进入市场关注区，光模块、服务器和液冷链条被反复提及。",
    sentiment: "positive",
    intensity: 82,
    novelty: 70,
    certainty: 0.72,
    a_share_relevance_score: 0.88,
    publish_time: "2026-06-20T09:45:00",
    crawl_time: "2026-06-20T09:50:00",
    knowable_time: "2026-06-20T09:50:00",
    tradable_time: "2026-06-20T09:50:00",
    source_name: "样例事件库",
    source_type: "sample",
    source_url: null,
    local_document_ref: "raw_documents:sample_doc_ai_1",
    evidence: {},
    related_sectors: [{ event_id: "sample_evt_ai_1", cluster_id: "sample_cluster_ai", sector_id: "theme_ai_compute", sector_name: "AI算力", theme: "AI算力", sub_theme: "算力基础设施", relevance: 0.92, direction: "positive", mapping_reason: "事件直接提及国产算力扩容。", created_at: "2026-06-20T09:50:00" }],
    related_stocks: [{ event_id: "sample_evt_ai_1", cluster_id: "sample_cluster_ai", ticker: "300308.SZ", ticker_name: "中际旭创", theme: "AI算力", sector_id: "theme_optical_module", relevance: 0.88, direction: "positive", mapping_reason: "光模块链条相关。", created_at: "2026-06-20T09:50:00" }],
    impact: {},
    impact_t1: { window: "T+1", status: "available", reaction_count: 8, sector_count: 3, stock_count: 5, avg_raw_return: 0.018, avg_abnormal_return: 0.012, worst_max_drawdown: -0.026 },
    impact_t5: { window: "T+5", status: "available", reaction_count: 8, sector_count: 3, stock_count: 5, avg_raw_return: 0.031, avg_abnormal_return: 0.018, worst_max_drawdown: -0.045 },
    impact_t20: { window: "T+20", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
    impact_t60: { window: "T+60", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
  },
];

const fallbackResponse: EventRecordListResponse = {
  status: "ok",
  records: fallbackRecords,
  record_count: fallbackRecords.length,
  impact_windows: ["T+1", "T+5", "T+20", "T+60"],
  research_only: true,
  live_trading: false,
};

function formatDateTime(value?: string | null): string {
  if (!value) return "未记录";
  return value.replace("T", " ").slice(0, 16);
}

function impactLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) return "待沉淀";
  return `${Math.round(value * 10000) / 100}%`;
}

export function EventRecords() {
  const [data, setData] = useState<EventRecordListResponse>(fallbackResponse);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.listEventRecords({ limit: 20, min_relevance: 0.4 })
      .then((response) => {
        if (active && response.records.length) setData(response);
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : "事件记录暂不可用。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const records = data.records;
  const verifiedCount = records.filter((record) => record.certainty >= 0.7).length;
  const sourceCount = new Set(records.map((record) => record.source_name || record.source_type)).size;
  const topTheme = useMemo(() => {
    const counts = records.reduce<Record<string, number>>((acc, record) => {
      acc[record.event_subtype] = (acc[record.event_subtype] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || "综合事件";
  }, [records]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <FileText className="h-3.5 w-3.5 text-primary" />
          客观事件沉淀
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight">事件记录库</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              这里不做买卖判断，只保存事实、来源链接、时间线和事件发生后的真实影响。
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs text-muted-foreground">
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> : <ShieldCheck className="h-3.5 w-3.5 text-success" />}
            Codex 可调取
          </div>
        </div>
      </header>

      {loadError ? (
        <section className="rounded-lg border bg-warning/5 p-4 text-sm text-warning">
          {loadError} 当前显示样例记录结构，真实采集完成后会自动替换。
        </section>
      ) : null}

      <section className="rounded-lg border bg-card p-5">
        <p className="text-sm font-semibold">今日事件摘要</p>
        <h2 className="mt-4 max-w-4xl text-lg font-semibold leading-8">
          {topTheme} 相关事件共 {data.record_count} 条，来自 {sourceCount} 类来源，其中 {verifiedCount} 条达到较高可信度。事件只作为研究证据，不直接生成买卖指令。
        </h2>
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="rounded-md border bg-info/5 px-2.5 py-1 text-xs text-info">{data.record_count} 条事件</span>
          <span className="rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">{verifiedCount} 条高可信</span>
          <span className="rounded-md border bg-warning/5 px-2.5 py-1 text-xs text-warning">{records.length - verifiedCount} 条待确认</span>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">事件证据链</h2>
          </div>
          <div className="mt-5 grid gap-3">
            {records.slice(0, 6).map((record) => (
              <div key={record.event_id} className="grid gap-3 rounded-lg border bg-background p-4 md:grid-cols-[92px_minmax(0,1fr)_120px] md:items-center">
                <span className="text-xs text-muted-foreground">{formatDateTime(record.knowable_time)}</span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{record.summary}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {record.source_name || "本地事件库"} / {record.event_subtype} / 相关度 {Math.round(record.a_share_relevance_score * 100)}
                  </p>
                </div>
                {record.source_url ? (
                  <a
                    className="inline-flex items-center justify-center gap-1 rounded-md border px-2 py-1 text-xs text-info hover:bg-muted"
                    href={record.source_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    原文链接
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <span className="rounded-md border bg-muted/30 px-2 py-1 text-center text-xs text-muted-foreground">
                    本地归档
                  </span>
                )}
              </div>
            ))}
          </div>
        </article>

        <aside className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">历史回看</h2>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {["按日", "按月", "按季度", "按年"].map((item, index) => (
              <span key={item} className={`rounded-md border px-2.5 py-1 text-xs ${index === 0 ? "bg-primary/10 text-primary" : "bg-muted/30 text-muted-foreground"}`}>
                {item}
              </span>
            ))}
          </div>
          <div className="mt-6 grid grid-cols-10 gap-2">
            {Array.from({ length: 30 }).map((_, index) => {
              const opacity = 0.2 + ((index * 7) % 9) / 12;
              return <span key={index} className="h-5 rounded bg-primary" style={{ opacity }} />;
            })}
          </div>
          <p className="mt-5 text-sm leading-6 text-muted-foreground">
            事件会按日期归档在本地事件库。你可以直接对 Codex 说：调出某个月 AI算力事件，或比较最近三个月的板块影响。
          </p>
        </aside>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">事件影响沉淀</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            事件发生后，系统会持续记录相关板块和个股在 T+1、T+5、T+20、T+60 后的表现，用于以后判断类似事件是否真的有效。
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            {["impact_t1", "impact_t5", "impact_t20"].map((key) => {
              const impact = records[0]?.[key as "impact_t1" | "impact_t5" | "impact_t20"];
              return (
                <div key={key} className="rounded-lg border bg-background p-4">
                  <p className="text-xs text-muted-foreground">{impact?.window || key}</p>
                  <p className="mt-2 text-lg font-semibold">{impactLabel(impact?.avg_abnormal_return)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{impact?.status === "available" ? "已沉淀" : "待沉淀"}</p>
                </div>
              );
            })}
          </div>
        </article>

        <aside className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-semibold">保存与调取</h2>
          <p className="mt-4 text-sm font-medium leading-7">
            所有事件保留原始证据、可信等级和影响沉淀。页面只展示摘要，详细字段可由 Codex 调取。
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">本地归档</span>
            <span className="rounded-md border bg-info/5 px-2.5 py-1 text-xs text-info">可追溯原文</span>
            <span className="rounded-md border bg-primary/5 px-2.5 py-1 text-xs text-primary">可按时间汇总</span>
          </div>
          <Link className="mt-5 inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted" to="/sector-stock-analysis">
            进入板块及股票分析
          </Link>
        </aside>
      </section>
    </div>
  );
}
