import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileInput,
  Layers,
  Loader2,
  Map,
  Newspaper,
  Radar,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  ApiError,
  api,
  type EventRadarCluster,
  type EventRadarCollectResponse,
  type EventRadarEvent,
  type EventRadarExtractResponse,
  type EventRadarMapResponse,
  type EventSectorMapping,
  type EventSourceRecord,
  type EventStockMapping,
  type EventRawDocument,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type LoadingAction = "refresh" | "collect" | "extract" | "map";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function defaultPublishTime(): string {
  return `${today()}T08:30:00+08:00`;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "事件雷达操作失败，请检查本地服务状态。";
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

function formatTime(value: string | null | undefined): string {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function sentimentLabel(value: string): string {
  if (value === "positive") return "正向";
  if (value === "negative") return "负向";
  if (value === "mixed") return "混合";
  if (value === "neutral") return "中性";
  return value;
}

function directionLabel(value: string): string {
  if (value === "positive") return "正向";
  if (value === "negative") return "负向";
  if (value === "neutral") return "中性";
  return value;
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

function SourceList({ sources }: { sources: EventSourceRecord[] }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">信息源</h2>
          <p className="mt-1 text-xs text-muted-foreground">共 {sources.length} 个本地登记源</p>
        </div>
        <Newspaper className="h-4 w-4 text-primary" />
      </div>
      {sources.length ? (
        <div className="mt-4 grid gap-2">
          {sources.slice(0, 6).map((source) => (
            <div key={source.source_id} className="rounded-md border bg-background p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{source.source_name}</p>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{source.source_id}</p>
                </div>
                <span className="rounded-md border bg-muted/30 px-2 py-1 text-[11px] text-muted-foreground">
                  {source.source_type}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>可信度 {formatScore(source.credibility)}</span>
                <span>{source.legal_mode}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无信息源。</p>
      )}
    </section>
  );
}

function DocumentList({ documents }: { documents: EventRawDocument[] }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <h2 className="text-sm font-semibold">最近文档</h2>
      {documents.length ? (
        <div className="mt-4 grid gap-3">
          {documents.slice(0, 4).map((document) => (
            <article key={document.doc_id} className="rounded-md border bg-background p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h3 className="line-clamp-1 text-sm font-medium">{document.title}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">{document.source_name}</p>
                </div>
                <span className="w-fit rounded-md border bg-muted/30 px-2 py-1 text-[11px] text-muted-foreground">
                  {formatTime(document.publish_time)}
                </span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无本地文档。</p>
      )}
    </section>
  );
}

function ClusterPanel({ clusters }: { clusters: EventRadarCluster[] }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">事件聚类</h2>
          <p className="mt-1 text-xs text-muted-foreground">共 {clusters.length} 个聚类</p>
        </div>
        <Sparkles className="h-4 w-4 text-primary" />
      </div>
      {clusters.length ? (
        <div className="mt-4 grid gap-3">
          {clusters.slice(0, 5).map((cluster) => (
            <article key={cluster.cluster_id} className="rounded-lg border bg-background p-4">
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <h3 className="line-clamp-1 text-sm font-semibold">{cluster.main_title}</h3>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{cluster.summary}</p>
                </div>
                <span className="w-fit rounded-md border bg-primary/5 px-2 py-1 text-xs text-primary">
                  {cluster.event_subtype}
                </span>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
                <div>
                  <dt className="text-muted-foreground">热度</dt>
                  <dd className="mt-1 font-medium">{formatScore(cluster.hot_score)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">A 股相关</dt>
                  <dd className="mt-1 font-medium">{formatScore(cluster.a_share_relevance_score)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">情绪</dt>
                  <dd className="mt-1 font-medium">{sentimentLabel(cluster.sentiment)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">来源</dt>
                  <dd className="mt-1 font-medium">{cluster.source_count}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无事件聚类。</p>
      )}
    </section>
  );
}

function EventTable({ events }: { events: EventRadarEvent[] }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <h2 className="text-sm font-semibold">结构化事件</h2>
      {events.length ? (
        <div className="mt-4 overflow-auto rounded-lg border">
          <table className="min-w-[920px] w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">类型</th>
                <th className="px-3 py-2 font-medium">主题</th>
                <th className="px-3 py-2 font-medium">摘要</th>
                <th className="px-3 py-2 font-medium">情绪</th>
                <th className="px-3 py-2 font-medium">强度</th>
                <th className="px-3 py-2 font-medium">可交易时间</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.event_id} className="border-t">
                  <td className="px-3 py-2 font-medium">{event.event_type}</td>
                  <td className="px-3 py-2 text-muted-foreground">{event.event_subtype}</td>
                  <td className="max-w-[360px] px-3 py-2">
                    <span className="line-clamp-2">{event.summary}</span>
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{sentimentLabel(event.sentiment)}</td>
                  <td className="px-3 py-2">{event.intensity}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatTime(event.tradable_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">暂无结构化事件。</p>
      )}
    </section>
  );
}

function MappingPanel({
  sectorMappings,
  stockMappings,
}: {
  sectorMappings: EventSectorMapping[];
  stockMappings: EventStockMapping[];
}) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">映射结果</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            板块 {sectorMappings.length} 条 / 股票 {stockMappings.length} 条
          </p>
        </div>
        <Map className="h-4 w-4 text-primary" />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">板块</th>
                <th className="px-3 py-2 font-medium">主题</th>
                <th className="px-3 py-2 font-medium">相关度</th>
                <th className="px-3 py-2 font-medium">方向</th>
              </tr>
            </thead>
            <tbody>
              {sectorMappings.slice(0, 8).map((row) => (
                <tr key={`${row.event_id}-${row.sector_id}-${row.sub_theme}`} className="border-t">
                  <td className="px-3 py-2 font-medium">{row.sector_name}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.theme}</td>
                  <td className="px-3 py-2">{formatScore(row.relevance)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{directionLabel(row.direction)}</td>
                </tr>
              ))}
              {!sectorMappings.length ? (
                <tr>
                  <td className="px-3 py-4 text-sm text-muted-foreground" colSpan={4}>暂无板块映射。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">股票</th>
                <th className="px-3 py-2 font-medium">主题</th>
                <th className="px-3 py-2 font-medium">相关度</th>
                <th className="px-3 py-2 font-medium">方向</th>
              </tr>
            </thead>
            <tbody>
              {stockMappings.slice(0, 8).map((row) => (
                <tr key={`${row.event_id}-${row.ticker}`} className="border-t">
                  <td className="px-3 py-2">
                    <span className="font-medium">{row.ticker_name}</span>
                    <span className="ml-2 text-muted-foreground">{row.ticker}</span>
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{row.theme}</td>
                  <td className="px-3 py-2">{formatScore(row.relevance)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{directionLabel(row.direction)}</td>
                </tr>
              ))}
              {!stockMappings.length ? (
                <tr>
                  <td className="px-3 py-4 text-sm text-muted-foreground" colSpan={4}>暂无股票映射。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export function EventRadar() {
  const [sourceId, setSourceId] = useState("gov_policy_cn");
  const [documentTitle, setDocumentTitle] = useState("AI 产业链事件跟踪");
  const [documentContent, setDocumentContent] = useState(
    "政策支持数据中心、光模块、服务器、液冷和半导体产业链建设，A 股 AI 算力板块景气度提升。",
  );
  const [publishTime, setPublishTime] = useState(defaultPublishTime());
  const [extractLimit, setExtractLimit] = useState("100");
  const [extractRelevance, setExtractRelevance] = useState("0.45");
  const [mapLimit, setMapLimit] = useState("100");
  const [mapRelevance, setMapRelevance] = useState("0.45");

  const [sources, setSources] = useState<EventSourceRecord[]>([]);
  const [documents, setDocuments] = useState<EventRawDocument[]>([]);
  const [clusters, setClusters] = useState<EventRadarCluster[]>([]);
  const [events, setEvents] = useState<EventRadarEvent[]>([]);
  const [sectorMappings, setSectorMappings] = useState<EventSectorMapping[]>([]);
  const [stockMappings, setStockMappings] = useState<EventStockMapping[]>([]);
  const [collectResult, setCollectResult] = useState<EventRadarCollectResponse | null>(null);
  const [extractResult, setExtractResult] = useState<EventRadarExtractResponse | null>(null);
  const [mapResult, setMapResult] = useState<EventRadarMapResponse | null>(null);
  const [loading, setLoading] = useState<LoadingAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const initialLoadStarted = useRef(false);

  const summary = useMemo(() => ({
    sourceCount: sources.length,
    documentCount: documents.length,
    clusterCount: clusters.length,
    eventCount: events.length,
    mappingCount: sectorMappings.length + stockMappings.length,
  }), [clusters.length, documents.length, events.length, sectorMappings.length, sources.length, stockMappings.length]);

  const loadOverview = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading("refresh");
    setError(null);
    try {
      const sourceResponse = await api.listEventSources({ enabled_only: false });
      const documentResponse = await api.listEventRawDocuments({ limit: 20 });
      const clusterResponse = await api.listEventRadarClusters({ limit: 20, min_relevance: 0 });
      const eventResponse = await api.listEventRadarEvents({ limit: 50, min_relevance: 0 });
      const sectorMapResponse = await api.listEventSectorMappings({ limit: 100 });
      const stockMapResponse = await api.listEventStockMappings({ limit: 100 });
      setSources(sourceResponse.sources);
      setDocuments(documentResponse.documents);
      setClusters(clusterResponse.clusters);
      setEvents(eventResponse.events);
      setSectorMappings(sectorMapResponse.sector_mappings);
      setStockMappings(stockMapResponse.stock_mappings);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      if (showLoading) setLoading(null);
    }
  }, []);

  useEffect(() => {
    if (initialLoadStarted.current) return;
    initialLoadStarted.current = true;
    void loadOverview();
  }, [loadOverview]);

  const collectDocument = async () => {
    setError(null);
    setLoading("collect");
    try {
      if (!sourceId.trim() || !documentTitle.trim() || !documentContent.trim()) {
        throw new Error("信息源、标题和正文不能为空。");
      }
      const response = await api.collectEventDocuments({
        documents: [{
          source_id: sourceId.trim(),
          title: documentTitle.trim(),
          content: documentContent.trim(),
          publish_time: publishTime.trim(),
          summary: documentTitle.trim(),
          language: "zh-CN",
        }],
      });
      setCollectResult(response);
      await loadOverview(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const extractEvents = async () => {
    setError(null);
    setLoading("extract");
    try {
      const response = await api.extractEventRadarEvents({
        limit: parseBoundedInteger(extractLimit, "抽取上限", 1, 500),
        min_relevance: parseBoundedNumber(extractRelevance, "A 股相关度", 0, 1),
      });
      setExtractResult(response);
      await loadOverview(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const mapEvents = async () => {
    setError(null);
    setLoading("map");
    try {
      const response = await api.mapEventRadarEvents({
        limit: parseBoundedInteger(mapLimit, "映射上限", 1, 500),
        min_relevance: parseBoundedNumber(mapRelevance, "映射相关度", 0, 1),
      });
      setMapResult(response);
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
          <Radar className="h-3.5 w-3.5 text-primary" />
          本地事件抽取与映射
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">事件雷达</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              将本地信息源文档转成结构化事件，并映射到 A 股主题、板块和股票，供候选池、回测和风控继续使用。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-success/5 px-3 py-2 text-xs text-success">
            <ShieldCheck className="h-3.5 w-3.5" />
            研究/模拟，不触发交易
          </div>
        </div>
      </header>

      <section className="grid gap-3 md:grid-cols-5">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">信息源</p>
          <p className="mt-1 text-xl font-semibold">{summary.sourceCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">文档</p>
          <p className="mt-1 text-xl font-semibold">{summary.documentCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">事件聚类</p>
          <p className="mt-1 text-xl font-semibold">{summary.clusterCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">结构化事件</p>
          <p className="mt-1 text-xl font-semibold">{summary.eventCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">映射行</p>
          <p className="mt-1 text-xl font-semibold">{summary.mappingCount}</p>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">事件输入</h2>
              <p className="mt-1 text-xs text-muted-foreground">默认任务：AI 产业链事件跟踪</p>
            </div>
            <button
              type="button"
              disabled={isBusy}
              onClick={() => loadOverview()}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-background px-3 text-xs font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "refresh" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              刷新雷达
            </button>
          </div>

          <div className="mt-5 grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                信息源
                <input
                  value={sourceId}
                  onChange={(event) => setSourceId(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                发布时间
                <input
                  value={publishTime}
                  onChange={(event) => setPublishTime(event.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            </div>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              标题
              <input
                value={documentTitle}
                onChange={(event) => setDocumentTitle(event.target.value)}
                className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              正文
              <textarea
                value={documentContent}
                onChange={(event) => setDocumentContent(event.target.value)}
                rows={5}
                className="resize-none rounded-md border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none focus:border-primary"
              />
            </label>
            <button
              type="button"
              disabled={isBusy}
              onClick={collectDocument}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "collect" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileInput className="h-4 w-4" />}
              导入本地文档
            </button>

            <fieldset className="grid gap-3 border-t pt-4">
              <legend className="text-xs font-medium text-muted-foreground">抽取与映射</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  抽取上限
                  <input
                    value={extractLimit}
                    onChange={(event) => setExtractLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  A 股相关度
                  <input
                    value={extractRelevance}
                    onChange={(event) => setExtractRelevance(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  映射上限
                  <input
                    value={mapLimit}
                    onChange={(event) => setMapLimit(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs text-muted-foreground">
                  映射相关度
                  <input
                    value={mapRelevance}
                    onChange={(event) => setMapRelevance(event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                  />
                </label>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={extractEvents}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading === "extract" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  抽取事件
                </button>
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={mapEvents}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading === "map" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Layers className="h-4 w-4" />}
                  映射板块股票
                </button>
              </div>
            </fieldset>

            {error ? <ResultNotice type="warning">{error}</ResultNotice> : null}
            {collectResult ? (
              <ResultNotice type="success">
                已导入 {collectResult.inserted} 条文档，重复 {collectResult.duplicates} 条。
              </ResultNotice>
            ) : null}
            {extractResult ? (
              <ResultNotice type="success">
                已抽取 {extractResult.extracted} 个事件，过滤低相关 {extractResult.skipped_low_relevance} 个。
              </ResultNotice>
            ) : null}
            {mapResult ? (
              <ResultNotice type="success">
                已映射 {mapResult.mapped_events} 个事件，写入 {mapResult.sector_rows_written} 条板块映射和 {mapResult.stock_rows_written} 条股票映射。
              </ResultNotice>
            ) : null}
          </div>
        </section>

        <div className="grid content-start gap-5">
          <div className="grid gap-5 lg:grid-cols-2">
            <SourceList sources={sources} />
            <DocumentList documents={documents} />
          </div>
          <ClusterPanel clusters={clusters} />
          <EventTable events={events} />
          <MappingPanel sectorMappings={sectorMappings} stockMappings={stockMappings} />
        </div>
      </div>
    </div>
  );
}
