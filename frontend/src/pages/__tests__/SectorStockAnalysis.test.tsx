import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { SectorStockAnalysis } from "../SectorStockAnalysis";

const apiMock = vi.hoisted(() => ({
  getSectorStockDashboard: vi.fn(),
  generateStrategyIdeas: vi.fn(),
  listStrategyIdeas: vi.fn(),
  saveStrategyIdeaSpec: vi.fn(),
  joinQuantCreateTask: vi.fn(),
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

const candidate = {
  ticker: "300308.SZ",
  ticker_name: "中际旭创",
  market: "CN_A",
  source: "local",
  sector_id: "theme_optical_module",
  sector_name: "光模块",
  theme: "AI算力",
  event_heat_score: 0.88,
  sector_heat_score: 0.81,
  stock_score: 0.91,
  risk_flag: "normal",
  included: true,
  reason: "光模块龙头，AI算力链高相关。",
};

const idea = {
  idea_id: "idea_ai",
  as_of_date: "2026-06-21",
  theme: "AI算力",
  strategy_type: "hot_sector_equal_weight",
  strategy_name: "AI算力热点板块等权策略",
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

const dashboard = {
  status: "ok",
  as_of_date: "2026-06-21",
  theme: "AI算力",
  data_mode: "local",
  sector_score: {
    theme: "AI算力",
    score: 82,
    summary: "AI算力热度较高，适合先生成候选策略卡。",
    badges: ["事件驱动强", "板块扩散中"],
  },
  sector_rankings: [
    { sector_id: "theme_ai_compute", sector_name: "AI算力", event_heat: 0.88, market_confirm: 0.72, breadth_score: 0.64, flow_score: 0.8, persistence_score: 0.76, crowding_risk: 0.58, sector_heat_score: 0.88, cycle_stage: "rising" },
  ],
  candidate_matrix: [
    { ticker: "300308.SZ", ticker_name: "中际旭创", sector_name: "光模块", leader_score: 0.91, order_score: 0.88, catch_up_score: 0.09, crowding_flag: false },
  ],
  candidate_pool: [candidate],
  strategy_ideas: [idea],
  codex_actions: ["让 Codex 生成多类型候选策略"],
  research_only: true,
  live_trading: false,
};

describe("Sector and stock analysis page", () => {
  beforeEach(() => {
    apiMock.getSectorStockDashboard.mockResolvedValue(dashboard);
    apiMock.generateStrategyIdeas.mockResolvedValue({
      status: "ok",
      as_of_date: "2026-06-21",
      theme: "AI算力",
      risk_preference: "balanced",
      idea_count: 1,
      ideas: [idea],
      research_only: true,
      live_trading: false,
    });
    apiMock.listStrategyIdeas.mockResolvedValue({
      status: "ok",
      idea_count: 1,
      ideas: [idea],
      research_only: true,
      live_trading: false,
    });
    apiMock.saveStrategyIdeaSpec.mockResolvedValue({
      status: "ok",
      idea_id: "idea_ai",
      research_only: true,
      live_trading: false,
      strategy_spec: {
        strategy_id: "spec_ai",
        strategy_name: "AI算力热点板块等权策略",
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
    });
    apiMock.joinQuantCreateTask.mockResolvedValue({
      status: "ok",
      research_only: true,
      live_trading: false,
      task: {
        task_id: "jqtask_ai",
        source_strategy_id: null,
        source_idea_id: "idea_ai",
        portfolio_id: "cn_a_main",
        signal_date: "2026-06-21",
        task_type: "backtest",
        status: "waiting_confirm",
        task_package: {},
        result_summary: {},
        evidence: [],
        fallback_instruction: "手动复制 strategy.py 到聚宽。",
        created_by: "codex",
        research_only: true,
        live_trading: false,
      },
    });
  });

  it("renders sector heat, candidate pool, strategy ideas, and lifecycle links", async () => {
    render(
      <MemoryRouter>
        <SectorStockAnalysis />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "板块及股票分析" })).toBeInTheDocument();
    expect(await screen.findByText("AI算力热度较高，适合先生成候选策略卡。")).toBeInTheDocument();
    expect(screen.getByText("热点板块排行")).toBeInTheDocument();
    expect(screen.getByText("板块到股票候选矩阵")).toBeInTheDocument();
    expect(screen.getByText("候选股票池")).toBeInTheDocument();
    expect(screen.getAllByText("中际旭创").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /聚宽任务中心/ })).toHaveAttribute("href", "/joinquant-export");
    expect(screen.getByRole("link", { name: /策略生命周期/ })).toHaveAttribute("href", "/strategy-lifecycle");
  });

  it("generates, saves, and creates JoinQuant tasks from strategy cards", async () => {
    render(
      <MemoryRouter>
        <SectorStockAnalysis />
      </MemoryRouter>,
    );

    await screen.findByText("AI算力热度较高，适合先生成候选策略卡。");
    fireEvent.click(screen.getByRole("button", { name: /生成策略卡/ }));
    await waitFor(() => expect(apiMock.generateStrategyIdeas).toHaveBeenCalledTimes(1));
    expect(screen.getByText("已生成 1 张策略卡。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /保存到策略实验室/ }));
    await waitFor(() => expect(apiMock.saveStrategyIdeaSpec).toHaveBeenCalledWith("idea_ai", { enabled: true }));
    expect(screen.getByText(/已保存为策略规格/)).toBeInTheDocument();
    expect(screen.getByText("状态：已进入策略实验室")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /创建聚宽任务/ }));
    await waitFor(() => expect(apiMock.joinQuantCreateTask).toHaveBeenCalledTimes(1));
    expect(apiMock.joinQuantCreateTask).toHaveBeenCalledWith(expect.objectContaining({
      source_idea_id: "idea_ai",
      portfolio_id: "cn_a_main",
      task_type: "backtest",
    }));
    expect(screen.getByText(/已创建聚宽任务：jqtask_ai/)).toBeInTheDocument();
  });
});
