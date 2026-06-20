"""Tests for the unified event records API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.event_radar.event_extraction import EventExtractionService
from src.event_radar.event_mapping import EventMappingService
from src.event_radar.source_ingestion import EventSourceIngestionService, RawDocumentRecord
from src.event_records.service import EventRecordError, EventRecordService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def service(store: AShareDataStore) -> EventRecordService:
    return EventRecordService(store=store)


def _ai_policy_doc() -> RawDocumentRecord:
    return RawDocumentRecord(
        source_id="finance_news_manual",
        title="AI 算力产业链订单增长",
        content="财经新闻称 AI 算力、光模块、数据中心和服务器产业链景气度提升，相关 A股板块受到关注。",
        publish_time="2026-06-19T08:30:00+08:00",
        crawl_time="2026-06-19T08:35:00+08:00",
        hot_rank=4,
        hot_value=92,
    )


def _prepare_event_record_inputs(store: AShareDataStore) -> None:
    EventSourceIngestionService(store=store).ingest_documents([_ai_policy_doc()])
    EventExtractionService(store=store).extract_events(limit=20, min_relevance=0.45)
    EventMappingService(store=store).map_events(limit=20, min_relevance=0.45)


def test_event_record_service_lists_evidence_mappings_and_reserved_impact_fields(
    store: AShareDataStore,
    service: EventRecordService,
) -> None:
    _prepare_event_record_inputs(store)

    records = service.list_records(limit=10, event_subtype="AI算力", min_relevance=0.45)

    assert len(records) == 1
    record = records[0]
    assert record["event_subtype"] == "AI算力"
    assert record["source_url"] is None
    assert record["local_document_ref"].startswith("raw_documents:")
    assert record["evidence"]["title"] == "AI 算力产业链订单增长"
    assert {sector["sector_id"] for sector in record["related_sectors"]} == {"theme_ai_compute"}
    assert {stock["ticker"] for stock in record["related_stocks"]}.issuperset({"300308.SZ", "000977.SZ"})
    assert record["impact_t1"]["status"] == "pending"
    assert record["impact_t5"]["stock_count"] == 0
    assert set(record["impact"]) == {"T+1", "T+5", "T+20", "T+60"}


def test_event_record_service_validates_date_range(service: EventRecordService) -> None:
    with pytest.raises(EventRecordError, match="from_date 不能晚于 to_date"):
        service.list_records(from_date="2026-06-20", to_date="2026-06-19")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_event_records_api_collect_extract_map_and_list_round_trip(client: TestClient) -> None:
    collect = client.post(
        "/api/event-radar/collect/run",
        json={
            "documents": [
                {
                    "source_id": "finance_news_manual",
                    "title": "AI 算力产业链订单增长",
                    "content": "财经新闻称 AI 算力、光模块、数据中心和服务器产业链景气度提升，相关 A股板块受到关注。",
                    "publish_time": "2026-06-19T08:30:00+08:00",
                    "crawl_time": "2026-06-19T08:35:00+08:00",
                    "hot_rank": 4,
                    "hot_value": 92,
                }
            ]
        },
    )
    assert collect.status_code == 200
    assert client.post("/api/event-radar/extract/run", json={"limit": 20, "min_relevance": 0.45}).status_code == 200
    assert client.post("/api/event-radar/map/run", json={"limit": 20, "min_relevance": 0.45}).status_code == 200

    response = client.get(
        "/api/event-records",
        params={"event_subtype": "AI算力", "from_date": "2026-06-19", "to_date": "2026-06-19"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["record_count"] == 1
    assert body["impact_windows"] == ["T+1", "T+5", "T+20", "T+60"]
    assert body["research_only"] is True
    assert body["live_trading"] is False
    record = body["records"][0]
    assert record["event_subtype"] == "AI算力"
    assert record["source_url"] is None
    assert record["local_document_ref"].startswith("raw_documents:")
    assert record["related_sectors"][0]["sector_name"] == "AI算力"
    assert {stock["ticker"] for stock in record["related_stocks"]}.issuperset({"300308.SZ", "000977.SZ"})
    assert record["impact_t1"]["status"] == "pending"
