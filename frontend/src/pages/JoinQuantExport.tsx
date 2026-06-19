import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  ClipboardCopy,
  Download,
  FileCode2,
  FileSearch,
  Gauge,
  ListChecks,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Upload,
} from "lucide-react";
import {
  ApiError,
  api,
  type JoinQuantCopyPackageResponse,
  type JoinQuantExecutionReport,
  type JoinQuantExecutionReportSummary,
  type JoinQuantExportRequest,
  type JoinQuantPreflightResponse,
  type JoinQuantSimulationReadinessReport,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const DEFAULT_RISK_NOTICE = "研究/模拟用途；复制到聚宽后必须人工确认风险，不能直接用于实盘。";
const DEFAULT_REPORT_JSON = JSON.stringify(
  [
    {
      ticker: "600519.XSHG",
      order_status: "filled",
      executed_weight: 0.08,
      fill_price: 1688.5,
      fill_amount: 8000,
    },
    {
      ticker: "300750.XSHE",
      order_status: "filled",
      executed_weight: 0.07,
    },
  ],
  null,
  2,
);

type LoadingAction = "preflight" | "package" | "copy" | null;
type ReportAction = "import" | "summary" | null;
type ReadinessAction = "readiness" | null;

type CopyState =
  | { status: "idle"; message: string }
  | { status: "success"; message: string; copiedAt: string }
  | { status: "failed"; message: string };

type ReportState =
  | { status: "idle"; message: string }
  | { status: "success"; message: string }
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
  return "聚宽操作失败，请检查本地服务状态。";
}

function formatPercent(value: number | null | undefined): string {
  const numeric = Number(value || 0);
  return `${Math.round(numeric * 10000) / 100}%`;
}

function parseReportRows(value: string): Record<string, unknown>[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error("报告 JSON 格式无效，请粘贴 JSON 数组或包含 reports 的对象。");
  }
  if (Array.isArray(parsed)) return parsed as Record<string, unknown>[];
  if (
    parsed
    && typeof parsed === "object"
    && Array.isArray((parsed as { reports?: unknown }).reports)
  ) {
    return (parsed as { reports: Record<string, unknown>[] }).reports;
  }
  throw new Error("报告 JSON 必须是数组，或包含 reports 数组的对象。");
}

function parseBoundedNumber(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须在 ${min} 到 ${max} 之间。`);
  }
  return parsed;
}

function parseBoundedInteger(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label}必须是 ${min} 到 ${max} 之间的整数。`);
  }
  return parsed;
}

function readinessStatusLabel(status: string): string {
  if (status === "ready") return "准备度通过";
  if (status === "ok") return "通过";
  if (status === "needs_more_data") return "继续观察";
  if (status === "needs_review") return "需要复盘";
  return status;
}

function recommendationLabel(recommendation: string): string {
  if (recommendation === "continue_simulation") return "继续模拟观察";
  if (recommendation === "extend_observation") return "延长观察窗口";
  if (recommendation === "fix_before_live") return "修复后再评估";
  return recommendation;
}

function checkStatusLabel(status: string): string {
  if (status === "pass") return "通过";
  if (status === "warning") return "提醒";
  if (status === "fail") return "阻断";
  return status;
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

function packageArchiveFilename(copyPackage: JoinQuantCopyPackageResponse): string {
  return `${copyPackage.manifest.strategy_id}_${copyPackage.manifest.signal_date}_copy_package.json`;
}

function packageArchiveContent(copyPackage: JoinQuantCopyPackageResponse): string {
  return JSON.stringify({
    generated_by: "Vibe-Trading",
    package_type: "joinquant-local-copy-package",
    manifest: copyPackage.manifest,
    validation: copyPackage.validation,
    files: copyPackage.files.map((file) => ({
      filename: file.filename,
      content_type: file.content_type,
      content: file.content,
      size: file.content.length,
    })),
    guardrails: {
      local_download_only: true,
      opens_joinquant: false,
      submits_orders: false,
      live_trading: false,
    },
  }, null, 2);
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

function CopyPackageArchive({ copyPackage }: { copyPackage: JoinQuantCopyPackageResponse }) {
  const archiveFilename = packageArchiveFilename(copyPackage);
  const archiveContent = packageArchiveContent(copyPackage);
  const totalSize = copyPackage.files.reduce((sum, file) => sum + file.content.length, 0);

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Download className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">复制包清单</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            将策略代码、信号文件、说明文档和校验清单打包为一个本地 JSON 文件，便于归档和转移。
          </p>
        </div>
        <button
          className="inline-flex w-fit items-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          onClick={() => downloadTextFile(archiveFilename, archiveContent, "application/json")}
          type="button"
        >
          <Download className="h-3.5 w-3.5" />
          下载完整复制包
        </button>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">文件数</dt>
          <dd className="mt-1 font-medium">{copyPackage.files.length}</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">内容大小</dt>
          <dd className="mt-1 font-medium">{totalSize} 字符</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">清单文件</dt>
          <dd className="mt-1 font-medium">{archiveFilename}</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">边界</dt>
          <dd className="mt-1 font-medium">本地下载 / 不提交</dd>
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
            {copyPackage.files.map((file) => (
              <tr key={file.filename} className="border-t">
                <td className="px-3 py-2 font-medium text-foreground">{file.filename}</td>
                <td className="px-3 py-2 text-muted-foreground">{file.content_type}</td>
                <td className="px-3 py-2 text-muted-foreground">{file.content.length} 字符</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
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

function CopyReviewPanel({
  copyPackage,
  copyState,
  requireApproved,
  riskNotice,
}: {
  copyPackage: JoinQuantCopyPackageResponse;
  copyState: CopyState;
  requireApproved: boolean;
  riskNotice: string;
}) {
  const manifest = copyPackage.manifest;
  const strategyFile = copyPackage.files.find((file) => file.filename === "strategy.py");
  const reviewItems = [
    {
      label: "代码映射检查",
      value: copyPackage.validation.status === "ok" ? "通过" : "未通过",
    },
    {
      label: "基础语法检查",
      value: strategyFile ? "已生成 Python 策略文件" : "缺少 strategy.py",
    },
    {
      label: "信号有效期检查",
      value: manifest.valid_for || "未提供",
    },
    {
      label: "导出状态限制",
      value: requireApproved ? "仅 approved 信号" : "允许研究草案",
    },
  ];

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">复制前审阅</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            复制到聚宽前，先确认策略、目标持仓来源、校验结果和风险提示。
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-muted/20 px-2.5 py-1 text-xs text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5 text-success" />
          人工复制
        </span>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">策略名称</dt>
          <dd className="mt-1 font-medium">{manifest.strategy_id}</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">股票池</dt>
          <dd className="mt-1 font-medium">已映射目标 {manifest.target_count} 只</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">回测区间 / 信号窗口</dt>
          <dd className="mt-1 font-medium">{manifest.signal_date} 至 {manifest.valid_for}</dd>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <dt className="text-xs text-muted-foreground">目标持仓来源</dt>
          <dd className="mt-1 font-medium">本地 execution_signals / {manifest.portfolio_id}</dd>
        </div>
      </dl>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {reviewItems.map((item) => (
          <div key={item.label} className="rounded-lg border bg-background p-3">
            <p className="text-xs text-muted-foreground">{item.label}</p>
            <p className="mt-1 text-sm font-medium">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-3 text-xs md:grid-cols-2">
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium text-foreground">风险提示</p>
          <p className="mt-2 leading-5 text-muted-foreground">{riskNotice || DEFAULT_RISK_NOTICE}</p>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium text-foreground">复制内容摘要和校验结果</p>
          <p className="mt-2 leading-5 text-muted-foreground">
            strategy.py {strategyFile?.content.length ?? 0} 字符，信号 {copyPackage.validation.checked_count} 条，
            错误 {copyPackage.validation.error_count} 个，提醒 {copyPackage.validation.warning_count} 个。
          </p>
          <p className="mt-2 leading-5 text-muted-foreground">
            最近复制时间：{copyState.status === "success" ? copyState.copiedAt : "尚未复制"}
          </p>
          <p className="mt-2 leading-5 text-muted-foreground">
            兜底下载：Download Python Strategy
          </p>
        </div>
      </div>
    </section>
  );
}

function SignalFilePreview({ copyPackage }: { copyPackage: JoinQuantCopyPackageResponse }) {
  const signalFiles = copyPackage.files.filter((file) =>
    file.filename === "signals.json" || file.filename === "signals.csv",
  );

  if (!signalFiles.length) {
    return null;
  }

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <FileCode2 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">信号文件预览</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            下载 JoinQuant 兼容的 signals JSON/CSV，用于模拟策略读取，不直接连接聚宽账户。
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-muted/20 px-2.5 py-1 text-xs text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5 text-success" />
          本地文件
        </span>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {signalFiles.map((file) => (
          <div key={file.filename} className="rounded-lg border bg-background p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold">{file.filename === "signals.json" ? "导出信号 JSON" : "导出信号 CSV"}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {file.filename} / {file.content_type} / {file.content.length} 字符
                </p>
              </div>
              <button
                className="inline-flex w-fit items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs font-medium transition-colors hover:bg-muted"
                onClick={() => downloadTextFile(file.filename, file.content, file.content_type)}
                type="button"
              >
                <Download className="h-3.5 w-3.5" />
                下载 {file.filename}
              </button>
            </div>
            <pre className="mt-4 max-h-56 overflow-auto rounded-md border bg-muted/20 p-3 text-xs leading-5 text-muted-foreground">
              {file.content}
            </pre>
          </div>
        ))}
      </div>
    </section>
  );
}

function ExecutionSummaryPanel({ summary }: { summary: JoinQuantExecutionReportSummary }) {
  const needsReview = summary.status !== "ok" || summary.action_required;
  const metrics = [
    { label: "报告数", value: String(summary.report_count) },
    { label: "匹配信号", value: `${summary.matched_signal_count}/${summary.signal_count}` },
    { label: "失败订单", value: String(summary.failed_count) },
    { label: "最大偏差", value: formatPercent(summary.max_abs_weight_diff) },
  ];

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold">执行复盘摘要</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {summary.portfolio_id} / {summary.signal_date} / {summary.trade_date}
          </p>
        </div>
        <span className={cn(
          "inline-flex w-fit items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs",
          needsReview
            ? "border-warning/30 bg-warning/5 text-warning"
            : "border-success/30 bg-success/5 text-success",
        )}>
          {needsReview ? <AlertTriangle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
          {needsReview ? "需要复盘" : "执行匹配"}
        </span>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((item) => (
          <div key={item.label} className="rounded-lg border bg-muted/20 p-3">
            <dt className="text-xs text-muted-foreground">{item.label}</dt>
            <dd className="mt-1 font-medium">{item.value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 grid gap-3 text-xs md:grid-cols-2">
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium text-foreground">状态分布</p>
          <p className="mt-2 leading-5 text-muted-foreground">
            {Object.entries(summary.status_counts).length > 0
              ? Object.entries(summary.status_counts).map(([key, value]) => `${key}: ${value}`).join(" / ")
              : "暂无状态统计"}
          </p>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium text-foreground">异常项</p>
          <p className="mt-2 leading-5 text-muted-foreground">
            未匹配 {summary.unmatched_report_count} 个，缺失 {summary.missing_report_count} 个，总偏差 {formatPercent(summary.total_abs_weight_diff)}
          </p>
        </div>
      </div>

      {summary.deviations.length > 0 ? (
        <div className="mt-4 overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">股票</th>
                <th className="px-3 py-2 font-medium">计划</th>
                <th className="px-3 py-2 font-medium">执行</th>
                <th className="px-3 py-2 font-medium">偏差</th>
                <th className="px-3 py-2 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {summary.deviations.map((row) => (
                <tr key={row.ticker} className={cn("border-t", row.needs_review ? "bg-warning/5" : "")}>
                  <td className="px-3 py-2 font-medium text-foreground">{row.ticker}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.planned_weight)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.executed_weight)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.abs_weight_diff)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.order_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-4 rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
          暂无偏差明细。
        </div>
      )}
    </section>
  );
}

function ExecutionReportTable({ reports }: { reports: JoinQuantExecutionReport[] }) {
  if (reports.length === 0) return null;

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center gap-2">
        <ListChecks className="h-4 w-4 text-primary" />
        <p className="text-sm font-semibold">最近导入报告</p>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg border">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/30 text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">股票</th>
              <th className="px-3 py-2 font-medium">信号日</th>
              <th className="px-3 py-2 font-medium">交易日</th>
              <th className="px-3 py-2 font-medium">计划仓位</th>
              <th className="px-3 py-2 font-medium">执行仓位</th>
              <th className="px-3 py-2 font-medium">状态</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((row) => (
              <tr key={row.report_id} className="border-t">
                <td className="px-3 py-2 font-medium text-foreground">{row.ticker}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.signal_date}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.trade_date}</td>
                <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.planned_weight)}</td>
                <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.executed_weight)}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.order_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReadinessReportPanel({ report }: { report: JoinQuantSimulationReadinessReport }) {
  const statusTone = report.status === "ready"
    ? "border-success/30 bg-success/5 text-success"
    : report.status === "needs_review"
      ? "border-destructive/30 bg-destructive/5 text-destructive"
      : "border-warning/30 bg-warning/5 text-warning";
  const metrics = [
    { label: "准备度分数", value: String(report.readiness_score) },
    { label: "观察批次", value: `${report.observed_batch_count}/${report.min_batches}` },
    { label: "失败订单", value: String(report.totals.failed_count) },
    { label: "最大偏差", value: formatPercent(report.totals.max_abs_weight_diff) },
    { label: "缺失回报", value: String(report.totals.missing_report_count) },
    { label: "最大延迟", value: `${report.totals.max_signal_delay_days} 天` },
    { label: "涨跌停/停牌", value: String(report.totals.limit_or_suspend_issue_count) },
    { label: "最差回撤", value: formatPercent(Math.abs(report.backtest_risk.worst_max_drawdown)) },
  ];

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold">模拟盘准备度报告</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {report.portfolio_id} / {report.window_start} 至 {report.window_end}
          </p>
        </div>
        <span className={cn("inline-flex w-fit items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs", statusTone)}>
          {report.status === "ready" ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
          {readinessStatusLabel(report.status)}
        </span>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((item) => (
          <div key={item.label} className="rounded-lg border bg-muted/20 p-3">
            <dt className="text-xs text-muted-foreground">{item.label}</dt>
            <dd className="mt-1 font-medium">{item.value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 grid gap-3 text-xs md:grid-cols-2">
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium text-foreground">建议</p>
          <p className="mt-2 leading-5 text-muted-foreground">
            {recommendationLabel(report.recommendation)}
          </p>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="font-medium text-foreground">执行率</p>
          <p className="mt-2 leading-5 text-muted-foreground">
            失败 {formatPercent(report.rates.failed_rate)} / 缺失 {formatPercent(report.rates.missing_report_rate)} / 偏差 {formatPercent(report.rates.deviation_rate)}
          </p>
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded-lg border">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/30 text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">检查项</th>
              <th className="px-3 py-2 font-medium">状态</th>
              <th className="px-3 py-2 font-medium">结果</th>
            </tr>
          </thead>
          <tbody>
            {report.checks.map((check) => (
              <tr key={check.name} className="border-t">
                <td className="px-3 py-2 font-medium text-foreground">{check.name}</td>
                <td className="px-3 py-2 text-muted-foreground">{checkStatusLabel(check.status)}</td>
                <td className="px-3 py-2 text-muted-foreground">{check.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 rounded-lg border bg-muted/20 p-3 text-xs leading-5 text-muted-foreground">
        <p className="font-medium text-foreground">发现</p>
        <ul className="mt-2 space-y-1">
          {report.findings.map((finding) => (
            <li key={finding}>{finding}</li>
          ))}
        </ul>
      </div>

      {report.daily_summaries.length > 0 ? (
        <div className="mt-4 overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">信号日</th>
                <th className="px-3 py-2 font-medium">交易日</th>
                <th className="px-3 py-2 font-medium">报告</th>
                <th className="px-3 py-2 font-medium">失败</th>
                <th className="px-3 py-2 font-medium">偏差</th>
                <th className="px-3 py-2 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {report.daily_summaries.map((row) => (
                <tr key={`${row.signal_date}-${row.trade_date}`} className="border-t">
                  <td className="px-3 py-2 font-medium text-foreground">{row.signal_date}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.trade_date}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.report_count}/{row.signal_count}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.failed_count}</td>
                  <td className="px-3 py-2 text-muted-foreground">{formatPercent(row.max_abs_weight_diff)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{readinessStatusLabel(row.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
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
  const [reportPortfolioId, setReportPortfolioId] = useState("cn_a_main");
  const [reportSignalDate, setReportSignalDate] = useState("");
  const [reportTradeDate, setReportTradeDate] = useState("");
  const [reportTolerance, setReportTolerance] = useState("0.01");
  const [reportReplace, setReportReplace] = useState(false);
  const [reportJson, setReportJson] = useState(DEFAULT_REPORT_JSON);
  const [reportAction, setReportAction] = useState<ReportAction>(null);
  const [reportState, setReportState] = useState<ReportState>({
    status: "idle",
    message: "尚未导入报告",
  });
  const [reportError, setReportError] = useState("");
  const [reportSummary, setReportSummary] = useState<JoinQuantExecutionReportSummary | null>(null);
  const [reportRows, setReportRows] = useState<JoinQuantExecutionReport[]>([]);
  const [readinessPortfolioId, setReadinessPortfolioId] = useState("cn_a_main");
  const [readinessLookbackDays, setReadinessLookbackDays] = useState("90");
  const [readinessMinBatches, setReadinessMinBatches] = useState("20");
  const [readinessTolerance, setReadinessTolerance] = useState("0.01");
  const [readinessAction, setReadinessAction] = useState<ReadinessAction>(null);
  const [readinessState, setReadinessState] = useState<ReportState>({
    status: "idle",
    message: "尚未生成准备度报告",
  });
  const [readinessError, setReadinessError] = useState("");
  const [readinessReport, setReadinessReport] = useState<JoinQuantSimulationReadinessReport | null>(null);
  const operationSeq = useRef(0);
  const reportSeq = useRef(0);
  const readinessSeq = useRef(0);

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

  function reportQuery() {
    return {
      portfolio_id: reportPortfolioId.trim() || "cn_a_main",
      signal_date: reportSignalDate.trim() || null,
      trade_date: reportTradeDate.trim() || null,
    };
  }

  function parsedTolerance(): number {
    const value = Number(reportTolerance);
    if (!Number.isFinite(value) || value < 0 || value > 1) {
      throw new Error("偏差容忍度必须是 0 到 1 之间的小数。");
    }
    return value;
  }

  async function importReports() {
    const operationId = reportSeq.current + 1;
    reportSeq.current = operationId;
    setReportAction("import");
    setReportError("");
    try {
      const rows = parseReportRows(reportJson);
      const query = reportQuery();
      const result = await api.joinQuantImportExecutionReports({
        ...query,
        replace: reportReplace,
        reports: rows,
      });
      if (operationId !== reportSeq.current) return;
      setReportRows(result.reports);
      setReportSummary(result.summary);
      setReportState({
        status: "success",
        message: `已导入 ${result.imported_count} 条聚宽报告。`,
      });
    } catch (err) {
      if (operationId !== reportSeq.current) return;
      setReportState({ status: "failed", message: "导入失败" });
      setReportError(errorMessage(err));
    } finally {
      if (operationId === reportSeq.current) setReportAction(null);
    }
  }

  async function refreshExecutionSummary() {
    const operationId = reportSeq.current + 1;
    reportSeq.current = operationId;
    setReportAction("summary");
    setReportError("");
    try {
      const query = reportQuery();
      const tolerance = parsedTolerance();
      const [summary, list] = await Promise.all([
        api.joinQuantExecutionReportSummary({ ...query, tolerance }),
        api.joinQuantListExecutionReports({ ...query, limit: 200 }),
      ]);
      if (operationId !== reportSeq.current) return;
      setReportSummary(summary);
      setReportRows(list.reports);
      setReportState({
        status: "success",
        message: `已加载 ${summary.report_count} 条报告的复盘摘要。`,
      });
    } catch (err) {
      if (operationId !== reportSeq.current) return;
      setReportState({ status: "failed", message: "查询失败" });
      setReportError(errorMessage(err));
    } finally {
      if (operationId === reportSeq.current) setReportAction(null);
    }
  }

  function readinessQuery() {
    return {
      portfolio_id: readinessPortfolioId.trim() || "cn_a_main",
      lookback_days: parseBoundedInteger(readinessLookbackDays, "观察天数", 1, 365),
      min_batches: parseBoundedInteger(readinessMinBatches, "最低批次", 1, 250),
      tolerance: parseBoundedNumber(readinessTolerance, "偏差容忍度", 0, 1),
    };
  }

  async function generateReadinessReport() {
    const operationId = readinessSeq.current + 1;
    readinessSeq.current = operationId;
    setReadinessAction("readiness");
    setReadinessError("");
    try {
      const result = await api.joinQuantSimulationReadiness(readinessQuery());
      if (operationId !== readinessSeq.current) return;
      setReadinessReport(result);
      setReadinessState({
        status: result.status === "ready" ? "success" : "failed",
        message: `准备度结论：${readinessStatusLabel(result.status)}。`,
      });
    } catch (err) {
      if (operationId !== readinessSeq.current) return;
      setReadinessState({ status: "failed", message: "准备度报告生成失败" });
      setReadinessError(errorMessage(err));
    } finally {
      if (operationId === readinessSeq.current) setReadinessAction(null);
    }
  }

  const preflightReady = preflight?.copy_ready;
  const isBusy = loadingAction !== null;
  const reportBusy = reportAction !== null;
  const readinessBusy = readinessAction !== null;

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

          {copyPackage ? (
            <CopyReviewPanel
              copyPackage={copyPackage}
              copyState={copyState}
              requireApproved={requireApproved}
              riskNotice={riskNotice}
            />
          ) : null}

          {error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm leading-6 text-destructive">
              {error}
            </div>
          ) : null}
        </div>
      </section>

      {copyPackage ? <PackageSummary copyPackage={copyPackage} /> : null}
      {copyPackage ? <CopyPackageArchive copyPackage={copyPackage} /> : null}
      {copyPackage ? <SignalFilePreview copyPackage={copyPackage} /> : null}

      <section className="rounded-lg border bg-card p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Upload className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">执行报告导入</h2>
            </div>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-muted-foreground">
              将聚宽回测或模拟盘导出的执行结果粘贴为 JSON，系统会写入本地复盘表并对比目标仓位、失败订单和偏差。
            </p>
          </div>
          <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-muted/20 px-2.5 py-1 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-success" />
            只导入本地报告
          </span>
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,0.45fr)_minmax(0,0.55fr)]">
          <div className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-1.5 text-sm">
                <span className="text-xs font-medium text-muted-foreground">报告组合 ID</span>
                <input
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                  value={reportPortfolioId}
                  onChange={(event) => setReportPortfolioId(event.target.value)}
                />
              </label>

              <label className="grid gap-1.5 text-sm">
                <span className="text-xs font-medium text-muted-foreground">偏差容忍度</span>
                <input
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                  inputMode="decimal"
                  value={reportTolerance}
                  onChange={(event) => setReportTolerance(event.target.value)}
                />
              </label>

              <label className="grid gap-1.5 text-sm">
                <span className="text-xs font-medium text-muted-foreground">报告信号日期</span>
                <input
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                  placeholder="留空使用报告内日期"
                  type="date"
                  value={reportSignalDate}
                  onChange={(event) => setReportSignalDate(event.target.value)}
                />
              </label>

              <label className="grid gap-1.5 text-sm">
                <span className="text-xs font-medium text-muted-foreground">报告交易日</span>
                <input
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                  placeholder="留空使用报告内日期"
                  type="date"
                  value={reportTradeDate}
                  onChange={(event) => setReportTradeDate(event.target.value)}
                />
              </label>
            </div>

            <label className="flex items-center gap-2 rounded-md border bg-muted/20 px-3 py-2 text-sm">
              <input
                checked={reportReplace}
                className="h-4 w-4 accent-primary"
                type="checkbox"
                onChange={(event) => setReportReplace(event.target.checked)}
              />
              <span>覆盖同一批次已有报告</span>
            </label>

            <div className={cn(
              "rounded-lg border p-3 text-xs leading-5",
              reportState.status === "failed"
                ? "border-destructive/30 bg-destructive/5 text-destructive"
                : "bg-muted/20 text-muted-foreground",
            )}>
              <p className="font-medium text-foreground">{reportState.message}</p>
              {reportError ? <p className="mt-1">{reportError}</p> : null}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={reportBusy}
                onClick={importReports}
                type="button"
              >
                {reportAction === "import" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                导入报告
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                disabled={reportBusy}
                onClick={refreshExecutionSummary}
                type="button"
              >
                {reportAction === "summary" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileSearch className="h-4 w-4" />
                )}
                查询复盘
              </button>
            </div>
          </div>

          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">报告 JSON</span>
            <textarea
              className="min-h-80 rounded-md border bg-background px-3 py-2 font-mono text-xs leading-5 outline-none transition-colors focus:border-primary"
              value={reportJson}
              onChange={(event) => setReportJson(event.target.value)}
              spellCheck={false}
            />
          </label>
        </div>
      </section>

      {reportSummary ? <ExecutionSummaryPanel summary={reportSummary} /> : null}
      <ExecutionReportTable reports={reportRows} />

      <section className="rounded-lg border bg-card p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">模拟盘准备度</h2>
            </div>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-muted-foreground">
              汇总最近聚宽模拟执行、回报缺失、仓位偏差、信号延迟和回测回撤证据。
            </p>
          </div>
          <span className="inline-flex w-fit items-center gap-1.5 rounded-md border bg-muted/20 px-2.5 py-1 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-success" />
            不构成实盘指令
          </span>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-4">
          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">准备度组合 ID</span>
            <input
              className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
              value={readinessPortfolioId}
              onChange={(event) => setReadinessPortfolioId(event.target.value)}
            />
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">观察天数</span>
            <input
              className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
              inputMode="numeric"
              value={readinessLookbackDays}
              onChange={(event) => setReadinessLookbackDays(event.target.value)}
            />
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">最低批次</span>
            <input
              className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
              inputMode="numeric"
              value={readinessMinBatches}
              onChange={(event) => setReadinessMinBatches(event.target.value)}
            />
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">准备度偏差容忍度</span>
            <input
              className="rounded-md border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
              inputMode="decimal"
              value={readinessTolerance}
              onChange={(event) => setReadinessTolerance(event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className={cn(
            "rounded-lg border p-3 text-xs leading-5 md:flex-1",
            readinessState.status === "failed"
              ? "border-warning/30 bg-warning/5 text-muted-foreground"
              : "bg-muted/20 text-muted-foreground",
          )}>
            <p className="font-medium text-foreground">{readinessState.message}</p>
            {readinessError ? <p className="mt-1 text-destructive">{readinessError}</p> : null}
          </div>

          <button
            className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={readinessBusy}
            onClick={generateReadinessReport}
            type="button"
          >
            {readinessAction === "readiness" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Gauge className="h-4 w-4" />
            )}
            生成准备度报告
          </button>
        </div>
      </section>

      {readinessReport ? <ReadinessReportPanel report={readinessReport} /> : null}
    </div>
  );
}
