"""PR-08 tests for event-driven A-share sector heat scoring."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.event_radar.event_extraction import EventExtractionService
from src.event_radar.event_mapping import EventMappingService
from src.event_radar.sector_scoring import SectorScoringError, SectorScoringService
from src.event_radar.source_ingestion import EventSourceIngestionService, RawDocumentRecord

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def ingestion(store: AShareDataStore) -> EventSourceIngestionService:
    return EventSourceIngestionService(store=store)


@pytest.fixture
def extractor(store: AShareDataStore) -> EventExtractionService:
    return EventExtractionService(store=store)


@pytest.fixture
def mapper(store: AShareDataStore) -> EventMappingService:
    return EventMappingService(store=store)


@pytest.fixture
def scorer(store: AShareDataStore) -> SectorScoringService:
    return SectorScoringService(store=store)


def _ai_policy_doc() -> RawDocumentRecord:
    return RawDocumentRecord(
        source_id="gov_policy_cn",
        title="国家部委发布 AI 算力基础设施支持政策",
        content=(
            "政策支持数据中心、光模块、液冷和服务器产业链建设，"
            "利好 A股 AI 算力板块。"
        ),
        publish_time="2026-06-19T20:00:00+08:00",
        crawl_time="2026-06-19T20:10:00+08:00",
        summary="国家级 AI 算力政策发布。",
        url="https://example.com/ai-policy-score",
    )


def _seed_sector_daily(store: AShareDataStore, sector_id: str = "theme_ai_compute") -> None:
    store.initialize()
    rows = [
        (date(2026, 6, 16), 100.0, 0.012, 120_000_000.0, 0.018, 2, 1, 0, 3),
        (date(2026, 6, 17), 102.0, 0.020, 150_000_000.0, 0.021, 3, 0, 1, 3),
        (date(2026, 6, 18), 103.5, 0.015, 170_000_000.0, 0.024, 3, 0, 1, 3),
        (date(2026, 6, 19), 104.0, 0.005, 180_000_000.0, 0.025, 2, 1, 0, 3),
        (date(2026, 6, 22), 107.0, 0.029, 260_000_000.0, 0.032, 3, 0, 1, 3),
    ]
    with store.connect() as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO sector_daily (
                  trade_date, sector_id, sector_name, open, high, low, close,
                  "return", amount, turnover, up_count, down_count, limit_up_count,
                  member_count, leading_ticker, source, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                """,
                [
                    row[0],
                    sector_id,
                    "AI算力",
                    row[1] * 0.98,
                    row[1] * 1.01,
                    row[1] * 0.97,
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    "300308.SZ",
                    "unit_test",
                ],
            )


def test_sector_scoring_writes_top_sector_scores(
    ingestion: EventSourceIngestionService,
    extractor: EventExtractionService,
    mapper: EventMappingService,
    scorer: SectorScoringService,
    store: AShareDataStore,
) -> None:
    ingestion.ingest_documents([_ai_policy_doc()])
    extractor.extract_events()
    mapper.map_events()
    _seed_sector_daily(store)

    result = scorer.score_sectors(trade_date="2026-06-22", limit=10)
    rows = scorer.list_sector_scores(trade_date="2026-06-22", limit=10)

    assert result["status"] == "ok"
    assert result["rows_written"] >= 1
    assert rows[0]["sector_id"] == "theme_ai_compute"
    assert rows[0]["sector_name"] == "AI算力"
    assert rows[0]["event_heat"] > 0
    assert rows[0]["market_confirm"] > 0.5
    assert rows[0]["sector_heat_score"] > 0.4
    assert rows[0]["cycle_stage"] in {"warming", "confirmed", "accelerating", "climax"}


def test_sector_scoring_returns_chinese_error_without_mappings(scorer: SectorScoringService) -> None:
    with pytest.raises(SectorScoringError, match="没有可评分的板块映射"):
        scorer.score_sectors(trade_date="2026-06-22")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_event_radar_api_sector_score_round_trip(client: TestClient) -> None:
    collect = client.post(
        "/api/event-radar/collect/run",
        json={
            "documents": [
                {
                    "source_id": "finance_news_manual",
                    "title": "AI 算力板块成交额放大",
                    "content": (
                        "财经新闻称数据中心、光模块、服务器和液冷产业链景气度提升，"
                        "A股 AI 算力板块受到关注。"
                    ),
                    "publish_time": "2026-06-19T08:30:00+08:00",
                    "crawl_time": "2026-06-19T08:35:00+08:00",
                    "hot_rank": 3,
                    "hot_value": 95,
                }
            ]
        },
    )
    assert collect.status_code == 200
    assert client.post("/api/event-radar/extract/run", json={"limit": 20, "min_relevance": 0.45}).status_code == 200
    assert client.post("/api/event-radar/map/run", json={"limit": 20, "min_relevance": 0.45}).status_code == 200

    score = client.post("/api/event-radar/sector-scores/run", json={"trade_date": "2026-06-19", "limit": 10})
    assert score.status_code == 200
    assert score.json()["rows_written"] >= 1

    scores = client.get("/api/event-radar/sector-scores")
    assert scores.status_code == 200
    assert scores.json()["sector_scores"][0]["sector_id"] == "theme_ai_compute"


def test_event_radar_sector_score_api_returns_chinese_error_without_mappings(client: TestClient) -> None:
    response = client.post("/api/event-radar/sector-scores/run", json={"trade_date": "2026-06-22"})

    assert response.status_code == 400
    assert "没有可评分的板块映射" in response.json()["detail"]
