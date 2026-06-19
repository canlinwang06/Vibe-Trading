import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DailyWorkflow } from "../DailyWorkflow";
import type { DailyWorkflowRunResponse } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  dailyWorkflowRun: vi.fn(),
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

const dryRunResponse: DailyWorkflowRunResponse = {
  status: "dry_run",
  workflow_date: "2026-06-22",
  portfolio_id: "cn_a_main",
  requested_steps: ["collect_documents", "extract_events"],
  completed_step_count: 0,
  skipped_step_count: 0,
  blocked_step: null,
  steps: [
    {
      name: "collect_documents",
      status: "planned",
      message: "将确认默认信息源，并在有手工文档时导入本地库。",
      metrics: {},
    },
    {
      name: "extract_events",
      status: "planned",
      message: "将从本地原始文档抽取结构化事件。",
      metrics: {},
    },
  ],
  research_only: true,
  live_trading: false,
};

const okResponse: DailyWorkflowRunResponse = {
  status: "ok",
  workflow_date: "2026-06-22",
  portfolio_id: "cn_a_main",
  requested_steps: [
    "collect_documents",
    "extract_events",
    "map_events",
    "score_sectors",
    "build_candidates",
    "seed_strategy_specs",
    "run_backtests",
    "rank_backtests",
    "allocate_portfolio",
    "generate_draft_signals",
  ],
  completed_step_count: 10,
  skipped_step_count: 0,
  blocked_step: null,
  steps: [
    {
      name: "collect_documents",
      status: "ok",
      message: "已导入 1 条原始文档，重复 0 条。",
      metrics: { inserted: 1, duplicates: 0 },
    },
    {
      name: "generate_draft_signals",
      status: "ok",
      message: "已生成 3 条执行信号草案，仍需人工确认。",
      metrics: { signals_written: 3 },
    },
  ],
  research_only: true,
  live_trading: false,
};

const blockedResponse: DailyWorkflowRunResponse = {
  ...okResponse,
  status: "blocked",
  completed_step_count: 4,
  blocked_step: "run_backtests",
  steps: [
    {
      name: "run_backtests",
      status: "blocked",
      message: "候选股票缺少回测行情，请先导入 market_daily。",
      metrics: {},
    },
  ],
};

describe("DailyWorkflow page", () => {
  beforeEach(() => {
    apiMock.dailyWorkflowRun.mockReset();
  });

  it("renders the Chinese daily workflow console with the AI industry-chain task", () => {
    render(<DailyWorkflow />);

    expect(screen.getByText("每日研究工作流")).toBeInTheDocument();
    expect(screen.getByText("运行参数")).toBeInTheDocument();
    expect(screen.getByDisplayValue("AI 产业链事件跟踪")).toBeInTheDocument();
    expect(screen.getByText("不审批 / 不导出 / 不实盘")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行工作流" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "试运行" })).toBeInTheDocument();
  });

  it("submits a dry-run request and renders planned steps", async () => {
    apiMock.dailyWorkflowRun.mockResolvedValueOnce(dryRunResponse);
    render(<DailyWorkflow />);

    fireEvent.click(screen.getByRole("button", { name: "试运行" }));

    await waitFor(() => expect(apiMock.dailyWorkflowRun).toHaveBeenCalledTimes(1));
    expect(apiMock.dailyWorkflowRun).toHaveBeenCalledWith(expect.objectContaining({
      dry_run: true,
      portfolio_id: "cn_a_main",
      documents: [expect.objectContaining({ title: "AI 产业链事件跟踪" })],
      steps: expect.arrayContaining(["collect_documents", "generate_draft_signals"]),
    }));
    expect(await screen.findByText("试运行计划已生成")).toBeInTheDocument();
    expect(screen.getAllByText("计划中").length).toBeGreaterThan(0);
  });

  it("runs the workflow and displays draft-signal evidence", async () => {
    apiMock.dailyWorkflowRun.mockResolvedValueOnce(okResponse);
    render(<DailyWorkflow />);

    fireEvent.click(screen.getByRole("button", { name: "运行工作流" }));

    expect(await screen.findByText("工作流已完成")).toBeInTheDocument();
    expect(screen.getAllByText("草稿信号").length).toBeGreaterThan(0);
    expect(screen.getByText("已生成 3 条执行信号草案，仍需人工确认。")).toBeInTheDocument();
    expect(screen.getAllByText("研究/模拟").length).toBeGreaterThan(0);
  });

  it("renders blocked-step feedback from the backend", async () => {
    apiMock.dailyWorkflowRun.mockResolvedValueOnce(blockedResponse);
    render(<DailyWorkflow />);

    fireEvent.click(screen.getByRole("button", { name: "运行工作流" }));

    expect(await screen.findByText("工作流已阻断")).toBeInTheDocument();
    expect(screen.getByText("候选股票缺少回测行情，请先导入 market_daily。")).toBeInTheDocument();
    expect(screen.getByText("阻断于 批量回测")).toBeInTheDocument();
  });

  it("blocks submission when no workflow step is selected", async () => {
    render(<DailyWorkflow />);

    fireEvent.click(screen.getByRole("button", { name: "清空步骤" }));
    fireEvent.click(screen.getByRole("button", { name: "运行工作流" }));

    expect(await screen.findByText("请至少选择一个工作流步骤。")).toBeInTheDocument();
    expect(apiMock.dailyWorkflowRun).not.toHaveBeenCalled();
  });
});
