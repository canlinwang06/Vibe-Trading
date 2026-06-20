import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BacktestResults } from "../BacktestResults";
import type {
  BacktestRankingResponse,
  BacktestRunListResponse,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  listStrategyBacktestRuns: vi.fn(),
  listStrategyBacktestRankings: vi.fn(),
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

const runsResponse: BacktestRunListResponse = {
  run_count: 1,
  backtest_runs: [
    {
      run_id: "bt_ai_1",
      strategy_id: "spec_hot_sector_balanced",
      market: "CN_A",
      start_date: "2025-06-19",
      end_date: "2026-06-19",
      universe_id: "candidate_pool_ai",
      benchmark: "000300.SH",
      total_return: 0.18,
      annual_return: 0.17,
      max_drawdown: -0.08,
      sharpe: 1.25,
      sortino: 1.5,
      calmar: 2.1,
      win_rate: 0.58,
      profit_loss_ratio: 1.4,
      turnover: 1.2,
      trade_count: 24,
      avg_holding_days: 5,
      excess_return: 0.09,
      information_ratio: 0.8,
      status: "completed",
    },
  ],
};

const rankingsResponse: BacktestRankingResponse = {
  ranking_count: 1,
  scoring_model: { version: "test" },
  research_only: true,
  live_trading: false,
  rankings: [
    {
      ...runsResponse.backtest_runs[0],
      strategy_name: "S01 热点板块等权策略 - 均衡参数",
      strategy_type: "hot_sector_equal_weight",
      params: {},
      rebalance_freq: "weekly",
      holding_period: 5,
      sample_days: 366,
      strategy_score: 82.5,
      risk_score: 28.1,
      score_components: {},
      recommendation: "优先观察",
      reason: "优先观察: 收益 18.00%, 最大回撤 -8.00%。",
      rank: 1,
      research_only: true,
      live_trading: false,
    },
  ],
};

describe("BacktestResults page", () => {
  beforeEach(() => {
    apiMock.listStrategyBacktestRuns.mockReset();
    apiMock.listStrategyBacktestRankings.mockReset();
  });

  it("renders the Chinese backtest result workbench", () => {
    render(<BacktestResults />);

    expect(screen.getAllByText("回测结果").length).toBeGreaterThan(0);
    expect(screen.getByText("只读验收页")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新回测结果" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新策略排名" })).toBeInTheDocument();
  });

  it("loads backtest runs through the API", async () => {
    apiMock.listStrategyBacktestRuns.mockResolvedValueOnce(runsResponse);
    render(<BacktestResults />);

    fireEvent.click(screen.getByRole("button", { name: "刷新回测结果" }));

    await waitFor(() => expect(apiMock.listStrategyBacktestRuns).toHaveBeenCalledTimes(1));
    expect(apiMock.listStrategyBacktestRuns).toHaveBeenCalledWith(expect.objectContaining({
      status: "completed",
      limit: 50,
    }));
    expect(await screen.findByText("已加载 1 条回测结果。")).toBeInTheDocument();
    expect(screen.getByText("bt_ai_1")).toBeInTheDocument();
    expect(screen.getByText("18%")).toBeInTheDocument();
  });

  it("loads strategy rankings through the API", async () => {
    apiMock.listStrategyBacktestRankings.mockResolvedValueOnce(rankingsResponse);
    render(<BacktestResults />);

    fireEvent.click(screen.getByRole("button", { name: "刷新策略排名" }));

    await waitFor(() => expect(apiMock.listStrategyBacktestRankings).toHaveBeenCalledTimes(1));
    expect(apiMock.listStrategyBacktestRankings).toHaveBeenCalledWith(expect.objectContaining({
      status: "completed",
      limit: 20,
    }));
    expect(await screen.findByText("已加载 1 条策略排名。")).toBeInTheDocument();
    expect(screen.getByText("S01 热点板块等权策略 - 均衡参数")).toBeInTheDocument();
    expect(screen.getAllByText("优先观察").length).toBeGreaterThan(0);
  });

  it("shows Chinese validation errors without calling the backend", async () => {
    render(<BacktestResults />);

    fireEvent.change(screen.getByLabelText("回测上限"), { target: { value: "9999" } });
    fireEvent.click(screen.getByRole("button", { name: "刷新回测结果" }));

    expect(await screen.findByText("回测上限必须是 1 到 500 之间的整数。")).toBeInTheDocument();
    expect(apiMock.listStrategyBacktestRuns).not.toHaveBeenCalled();
  });

  it("shows Chinese API errors", async () => {
    apiMock.listStrategyBacktestRankings.mockRejectedValueOnce(new Error("没有可排名的回测结果，请先运行批量回测。"));
    render(<BacktestResults />);

    fireEvent.click(screen.getByRole("button", { name: "刷新策略排名" }));

    expect(await screen.findByText("没有可排名的回测结果，请先运行批量回测。")).toBeInTheDocument();
  });
});
