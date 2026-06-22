"""PR-07 tests for event-to-theme/sector/stock mapping."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.event_radar.event_extraction import EventExtractionService
from src.event_radar.event_mapping import EventMappingError, EventMappingService
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


def _ai_policy_doc() -> RawDocumentRecord:
    return RawDocumentRecord(
        source_id="gov_policy_cn",
        title="国家部委发布 AI 算力基础设施支持政策",
        content="政策支持数据中心、光模块、液冷和服务器产业链建设，利好 A股 AI 算力板块。",
        publish_time="2026-06-19T20:00:00+08:00",
        crawl_time="2026-06-19T20:10:00+08:00",
        summary="国家级 AI 算力政策发布。",
        url="https://example.com/ai-policy-map",
    )


def test_default_theme_map_seeds_theme_sector_and_members(mapper: EventMappingService, store: AShareDataStore) -> None:
    rows = mapper.list_theme_map(theme="AI算力")

    assert len(rows) >= 3
    assert {row["ticker"] for row in rows}.issuperset({"300308.SZ", "000977.SZ"})
    assert all(row["sector_id"] == "theme_ai_compute" for row in rows)
    with store.connect(read_only=True) as conn:
        sector = conn.execute(
            "SELECT sector_name, sector_type FROM sectors WHERE sector_id = ?",
            ["theme_ai_compute"],
        ).fetchone()
        members = conn.execute(
            "SELECT ticker FROM sector_members WHERE sector_id = ? ORDER BY ticker",
            ["theme_ai_compute"],
        ).fetchall()
    assert sector == ("AI算力", "custom_theme")
    assert ("300308.SZ",) in members


def test_map_events_writes_sector_and_stock_maps(
    ingestion: EventSourceIngestionService,
    extractor: EventExtractionService,
    mapper: EventMappingService,
) -> None:
    ingestion.ingest_documents([_ai_policy_doc()])
    extractor.extract_events()

    result = mapper.map_events(min_relevance=0.45)
    sector_maps = mapper.list_event_sector_maps()
    stock_maps = mapper.list_event_stock_maps()

    assert result["mapped_events"] == 1
    assert result["sector_rows_written"] >= 1
    assert result["stock_rows_written"] >= 2
    assert sector_maps[0]["theme"] == "AI算力"
    assert sector_maps[0]["sector_id"] == "theme_ai_compute"
    assert sector_maps[0]["direction"] == "positive"
    assert {row["ticker"] for row in stock_maps}.issuperset({"300308.SZ", "000977.SZ"})
    assert all(row["relevance"] >= 0.45 for row in stock_maps)


def test_map_events_returns_chinese_error_without_events(mapper: EventMappingService) -> None:
    with pytest.raises(EventMappingError, match="没有可映射的事件"):
        mapper.map_events()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_event_radar_api_collect_extract_map_and_query_round_trip(client: TestClient) -> None:
    collect = client.post(
        "/api/event-radar/collect/run",
        json={
            "documents": [
                {
                    "source_id": "finance_news_manual",
                    "title": "机器人产业链订单增长",
                    "content": "财经新闻称机器人、智能制造和自动化产业链景气度提升，相关 A股板块受到关注。",
                    "publish_time": "2026-06-19T08:30:00+08:00",
                    "crawl_time": "2026-06-19T08:35:00+08:00",
                    "hot_rank": 4,
                    "hot_value": 92,
                }
            ]
        },
    )
    assert collect.status_code == 200

    extract = client.post("/api/event-radar/extract/run", json={"limit": 20, "min_relevance": 0.45})
    assert extract.status_code == 200
    mapping = client.post("/api/event-radar/map/run", json={"limit": 20, "min_relevance": 0.45})
    assert mapping.status_code == 200
    assert mapping.json()["mapped_events"] == 1

    sectors = client.get("/api/event-radar/mappings/sectors")
    assert sectors.status_code == 200
    assert sectors.json()["sector_mappings"][0]["theme"] == "人形机器人"

    stocks = client.get("/api/event-radar/mappings/stocks")
    assert stocks.status_code == 200
    assert {row["ticker"] for row in stocks.json()["stock_mappings"]}.issuperset({"300024.SZ", "002747.SZ"})


def test_event_radar_map_api_returns_chinese_error_without_events(client: TestClient) -> None:
    response = client.post("/api/event-radar/map/run", json={"limit": 20})

    assert response.status_code == 400
    assert "没有可映射的事件" in response.json()["detail"]
