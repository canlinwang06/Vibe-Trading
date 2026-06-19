"""PR-24 tests for A-share event reaction study."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.event_radar.event_extraction import EventExtractionService
from src.event_radar.event_mapping import EventMappingService
from src.event_radar.source_ingestion import EventSourceIngestionService, RawDocumentRecord
from src.event_reactions.service import EventReactionError, EventReactionService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def service(store: AShareDataStore) -> EventReactionService:
    return EventReactionService(store=store)


def _ai_policy_doc() -> RawDocumentRecord:
    return RawDocumentRecord(
        source_id="gov_policy_cn",
        title="国家部委发布 AI 算力基础设施支持政策",
        content=(
            "政策支持数据中心、光模块、液冷和服务器产业链建设，"
            "利好 A股 AI 算力、光模块和服务器上市公司。"
        ),
        publish_time="2026-06-19T20:00:00+08:00",
        crawl_time="2026-06-19T20:10:00+08:00",
        summary="国家级 AI 算力政策发布。",
        url="https://example.com/pr-24-ai-policy",
        hot_rank=2,
        hot_value=98,
    )


def _dates() -> list[date]:
    start = date(2026, 6, 22)
    return [start + timedelta(days=idx) for idx in range(8)]


def _seed_event_mapping(store: AShareDataStore) -> None:
    ingestion = EventSourceIngestionService(store=store)
    extractor = EventExtractionService(store=store)
    mapper = EventMappingService(store=store)
    ingestion.ingest_documents([_ai_policy_doc()])
    extractor.extract_events(limit=20, min_relevance=0.45)
    mapper.map_events(limit=20, min_relevance=0.45)


def _seed_market_daily(store: AShareDataStore) -> None:
    store.initialize()
    prices = {
        "300308.SZ": ("中际旭创", [40.0, 42.0, 41.0, 44.0, 46.0, 48.0, 47.0, 49.0]),
        "000977.SZ": ("浪潮信息", [30.0, 31.0, 30.5, 32.0, 33.5, 35.0, 35.5, 36.0]),
        "601138.SH": ("工业富联", [25.0, 25.5, 25.2, 26.0, 27.0, 28.0, 27.8, 28.2]),
        "000300.SH": ("沪深300", [100.0, 101.0, 101.5, 102.0, 103.0, 104.0, 103.8, 104.2]),
    }
    with store.connect() as conn:
        for offset, (ticker, (name, closes)) in enumerate(prices.items()):
            conn.execute(
                """
                INSERT INTO assets (ticker, ticker_name, exchange, asset_type, active)
                VALUES (?, ?, ?, 'stock', true)
                """,
                [ticker, name, ticker.split(".")[1]],
            )
            for idx, trade_date in enumerate(_dates()):
                close = closes[idx]
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
                        1_000_000 + idx * 100_000 + offset * 20_000,
                        220_000_000 + idx * 20_000_000 + offset * 12_000_000,
                        0.02 + idx * 0.001,
                    ],
                )


def _seed_sector_daily(store: AShareDataStore) -> None:
    store.initialize()
    closes = [100.0, 103.0, 102.0, 106.0, 108.0, 111.0, 110.0, 112.0]
    with store.connect() as conn:
        for idx, trade_date in enumerate(_dates()):
            close = closes[idx]
            conn.execute(
                """
                INSERT INTO sector_daily (
                  trade_date, sector_id, sector_name, open, high, low, close,
                  "return", amount, turnover, up_count, down_count, limit_up_count,
                  member_count, leading_ticker, source, created_at
                )
                VALUES (?, 'theme_ai_compute', 'AI算力', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 3, '300308.SZ', 'unit_test', now())
                """,
                [
                    trade_date,
                    close * 0.99,
                    close * 1.02,
                    close * 0.98,
                    close,
                    0.0 if idx == 0 else close / closes[idx - 1] - 1,
                    180_000_000 + idx * 35_000_000,
                    0.02 + idx * 0.001,
                    2 + (idx % 2),
                    1,
                    1 if idx in {1, 5} else 0,
                ],
            )


def _prepare_reaction_inputs(store: AShareDataStore) -> None:
    _seed_event_mapping(store)
    _seed_market_daily(store)
    _seed_sector_daily(store)


def test_calculate_event_reactions_for_stock_and_sector(
    service: EventReactionService,
    store: AShareDataStore,
) -> None:
    _prepare_reaction_inputs(store)

    result = service.calculate_reactions(windows=["T+1", "T+5"], target_types=["sector", "stock"])
    rows = service.list_reactions(window="T+5", limit=50)

    assert result["status"] == "ok"
    assert result["reactions_written"] >= 4
    assert result["research_only"] is True
    assert result["live_trading"] is False
    assert {row["target_type"] for row in rows}.issuperset({"sector", "stock"})

    stock = next(row for row in rows if row["target_id"] == "300308.SZ")
    assert stock["raw_return"] > stock["benchmark_return"]
    assert stock["abnormal_return"] > 0
    assert stock["max_drawdown"] <= 0
    assert stock["volume_change"] > 0


def test_event_reaction_summary_answers_ai_policy_t5_average(
    service: EventReactionService,
    store: AShareDataStore,
) -> None:
    _prepare_reaction_inputs(store)
    service.calculate_reactions(windows=["T+5"], target_types=["stock"])

    summary = service.summary(event_subtype="AI算力", target_type="stock", window="T+5")

    assert summary["status"] == "ok"
    assert summary["summary_count"] == 1
    row = summary["summaries"][0]
    assert row["reaction_count"] >= 1
    assert row["avg_raw_return"] > row["avg_benchmark_return"]
    assert row["avg_abnormal_return"] > 0
    assert summary["research_only"] is True
    assert summary["live_trading"] is False


def test_event_reactions_return_chinese_error_without_mappings(service: EventReactionService) -> None:
    with pytest.raises(EventReactionError, match="没有可计算的事件映射"):
        service.calculate_reactions(windows=["T+1"], target_types=["stock"])


def test_event_reactions_validate_windows(service: EventReactionService) -> None:
    with pytest.raises(EventReactionError, match="观察窗口只支持"):
        service.calculate_reactions(windows=["T+3"], target_types=["stock"])


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_event_reaction_api_round_trip(client: TestClient) -> None:
    store = AShareDataStore()
    _prepare_reaction_inputs(store)

    calculate = client.post(
        "/api/event-reactions/calculate",
        json={"windows": ["T+1", "T+5"], "target_types": ["stock"], "limit": 20},
    )
    assert calculate.status_code == 200
    assert calculate.json()["reactions_written"] >= 2

    listed = client.get("/api/event-reactions", params={"target_type": "stock", "window": "T+5"})
    assert listed.status_code == 200
    assert listed.json()["reaction_count"] >= 1

    summary = client.get(
        "/api/event-reactions/summary",
        params={"event_subtype": "AI算力", "target_type": "stock", "window": "T+5"},
    )
    assert summary.status_code == 200
    assert summary.json()["summaries"][0]["avg_abnormal_return"] > 0
