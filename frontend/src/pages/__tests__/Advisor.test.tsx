import { render, screen } from "@testing-library/react";
import { AdvisorHoldings, AdvisorJournal, AdvisorToday, AdvisorWatchlist } from "../Advisor";

const apiMock = vi.hoisted(() => ({
  getAdvisorTodaySnapshot: vi.fn(),
  getAdvisorHoldingsSnapshot: vi.fn(),
  getAdvisorWatchlistSnapshot: vi.fn(),
  getAdvisorJournalSnapshot: vi.fn(),
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

const diagnostic = {
  ticker: "300308.SZ",
  ticker_name: "中际旭创",
  action: "hold",
  action_label: "继续持有",
  reason: "未触发硬止损、减仓线或复盘退出条件。",
  current_price: 88.5,
  next_review_date: "2026-06-24",
  sell_line: { hard_stop_price: 80, take_profit_price: 96 },
};

const candidate = {
  ticker: "000977.SZ",
  ticker_name: "浪潮信息",
  suggested_status: "ready_small_probe",
  suggested_status_label: "可小仓试探",
  reason: "价格达到触发线且退出条件完整，只能作为研究候选。",
  buy_trigger_price: 42,
  buy_trigger_condition: "放量突破触发价且板块热度不退潮。",
  not_buy_conditions: "高开超过 6% 或量能不足不买。",
  max_position_pct: 0.08,
  target_holding_days: 8,
};

describe("Advisor pages", () => {
  beforeEach(() => {
    apiMock.getAdvisorTodaySnapshot.mockReset();
    apiMock.getAdvisorHoldingsSnapshot.mockReset();
    apiMock.getAdvisorWatchlistSnapshot.mockReset();
    apiMock.getAdvisorJournalSnapshot.mockReset();
  });

  it("renders the today advisor snapshot", async () => {
    apiMock.getAdvisorTodaySnapshot.mockResolvedValueOnce({
      snapshot_type: "today",
      title: "今日建议",
      portfolio_id: "cn_a_main",
      as_of_date: "2026-06-21",
      headline: "有候选达到试探条件，但仍需遵守仓位和不买条件。",
      summary_cards: [
        { label: "持仓数量", value: 1 },
        { label: "候选数量", value: 1 },
      ],
      primary_actions: [
        {
          type: "watchlist",
          ticker: "000977.SZ",
          ticker_name: "浪潮信息",
          action: "ready_small_probe",
          label: "可小仓试探",
          reason: "价格达到触发线且退出条件完整。",
        },
      ],
      holding_action_counts: {},
      candidate_status_counts: {},
      risk_rule_counts: {},
      data_freshness: {},
      research_only: true,
      live_trading: false,
    });

    render(<AdvisorToday />);

    expect(await screen.findByText("今日建议")).toBeInTheDocument();
    expect(screen.getByText("有候选达到试探条件，但仍需遵守仓位和不买条件。")).toBeInTheDocument();
    expect(screen.getByText("可小仓试探")).toBeInTheDocument();
  });

  it("renders holdings diagnostics", async () => {
    apiMock.getAdvisorHoldingsSnapshot.mockResolvedValueOnce({
      snapshot_type: "holdings",
      title: "我的持仓",
      portfolio_id: "cn_a_main",
      as_of_date: "2026-06-21",
      headline: "优先看护已买股票，明确持有、退出或补充逻辑。",
      portfolio_summary: { position_count: 1, market_value: 8850, unrealized_pnl: 300, total_pnl: 300 },
      diagnostics: [diagnostic],
      prices: [],
      action_counts: { hold: 1 },
      research_only: true,
      live_trading: false,
    });

    render(<AdvisorHoldings />);

    expect(await screen.findByText("我的持仓")).toBeInTheDocument();
    expect(screen.getByText("继续持有")).toBeInTheDocument();
    expect(screen.getByText("中际旭创 / 300308.SZ")).toBeInTheDocument();
  });

  it("renders watchlist candidates and current risk items", async () => {
    apiMock.getAdvisorWatchlistSnapshot.mockResolvedValueOnce({
      snapshot_type: "watchlist",
      title: "观察清单",
      portfolio_id: "cn_a_main",
      as_of_date: "2026-06-21",
      headline: "候选只代表观察和条件等待，不代表直接买入。",
      candidates: [candidate],
      do_not_buy_items: [
        {
          ticker: "601138.SH",
          ticker_name: "工业富联",
          rule_id: "chase_risk",
          rule_label: "追高风险",
          severity: "high",
          reason: "当前阶段暂不追高。",
        },
      ],
      status_counts: { ready_small_probe: 1 },
      risk_rule_counts: { chase_risk: 1 },
      research_only: true,
      live_trading: false,
    });

    render(<AdvisorWatchlist />);

    expect(await screen.findByText("观察清单")).toBeInTheDocument();
    expect(screen.getByText("可小仓试探")).toBeInTheDocument();
    expect(screen.getByText("建议仓位上限")).toBeInTheDocument();
    expect(screen.getByText("8%")).toBeInTheDocument();
    expect(screen.getByText("当前阶段暂不买")).toBeInTheDocument();
    expect(screen.getByText("追高风险")).toBeInTheDocument();
  });

  it("renders advisor journal records", async () => {
    apiMock.getAdvisorJournalSnapshot.mockResolvedValueOnce({
      snapshot_type: "journal",
      title: "复盘记录",
      portfolio_id: "cn_a_main",
      headline: "记录 Codex 指令、系统建议和外部验证写回。",
      commands: [{ command_id: "cmd_1" }],
      recommendations: [
        {
          recommendation_id: "rec_1",
          action_label: "继续持有",
          ticker_name: "中际旭创",
          ticker: "300308.SZ",
          reason: "未触发退出条件。",
        },
      ],
      external_validations: [
        {
          validation_id: "validation_1",
          source: "joinquant",
          source_ref: "jq-run-001",
          subject_type: "strategy",
          subject_id: "strategy_ai_compute_breakout",
          validation_date: "2026-06-21",
          status: "passed",
          metrics: { annual_return: 0.18, max_drawdown: -0.08, sharpe: 1.28 },
          summary: "聚宽模拟回测通过初筛。",
        },
      ],
      decision_journals: [],
      record_count: 3,
      research_only: true,
      live_trading: false,
    });

    render(<AdvisorJournal />);

    expect(await screen.findByText("复盘记录")).toBeInTheDocument();
    expect(screen.getByText("系统建议")).toBeInTheDocument();
    expect(screen.getByText("未触发退出条件。")).toBeInTheDocument();
    expect(screen.getByText("聚宽模拟回测通过初筛。")).toBeInTheDocument();
    expect(screen.getByText("joinquant / strategy_ai_compute_breakout")).toBeInTheDocument();
  });
});
