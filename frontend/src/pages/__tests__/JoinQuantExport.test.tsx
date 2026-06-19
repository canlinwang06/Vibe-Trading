import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { JoinQuantExport } from "../JoinQuantExport";
import type {
  JoinQuantCopyPackageResponse,
  JoinQuantExecutionReport,
  JoinQuantExecutionReportImportResponse,
  JoinQuantExecutionReportListResponse,
  JoinQuantExecutionReportSummary,
  JoinQuantPreflightResponse,
  JoinQuantSimulationReadinessReport,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  joinQuantPreflight: vi.fn(),
  joinQuantExportCopyPackage: vi.fn(),
  joinQuantImportExecutionReports: vi.fn(),
  joinQuantExecutionReportSummary: vi.fn(),
  joinQuantListExecutionReports: vi.fn(),
  joinQuantSimulationReadiness: vi.fn(),
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

const executionReports: JoinQuantExecutionReport[] = [
  {
    report_id: "cn_a_main:2026-06-23:2026-06-24:600519.SH",
    portfolio_id: "cn_a_main",
    signal_date: "2026-06-23",
    trade_date: "2026-06-24",
    ticker: "600519.SH",
    planned_weight: 0.08,
    executed_weight: 0.08,
    order_status: "filled",
    fill_price: 1688.5,
    fill_amount: 8000,
  },
  {
    report_id: "cn_a_main:2026-06-23:2026-06-24:300750.SZ",
    portfolio_id: "cn_a_main",
    signal_date: "2026-06-23",
    trade_date: "2026-06-24",
    ticker: "300750.SZ",
    planned_weight: 0.07,
    executed_weight: 0,
    order_status: "rejected",
    error_message: "涨停无法买入",
  },
];

const executionSummary: JoinQuantExecutionReportSummary = {
  status: "needs_review",
  portfolio_id: "cn_a_main",
  signal_date: "2026-06-23",
  trade_date: "2026-06-24",
  report_count: 2,
  signal_count: 2,
  matched_signal_count: 2,
  failed_count: 1,
  unmatched_report_count: 0,
  missing_report_count: 0,
  total_planned_weight: 0.15,
  total_executed_weight: 0.08,
  max_abs_weight_diff: 0.07,
  total_abs_weight_diff: 0.07,
  tolerance: 0.01,
  status_counts: { filled: 1, rejected: 1 },
  unmatched_reports: [],
  missing_reports: [],
  deviations: [
    {
      ticker: "600519.SH",
      planned_weight: 0.08,
      executed_weight: 0.08,
      abs_weight_diff: 0,
      order_status: "filled",
      matched_signal: true,
      needs_review: false,
    },
    {
      ticker: "300750.SZ",
      planned_weight: 0.07,
      executed_weight: 0,
      abs_weight_diff: 0.07,
      order_status: "rejected",
      matched_signal: true,
      needs_review: true,
    },
  ],
  action_required: true,
  research_only: true,
  live_trading: false,
};

const importResponse: JoinQuantExecutionReportImportResponse = {
  status: "needs_review",
  imported_count: 2,
  portfolio_id: "cn_a_main",
  signal_date: "2026-06-23",
  trade_date: "2026-06-24",
  replace: false,
  reports: executionReports,
  summary: executionSummary,
  research_only: true,
  live_trading: false,
};

const listResponse: JoinQuantExecutionReportListResponse = {
  status: "ok",
  count: executionReports.length,
  reports: executionReports,
};

const readinessReport: JoinQuantSimulationReadinessReport = {
  status: "needs_review",
  recommendation: "fix_before_live",
  readiness_score: 52,
  portfolio_id: "cn_a_main",
  lookback_days: 30,
  window_start: "2026-05-26",
  window_end: "2026-06-24",
  tolerance: 0.02,
  min_batches: 2,
  observed_batch_count: 2,
  signal_batch_count: 2,
  missing_signal_batch_count: 0,
  totals: {
    report_count: 6,
    signal_count: 6,
    failed_count: 1,
    missing_report_count: 0,
    unmatched_report_count: 0,
    deviation_count: 1,
    limit_or_suspend_issue_count: 1,
    total_abs_weight_diff: 0.07,
    max_abs_weight_diff: 0.07,
    avg_signal_delay_days: 1,
    max_signal_delay_days: 1,
  },
  rates: {
    failed_rate: 0.166667,
    missing_report_rate: 0,
    unmatched_report_rate: 0,
    deviation_rate: 0.166667,
  },
  backtest_risk: {
    status: "needs_review",
    run_count: 3,
    worst_max_drawdown: -0.12,
    avg_sharpe: 1.12,
    avg_trade_count: 38,
    message: "回测最差最大回撤 -12.00%，达到复盘阈值。",
  },
  checks: [
    {
      name: "execution_failure_rate",
      status: "fail",
      observed: 0.166667,
      threshold: 0.05,
      message: "存在失败、撤单或拒单记录，需要复盘原因。",
    },
    {
      name: "observation_window",
      status: "pass",
      observed: 2,
      threshold: 2,
      message: "模拟盘观察批次数已达到验收下限。",
    },
  ],
  findings: [
    "发现 1 条失败、撤单或拒单记录，需要定位聚宽侧原因。",
    "回测最差最大回撤 -12.00%，达到复盘阈值。",
  ],
  daily_summaries: [
    {
      signal_date: "2026-06-23",
      trade_date: "2026-06-24",
      status: "needs_review",
      report_count: 3,
      signal_count: 3,
      failed_count: 1,
      missing_report_count: 0,
      unmatched_report_count: 0,
      max_abs_weight_diff: 0.07,
      total_abs_weight_diff: 0.07,
      deviation_count: 1,
      signal_delay_days: 1,
      action_required: true,
    },
  ],
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
    apiMock.joinQuantImportExecutionReports.mockReset();
    apiMock.joinQuantExecutionReportSummary.mockReset();
    apiMock.joinQuantListExecutionReports.mockReset();
    apiMock.joinQuantSimulationReadiness.mockReset();
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
    expect(screen.getByText("执行报告导入")).toBeInTheDocument();
    expect(screen.getByText("模拟盘准备度")).toBeInTheDocument();
    expect(screen.getByLabelText("报告 JSON")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成准备度报告" })).toBeInTheDocument();
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
    expect(screen.getByText("复制前审阅")).toBeInTheDocument();
    expect(screen.getByText("代码映射检查")).toBeInTheDocument();
    expect(screen.getByText("基础语法检查")).toBeInTheDocument();
    expect(screen.getByText("目标持仓来源")).toBeInTheDocument();
    expect(screen.getByText(/Download Python Strategy/)).toBeInTheDocument();
    expect(screen.getAllByText("strategy.py").length).toBeGreaterThan(0);
    expect(screen.getByText("复制包清单")).toBeInTheDocument();
    expect(screen.getByText("下载完整复制包")).toBeInTheDocument();
    expect(screen.getByText("cn_a_main_jq_test_2026-06-23_copy_package.json")).toBeInTheDocument();
    expect(screen.getByText("信号文件预览")).toBeInTheDocument();
    expect(screen.getByText("导出信号 JSON")).toBeInTheDocument();
    expect(screen.getByText("导出信号 CSV")).toBeInTheDocument();
    expect(screen.getByText("signals.json / application/json / 2 字符")).toBeInTheDocument();
    expect(screen.getByText("signals.csv / text/csv / 21 字符")).toBeInTheDocument();
    expect(screen.getByText("3 个 / 19%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "复制策略代码" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(copyPackage.clipboard_text));
    expect(screen.getByText(/已复制 strategy.py/)).toBeInTheDocument();
    expect(screen.getByText(/最近复制时间：/)).toBeInTheDocument();
  });

  it("downloads generated signal JSON and CSV files", async () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:signals");
    const revokeObjectURL = vi.fn();
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
    expect(await screen.findByText("信号文件预览")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下载 signals.json" }));
    fireEvent.click(screen.getByRole("button", { name: "下载 signals.csv" }));

    expect(createObjectURL).toHaveBeenCalledTimes(2);
    expect(revokeObjectURL).toHaveBeenCalledTimes(2);
  });

  it("downloads the complete local copy package manifest", async () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:package");
    const revokeObjectURL = vi.fn();
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
    expect(await screen.findByText("复制包清单")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下载完整复制包" }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:package");
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("application/json");
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

  it("imports pasted JoinQuant execution reports and shows reconciliation", async () => {
    apiMock.joinQuantImportExecutionReports.mockResolvedValue(importResponse);

    render(<JoinQuantExport />);
    fireEvent.change(screen.getByLabelText("报告信号日期"), { target: { value: "2026-06-23" } });
    fireEvent.change(screen.getByLabelText("报告交易日"), { target: { value: "2026-06-24" } });
    fireEvent.click(screen.getByRole("button", { name: "导入报告" }));

    await waitFor(() => expect(apiMock.joinQuantImportExecutionReports).toHaveBeenCalledTimes(1));
    expect(apiMock.joinQuantImportExecutionReports).toHaveBeenCalledWith(
      expect.objectContaining({
        portfolio_id: "cn_a_main",
        signal_date: "2026-06-23",
        trade_date: "2026-06-24",
        replace: false,
        reports: expect.arrayContaining([
          expect.objectContaining({ ticker: "600519.XSHG", order_status: "filled" }),
        ]),
      }),
    );
    expect(await screen.findByText("已导入 2 条聚宽报告。")).toBeInTheDocument();
    expect(screen.getByText("执行复盘摘要")).toBeInTheDocument();
    expect(screen.getByText("需要复盘")).toBeInTheDocument();
    expect(screen.getByText("失败订单")).toBeInTheDocument();
    expect(screen.getAllByText("300750.SZ").length).toBeGreaterThan(0);
    expect(screen.getByText("最近导入报告")).toBeInTheDocument();
  });

  it("blocks invalid execution report JSON before calling the API", async () => {
    render(<JoinQuantExport />);
    fireEvent.change(screen.getByLabelText("报告 JSON"), { target: { value: "{not json" } });
    fireEvent.click(screen.getByRole("button", { name: "导入报告" }));

    expect(await screen.findByText("报告 JSON 格式无效，请粘贴 JSON 数组或包含 reports 的对象。")).toBeInTheDocument();
    expect(apiMock.joinQuantImportExecutionReports).not.toHaveBeenCalled();
  });

  it("refreshes execution summary and report list", async () => {
    apiMock.joinQuantExecutionReportSummary.mockResolvedValue(executionSummary);
    apiMock.joinQuantListExecutionReports.mockResolvedValue(listResponse);

    render(<JoinQuantExport />);
    fireEvent.change(screen.getByLabelText("报告信号日期"), { target: { value: "2026-06-23" } });
    fireEvent.change(screen.getByLabelText("报告交易日"), { target: { value: "2026-06-24" } });
    fireEvent.change(screen.getByLabelText("偏差容忍度"), { target: { value: "0.02" } });
    fireEvent.click(screen.getByRole("button", { name: "查询复盘" }));

    await waitFor(() => expect(apiMock.joinQuantExecutionReportSummary).toHaveBeenCalledTimes(1));
    expect(apiMock.joinQuantExecutionReportSummary).toHaveBeenCalledWith({
      portfolio_id: "cn_a_main",
      signal_date: "2026-06-23",
      trade_date: "2026-06-24",
      tolerance: 0.02,
    });
    expect(apiMock.joinQuantListExecutionReports).toHaveBeenCalledWith({
      portfolio_id: "cn_a_main",
      signal_date: "2026-06-23",
      trade_date: "2026-06-24",
      limit: 200,
    });
    expect(await screen.findByText("已加载 2 条报告的复盘摘要。")).toBeInTheDocument();
    expect(screen.getByText("执行复盘摘要")).toBeInTheDocument();
    expect(screen.getByText("最近导入报告")).toBeInTheDocument();
  });

  it("generates a simulation readiness report from the Chinese UI", async () => {
    apiMock.joinQuantSimulationReadiness.mockResolvedValue(readinessReport);

    render(<JoinQuantExport />);
    fireEvent.change(screen.getByLabelText("观察天数"), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("最低批次"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("准备度偏差容忍度"), { target: { value: "0.02" } });
    fireEvent.click(screen.getByRole("button", { name: "生成准备度报告" }));

    await waitFor(() => expect(apiMock.joinQuantSimulationReadiness).toHaveBeenCalledTimes(1));
    expect(apiMock.joinQuantSimulationReadiness).toHaveBeenCalledWith({
      portfolio_id: "cn_a_main",
      lookback_days: 30,
      min_batches: 2,
      tolerance: 0.02,
    });
    expect(await screen.findByText("准备度结论：需要复盘。")).toBeInTheDocument();
    expect(screen.getByText("模拟盘准备度报告")).toBeInTheDocument();
    expect(screen.getByText("修复后再评估")).toBeInTheDocument();
    expect(screen.getByText("发现 1 条失败、撤单或拒单记录，需要定位聚宽侧原因。")).toBeInTheDocument();
    expect(screen.getByText("execution_failure_rate")).toBeInTheDocument();
  });

  it("blocks invalid readiness parameters before calling the API", async () => {
    render(<JoinQuantExport />);
    fireEvent.change(screen.getByLabelText("观察天数"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "生成准备度报告" }));

    expect(await screen.findByText("观察天数必须是 1 到 365 之间的整数。")).toBeInTheDocument();
    expect(apiMock.joinQuantSimulationReadiness).not.toHaveBeenCalled();
  });
});
