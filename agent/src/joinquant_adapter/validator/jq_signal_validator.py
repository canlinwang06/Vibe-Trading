"""Preflight validation for JoinQuant signal exports."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from src.joinquant_adapter.mapper.code_mapper import JoinQuantMappingError, map_ticker


ALLOWED_SIGNAL_ACTIONS = {"buy", "sell", "hold", "reduce", "increase"}


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


class JoinQuantSignalValidator:
    """Validate approved local execution signals before JoinQuant export."""

    def validate(
        self,
        signals: list[dict[str, Any]],
        *,
        require_approved: bool = True,
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        mapped_targets: list[dict[str, Any]] = []
        seen_tickers: set[str] = set()

        if not signals:
            errors.append("没有可导出的 execution_signals，请先生成并审批信号。")
            return self._result(errors, warnings, mapped_targets, checked_count=0)

        total_weight = 0.0
        for idx, signal in enumerate(signals, start=1):
            status = str(signal.get("status") or "").strip()
            ticker = str(signal.get("ticker") or "").strip()
            action = str(signal.get("action") or "").strip()
            target_weight = self._float(signal.get("target_weight"))
            signal_date = _parse_date(signal.get("signal_date"))
            valid_for = _parse_date(signal.get("valid_for"))
            if require_approved and status != "approved":
                errors.append(f"第 {idx} 条信号状态为 {status or '空'}，只有 approved 状态可以导出。")
            if action not in ALLOWED_SIGNAL_ACTIONS:
                errors.append(f"第 {idx} 条信号 action 无效: {action}")
            if target_weight < 0 or target_weight > 1:
                errors.append(f"第 {idx} 条信号目标权重必须在 0 到 1 之间。")
            if signal_date is None or valid_for is None:
                errors.append(f"第 {idx} 条信号缺少有效日期。")
            elif valid_for < signal_date:
                errors.append(f"第 {idx} 条信号 valid_for 不能早于 signal_date。")

            try:
                mapped_ticker = map_ticker(ticker)
            except JoinQuantMappingError as exc:
                errors.append(str(exc))
                continue
            if mapped_ticker in seen_tickers:
                errors.append(f"聚宽代码重复: {mapped_ticker}")
            seen_tickers.add(mapped_ticker)
            total_weight += target_weight
            mapped_targets.append({**signal, "source_ticker": ticker, "ticker": mapped_ticker})

        if total_weight > 1.0:
            errors.append("组合目标仓位超过 100%，不能导出。")
        if total_weight <= 0:
            errors.append("组合目标仓位为 0，不能导出。")
        if total_weight > 0.95:
            warnings.append("组合目标仓位接近满仓，请确认风险预算。")

        return self._result(errors, warnings, mapped_targets, checked_count=len(signals))

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _result(
        errors: list[str],
        warnings: list[str],
        mapped_targets: list[dict[str, Any]],
        *,
        checked_count: int,
    ) -> dict[str, Any]:
        return {
            "status": "ok" if not errors else "blocked",
            "checked_count": checked_count,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "mapped_targets": mapped_targets if not errors else [],
        }
