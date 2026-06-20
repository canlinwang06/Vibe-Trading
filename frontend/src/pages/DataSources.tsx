import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  CheckCircle2,
  Database,
  FileInput,
  KeyRound,
  Loader2,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { api, type DataSourceSettings } from "@/lib/api";
import { cn } from "@/lib/utils";

const fieldClass =
  "w-full rounded-md border bg-background px-3 py-2 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60";
const labelClass = "text-sm font-medium";
const hintClass = "text-xs leading-5 text-muted-foreground";

type SourceTone = "ready" | "optional" | "blocked";

interface SourceCardProps {
  title: string;
  description: string;
  status: string;
  detail: string;
  tone: SourceTone;
  icon: typeof Database;
}

function statusTone(tone: SourceTone): string {
  if (tone === "ready") return "border-success/30 bg-success/5 text-success";
  if (tone === "blocked") return "border-destructive/30 bg-destructive/5 text-destructive";
  return "border-warning/30 bg-warning/5 text-warning";
}

function SourceCard({ title, description, status, detail, tone, icon: Icon }: SourceCardProps) {
  return (
    <article className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="rounded-md border bg-muted/30 p-2">
            <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">{title}</h2>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
          </div>
        </div>
        <span className={cn("shrink-0 rounded-md border px-2 py-1 text-xs font-medium", statusTone(tone))}>
          {status}
        </span>
      </div>
      <p className="mt-4 border-l pl-3 text-xs leading-5 text-muted-foreground">{detail}</p>
    </article>
  );
}

function SettingsSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex min-h-28 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在读取本地数据源状态...
      </div>
    </div>
  );
}

export function DataSources() {
  const [settings, setSettings] = useState<DataSourceSettings | null>(null);
  const [tushareToken, setTushareToken] = useState("");
  const [clearTushareToken, setClearTushareToken] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getDataSourceSettings();
      setSettings(data);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "数据源状态加载失败，请检查本地服务。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const tushareStatus = settings?.tushare_token_configured ? "已配置" : "未配置";
  const tushareHint = settings?.tushare_token_hint || "页面不会回显 token 明文；留空提交会保留当前配置。";

  const sourceCards = useMemo<SourceCardProps[]>(() => {
    const baostockReady = Boolean(settings?.baostock_supported);
    return [
      {
        title: "Tushare",
        description: "用于更完整的 A 股、基金和宏观数据补充。",
        status: settings?.tushare_token_configured ? "已配置" : "可选",
        detail: settings?.tushare_token_configured
          ? "本地环境已保存 token，后端可在需要时读取。"
          : "未配置时，系统仍会优先走免费或本地数据源。",
        tone: settings?.tushare_token_configured ? "ready" : "optional",
        icon: KeyRound,
      },
      {
        title: "AKShare",
        description: "默认优先的免费 A 股数据入口，适合日常研究和样例回测。",
        status: "免费优先",
        detail: "不需要额外模型费用；数据可用性取决于本地 Python 环境和公开源稳定性。",
        tone: "ready",
        icon: Sparkles,
      },
      {
        title: "BaoStock",
        description: "用于补充历史行情和基础字段，适合作为第二免费源。",
        status: baostockReady ? "加载器可用" : "待接入",
        detail: settings?.baostock_message || "当前后端未返回 BaoStock 状态。",
        tone: baostockReady ? "ready" : "optional",
        icon: Database,
      },
      {
        title: "本地数据桥",
        description: "承接 CSV、JSON、研究报告和人工整理文件。",
        status: "本地优先",
        detail: "适合把外部整理资料导入工作流，避免把敏感凭据写入前端代码或提交记录。",
        tone: "ready",
        icon: FileInput,
      },
    ];
  }, [settings]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setSaveMessage(null);
    setSaveError(null);
    try {
      const updated = await api.updateDataSourceSettings({
        tushare_token: tushareToken.trim() || undefined,
        clear_tushare_token: clearTushareToken,
      });
      setSettings(updated);
      setTushareToken("");
      setClearTushareToken(false);
      setSaveMessage("数据源设置已保存。");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "数据源设置保存失败，请检查本地服务。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="space-y-3">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Database className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          <span>A 股数据源与本地缓存</span>
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">数据源设置</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              集中管理 A 股研究和回测的数据入口。默认走免费或本地数据源，Tushare 仅在你主动配置后作为补充。
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadSettings()}
            disabled={loading}
            className="inline-flex w-fit items-center gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            刷新状态
          </button>
        </div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Tushare token</p>
          <p className="mt-2 text-lg font-semibold">{tushareStatus}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">BaoStock</p>
          <p className="mt-2 text-lg font-semibold">{settings?.baostock_supported ? "可用" : "待接入"}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">数据策略</p>
          <p className="mt-2 text-lg font-semibold">免费 / 本地优先</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">交易边界</p>
          <p className="mt-2 text-lg font-semibold">研究模拟</p>
        </div>
      </section>

      {loading && !settings ? <SettingsSkeleton /> : null}

      {loadError ? (
        <section className="rounded-lg border border-destructive/30 bg-destructive/5 p-5">
          <div className="flex items-start gap-3">
            <TriangleAlert className="mt-0.5 h-4 w-4 text-destructive" aria-hidden="true" />
            <div>
              <h2 className="text-sm font-semibold">数据源状态暂不可用</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">{loadError}</p>
            </div>
          </div>
        </section>
      ) : null}

      {settings ? (
        <>
          <section className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
            <form onSubmit={submit} className="rounded-lg border bg-card p-5">
              <div className="mb-5 flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <KeyRound className="h-4 w-4 text-primary" aria-hidden="true" />
                    <h2 className="text-base font-semibold">凭据管理</h2>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">只管理本地数据源凭据，不配置模型密钥。</p>
                </div>
                <span className={cn(
                  "shrink-0 rounded-md border px-2 py-1 text-xs font-medium",
                  settings.tushare_token_configured
                    ? "border-success/30 bg-success/5 text-success"
                    : "border-warning/30 bg-warning/5 text-warning",
                )}>
                  {settings.tushare_token_configured ? "当前已保存" : "当前未保存"}
                </span>
              </div>

              <div className="grid gap-4">
                <label className="grid gap-2">
                  <span className={labelClass}>Tushare token</span>
                  <input
                    type="password"
                    aria-label="Tushare token"
                    value={tushareToken}
                    onChange={(event) => setTushareToken(event.target.value)}
                    className={fieldClass}
                    placeholder={settings.tushare_token_configured ? "留空以保留当前 token" : "可选，仅在你已有 Tushare token 时填写"}
                    autoComplete="current-password"
                    disabled={clearTushareToken}
                  />
                  <span className={hintClass}>{tushareHint}</span>
                </label>

                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={clearTushareToken}
                    onChange={(event) => {
                      setClearTushareToken(event.target.checked);
                      if (event.target.checked) setTushareToken("");
                    }}
                    className="h-3.5 w-3.5 accent-primary"
                  />
                  清除已保存的 Tushare token
                </label>

                <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">保存路径: </span>
                  <span className="break-all font-mono">{settings.env_path}</span>
                </div>

                {saveMessage ? (
                  <div className="flex items-center gap-2 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-xs text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    {saveMessage}
                  </div>
                ) : null}
                {saveError ? (
                  <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                    <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
                    {saveError}
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  {saving ? "保存中..." : "保存数据源设置"}
                </button>
              </div>
            </form>

            <aside className="rounded-lg border bg-card p-5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
                <h2 className="text-base font-semibold">安全边界</h2>
              </div>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                <li>页面不会显示已保存 token 的明文。</li>
                <li>凭据只用于本地后端读取，不写入前端代码、报告或 PR 文档。</li>
                <li>所有流程默认研究和模拟，不触发实盘交易。</li>
                <li>模型调用沿用 Codex 登录态，不要求新增模型 API 凭据。</li>
              </ul>
            </aside>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            {sourceCards.map((source) => (
              <SourceCard key={source.title} {...source} />
            ))}
          </section>
        </>
      ) : null}
    </div>
  );
}
