"""Tests for advisor MCP helper tools used by Codex orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import mcp_server

pytest.importorskip("duckdb")


def _payload(raw: str) -> dict:
    return json.loads(raw)


def test_advisor_mcp_tools_write_local_research_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))

    transaction = _payload(
        mcp_server.advisor_record_transaction(
            ticker="300308.SZ",
            ticker_name="中际旭创",
            action="buy",
            price=10.2,
            quantity=300,
            trade_date="2026-06-21",
            idempotency_key="mcp-buy-300308",
            source_command="我买入了 300 股中际旭创。",
        )
    )
    thesis = _payload(
        mcp_server.advisor_upsert_thesis(
            ticker="300308.SZ",
            ticker_name="中际旭创",
            strategy_type="短期热点趋势",
            buy_reason="AI 算力板块热度扩散。",
            entry_conditions="放量突破后观察。",
            exit_conditions="跌破 20 日线或板块热度退潮。",
            not_buy_conditions="高开过多不买。",
            stop_loss_price=9.5,
            max_position_pct=0.12,
            target_holding_days=10,
            review_frequency_days=3,
            as_of_date="2026-06-21",
        )
    )
    watchlist = _payload(
        mcp_server.advisor_upsert_watchlist_item(
            ticker="000977.SZ",
            ticker_name="浪潮信息",
            theme="AI算力",
            trigger_price=42.0,
            not_buy_conditions="高开过多不买。",
            reason="等待服务器链条确认买点。",
        )
    )
    snapshot = _payload(mcp_server.advisor_today_snapshot(as_of_date="2026-06-21"))

    assert transaction["status"] == "ok"
    assert transaction["result"]["live_trading"] is False
    assert thesis["status"] == "ok"
    assert thesis["result"]["completeness_status"] == "complete"
    assert watchlist["status"] == "ok"
    assert watchlist["result"]["ticker"] == "000977.SZ"
    assert snapshot["status"] == "ok"
    assert snapshot["result"]["title"] == "今日建议"
    assert snapshot["result"]["research_only"] is True


def test_advisor_mcp_transaction_rejects_non_a_share(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))

    result = _payload(
        mcp_server.advisor_record_transaction(
            ticker="AAPL.US",
            action="buy",
            price=100.0,
            quantity=1,
        )
    )

    assert result["status"] == "error"
    assert result["error_type"] == "advisor_transaction"
    assert "沪深 A 股" in result["error"]

