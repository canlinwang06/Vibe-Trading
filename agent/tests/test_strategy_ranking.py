"""PR-12 tests for local backtest ranking and strategy scoring."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.strategy_lab.backtest_factory import BacktestFactoryService
from src.strategy_lab.ranking import StrategyRankingError, StrategyRankingService
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
def ranking_service(store: AShareDataStore) -> StrategyRankingService:
    return StrategyRankingService(store=store)


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
                [row[0], row[1], row[2], row[3], row[4], row[5], row[7], row[6], "PR-12 test candidate"],
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


def _seed_backtest_runs(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    store: AShareDataStore,
    *,
    limit: int = 4,
) -> None:
    strategy_lab.seed_strategy_specs()
    _seed_candidates_and_market(store)
    backtest_factory.run_backtest_batch(
        start_date="2026-06-16",
        end_date="2026-06-23",
        as_of_date="2026-06-22",
        limit=limit,
    )


def test_backtest_rankings_are_sorted_and_scored(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    ranking_service: StrategyRankingService,
    store: AShareDataStore,
) -> None:
    _seed_backtest_runs(strategy_lab, backtest_factory, store, limit=4)

    rankings = ranking_service.list_rankings(limit=10)

    assert len(rankings) == 4
    assert [row["rank"] for row in rankings] == [1, 2, 3, 4]
    assert rankings == sorted(rankings, key=lambda row: (-row["strategy_score"], row["risk_score"]))
    assert 0 <= rankings[0]["strategy_score"] <= 100
    assert 0 <= rankings[0]["risk_score"] <= 100
    assert rankings[0]["research_only"] is True
    assert rankings[0]["live_trading"] is False
    assert rankings[0]["recommendation"] in {"优先观察", "小仓验证", "继续跟踪", "暂不纳入"}
    assert set(rankings[0]["score_components"]) == set(ranking_service.scoring_model()["weights"])


def test_backtest_rankings_can_filter_by_strategy_type(
    strategy_lab: StrategyLabService,
    backtest_factory: BacktestFactoryService,
    ranking_service: StrategyRankingService,
    store: AShareDataStore,
) -> None:
    _seed_backtest_runs(strategy_lab, backtest_factory, store, limit=6)
    all_rankings = ranking_service.list_rankings(limit=10)
    strategy_type = all_rankings[0]["strategy_type"]

    filtered = ranking_service.list_rankings(strategy_type=strategy_type, limit=10)

    assert filtered
    assert all(row["strategy_type"] == strategy_type for row in filtered)
    assert [row["rank"] for row in filtered] == list(range(1, len(filtered) + 1))


def test_backtest_rankings_return_chinese_error_without_runs(
    ranking_service: StrategyRankingService,
) -> None:
    with pytest.raises(StrategyRankingError, match="没有可排名的回测结果"):
        ranking_service.list_rankings()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_strategy_lab_ranking_api_round_trip(client: TestClient) -> None:
    assert client.post("/api/strategy-lab/specs/seed", json={"replace": False}).status_code == 200
    store = AShareDataStore()
    _seed_candidates_and_market(store)
    batch = client.post(
        "/api/strategy-lab/backtest-batch",
        json={
            "start_date": "2026-06-16",
            "end_date": "2026-06-23",
            "as_of_date": "2026-06-22",
            "limit": 3,
        },
    )
    assert batch.status_code == 200

    response = client.get("/api/strategy-lab/backtest-rankings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_count"] == 3
    assert payload["research_only"] is True
    assert payload["live_trading"] is False
    assert payload["rankings"][0]["rank"] == 1
    assert "score_components" in payload["rankings"][0]
    assert "recent_return" in payload["scoring_model"]["weights"]


def test_strategy_lab_ranking_api_returns_chinese_error_without_runs(client: TestClient) -> None:
    response = client.get("/api/strategy-lab/backtest-rankings")

    assert response.status_code == 400
    assert "没有可排名的回测结果" in response.json()["detail"]
