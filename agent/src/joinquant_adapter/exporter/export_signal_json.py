"""Build JoinQuant-compatible signal JSON payloads."""

from __future__ import annotations

import json
from typing import Any


def build_signal_json_payload(
    *,
    portfolio_id: str,
    signal_date: str,
    valid_for: str,
    strategy_allocations: list[dict[str, Any]],
    mapped_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    total_exposure = round(sum(float(row["target_weight"]) for row in mapped_targets), 6)
    return {
        "signal_date": signal_date,
        "valid_for": valid_for,
        "portfolio_id": portfolio_id,
        "total_exposure": total_exposure,
        "strategy_allocations": [
            {
                "strategy_id": row["strategy_id"],
                "weight": row["allocated_weight"],
            }
            for row in strategy_allocations
        ],
        "targets": [
            {
                "ticker": row["ticker"],
                "source_ticker": row["source_ticker"],
                "ticker_name": row["ticker_name"],
                "target_weight": row["target_weight"],
                "current_weight": row["current_weight"],
                "action": row["action"],
                "strategy_sources": row["strategy_sources"],
                "theme": row["theme"],
                "reason": row["reason"],
                "risk": row["risk"],
            }
            for row in mapped_targets
        ],
    }


def dumps_signal_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
