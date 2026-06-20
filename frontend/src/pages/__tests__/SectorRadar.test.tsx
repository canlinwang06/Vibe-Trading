import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SectorRadar } from "../SectorRadar";
import type {
  EventRadarThemeMapResponse,
  EventSectorMappingListResponse,
  SectorScoreListResponse,
  SectorScoreRunResponse,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  listSectorScores: vi.fn(),
  listEventSectorMappings: vi.fn(),
  listEventRadarThemeMap: vi.fn(),
  runSectorScoring: vi.fn(),
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

const scoreResponse: SectorScoreListResponse = {
  row_count: 2,
  sector_scores: [
    {
      trade_date: "2026-06-19",
      sector_id: "theme_ai_compute",
      sector_name: "AI算力",
      event_heat: 0.82,
      market_confirm: 0.76,
      breadth_score: 0.7,
      flow_score: 0.68,
      persistence_score: 0.62,
      crowding_risk: 0.22,
      sector_heat_score: 0.74,
      cycle_stage: "accelerating",
      created_at: "2026-06-19T08:45:00",
    },
    {
      trade_date: "2026-06-19",
      sector_id: "theme_semiconductor",
      sector_name: "半导体",
      event_heat: 0.62,
      market_confirm: 0.58,
      breadth_score: 0.54,
      flow_score: 0.51,
      persistence_score: 0.48,
      crowding_risk: 0.18,
      sector_heat_score: 0.59,
      cycle_stage: "confirmed",
      created_at: "2026-06-19T08:45:00",
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

const themeMapResponse: EventRadarThemeMapResponse = {
  row_count: 1,
  theme_map: [
    {
      theme: "AI算力",
      sub_theme: "光模块",
      keyword: "AI 算力 光模块 数据中心",
      sector_id: "theme_ai_compute",
      sector_name: "AI算力",
      ticker: "300308.SZ",
      ticker_name: "中际旭创",
      relevance: 0.92,
      evidence: "光模块是 AI 算力基础设施上游核心环节",
      source: "manual",
      updated_at: "2026-06-19T08:00:00",
    },
  ],
};

const runResponse: SectorScoreRunResponse = {
  status: "ok",
  trade_date: "2026-06-19",
  scored_sectors: 2,
  rows_written: 2,
  top_sectors: scoreResponse.sector_scores,
};

function mockOverview() {
  apiMock.listSectorScores.mockResolvedValue(scoreResponse);
  apiMock.listEventSectorMappings.mockResolvedValue(sectorMappingsResponse);
  apiMock.listEventRadarThemeMap.mockResolvedValue(themeMapResponse);
}

async function waitForReady() {
  await waitFor(() => expect(screen.getByRole("button", { name: "生成板块评分" })).not.toBeDisabled());
}

describe("SectorRadar page", () => {
  beforeEach(() => {
    Object.values(apiMock).forEach((mock) => mock.mockReset());
    mockOverview();
  });

  it("renders the Chinese sector radar workbench and loaded scores", async () => {
    render(<SectorRadar />);

    expect(screen.getByText("板块雷达")).toBeInTheDocument();
    expect(screen.getByText("研究/模拟，不展示实时行情")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成板块评分" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新评分" })).toBeInTheDocument();

    expect((await screen.findAllByText("AI算力")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("半导体").length).toBeGreaterThan(0);
    expect(screen.getAllByText("加速").length).toBeGreaterThan(0);
    expect(screen.getByText("中际旭创")).toBeInTheDocument();
  });

  it("runs sector scoring through the local API", async () => {
    apiMock.runSectorScoring.mockResolvedValueOnce(runResponse);
    render(<SectorRadar />);
    await waitForReady();

    fireEvent.click(screen.getByRole("button", { name: "生成板块评分" }));

    await waitFor(() => expect(apiMock.runSectorScoring).toHaveBeenCalledTimes(1));
    expect(apiMock.runSectorScoring).toHaveBeenCalledWith(expect.objectContaining({
      limit: 10,
      min_relevance: 0.45,
    }));
    expect(await screen.findByText("已在 2026-06-19 写入 2 条板块评分。")).toBeInTheDocument();
  });

  it("refreshes sector scores with the current filters", async () => {
    render(<SectorRadar />);
    await waitForReady();

    fireEvent.change(screen.getByLabelText("最低热度"), { target: { value: "0.5" } });
    await waitForReady();
    fireEvent.click(screen.getByRole("button", { name: "刷新评分" }));

    await waitFor(() => expect(apiMock.listSectorScores).toHaveBeenCalledWith(expect.objectContaining({
      limit: 10,
      min_score: 0.5,
    })));
  });

  it("shows Chinese validation and API errors", async () => {
    render(<SectorRadar />);
    await waitForReady();

    fireEvent.change(screen.getByLabelText("评分上限"), { target: { value: "99" } });
    fireEvent.click(screen.getByRole("button", { name: "生成板块评分" }));
    expect(await screen.findByText("评分上限必须是 1 到 50 之间的整数。")).toBeInTheDocument();
    expect(apiMock.runSectorScoring).not.toHaveBeenCalled();

    apiMock.runSectorScoring.mockRejectedValueOnce(new Error("没有可评分的板块映射，请先运行事件映射。"));
    fireEvent.change(screen.getByLabelText("评分上限"), { target: { value: "10" } });
    await waitForReady();
    fireEvent.click(screen.getByRole("button", { name: "生成板块评分" }));
    expect(await screen.findByText("没有可评分的板块映射，请先运行事件映射。")).toBeInTheDocument();
  });
});
