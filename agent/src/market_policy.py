"""A-share market policy guardrails for the local research workbench."""

from __future__ import annotations

import os
import re
from typing import Any, Iterable

CN_A_ONLY_ENV = "CN_A_ONLY"

_FALSE_VALUES = {"0", "false", "no", "off"}
_A_SHARE_CODE_RE = re.compile(r"^\d{6}\.(SH|SZ)$", re.IGNORECASE)
_A_SHARE_SOURCES = frozenset({"auto", "tushare", "mootdx", "baostock", "tencent", "akshare", "futu", "local"})


class MarketPolicyError(ValueError):
    """Raised when a request violates the configured market policy."""


def cn_a_only_enabled() -> bool:
    """Return whether the project is constrained to Shanghai/Shenzhen A-shares."""
    return os.environ.get(CN_A_ONLY_ENV, "1").strip().lower() not in _FALSE_VALUES


def normalize_a_share_code(code: str) -> str:
    """Normalize a symbol into the canonical A-share suffix form."""
    return code.strip().upper()


def is_a_share_code(code: str) -> bool:
    """Return whether ``code`` is a supported Shanghai/Shenzhen A-share stock."""
    return bool(_A_SHARE_CODE_RE.fullmatch(normalize_a_share_code(code)))


def validate_a_share_codes(codes: Iterable[str], *, surface: str = "symbols") -> list[str]:
    """Validate and normalize user-facing symbols when ``CN_A_ONLY`` is enabled.

    Args:
        codes: Candidate symbols.
        surface: Human-readable request surface for error messages.

    Returns:
        Normalized symbol list.

    Raises:
        MarketPolicyError: If any symbol is outside the A-share-only boundary.
    """
    normalized = [normalize_a_share_code(code) for code in codes]
    if not cn_a_only_enabled():
        return normalized
    invalid = [code for code in normalized if not is_a_share_code(code)]
    if invalid:
        examples = "600519.SH, 300750.SZ, 000001.SZ"
        raise MarketPolicyError(
            f"CN_A_ONLY {surface} only accepts Shanghai/Shenzhen A-share stock codes "
            f"such as {examples}; rejected: {', '.join(invalid)}"
        )
    return normalized


def validate_backtest_config(config: dict[str, Any]) -> dict[str, Any]:
    """Apply A-share-only research limits to a backtest config.

    The policy is intentionally conservative for PR-01: long-only, cash-only,
    daily A-share stock research. Later PRs can extend the surface deliberately.
    """
    if not cn_a_only_enabled():
        return dict(config)

    checked = dict(config)
    checked["codes"] = validate_a_share_codes(checked.get("codes") or [], surface="backtest")

    source = str(checked.get("source", "tushare")).strip().lower()
    if source not in _A_SHARE_SOURCES:
        raise MarketPolicyError(
            f"CN_A_ONLY backtest source must be one of {sorted(_A_SHARE_SOURCES)}; got: {source}"
        )
    checked["source"] = source

    engine = str(checked.get("engine", "daily")).strip().lower()
    if engine != "daily":
        raise MarketPolicyError("CN_A_ONLY supports only the daily A-share stock engine; options/futures engines are disabled")
    checked["engine"] = engine

    leverage = checked.get("leverage", 1.0)
    try:
        leverage_value = float(leverage)
    except (TypeError, ValueError):
        raise MarketPolicyError("CN_A_ONLY backtests must be cash-only with leverage=1")
    if leverage_value != 1.0:
        raise MarketPolicyError("CN_A_ONLY backtests are cash-only; leverage must be 1")
    checked["leverage"] = 1.0

    for key in ("allow_short", "enable_short", "short_selling", "margin", "crypto", "options", "futures", "forex"):
        if checked.get(key):
            raise MarketPolicyError(f"CN_A_ONLY disables {key}; use long-only A-share research settings")

    checked.setdefault("trade_plan_status", "draft")
    return checked


def agent_market_boundary_prompt() -> str:
    """Return the Agent system-prompt section for the active market policy."""
    if not cn_a_only_enabled():
        return ""
    return """## A-Share Research Boundary

CN_A_ONLY is enabled for this workspace.
- Work only with Shanghai/Shenzhen A-share stock codes such as 600519.SH, 300750.SZ, 000001.SZ.
- Reject AAPL.US, 0700.HK, BTC-USDT, futures, options, forex, crypto, and cross-market allocation requests.
- Research, simulation, and backtesting only. Do not place live orders or instruct broker execution.
- All trade plans are drafts for user review. No automatic order placement.
- Strategies must be long-only and cash-only: no short selling, no leverage, no derivatives.
"""
