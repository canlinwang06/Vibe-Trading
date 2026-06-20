export const ASHARE_NAV_ITEMS = [
  { to: "/", labelKey: "layout.dashboard" },
  { to: "/event-records", labelKey: "layout.eventRecords" },
  { to: "/sector-stock-analysis", labelKey: "layout.sectorStockAnalysis" },
  { to: "/strategy-lab", labelKey: "layout.strategyLab" },
  { to: "/backtest-results", labelKey: "layout.backtestResults" },
  { to: "/risk-portfolio", labelKey: "layout.riskPortfolio" },
  { to: "/trade-plan", labelKey: "layout.tradePlan" },
  { to: "/joinquant-export", labelKey: "layout.joinquantExport" },
  { to: "/strategy-lifecycle", labelKey: "layout.strategyLifecycle" },
  { to: "/daily-workflow", labelKey: "layout.dailyWorkflow" },
  { to: "/data-sources", labelKey: "layout.dataSources" },
  { to: "/settings", labelKey: "layout.systemSettings" },
] as const;

export const ASHARE_NAV_LABELS_ZH = [
  "A 股驾驶舱",
  "事件记录库",
  "板块及股票分析",
  "策略实验室",
  "回测结果",
  "风控组合",
  "交易计划",
  "聚宽任务中心",
  "策略生命周期",
  "每日工作流",
  "数据源设置",
  "系统设置",
] as const;
