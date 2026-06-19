"""JoinQuant export service for local research signals."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
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
        return {
            "status": summary["status"],
            "imported_count": len(normalized),
            "portfolio_id": primary_portfolio,
            "signal_date": primary_signal.isoformat(),
            "trade_date": primary_trade.isoformat(),
            "replace": replace,
            "reports": [self._public_report(row) for row in normalized],
            "summary": summary,
            "research_only": True,
            "live_trading": False,
        }

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
