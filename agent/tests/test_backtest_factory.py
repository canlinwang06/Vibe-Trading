"""PR-11 tests for batch backtest factory outputs."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.strategy_lab.backtest_factory import BacktestFactoryError, BacktestFactoryService
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
                [row[0], row[1], row[2], row[3], row[4], row[5], row[7], row[6], "PR-11 test candidate"],
            )
        tickers = ["300308.SZ", "000977.SZ", "601138.SH", "600519.SH", "000300.SH"]
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


def test_batch_backtest_writes_runs_and_artifacts(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    store: AShareDataStore,
) -> None:
    strategy_lab.seed_strategy_specs()
    _seed_candidates_and_market(store)

    result = backtest_factory.run_backtest_batch(
        start_date="2026-06-16",
        end_date="2026-06-23",
        as_of_date="2026-06-22",
        limit=3,
    )
    runs = backtest_factory.list_backtest_runs(limit=10)

    assert result["status"] == "ok"
    assert result["runs_written"] == 3
    assert len(runs) == 3
    assert runs[0]["status"] == "completed"
    assert runs[0]["market"] == "CN_A"
    assert runs[0]["trade_count"] > 0
    assert runs[0]["artifacts_path"]

    artifact = Path(runs[0]["artifacts_path"]) / "run.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["assumptions"]["long_only"] is True
    assert payload["assumptions"]["lot_size"] == 100
    assert payload["assumptions"]["live_trading"] is False
    assert payload["universe"]

    loaded = backtest_factory.get_backtest_run(runs[0]["run_id"])
    assert loaded["run_id"] == runs[0]["run_id"]


def test_batch_backtest_returns_chinese_error_without_candidates(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
) -> None:
    strategy_lab.seed_strategy_specs()

    with pytest.raises(BacktestFactoryError, match="没有可回测的候选池"):
        backtest_factory.run_backtest_batch(start_date="2026-06-16", end_date="2026-06-23")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_strategy_lab_backtest_api_round_trip(client: TestClient) -> None:
    assert client.post("/api/strategy-lab/specs/seed", json={"replace": False}).status_code == 200
    store = AShareDataStore()
    _seed_candidates_and_market(store)

    batch = client.post(
        "/api/strategy-lab/backtest-batch",
        json={
            "start_date": "2026-06-16",
            "end_date": "2026-06-23",
            "as_of_date": "2026-06-22",
            "limit": 2,
        },
    )
    assert batch.status_code == 200
    assert batch.json()["runs_written"] == 2

    runs = client.get("/api/strategy-lab/backtest-runs")
    assert runs.status_code == 200
    assert runs.json()["run_count"] == 2

    run_id = runs.json()["backtest_runs"][0]["run_id"]
    detail = client.get(f"/api/strategy-lab/backtest-runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id


def test_strategy_lab_backtest_api_returns_chinese_error_without_candidates(client: TestClient) -> None:
    response = client.post(
        "/api/strategy-lab/backtest-batch",
        json={"start_date": "2026-06-16", "end_date": "2026-06-23", "limit": 2},
    )

    assert response.status_code == 400
    assert "没有可回测的候选池" in response.json()["detail"]
