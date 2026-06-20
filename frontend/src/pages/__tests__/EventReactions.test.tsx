import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EventReactions } from "../EventReactions";
import type {
  EventReactionCalculateResponse,
  EventReactionListResponse,
  EventReactionSummaryResponse,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  eventReactionsCalculate: vi.fn(),
  eventReactionSummary: vi.fn(),
  listEventReactions: vi.fn(),
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

const calculateResponse: EventReactionCalculateResponse = {
  status: "ok",
  requested_targets: 4,
  windows: ["T+1", "T+5", "T+20", "T+60"],
  target_types: ["sector", "stock"],
  reactions_written: 16,
  skipped_existing: 0,
  skipped_insufficient_data: 1,
  research_only: true,
  live_trading: false,
};

const summaryResponse: EventReactionSummaryResponse = {
  status: "ok",
  event_subtype: "AI算力",
  target_type: "stock",
  target_id: null,
  window: "T+5",
  summary_count: 1,
  research_only: true,
  live_trading: false,
  summaries: [
    {
      target_type: "stock",
      window: "T+5",
      reaction_count: 3,
      avg_raw_return: 0.12,
      avg_benchmark_return: 0.04,
      avg_sector_return: 0.08,
      avg_abnormal_return: 0.08,
      avg_max_drawdown: -0.015,
      avg_volume_change: 0.25,
      avg_breadth_change: 0.1,
    },
  ],
};

const listResponse: EventReactionListResponse = {
  status: "ok",
  reaction_count: 1,
  reactions: [
    {
      reaction_id: "rxn_1",
      cluster_id: "clu_ai",
      event_id: "evt_ai",
      target_type: "stock",
      target_id: "300308.SZ",
      target_name: "中际旭创",
      window: "T+5",
      raw_return: 0.2,
      benchmark_return: 0.04,
      sector_return: 0.11,
      abnormal_return: 0.16,
      max_drawdown: -0.01,
      volume_change: 0.35,
      breadth_change: 0.1,
      calculated_at: "2026-06-19T12:00:00",
    },
  ],
};

describe("EventReactions page", () => {
  beforeEach(() => {
    apiMock.eventReactionsCalculate.mockReset();
    apiMock.eventReactionSummary.mockReset();
    apiMock.listEventReactions.mockReset();
  });

  it("renders the Chinese event reaction workbench", () => {
    render(<EventReactions />);

    expect(screen.getByText("事件反应研究")).toBeInTheDocument();
    expect(screen.getByDisplayValue("AI算力")).toBeInTheDocument();
    expect(screen.getByText("只读研究结果")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "计算事件反应" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成摘要" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新明细" })).toBeInTheDocument();
  });

  it("calculates event reactions through the API", async () => {
    apiMock.eventReactionsCalculate.mockResolvedValueOnce(calculateResponse);
    render(<EventReactions />);

    fireEvent.click(screen.getByRole("button", { name: "计算事件反应" }));

    await waitFor(() => expect(apiMock.eventReactionsCalculate).toHaveBeenCalledTimes(1));
    expect(apiMock.eventReactionsCalculate).toHaveBeenCalledWith(expect.objectContaining({
      windows: ["T+1", "T+5", "T+20", "T+60"],
      target_types: ["sector", "stock"],
      replace: true,
    }));
    expect(await screen.findByText("计算完成")).toBeInTheDocument();
    expect(screen.getByText("16")).toBeInTheDocument();
  });

  it("renders summary and reaction details", async () => {
    apiMock.eventReactionSummary.mockResolvedValueOnce(summaryResponse);
    apiMock.listEventReactions.mockResolvedValueOnce(listResponse);
    render(<EventReactions />);

    fireEvent.click(screen.getByRole("button", { name: "生成摘要" }));
    expect(await screen.findByText("反应摘要")).toBeInTheDocument();
    expect(screen.getByText("8%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "刷新明细" }));
    expect(await screen.findByText("反应明细")).toBeInTheDocument();
    expect(screen.getByText("中际旭创")).toBeInTheDocument();
    expect(screen.getByText("300308.SZ")).toBeInTheDocument();
  });

  it("shows Chinese API errors", async () => {
    apiMock.eventReactionSummary.mockRejectedValueOnce(new Error("没有可计算的事件映射，请先运行事件映射。"));
    render(<EventReactions />);

    fireEvent.click(screen.getByRole("button", { name: "生成摘要" }));

    expect(await screen.findByText("没有可计算的事件映射，请先运行事件映射。")).toBeInTheDocument();
  });
});
