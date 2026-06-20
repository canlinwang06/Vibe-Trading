import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RiskPortfolio } from "../RiskPortfolio";
import type {
  PortfolioAllocationListResponse,
  PortfolioAllocationResponse,
  PortfolioTradePlanResponse,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  allocateRiskPortfolio: vi.fn(),
  listRiskPortfolioAllocations: vi.fn(),
  getRiskTradePlan: vi.fn(),
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

const allocation = {
  as_of_date: "2026-06-23",
  portfolio_id: "cn_a_main",
  strategy_id: "spec_hot_sector_balanced",
  strategy_name: "S01 热点板块等权策略 - 均衡参数",
  strategy_type: "hot_sector_equal_weight",
  strategy_score: 82.5,
  risk_score: 28.1,
  volatility: 0.08,
  correlation_penalty: 0.12,
  allocated_weight: 0.22,
  reason: "优先观察: strategy_score=82.50, allocated_weight=22.00%。",
  created_at: "2026-06-23T12:00:00",
};

const allocateResponse: PortfolioAllocationResponse = {
  status: "draft",
  portfolio_id: "cn_a_main",
  as_of_date: "2026-06-23",
  market_regime: "normal",
  model_total_exposure: 0.55,
  allocated_exposure: 0.42,
  cash_weight: 0.58,
  allocation_count: 1,
  strategy_allocations: [allocation],
  constraints: {
    max_strategy_weight: 0.3,
  },
  risk_rules: [
    { threshold: -0.03, action: "降低新开仓", triggered: false },
    { threshold: -0.10, action: "停止交易，进入复盘模式", triggered: false },
  ],
  requires_human_confirmation: true,
  research_only: true,
  live_trading: false,
};

const allocationList: PortfolioAllocationListResponse = {
  allocation_count: 1,
  strategy_allocations: [allocation],
};

const tradePlan: PortfolioTradePlanResponse = {
  status: "draft",
  portfolio_id: "cn_a_main",
  as_of_date: "2026-06-23",
  target_total_exposure: 0.2,
  strategy_allocated_exposure: 0.42,
  cash_weight: 0.8,
  strategy_allocations: [allocation],
  target_positions: [
    {
      ticker: "300308.SZ",
      ticker_name: "中际旭创",
      target_weight: 0.1,
      current_weight: 0,
      action: "draft_target",
      strategy_sources: ["spec_hot_sector_balanced"],
      theme: "AI算力",
      sector_id: "theme_ai_compute",
      sector_name: "AI算力",
      reason: "由策略权重和候选股票池合成的草案目标权重。",
      risk: "研究草案，未审批，不能作为实盘指令。",
    },
  ],
  risk_limits: {
    max_single_stock_weight: 0.12,
    max_sector_weight: 0.4,
  },
  requires_human_confirmation: true,
  approval_status: "draft_not_generated",
  research_only: true,
  live_trading: false,
};

describe("RiskPortfolio page", () => {
  beforeEach(() => {
    apiMock.allocateRiskPortfolio.mockReset();
    apiMock.listRiskPortfolioAllocations.mockReset();
    apiMock.getRiskTradePlan.mockReset();
  });

  it("renders the Chinese risk portfolio workbench", () => {
    render(<RiskPortfolio />);

    expect(screen.getByText("风控组合")).toBeInTheDocument();
    expect(screen.getByText("不审批 / 不下单")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行组合风控" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新策略分配" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成交易计划草案" })).toBeInTheDocument();
  });

  it("allocates strategy capital through the API", async () => {
    apiMock.allocateRiskPortfolio.mockResolvedValueOnce(allocateResponse);
    render(<RiskPortfolio />);

    fireEvent.click(screen.getByRole("button", { name: "运行组合风控" }));

    await waitFor(() => expect(apiMock.allocateRiskPortfolio).toHaveBeenCalledTimes(1));
    expect(apiMock.allocateRiskPortfolio).toHaveBeenCalledWith(expect.objectContaining({
      portfolio_id: "cn_a_main",
      top_n: 5,
      market_regime: "normal",
      max_strategy_weight: 0.3,
    }));
    expect(await screen.findByText("已生成 1 条策略分配。")).toBeInTheDocument();
    expect(screen.getByText("S01 热点板块等权策略 - 均衡参数")).toBeInTheDocument();
    expect(screen.getByText("降低新开仓")).toBeInTheDocument();
  });

  it("refreshes persisted allocations", async () => {
    apiMock.listRiskPortfolioAllocations.mockResolvedValueOnce(allocationList);
    render(<RiskPortfolio />);

    fireEvent.click(screen.getByRole("button", { name: "刷新策略分配" }));

    await waitFor(() => expect(apiMock.listRiskPortfolioAllocations).toHaveBeenCalledTimes(1));
    expect(apiMock.listRiskPortfolioAllocations).toHaveBeenCalledWith(expect.objectContaining({
      portfolio_id: "cn_a_main",
      limit: 100,
    }));
    expect(await screen.findByText("已加载 1 条策略分配。")).toBeInTheDocument();
    expect(screen.getByText("spec_hot_sector_balanced")).toBeInTheDocument();
  });

  it("loads a draft trade plan without approving it", async () => {
    apiMock.getRiskTradePlan.mockResolvedValueOnce(tradePlan);
    render(<RiskPortfolio />);

    fireEvent.click(screen.getByRole("button", { name: "生成交易计划草案" }));

    await waitFor(() => expect(apiMock.getRiskTradePlan).toHaveBeenCalledTimes(1));
    expect(apiMock.getRiskTradePlan).toHaveBeenCalledWith(expect.objectContaining({
      portfolio_id: "cn_a_main",
      max_single_stock_weight: 0.12,
      max_sector_weight: 0.4,
    }));
    expect(await screen.findByText("已生成 1 条草案目标持仓。")).toBeInTheDocument();
    expect(screen.getByText("中际旭创")).toBeInTheDocument();
    expect(screen.getByText(/尚未生成信号/)).toBeInTheDocument();
    expect(apiMock).not.toHaveProperty("approvePlan");
  });

  it("shows Chinese validation errors without calling the backend", async () => {
    render(<RiskPortfolio />);

    fireEvent.change(screen.getByLabelText("策略数量"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "运行组合风控" }));

    expect(await screen.findByText("策略数量必须是 3 到 5 之间的整数。")).toBeInTheDocument();
    expect(apiMock.allocateRiskPortfolio).not.toHaveBeenCalled();
  });

  it("shows Chinese API errors", async () => {
    apiMock.getRiskTradePlan.mockRejectedValueOnce(new Error("没有策略分配结果，请先运行组合风控分配。"));
    render(<RiskPortfolio />);

    fireEvent.click(screen.getByRole("button", { name: "生成交易计划草案" }));

    expect(await screen.findByText("没有策略分配结果，请先运行组合风控分配。")).toBeInTheDocument();
  });
});
