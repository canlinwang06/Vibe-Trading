export const ASHARE_NAV_ITEMS = [
  { to: "/", labelKey: "layout.dashboard" },
  { to: "/event-radar", labelKey: "layout.eventRadar" },
  { to: "/sector-radar", labelKey: "layout.sectorRadar" },
  { to: "/candidate-pool", labelKey: "layout.candidatePool" },
  { to: "/strategy-lab", labelKey: "layout.strategyLab" },
  { to: "/backtest-results", labelKey: "layout.backtestResults" },
  { to: "/risk-portfolio", labelKey: "layout.riskPortfolio" },
  { to: "/trade-plan", labelKey: "layout.tradePlan" },
  { to: "/joinquant-export", labelKey: "layout.joinquantExport" },
  { to: "/data-sources", labelKey: "layout.dataSources" },
  { to: "/settings", labelKey: "layout.systemSettings" },
] as const;

export const ASHARE_NAV_LABELS_ZH = [
  "A 股驾驶舱",
  "事件雷达",
  "板块雷达",
  "候选股票池",
  "策略实验室",
  "回测结果",
  "风控组合",
  "交易计划",
  "聚宽导出",
  "数据源设置",
  "系统设置",
] as const;
