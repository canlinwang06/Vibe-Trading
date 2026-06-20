import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrategyLab } from "../StrategyLab";
import type {
  BacktestBatchResponse,
  BacktestRankingResponse,
  BacktestRunListResponse,
  StrategySpecListResponse,
  StrategySpecSeedResponse,
  StrategyTemplateListResponse,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  listStrategyTemplates: vi.fn(),
  seedStrategySpecs: vi.fn(),
  listStrategySpecs: vi.fn(),
  runStrategyBacktestBatch: vi.fn(),
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

const templateResponse: StrategyTemplateListResponse = {
  template_count: 1,
  templates: [
    {
      strategy_type: "hot_sector_equal_weight",
      template_name: "S01 热点板块等权策略",
      description: "选择 sector_heat_score 排名前 N 的板块。",
      signal_rules: ["sector_heat_score 排名前 N"],
      risk_notes: ["避免单板块过度集中"],
      default_rebalance_freq: "weekly",
      default_holding_period: 5,
      default_max_position: 0.08,
      default_max_sector_exposure: 0.35,
      default_max_total_exposure: 0.65,
      default_stop_loss: 0.08,
      default_take_profit: 0.18,
    },
  ],
};

const specResponse: StrategySpecListResponse = {
  spec_count: 1,
  strategy_specs: [
    {
      strategy_id: "spec_hot_sector_balanced",
      strategy_name: "S01 热点板块等权策略 - 均衡参数",
      market: "CN_A",
      strategy_type: "hot_sector_equal_weight",
      params: { execution_mode: "research_only" },
      rebalance_freq: "weekly",
      holding_period: 5,
      max_position: 0.08,
      max_sector_exposure: 0.35,
      max_total_exposure: 0.65,
      stop_loss: 0.08,
      take_profit: 0.18,
      enabled: true,
    },
  ],
};

const seedResponse: StrategySpecSeedResponse = {
  status: "ok",
  template_count: 8,
  variant_count: 3,
  strategy_specs_written: 24,
  strategy_specs_skipped: 0,
  total_expected_specs: 24,
};

const batchResponse: BacktestBatchResponse = {
  status: "ok",
  as_of_date: "2026-06-19",
  start_date: "2025-06-19",
  end_date: "2026-06-19",
  runs_written: 1,
  top_runs: [
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

const runsResponse: BacktestRunListResponse = {
  run_count: 1,
  backtest_runs: batchResponse.top_runs,
};

const rankingsResponse: BacktestRankingResponse = {
  ranking_count: 1,
  scoring_model: { version: "test" },
  research_only: true,
  live_trading: false,
  rankings: [
    {
      ...batchResponse.top_runs[0],
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

describe("StrategyLab page", () => {
  beforeEach(() => {
    apiMock.listStrategyTemplates.mockReset();
    apiMock.seedStrategySpecs.mockReset();
    apiMock.listStrategySpecs.mockReset();
    apiMock.runStrategyBacktestBatch.mockReset();
    apiMock.listStrategyBacktestRuns.mockReset();
    apiMock.listStrategyBacktestRankings.mockReset();
  });

  it("renders the Chinese strategy-lab workbench", () => {
    render(<StrategyLab />);

    expect(screen.getByText("策略实验室")).toBeInTheDocument();
    expect(screen.getByText("研究回测，不下单")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加载模板" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成策略规格" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行批量回测" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新排名" })).toBeInTheDocument();
  });

  it("loads strategy templates through the API", async () => {
    apiMock.listStrategyTemplates.mockResolvedValueOnce(templateResponse);
    render(<StrategyLab />);

    fireEvent.click(screen.getByRole("button", { name: "加载模板" }));

    await waitFor(() => expect(apiMock.listStrategyTemplates).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("S01 热点板块等权策略")).toBeInTheDocument();
    expect(screen.getByText("已加载 1 个策略模板。")).toBeInTheDocument();
  });

  it("seeds and refreshes strategy specs", async () => {
    apiMock.seedStrategySpecs.mockResolvedValueOnce(seedResponse);
    apiMock.listStrategySpecs.mockResolvedValueOnce(specResponse);
    render(<StrategyLab />);

    fireEvent.click(screen.getByRole("button", { name: "生成策略规格" }));

    await waitFor(() => expect(apiMock.seedStrategySpecs).toHaveBeenCalledWith({ replace: false }));
    expect(apiMock.listStrategySpecs).toHaveBeenCalledWith(expect.objectContaining({
      enabled: true,
      limit: 24,
    }));
    expect(await screen.findByText("已写入 24 条策略规格。")).toBeInTheDocument();
    expect(screen.getByText("S01 热点板块等权策略 - 均衡参数")).toBeInTheDocument();
  });

  it("runs batch backtests and renders the top runs", async () => {
    apiMock.runStrategyBacktestBatch.mockResolvedValueOnce(batchResponse);
    render(<StrategyLab />);

    fireEvent.click(screen.getByRole("button", { name: "运行批量回测" }));

    await waitFor(() => expect(apiMock.runStrategyBacktestBatch).toHaveBeenCalledTimes(1));
    expect(apiMock.runStrategyBacktestBatch).toHaveBeenCalledWith(expect.objectContaining({
      benchmark: "000300.SH",
      limit: 24,
    }));
    expect(await screen.findByText("已完成 1 条策略回测。")).toBeInTheDocument();
    expect(screen.getByText("bt_ai_1")).toBeInTheDocument();
  });

  it("refreshes backtest runs and rankings", async () => {
    apiMock.listStrategyBacktestRuns.mockResolvedValueOnce(runsResponse);
    apiMock.listStrategyBacktestRankings.mockResolvedValueOnce(rankingsResponse);
    render(<StrategyLab />);

    fireEvent.click(screen.getByRole("button", { name: "刷新回测" }));
    expect(await screen.findByText("已加载 1 条回测结果。")).toBeInTheDocument();
    expect(screen.getByText("bt_ai_1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "刷新排名" }));
    await waitFor(() => expect(apiMock.listStrategyBacktestRankings).toHaveBeenCalledWith(expect.objectContaining({
      status: "completed",
      limit: 20,
    })));
    expect(await screen.findByText("已生成 1 条策略排名。")).toBeInTheDocument();
    expect(screen.getByText("优先观察")).toBeInTheDocument();
  });

  it("shows Chinese validation errors without calling the backend", async () => {
    render(<StrategyLab />);

    fireEvent.change(screen.getByLabelText("排名上限"), { target: { value: "9999" } });
    fireEvent.click(screen.getByRole("button", { name: "刷新排名" }));

    expect(await screen.findByText("排名上限必须是 1 到 500 之间的整数。")).toBeInTheDocument();
    expect(apiMock.listStrategyBacktestRankings).not.toHaveBeenCalled();
  });

  it("shows Chinese API errors", async () => {
    apiMock.runStrategyBacktestBatch.mockRejectedValueOnce(new Error("没有可回测的候选股票，请先生成候选股票池。"));
    render(<StrategyLab />);

    fireEvent.click(screen.getByRole("button", { name: "运行批量回测" }));

    expect(await screen.findByText("没有可回测的候选股票，请先生成候选股票池。")).toBeInTheDocument();
  });
});
