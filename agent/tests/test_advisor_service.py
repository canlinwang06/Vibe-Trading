"""Tests for Codex-directed advisor holdings and transaction recording."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.advisor.service import AdvisorError, AdvisorService
from src.ashare_data.store import AShareDataStore

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def service(store: AShareDataStore) -> AdvisorService:
    return AdvisorService(store=store)


def test_advisor_buy_creates_portfolio_position_lot_thesis_and_command_event(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    result = service.record_transaction(
        portfolio_id="cn_a_main",
        ticker="300308.SZ",
        ticker_name="中际旭创",
        action="buy",
        price=10.2,
        quantity=300,
        trade_date="2026-06-21",
        strategy_type="hotspot_momentum",
        strategy_cycle="short",
        thesis="AI 算力景气度提升，观察光模块龙头弹性。",
        stop_loss_price=9.6,
        take_profit_price=12.0,
        reason="Codex 口头记录买入事实。",
        idempotency_key="advisor-buy-300308-20260621",
    )

    assert result["status"] == "ok"
    assert result["research_only"] is True
    assert result["live_trading"] is False
    assert result["position"]["ticker"] == "300308.SZ"
    assert result["position"]["total_quantity"] == 300
    assert result["position"]["average_cost"] == 10.2

    with store.connect(read_only=True) as conn:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "portfolios",
                "positions",
                "advisor_transactions",
                "position_lots",
                "investment_theses",
                "advisor_command_events",
            )
        }
    assert counts == {
        "portfolios": 1,
        "positions": 1,
        "advisor_transactions": 1,
        "position_lots": 1,
        "investment_theses": 1,
        "advisor_command_events": 1,
    }


def test_advisor_transaction_idempotency_prevents_duplicate_codex_retries(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    payload = {
        "portfolio_id": "cn_a_main",
        "ticker": "000977.SZ",
        "ticker_name": "浪潮信息",
        "action": "buy",
        "price": 38.5,
        "quantity": 100,
        "trade_date": "2026-06-21",
        "idempotency_key": "same-codex-command",
    }

    first = service.record_transaction(**payload)
    second = service.record_transaction(**payload)

    assert first["position"]["total_quantity"] == 100
    assert second["idempotent_replay"] is True
    assert second["position"]["total_quantity"] == 100
    with store.connect(read_only=True) as conn:
        transaction_count = conn.execute("SELECT COUNT(*) FROM advisor_transactions").fetchone()[0]
        command_count = conn.execute("SELECT COUNT(*) FROM advisor_command_events").fetchone()[0]
    assert transaction_count == 1
    assert command_count == 1


def test_advisor_sell_updates_partial_and_closed_position(service: AdvisorService, store: AShareDataStore) -> None:
    service.record_transaction(
        ticker="601138.SH",
        ticker_name="工业富联",
        action="buy",
        price=25.0,
        quantity=300,
        trade_date="2026-06-18",
        idempotency_key="buy-601138",
    )
    partial = service.record_transaction(
        ticker="601138.SH",
        ticker_name="工业富联",
        action="sell",
        price=27.0,
        quantity=100,
        trade_date="2026-06-21",
        idempotency_key="sell-601138-partial",
    )
    assert partial["position"]["status"] == "open"
    assert partial["position"]["total_quantity"] == 200
    assert service.list_positions()[0]["ticker"] == "601138.SH"

    closed = service.record_transaction(
        ticker="601138.SH",
        ticker_name="工业富联",
        action="sell",
        price=28.0,
        quantity=200,
        trade_date="2026-06-22",
        idempotency_key="sell-601138-closed",
    )
    assert closed["position"]["status"] == "closed"
    assert closed["position"]["total_quantity"] == 0
    assert service.list_positions() == []
    assert service.list_positions(include_closed=True)[0]["status"] == "closed"
    with store.connect(read_only=True) as conn:
        remaining = conn.execute("SELECT SUM(remaining_quantity) FROM position_lots").fetchone()[0]
        transaction_count = conn.execute("SELECT COUNT(*) FROM advisor_transactions").fetchone()[0]
    assert remaining == 0
    assert transaction_count == 3


def test_advisor_complete_thesis_links_to_existing_position(service: AdvisorService, store: AShareDataStore) -> None:
    service.record_transaction(
        ticker="300308.SZ",
        ticker_name="中际旭创",
        action="buy",
        price=10.2,
        quantity=300,
        trade_date="2026-06-21",
        idempotency_key="buy-300308-before-thesis",
    )

    thesis = service.upsert_thesis(
        ticker="300308.SZ",
        ticker_name="中际旭创",
        strategy_type="短期热点趋势",
        strategy_cycle="short",
        thesis="AI 算力热点扩散，光模块龙头具备弹性。",
        buy_reason="板块热度上升且个股处于观察区间。",
        entry_conditions="放量站上 10 日线且板块热度维持高位。",
        exit_conditions="跌破 20 日线或板块热度连续两日退潮。",
        not_buy_conditions="高开超过 7% 或成交额明显缩量不买。",
        stop_loss_price=9.5,
        take_profit_price=12.8,
        max_position_pct=0.12,
        target_holding_days=10,
        review_frequency_days=3,
        as_of_date="2026-06-21",
        evidence={"sources": ["unit-test"]},
    )

    assert thesis["completeness_status"] == "complete"
    assert thesis["strategy_type"] == "short_hotspot_momentum"
    assert thesis["strategy_type_label"] == "短期热点趋势"
    assert thesis["can_enter_ready_to_buy"] is True
    assert thesis["next_review_date"] == "2026-06-24"
    assert thesis["bound_position"]["ticker"] == "300308.SZ"
    assert thesis["bound_position"]["thesis_id"] == thesis["thesis_id"]
    assert service.list_theses(include_incomplete=False)[0]["thesis_id"] == thesis["thesis_id"]
    with store.connect(read_only=True) as conn:
        row = conn.execute(
            "SELECT thesis_id, next_review_date FROM positions WHERE ticker = '300308.SZ'"
        ).fetchone()
    assert row[0] == thesis["thesis_id"]
    assert row[1].isoformat() == "2026-06-24"


def test_advisor_thesis_without_exit_condition_is_incomplete(service: AdvisorService) -> None:
    thesis = service.upsert_thesis(
        ticker="000977.SZ",
        ticker_name="浪潮信息",
        strategy_type="中期景气趋势",
        buy_reason="服务器产业链景气度仍在观察。",
        entry_conditions="股价回踩均线后重新放量。",
        not_buy_conditions="业绩预期下修或板块扩散失败。",
        max_position_pct=0.10,
        target_holding_days=30,
        review_frequency_days=7,
        as_of_date="2026-06-21",
    )

    assert thesis["completeness_status"] == "incomplete"
    assert "退出条件" in thesis["missing_fields"]
    assert thesis["has_exit_condition"] is False
    assert thesis["can_enter_ready_to_buy"] is False
    assert service.list_theses(include_incomplete=False) == []


def _seed_market_price(
    store: AShareDataStore,
    *,
    ticker: str,
    ticker_name: str,
    trade_date: date,
    close: float,
    suspended: bool = False,
) -> None:
    store.initialize()
    with store.connect() as conn:
        conn.execute("DELETE FROM assets WHERE ticker = ?", [ticker])
        conn.execute(
            """
            INSERT INTO assets (ticker, ticker_name, exchange, asset_type, active, updated_at)
            VALUES (?, ?, ?, 'stock', true, now())
            """,
            [ticker, ticker_name, ticker.split(".")[1]],
        )
        conn.execute(
            "DELETE FROM market_daily WHERE trade_date = ? AND ticker = ?",
            [trade_date, ticker],
        )
        conn.execute(
            """
            INSERT INTO market_daily (
              trade_date, ticker, open, high, low, close, volume, amount,
              turnover, adj_factor, limit_status, suspended, source, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1000000, 50000000, 0.03, 1.0, 'normal', ?, 'unit_test', now())
            """,
            [trade_date, ticker, close * 0.98, close * 1.02, close * 0.97, close, suspended],
        )


def test_advisor_price_resolver_returns_latest_trade_date_price(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_market_price(
        store,
        ticker="300308.SZ",
        ticker_name="中际旭创",
        trade_date=date(2026, 6, 19),
        close=88.5,
    )

    result = service.resolve_prices(tickers=["300308.SZ"], as_of_date="2026-06-19")
    price = result["prices"][0]

    assert price["close"] == 88.5
    assert price["data_date"] == "2026-06-19"
    assert price["is_latest"] is True
    assert price["freshness_status"] == "latest"
    assert price["source"] == "unit_test"


def test_advisor_price_resolver_marks_weekend_recent_trade_data(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_market_price(
        store,
        ticker="000977.SZ",
        ticker_name="浪潮信息",
        trade_date=date(2026, 6, 19),
        close=42.0,
    )

    result = service.resolve_prices(tickers=["000977.SZ"], as_of_date="2026-06-21")
    price = result["prices"][0]

    assert price["is_latest"] is False
    assert price["days_lag"] == 2
    assert price["freshness_status"] == "non_trading_day_recent"
    assert "最近交易日" in price["freshness_reason"]


def test_advisor_price_resolver_degrades_when_data_missing(service: AdvisorService) -> None:
    result = service.resolve_prices(tickers=["601138.SH"], as_of_date="2026-06-21")
    price = result["prices"][0]

    assert price["freshness_status"] == "missing"
    assert price["close"] is None
    assert "缺少可用行情数据" in price["freshness_reason"]


def _seed_complete_holding(
    service: AdvisorService,
    store: AShareDataStore,
    *,
    ticker: str = "300308.SZ",
    ticker_name: str = "中际旭创",
    close: float = 10.8,
    price_date: date = date(2026, 6, 22),
    stop_loss_price: float = 9.5,
    take_profit_price: float = 12.8,
) -> None:
    service.record_transaction(
        ticker=ticker,
        ticker_name=ticker_name,
        action="buy",
        price=10.2,
        quantity=300,
        trade_date="2026-06-21",
        idempotency_key=f"buy-{ticker}-diagnosis",
    )
    _seed_market_price(
        store,
        ticker=ticker,
        ticker_name=ticker_name,
        trade_date=price_date,
        close=close,
    )
    service.upsert_thesis(
        ticker=ticker,
        ticker_name=ticker_name,
        strategy_type="短期热点趋势",
        strategy_cycle="short",
        thesis="AI 算力热点扩散，光模块龙头具备弹性。",
        buy_reason="板块热度上升且个股处于观察区间。",
        entry_conditions="放量站上 10 日线且板块热度维持高位。",
        exit_conditions="跌破 20 日线或板块热度连续两日退潮。",
        not_buy_conditions="高开超过 7% 或成交额明显缩量不买。",
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        max_position_pct=0.12,
        target_holding_days=10,
        review_frequency_days=3,
        as_of_date="2026-06-21",
    )


def test_advisor_holding_diagnosis_outputs_hold_and_sell_line(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_complete_holding(service, store)

    result = service.diagnose_holdings(as_of_date="2026-06-22")
    diagnostic = result["diagnostics"][0]

    assert diagnostic["action"] == "hold"
    assert diagnostic["action_label"] == "继续持有"
    assert diagnostic["sell_line"]["hard_stop_price"] == 9.5
    assert diagnostic["sell_line"]["take_profit_price"] == 12.8
    assert "硬止损" in diagnostic["reason"]
    assert diagnostic["research_only"] is True
    with store.connect(read_only=True) as conn:
        saved = conn.execute("SELECT action_type FROM advisor_action_recommendations").fetchone()
    assert saved[0] == "hold"


def test_advisor_holding_diagnosis_triggers_exit_on_hard_stop(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_complete_holding(service, store, close=9.4)

    result = service.diagnose_holdings(as_of_date="2026-06-22")
    diagnostic = result["diagnostics"][0]

    assert diagnostic["action"] == "exit"
    assert diagnostic["action_label"] == "触发退出"
    assert "硬止损价" in diagnostic["trigger_price_or_condition"]
    assert "不只是简单下跌" in diagnostic["reason"]


def test_advisor_holding_diagnosis_requires_thesis_before_specific_sell_price(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    service.record_transaction(
        ticker="601138.SH",
        ticker_name="工业富联",
        action="buy",
        price=25.0,
        quantity=100,
        trade_date="2026-06-21",
        idempotency_key="buy-601138-no-thesis",
    )
    _seed_market_price(
        store,
        ticker="601138.SH",
        ticker_name="工业富联",
        trade_date=date(2026, 6, 22),
        close=26.0,
    )

    result = service.diagnose_holdings(as_of_date="2026-06-22")
    diagnostic = result["diagnostics"][0]

    assert diagnostic["action"] == "complete_thesis"
    assert diagnostic["sell_line"] is None
    assert "不编造具体卖出价" in diagnostic["reason"]


def test_advisor_holding_diagnosis_is_cautious_with_stale_price(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_complete_holding(service, store, close=10.8, price_date=date(2026, 6, 1))

    result = service.diagnose_holdings(as_of_date="2026-06-22", stale_after_days=5)
    diagnostic = result["diagnostics"][0]

    assert diagnostic["action"] == "observe"
    assert diagnostic["action_label"] == "谨慎观察"
    assert diagnostic["price"]["freshness_status"] == "stale"
    assert "行情数据不新" in diagnostic["reason"]


def _seed_watchlist_candidate(
    service: AdvisorService,
    store: AShareDataStore,
    *,
    ticker: str = "000977.SZ",
    ticker_name: str = "浪潮信息",
    close: float = 40.0,
    trigger_price: float = 42.0,
    include_exit: bool = True,
) -> None:
    _seed_market_price(
        store,
        ticker=ticker,
        ticker_name=ticker_name,
        trade_date=date(2026, 6, 22),
        close=close,
    )
    service.upsert_thesis(
        ticker=ticker,
        ticker_name=ticker_name,
        strategy_type="短期热点趋势",
        strategy_cycle="short",
        thesis="AI 算力服务器链条热点扩散。",
        buy_reason="板块热度上升，个股等待放量确认。",
        entry_conditions="放量突破触发价且板块热度不退潮。",
        exit_conditions="跌破 20 日线或板块热度退潮。" if include_exit else None,
        not_buy_conditions="高开超过 6% 或量能不足不买。",
        stop_loss_price=trigger_price * 0.92 if include_exit else None,
        max_position_pct=0.10,
        target_holding_days=8,
        review_frequency_days=3,
        as_of_date="2026-06-21",
    )
    service.upsert_watchlist_item(
        ticker=ticker,
        ticker_name=ticker_name,
        theme="AI算力",
        trigger_price=trigger_price,
        max_position_pct=0.10,
        not_buy_conditions="高开超过 6% 或量能不足不买。",
        reason="等待服务器链条确认买点。",
    )


def test_advisor_watchlist_candidate_waits_for_trigger(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=40.0, trigger_price=42.0)

    result = service.build_watchlist_candidates(as_of_date="2026-06-22")
    candidate = result["candidates"][0]

    assert candidate["suggested_status"] == "waiting_trigger"
    assert candidate["buy_trigger_price"] == 42.0
    assert "放量突破" in candidate["buy_trigger_condition"]
    assert "高开超过" in candidate["not_buy_conditions"]
    assert candidate["target_holding_days"] == 8


def test_advisor_watchlist_candidate_includes_lot_sizing(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=42.2, trigger_price=42.0)
    with store.connect() as conn:
        conn.execute(
            "UPDATE portfolios SET initial_cash = 100000, cash_balance = 100000 WHERE portfolio_id = 'cn_a_main'"
        )

    result = service.build_watchlist_candidates(as_of_date="2026-06-22")
    candidate = result["candidates"][0]

    assert candidate["position_budget"] == 10000.0
    assert candidate["sizing_price"] == 42.0
    assert candidate["suggested_buy_shares"] == 200
    assert candidate["suggested_buy_amount"] == 8400.0
    assert candidate["risk_amount_at_stop"] == 672.0


def test_advisor_watchlist_candidate_can_be_small_probe_only_with_exit_condition(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=42.2, trigger_price=42.0)

    result = service.build_watchlist_candidates(as_of_date="2026-06-22")
    candidate = result["candidates"][0]

    assert candidate["suggested_status"] == "ready_small_probe"
    assert candidate["suggested_status_label"] == "可小仓试探"
    assert candidate["evidence"]["has_exit_condition"] is True


def test_advisor_watchlist_candidate_without_exit_condition_cannot_be_small_probe(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=42.2, trigger_price=42.0, include_exit=False)

    result = service.build_watchlist_candidates(as_of_date="2026-06-22")
    candidate = result["candidates"][0]

    assert candidate["suggested_status"] == "needs_exit_condition"
    assert candidate["suggested_status_label"] == "补充退出条件"
    assert "不能进入可小仓试探" in candidate["reason"]


def test_advisor_watchlist_candidates_can_include_candidate_pool_sources(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    store.initialize()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO candidate_pool (
              as_of_date, ticker, ticker_name, source, sector_id, sector_name,
              theme, stock_score, risk_flag, included, reason, created_at
            )
            VALUES (
              DATE '2026-06-22', '601138.SH', '工业富联', 'sector_radar',
              'theme_ai_compute', 'AI算力', 'AI算力', 0.76, 'normal', true,
              '板块热度上升带来的候选。', now()
            )
            """
        )
    _seed_market_price(
        store,
        ticker="601138.SH",
        ticker_name="工业富联",
        trade_date=date(2026, 6, 22),
        close=26.0,
    )

    result = service.build_watchlist_candidates(as_of_date="2026-06-22")
    candidate = result["candidates"][0]

    assert candidate["ticker"] == "601138.SH"
    assert candidate["source"] == "sector_radar"
    assert candidate["theme"] == "AI算力"
    assert candidate["suggested_status"] == "needs_exit_condition"


def test_advisor_risk_filter_flags_chase_risk(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=46.0, trigger_price=42.0)

    result = service.build_risk_filters(as_of_date="2026-06-22")
    rule_ids = {item["rule_id"] for item in result["do_not_buy_items"]}

    assert "chase_risk" in rule_ids
    assert result["scope"] == "current_stage_risk_only"
    assert any("当前阶段暂不追高" in item["reason"] for item in result["do_not_buy_items"])


def test_advisor_risk_filter_flags_missing_exit_condition(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=42.2, trigger_price=42.0, include_exit=False)

    result = service.build_risk_filters(as_of_date="2026-06-22")
    rule_ids = {item["rule_id"] for item in result["do_not_buy_items"]}

    assert "missing_exit_condition" in rule_ids
    assert any("当前阶段暂不买" in item["reason"] for item in result["do_not_buy_items"])


def test_advisor_risk_filter_flags_insufficient_evidence(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_market_price(
        store,
        ticker="002230.SZ",
        ticker_name="科大讯飞",
        trade_date=date(2026, 6, 22),
        close=50.0,
    )
    service.upsert_watchlist_item(
        ticker="002230.SZ",
        ticker_name="科大讯飞",
        trigger_price=51.0,
        reason=None,
    )

    result = service.build_risk_filters(as_of_date="2026-06-22")
    rule_ids = {item["rule_id"] for item in result["do_not_buy_items"]}

    assert "insufficient_evidence" in rule_ids
    assert "missing_not_buy_condition" in rule_ids


def test_advisor_risk_filter_flags_holding_overlap(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=42.2, trigger_price=42.0)
    service.record_transaction(
        ticker="000977.SZ",
        ticker_name="浪潮信息",
        action="buy",
        price=38.0,
        quantity=100,
        trade_date="2026-06-21",
        idempotency_key="buy-overlap-000977",
    )

    candidates = service.build_watchlist_candidates(as_of_date="2026-06-22")
    result = service.build_risk_filters(as_of_date="2026-06-22")
    rule_ids = {item["rule_id"] for item in result["do_not_buy_items"]}

    assert candidates["candidates"][0]["suggested_status"] == "risk_high"
    assert "holding_overlap" in rule_ids


def test_advisor_alerts_generate_and_status_flow(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_complete_holding(service, store, close=9.4)

    result = service.generate_alerts(as_of_date="2026-06-22")
    sell_alert = next(alert for alert in result["alerts"] if alert["alert_type"] == "sell_line_touched")

    assert sell_alert["severity"] == "high"
    assert sell_alert["title"] == "触及卖出线"
    assert sell_alert["status"] == "open"
    assert sell_alert["ticker"] == "300308.SZ"
    assert service.list_alerts(status="open")[0]["alert_id"] == sell_alert["alert_id"]

    acknowledged = service.update_alert_status(alert_id=sell_alert["alert_id"], status="acknowledged")
    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["acknowledged_at"] is not None

    closed = service.update_alert_status(alert_id=sell_alert["alert_id"], status="closed")
    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None
    assert service.list_alerts(status="open") == []


def test_advisor_decision_journal_is_written_and_visible_in_snapshot(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_complete_holding(service, store, close=9.4)
    alerts = service.generate_alerts(as_of_date="2026-06-22")
    sell_alert = next(alert for alert in alerts["alerts"] if alert["alert_type"] == "sell_line_touched")

    journal = service.write_decision_journal(
        decision_date="2026-06-22",
        subject_type="alert",
        subject_id=sell_alert["alert_id"],
        ticker="300308.SZ",
        ticker_name="中际旭创",
        decision="accept_exit_plan",
        user_intent="先按助手建议减仓观察。",
        codex_explanation="价格触及硬止损线，原短线热点假设需要重新验证。",
        review_notes="等待下一交易日验证是否继续退潮。",
        evidence={"alert_id": sell_alert["alert_id"]},
    )
    snapshot = service.journal_snapshot(limit=20)

    assert journal["decision"] == "accept_exit_plan"
    assert journal["codex_explanation"].startswith("价格触及硬止损线")
    assert snapshot["decision_journals"][0]["journal_id"] == journal["journal_id"]
    assert any(alert["alert_id"] == sell_alert["alert_id"] for alert in snapshot["alerts"])


def test_advisor_external_validation_writeback_is_visible_in_journal_snapshot(
    service: AdvisorService,
) -> None:
    first = service.record_external_validation(
        source="joinquant",
        source_ref="jq-run-ai-compute-001",
        subject_type="strategy",
        subject_id="strategy_ai_compute_breakout",
        validation_date="2026-06-22",
        status="passed",
        metrics={"annual_return": 0.18, "max_drawdown": -0.08, "sharpe": 1.35},
        summary="AI 算力突破策略在聚宽模拟回测中通过初筛。",
        raw_result={"period": "2024-01-01~2026-06-22"},
    )
    second = service.record_external_validation(
        source="joinquant",
        source_ref="jq-run-ai-compute-001",
        subject_type="strategy",
        subject_id="strategy_ai_compute_breakout",
        validation_date="2026-06-22",
        status="passed",
        metrics={"annual_return": 0.2, "max_drawdown": -0.08, "sharpe": 1.42},
        summary="同一聚宽结果再次写回时覆盖为最新指标。",
    )
    validations = service.list_external_validations(subject_type="strategy")
    snapshot = service.journal_snapshot(limit=20)

    assert first["validation_id"] == second["validation_id"]
    assert validations[0]["metrics"]["annual_return"] == 0.2
    assert validations[0]["source"] == "joinquant"
    assert snapshot["external_validations"][0]["validation_id"] == second["validation_id"]
    assert "聚宽" in snapshot["external_validations"][0]["summary"]


def test_advisor_external_validation_can_downgrade_candidate_status(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_watchlist_candidate(service, store, close=42.2, trigger_price=42.0)
    service.record_external_validation(
        source="joinquant",
        source_ref="jq-run-risk-001",
        subject_type="ticker",
        subject_id="000977.SZ",
        validation_date="2026-06-22",
        status="failed",
        metrics={"annual_return": -0.06, "max_drawdown": -0.18},
        summary="模拟回测回撤超过当前筛选门槛。",
    )

    candidates = service.build_watchlist_candidates(as_of_date="2026-06-22")
    candidate = candidates["candidates"][0]
    risks = service.build_risk_filters(as_of_date="2026-06-22")
    rule_ids = {item["rule_id"] for item in risks["do_not_buy_items"]}

    assert candidate["suggested_status"] == "risk_high"
    assert candidate["suggested_status_label"] == "验证未通过"
    assert candidate["evidence"]["external_validation"]["source"] == "joinquant"
    assert "external_validation_failed" in rule_ids


def test_advisor_display_snapshots_are_page_ready(
    service: AdvisorService,
    store: AShareDataStore,
) -> None:
    _seed_complete_holding(service, store)
    _seed_watchlist_candidate(service, store, close=42.2, trigger_price=42.0)

    today = service.today_snapshot(as_of_date="2026-06-22")
    holdings = service.holdings_snapshot(as_of_date="2026-06-22")
    watchlist = service.watchlist_snapshot(as_of_date="2026-06-22")
    journal = service.journal_snapshot()

    assert today["title"] == "今日建议"
    assert today["summary_cards"]
    assert today["primary_actions"]
    assert any(card["label"] == "提醒" for card in today["summary_cards"])
    assert today["top_alerts"]
    assert holdings["title"] == "我的持仓"
    assert holdings["diagnostics"][0]["action"] == "hold"
    assert watchlist["title"] == "观察清单"
    assert watchlist["candidates"][0]["suggested_status"] == "ready_small_probe"
    assert journal["title"] == "复盘记录"
    assert journal["commands"]
    assert journal["recommendations"]
    with store.connect(read_only=True) as conn:
        snapshot_count = conn.execute("SELECT COUNT(*) FROM advisor_action_snapshots").fetchone()[0]
    assert snapshot_count == 4


def test_advisor_rejects_non_a_share_and_oversell(service: AdvisorService) -> None:
    with pytest.raises(AdvisorError, match="沪深 A 股"):
        service.record_transaction(ticker="AAPL.US", action="buy", price=100, quantity=1)

    service.record_transaction(
        ticker="600519.SH",
        ticker_name="贵州茅台",
        action="buy",
        price=1500,
        quantity=10,
        idempotency_key="buy-600519-small",
    )
    with pytest.raises(AdvisorError, match="卖出数量超过当前持仓"):
        service.record_transaction(
            ticker="600519.SH",
            ticker_name="贵州茅台",
            action="sell",
            price=1510,
            quantity=11,
            idempotency_key="sell-600519-too-much",
        )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_advisor_api_round_trip_and_no_order_endpoint(client: TestClient) -> None:
    buy = client.post(
        "/api/advisor/transactions",
        json={
            "portfolio_id": "cn_a_main",
            "ticker": "300750.SZ",
            "ticker_name": "宁德时代",
            "action": "buy",
            "price": 188.0,
            "quantity": 50,
            "trade_date": "2026-06-21",
            "idempotency_key": "api-buy-300750",
            "source_command": "我买入了 50 股宁德时代。",
        },
    )
    assert buy.status_code == 200
    assert buy.json()["live_trading"] is False

    positions = client.get("/api/advisor/positions", params={"portfolio_id": "cn_a_main"})
    assert positions.status_code == 200
    assert positions.json()["position_count"] == 1
    assert positions.json()["positions"][0]["ticker"] == "300750.SZ"

    summary = client.get("/api/advisor/portfolio-summary", params={"portfolio_id": "cn_a_main"})
    assert summary.status_code == 200
    assert summary.json()["position_count"] == 1
    assert summary.json()["research_only"] is True
    assert summary.json()["live_trading"] is False

    _seed_market_price(
        AShareDataStore(),
        ticker="300750.SZ",
        ticker_name="宁德时代",
        trade_date=date(2026, 6, 19),
        close=190.5,
    )
    prices = client.get(
        "/api/advisor/portfolio-prices",
        params={"portfolio_id": "cn_a_main", "as_of_date": "2026-06-21"},
    )
    assert prices.status_code == 200
    assert prices.json()["price_count"] == 1
    assert prices.json()["prices"][0]["close"] == 190.5
    assert prices.json()["prices"][0]["freshness_status"] == "non_trading_day_recent"

    thesis = client.post(
        "/api/advisor/theses",
        json={
            "portfolio_id": "cn_a_main",
            "ticker": "300750.SZ",
            "ticker_name": "宁德时代",
            "strategy_type": "中期景气趋势",
            "strategy_cycle": "medium",
            "thesis": "新能源产业链景气度修复候选。",
            "buy_reason": "基本面修复预期叠加价格回到观察区。",
            "entry_conditions": "放量突破近 20 日平台。",
            "exit_conditions": "跌破 20 日线或景气数据转弱。",
            "not_buy_conditions": "高开过多或板块退潮时不买。",
            "max_position_pct": 0.1,
            "target_holding_days": 30,
            "review_frequency_days": 7,
            "as_of_date": "2026-06-21",
        },
    )
    assert thesis.status_code == 200
    assert thesis.json()["completeness_status"] == "complete"
    assert thesis.json()["bound_position"]["ticker"] == "300750.SZ"

    theses = client.get("/api/advisor/theses", params={"portfolio_id": "cn_a_main"})
    assert theses.status_code == 200
    assert theses.json()["thesis_count"] == 1
    assert theses.json()["theses"][0]["can_enter_ready_to_buy"] is True

    diagnostics = client.get(
        "/api/advisor/holding-diagnostics",
        params={"portfolio_id": "cn_a_main", "as_of_date": "2026-06-21"},
    )
    assert diagnostics.status_code == 200
    assert diagnostics.json()["diagnostic_count"] == 1
    assert diagnostics.json()["diagnostics"][0]["action"] == "hold"
    assert diagnostics.json()["research_only"] is True
    assert diagnostics.json()["live_trading"] is False

    _seed_market_price(
        AShareDataStore(),
        ticker="000977.SZ",
        ticker_name="浪潮信息",
        trade_date=date(2026, 6, 19),
        close=42.2,
    )
    thesis_for_watchlist = client.post(
        "/api/advisor/theses",
        json={
            "portfolio_id": "cn_a_main",
            "ticker": "000977.SZ",
            "ticker_name": "浪潮信息",
            "strategy_type": "短期热点趋势",
            "strategy_cycle": "short",
            "thesis": "AI 算力服务器链条热点扩散。",
            "buy_reason": "板块热度上升，个股等待放量确认。",
            "entry_conditions": "放量突破触发价且板块热度不退潮。",
            "exit_conditions": "跌破 20 日线或板块热度退潮。",
            "not_buy_conditions": "高开超过 6% 或量能不足不买。",
            "max_position_pct": 0.1,
            "target_holding_days": 8,
            "review_frequency_days": 3,
            "as_of_date": "2026-06-21",
        },
    )
    assert thesis_for_watchlist.status_code == 200
    watchlist = client.post(
        "/api/advisor/watchlist",
        json={
            "portfolio_id": "cn_a_main",
            "ticker": "000977.SZ",
            "ticker_name": "浪潮信息",
            "theme": "AI算力",
            "trigger_price": 42.0,
            "max_position_pct": 0.1,
            "not_buy_conditions": "高开超过 6% 或量能不足不买。",
            "reason": "等待服务器链条确认买点。",
        },
    )
    assert watchlist.status_code == 200

    candidates = client.get(
        "/api/advisor/watchlist-candidates",
        params={"portfolio_id": "cn_a_main", "as_of_date": "2026-06-21"},
    )
    assert candidates.status_code == 200
    assert candidates.json()["candidate_count"] == 1
    assert candidates.json()["candidates"][0]["suggested_status"] == "ready_small_probe"
    assert candidates.json()["candidates"][0]["research_only"] is True

    risk_filters = client.get(
        "/api/advisor/risk-filters",
        params={"portfolio_id": "cn_a_main", "as_of_date": "2026-06-21"},
    )
    assert risk_filters.status_code == 200
    assert risk_filters.json()["scope"] == "current_stage_risk_only"
    assert risk_filters.json()["research_only"] is True

    alerts = client.post(
        "/api/advisor/alerts/generate",
        params={"portfolio_id": "cn_a_main", "as_of_date": "2026-06-21"},
    )
    assert alerts.status_code == 200
    assert alerts.json()["alert_count"] >= 1
    alert_id = alerts.json()["alerts"][0]["alert_id"]

    listed_alerts = client.get(
        "/api/advisor/alerts",
        params={"portfolio_id": "cn_a_main", "status": "open"},
    )
    assert listed_alerts.status_code == 200
    assert listed_alerts.json()["alerts"][0]["status"] == "open"

    alert_status = client.post(
        "/api/advisor/alerts/status",
        json={"alert_id": alert_id, "status": "acknowledged"},
    )
    assert alert_status.status_code == 200
    assert alert_status.json()["status"] == "acknowledged"

    decision = client.post(
        "/api/advisor/decision-journal",
        json={
            "portfolio_id": "cn_a_main",
            "decision_date": "2026-06-21",
            "subject_type": "alert",
            "subject_id": alert_id,
            "ticker": "000977.SZ",
            "ticker_name": "浪潮信息",
            "decision": "observe",
            "user_intent": "先观察，不直接买入。",
            "codex_explanation": "候选进入观察，但仍需要等下一次确认。",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["decision"] == "observe"

    validation = client.post(
        "/api/advisor/external-validations",
        json={
            "portfolio_id": "cn_a_main",
            "source": "joinquant",
            "source_ref": "jq-api-run-001",
            "subject_type": "strategy",
            "subject_id": "strategy_ai_compute_breakout",
            "validation_date": "2026-06-21",
            "status": "passed",
            "metrics": {"annual_return": 0.16, "max_drawdown": -0.07, "sharpe": 1.2},
            "summary": "聚宽模拟回测通过初筛，仍需人工复核交易成本假设。",
        },
    )
    assert validation.status_code == 200
    assert validation.json()["source"] == "joinquant"
    assert validation.json()["metrics"]["annual_return"] == 0.16

    validations = client.get(
        "/api/advisor/external-validations",
        params={"portfolio_id": "cn_a_main", "subject_type": "strategy"},
    )
    assert validations.status_code == 200
    assert validations.json()["validation_count"] == 1
    assert validations.json()["external_validations"][0]["status"] == "passed"

    for path, title in (
        ("/api/advisor/today-snapshot", "今日建议"),
        ("/api/advisor/holdings-snapshot", "我的持仓"),
        ("/api/advisor/watchlist-snapshot", "观察清单"),
        ("/api/advisor/journal-snapshot", "复盘记录"),
    ):
        snapshot = client.get(path, params={"portfolio_id": "cn_a_main", "as_of_date": "2026-06-21"})
        assert snapshot.status_code == 200
        assert snapshot.json()["title"] == title
        assert snapshot.json()["research_only"] is True
        assert snapshot.json()["live_trading"] is False

    assert client.post("/api/advisor/place-order", json={}).status_code == 404
