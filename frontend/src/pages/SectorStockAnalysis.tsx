import { Link } from "react-router-dom";
import { BarChart3, ExternalLink, Layers, ShieldCheck, Target } from "lucide-react";

const SUMMARY_CARDS = [
  { label: "热点板块", value: "由事件沉淀得出", desc: "综合历史事件密度、持续性、市场确认和拥挤风险。" },
  { label: "候选股票", value: "建议观察", desc: "从热点板块和事件映射中筛出可复核的股票池。" },
  { label: "推荐理由", value: "可解释", desc: "每只股票都需要能回溯到板块、事件和风险约束。" },
  { label: "策略衔接", value: "可复制", desc: "把确认后的观察池送入策略实验室，再输出聚宽草稿。" },
];

const RESPONSIBILITIES = [
  "基于事件记录库沉淀的数据，判断当前哪些板块正在升温。",
  "在热点板块内筛选建议观察股票，并说明为什么值得进入观察池。",
  "只输出研究和模拟准备结果，不替代你的最终投资判断。",
];

export function SectorStockAnalysis() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Layers className="h-3.5 w-3.5 text-primary" />
          分析决策层
        </div>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
          <div className="space-y-3">
            <h1 className="text-2xl font-semibold tracking-tight">板块及股票分析</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              从历史事件影响中提炼当前热点板块，再结合板块成分和事件映射生成建议观察股票池。
            </p>
          </div>
          <div className="rounded-lg border bg-muted/20 p-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <p className="text-sm font-medium">使用边界</p>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  本页负责研究排序和股票观察池，不在本地执行回测，也不直接连接聚宽账户。
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {SUMMARY_CARDS.map((card) => (
          <article key={card.label} className="rounded-lg border bg-card p-4">
            <p className="text-xs text-muted-foreground">{card.label}</p>
            <h2 className="mt-2 text-lg font-semibold">{card.value}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{card.desc}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">页面职责</h2>
          </div>
          <div className="mt-4 grid gap-3">
            {RESPONSIBILITIES.map((item) => (
              <div key={item} className="rounded-md border bg-background p-3 text-sm leading-6 text-muted-foreground">
                {item}
              </div>
            ))}
          </div>
        </div>

        <aside className="rounded-lg border bg-muted/20 p-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">兼容入口</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            原有分析页面保留给细节检查，后续会作为本页的数据来源和钻取视图。
          </p>
          <div className="mt-4 grid gap-2">
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/sector-radar">
              板块雷达
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/candidate-pool">
              候选股票池
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/strategy-lab">
              策略实验室
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
          </div>
        </aside>
      </section>
    </div>
  );
}
