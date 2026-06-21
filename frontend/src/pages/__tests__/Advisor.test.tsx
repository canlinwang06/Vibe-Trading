import { render, screen } from "@testing-library/react";
import { AdvisorHoldings, AdvisorJournal, AdvisorMemory, AdvisorStocks, AdvisorToday, AdvisorWatchlist } from "../Advisor";

const apiMock = vi.hoisted(() => ({
  getAdvisorTodaySnapshot: vi.fn(),
  getAdvisorHoldingsSnapshot: vi.fn(),
  getAdvisorWatchlistSnapshot: vi.fn(),
  getAdvisorStocksSnapshot: vi.fn(),
  getAdvisorJournalSnapshot: vi.fn(),
  getAdvisorMemorySnapshot: vi.fn(),
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
  suggested_buy_shares: 100,
  suggested_buy_amount: 4200,
  target_holding_days: 8,
};

describe("Advisor pages", () => {
  beforeEach(() => {
    apiMock.getAdvisorTodaySnapshot.mockReset();
    apiMock.getAdvisorHoldingsSnapshot.mockReset();
    apiMock.getAdvisorWatchlistSnapshot.mockReset();
    apiMock.getAdvisorStocksSnapshot.mockReset();
    apiMock.getAdvisorJournalSnapshot.mockReset();
    apiMock.getAdvisorMemorySnapshot.mockReset();
  });

  it("renders the today advisor snapshot", async () => {
    apiMock.getAdvisorTodaySnapshot.mockResolvedValueOnce({
      snapshot_type: "today",
      title: "今日助手",
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

    expect(await screen.findByText("今日助手")).toBeInTheDocument();
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
    expect(screen.getByText("模拟买入")).toBeInTheDocument();
    expect(screen.getByText("100 股")).toBeInTheDocument();
    expect(screen.getByText("预计金额")).toBeInTheDocument();
    expect(screen.getByText("¥4,200")).toBeInTheDocument();
    expect(screen.getByText("当前阶段暂不买")).toBeInTheDocument();
    expect(screen.getByText("追高风险")).toBeInTheDocument();
  });

  it("renders the unified stock pool snapshot", async () => {
    apiMock.getAdvisorStocksSnapshot.mockResolvedValueOnce({
      snapshot_type: "stocks",
      title: "我的股票池",
      portfolio_id: "cn_a_main",
      as_of_date: "2026-06-21",
      headline: "集中看护已买、观察、待买和暂不买股票。",
      summary_cards: [
        { label: "已持仓", value: 1 },
        { label: "观察中", value: 1 },
      ],
      portfolio_summary: { position_count: 1, total_pnl: 300 },
      holdings: [diagnostic],
      watchlist: [candidate],
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
      prices: [],
      action_counts: { hold: 1 },
      status_counts: { ready_small_probe: 1 },
      risk_rule_counts: { chase_risk: 1 },
      research_only: true,
      live_trading: false,
    });

    render(<AdvisorStocks />);

    expect(await screen.findByText("我的股票池")).toBeInTheDocument();
    expect(screen.getByText("已持仓：什么时候继续持有，什么时候退出")).toBeInTheDocument();
    expect(screen.getByText("继续持有")).toBeInTheDocument();
    expect(screen.getByText("观察中：到什么价位、什么条件才考虑买")).toBeInTheDocument();
    expect(screen.getByText("可小仓试探")).toBeInTheDocument();
    expect(screen.getByText("暂不买：当前阶段需要避开的条件")).toBeInTheDocument();
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

  it("renders the market memory snapshot", async () => {
    apiMock.getAdvisorMemorySnapshot.mockResolvedValueOnce({
      snapshot_type: "memory",
      title: "市场记忆",
      portfolio_id: "cn_a_main",
      headline: "按事实、判断、决策和验证沉淀市场记忆。",
      events: [
        {
          event_id: "event_ai_1",
          cluster_id: "cluster_ai",
          doc_id: "doc_ai_1",
          event_type: "industry",
          event_subtype: "AI算力",
          summary: "头部云厂商继续加码算力基础设施。",
          sentiment: "positive",
          intensity: 0.8,
          novelty: 0.6,
          certainty: 0.9,
          a_share_relevance_score: 0.86,
          source_name: "示例新闻源",
          source_type: "news",
          source_url: "https://example.com/news",
          knowable_time: "2026-06-21T09:00:00",
          evidence: {},
          related_sectors: [
            {
              event_id: "event_ai_1",
              cluster_id: "cluster_ai",
              sector_id: "theme_ai_compute",
              sector_name: "AI算力",
              theme: "AI算力",
              sub_theme: "算力基础设施",
              relevance: 0.9,
              direction: "positive",
              mapping_reason: "直接影响算力链。",
              created_at: "2026-06-21T09:05:00",
            },
          ],
          related_stocks: [
            {
              event_id: "event_ai_1",
              cluster_id: "cluster_ai",
              ticker: "000977.SZ",
              ticker_name: "浪潮信息",
              theme: "AI算力",
              sector_id: "theme_ai_compute",
              relevance: 0.82,
              direction: "positive",
              mapping_reason: "服务器链条相关。",
              created_at: "2026-06-21T09:05:00",
            },
          ],
          impact: {},
          impact_t1: { window: "T+1", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
          impact_t5: { window: "T+5", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
          impact_t20: { window: "T+20", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
          impact_t60: { window: "T+60", status: "pending", reaction_count: 0, sector_count: 0, stock_count: 0, avg_raw_return: null, avg_abnormal_return: null, worst_max_drawdown: null },
        },
      ],
      event_count: 1,
      commands: [],
      recommendations: [
        {
          recommendation_id: "rec_1",
          action_label: "继续观察",
          ticker_name: "浪潮信息",
          ticker: "000977.SZ",
          reason: "等待买入触发线。",
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
      summary_cards: [
        { label: "热点事实", value: 1 },
        { label: "系统建议", value: 1 },
      ],
      research_only: true,
      live_trading: false,
    });

    render(<AdvisorMemory />);

    expect(await screen.findByText("市场记忆")).toBeInTheDocument();
    expect(screen.getByText("热点事实：发生了什么")).toBeInTheDocument();
    expect(screen.getByText("头部云厂商继续加码算力基础设施。")).toBeInTheDocument();
    expect(screen.getByText("系统判断与外部验证：后来证明得怎么样")).toBeInTheDocument();
    expect(screen.getByText("等待买入触发线。")).toBeInTheDocument();
    expect(screen.getByText("聚宽模拟回测通过初筛。")).toBeInTheDocument();
  });
});
