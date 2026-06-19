"""JoinQuant export service for local research signals."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from src.ashare_data.store import AShareDataStore
from src.joinquant_adapter.codegen.signal_executor_template import (
    build_signal_executor_notes,
    copy_package_manifest,
)
from src.joinquant_adapter.exporter.export_signal_csv import build_signal_csv_text
from src.joinquant_adapter.exporter.export_signal_json import build_signal_json_payload, dumps_signal_json
from src.joinquant_adapter.exporter.export_strategy import DEFAULT_RISK_NOTICE, build_strategy_export
from src.joinquant_adapter.validator.jq_signal_validator import JoinQuantSignalValidator
from src.portfolio_risk.service import PortfolioRiskService


class JoinQuantExportError(RuntimeError):
    """Raised when JoinQuant export preflight blocks an export."""


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
