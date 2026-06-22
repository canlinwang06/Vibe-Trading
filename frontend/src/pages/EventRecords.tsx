import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  CalendarDays,
  ExternalLink,
  FileText,
  Loader2,
  Radio,
  ShieldCheck,
} from "lucide-react";
import { api, type EventRecord, type EventRecordImpactSummary, type EventRecordListResponse } from "@/lib/api";

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

const impactKeys = [
  { key: "impact_t1", label: "T+1" },
  { key: "impact_t5", label: "T+5" },
  { key: "impact_t20", label: "T+20" },
  { key: "impact_t60", label: "T+60" },
] as const;

type ImpactKey = (typeof impactKeys)[number]["key"];

function formatDateTime(value?: string | null): string {
  if (!value) return "未记录";
  return value.replace("T", " ").slice(0, 16);
}

function formatImpact(value: number | null | undefined): string {
  if (value === null || value === undefined) return "待沉淀";
  return `${Math.round(value * 10000) / 100}%`;
}

function sentimentLabel(value: string): string {
  if (value === "positive") return "偏正面";
  if (value === "negative") return "偏负面";
  return "中性";
}

function countBy(records: EventRecord[], field: "event_subtype" | "event_type" | "sentiment") {
  return Object.entries(
    records.reduce<Record<string, number>>((acc, record) => {
      const key = record[field] || "未分类";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {}),
  ).sort((a, b) => b[1] - a[1]);
}

function average(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function aggregateImpact(records: EventRecord[], key: ImpactKey) {
  const impacts = records.map((record) => record[key]).filter(Boolean) as EventRecordImpactSummary[];
  const values = impacts
    .filter((impact) => impact.status === "available" && typeof impact.avg_abnormal_return === "number")
    .map((impact) => impact.avg_abnormal_return as number);

  return {
    available: values.length,
    pending: Math.max(impacts.length - values.length, 0),
    average: average(values),
  };
}

export function EventRecords() {
  const [data, setData] = useState<EventRecordListResponse>(fallbackResponse);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.listEventRecords({ limit: 20, min_relevance: 0.4 })
      .then((response) => {
        if (active) setData(response);
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : "热点记录暂不可用。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const records = data.records;
  const recordCount = data.record_count || records.length;
  const verifiedCount = records.filter((record) => record.certainty >= 0.7).length;
  const linkedCount = records.filter((record) => Boolean(record.source_url)).length;
  const sourceCount = new Set(records.map((record) => record.source_name || record.source_type || "本地归档")).size;
  const topTheme = countBy(records, "event_subtype")[0]?.[0] || "暂无热点";
  const eventTypeCounts = countBy(records, "event_type").slice(0, 4);
  const sentimentCounts = countBy(records, "sentiment");
  const negativeCount = records.filter((record) => record.sentiment === "negative").length;
  const avgRelevance = average(records.map((record) => record.a_share_relevance_score));
  const t1Impact = aggregateImpact(records, "impact_t1");

  const agentBriefs = useMemo(() => {
    return [
      {
        title: "新闻观察员",
        value: `${sourceCount} 类来源`,
        body: `${linkedCount} 条可打开原文，${Math.max(recordCount - linkedCount, 0)} 条保留本地归档。`,
      },
      {
        title: "事件分析员",
        value: topTheme,
        body: `${recordCount} 条近期事实，${verifiedCount} 条可信度达到 70% 以上。`,
      },
      {
        title: "市场反应员",
        value: formatImpact(t1Impact.average),
        body: t1Impact.available ? `已沉淀 ${t1Impact.available} 条 T+1 反应。` : "影响还在等待交易日沉淀。",
      },
      {
        title: "风险观察员",
        value: negativeCount ? `${negativeCount} 条偏负面` : "未见明显偏负面",
        body: "这里只记录事实和风险变化，不直接生成买卖指令。",
      },
    ];
  }, [linkedCount, negativeCount, recordCount, sourceCount, t1Impact.available, t1Impact.average, topTheme, verifiedCount]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Radio className="h-3.5 w-3.5 text-primary" />
          客观事实窗口
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight">热点记录</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              近期新闻、公告和市场事实的摘要视图。页面只做记录和归因，不给买卖结论。
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs text-muted-foreground">
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> : <ShieldCheck className="h-3.5 w-3.5 text-success" />}
            本地归档 · Codex 可调取
          </div>
        </div>
      </header>

      {loadError ? (
        <section className="rounded-lg border bg-warning/5 p-4 text-sm text-warning">
          {loadError} 当前显示样例结构，真实采集恢复后会自动替换。
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.8fr)]">
        <article className="rounded-lg border bg-card p-5">
          <p className="text-sm font-semibold">今日事实简报</p>
          <h2 className="mt-4 max-w-4xl text-xl font-semibold leading-8">
            {recordCount ? `${topTheme} 是近期最高频主题，共记录 ${recordCount} 条事实。` : "暂无已入库的热点事件。"}
          </h2>
          <div className="mt-5 grid gap-3 sm:grid-cols-4">
            <div className="rounded-md border bg-background p-3">
              <p className="text-xs text-muted-foreground">事件数</p>
              <p className="mt-1 text-xl font-semibold">{recordCount}</p>
            </div>
            <div className="rounded-md border bg-background p-3">
              <p className="text-xs text-muted-foreground">高可信</p>
              <p className="mt-1 text-xl font-semibold">{verifiedCount}</p>
            </div>
            <div className="rounded-md border bg-background p-3">
              <p className="text-xs text-muted-foreground">原文链接</p>
              <p className="mt-1 text-xl font-semibold">{linkedCount}</p>
            </div>
            <div className="rounded-md border bg-background p-3">
              <p className="text-xs text-muted-foreground">A股相关</p>
              <p className="mt-1 text-xl font-semibold">{avgRelevance === null ? "-" : Math.round(avgRelevance * 100)}</p>
            </div>
          </div>
        </article>

        <aside className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">事实结构</h2>
          </div>
          <div className="mt-5 space-y-4">
            {eventTypeCounts.length ? eventTypeCounts.map(([label, count]) => (
              <div key={label}>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{label}</span>
                  <span>{count}</span>
                </div>
                <div className="mt-2 h-2 rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.max((count / recordCount) * 100, 8)}%` }} />
                </div>
              </div>
            )) : (
              <p className="text-sm text-muted-foreground">采集完成后展示事件类型分布。</p>
            )}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {sentimentCounts.map(([label, count]) => (
              <span key={label} className="rounded-md border bg-muted/30 px-2.5 py-1 text-xs text-muted-foreground">
                {sentimentLabel(label)} {count}
              </span>
            ))}
          </div>
        </aside>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {agentBriefs.map((brief) => (
          <article key={brief.title} className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              <p className="text-sm font-semibold">{brief.title}</p>
            </div>
            <p className="mt-4 text-lg font-semibold">{brief.value}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{brief.body}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <article className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">近期动态</h2>
          </div>
          <div className="mt-5 grid gap-3">
            {records.slice(0, 8).map((record) => (
              <div key={record.event_id} className="grid gap-3 rounded-lg border bg-background p-4 md:grid-cols-[96px_minmax(0,1fr)_112px] md:items-center">
                <span className="text-xs text-muted-foreground">{formatDateTime(record.knowable_time)}</span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold leading-6">{record.summary}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {record.source_name || "本地事件库"} / {record.event_subtype} / 可信度 {Math.round(record.certainty * 100)}
                  </p>
                </div>
                {record.source_url ? (
                  <a
                    className="inline-flex items-center justify-center gap-1 rounded-md border px-2 py-1 text-xs text-info hover:bg-muted"
                    href={record.source_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    原文
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <span className="rounded-md border bg-muted/30 px-2 py-1 text-center text-xs text-muted-foreground">
                    本地归档
                  </span>
                )}
              </div>
            ))}
            {!records.length ? (
              <div className="rounded-lg border bg-background p-6 text-sm text-muted-foreground">
                暂无事件记录。每日采集任务完成后，这里会展示近期热点和来源链接。
              </div>
            ) : null}
          </div>
        </article>

        <aside className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">历史热度</h2>
          </div>
          <div className="mt-5 grid grid-cols-10 gap-2">
            {Array.from({ length: 30 }).map((_, index) => {
              const opacity = records.length ? 0.18 + ((index * 7) % 9) / 12 : 0.12;
              return <span key={index} className="h-5 rounded bg-primary" style={{ opacity }} />;
            })}
          </div>
          <p className="mt-5 text-sm leading-6 text-muted-foreground">
            可以让 Codex 按日期、月份、主题或来源调取历史事实。
          </p>
        </aside>
      </section>

      <section className="rounded-lg border bg-card p-5">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold">事件影响沉淀</h2>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-4">
          {impactKeys.map(({ key, label }) => {
            const impact = aggregateImpact(records, key);
            return (
              <div key={key} className="rounded-lg border bg-background p-4">
                <p className="text-xs text-muted-foreground">{label} 平均异常收益</p>
                <p className="mt-2 text-lg font-semibold">{formatImpact(impact.average)}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {impact.available ? `${impact.available} 条已沉淀` : `${impact.pending} 条待沉淀`}
                </p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
