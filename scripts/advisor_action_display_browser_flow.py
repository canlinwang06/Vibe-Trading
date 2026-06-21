#!/usr/bin/env python3
"""Browser acceptance flow for the advisor action-display pages."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent"
sys.path.insert(0, str(AGENT_ROOT))

from src.ashare_data.store import AShareDataStore  # noqa: E402

BACKEND_URL = os.environ.get("VIBE_ADVISOR_BACKEND_URL", "http://127.0.0.1:18998").rstrip("/")
FRONTEND_URL = os.environ.get("VIBE_ADVISOR_FRONTEND_URL", "http://127.0.0.1:15898").rstrip("/")
AS_OF_DATE = os.environ.get("VIBE_ADVISOR_AS_OF_DATE", "2026-06-21")


def api_json(path: str, payload: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=body if method != "GET" else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def seed_market_price(ticker: str, ticker_name: str, close: float) -> None:
    store = AShareDataStore()
    store.initialize()
    trade_date = date(2026, 6, 19)
    with store.connect() as conn:
        conn.execute("DELETE FROM assets WHERE ticker = ?", [ticker])
        conn.execute(
            """
            INSERT INTO assets (ticker, ticker_name, exchange, asset_type, active, updated_at)
            VALUES (?, ?, ?, 'stock', true, now())
            """,
            [ticker, ticker_name, ticker.split(".")[1]],
        )
        conn.execute("DELETE FROM market_daily WHERE trade_date = ? AND ticker = ?", [trade_date, ticker])
        conn.execute(
            """
            INSERT INTO market_daily (
              trade_date, ticker, open, high, low, close, volume, amount,
              turnover, adj_factor, limit_status, suspended, source, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1000000, 50000000, 0.03, 1.0, 'normal', false, 'advisor_acceptance', now())
            """,
            [trade_date, ticker, close * 0.98, close * 1.02, close * 0.97, close],
        )


def seed_advisor_flow() -> None:
    seed_market_price("300308.SZ", "中际旭创", 10.8)
    seed_market_price("000977.SZ", "浪潮信息", 42.2)
    seed_market_price("601138.SH", "工业富联", 46.0)

    api_json(
        "/api/advisor/transactions",
        {
            "ticker": "300308.SZ",
            "ticker_name": "中际旭创",
            "action": "buy",
            "price": 10.2,
            "quantity": 300,
            "trade_date": "2026-06-18",
            "strategy_type": "短期热点趋势",
            "strategy_cycle": "short",
            "idempotency_key": "advisor-acceptance-buy-300308",
            "source_command": "我买入了 300 股中际旭创。",
        },
    )
    api_json(
        "/api/advisor/theses",
        {
            "ticker": "300308.SZ",
            "ticker_name": "中际旭创",
            "strategy_type": "短期热点趋势",
            "strategy_cycle": "short",
            "thesis": "AI 算力热点扩散，光模块龙头具备弹性。",
            "buy_reason": "板块热度上升且个股处于观察区间。",
            "entry_conditions": "放量站上 10 日线且板块热度维持高位。",
            "exit_conditions": "跌破 20 日线或板块热度连续两日退潮。",
            "not_buy_conditions": "高开超过 7% 或成交额明显缩量不买。",
            "stop_loss_price": 9.5,
            "take_profit_price": 12.8,
            "max_position_pct": 0.12,
            "target_holding_days": 10,
            "review_frequency_days": 3,
            "as_of_date": AS_OF_DATE,
        },
    )
    for ticker, name, close, trigger in [
        ("000977.SZ", "浪潮信息", 42.2, 42.0),
        ("601138.SH", "工业富联", 46.0, 42.0),
    ]:
        api_json(
            "/api/advisor/theses",
            {
                "ticker": ticker,
                "ticker_name": name,
                "strategy_type": "短期热点趋势",
                "strategy_cycle": "short",
                "thesis": "AI 算力服务器和工业互联网链条热点扩散。",
                "buy_reason": "板块热度上升，个股等待放量确认。",
                "entry_conditions": "放量突破触发价且板块热度不退潮。",
                "exit_conditions": "跌破 20 日线或板块热度退潮。",
                "not_buy_conditions": "高开超过 6% 或量能不足不买。",
                "stop_loss_price": round(close * 0.92, 2),
                "max_position_pct": 0.1,
                "target_holding_days": 8,
                "review_frequency_days": 3,
                "as_of_date": AS_OF_DATE,
            },
        )
        api_json(
            "/api/advisor/watchlist",
            {
                "ticker": ticker,
                "ticker_name": name,
                "theme": "AI算力",
                "trigger_price": trigger,
                "max_position_pct": 0.1,
                "not_buy_conditions": "高开超过 6% 或量能不足不买。",
                "reason": "等待 AI 算力链条确认买点。",
            },
        )
    api_json(
        "/api/advisor/external-validations",
        {
            "source": "joinquant",
            "source_ref": "advisor-acceptance-jq-001",
            "subject_type": "strategy",
            "subject_id": "strategy_ai_compute_breakout",
            "validation_date": AS_OF_DATE,
            "status": "passed",
            "metrics": {"annual_return": 0.18, "max_drawdown": -0.08, "sharpe": 1.28},
            "summary": "聚宽模拟回测通过初筛，仍需人工复核交易成本假设。",
        },
    )
    api_json("/api/advisor/alerts/generate", {}, method="POST")
    api_json(
        "/api/advisor/decision-journal",
        {
            "decision_date": AS_OF_DATE,
            "subject_type": "candidate",
            "subject_id": "000977.SZ",
            "ticker": "000977.SZ",
            "ticker_name": "浪潮信息",
            "decision": "observe",
            "user_intent": "先观察，不直接买入。",
            "codex_explanation": "候选达到触发线，但仍按小仓研究候选处理。",
        },
    )


def expect_text(page: Page, text: str) -> None:
    expect(page.get_by_text(text, exact=False).first).to_be_visible(timeout=30_000)


def open_page(page: Page, route: str, marker: str) -> None:
    page.goto(f"{FRONTEND_URL}{route}", wait_until="networkidle")
    expect_text(page, marker)


def assert_no_forbidden_buttons(page: Page) -> None:
    for label in ("发起回测", "运行回测", "登录聚宽", "实盘下单", "开始交易"):
        expect(page.get_by_role("button", name=label)).to_have_count(0)


def run_browser_checks() -> None:
    console_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        open_page(page, "/advisor/today", "今日建议")
        expect_text(page, "持仓数量")
        expect_text(page, "候选数量")
        assert_no_forbidden_buttons(page)

        open_page(page, "/advisor/holdings", "我的持仓")
        expect_text(page, "中际旭创")
        expect_text(page, "继续持有")
        assert_no_forbidden_buttons(page)

        open_page(page, "/advisor/watchlist", "观察清单")
        expect_text(page, "浪潮信息")
        expect_text(page, "可小仓试探")
        expect_text(page, "工业富联")
        expect_text(page, "追高风险")
        assert_no_forbidden_buttons(page)

        open_page(page, "/advisor/journal", "复盘记录")
        expect_text(page, "聚宽模拟回测通过初筛")
        expect_text(page, "joinquant / strategy_ai_compute_breakout")
        assert_no_forbidden_buttons(page)

        browser.close()

    if console_errors:
        raise AssertionError("browser console errors:\n" + "\n".join(console_errors[:20]))


def main() -> None:
    seed_advisor_flow()
    today = api_json(f"/api/advisor/today-snapshot?portfolio_id=cn_a_main&as_of_date={AS_OF_DATE}", method="GET")
    if not today.get("research_only") or today.get("live_trading"):
        raise AssertionError("advisor today snapshot violated research-only guardrail")
    run_browser_checks()
    print("advisor action-display browser acceptance passed")


if __name__ == "__main__":
    main()
