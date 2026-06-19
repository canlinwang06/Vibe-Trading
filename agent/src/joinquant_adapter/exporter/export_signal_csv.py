"""Build JoinQuant-compatible signal CSV text."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


CSV_FIELDS = [
    "signal_date",
    "valid_for",
    "portfolio_id",
    "ticker",
    "source_ticker",
    "ticker_name",
    "target_weight",
    "current_weight",
    "action",
    "strategy_sources",
    "theme",
    "reason",
    "risk",
]


def build_signal_csv_text(
    *,
    portfolio_id: str,
    signal_date: str,
    valid_for: str,
    mapped_targets: list[dict[str, Any]],
) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in mapped_targets:
        writer.writerow(
            {
                "signal_date": signal_date,
                "valid_for": valid_for,
                "portfolio_id": portfolio_id,
                "ticker": row["ticker"],
                "source_ticker": row["source_ticker"],
                "ticker_name": row["ticker_name"],
                "target_weight": row["target_weight"],
                "current_weight": row["current_weight"],
                "action": row["action"],
                "strategy_sources": json.dumps(row["strategy_sources"], ensure_ascii=False),
                "theme": row["theme"],
                "reason": row["reason"],
                "risk": row["risk"],
            }
        )
    return buffer.getvalue()
