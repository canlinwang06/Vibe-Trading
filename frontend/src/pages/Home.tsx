import { Link } from "react-router-dom";
import { BarChart3, ClipboardList, FileText, Layers, ListChecks, Radar, ShieldCheck, Target } from "lucide-react";

const WORKFLOW = [
  { title: "事件雷达", desc: "收集热点事件并判断 A 股相关度", to: "/event-radar", icon: Radar },
  { title: "板块雷达", desc: "观察行业和概念板块热度", to: "/sector-radar", icon: Layers },
  { title: "候选股票池", desc: "沉淀可复核的沪深 A 股候选标的", to: "/candidate-pool", icon: Target },
  { title: "回测结果", desc: "验收策略收益、回撤和交易成本", to: "/backtest-results", icon: BarChart3 },
  { title: "风控组合", desc: "统一多策略资金分配和目标持仓", to: "/risk-portfolio", icon: ShieldCheck },
  { title: "聚宽导出", desc: "复制到聚宽回测或模拟运行", to: "/joinquant-export", icon: FileText },
  { title: "每日工作流", desc: "手动串联事件、候选、回测、风控和草稿信号", to: "/daily-workflow", icon: ListChecks },
];

const STATUS = [
  { label: "市场范围", value: "沪深 A 股" },
  { label: "交易模式", value: "研究 / 回测 / 草稿计划" },
  { label: "执行边界", value: "不自动下单" },
  { label: "模型接入", value: "Codex OAuth" },
];

export function Home() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 p-6">
      <header className="space-y-5">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-success" />
          A 股单市场研究模式
        </div>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
          <div className="space-y-3">
            <h1 className="max-w-3xl text-3xl font-semibold tracking-tight">
              A 股事件驱动策略驾驶舱
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              从事件、板块、候选股票到策略回测、风控组合和聚宽导出，所有入口都围绕沪深 A 股研究流程组织。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {STATUS.map((item) => (
              <div key={item.label} className="rounded-lg border bg-card p-3">
                <p className="text-xs text-muted-foreground">{item.label}</p>
                <p className="mt-1 text-sm font-medium text-foreground">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </header>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {WORKFLOW.map(({ title, desc, to, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="group rounded-lg border bg-card p-5 transition-colors hover:border-primary/50 hover:bg-muted/20"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-md border bg-background p-2 text-primary">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 space-y-1">
                <h2 className="text-sm font-semibold text-foreground">{title}</h2>
                <p className="text-sm leading-6 text-muted-foreground">{desc}</p>
              </div>
            </div>
          </Link>
        ))}
      </section>

      <section className="rounded-lg border bg-muted/20 p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-sm font-semibold">当前阶段状态</h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              当前阶段先提供清晰入口和研究边界，真实数据、事件抽取、批量回测和聚宽复制将在后续模块接入。
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs text-muted-foreground">
            <ClipboardList className="h-3.5 w-3.5 text-primary" />
            所有交易计划仍为草稿
          </div>
        </div>
      </section>
    </div>
  );
}
