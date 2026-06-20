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
    const idea = {
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
    };
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
          ideas: [idea],
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

  it("saves a strategy idea card into the strategy lab", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/save-spec")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              status: "ok",
              idea_id: "idea_ai",
              research_only: true,
              live_trading: false,
              strategy_spec: {
                strategy_id: "spec_ai",
                strategy_name: "AI算力 - S01 热点板块等权策略",
                market: "CN_A",
                strategy_type: "hot_sector_equal_weight",
                params: { source_strategy_idea_id: "idea_ai" },
                rebalance_freq: "weekly",
                holding_period: 5,
                max_position: 0.08,
                max_sector_exposure: 0.35,
                max_total_exposure: 0.65,
                stop_loss: 0.08,
                take_profit: 0.18,
                enabled: true,
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(
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
    });

    render(
      <MemoryRouter>
        <SectorStockAnalysis />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /生成策略卡/ }));
    await screen.findByText("AI算力 - S01 热点板块等权策略");
    fireEvent.click(screen.getByRole("button", { name: /保存到策略实验室/ }));

    await waitFor(() => expect(screen.getByText(/已保存为策略规格/)).toBeInTheDocument());
    expect(screen.getByText("状态：已进入策略实验室")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/strategy-ideas/idea_ai/save-spec",
      expect.objectContaining({ method: "POST" }),
    );

    fetchMock.mockRestore();
  });
});
