import { useTranslation } from "react-i18next";
import { Bot, TrendingUp, Globe, Sparkles, Users, NotebookPen, Landmark } from "lucide-react";

interface Example {
  title: string;
  desc: string;
  prompt: string;
}

interface Category {
  label: string;
  icon: React.ReactNode;
  color: string;
  examples: Example[];
}

const CATEGORIES: Category[] = [
  {
    label: "A 股研究回测",
    icon: <TrendingUp className="h-4 w-4" />,
    color: "text-red-400 border-red-500/30 hover:border-red-500/60 hover:bg-red-500/5",
    examples: [
      {
        title: "贵州茅台趋势回测",
        desc: "仅使用沪深 A 股日线数据",
        prompt: "为 600519.SH 设计一个只做多、现金账户、无杠杆的均线策略，回测 2024 年并说明数据来源、手续费假设和主要风险。",
      },
      {
        title: "宁德时代事件复盘",
        desc: "产业链事件到交易假设",
        prompt: "研究 300750.SZ 近期新能源产业链事件影响，只输出研究结论和草稿交易计划，不自动下单。",
      },
      {
        title: "银行股防守组合",
        desc: "多标的相关性与回撤约束",
        prompt: "基于 000001.SZ、600036.SH、601398.SH 做只做多组合研究，比较等权和低波动配置，并输出草稿策略。",
      },
    ],
  },
  {
    label: "事件驱动研究",
    icon: <Sparkles className="h-4 w-4" />,
    color: "text-amber-400 border-amber-500/30 hover:border-amber-500/60 hover:bg-amber-500/5",
    examples: [
      {
        title: "AI 产业链研究任务",
        desc: "主题、催化、候选池与风险",
        prompt: "围绕 AI 产业链热点事件，筛选相关 A 股主题、板块和股票候选池，说明催化逻辑、数据来源、风险点和下一步回测方案。",
      },
      {
        title: "政策事件冲击分析",
        desc: "事件窗口与基准对比",
        prompt: "针对最近一项 A 股行业政策事件，定义事件窗口、股票池、基准和持有期，形成可回测的研究假设。",
      },
    ],
  },
  {
    label: "研究协同",
    icon: <Users className="h-4 w-4" />,
    color: "text-violet-400 border-violet-500/30 hover:border-violet-500/60 hover:bg-violet-500/5",
    examples: [
      {
        title: "投研委员会评审",
        desc: "研究员、风控、组合经理协同",
        prompt: "[Swarm Team Mode] 使用投研委员会方式评审 AI 产业链 A 股策略，只讨论研究假设、风险和草稿计划，不触发任何实盘操作。",
      },
      {
        title: "量化策略台",
        desc: "选股、因子、回测、风控串联",
        prompt: "[Swarm Team Mode] 在沪深 A 股范围内设计一个事件驱动策略流水线：候选池、因子、回测、风控和复盘都要给出验收口径。",
      },
    ],
  },
  {
    label: "资料与复盘",
    icon: <Globe className="h-4 w-4" />,
    color: "text-blue-400 border-blue-500/30 hover:border-blue-500/60 hover:bg-blue-500/5",
    examples: [
      {
        title: "研报 PDF 摘要",
        desc: "财务、催化、估值与风险",
        prompt: "总结我上传研报中的关键财务指标、产业催化、估值假设和风险，并转成 A 股事件策略研究要点。",
      },
      {
        title: "宏观事件复盘",
        desc: "只落到 A 股研究口径",
        prompt: "整理最近一项宏观事件对 A 股市场风格、行业轮动和风险偏好的影响，给出可验证的研究假设。",
      },
    ],
  },
  {
    label: "交易日志分析",
    icon: <NotebookPen className="h-4 w-4" />,
    color: "text-orange-400 border-orange-500/30 hover:border-orange-500/60 hover:bg-orange-500/5",
    examples: [
      {
        title: "分析我的交易导出",
        desc: "胜率、持仓天数、盈亏比与行为偏差",
        prompt: "分析我刚上传的 A 股交易日志，输出持仓统计、胜率、盈亏比、常见亏损模式和可改进的研究规则。",
      },
      {
        title: "行为偏差诊断",
        desc: "追涨、过度交易、止损纪律",
        prompt: "基于我的 A 股交易日志诊断行为偏差，按证据强弱排序，并转成下一次回测要验证的规则。",
      },
    ],
  },
  {
    label: "策略草稿交付",
    icon: <Landmark className="h-4 w-4" />,
    color: "text-cyan-400 border-cyan-500/30 hover:border-cyan-500/60 hover:bg-cyan-500/5",
    examples: [
      {
        title: "生成聚宽草稿",
        desc: "便于复制到模拟运行平台",
        prompt: "把 600519.SH 的均线策略整理成可复制到聚宽模拟环境的策略草稿，包含参数、股票池、风控和回测假设，不进行实盘下单。",
      },
      {
        title: "策略验收清单",
        desc: "上线前的研究检查项",
        prompt: "为当前 A 股事件策略生成验收清单：数据、股票池、交易成本、风险约束、复制到聚宽前检查项和自动测试用例。",
      },
    ],
  },
];

const CAPABILITY_CHIPS = [
  "A 股事件研究",
  "沪深股票代码",
  "只做多",
  "现金账户",
  "交易计划草稿",
  "本地回测",
  "Codex 协同",
  "因子分析",
  "风险指标",
  "PDF 与网页研究",
  "交易日志分析",
  "聚宽复制准备",
  "持久记忆",
  "会话检索",
];

interface Props {
  onExample: (s: string) => void;
}

export function WelcomeScreen({ onExample }: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8 text-center">
      {/* Header */}
      <div className="space-y-3">
        <div className="h-16 w-16 mx-auto rounded-2xl bg-gradient-to-br from-primary/80 to-info/80 flex items-center justify-center shadow-lg">
          <Bot className="h-8 w-8 text-white" />
        </div>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{t('welcome.title')}</h2>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto leading-relaxed">
            Codex 驱动的本地 A 股研究、回测与策略草稿工作台
          </p>
          <p className="text-sm text-muted-foreground mt-2 max-w-md leading-relaxed mx-auto">
            输入一个 A 股研究任务即可开始。
          </p>
        </div>
      </div>

      {/* Capability chips */}
      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {CAPABILITY_CHIPS.map((chip) => (
          <span
            key={chip}
            className="px-2.5 py-1 text-xs rounded-full border border-border/60 text-muted-foreground bg-muted/30"
          >
            {chip}
          </span>
        ))}
      </div>

      {/* Example categories grid */}
      <div className="w-full max-w-2xl text-left space-y-4">
        <p className="text-xs text-muted-foreground px-1">{t('welcome.tryExample')}</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {CATEGORIES.map((cat) => (
            <div key={cat.label} className="space-y-2">
              <div className={`flex items-center gap-1.5 text-xs font-medium px-1 ${cat.color.split(" ").filter(c => c.startsWith("text-")).join(" ")}`}>
                {cat.icon}
                <span>{cat.label}</span>
              </div>
              <div className="space-y-1.5">
                {cat.examples.map((ex) => (
                  <button
                    key={ex.title}
                    onClick={() => onExample(ex.prompt)}
                    className={`block w-full text-left px-3 py-2.5 rounded-xl border transition-colors ${cat.color}`}
                  >
                    <span className="text-sm font-medium text-foreground leading-snug">
                      {ex.title}
                    </span>
                    <span className="block text-xs text-muted-foreground mt-0.5 leading-snug">
                      {ex.desc}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
