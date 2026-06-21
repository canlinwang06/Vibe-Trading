import { Suspense, lazy, type ComponentType } from "react";
import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";

const Home = lazy(() => import("@/pages/Home").then((m) => ({ default: m.Home })));
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

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: wrap(Home) },
      { path: "/advisor/today", element: wrap(AdvisorToday) },
      { path: "/advisor/holdings", element: wrap(AdvisorHoldings) },
      { path: "/advisor/watchlist", element: wrap(AdvisorWatchlist) },
      { path: "/advisor/journal", element: wrap(AdvisorJournal) },
      { path: "/event-records", element: wrap(EventRecords) },
      { path: "/sector-stock-analysis", element: wrap(SectorStockAnalysis) },
      { path: "/event-radar", element: wrap(EventRadar) },
      { path: "/sector-radar", element: wrap(SectorRadar) },
      { path: "/event-reactions", element: wrap(EventReactions) },
      { path: "/candidate-pool", element: wrap(CandidatePool) },
      { path: "/strategy-lab", element: wrap(StrategyLab) },
      { path: "/backtest-results", element: wrap(BacktestResults) },
      { path: "/risk-portfolio", element: wrap(RiskPortfolio) },
      { path: "/trade-plan", element: wrap(TradePlan) },
      { path: "/joinquant-export", element: wrap(JoinQuantExport) },
      { path: "/strategy-lifecycle", element: wrap(StrategyLifecycle) },
      { path: "/daily-workflow", element: wrap(DailyWorkflow) },
      { path: "/data-sources", element: wrap(DataSources) },
      { path: "/agent", element: wrap(Agent) },
      { path: "/runtime", element: wrap(Runtime) },
      { path: "/settings", element: wrap(Settings) },
      { path: "/runs/:runId", element: wrap(RunDetail) },
      { path: "/compare", element: wrap(Compare) },
      { path: "/correlation", element: wrap(Correlation) },
      { path: "/alpha-zoo", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/bench", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/compare", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/:alphaId", element: wrap(AlphaZoo) },
    ],
  },
]);
