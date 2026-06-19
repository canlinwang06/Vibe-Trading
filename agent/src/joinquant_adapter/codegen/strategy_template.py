"""Generate copyable JoinQuant strategy code from approved local signals."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from string import Template
from typing import Any


STRATEGY_TEMPLATE = Template(
    '''# generated_by: Vibe-Trading Codex local JoinQuant adapter
# generated_at: $generated_at
# strategy_id: $strategy_id
# risk_notice: $risk_notice
# source_portfolio_id: $portfolio_id
# source_signal_date: $signal_date
#
# Research/simulation code only. Review in JoinQuant before any simulated run.

import json


SIGNAL_JSON = r"""$signal_json"""


def initialize(context):
    log.info("Vibe-Trading JoinQuant strategy initialized")
    g.signal_payload = json.loads(SIGNAL_JSON)
    g.target_map = {item["ticker"]: item for item in g.signal_payload["targets"]}
    g.max_single_position = 0.15
    g.max_total_exposure = min(float(g.signal_payload.get("total_exposure", 0)), 1.0)
    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    run_daily(before_trading_start, time="09:20")


def map_a_share_ticker(ticker):
    if ticker.endswith(".XSHG") or ticker.endswith(".XSHE"):
        return ticker
    if ticker.endswith(".SH"):
        return ticker.replace(".SH", ".XSHG")
    if ticker.endswith(".SZ"):
        return ticker.replace(".SZ", ".XSHE")
    raise ValueError("unsupported ticker for JoinQuant: %s" % ticker)


def before_trading_start(context):
    signal_date = g.signal_payload.get("signal_date")
    valid_for = g.signal_payload.get("valid_for")
    log.info("Vibe signal date=%s valid_for=%s targets=%s" % (signal_date, valid_for, len(g.target_map)))


def handle_data(context, data):
    if not _risk_gate(context):
        log.warn("risk gate blocked this bar")
        return
    total_target = sum(float(item.get("target_weight", 0)) for item in g.target_map.values())
    if total_target > g.max_total_exposure + 0.0001:
        log.warn("target exposure exceeds configured max, skip rebalance")
        return
    for security, item in sorted(g.target_map.items()):
        target_weight = min(float(item.get("target_weight", 0)), g.max_single_position)
        if not _can_trade(security, data):
            log.warn("skip %s due to suspension or price limit" % security)
            continue
        order_target_percent(security, target_weight)
        log.info("target %s weight %.4f reason=%s risk=%s" % (
            security,
            target_weight,
            item.get("reason", ""),
            item.get("risk", ""),
        ))


def _risk_gate(context):
    exposure = sum(float(item.get("target_weight", 0)) for item in g.target_map.values())
    if exposure > 1.0:
        log.warn("exposure > 100%%, blocked")
        return False
    return True


def _can_trade(security, data):
    current = data[security]
    if current.paused:
        return False
    price = current.close
    high_limit = getattr(current, "high_limit", None)
    low_limit = getattr(current, "low_limit", None)
    if high_limit is not None and price >= high_limit:
        return False
    if low_limit is not None and price <= low_limit:
        return False
    return True
'''
)


def build_strategy_code(
    *,
    payload: dict[str, Any],
    strategy_id: str,
    risk_notice: str,
    generated_at: datetime | None = None,
) -> str:
    """Return a complete JoinQuant Python strategy file as text."""
    timestamp = (generated_at or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    return STRATEGY_TEMPLATE.substitute(
        generated_at=timestamp,
        strategy_id=strategy_id,
        risk_notice=risk_notice,
        portfolio_id=payload["portfolio_id"],
        signal_date=payload["signal_date"],
        signal_json=json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
    )
