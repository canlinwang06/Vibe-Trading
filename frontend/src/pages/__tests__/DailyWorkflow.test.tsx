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

function checkboxForStep(label: string): HTMLInputElement {
  const field = screen.getByText(label).closest("label");
  if (!field) throw new Error(`Missing step label: ${label}`);
  const checkbox = field.querySelector<HTMLInputElement>('input[type="checkbox"]');
  if (!checkbox) throw new Error(`Missing checkbox for step: ${label}`);
  return checkbox;
}

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
    "prepare_joinquant_strategy",
  ],
  completed_step_count: 6,
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
      name: "prepare_joinquant_strategy",
      status: "ok",
      message: "已生成 3 条聚宽模拟策略草案信号。",
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
  blocked_step: "build_candidates",
  steps: [
    {
      name: "build_candidates",
      status: "blocked",
      message: "没有可生成候选池的板块评分，请先运行板块评分。",
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
    expect(screen.getByText("不本地回测 / 不审批 / 不实盘")).toBeInTheDocument();
    expect(checkboxForStep("聚宽策略")).toBeChecked();
    expect(checkboxForStep("本地回测")).not.toBeChecked();
    expect(screen.queryByText("回测开始")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行工作流" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "试运行" })).toBeInTheDocument();
  });

  it("shows local backtest parameters only when optional local validation is selected", () => {
    render(<DailyWorkflow />);

    expect(screen.queryByText("可选本地验证参数")).not.toBeInTheDocument();

    fireEvent.click(checkboxForStep("本地回测"));

    expect(screen.getByText("可选本地验证参数")).toBeInTheDocument();
    expect(screen.getByText("回测开始")).toBeInTheDocument();
    expect(screen.getByText("回测结束")).toBeInTheDocument();
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
      steps: expect.arrayContaining(["collect_documents", "prepare_joinquant_strategy"]),
      event_reaction_windows: ["T+1", "T+5", "T+20", "T+60"],
      event_reaction_target_types: ["sector", "stock"],
    }));
    expect(await screen.findByText("试运行计划已生成")).toBeInTheDocument();
    expect(screen.getAllByText("计划中").length).toBeGreaterThan(0);
  });

  it("runs the workflow and displays JoinQuant strategy-draft evidence", async () => {
    apiMock.dailyWorkflowRun.mockResolvedValueOnce(okResponse);
    render(<DailyWorkflow />);

    fireEvent.click(screen.getByRole("button", { name: "运行工作流" }));

    expect(await screen.findByText("工作流已完成")).toBeInTheDocument();
    expect(screen.getAllByText("聚宽策略").length).toBeGreaterThan(0);
    expect(screen.getByText("已生成 3 条聚宽模拟策略草案信号。")).toBeInTheDocument();
    expect(screen.getAllByText("研究/模拟").length).toBeGreaterThan(0);
  });

  it("renders blocked-step feedback from the backend", async () => {
    apiMock.dailyWorkflowRun.mockResolvedValueOnce(blockedResponse);
    render(<DailyWorkflow />);

    fireEvent.click(screen.getByRole("button", { name: "运行工作流" }));

    expect(await screen.findByText("工作流已阻断")).toBeInTheDocument();
    expect(screen.getByText("没有可生成候选池的板块评分，请先运行板块评分。")).toBeInTheDocument();
    expect(screen.getByText("阻断于 候选股票")).toBeInTheDocument();
  });

  it("blocks submission when no workflow step is selected", async () => {
    render(<DailyWorkflow />);

    fireEvent.click(screen.getByRole("button", { name: "全选步骤" }));
    fireEvent.click(screen.getByRole("button", { name: "清空步骤" }));
    fireEvent.click(screen.getByRole("button", { name: "运行工作流" }));

    expect(await screen.findByText("请至少选择一个工作流步骤。")).toBeInTheDocument();
    expect(apiMock.dailyWorkflowRun).not.toHaveBeenCalled();
  });
});
