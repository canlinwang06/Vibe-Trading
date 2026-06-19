import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TradePlan } from "../TradePlan";
import type { PortfolioTradePlanResponse } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
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

const tradePlan: PortfolioTradePlanResponse = {
  status: "draft",
  portfolio_id: "cn_a_main",
  as_of_date: "2026-06-23",
  target_total_exposure: 0.2,
  strategy_allocated_exposure: 0.42,
  cash_weight: 0.8,
  strategy_allocations: [
    {
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
    },
  ],
  target_positions: [
    {
      ticker: "300308.SZ",
      ticker_name: "中际旭创",
      target_weight: 0.1,
      current_weight: 0.02,
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

describe("TradePlan page", () => {
  beforeEach(() => {
    apiMock.getRiskTradePlan.mockReset();
  });

  it("renders the Chinese trade-plan review page", () => {
    render(<TradePlan />);

    expect(screen.getByText("交易计划")).toBeInTheDocument();
    expect(screen.getAllByText("草稿审阅 / 不审批不下单").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "刷新交易计划" })).toBeInTheDocument();
    expect(screen.getByText("目标持仓")).toBeInTheDocument();
    expect(screen.getByText("策略来源")).toBeInTheDocument();
  });

  it("loads a draft trade plan through the API", async () => {
    apiMock.getRiskTradePlan.mockResolvedValueOnce(tradePlan);
    render(<TradePlan />);

    fireEvent.click(screen.getByRole("button", { name: "刷新交易计划" }));

    await waitFor(() => expect(apiMock.getRiskTradePlan).toHaveBeenCalledTimes(1));
    expect(apiMock.getRiskTradePlan).toHaveBeenCalledWith(expect.objectContaining({
      portfolio_id: "cn_a_main",
      max_single_stock_weight: 0.12,
      max_sector_weight: 0.4,
    }));
    expect(await screen.findByText("已加载 1 条目标持仓。")).toBeInTheDocument();
    expect(screen.getByText("中际旭创")).toBeInTheDocument();
    expect(screen.getAllByText("10%").length).toBeGreaterThan(0);
    expect(screen.getByText("尚未生成执行信号")).toBeInTheDocument();
    expect(screen.getByText("研究草案，未审批，不能作为实盘指令。")).toBeInTheDocument();
  });

  it("shows Chinese validation errors without calling the backend", async () => {
    render(<TradePlan />);

    fireEvent.change(screen.getByLabelText("单票上限"), { target: { value: "0.9" } });
    fireEvent.click(screen.getByRole("button", { name: "刷新交易计划" }));

    expect(await screen.findByText("单票上限必须是 0.01 到 0.3 之间的小数。")).toBeInTheDocument();
    expect(apiMock.getRiskTradePlan).not.toHaveBeenCalled();
  });

  it("shows Chinese API errors", async () => {
    apiMock.getRiskTradePlan.mockRejectedValueOnce(new Error("没有策略分配结果，请先运行组合风控分配。"));
    render(<TradePlan />);

    fireEvent.click(screen.getByRole("button", { name: "刷新交易计划" }));

    expect(await screen.findByText("没有策略分配结果，请先运行组合风控分配。")).toBeInTheDocument();
  });

  it("does not expose approval, signal generation, or live trading actions", () => {
    render(<TradePlan />);

    expect(screen.queryByRole("button", { name: /审批|生成信号|下单|实盘/ })).not.toBeInTheDocument();
    expect(apiMock).not.toHaveProperty("approvePlan");
    expect(apiMock).not.toHaveProperty("generateDraftSignals");
    expect(apiMock).not.toHaveProperty("placeOrder");
  });
});
