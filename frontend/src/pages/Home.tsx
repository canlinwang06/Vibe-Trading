import { Link } from "react-router-dom";
import { BarChart3, ClipboardList, FileText, Layers, ListChecks, ShieldCheck } from "lucide-react";

const WORKFLOW = [
  { title: "事件记录库", desc: "客观沉淀事件、原文证据和事后影响", to: "/event-records", icon: ClipboardList },
  { title: "板块及股票分析", desc: "基于历史事件分析热点板块和建议观察股票", to: "/sector-stock-analysis", icon: Layers },
  { title: "策略实验室", desc: "把观察股票池转换为可复核的策略草稿", to: "/strategy-lab", icon: BarChart3 },
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
              先沉淀客观事件记录，再分析板块热度和候选股票，最后生成可复制到聚宽的策略草稿。
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
              核心研究链路已按“事件记录库”和“板块及股票分析”两层组织，策略输出保持研究与模拟边界。
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
