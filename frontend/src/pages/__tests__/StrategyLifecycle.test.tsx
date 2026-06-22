import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { StrategyLifecycle } from "../StrategyLifecycle";

const apiMock = vi.hoisted(() => ({
  getStrategyLifecycleOverview: vi.fn(),
  refreshStrategyLifecycle: vi.fn(),
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

const overview = {
  status: "ok",
  data_mode: "local",
  funnel: [
    { state: "idea", label: "想法", count: 1 },
    { state: "candidate", label: "候选", count: 2 },
    { state: "qualified", label: "合格", count: 1 },
    { state: "paper_trading", label: "模拟盘", count: 1 },
  ],
  health_distribution: [
    { label: "稳定观察", count: 1, min_score: 70, max_score: 100 },
    { label: "继续小样本", count: 2, min_score: 55, max_score: 69.999 },
  ],
  strategies: [
    {
      strategy_id: "spec_ai",
      idea_id: "idea_ai",
      strategy_name: "AI算力热点动量",
      theme: "AI算力",
      lifecycle_state: "paper_trading",
      health_score: 78,
      recommendation: "继续观察",
      reason: "模拟盘观察第 3 周，仍需控制仓位。",
      first_seen_date: "2026-06-02",
      last_review_date: "2026-06-20",
      paper_days: 15,
      signal_count: 6,
      backtest_count: 3,
      best_annual_return: 0.186,
      worst_max_drawdown: -0.098,
      avg_sharpe: 1.42,
      win_rate: 0.54,
      evidence: {},
      research_only: true,
      live_trading: false,
    },
  ],
  events: [
    {
      event_id: "lifeevt_ai",
      strategy_id: "spec_ai",
      event_time: "2026-06-20T15:00:00",
      from_state: "qualified",
      to_state: "paper_trading",
      reason: "聚宽回测结果入库后进入模拟观察。",
      evidence: {},
      created_by: "codex",
      research_only: true,
      live_trading: false,
    },
  ],
  recommendations: [
    {
      strategy_id: "spec_ai",
      strategy_name: "AI算力热点动量",
      recommendation: "继续观察",
      reason: "模拟盘观察第 3 周，仍需控制仓位。",
      health_score: 78,
    },
  ],
  research_only: true,
  live_trading: false,
};

describe("StrategyLifecycle page", () => {
  beforeEach(() => {
    apiMock.getStrategyLifecycleOverview.mockResolvedValue(overview);
    apiMock.refreshStrategyLifecycle.mockResolvedValue({
      status: "ok",
      strategy_count: 1,
      strategies: overview.strategies,
      research_only: true,
      live_trading: false,
    });
  });

  it("renders lifecycle funnel, health distribution, recommendations, and event history", async () => {
    render(<StrategyLifecycle />);

    expect(screen.getByRole("heading", { name: "策略生命周期" })).toBeInTheDocument();
    expect((await screen.findAllByText("AI算力热点动量")).length).toBeGreaterThan(0);
    expect(screen.getByText("策略漏斗")).toBeInTheDocument();
    expect(screen.getByText("健康度分布")).toBeInTheDocument();
    expect(screen.getByText("重点策略观察")).toBeInTheDocument();
    expect(screen.getByText("下一步建议")).toBeInTheDocument();
    expect(screen.getByText("状态变更记录")).toBeInTheDocument();
    expect(screen.getAllByText("继续观察").length).toBeGreaterThan(0);
  });

  it("refreshes lifecycle rows through the local API", async () => {
    render(<StrategyLifecycle />);
    await screen.findAllByText("AI算力热点动量");

    fireEvent.click(screen.getByRole("button", { name: "刷新生命周期" }));

    await waitFor(() => expect(apiMock.refreshStrategyLifecycle).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("已刷新 1 条策略生命周期。")).toBeInTheDocument();
  });
});
