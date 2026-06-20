"""JoinQuant export service for local research signals."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore
from src.joinquant_adapter.codegen.signal_executor_template import (
    build_signal_executor_notes,
    copy_package_manifest,
)
from src.joinquant_adapter.exporter.export_signal_csv import build_signal_csv_text
from src.joinquant_adapter.exporter.export_signal_json import build_signal_json_payload, dumps_signal_json
from src.joinquant_adapter.exporter.export_strategy import DEFAULT_RISK_NOTICE, build_strategy_export
from src.joinquant_adapter.mapper.code_mapper import JoinQuantMappingError, unmap_ticker
from src.joinquant_adapter.validator.jq_signal_validator import JoinQuantSignalValidator
from src.portfolio_risk.service import PortfolioRiskService


class JoinQuantExportError(RuntimeError):
    """Raised when JoinQuant export preflight blocks an export."""


EXECUTION_STATUS_ALIASES = {
    "filled": "filled",
    "成交": "filled",
    "已成交": "filled",
    "complete": "filled",
    "completed": "filled",
    "partially_filled": "partially_filled",
    "partial": "partially_filled",
    "部分成交": "partially_filled",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "已撤单": "cancelled",
    "rejected": "rejected",
    "拒单": "rejected",
    "error": "error",
    "failed": "error",
    "失败": "error",
    "skipped": "skipped",
    "跳过": "skipped",
    "held": "held",
    "持有": "held",
    "pending": "pending",
    "待处理": "pending",
}
SUCCESS_REPORT_STATUSES = {"filled", "partially_filled", "held", "skipped"}
FAILED_REPORT_STATUSES = {"cancelled", "rejected", "error"}
LIMIT_OR_SUSPEND_KEYWORDS = ("涨停", "跌停", "停牌", "limit", "suspend", "suspended")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None, *, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError as exc:
        raise JoinQuantExportError(f"{field_name} 日期格式无效: {value}") from exc


def _float_or_none(value: Any, *, field_name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise JoinQuantExportError(f"{field_name} 必须是数字。") from exc
    return parsed


def _weight_or_none(value: Any, *, field_name: str) -> float | None:
    parsed = _float_or_none(value, field_name=field_name)
    if parsed is None:
        return None
    if parsed < 0 or parsed > 1:
        raise JoinQuantExportError(f"{field_name} 必须在 0 到 1 之间。")
    return round(parsed, 6)


def _non_negative_or_none(value: Any, *, field_name: str) -> float | None:
    parsed = _float_or_none(value, field_name=field_name)
    if parsed is None:
        return None
    if parsed < 0:
        raise JoinQuantExportError(f"{field_name} 不能为负数。")
    return parsed


def _normalize_execution_status(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    status = EXECUTION_STATUS_ALIASES.get(raw)
    if status is None:
        raise JoinQuantExportError(f"聚宽执行状态无法识别: {value}")
    return status


def _report_id(*, portfolio_id: str, signal_date: date, trade_date: date, ticker: str) -> str:
    digest = hashlib.sha256(f"{portfolio_id}|{signal_date}|{trade_date}|{ticker}".encode("utf-8")).hexdigest()[:18]
    return f"jqrep_{digest}"


class JoinQuantExportService:
    """Run JoinQuant signal preflight and build local export payloads."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()
        self.validator = JoinQuantSignalValidator()

    def preflight(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        require_approved: bool = True,
    ) -> dict[str, Any]:
        self.store.initialize()
        signal = self._resolve_signal_date(
            portfolio_id=portfolio_id,
            signal_date=signal_date,
            require_approved=require_approved,
        )
        signals = PortfolioRiskService(store=self.store).list_signals(
            portfolio_id=portfolio_id,
            signal_date=signal,
            limit=500,
        )
        validation = self.validator.validate(signals, require_approved=require_approved)
        return {
            "portfolio_id": portfolio_id,
            "signal_date": signal.isoformat(),
            "validation": self._public_validation(validation),
            "copy_ready": validation["status"] == "ok",
            "research_only": True,
            "live_trading": False,
        }

    def export_signals_json(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        require_approved: bool = True,
    ) -> dict[str, Any]:
        self.store.initialize()
        signal, valid_for, validation, allocations = self._validated_export_context(
            portfolio_id=portfolio_id,
            signal_date=signal_date,
            require_approved=require_approved,
        )
        payload = build_signal_json_payload(
            portfolio_id=portfolio_id,
            signal_date=signal.isoformat(),
            valid_for=valid_for,
            strategy_allocations=allocations,
            mapped_targets=validation["mapped_targets"],
        )
        return {
            "status": "ok",
            "export_type": "signals-json",
            "portfolio_id": portfolio_id,
            "signal_date": signal.isoformat(),
            "payload": payload,
            "json_text": dumps_signal_json(payload),
            "validation": self._public_validation(validation),
            "research_only": True,
            "live_trading": False,
        }

    def export_signals_csv(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        require_approved: bool = True,
    ) -> dict[str, Any]:
        self.store.initialize()
        signal, valid_for, validation, _allocations = self._validated_export_context(
            portfolio_id=portfolio_id,
            signal_date=signal_date,
            require_approved=require_approved,
        )
        csv_text = build_signal_csv_text(
            portfolio_id=portfolio_id,
            signal_date=signal.isoformat(),
            valid_for=valid_for,
            mapped_targets=validation["mapped_targets"],
        )
        return {
            "status": "ok",
            "export_type": "signals-csv",
            "portfolio_id": portfolio_id,
            "signal_date": signal.isoformat(),
            "row_count": len(validation["mapped_targets"]),
            "csv_text": csv_text,
            "validation": self._public_validation(validation),
            "research_only": True,
            "live_trading": False,
        }

    def export_strategy_code(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        strategy_id: str | None = None,
        risk_notice: str = DEFAULT_RISK_NOTICE,
        require_approved: bool = True,
    ) -> dict[str, Any]:
        self.store.initialize()
        signal, _valid_for, validation, allocations = self._validated_export_context(
            portfolio_id=portfolio_id,
            signal_date=signal_date,
            require_approved=require_approved,
        )
        payload = self._signal_payload(
            portfolio_id=portfolio_id,
            signal=signal,
            validation=validation,
            allocations=allocations,
        )
        resolved_strategy_id = strategy_id or self._default_strategy_id(portfolio_id, signal)
        strategy_export = build_strategy_export(
            payload=payload,
            strategy_id=resolved_strategy_id,
            risk_notice=risk_notice,
        )
        return {
            "status": "ok",
            "export_type": "strategy-code",
            "portfolio_id": portfolio_id,
            "signal_date": signal.isoformat(),
            "strategy_id": resolved_strategy_id,
            "filename": strategy_export["filename"],
            "python_code": strategy_export["content"],
            "risk_notice": strategy_export["risk_notice"],
            "validation": self._public_validation(validation),
            "copy_ready": True,
            "manual_confirmation_required": True,
            "research_only": True,
            "live_trading": False,
        }

    def export_copy_package(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        strategy_id: str | None = None,
        risk_notice: str = DEFAULT_RISK_NOTICE,
        require_approved: bool = True,
    ) -> dict[str, Any]:
        self.store.initialize()
        signal, _valid_for, validation, allocations = self._validated_export_context(
            portfolio_id=portfolio_id,
            signal_date=signal_date,
            require_approved=require_approved,
        )
        payload = self._signal_payload(
            portfolio_id=portfolio_id,
            signal=signal,
            validation=validation,
            allocations=allocations,
        )
        resolved_strategy_id = strategy_id or self._default_strategy_id(portfolio_id, signal)
        strategy_export = build_strategy_export(
            payload=payload,
            strategy_id=resolved_strategy_id,
            risk_notice=risk_notice,
        )
        json_text = dumps_signal_json(payload)
        csv_text = build_signal_csv_text(
            portfolio_id=portfolio_id,
            signal_date=signal.isoformat(),
            valid_for=payload["valid_for"],
            mapped_targets=validation["mapped_targets"],
        )
        files = [
            strategy_export,
            {"filename": "signals.json", "content_type": "application/json", "content": json_text},
            {"filename": "signals.csv", "content_type": "text/csv", "content": csv_text},
            {
                "filename": "README.md",
                "content_type": "text/markdown",
                "content": build_signal_executor_notes(payload),
            },
        ]
        return {
            "status": "ok",
            "export_type": "copy-package",
            "portfolio_id": portfolio_id,
            "signal_date": signal.isoformat(),
            "strategy_id": resolved_strategy_id,
            "manifest": copy_package_manifest(payload=payload, strategy_id=resolved_strategy_id, files=files),
            "files": files,
            "clipboard_text": strategy_export["content"],
            "validation": self._public_validation(validation),
            "copy_ready": True,
            "manual_confirmation_required": True,
            "research_only": True,
            "live_trading": False,
        }

    def import_execution_reports(
        self,
        *,
        reports: list[dict[str, Any]],
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        trade_date: str | date | datetime | None = None,
        replace: bool = False,
        jq_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist JoinQuant execution reports for local review and reconciliation."""
        self.store.initialize()
        normalized = self._normalize_execution_reports(
            reports=reports,
            portfolio_id=portfolio_id,
            signal_date=signal_date,
            trade_date=trade_date,
        )
        now = _utc_now()
        groups = {
            (row["portfolio_id"], row["signal_date"], row["trade_date"])
            for row in normalized
        }
        if len(groups) != 1:
            raise JoinQuantExportError("单次导入仅支持同一 portfolio_id、signal_date 和 trade_date 的聚宽报告。")
        with self.store.connect() as conn:
            if replace:
                for group_portfolio, group_signal, group_trade in groups:
                    conn.execute(
                        """
                        DELETE FROM jq_execution_reports
                        WHERE portfolio_id = ? AND signal_date = ? AND trade_date = ?
                        """,
                        [group_portfolio, group_signal, group_trade],
                    )
            for row in normalized:
                conn.execute("DELETE FROM jq_execution_reports WHERE report_id = ?", [row["report_id"]])
                conn.execute(
                    """
                    INSERT INTO jq_execution_reports (
                      report_id, signal_date, trade_date, portfolio_id, ticker,
                      planned_weight, executed_weight, order_status, fill_price,
                      fill_amount, error_message, raw_report, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row["report_id"],
                        row["signal_date"],
                        row["trade_date"],
                        row["portfolio_id"],
                        row["ticker"],
                        row["planned_weight"],
                        row["executed_weight"],
                        row["order_status"],
                        row["fill_price"],
                        row["fill_amount"],
                        row["error_message"],
                        row["raw_report"],
                        now,
                    ],
                )
                if row["order_status"] in SUCCESS_REPORT_STATUSES:
                    conn.execute(
                        """
                        UPDATE execution_signals
                        SET status = 'executed'
                        WHERE portfolio_id = ? AND signal_date = ? AND ticker = ?
                          AND status IN ('approved', 'exported', 'executed')
                        """,
                        [row["portfolio_id"], row["signal_date"], row["ticker"]],
                    )
                elif row["order_status"] == "cancelled":
                    conn.execute(
                        """
                        UPDATE execution_signals
                        SET status = 'cancelled'
                        WHERE portfolio_id = ? AND signal_date = ? AND ticker = ?
                          AND status IN ('approved', 'exported', 'cancelled')
                        """,
                        [row["portfolio_id"], row["signal_date"], row["ticker"]],
                    )
        primary_portfolio, primary_signal, primary_trade = sorted(groups)[0]
        summary = self.execution_report_summary(
            portfolio_id=primary_portfolio,
            signal_date=primary_signal,
            trade_date=primary_trade,
        )
        linked_task_id = self._write_summary_to_task(jq_task_id, summary) if jq_task_id else None
        return {
            "status": summary["status"],
            "imported_count": len(normalized),
            "portfolio_id": primary_portfolio,
            "signal_date": primary_signal.isoformat(),
            "trade_date": primary_trade.isoformat(),
            "jq_task_id": linked_task_id,
            "replace": replace,
            "reports": [self._public_report(row) for row in normalized],
            "summary": summary,
            "research_only": True,
            "live_trading": False,
        }

    def _write_summary_to_task(self, jq_task_id: str | None, summary: dict[str, Any]) -> str | None:
        clean_task_id = (jq_task_id or "").strip()
        if not clean_task_id:
            return None
        try:
            from src.joinquant_orchestration.service import JoinQuantTaskError, JoinQuantTaskService

            JoinQuantTaskService(store=self.store).update_task(
                clean_task_id,
                status="completed",
                result_summary={
                    "source": "joinquant_execution_report_import",
                    "summary": summary,
                },
                evidence=[
                    {
                        "type": "joinquant_execution_reports",
                        "portfolio_id": summary["portfolio_id"],
                        "signal_date": summary["signal_date"],
                        "trade_date": summary["trade_date"],
                        "report_count": summary["report_count"],
                        "action_required": summary["action_required"],
                    }
                ],
                error_message="聚宽报告需要复盘。" if summary["action_required"] else None,
            )
        except JoinQuantTaskError as exc:
            raise JoinQuantExportError(f"聚宽任务写回失败: {exc}") from exc
        return clean_task_id

    def list_execution_reports(
        self,
        *,
        portfolio_id: str | None = None,
        signal_date: str | date | datetime | None = None,
        trade_date: str | date | datetime | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 500)
        filters: list[str] = []
        params: list[Any] = []
        if portfolio_id:
            filters.append("portfolio_id = ?")
            params.append(portfolio_id.strip())
        parsed_signal = _parse_date(signal_date, field_name="signal_date")
        if parsed_signal:
            filters.append("signal_date = ?")
            params.append(parsed_signal)
        parsed_trade = _parse_date(trade_date, field_name="trade_date")
        if parsed_trade:
            filters.append("trade_date = ?")
            params.append(parsed_trade)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT report_id, signal_date, trade_date, portfolio_id, ticker,
                       planned_weight, executed_weight, order_status, fill_price,
                       fill_amount, error_message, raw_report, created_at
                FROM jq_execution_reports
                {where}
                ORDER BY trade_date DESC, signal_date DESC, portfolio_id, ticker
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_report(row) for row in rows]

    def execution_report_summary(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        trade_date: str | date | datetime | None = None,
        tolerance: float = 0.01,
    ) -> dict[str, Any]:
        self.store.initialize()
        resolved_signal = self._resolve_report_signal_date(
            portfolio_id=portfolio_id,
            signal_date=signal_date,
        )
        resolved_trade = self._resolve_report_trade_date(
            portfolio_id=portfolio_id,
            signal_date=resolved_signal,
            trade_date=trade_date,
        )
        reports = self.list_execution_reports(
            portfolio_id=portfolio_id,
            signal_date=resolved_signal,
            trade_date=resolved_trade,
            limit=500,
        )
        if not reports:
            raise JoinQuantExportError("没有可复盘的聚宽执行报告，请先导入报告。")
        signals = PortfolioRiskService(store=self.store).list_signals(
            portfolio_id=portfolio_id,
            signal_date=resolved_signal,
            limit=500,
        )
        signal_by_ticker = {row["ticker"]: row for row in signals}
        report_by_ticker = {row["ticker"]: row for row in reports}
        deviations: list[dict[str, Any]] = []
        max_abs_diff = 0.0
        total_abs_diff = 0.0
        for report in reports:
            planned = float(report.get("planned_weight") or 0.0)
            executed = float(report.get("executed_weight") or 0.0)
            abs_diff = round(abs(executed - planned), 6)
            max_abs_diff = max(max_abs_diff, abs_diff)
            total_abs_diff = round(total_abs_diff + abs_diff, 6)
            deviations.append({
                "ticker": report["ticker"],
                "planned_weight": planned,
                "executed_weight": executed,
                "abs_weight_diff": abs_diff,
                "order_status": report["order_status"],
                "matched_signal": report["ticker"] in signal_by_ticker,
                "needs_review": abs_diff > tolerance or report["order_status"] in FAILED_REPORT_STATUSES,
            })
        status_counts: dict[str, int] = {}
        for report in reports:
            status_counts[report["order_status"]] = status_counts.get(report["order_status"], 0) + 1
        failed_count = sum(status_counts.get(status, 0) for status in FAILED_REPORT_STATUSES)
        unmatched_reports = [row["ticker"] for row in reports if row["ticker"] not in signal_by_ticker]
        missing_reports = [ticker for ticker in signal_by_ticker if ticker not in report_by_ticker]
        action_required = (
            failed_count > 0
            or bool(unmatched_reports)
            or bool(missing_reports)
            or max_abs_diff > tolerance
        )
        return {
            "status": "needs_review" if action_required else "ok",
            "portfolio_id": portfolio_id,
            "signal_date": resolved_signal.isoformat(),
            "trade_date": resolved_trade.isoformat(),
            "report_count": len(reports),
            "signal_count": len(signals),
            "matched_signal_count": len(reports) - len(unmatched_reports),
            "failed_count": failed_count,
            "unmatched_report_count": len(unmatched_reports),
            "missing_report_count": len(missing_reports),
            "total_planned_weight": round(sum(float(row.get("planned_weight") or 0.0) for row in reports), 6),
            "total_executed_weight": round(sum(float(row.get("executed_weight") or 0.0) for row in reports), 6),
            "max_abs_weight_diff": round(max_abs_diff, 6),
            "total_abs_weight_diff": round(total_abs_diff, 6),
            "tolerance": tolerance,
            "status_counts": status_counts,
            "unmatched_reports": unmatched_reports,
            "missing_reports": missing_reports,
            "deviations": deviations,
            "action_required": action_required,
            "research_only": True,
            "live_trading": False,
        }

    def simulation_readiness_report(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        lookback_days: int = 90,
        min_batches: int = 20,
        tolerance: float = 0.01,
        max_failed_rate: float = 0.05,
        max_missing_rate: float = 0.05,
        max_deviation_rate: float = 0.10,
        max_signal_delay_days: int = 3,
    ) -> dict[str, Any]:
        """Summarize JoinQuant simulation health before any small-capital live trial."""
        self.store.initialize()
        lookback_days = min(max(int(lookback_days), 1), 365)
        min_batches = min(max(int(min_batches), 1), 250)
        tolerance = self._bounded_ratio(tolerance, field_name="tolerance")
        max_failed_rate = self._bounded_ratio(max_failed_rate, field_name="max_failed_rate")
        max_missing_rate = self._bounded_ratio(max_missing_rate, field_name="max_missing_rate")
        max_deviation_rate = self._bounded_ratio(max_deviation_rate, field_name="max_deviation_rate")
        max_signal_delay_days = min(max(int(max_signal_delay_days), 0), 30)
        latest_trade = self._latest_report_trade_date(portfolio_id)
        window_start = latest_trade - timedelta(days=lookback_days - 1)
        batches = self._report_batches(
            portfolio_id=portfolio_id,
            start_date=window_start,
            end_date=latest_trade,
        )
        if not batches:
            raise JoinQuantExportError("没有可评估的聚宽模拟盘报告，请先导入执行报告。")

        daily_summaries: list[dict[str, Any]] = []
        total_reports = 0
        total_signals = 0
        failed_count = 0
        unmatched_count = 0
        missing_report_count = 0
        deviation_count = 0
        total_abs_weight_diff = 0.0
        max_abs_weight_diff = 0.0
        signal_delay_days: list[int] = []
        limit_or_suspend_issue_count = 0

        for batch in batches:
            summary = self.execution_report_summary(
                portfolio_id=portfolio_id,
                signal_date=batch["signal_date"],
                trade_date=batch["trade_date"],
                tolerance=tolerance,
            )
            reports = self.list_execution_reports(
                portfolio_id=portfolio_id,
                signal_date=batch["signal_date"],
                trade_date=batch["trade_date"],
                limit=500,
            )
            delay_days = (batch["trade_date"] - batch["signal_date"]).days
            signal_delay_days.append(delay_days)
            total_reports += summary["report_count"]
            total_signals += summary["signal_count"]
            failed_count += summary["failed_count"]
            unmatched_count += summary["unmatched_report_count"]
            missing_report_count += summary["missing_report_count"]
            batch_deviation_count = sum(
                1 for row in summary["deviations"] if float(row["abs_weight_diff"] or 0.0) > tolerance
            )
            deviation_count += batch_deviation_count
            total_abs_weight_diff = round(total_abs_weight_diff + float(summary["total_abs_weight_diff"]), 6)
            max_abs_weight_diff = max(max_abs_weight_diff, float(summary["max_abs_weight_diff"]))
            limit_or_suspend_issue_count += self._count_limit_or_suspend_issues(reports)
            daily_summaries.append({
                "signal_date": summary["signal_date"],
                "trade_date": summary["trade_date"],
                "status": summary["status"],
                "report_count": summary["report_count"],
                "signal_count": summary["signal_count"],
                "failed_count": summary["failed_count"],
                "missing_report_count": summary["missing_report_count"],
                "unmatched_report_count": summary["unmatched_report_count"],
                "max_abs_weight_diff": summary["max_abs_weight_diff"],
                "total_abs_weight_diff": summary["total_abs_weight_diff"],
                "deviation_count": batch_deviation_count,
                "signal_delay_days": delay_days,
                "action_required": summary["action_required"],
            })

        signal_batches = self._signal_batches(
            portfolio_id=portfolio_id,
            start_date=window_start,
            end_date=latest_trade,
        )
        report_signal_dates = {batch["signal_date"] for batch in batches}
        missing_batch_signal_count = sum(
            count for signal_date, count in signal_batches.items() if signal_date not in report_signal_dates
        )
        missing_signal_batch_count = sum(1 for signal_date in signal_batches if signal_date not in report_signal_dates)
        total_signals += missing_batch_signal_count
        missing_report_count += missing_batch_signal_count

        backtest_risk = self._backtest_risk_snapshot()
        avg_delay = round(sum(signal_delay_days) / len(signal_delay_days), 2) if signal_delay_days else 0.0
        max_delay = max(signal_delay_days) if signal_delay_days else 0
        rates = {
            "failed_rate": self._rate(failed_count, total_reports),
            "missing_report_rate": self._rate(missing_report_count, total_signals),
            "unmatched_report_rate": self._rate(unmatched_count, total_reports),
            "deviation_rate": self._rate(deviation_count, total_reports),
        }
        checks = [
            self._check(
                "observation_window",
                observed=len(batches),
                threshold=min_batches,
                ok=len(batches) >= min_batches,
                message_ok="模拟盘观察批次数已达到验收下限。",
                message_fail="模拟盘观察批次数不足，继续运行后再评估。",
                fail_status="warning",
            ),
            self._check(
                "execution_failure_rate",
                observed=rates["failed_rate"],
                threshold=max_failed_rate,
                ok=rates["failed_rate"] <= max_failed_rate and failed_count == 0,
                message_ok="执行失败率在可接受范围内。",
                message_fail="存在失败、撤单或拒单记录，需要复盘原因。",
            ),
            self._check(
                "report_coverage",
                observed=rates["missing_report_rate"],
                threshold=max_missing_rate,
                ok=rates["missing_report_rate"] <= max_missing_rate and missing_signal_batch_count == 0,
                message_ok="计划信号和聚宽回报匹配充分。",
                message_fail="存在缺失回报或未覆盖的信号批次。",
            ),
            self._check(
                "weight_deviation",
                observed=rates["deviation_rate"],
                threshold=max_deviation_rate,
                ok=rates["deviation_rate"] <= max_deviation_rate and max_abs_weight_diff <= tolerance,
                message_ok="目标仓位和实际仓位偏差可控。",
                message_fail="目标仓位和实际仓位偏差超出容忍度。",
            ),
            self._check(
                "signal_delay",
                observed=max_delay,
                threshold=max_signal_delay_days,
                ok=max_delay <= max_signal_delay_days,
                message_ok="信号日至执行日延迟在可接受范围内。",
                message_fail="存在较长的信号执行延迟。",
            ),
            self._check(
                "limit_or_suspend_handling",
                observed=limit_or_suspend_issue_count,
                threshold=0,
                ok=limit_or_suspend_issue_count == 0,
                message_ok="未发现涨跌停或停牌相关失败记录。",
                message_fail="存在涨跌停或停牌相关失败记录，需要检查聚宽侧处理。",
                fail_status="warning",
            ),
            self._check(
                "backtest_drawdown",
                observed=backtest_risk["worst_max_drawdown"],
                threshold=-0.10,
                ok=backtest_risk["status"] in {"ok", "unknown"},
                message_ok=backtest_risk["message"],
                message_fail=backtest_risk["message"],
                fail_status="warning" if backtest_risk["status"] == "unknown" else "fail",
            ),
        ]
        status, recommendation, readiness_score = self._readiness_decision(checks)
        findings = self._readiness_findings(
            status=status,
            failed_count=failed_count,
            missing_report_count=missing_report_count,
            deviation_count=deviation_count,
            max_abs_weight_diff=max_abs_weight_diff,
            max_delay=max_delay,
            limit_or_suspend_issue_count=limit_or_suspend_issue_count,
            backtest_risk=backtest_risk,
            min_batches=min_batches,
            observed_batches=len(batches),
            max_signal_delay_days=max_signal_delay_days,
        )
        return {
            "status": status,
            "recommendation": recommendation,
            "readiness_score": readiness_score,
            "portfolio_id": portfolio_id,
            "lookback_days": lookback_days,
            "window_start": window_start.isoformat(),
            "window_end": latest_trade.isoformat(),
            "tolerance": tolerance,
            "min_batches": min_batches,
            "observed_batch_count": len(batches),
            "signal_batch_count": len(signal_batches),
            "missing_signal_batch_count": missing_signal_batch_count,
            "totals": {
                "report_count": total_reports,
                "signal_count": total_signals,
                "failed_count": failed_count,
                "missing_report_count": missing_report_count,
                "unmatched_report_count": unmatched_count,
                "deviation_count": deviation_count,
                "limit_or_suspend_issue_count": limit_or_suspend_issue_count,
                "total_abs_weight_diff": round(total_abs_weight_diff, 6),
                "max_abs_weight_diff": round(max_abs_weight_diff, 6),
                "avg_signal_delay_days": avg_delay,
                "max_signal_delay_days": max_delay,
            },
            "rates": rates,
            "backtest_risk": backtest_risk,
            "checks": checks,
            "findings": findings,
            "daily_summaries": daily_summaries,
            "research_only": True,
            "live_trading": False,
        }

    def _latest_report_trade_date(self, portfolio_id: str) -> date:
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                "SELECT MAX(trade_date) FROM jq_execution_reports WHERE portfolio_id = ?",
                [portfolio_id],
            ).fetchone()
        latest = row[0] if row and row[0] else None
        parsed = _parse_date(latest, field_name="trade_date")
        if parsed is None:
            raise JoinQuantExportError("没有可评估的聚宽模拟盘报告，请先导入执行报告。")
        return parsed

    def _report_batches(self, *, portfolio_id: str, start_date: date, end_date: date) -> list[dict[str, date]]:
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT signal_date, trade_date
                FROM jq_execution_reports
                WHERE portfolio_id = ? AND trade_date BETWEEN ? AND ?
                GROUP BY signal_date, trade_date
                ORDER BY trade_date, signal_date
                """,
                [portfolio_id, start_date, end_date],
            ).fetchall()
        return [
            {
                "signal_date": _parse_date(row[0], field_name="signal_date") or start_date,
                "trade_date": _parse_date(row[1], field_name="trade_date") or end_date,
            }
            for row in rows
        ]

    def _signal_batches(self, *, portfolio_id: str, start_date: date, end_date: date) -> dict[date, int]:
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT signal_date, COUNT(*)
                FROM execution_signals
                WHERE portfolio_id = ? AND signal_date BETWEEN ? AND ?
                GROUP BY signal_date
                ORDER BY signal_date
                """,
                [portfolio_id, start_date, end_date],
            ).fetchall()
        result: dict[date, int] = {}
        for row in rows:
            parsed = _parse_date(row[0], field_name="signal_date")
            if parsed is not None:
                result[parsed] = int(row[1] or 0)
        return result

    @staticmethod
    def _bounded_ratio(value: float, *, field_name: str) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise JoinQuantExportError(f"{field_name} 必须是 0 到 1 之间的小数。") from exc
        if parsed < 0 or parsed > 1:
            raise JoinQuantExportError(f"{field_name} 必须是 0 到 1 之间的小数。")
        return parsed

    @staticmethod
    def _rate(numerator: int | float, denominator: int | float) -> float:
        return round(float(numerator) / float(denominator), 6) if denominator else 0.0

    @staticmethod
    def _count_limit_or_suspend_issues(reports: list[dict[str, Any]]) -> int:
        count = 0
        for report in reports:
            message = str(report.get("error_message") or "").lower()
            if any(keyword.lower() in message for keyword in LIMIT_OR_SUSPEND_KEYWORDS):
                count += 1
        return count

    def _backtest_risk_snapshot(self) -> dict[str, Any]:
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT strategy_id, end_date, max_drawdown, sharpe, trade_count
                FROM backtest_runs
                WHERE market = 'CN_A' AND status = 'completed'
                ORDER BY end_date DESC, strategy_id
                LIMIT 50
                """
            ).fetchall()
        if not rows:
            return {
                "status": "unknown",
                "run_count": 0,
                "worst_max_drawdown": 0.0,
                "avg_sharpe": 0.0,
                "avg_trade_count": 0.0,
                "message": "暂无已完成 A 股回测结果，实盘前仍需补充回撤和稳定性证据。",
            }
        drawdowns = [float(row[2] or 0.0) for row in rows]
        sharpes = [float(row[3] or 0.0) for row in rows]
        trade_counts = [float(row[4] or 0.0) for row in rows]
        worst_drawdown = min(drawdowns)
        avg_sharpe = round(sum(sharpes) / len(sharpes), 4)
        avg_trade_count = round(sum(trade_counts) / len(trade_counts), 2)
        status = "needs_review" if abs(worst_drawdown) >= 0.10 else "ok"
        message = (
            f"已检查 {len(rows)} 个完成回测，最差最大回撤 {worst_drawdown:.2%}。"
            if status == "ok"
            else f"回测最差最大回撤 {worst_drawdown:.2%}，达到复盘阈值。"
        )
        return {
            "status": status,
            "run_count": len(rows),
            "worst_max_drawdown": round(worst_drawdown, 6),
            "avg_sharpe": avg_sharpe,
            "avg_trade_count": avg_trade_count,
            "message": message,
        }

    @staticmethod
    def _check(
        name: str,
        *,
        observed: int | float,
        threshold: int | float,
        ok: bool,
        message_ok: str,
        message_fail: str,
        fail_status: str = "fail",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "pass" if ok else fail_status,
            "observed": observed,
            "threshold": threshold,
            "message": message_ok if ok else message_fail,
        }

    @staticmethod
    def _readiness_decision(checks: list[dict[str, Any]]) -> tuple[str, str, int]:
        fail_count = sum(1 for item in checks if item["status"] == "fail")
        warning_count = sum(1 for item in checks if item["status"] == "warning")
        score = max(0, 100 - fail_count * 24 - warning_count * 10)
        if fail_count:
            return "needs_review", "fix_before_live", score
        if warning_count:
            return "needs_more_data", "extend_observation", score
        return "ready", "continue_simulation", score

    @staticmethod
    def _readiness_findings(
        *,
        status: str,
        failed_count: int,
        missing_report_count: int,
        deviation_count: int,
        max_abs_weight_diff: float,
        max_delay: int,
        limit_or_suspend_issue_count: int,
        backtest_risk: dict[str, Any],
        min_batches: int,
        observed_batches: int,
        max_signal_delay_days: int,
    ) -> list[str]:
        findings: list[str] = []
        if observed_batches < min_batches:
            findings.append(f"模拟盘观察批次 {observed_batches}/{min_batches}，建议继续积累样本。")
        if failed_count:
            findings.append(f"发现 {failed_count} 条失败、撤单或拒单记录，需要定位聚宽侧原因。")
        if missing_report_count:
            findings.append(f"发现 {missing_report_count} 条计划信号缺少聚宽执行回报。")
        if deviation_count:
            findings.append(f"发现 {deviation_count} 条仓位偏差超阈值，最大偏差 {max_abs_weight_diff:.2%}。")
        if max_delay > max_signal_delay_days:
            findings.append(f"最大信号执行延迟 {max_delay} 天，需要检查导出和执行节奏。")
        if limit_or_suspend_issue_count:
            findings.append(f"发现 {limit_or_suspend_issue_count} 条涨跌停或停牌相关问题。")
        if backtest_risk["status"] != "ok":
            findings.append(backtest_risk["message"])
        if not findings:
            findings.append("模拟盘执行、回传和回测风险均未触发阻断项，继续保持人工确认。")
        if status == "ready":
            findings.append("当前仅代表模拟盘准备度通过，不构成实盘下单建议。")
        return findings

    def _validated_export_context(
        self,
        *,
        portfolio_id: str,
        signal_date: str | date | datetime | None,
        require_approved: bool,
    ) -> tuple[date, str, dict[str, Any], list[dict[str, Any]]]:
        signal = self._resolve_signal_date(
            portfolio_id=portfolio_id,
            signal_date=signal_date,
            require_approved=require_approved,
        )
        portfolio = PortfolioRiskService(store=self.store)
        signals = portfolio.list_signals(portfolio_id=portfolio_id, signal_date=signal, limit=500)
        validation = self.validator.validate(signals, require_approved=require_approved)
        if validation["status"] != "ok":
            raise JoinQuantExportError("导出前校验未通过: " + "；".join(validation["errors"]))
        allocations = portfolio.list_allocations(portfolio_id=portfolio_id, as_of_date=signal, limit=100)
        valid_for = self._valid_for(validation["mapped_targets"])
        return signal, valid_for, validation, allocations

    def _signal_payload(
        self,
        *,
        portfolio_id: str,
        signal: date,
        validation: dict[str, Any],
        allocations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        valid_for = self._valid_for(validation["mapped_targets"])
        return build_signal_json_payload(
            portfolio_id=portfolio_id,
            signal_date=signal.isoformat(),
            valid_for=valid_for,
            strategy_allocations=allocations,
            mapped_targets=validation["mapped_targets"],
        )

    def _resolve_signal_date(
        self,
        *,
        portfolio_id: str,
        signal_date: str | date | datetime | None,
        require_approved: bool,
    ) -> date:
        parsed = _parse_date(signal_date, field_name="signal_date")
        if parsed:
            return parsed
        status_filter = "AND status = 'approved'" if require_approved else ""
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                f"""
                SELECT MAX(signal_date)
                FROM execution_signals
                WHERE portfolio_id = ?
                {status_filter}
                """,
                [portfolio_id],
            ).fetchone()
        resolved = row[0] if row and row[0] else None
        parsed_resolved = _parse_date(resolved, field_name="signal_date")
        if parsed_resolved is None:
            raise JoinQuantExportError("没有可导出的 approved 信号，请先完成模拟审批。")
        return parsed_resolved

    @staticmethod
    def _valid_for(mapped_targets: list[dict[str, Any]]) -> str:
        dates = [str(row.get("valid_for") or "") for row in mapped_targets if row.get("valid_for")]
        return min(dates) if dates else ""

    @staticmethod
    def _default_strategy_id(portfolio_id: str, signal: date) -> str:
        compact_date = signal.isoformat().replace("-", "")
        return f"{portfolio_id}_jq_signal_executor_{compact_date}"

    @staticmethod
    def _public_validation(validation: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": validation["status"],
            "checked_count": validation["checked_count"],
            "error_count": validation["error_count"],
            "warning_count": validation["warning_count"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

    def _normalize_execution_reports(
        self,
        *,
        reports: list[dict[str, Any]],
        portfolio_id: str,
        signal_date: str | date | datetime | None,
        trade_date: str | date | datetime | None,
    ) -> list[dict[str, Any]]:
        if not reports:
            raise JoinQuantExportError("聚宽执行报告不能为空。")
        if len(reports) > 500:
            raise JoinQuantExportError("单次最多导入 500 条聚宽执行报告。")
        default_signal = _parse_date(signal_date, field_name="signal_date")
        default_trade = _parse_date(trade_date, field_name="trade_date")
        normalized: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for idx, raw_report in enumerate(reports, start=1):
            if not isinstance(raw_report, dict):
                raise JoinQuantExportError(f"第 {idx} 条聚宽报告必须是对象。")
            row_portfolio = str(raw_report.get("portfolio_id") or portfolio_id).strip()
            if not row_portfolio:
                raise JoinQuantExportError(f"第 {idx} 条聚宽报告缺少 portfolio_id。")
            row_signal = _parse_date(raw_report.get("signal_date") or default_signal, field_name=f"reports[{idx}].signal_date")
            if row_signal is None:
                raise JoinQuantExportError(f"第 {idx} 条聚宽报告缺少 signal_date。")
            row_trade = _parse_date(raw_report.get("trade_date") or default_trade or row_signal, field_name=f"reports[{idx}].trade_date")
            if row_trade is None:  # pragma: no cover - row_signal fallback already covers this
                raise JoinQuantExportError(f"第 {idx} 条聚宽报告缺少 trade_date。")
            ticker_value = raw_report.get("ticker") or raw_report.get("security") or raw_report.get("jq_ticker")
            if not ticker_value:
                raise JoinQuantExportError(f"第 {idx} 条聚宽报告缺少 ticker。")
            try:
                local_ticker = unmap_ticker(str(ticker_value))
            except JoinQuantMappingError as exc:
                raise JoinQuantExportError(str(exc)) from exc
            status = _normalize_execution_status(raw_report.get("order_status") or raw_report.get("status"))
            planned = _weight_or_none(
                raw_report.get("planned_weight", raw_report.get("target_weight")),
                field_name=f"reports[{idx}].planned_weight",
            )
            executed = _weight_or_none(
                raw_report.get("executed_weight", raw_report.get("actual_weight", raw_report.get("position_weight", 0.0))),
                field_name=f"reports[{idx}].executed_weight",
            )
            if executed is None:
                executed = 0.0
            normalized_row = {
                "report_id": str(
                    raw_report.get("report_id")
                    or _report_id(
                        portfolio_id=row_portfolio,
                        signal_date=row_signal,
                        trade_date=row_trade,
                        ticker=local_ticker,
                    )
                ),
                "signal_date": row_signal,
                "trade_date": row_trade,
                "portfolio_id": row_portfolio,
                "ticker": local_ticker,
                "planned_weight": planned,
                "executed_weight": executed,
                "order_status": status,
                "fill_price": _non_negative_or_none(raw_report.get("fill_price"), field_name=f"reports[{idx}].fill_price"),
                "fill_amount": _non_negative_or_none(raw_report.get("fill_amount"), field_name=f"reports[{idx}].fill_amount"),
                "error_message": str(raw_report.get("error_message") or "").strip() or None,
                "raw_report": json.dumps(raw_report, ensure_ascii=False, sort_keys=True, default=str),
            }
            if normalized_row["report_id"] in seen_ids:
                raise JoinQuantExportError(f"聚宽报告 report_id 重复: {normalized_row['report_id']}")
            seen_ids.add(normalized_row["report_id"])
            normalized.append(normalized_row)
        self._fill_missing_planned_weights(normalized)
        return normalized

    def _fill_missing_planned_weights(self, normalized: list[dict[str, Any]]) -> None:
        missing = [row for row in normalized if row["planned_weight"] is None]
        if not missing:
            return
        with self.store.connect(read_only=True) as conn:
            for row in missing:
                signal = conn.execute(
                    """
                    SELECT target_weight
                    FROM execution_signals
                    WHERE portfolio_id = ? AND signal_date = ? AND ticker = ?
                    """,
                    [row["portfolio_id"], row["signal_date"], row["ticker"]],
                ).fetchone()
                if signal is None:
                    raise JoinQuantExportError(
                        "聚宽报告缺少 planned_weight，且未找到匹配 execution_signal: "
                        f"{row['portfolio_id']} {row['signal_date']} {row['ticker']}"
                    )
                row["planned_weight"] = round(float(signal[0] or 0.0), 6)

    def _resolve_report_signal_date(
        self,
        *,
        portfolio_id: str,
        signal_date: str | date | datetime | None,
    ) -> date:
        parsed = _parse_date(signal_date, field_name="signal_date")
        if parsed:
            return parsed
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                "SELECT MAX(signal_date) FROM jq_execution_reports WHERE portfolio_id = ?",
                [portfolio_id],
            ).fetchone()
        resolved = row[0] if row and row[0] else None
        parsed_resolved = _parse_date(resolved, field_name="signal_date")
        if parsed_resolved is None:
            raise JoinQuantExportError("没有可复盘的聚宽执行报告，请先导入报告。")
        return parsed_resolved

    def _resolve_report_trade_date(
        self,
        *,
        portfolio_id: str,
        signal_date: date,
        trade_date: str | date | datetime | None,
    ) -> date:
        parsed = _parse_date(trade_date, field_name="trade_date")
        if parsed:
            return parsed
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT MAX(trade_date)
                FROM jq_execution_reports
                WHERE portfolio_id = ? AND signal_date = ?
                """,
                [portfolio_id, signal_date],
            ).fetchone()
        resolved = row[0] if row and row[0] else None
        parsed_resolved = _parse_date(resolved, field_name="trade_date")
        if parsed_resolved is None:
            raise JoinQuantExportError("没有可复盘的聚宽执行报告，请先导入报告。")
        return parsed_resolved

    @staticmethod
    def _row_to_report(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "report_id": row[0],
            "signal_date": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
            "trade_date": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
            "portfolio_id": row[3],
            "ticker": row[4],
            "planned_weight": float(row[5] or 0.0),
            "executed_weight": float(row[6] or 0.0),
            "order_status": row[7],
            "fill_price": None if row[8] is None else float(row[8]),
            "fill_amount": None if row[9] is None else float(row[9]),
            "error_message": row[10],
            "raw_report": row[11],
            "created_at": row[12].isoformat() if hasattr(row[12], "isoformat") else str(row[12]),
        }

    @staticmethod
    def _public_report(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_id": row["report_id"],
            "signal_date": row["signal_date"].isoformat(),
            "trade_date": row["trade_date"].isoformat(),
            "portfolio_id": row["portfolio_id"],
            "ticker": row["ticker"],
            "planned_weight": row["planned_weight"],
            "executed_weight": row["executed_weight"],
            "order_status": row["order_status"],
            "fill_price": row["fill_price"],
            "fill_amount": row["fill_amount"],
            "error_message": row["error_message"],
        }
