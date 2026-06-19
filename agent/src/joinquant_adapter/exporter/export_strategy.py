"""JoinQuant strategy-code export helpers."""

from __future__ import annotations

from typing import Any

from src.joinquant_adapter.codegen.strategy_template import build_strategy_code


DEFAULT_RISK_NOTICE = "研究/模拟用途；复制到聚宽后必须人工确认风险，不能直接用于实盘。"


def build_strategy_export(
    *,
    payload: dict[str, Any],
    strategy_id: str,
    risk_notice: str = DEFAULT_RISK_NOTICE,
) -> dict[str, Any]:
    code = build_strategy_code(payload=payload, strategy_id=strategy_id, risk_notice=risk_notice)
    return {
        "filename": "strategy.py",
        "content_type": "text/x-python",
        "content": code,
        "strategy_id": strategy_id,
        "risk_notice": risk_notice,
    }
