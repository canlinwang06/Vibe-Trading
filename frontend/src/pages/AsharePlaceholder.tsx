import {
  BarChart3,
  ClipboardList,
  Database,
  FileText,
  FlaskConical,
  Layers,
  Radar,
  ShieldCheck,
  Target,
} from "lucide-react";

type PlaceholderKey =
  | "eventRadar"
  | "sectorRadar"
  | "candidatePool"
  | "strategyLab"
  | "backtestResults"
  | "riskPortfolio"
  | "tradePlan"
  | "joinquantExport"
  | "dataSources";

const PAGES: Record<PlaceholderKey, {
  title: string;
  eyebrow: string;
  description: string;
  primary: string;
  secondary: string;
  icon: typeof Radar;
}> = {
  eventRadar: {
    title: "事件雷达",
    eyebrow: "热点事件与 A 股相关度",
    description: "用于汇总政策、公告、产业新闻和社会热点，并判断事件是否可映射到 A 股主题、板块和个股。",
    primary: "该入口已迁移到事件雷达真实页面。",
    secondary: "备用页面不读取外部新闻，也不会生成交易信号。",
    icon: Radar,
  },
  sectorRadar: {
    title: "板块雷达",
    eyebrow: "板块热度与轮动观察",
    description: "用于跟踪行业板块、概念板块和事件驱动热度，形成板块层面的研究入口。",
    primary: "该入口已迁移到板块雷达真实页面。",
    secondary: "备用页面不展示实时行情，避免把空状态误认为研究结论。",
    icon: Layers,
  },
  candidatePool: {
    title: "候选股票池",
    eyebrow: "事件到股票的人工确认区",
    description: "用于承接事件映射、板块成员和用户自选股，形成可复核的 A 股候选池。",
    primary: "该入口已迁移到候选股票池真实页面。",
    secondary: "所有股票仍需满足沪深 A 股代码边界，例如 600519.SH。",
    icon: Target,
  },
  strategyLab: {
    title: "策略实验室",
    eyebrow: "模板化策略与参数管理",
    description: "用于把研究假设映射到可审计的策略模板，避免每天随机生成不可维护的交易代码。",
    primary: "该入口已迁移到策略实验室真实页面。",
    secondary: "策略计划保持草稿状态，仍不触发自动下单。",
    icon: FlaskConical,
  },
  backtestResults: {
    title: "回测结果",
    eyebrow: "批量回测与结果验收",
    description: "用于展示策略批量回测后的收益、回撤、胜率、交易成本和基准对比。",
    primary: "该入口已迁移到回测结果真实页面。",
    secondary: "当前页面不读取历史 run 结果，旧回测详情仍可通过直接链接访问。",
    icon: BarChart3,
  },
  riskPortfolio: {
    title: "风控组合",
    eyebrow: "多策略统一资金分配",
    description: "用于合并多个策略建议，统一生成目标持仓和风险约束，避免多策略各自下单。",
    primary: "该入口已迁移到风控组合真实页面。",
    secondary: "第一阶段仅做研究和模拟准备，不接券商实盘交易。",
    icon: ShieldCheck,
  },
  tradePlan: {
    title: "交易计划",
    eyebrow: "草稿计划与人工确认",
    description: "用于承接目标持仓、调仓理由、风险提示和人工确认记录。",
    primary: "该入口已迁移到交易计划真实页面。",
    secondary: "所有交易计划默认 draft，用户确认前不进入执行。",
    icon: ClipboardList,
  },
  joinquantExport: {
    title: "聚宽导出",
    eyebrow: "复制到聚宽模拟运行",
    description: "用于输出 JoinQuant 兼容策略代码或信号文件，便于复制到聚宽回测和模拟盘。",
    primary: "该入口已迁移到聚宽导出真实页面。",
    secondary: "当前页面不会连接聚宽账户，也不会提交任何订单。",
    icon: FileText,
  },
  dataSources: {
    title: "数据源设置",
    eyebrow: "A 股数据源与本地缓存",
    description: "用于集中展示 Tushare、AKShare、BaoStock、本地文件等 A 股数据源状态。",
    primary: "该入口已迁移到数据源设置真实页面。",
    secondary: "Codex 模型仍使用 ChatGPT 登录态，不需要额外模型密钥。",
    icon: Database,
  },
};

function AsharePlaceholder({ page }: { page: PlaceholderKey }) {
  const spec = PAGES[page];
  const Icon = spec.icon;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <header className="space-y-3">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Icon className="h-3.5 w-3.5 text-primary" />
          <span>{spec.eyebrow}</span>
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">{spec.title}</h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{spec.description}</p>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-5">
          <p className="text-sm font-medium text-foreground">当前状态</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{spec.primary}</p>
        </div>
        <div className="rounded-lg border bg-muted/20 p-5">
          <p className="text-sm font-medium text-foreground">安全边界</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{spec.secondary}</p>
        </div>
      </section>
    </div>
  );
}

export function EventRadar() {
  return <AsharePlaceholder page="eventRadar" />;
}

export function SectorRadar() {
  return <AsharePlaceholder page="sectorRadar" />;
}

export function CandidatePool() {
  return <AsharePlaceholder page="candidatePool" />;
}

export function StrategyLab() {
  return <AsharePlaceholder page="strategyLab" />;
}

export function BacktestResults() {
  return <AsharePlaceholder page="backtestResults" />;
}

export function RiskPortfolio() {
  return <AsharePlaceholder page="riskPortfolio" />;
}

export function TradePlan() {
  return <AsharePlaceholder page="tradePlan" />;
}

export function JoinQuantExport() {
  return <AsharePlaceholder page="joinquantExport" />;
}

export function DataSources() {
  return <AsharePlaceholder page="dataSources" />;
}
