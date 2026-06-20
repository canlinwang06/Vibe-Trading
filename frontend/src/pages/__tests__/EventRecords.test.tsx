import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { EventRecords } from "../EventRecords";

const apiMock = vi.hoisted(() => ({
  listEventRecords: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
}));

const eventRecordResponse = {
  status: "ok",
  record_count: 1,
  impact_windows: ["T+1", "T+5", "T+20", "T+60"],
  research_only: true,
  live_trading: false,
  records: [
    {
      event_id: "evt_ai",
      cluster_id: "cluster_ai",
      event_type: "industry",
      event_subtype: "AI算力",
      summary: "国产算力招标扩容进入市场关注区。",
      sentiment: "positive",
      intensity: 82,
      novelty: 70,
      certainty: 0.76,
      a_share_relevance_score: 0.88,
      knowable_time: "2026-06-21T09:50:00",
      source_name: "财经媒体",
      source_type: "finance_news",
      source_url: "https://example.com/ai",
      local_document_ref: "raw_documents:evt_ai",
      evidence: {},
      related_sectors: [],
      related_stocks: [],
      impact: {},
      impact_t1: { window: "T+1", status: "available", reaction_count: 3, sector_count: 2, stock_count: 3, avg_raw_return: 0.02, avg_abnormal_return: 0.012, worst_max_drawdown: -0.03 },
      impact_t5: { window: "T+5", status: "available", reaction_count: 3, sector_count: 2, stock_count: 3, avg_raw_return: 0.03, avg_abnormal_return: 0.018, worst_max_drawdown: -0.04 },
      impact_t20: { window: "T+20", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
      impact_t60: { window: "T+60", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
    },
  ],
};

describe("Event records page", () => {
  beforeEach(() => {
    apiMock.listEventRecords.mockResolvedValue(eventRecordResponse);
  });

  it("summarizes objective event records with evidence links and impact windows", async () => {
    render(
      <MemoryRouter>
        <EventRecords />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "事件记录库" })).toBeInTheDocument();
    expect(await screen.findByText(/AI算力 相关事件共 1 条/)).toBeInTheDocument();
    expect(screen.getByText("事件证据链")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /原文链接/ })).toHaveAttribute("href", "https://example.com/ai");
    expect(screen.getByText("事件影响沉淀")).toBeInTheDocument();
    expect(screen.getByText("1.2%")).toBeInTheDocument();
    expect(apiMock.listEventRecords).toHaveBeenCalledWith({ limit: 20, min_relevance: 0.4 });
  });
});
