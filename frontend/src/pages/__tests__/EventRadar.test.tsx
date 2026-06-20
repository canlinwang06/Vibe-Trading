import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EventRadar } from "../EventRadar";
import type {
  EventRadarClusterListResponse,
  EventRadarCollectResponse,
  EventRadarEventListResponse,
  EventRadarExtractResponse,
  EventRadarMapResponse,
  EventRawDocumentListResponse,
  EventSectorMappingListResponse,
  EventSourceListResponse,
  EventStockMappingListResponse,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  listEventSources: vi.fn(),
  listEventRawDocuments: vi.fn(),
  listEventRadarClusters: vi.fn(),
  listEventRadarEvents: vi.fn(),
  listEventSectorMappings: vi.fn(),
  listEventStockMappings: vi.fn(),
  collectEventDocuments: vi.fn(),
  extractEventRadarEvents: vi.fn(),
  mapEventRadarEvents: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  api: apiMock,
}));

const sourcesResponse: EventSourceListResponse = {
  source_count: 1,
  sources: [
    {
      source_id: "gov_policy_cn",
      source_name: "国务院政策文件",
      source_type: "policy",
      endpoint_type: "html",
      url_or_route: "https://www.gov.cn/zhengce/",
      fetch_interval_minutes: 240,
      parser: "public_page_list",
      credibility: 1,
      legal_mode: "public_page",
      enabled: true,
      last_fetch_time: null,
      created_at: "2026-06-19T08:00:00",
      updated_at: "2026-06-19T08:00:00",
    },
  ],
};

const documentsResponse: EventRawDocumentListResponse = {
  document_count: 1,
  documents: [
    {
      doc_id: "raw_ai",
      source_id: "gov_policy_cn",
      source_name: "国务院政策文件",
      source_type: "policy",
      title: "AI 产业链事件跟踪",
      content: "政策支持 AI 算力、数据中心和光模块产业链建设。",
      summary: "AI 产业链事件跟踪",
      publish_time: "2026-06-19T08:30:00",
      crawl_time: "2026-06-19T08:35:00",
      url: null,
      content_hash: "hash",
      language: "zh-CN",
      author_or_account: null,
      hot_rank: null,
      hot_value: null,
      raw_json: {},
      credibility: 1,
      created_at: "2026-06-19T08:35:00",
    },
  ],
};

const clustersResponse: EventRadarClusterListResponse = {
  cluster_count: 1,
  clusters: [
    {
      cluster_id: "clu_ai",
      first_seen_time: "2026-06-19T08:35:00",
      last_seen_time: "2026-06-19T08:35:00",
      main_title: "政策支持 AI 算力产业链建设",
      event_type: "政策",
      event_subtype: "AI算力",
      summary: "政策支持 AI 算力、数据中心和光模块产业链建设。",
      sentiment: "positive",
      intensity: 4,
      novelty: 4,
      hot_score: 1.2,
      a_share_relevance_score: 0.9,
      source_count: 1,
      mention_count: 1,
      cross_platform_score: 0.33,
      status: "active",
      created_at: "2026-06-19T08:35:00",
      updated_at: "2026-06-19T08:35:00",
    },
  ],
};

const eventsResponse: EventRadarEventListResponse = {
  event_count: 1,
  events: [
    {
      event_id: "evt_ai",
      cluster_id: "clu_ai",
      doc_id: "raw_ai",
      event_time: "2026-06-19T08:30:00",
      publish_time: "2026-06-19T08:30:00",
      crawl_time: "2026-06-19T08:35:00",
      knowable_time: "2026-06-19T08:35:00",
      tradable_time: "2026-06-19T09:30:00",
      event_type: "政策",
      event_subtype: "AI算力",
      summary: "政策支持 AI 算力、数据中心和光模块产业链建设。",
      sentiment: "positive",
      intensity: 4,
      novelty: 4,
      certainty: 0.88,
      a_share_relevance_score: 0.9,
      policy_level: "national",
      created_at: "2026-06-19T08:35:00",
    },
  ],
};

const sectorMappingsResponse: EventSectorMappingListResponse = {
  row_count: 1,
  sector_mappings: [
    {
      event_id: "evt_ai",
      cluster_id: "clu_ai",
      sector_id: "theme_ai_compute",
      sector_name: "AI算力",
      theme: "AI算力",
      sub_theme: "光模块",
      relevance: 0.92,
      direction: "positive",
      mapping_reason: "AI 算力主题匹配。",
      created_at: "2026-06-19T08:40:00",
    },
  ],
};

const stockMappingsResponse: EventStockMappingListResponse = {
  row_count: 1,
  stock_mappings: [
    {
      event_id: "evt_ai",
      cluster_id: "clu_ai",
      ticker: "300308.SZ",
      ticker_name: "中际旭创",
      theme: "AI算力",
      sector_id: "theme_ai_compute",
      relevance: 0.92,
      direction: "positive",
      mapping_reason: "光模块代表公司。",
      created_at: "2026-06-19T08:40:00",
    },
  ],
};

const collectResponse: EventRadarCollectResponse = {
  status: "ok",
  requested: 1,
  inserted: 1,
  duplicates: 0,
  doc_ids: ["raw_ai"],
  duplicate_doc_ids: [],
  source_ids: ["gov_policy_cn"],
  crawl_time: "2026-06-19T08:35:00",
};

const extractResponse: EventRadarExtractResponse = {
  status: "ok",
  requested: 1,
  extracted: 1,
  skipped_low_relevance: 0,
  event_ids: ["evt_ai"],
  cluster_ids: ["clu_ai"],
};

const mapResponse: EventRadarMapResponse = {
  status: "ok",
  requested_events: 1,
  mapped_events: 1,
  sector_rows_written: 1,
  stock_rows_written: 1,
  event_ids: ["evt_ai"],
};

function mockOverview() {
  apiMock.listEventSources.mockResolvedValue(sourcesResponse);
  apiMock.listEventRawDocuments.mockResolvedValue(documentsResponse);
  apiMock.listEventRadarClusters.mockResolvedValue(clustersResponse);
  apiMock.listEventRadarEvents.mockResolvedValue(eventsResponse);
  apiMock.listEventSectorMappings.mockResolvedValue(sectorMappingsResponse);
  apiMock.listEventStockMappings.mockResolvedValue(stockMappingsResponse);
}

async function waitForReady() {
  await waitFor(() => expect(screen.getByRole("button", { name: "导入本地文档" })).not.toBeDisabled());
}

describe("EventRadar page", () => {
  beforeEach(() => {
    Object.values(apiMock).forEach((mock) => mock.mockReset());
    mockOverview();
  });

  it("renders the Chinese event radar workbench and loaded context", async () => {
    render(<EventRadar />);

    expect(screen.getByText("事件雷达")).toBeInTheDocument();
    expect(screen.getByDisplayValue("AI 产业链事件跟踪")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新雷达" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导入本地文档" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "抽取事件" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "映射板块股票" })).toBeInTheDocument();

    expect((await screen.findAllByText("国务院政策文件")).length).toBeGreaterThan(0);
    expect(screen.getByText("政策支持 AI 算力产业链建设")).toBeInTheDocument();
    expect(screen.getByText("中际旭创")).toBeInTheDocument();
  });

  it("imports a local document through the event collection API", async () => {
    apiMock.collectEventDocuments.mockResolvedValueOnce(collectResponse);
    render(<EventRadar />);
    await waitForReady();

    fireEvent.click(screen.getByRole("button", { name: "导入本地文档" }));

    await waitFor(() => expect(apiMock.collectEventDocuments).toHaveBeenCalledTimes(1));
    expect(apiMock.collectEventDocuments).toHaveBeenCalledWith({
      documents: [expect.objectContaining({
        source_id: "gov_policy_cn",
        title: "AI 产业链事件跟踪",
        language: "zh-CN",
      })],
    });
    expect(await screen.findByText("已导入 1 条文档，重复 0 条。")).toBeInTheDocument();
  });

  it("extracts and maps events through the local APIs", async () => {
    apiMock.extractEventRadarEvents.mockResolvedValueOnce(extractResponse);
    apiMock.mapEventRadarEvents.mockResolvedValueOnce(mapResponse);
    render(<EventRadar />);
    await waitForReady();

    fireEvent.click(screen.getByRole("button", { name: "抽取事件" }));
    await waitFor(() => expect(apiMock.extractEventRadarEvents).toHaveBeenCalledTimes(1));
    expect(apiMock.extractEventRadarEvents).toHaveBeenCalledWith({
      limit: 100,
      min_relevance: 0.45,
    });
    expect(await screen.findByText("已抽取 1 个事件，过滤低相关 0 个。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "映射板块股票" }));
    await waitFor(() => expect(apiMock.mapEventRadarEvents).toHaveBeenCalledTimes(1));
    expect(apiMock.mapEventRadarEvents).toHaveBeenCalledWith({
      limit: 100,
      min_relevance: 0.45,
    });
    expect(await screen.findByText("已映射 1 个事件，写入 1 条板块映射和 1 条股票映射。")).toBeInTheDocument();
  });

  it("shows Chinese validation and API errors", async () => {
    render(<EventRadar />);
    await waitForReady();

    fireEvent.change(screen.getByLabelText("抽取上限"), { target: { value: "9999" } });
    fireEvent.click(screen.getByRole("button", { name: "抽取事件" }));
    expect(await screen.findByText("抽取上限必须是 1 到 500 之间的整数。")).toBeInTheDocument();
    expect(apiMock.extractEventRadarEvents).not.toHaveBeenCalled();

    apiMock.mapEventRadarEvents.mockRejectedValueOnce(new Error("没有可映射的事件，请先运行事件抽取。"));
    fireEvent.change(screen.getByLabelText("抽取上限"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "映射板块股票" }));
    expect(await screen.findByText("没有可映射的事件，请先运行事件抽取。")).toBeInTheDocument();
  });
});
