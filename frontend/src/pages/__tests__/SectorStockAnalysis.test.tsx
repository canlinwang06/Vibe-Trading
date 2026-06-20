import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { SectorStockAnalysis } from "../SectorStockAnalysis";

describe("Sector and stock analysis page", () => {
  it("explains the analysis layer and keeps legacy drill-down links", () => {
    render(
      <MemoryRouter>
        <SectorStockAnalysis />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "板块及股票分析" })).toBeInTheDocument();
    expect(screen.getByText("基于事件记录库沉淀的数据，判断当前哪些板块正在升温。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /板块雷达/ })).toHaveAttribute("href", "/sector-radar");
    expect(screen.getByRole("link", { name: /候选股票池/ })).toHaveAttribute("href", "/candidate-pool");
    expect(screen.getByRole("link", { name: /策略实验室/ })).toHaveAttribute("href", "/strategy-lab");
  });

  it("generates and renders strategy idea cards", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          as_of_date: "2026-06-22",
          theme: "AI算力",
          risk_preference: "balanced",
          idea_count: 1,
          research_only: true,
          live_trading: false,
          ideas: [
            {
              idea_id: "idea_ai",
              as_of_date: "2026-06-22",
              theme: "AI算力",
              strategy_type: "hot_sector_equal_weight",
              strategy_name: "AI算力 - S01 热点板块等权策略",
              strategy_family: "板块轮动",
              idea_category: "热点板块等权",
              risk_preference: "balanced",
              holding_period: 5,
              rebalance_freq: "weekly",
              idea_score: 82.5,
              status: "generated",
              thesis: "AI算力 当前具备热点板块等权回测条件。",
              candidate_tickers: [{ ticker: "300308.SZ", ticker_name: "中际旭创", stock_score: 0.91 }],
              sector_ids: ["theme_ai_compute"],
              source_event_ids: ["evt_ai"],
              entry_rules: ["主题限定为 AI算力", "sector_heat_score 排名前 N"],
              exit_rules: ["持有 5 个交易日后重新评估"],
              risk_controls: ["单股最大仓位 8%", "总暴露不超过 65%"],
              params: { execution_mode: "research_only" },
              evidence: {},
              research_only: true,
              live_trading: false,
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(
      <MemoryRouter>
        <SectorStockAnalysis />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /生成策略卡/ }));

    await waitFor(() => expect(screen.getByText("AI算力 - S01 热点板块等权策略")).toBeInTheDocument());
    expect(screen.getByText("已生成 1 张策略卡。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/strategy-ideas/generate",
      expect.objectContaining({ method: "POST" }),
    );

    fetchMock.mockRestore();
  });
});
