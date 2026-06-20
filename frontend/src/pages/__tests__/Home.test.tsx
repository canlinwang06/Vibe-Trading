import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { Home } from "../Home";

const apiMock = vi.hoisted(() => ({
  getDailyIntelligence: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
}));

const dailyIntelligence = {
  status: "ok",
  as_of_date: "2026-06-21",
  data_mode: "local",
  headline: "AI算力热度扩散，先生成候选策略再送聚宽验证。",
  market_temperature: { score: 76, label: "偏热", heat: 0.78, event_relevance: 0.74 },
  market_metrics: [
    { label: "涨停数量", value: "42", delta: "本地", tone: "success" },
    { label: "成交额", value: "1.2万亿", delta: "放大", tone: "info" },
  ],
  sector_heat: [
    { sector_id: "theme_ai_compute", sector_name: "AI算力", event_heat: 0.88, market_confirm: 0.72, breadth_score: 0.64, flow_score: 0.8, persistence_score: 0.76, crowding_risk: 0.58, sector_heat_score: 0.88, cycle_stage: "rising" },
  ],
  event_timeline: [
    { event_id: "evt_ai", theme: "AI算力", summary: "国产算力招标扩容。", time: "09:45", relevance: 0.88, certainty: 0.72, source_name: "财经媒体", source_type: "finance_news", source_url: null, verification_status: "已核验" },
  ],
  source_freshness: [
    { source_type: "finance_news", source_name: "财经媒体", enabled_count: 2, source_count: 2, fetched_count: 1, credibility: 0.8, status: "已采集" },
  ],
  codex_actions: ["让 Codex 基于今日热点生成候选策略卡"],
  warnings: [],
  research_only: true,
  live_trading: false,
};

describe("A-share daily intelligence home", () => {
  beforeEach(() => {
    apiMock.getDailyIntelligence.mockResolvedValue(dailyIntelligence);
  });

  it("renders the simplified daily intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "每日市场情报" })).toBeInTheDocument();
    expect(await screen.findByText("AI算力热度扩散，先生成候选策略再送聚宽验证。")).toBeInTheDocument();
    expect(screen.getByText("热点板块强度")).toBeInTheDocument();
    expect(screen.getByText("今日关键事件")).toBeInTheDocument();
    expect(screen.getByText("Codex 建议动作")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /事件记录库/ })).toHaveAttribute("href", "/event-records");
    expect(screen.getByRole("link", { name: /板块及股票分析/ })).toHaveAttribute("href", "/sector-stock-analysis");
    expect(apiMock.getDailyIntelligence).toHaveBeenCalledTimes(1);
  });

  it("does not render legacy multi-market examples", () => {
    const { container } = render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    expect(container.textContent).not.toMatch(/crypto|AAPL|BTC|options|美股|港股|加密货币|期权/i);
    expect(container.textContent).not.toMatch(/等待 PR|后续模块接入/);
    expect(container.textContent).not.toMatch(/事件雷达|板块雷达|事件反应|候选股票池/);
  });
});
