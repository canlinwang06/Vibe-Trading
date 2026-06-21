"""Tests for Codex-directed advisor holdings and transaction recording."""

from __future__ import annotations

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

    assert client.post("/api/advisor/place-order", json={}).status_code == 404

