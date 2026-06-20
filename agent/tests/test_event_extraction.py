"""PR-06 tests for rule-based event extraction and clustering."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.event_radar.event_extraction import EventExtractionError, EventExtractionService
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


def _ai_policy_doc(source_id: str = "gov_policy_cn") -> RawDocumentRecord:
    return RawDocumentRecord(
        source_id=source_id,
        title="国家部委发布 AI 算力基础设施支持政策",
        content="政策提出支持数据中心、光模块、液冷和服务器产业链建设，利好 A股 AI 算力板块。",
        publish_time="2026-06-19T20:00:00+08:00",
        crawl_time="2026-06-19T20:10:00+08:00",
        summary="国家级 AI 算力政策发布。",
        url=f"https://example.com/{source_id}/ai-policy",
        raw_json={"topic": "AI算力"},
    )


def test_extract_events_writes_point_in_time_event_and_cluster(
    ingestion: EventSourceIngestionService,
    extractor: EventExtractionService,
) -> None:
    ingestion.ingest_documents([_ai_policy_doc()])

    result = extractor.extract_events()
    events = extractor.list_events()
    clusters = extractor.list_clusters()

    assert result["extracted"] == 1
    assert len(events) == 1
    assert events[0]["event_type"] == "政策"
    assert events[0]["event_subtype"] == "AI算力"
    assert events[0]["sentiment"] == "positive"
    assert events[0]["a_share_relevance_score"] >= 0.75
    assert events[0]["knowable_time"].startswith("2026-06-19T12:10:00")
    assert events[0]["tradable_time"].startswith("2026-06-22T09:30:00")
    assert len(clusters) == 1
    assert clusters[0]["mention_count"] == 1
    assert clusters[0]["source_count"] == 1
    assert clusters[0]["status"] in {"active", "fading"}


def test_extract_events_groups_same_topic_into_one_cluster(
    ingestion: EventSourceIngestionService,
    extractor: EventExtractionService,
) -> None:
    ingestion.ingest_documents(
        [
            _ai_policy_doc("gov_policy_cn"),
            _ai_policy_doc("csrc_policy_cn"),
        ]
    )

    result = extractor.extract_events()
    clusters = extractor.list_clusters()
    detail = extractor.get_cluster(clusters[0]["cluster_id"])

    assert result["extracted"] == 2
    assert len(clusters) == 1
    assert clusters[0]["source_count"] == 2
    assert clusters[0]["mention_count"] == 2
    assert clusters[0]["cross_platform_score"] > 0
    assert len(detail["events"]) == 2


def test_extract_events_maps_weekend_knowable_time_to_next_monday_open(
    ingestion: EventSourceIngestionService,
    extractor: EventExtractionService,
) -> None:
    ingestion.ingest_documents(
        [
            RawDocumentRecord(
                source_id="finance_news_manual",
                title="周末 AI 算力产业链政策解读",
                content="周末财经新闻继续解读 AI 算力、光模块和数据中心产业链，关注 A股板块反应。",
                publish_time="2026-06-20T10:00:00+08:00",
                crawl_time="2026-06-20T10:05:00+08:00",
                url="https://example.com/weekend-ai",
            )
        ]
    )

    extractor.extract_events()
    events = extractor.list_events()

    assert events[0]["knowable_time"].startswith("2026-06-20T02:05:00")
    assert events[0]["tradable_time"].startswith("2026-06-22T09:30:00")


def test_extract_events_returns_chinese_error_when_no_raw_documents(extractor: EventExtractionService) -> None:
    with pytest.raises(EventExtractionError, match="没有可抽取的原始文档"):
        extractor.extract_events()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_event_radar_api_collect_extract_and_query_round_trip(client: TestClient) -> None:
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
                    "raw_json": {"topic": "机器人"},
                }
            ]
        },
    )
    assert collect.status_code == 200

    extract = client.post("/api/event-radar/extract/run", json={"limit": 20, "min_relevance": 0.45})
    assert extract.status_code == 200
    assert extract.json()["extracted"] == 1

    events = client.get("/api/event-radar/events", params={"min_relevance": 0.45})
    assert events.status_code == 200
    event_body = events.json()
    assert event_body["event_count"] == 1
    assert event_body["events"][0]["event_subtype"] == "机器人"
    assert event_body["events"][0]["tradable_time"].endswith("09:30:00")

    clusters = client.get("/api/event-radar/clusters")
    assert clusters.status_code == 200
    cluster_id = clusters.json()["clusters"][0]["cluster_id"]

    detail = client.get(f"/api/event-radar/clusters/{cluster_id}")
    assert detail.status_code == 200
    assert detail.json()["cluster_id"] == cluster_id
    assert len(detail.json()["events"]) == 1


def test_event_radar_extract_api_returns_chinese_error_without_raw_documents(client: TestClient) -> None:
    response = client.post("/api/event-radar/extract/run", json={"limit": 20})

    assert response.status_code == 400
    assert "没有可抽取的原始文档" in response.json()["detail"]
