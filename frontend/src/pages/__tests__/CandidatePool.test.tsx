import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CandidatePool } from "../CandidatePool";
import type {
  CandidatePoolBuildResponse,
  CandidatePoolListResponse,
  CandidateRecord,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  listCandidatePool: vi.fn(),
  buildCandidatePool: vi.fn(),
  addUserCandidate: vi.fn(),
  includeCandidate: vi.fn(),
  excludeCandidate: vi.fn(),
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

const candidate: CandidateRecord = {
  as_of_date: "2026-06-19",
  ticker: "300308.SZ",
  ticker_name: "中际旭创",
  market: "CN_A",
  source: "sector_radar",
  sector_id: "theme_ai_optical",
  sector_name: "光模块",
  theme: "AI算力",
  event_heat_score: 0.82,
  sector_heat_score: 0.78,
  stock_score: 0.86,
  user_priority: 0,
  risk_flag: "normal",
  included: true,
  reason: "AI算力 主题映射。",
  created_at: "2026-06-19T12:00:00",
};

const excludedCandidate: CandidateRecord = {
  ...candidate,
  ticker: "300502.SZ",
  ticker_name: "新易盛",
  included: false,
};

const listResponse: CandidatePoolListResponse = {
  candidate_count: 2,
  candidates: [candidate, excludedCandidate],
};

const buildResponse: CandidatePoolBuildResponse = {
  status: "ok",
  as_of_date: "2026-06-19",
  rows_written: 2,
  candidate_count: 2,
  candidates: [candidate, excludedCandidate],
};

describe("CandidatePool page", () => {
  beforeEach(() => {
    apiMock.listCandidatePool.mockReset();
    apiMock.buildCandidatePool.mockReset();
    apiMock.addUserCandidate.mockReset();
    apiMock.includeCandidate.mockReset();
    apiMock.excludeCandidate.mockReset();
  });

  it("renders the Chinese candidate-pool workbench", () => {
    render(<CandidatePool />);

    expect(screen.getByText("候选股票池")).toBeInTheDocument();
    expect(screen.getByText("不生成交易信号")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新候选" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成候选池" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加入候选池" })).toBeInTheDocument();
  });

  it("loads candidates through the API", async () => {
    apiMock.listCandidatePool.mockResolvedValueOnce(listResponse);
    render(<CandidatePool />);

    fireEvent.click(screen.getByRole("button", { name: "刷新候选" }));

    await waitFor(() => expect(apiMock.listCandidatePool).toHaveBeenCalledTimes(1));
    expect(apiMock.listCandidatePool).toHaveBeenCalledWith(expect.objectContaining({
      limit: 100,
      included: null,
      min_score: 0,
    }));
    expect(await screen.findByText("中际旭创")).toBeInTheDocument();
    expect(screen.getByText("新易盛")).toBeInTheDocument();
    expect(screen.getAllByText("板块雷达").length).toBeGreaterThan(0);
  });

  it("builds a candidate pool and renders the result", async () => {
    apiMock.buildCandidatePool.mockResolvedValueOnce(buildResponse);
    render(<CandidatePool />);

    fireEvent.click(screen.getByRole("button", { name: "生成候选池" }));

    await waitFor(() => expect(apiMock.buildCandidatePool).toHaveBeenCalledTimes(1));
    expect(apiMock.buildCandidatePool).toHaveBeenCalledWith(expect.objectContaining({
      limit: 50,
      min_sector_score: 0,
    }));
    expect(await screen.findByText("生成完成")).toBeInTheDocument();
    expect(screen.getByText("已生成 2 条候选股票。")).toBeInTheDocument();
    expect(screen.getByText("中际旭创")).toBeInTheDocument();
  });

  it("adds a manual candidate and refreshes the list", async () => {
    apiMock.addUserCandidate.mockResolvedValueOnce({ ...candidate, source: "user_added" });
    apiMock.listCandidatePool.mockResolvedValueOnce(listResponse);
    render(<CandidatePool />);

    fireEvent.click(screen.getByRole("button", { name: "加入候选池" }));

    await waitFor(() => expect(apiMock.addUserCandidate).toHaveBeenCalledTimes(1));
    expect(apiMock.addUserCandidate).toHaveBeenCalledWith(expect.objectContaining({
      ticker: "300308.SZ",
      ticker_name: "中际旭创",
      theme: "AI算力",
      sector_name: "光模块",
    }));
    expect(await screen.findByText("已加入 中际旭创。")).toBeInTheDocument();
    expect(apiMock.listCandidatePool).toHaveBeenCalledTimes(1);
  });

  it("excludes and includes candidates from the table", async () => {
    apiMock.listCandidatePool
      .mockResolvedValueOnce(listResponse)
      .mockResolvedValueOnce({ candidate_count: 1, candidates: [{ ...candidate, included: false }] })
      .mockResolvedValueOnce(listResponse);
    apiMock.excludeCandidate.mockResolvedValueOnce({ ...candidate, included: false });
    apiMock.includeCandidate.mockResolvedValueOnce({ ...candidate, included: true });
    render(<CandidatePool />);

    fireEvent.click(screen.getByRole("button", { name: "刷新候选" }));
    expect(await screen.findByText("中际旭创")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "排除" })[0]);
    await waitFor(() => expect(apiMock.excludeCandidate).toHaveBeenCalledTimes(1));
    expect(apiMock.excludeCandidate).toHaveBeenCalledWith(expect.objectContaining({
      ticker: "300308.SZ",
      reason: "用户在候选池页面排除观察。",
    }));
    expect(await screen.findByText("中际旭创 已排除候选池。")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "纳入" })[0]);
    await waitFor(() => expect(apiMock.includeCandidate).toHaveBeenCalledTimes(1));
  });

  it("shows Chinese validation errors without calling the backend", async () => {
    render(<CandidatePool />);

    fireEvent.change(screen.getByLabelText("查询上限"), { target: { value: "9999" } });
    fireEvent.click(screen.getByRole("button", { name: "刷新候选" }));

    expect(await screen.findByText("查询上限必须是 1 到 500 之间的整数。")).toBeInTheDocument();
    expect(apiMock.listCandidatePool).not.toHaveBeenCalled();
  });

  it("shows Chinese API errors", async () => {
    apiMock.buildCandidatePool.mockRejectedValueOnce(new Error("没有可生成候选池的板块评分，请先运行板块评分。"));
    render(<CandidatePool />);

    fireEvent.click(screen.getByRole("button", { name: "生成候选池" }));

    expect(await screen.findByText("没有可生成候选池的板块评分，请先运行板块评分。")).toBeInTheDocument();
  });
});
