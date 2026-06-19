import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  ClipboardCopy,
  Download,
  FileCode2,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  ApiError,
  api,
  type JoinQuantCopyPackageResponse,
  type JoinQuantExportRequest,
  type JoinQuantPreflightResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const DEFAULT_RISK_NOTICE = "研究/模拟用途；复制到聚宽后必须人工确认风险，不能直接用于实盘。";

type LoadingAction = "preflight" | "package" | "copy" | null;

type CopyState =
  | { status: "idle"; message: string }
  | { status: "success"; message: string; copiedAt: string }
  | { status: "failed"; message: string };

function todayLabel(): string {
  return new Date().toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "聚宽复制包生成失败，请检查本地服务状态。";
}

function downloadTextFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function ValidationSummary({ validation }: { validation: JoinQuantPreflightResponse["validation"] }) {
  const ready = validation.status === "ok";
  const messages = ready ? validation.warnings : validation.errors;

  return (
    <div className={cn(
      "rounded-lg border p-4",
      ready ? "border-success/30 bg-success/5" : "border-destructive/30 bg-destructive/5",
    )}>
      <div className="flex items-center gap-2">
        {ready ? (
          <CheckCircle2 className="h-4 w-4 text-success" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-destructive" />
        )}
        <p className="text-sm font-semibold">{ready ? "预检查通过" : "预检查阻断"}</p>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-3 text-xs">
        <div>
          <dt className="text-muted-foreground">信号数</dt>
          <dd className="mt-1 font-medium">{validation.checked_count}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">错误</dt>
          <dd className="mt-1 font-medium">{validation.error_count}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">提醒</dt>
          <dd className="mt-1 font-medium">{validation.warning_count}</dd>
        </div>
      </dl>
      {messages.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs leading-5 text-muted-foreground">
          {messages.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function PackageSummary({ copyPackage }: { copyPackage: JoinQuantCopyPackageResponse }) {
  const manifest = copyPackage.manifest;
  const exposure = `${Math.round(manifest.total_exposure * 10000) / 100}%`;

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold">复制包摘要</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {manifest.strategy_id}
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-success/5 px-2.5 py-1 text-xs text-success">
          <ShieldCheck className="h-3.5 w-3.5" />
          仅模拟研究
        </span>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">组合</dt>
          <dd className="mt-1 font-medium">{manifest.portfolio_id}</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">信号日期</dt>
          <dd className="mt-1 font-medium">{manifest.signal_date}</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">有效期</dt>
          <dd className="mt-1 font-medium">{manifest.valid_for || "未提供"}</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">目标仓位</dt>
          <dd className="mt-1 font-medium">{manifest.target_count} 个 / {exposure}</dd>
        </div>
      </dl>

      <div className="mt-4 overflow-hidden rounded-lg border">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/30 text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">文件</th>
              <th className="px-3 py-2 font-medium">类型</th>
              <th className="px-3 py-2 font-medium">大小</th>
            </tr>
          </thead>
          <tbody>
            {manifest.files.map((file) => (
              <tr key={file.filename} className="border-t">
                <td className="px-3 py-2 font-medium text-foreground">{file.filename}</td>
                <td className="px-3 py-2 text-muted-foreground">{file.content_type}</td>
                <td className="px-3 py-2 text-muted-foreground">{file.size} 字符</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function JoinQuantExport() {
  const [portfolioId, setPortfolioId] = useState("cn_a_main");
  const [signalDate, setSignalDate] = useState("");
  const [strategyId, setStrategyId] = useState("");
  const [riskNotice, setRiskNotice] = useState(DEFAULT_RISK_NOTICE);
  const [requireApproved, setRequireApproved] = useState(true);
  const [preflight, setPreflight] = useState<JoinQuantPreflightResponse | null>(null);
  const [copyPackage, setCopyPackage] = useState<JoinQuantCopyPackageResponse | null>(null);
  const [loadingAction, setLoadingAction] = useState<LoadingAction>(null);
  const [error, setError] = useState("");
  const [copyState, setCopyState] = useState<CopyState>({
    status: "idle",
    message: "尚未复制",
  });
  const operationSeq = useRef(0);

  const payload = useMemo<JoinQuantExportRequest>(() => ({
    portfolio_id: portfolioId.trim() || "cn_a_main",
    signal_date: signalDate.trim() || null,
    strategy_id: strategyId.trim() || null,
    risk_notice: riskNotice.trim() || DEFAULT_RISK_NOTICE,
    require_approved: requireApproved,
  }), [portfolioId, requireApproved, riskNotice, signalDate, strategyId]);

  const strategyFile = copyPackage?.files.find((file) => file.filename === "strategy.py");
  const canCopy = Boolean(copyPackage?.copy_ready && copyPackage.clipboard_text);

  function resetExportState() {
    operationSeq.current += 1;
    setPreflight(null);
    setCopyPackage(null);
    setLoadingAction(null);
    setError("");
    setCopyState({ status: "idle", message: "尚未复制" });
  }

  async function runPreflight(): Promise<JoinQuantPreflightResponse | null> {
    const operationId = operationSeq.current + 1;
    operationSeq.current = operationId;
    const requestPayload = payload;
    setLoadingAction("preflight");
    setError("");
    setCopyState({ status: "idle", message: "尚未复制" });
    try {
      const result = await api.joinQuantPreflight(requestPayload);
      if (operationId !== operationSeq.current) return null;
      setPreflight(result);
      if (!result.copy_ready) setCopyPackage(null);
      return result;
    } catch (err) {
      if (operationId !== operationSeq.current) return null;
      setPreflight(null);
      setCopyPackage(null);
      setError(errorMessage(err));
      return null;
    } finally {
      if (operationId === operationSeq.current) setLoadingAction(null);
    }
  }

  async function generatePackage(): Promise<JoinQuantCopyPackageResponse | null> {
    const operationId = operationSeq.current + 1;
    operationSeq.current = operationId;
    const requestPayload = payload;
    setLoadingAction("package");
    setError("");
    setCopyState({ status: "idle", message: "尚未复制" });
    try {
      const checked = await api.joinQuantPreflight(requestPayload);
      if (operationId !== operationSeq.current) return null;
      setPreflight(checked);
      if (!checked.copy_ready) {
        setCopyPackage(null);
        return null;
      }
      const result = await api.joinQuantExportCopyPackage(requestPayload);
      if (operationId !== operationSeq.current) return null;
      setCopyPackage(result);
      return result;
    } catch (err) {
      if (operationId !== operationSeq.current) return null;
      setCopyPackage(null);
      setError(errorMessage(err));
      return null;
    } finally {
      if (operationId === operationSeq.current) setLoadingAction(null);
    }
  }

  async function copyStrategy() {
    if (!copyPackage) return;
    const operationId = operationSeq.current + 1;
    operationSeq.current = operationId;
    const source = copyPackage;
    setLoadingAction("copy");
    setError("");
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("当前浏览器不支持剪贴板写入。");
      }
      await navigator.clipboard.writeText(source.clipboard_text);
      if (operationId !== operationSeq.current) return;
      setCopyState({
        status: "success",
        message: "已复制 strategy.py，可粘贴到聚宽策略编辑器。",
        copiedAt: todayLabel(),
      });
    } catch (err) {
      if (operationId !== operationSeq.current) return;
      setCopyState({
        status: "failed",
        message: errorMessage(err),
      });
    } finally {
      if (operationId === operationSeq.current) setLoadingAction(null);
    }
  }

  function downloadStrategy() {
    if (!strategyFile) return;
    downloadTextFile(strategyFile.filename, strategyFile.content, strategyFile.content_type);
  }

  const preflightReady = preflight?.copy_ready;
  const isBusy = loadingAction !== null;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <header className="space-y-3">
        <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-xs text-muted-foreground">
          <FileCode2 className="h-3.5 w-3.5 text-primary" />
          复制到聚宽模拟运行
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">聚宽导出</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              将已审批的本地 A 股模拟信号生成 JoinQuant 兼容策略代码，并保留人工确认与下载兜底。
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-success" />
            不登录聚宽，不提交订单
          </div>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">导出参数</h2>
            {preflight ? (
              <span className={cn(
                "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs",
                preflightReady
                  ? "border-success/30 bg-success/5 text-success"
                  : "border-destructive/30 bg-destructive/5 text-destructive",
              )}>
                {preflightReady ? "可复制" : "暂不可复制"}
              </span>
            ) : null}
          </div>

          <div className="mt-4 grid gap-4">
            <label className="grid gap-1.5 text-sm">
              <span className="text-xs font-medium text-muted-foreground">组合 ID</span>
              <input
                className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                value={portfolioId}
                onChange={(event) => {
                  setPortfolioId(event.target.value);
                  resetExportState();
                }}
              />
            </label>

            <label className="grid gap-1.5 text-sm">
              <span className="text-xs font-medium text-muted-foreground">信号日期</span>
              <input
                className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                placeholder="留空使用最近 approved 信号"
                type="date"
                value={signalDate}
                onChange={(event) => {
                  setSignalDate(event.target.value);
                  resetExportState();
                }}
              />
            </label>

            <label className="grid gap-1.5 text-sm">
              <span className="text-xs font-medium text-muted-foreground">聚宽策略 ID</span>
              <input
                className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                placeholder="留空自动生成"
                value={strategyId}
                onChange={(event) => {
                  setStrategyId(event.target.value);
                  resetExportState();
                }}
              />
            </label>

            <label className="grid gap-1.5 text-sm">
              <span className="text-xs font-medium text-muted-foreground">风险提示</span>
              <textarea
                className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm leading-6 outline-none transition-colors focus:border-primary"
                value={riskNotice}
                onChange={(event) => {
                  setRiskNotice(event.target.value);
                  resetExportState();
                }}
              />
            </label>

            <label className="flex items-center gap-2 rounded-md border bg-muted/20 px-3 py-2 text-sm">
              <input
                checked={requireApproved}
                className="h-4 w-4 accent-primary"
                type="checkbox"
                onChange={(event) => {
                  setRequireApproved(event.target.checked);
                  resetExportState();
                }}
              />
              <span>仅导出 approved 信号</span>
            </label>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <button
              className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isBusy}
              onClick={runPreflight}
              type="button"
            >
              {loadingAction === "preflight" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              预检查
            </button>
            <button
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isBusy}
              onClick={generatePackage}
              type="button"
            >
              {loadingAction === "package" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileCode2 className="h-4 w-4" />
              )}
              生成复制包
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-lg border bg-card p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-sm font-semibold">复制状态</h2>
                <p className="mt-1 text-xs text-muted-foreground">{copyState.message}</p>
              </div>
              {copyState.status === "success" ? (
                <span className="inline-flex w-fit items-center gap-1.5 rounded-md border border-success/30 bg-success/5 px-2.5 py-1 text-xs text-success">
                  <ClipboardCheck className="h-3.5 w-3.5" />
                  {copyState.copiedAt}
                </span>
              ) : null}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isBusy || !canCopy}
                onClick={copyStrategy}
                type="button"
              >
                {loadingAction === "copy" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ClipboardCopy className="h-4 w-4" />
                )}
                复制策略代码
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!strategyFile}
                onClick={downloadStrategy}
                type="button"
              >
                <Download className="h-4 w-4" />
                下载 strategy.py
              </button>
            </div>

            {copyState.status === "failed" ? (
              <div className="mt-4 rounded-lg border border-warning/30 bg-warning/5 p-3 text-xs leading-5 text-muted-foreground">
                剪贴板写入失败时，请使用下载文件作为兜底。
              </div>
            ) : null}
          </div>

          {preflight ? <ValidationSummary validation={preflight.validation} /> : null}

          {error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm leading-6 text-destructive">
              {error}
            </div>
          ) : null}
        </div>
      </section>

      {copyPackage ? <PackageSummary copyPackage={copyPackage} /> : null}
    </div>
  );
}
