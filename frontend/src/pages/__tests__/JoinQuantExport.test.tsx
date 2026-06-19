import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { JoinQuantExport } from "../JoinQuantExport";
import type { JoinQuantCopyPackageResponse, JoinQuantPreflightResponse } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  joinQuantPreflight: vi.fn(),
  joinQuantExportCopyPackage: vi.fn(),
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

const okPreflight: JoinQuantPreflightResponse = {
  portfolio_id: "cn_a_main",
  signal_date: "2026-06-23",
  validation: {
    status: "ok",
    checked_count: 3,
    error_count: 0,
    warning_count: 0,
    errors: [],
    warnings: [],
  },
  copy_ready: true,
  research_only: true,
  live_trading: false,
};

const blockedPreflight: JoinQuantPreflightResponse = {
  ...okPreflight,
  validation: {
    status: "blocked",
    checked_count: 1,
    error_count: 1,
    warning_count: 0,
    errors: ["第 1 条信号状态为 draft，只有 approved 状态可以导出。"],
    warnings: [],
  },
  copy_ready: false,
};

const copyPackage: JoinQuantCopyPackageResponse = {
  status: "ok",
  export_type: "copy-package",
  portfolio_id: "cn_a_main",
  signal_date: "2026-06-23",
  strategy_id: "cn_a_main_jq_test",
  manifest: {
    package_type: "joinquant-copy-package",
    strategy_id: "cn_a_main_jq_test",
    portfolio_id: "cn_a_main",
    signal_date: "2026-06-23",
    valid_for: "2026-06-24",
    target_count: 3,
    total_exposure: 0.19,
    files: [
      { filename: "strategy.py", content_type: "text/x-python", size: 128 },
      { filename: "signals.json", content_type: "application/json", size: 256 },
      { filename: "signals.csv", content_type: "text/csv", size: 96 },
      { filename: "README.md", content_type: "text/markdown", size: 180 },
    ],
    manual_confirmation_required: true,
    live_trading: false,
  },
  files: [
    {
      filename: "strategy.py",
      content_type: "text/x-python",
      content: "def initialize(context):\n    pass\n",
    },
    { filename: "signals.json", content_type: "application/json", content: "{}" },
    { filename: "signals.csv", content_type: "text/csv", content: "ticker,target_weight\n" },
    { filename: "README.md", content_type: "text/markdown", content: "# Vibe-Trading\n" },
  ],
  clipboard_text: "def initialize(context):\n    pass\n",
  validation: okPreflight.validation,
  copy_ready: true,
  manual_confirmation_required: true,
  research_only: true,
  live_trading: false,
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("JoinQuantExport page", () => {
  beforeEach(() => {
    apiMock.joinQuantPreflight.mockReset();
    apiMock.joinQuantExportCopyPackage.mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  });

  it("renders the Chinese JoinQuant copy workspace", () => {
    render(<JoinQuantExport />);

    expect(screen.getByText("聚宽导出")).toBeInTheDocument();
    expect(screen.getByText("导出参数")).toBeInTheDocument();
    expect(screen.getByText("复制状态")).toBeInTheDocument();
    expect(screen.getByText("仅导出 approved 信号")).toBeInTheDocument();
    expect(screen.getByText("不登录聚宽，不提交订单")).toBeInTheDocument();
  });

  it("runs preflight with the approved-signal guard enabled", async () => {
    apiMock.joinQuantPreflight.mockResolvedValue(okPreflight);

    render(<JoinQuantExport />);
    fireEvent.click(screen.getByRole("button", { name: "预检查" }));

    await waitFor(() => expect(apiMock.joinQuantPreflight).toHaveBeenCalledTimes(1));
    expect(apiMock.joinQuantPreflight).toHaveBeenCalledWith(
      expect.objectContaining({
        portfolio_id: "cn_a_main",
        require_approved: true,
      }),
    );
    expect(await screen.findByText("预检查通过")).toBeInTheDocument();
    expect(screen.getByText("可复制")).toBeInTheDocument();
  });

  it("keeps blocked preflight visible and does not show a package", async () => {
    apiMock.joinQuantPreflight.mockResolvedValue(blockedPreflight);

    render(<JoinQuantExport />);
    fireEvent.click(screen.getByRole("button", { name: "预检查" }));

    expect(await screen.findByText("预检查阻断")).toBeInTheDocument();
    expect(screen.getByText("暂不可复制")).toBeInTheDocument();
    expect(screen.getByText(/只有 approved 状态可以导出/)).toBeInTheDocument();
    expect(screen.queryByText("复制包摘要")).not.toBeInTheDocument();
  });

  it("generates the copy package and copies strategy.py to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    apiMock.joinQuantPreflight.mockResolvedValue(okPreflight);
    apiMock.joinQuantExportCopyPackage.mockResolvedValue(copyPackage);

    render(<JoinQuantExport />);
    fireEvent.click(screen.getByRole("button", { name: "生成复制包" }));

    expect(await screen.findByText("复制包摘要")).toBeInTheDocument();
    expect(screen.getByText("strategy.py")).toBeInTheDocument();
    expect(screen.getByText("3 个 / 19%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "复制策略代码" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(copyPackage.clipboard_text));
    expect(screen.getByText(/已复制 strategy.py/)).toBeInTheDocument();
  });

  it("clears the generated package when export parameters change", async () => {
    apiMock.joinQuantPreflight.mockResolvedValue(okPreflight);
    apiMock.joinQuantExportCopyPackage.mockResolvedValue(copyPackage);

    render(<JoinQuantExport />);
    fireEvent.click(screen.getByRole("button", { name: "生成复制包" }));
    expect(await screen.findByText("复制包摘要")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("组合 ID"), { target: { value: "cn_a_alt" } });

    expect(screen.queryByText("复制包摘要")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "复制策略代码" })).toBeDisabled();
  });

  it("ignores stale export responses after parameters change", async () => {
    const pendingPreflight = deferred<JoinQuantPreflightResponse>();
    apiMock.joinQuantPreflight.mockReturnValueOnce(pendingPreflight.promise);

    render(<JoinQuantExport />);
    fireEvent.click(screen.getByRole("button", { name: "生成复制包" }));
    fireEvent.change(screen.getByLabelText("组合 ID"), { target: { value: "cn_a_alt" } });

    await act(async () => {
      pendingPreflight.resolve(okPreflight);
      await pendingPreflight.promise;
      await Promise.resolve();
    });

    expect(apiMock.joinQuantExportCopyPackage).not.toHaveBeenCalled();
    expect(screen.queryByText("预检查通过")).not.toBeInTheDocument();
    expect(screen.queryByText("复制包摘要")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "复制策略代码" })).toBeDisabled();
  });

  it("offers strategy.py download when clipboard copy fails", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("clipboard denied"));
    const createObjectURL = vi.fn().mockReturnValue("blob:strategy");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectURL,
    });
    apiMock.joinQuantPreflight.mockResolvedValue(okPreflight);
    apiMock.joinQuantExportCopyPackage.mockResolvedValue(copyPackage);

    render(<JoinQuantExport />);
    fireEvent.click(screen.getByRole("button", { name: "生成复制包" }));
    await screen.findByText("复制包摘要");

    fireEvent.click(screen.getByRole("button", { name: "复制策略代码" }));
    expect(await screen.findByText("clipboard denied")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下载 strategy.py" }));
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:strategy");
  });
});
