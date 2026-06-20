"""Copy-package metadata for JoinQuant signal execution templates."""

from __future__ import annotations

from typing import Any


def build_signal_executor_notes(payload: dict[str, Any]) -> str:
    """Return human-readable notes shipped with the copy package."""
    return "\n".join(
        [
            "# Vibe-Trading JoinQuant Copy Package",
            "",
            f"- portfolio_id: {payload['portfolio_id']}",
            f"- signal_date: {payload['signal_date']}",
            f"- valid_for: {payload['valid_for']}",
            f"- target_count: {len(payload['targets'])}",
            f"- total_exposure: {payload['total_exposure']}",
            "",
            "使用说明:",
            "1. 先查看 signals.json 与 signals.csv，确认目标仓位和风险提示。",
            "2. 将 strategy.py 的完整内容复制到聚宽策略编辑器。",
            "3. 先在聚宽内手动运行回测或模拟盘，不要直接用于实盘。",
            "4. 本包不会自动登录聚宽、不会提交策略、不会下单。",
        ]
    )


def copy_package_manifest(
    *,
    payload: dict[str, Any],
    strategy_id: str,
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact manifest for UI copy/download workflows."""
    return {
        "package_type": "joinquant-copy-package",
        "strategy_id": strategy_id,
        "portfolio_id": payload["portfolio_id"],
        "signal_date": payload["signal_date"],
        "valid_for": payload["valid_for"],
        "target_count": len(payload["targets"]),
        "total_exposure": payload["total_exposure"],
        "files": [
            {
                "filename": item["filename"],
                "content_type": item["content_type"],
                "size": len(item["content"]),
            }
            for item in files
        ],
        "manual_confirmation_required": True,
        "live_trading": False,
    }
