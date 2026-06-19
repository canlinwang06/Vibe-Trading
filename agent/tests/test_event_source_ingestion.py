"""PR-05 tests for event source registration and raw-document ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.event_radar.source_ingestion import (
    EventSourceIngestionError,
    EventSourceIngestionService,
    RawDocumentRecord,
)

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def service(store: AShareDataStore) -> EventSourceIngestionService:
    return EventSourceIngestionService(store=store)


def _sample_document(**overrides) -> RawDocumentRecord:
    payload = {
        "source_id": "finance_news_manual",
        "title": "AI 产业链景气度继续提升",
        "content": "算力、光模块和服务器板块受到多家财经媒体关注。",
        "publish_time": "2026-06-19T08:30:00+08:00",
        "summary": "AI 产业链热度上升。",
        "url": "https://example.com/ai-chain",
        "hot_rank": 3,
        "hot_value": 98.5,
        "raw_json": {"topic": "AI产业链", "rank": 3},
    }
    payload.update(overrides)
    return RawDocumentRecord(**payload)


def test_default_event_sources_cover_required_categories(service: EventSourceIngestionService) -> None:
    service.ensure_default_sources()

    sources = service.list_sources()
    source_ids = {source["source_id"] for source in sources}
    source_types = {source["source_type"] for source in sources}

    assert {
        "gov_policy_cn",
        "csrc_policy_cn",
        "cninfo_announcement",
        "finance_news_manual",
        "social_hot_manual",
    }.issubset(source_ids)
    assert {"policy", "announcement", "finance_news", "social_hot"}.issubset(source_types)
    assert all(source["legal_mode"] in {"public_page", "manual"} for source in sources)


def test_ingest_raw_documents_writes_hash_times_and_deduplicates(service: EventSourceIngestionService) -> None:
    first = _sample_document()
    duplicate = _sample_document()

    result = service.ingest_documents([first, duplicate])
    rows = service.list_raw_documents(source_id="finance_news_manual")
    sources = service.list_sources()
    finance_source = next(source for source in sources if source["source_id"] == "finance_news_manual")

    assert result["requested"] == 2
    assert result["inserted"] == 1
    assert result["duplicates"] == 1
    assert len(rows) == 1
    assert rows[0]["title"] == "AI 产业链景气度继续提升"
    assert rows[0]["source_type"] == "finance_news"
    assert rows[0]["content_hash"]
    assert rows[0]["publish_time"].startswith("2026-06-19T00:30:00")
    assert rows[0]["crawl_time"]
    assert rows[0]["hot_rank"] == 3
    assert rows[0]["raw_json"]["topic"] == "AI产业链"
    assert finance_source["last_fetch_time"] is not None


def test_ingest_rejects_unknown_source_with_chinese_error(service: EventSourceIngestionService) -> None:
    with pytest.raises(EventSourceIngestionError, match="未找到信息源"):
        service.ingest_documents([_sample_document(source_id="unknown_source")])


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_event_radar_sources_api_lists_default_sources(client: TestClient) -> None:
    response = client.get("/api/event-radar/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["source_count"] >= 5
    assert any(source["source_id"] == "cninfo_announcement" for source in body["sources"])


def test_event_radar_collect_api_ingests_and_lists_raw_documents(client: TestClient) -> None:
    collect = client.post(
        "/api/event-radar/collect/run",
        json={
            "documents": [
                {
                    "source_id": "social_hot_manual",
                    "title": "机器人概念登上公开热榜",
                    "content": "公开热榜显示机器人话题热度上升，需后续映射到 A 股板块。",
                    "publish_time": "2026-06-19T11:40:00+08:00",
                    "url": "https://example.com/robot-hot",
                    "hot_rank": 8,
                    "raw_json": {"榜单": "公开热榜", "排名": 8},
                }
            ]
        },
    )

    assert collect.status_code == 200
    assert collect.json()["inserted"] == 1

    response = client.get("/api/event-radar/raw-documents", params={"source_type": "social_hot"})
    assert response.status_code == 200
    body = response.json()
    assert body["document_count"] == 1
    assert body["documents"][0]["title"] == "机器人概念登上公开热榜"
    assert body["documents"][0]["content_hash"]


def test_event_radar_collect_api_returns_chinese_error_for_bad_source(client: TestClient) -> None:
    response = client.post(
        "/api/event-radar/collect/run",
        json={
            "documents": [
                {
                    "source_id": "bad_source",
                    "title": "测试标题",
                    "content": "测试正文",
                    "publish_time": "2026-06-19T08:30:00+08:00",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "未找到信息源" in response.json()["detail"]
