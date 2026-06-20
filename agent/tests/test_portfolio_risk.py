"""PR-13 tests for portfolio-risk strategy allocation."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.portfolio_risk.service import PortfolioRiskError, PortfolioRiskService
from src.strategy_lab.backtest_factory import BacktestFactoryService
from src.strategy_lab.service import StrategyLabService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def strategy_lab(store: AShareDataStore) -> StrategyLabService:
    return StrategyLabService(store=store)


@pytest.fixture
def backtest_factory(store: AShareDataStore) -> BacktestFactoryService:
    return BacktestFactoryService(store=store)


@pytest.fixture
def portfolio_risk(store: AShareDataStore) -> PortfolioRiskService:
    return PortfolioRiskService(store=store)


def _trading_dates() -> list[date]:
    start = date(2026, 6, 16)
    return [start + timedelta(days=idx) for idx in range(8)]


def _seed_candidates_and_market(store: AShareDataStore) -> None:
    store.initialize()
    candidates = [
        ("300308.SZ", "中际旭创", "sector_radar", "theme_ai_compute", "AI算力", "AI算力", 0.82, 0.71),
        ("000977.SZ", "浪潮信息", "sector_radar", "theme_ai_compute", "AI算力", "AI算力", 0.76, 0.71),
        ("601138.SH", "工业富联", "sector_radar", "theme_ai_compute", "AI算力", "AI算力", 0.70, 0.71),
        (
            "688111.SH",
            "金山办公",
            "sector_radar",
            "theme_ai_application",
            "AI应用",
            "AI应用",
            0.68,
            0.64,
        ),
        (
            "600519.SH",
            "贵州茅台",
            "user_added",
            "theme_media_consumption",
            "文娱消费",
            "文娱消费",
            0.66,
            0.48,
        ),
    ]
    with store.connect() as conn:
        for row in candidates:
            conn.execute(
                """
                INSERT INTO candidate_pool (
                  as_of_date, ticker, ticker_name, source, sector_id, sector_name,
                  theme, event_heat_score, sector_heat_score, stock_score,
                  user_priority, risk_flag, included, reason, created_at
                )
                VALUES (DATE '2026-06-22', ?, ?, ?, ?, ?, ?, 0.62, ?, ?, 0, 'normal', true, ?, now())
                """,
                [row[0], row[1], row[2], row[3], row[4], row[5], row[7], row[6], "PR-13 test candidate"],
            )
        tickers = ["300308.SZ", "000977.SZ", "601138.SH", "688111.SH", "600519.SH", "000300.SH"]
        for offset, ticker in enumerate(tickers):
            for idx, trade_date in enumerate(_trading_dates()):
                base = 30 + offset * 8
                close = base * (1 + idx * (0.012 + offset * 0.001))
                conn.execute(
                    """
                    INSERT INTO market_daily (
                      trade_date, ticker, open, high, low, close, volume, amount,
                      turnover, adj_factor, limit_status, suspended, source, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 'normal', false, 'unit_test', now())
                    """,
                    [
                        trade_date,
                        ticker,
                        close * 0.99,
                        close * 1.02,
                        close * 0.98,
                        close,
                        1_000_000 + idx * 100_000,
                        200_000_000 + offset * 30_000_000 + idx * 10_000_000,
                        0.02 + idx * 0.001,
                    ],
                )


def _seed_backtest_runs(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    store: AShareDataStore,
    *,
    limit: int = 12,
) -> None:
    strategy_lab.seed_strategy_specs()
    _seed_candidates_and_market(store)
    backtest_factory.run_backtest_batch(
        start_date="2026-06-16",
        end_date="2026-06-23",
        as_of_date="2026-06-22",
        limit=limit,
    )


def test_portfolio_allocation_writes_strategy_weights_and_respects_caps(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    portfolio_risk: PortfolioRiskService,
    store: AShareDataStore,
) -> None:
    _seed_backtest_runs(strategy_lab, backtest_factory, store)

    result = portfolio_risk.allocate(
        portfolio_id="cn_a_main",
        as_of_date="2026-06-23",
        top_n=5,
        max_strategy_weight=0.30,
        max_strategy_type_weight=0.50,
    )
    allocations = result["strategy_allocations"]
    type_weights: defaultdict[str, float] = defaultdict(float)
    for row in allocations:
        type_weights[row["strategy_type"]] += row["allocated_weight"]

    assert result["status"] == "draft"
    assert 3 <= result["allocation_count"] <= 5
    assert result["allocated_exposure"] <= result["model_total_exposure"]
    assert result["cash_weight"] == pytest.approx(1 - result["allocated_exposure"])
    assert all(row["allocated_weight"] <= 0.30 for row in allocations)
    assert all(weight <= 0.50 for weight in type_weights.values())
    assert all(row["strategy_score"] > 0 for row in allocations)

    persisted = portfolio_risk.list_allocations(portfolio_id="cn_a_main", as_of_date="2026-06-23")
    assert len(persisted) == len(allocations)
    assert persisted[0]["allocated_weight"] >= persisted[-1]["allocated_weight"]


def test_portfolio_trade_plan_outputs_draft_target_positions(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    portfolio_risk: PortfolioRiskService,
    store: AShareDataStore,
) -> None:
    _seed_backtest_runs(strategy_lab, backtest_factory, store)
    portfolio_risk.allocate(portfolio_id="cn_a_main", as_of_date="2026-06-23", top_n=5)

    plan = portfolio_risk.trade_plan(
        portfolio_id="cn_a_main",
        as_of_date="2026-06-23",
        max_single_stock_weight=0.10,
        max_sector_weight=0.40,
    )

    assert plan["status"] == "draft"
    assert plan["approval_status"] == "draft_not_generated"
    assert plan["requires_human_confirmation"] is True
    assert plan["live_trading"] is False
    assert plan["target_positions"]
    assert all(row["target_weight"] <= 0.10 for row in plan["target_positions"])
    assert all(row["action"] == "draft_target" for row in plan["target_positions"])

    with store.connect(read_only=True) as conn:
        signal_count = conn.execute("SELECT COUNT(*) FROM execution_signals").fetchone()[0]
    assert signal_count == 0


def test_portfolio_generate_draft_signals_and_approve_for_simulation(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    portfolio_risk: PortfolioRiskService,
    store: AShareDataStore,
) -> None:
    _seed_backtest_runs(strategy_lab, backtest_factory, store)
    portfolio_risk.allocate(portfolio_id="cn_a_main", as_of_date="2026-06-23", top_n=5)

    draft = portfolio_risk.generate_draft_signals(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        valid_for="2026-06-24",
        current_positions={},
    )

    assert draft["status"] == "draft"
    assert draft["signals_written"] > 0
    assert draft["valid_for"] == "2026-06-24"
    assert all(row["status"] == "draft" for row in draft["execution_signals"])
    assert all(row["action"] == "buy" for row in draft["execution_signals"])
    assert all(row["approved_at"] is None for row in draft["execution_signals"])

    listed = portfolio_risk.list_signals(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        status="draft",
    )
    assert len(listed) == draft["signals_written"]

    with pytest.raises(PortfolioRiskError, match="审批前必须确认风险提示"):
        portfolio_risk.approve_plan(portfolio_id="cn_a_main", signal_date="2026-06-23")

    approved = portfolio_risk.approve_plan(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        confirm_risk=True,
        simulation_only=True,
    )

    assert approved["status"] == "approved"
    assert approved["approved_count"] == draft["signals_written"]
    assert approved["simulation_only"] is True
    assert approved["export_enabled"] is False
    assert approved["live_trading"] is False
    assert all(row["status"] == "approved" for row in approved["execution_signals"])
    assert all(row["approved_at"] for row in approved["execution_signals"])

    approved_plan = portfolio_risk.trade_plan(portfolio_id="cn_a_main", as_of_date="2026-06-23")
    assert approved_plan["approval_status"] == "approved_for_simulation"

    with pytest.raises(PortfolioRiskError, match="不能覆盖"):
        portfolio_risk.generate_draft_signals(portfolio_id="cn_a_main", signal_date="2026-06-23")


def test_portfolio_approval_rejects_live_execution_request(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    portfolio_risk: PortfolioRiskService,
    store: AShareDataStore,
) -> None:
    _seed_backtest_runs(strategy_lab, backtest_factory, store)
    portfolio_risk.allocate(portfolio_id="cn_a_main", as_of_date="2026-06-23", top_n=5)
    portfolio_risk.generate_draft_signals(portfolio_id="cn_a_main", signal_date="2026-06-23")

    with pytest.raises(PortfolioRiskError, match="仅支持模拟审批"):
        portfolio_risk.approve_plan(
            portfolio_id="cn_a_main",
            signal_date="2026-06-23",
            confirm_risk=True,
            simulation_only=False,
        )


def test_portfolio_allocation_risk_off_returns_cash_only(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    portfolio_risk: PortfolioRiskService,
    store: AShareDataStore,
) -> None:
    _seed_backtest_runs(strategy_lab, backtest_factory, store)

    result = portfolio_risk.allocate(
        portfolio_id="cn_a_main",
        as_of_date="2026-06-23",
        current_drawdown=-0.10,
    )

    assert result["status"] == "risk_off"
    assert result["allocated_exposure"] == 0.0
    assert result["cash_weight"] == 1.0
    assert result["risk_rules"][-1]["triggered"] is True


def test_portfolio_allocation_returns_chinese_error_without_rankings(
    portfolio_risk: PortfolioRiskService,
) -> None:
    with pytest.raises(PortfolioRiskError, match="没有可分配的回测结果|没有可分配的策略"):
        portfolio_risk.allocate(as_of_date="2026-06-23")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_portfolio_risk_api_round_trip(client: TestClient) -> None:
    assert client.post("/api/strategy-lab/specs/seed", json={"replace": False}).status_code == 200
    store = AShareDataStore()
    _seed_candidates_and_market(store)
    batch = client.post(
        "/api/strategy-lab/backtest-batch",
        json={
            "start_date": "2026-06-16",
            "end_date": "2026-06-23",
            "as_of_date": "2026-06-22",
            "limit": 10,
        },
    )
    assert batch.status_code == 200

    allocated = client.post(
        "/api/portfolio-risk/allocate",
        json={"portfolio_id": "cn_a_main", "as_of_date": "2026-06-23", "top_n": 5},
    )
    assert allocated.status_code == 200
    assert allocated.json()["allocation_count"] >= 3

    allocations = client.get("/api/portfolio-risk/allocations?portfolio_id=cn_a_main")
    assert allocations.status_code == 200
    assert allocations.json()["allocation_count"] == allocated.json()["allocation_count"]

    plan = client.get("/api/portfolio-risk/trade-plan?portfolio_id=cn_a_main")
    assert plan.status_code == 200
    assert plan.json()["target_positions"]
    assert plan.json()["research_only"] is True

    draft = client.post(
        "/api/portfolio-risk/generate-signals",
        json={
            "portfolio_id": "cn_a_main",
            "signal_date": "2026-06-23",
            "valid_for": "2026-06-24",
        },
    )
    assert draft.status_code == 200
    assert draft.json()["signals_written"] > 0

    signals = client.get("/api/portfolio-risk/signals?portfolio_id=cn_a_main&status=draft")
    assert signals.status_code == 200
    assert signals.json()["signal_count"] == draft.json()["signals_written"]

    rejected = client.post(
        "/api/portfolio-risk/approve-plan",
        json={"portfolio_id": "cn_a_main", "signal_date": "2026-06-23", "confirm_risk": False},
    )
    assert rejected.status_code == 400
    assert "确认风险提示" in rejected.json()["detail"]

    approved = client.post(
        "/api/portfolio-risk/approve-plan",
        json={
            "portfolio_id": "cn_a_main",
            "signal_date": "2026-06-23",
            "confirm_risk": True,
            "simulation_only": True,
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["export_enabled"] is False
    assert approved.json()["live_trading"] is False


def test_portfolio_risk_api_returns_chinese_error_without_allocations(client: TestClient) -> None:
    response = client.get("/api/portfolio-risk/trade-plan?portfolio_id=cn_a_main")

    assert response.status_code == 400
    assert "没有策略分配结果" in response.json()["detail"]
