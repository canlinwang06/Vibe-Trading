import { Suspense, lazy, type ComponentType } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";

const Agent = lazy(() => import("@/pages/Agent").then((m) => ({ default: m.Agent })));
const RunDetail = lazy(() =>
  import("@/pages/RunDetail").then((m) => ({ default: m.RunDetail })),
);
const Compare = lazy(() =>
  import("@/pages/Compare").then((m) => ({ default: m.Compare })),
);
const Settings = lazy(() =>
  import("@/pages/Settings").then((m) => ({ default: m.Settings })),
);
const Runtime = lazy(() =>
  import("@/pages/Runtime").then((m) => ({ default: m.Runtime })),
);
const Correlation = lazy(() =>
  import("@/pages/Correlation").then((m) => ({ default: m.Correlation })),
);
const AlphaZoo = lazy(() =>
  import("@/pages/AlphaZoo").then((m) => ({ default: m.AlphaZoo })),
);
const EventRadar = lazy(() =>
  import("@/pages/EventRadar").then((m) => ({ default: m.EventRadar })),
);
const EventRecords = lazy(() =>
  import("@/pages/EventRecords").then((m) => ({ default: m.EventRecords })),
);
const SectorStockAnalysis = lazy(() =>
  import("@/pages/SectorStockAnalysis").then((m) => ({ default: m.SectorStockAnalysis })),
);
const SectorRadar = lazy(() =>
  import("@/pages/SectorRadar").then((m) => ({ default: m.SectorRadar })),
);
const EventReactions = lazy(() =>
  import("@/pages/EventReactions").then((m) => ({ default: m.EventReactions })),
);
const CandidatePool = lazy(() =>
  import("@/pages/CandidatePool").then((m) => ({ default: m.CandidatePool })),
);
const StrategyLab = lazy(() =>
  import("@/pages/StrategyLab").then((m) => ({ default: m.StrategyLab })),
);
const BacktestResults = lazy(() =>
  import("@/pages/BacktestResults").then((m) => ({ default: m.BacktestResults })),
);
const RiskPortfolio = lazy(() =>
  import("@/pages/RiskPortfolio").then((m) => ({ default: m.RiskPortfolio })),
);
const TradePlan = lazy(() =>
  import("@/pages/TradePlan").then((m) => ({ default: m.TradePlan })),
);
const JoinQuantExport = lazy(() =>
  import("@/pages/JoinQuantExport").then((m) => ({ default: m.JoinQuantExport })),
);
const StrategyLifecycle = lazy(() =>
  import("@/pages/StrategyLifecycle").then((m) => ({ default: m.StrategyLifecycle })),
);
const DailyWorkflow = lazy(() =>
  import("@/pages/DailyWorkflow").then((m) => ({ default: m.DailyWorkflow })),
);
const DataSources = lazy(() =>
  import("@/pages/DataSources").then((m) => ({ default: m.DataSources })),
);
const AdvisorToday = lazy(() =>
  import("@/pages/Advisor").then((m) => ({ default: m.AdvisorToday })),
);
const AdvisorStocks = lazy(() =>
  import("@/pages/Advisor").then((m) => ({ default: m.AdvisorStocks })),
);
const AdvisorMemory = lazy(() =>
  import("@/pages/Advisor").then((m) => ({ default: m.AdvisorMemory })),
);
const AdvisorHoldings = lazy(() =>
  import("@/pages/Advisor").then((m) => ({ default: m.AdvisorHoldings })),
);
const AdvisorWatchlist = lazy(() =>
  import("@/pages/Advisor").then((m) => ({ default: m.AdvisorWatchlist })),
);
const AdvisorJournal = lazy(() =>
  import("@/pages/Advisor").then((m) => ({ default: m.AdvisorJournal })),
);

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
      正在加载…
    </div>
  );
}

function wrap(Component: ComponentType) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  );
}

const CLOUD_THREE_PAGE_MODE = import.meta.env.VITE_VIBE_CLOUD_THREE_PAGE === "1";
const ROUTER_BASENAME =
  import.meta.env.BASE_URL && import.meta.env.BASE_URL !== "/"
    ? import.meta.env.BASE_URL.replace(/\/$/, "")
    : undefined;

function localOnly(Component: ComponentType) {
  return CLOUD_THREE_PAGE_MODE ? <Navigate to="/advisor/today" replace /> : wrap(Component);
}

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Navigate to="/advisor/today" replace /> },
      { path: "/advisor/today", element: wrap(AdvisorToday) },
      { path: "/advisor/stocks", element: wrap(AdvisorStocks) },
      { path: "/advisor/memory", element: wrap(AdvisorMemory) },
      { path: "/advisor/holdings", element: localOnly(AdvisorHoldings) },
      { path: "/advisor/watchlist", element: localOnly(AdvisorWatchlist) },
      { path: "/advisor/journal", element: localOnly(AdvisorJournal) },
      { path: "/event-records", element: localOnly(EventRecords) },
      { path: "/sector-stock-analysis", element: localOnly(SectorStockAnalysis) },
      { path: "/event-radar", element: localOnly(EventRadar) },
      { path: "/sector-radar", element: localOnly(SectorRadar) },
      { path: "/event-reactions", element: localOnly(EventReactions) },
      { path: "/candidate-pool", element: localOnly(CandidatePool) },
      { path: "/strategy-lab", element: localOnly(StrategyLab) },
      { path: "/backtest-results", element: localOnly(BacktestResults) },
      { path: "/risk-portfolio", element: localOnly(RiskPortfolio) },
      { path: "/trade-plan", element: localOnly(TradePlan) },
      { path: "/joinquant-export", element: localOnly(JoinQuantExport) },
      { path: "/strategy-lifecycle", element: localOnly(StrategyLifecycle) },
      { path: "/daily-workflow", element: localOnly(DailyWorkflow) },
      { path: "/data-sources", element: localOnly(DataSources) },
      { path: "/agent", element: localOnly(Agent) },
      { path: "/runtime", element: localOnly(Runtime) },
      { path: "/settings", element: localOnly(Settings) },
      { path: "/runs/:runId", element: localOnly(RunDetail) },
      { path: "/compare", element: localOnly(Compare) },
      { path: "/correlation", element: localOnly(Correlation) },
      { path: "/alpha-zoo", element: localOnly(AlphaZoo) },
      { path: "/alpha-zoo/bench", element: localOnly(AlphaZoo) },
      { path: "/alpha-zoo/compare", element: localOnly(AlphaZoo) },
      { path: "/alpha-zoo/:alphaId", element: localOnly(AlphaZoo) },
      { path: "*", element: <Navigate to="/advisor/today" replace /> },
    ],
  },
], { basename: ROUTER_BASENAME });
