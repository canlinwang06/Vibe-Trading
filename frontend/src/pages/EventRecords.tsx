import { Link } from "react-router-dom";
import { BarChart3, ClipboardList, ExternalLink, FileText, ShieldCheck } from "lucide-react";

const SUMMARY_CARDS = [
  { label: "事件记录", value: "客观事实", desc: "按时间沉淀事件标题、摘要、发布时间和可交易时间。" },
  { label: "原文证据", value: "可回看", desc: "保留原始链接或本地文档引用，方便回到信息源复核。" },
  { label: "影响跟踪", value: "事后验证", desc: "持续记录事件后对板块和个股的 T+1/T+5/T+20/T+60 影响。" },
  { label: "历史归档", value: "可检索", desc: "支持后续按日、月、季度和年份回看历史事件总结。" },
];

const RESPONSIBILITIES = [
  "只记录事实、来源和事后影响，不直接给买入建议。",
  "将事件、原文证据、板块映射和个股映射放在同一条记录里。",
  "让后续板块及股票分析基于可追溯的历史记录，而不是一次性页面判断。",
];

export function EventRecords() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <ClipboardList className="h-3.5 w-3.5 text-primary" />
          客观记录层
        </div>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
          <div className="space-y-3">
            <h1 className="text-2xl font-semibold tracking-tight">事件记录库</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              用一张清晰的记录表承接每天探索到的事件、来源证据和事后影响，帮助你随时回看某一天发生了什么。
            </p>
          </div>
          <div className="rounded-lg border bg-muted/20 p-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <p className="text-sm font-medium">安全边界</p>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  本页是研究记录，不连接券商、不下单，也不生成实时买卖指令。
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
            <FileText className="h-4 w-4 text-primary" />
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
            原有细分页面仍可作为高级工作台访问，后续会逐步并入事件记录库。
          </p>
          <div className="mt-4 grid gap-2">
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/event-radar">
              事件雷达
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
            <Link className="inline-flex items-center justify-between rounded-md border bg-card px-3 py-2 text-sm hover:border-primary/50" to="/event-reactions">
              事件反应
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
          </div>
        </aside>
      </section>
    </div>
  );
}
