"""Tests for strategy idea generation from hotspot candidates."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.strategy_ideas.service import StrategyIdeaError, StrategyIdeaService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def service(store: AShareDataStore) -> StrategyIdeaService:
    return StrategyIdeaService(store=store)


def _seed_hotspot_inputs(store: AShareDataStore) -> None:
    store.initialize()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO sector_scores (
              trade_date, sector_id, sector_name, event_heat, market_confirm,
              breadth_score, flow_score, persistence_score, crowding_risk,
              sector_heat_score, cycle_stage, created_at
            )
            VALUES (
              DATE '2026-06-22', 'theme_ai_compute', 'AI算力', 0.82, 0.70,
              0.64, 0.68, 0.72, 0.26, 0.78, 'confirmed', now()
            )
            """
        )
        conn.execute(
            """
            INSERT INTO events (
              event_id, cluster_id, doc_id, event_time, publish_time, crawl_time,
              knowable_time, tradable_time, event_type, event_subtype, summary,
              sentiment, intensity, novelty, certainty, a_share_relevance_score,
              policy_level, created_at
            )
            VALUES (
              'evt_ai_compute_001', 'clu_ai_compute_001', 'doc_ai_compute_001',
              TIMESTAMP '2026-06-19 08:30:00', TIMESTAMP '2026-06-19 08:30:00',
              TIMESTAMP '2026-06-19 08:35:00', TIMESTAMP '2026-06-19 08:35:00',
              TIMESTAMP '2026-06-22 09:30:00', '产业新闻', 'AI算力',
              'AI 算力、光模块、数据中心和服务器产业链景气度提升。',
              'positive', 4, 4, 0.82, 0.92, NULL, now()
            )
            """
        )
        for ticker, name, score in [
            ("300308.SZ", "中际旭创", 0.91),
            ("000977.SZ", "浪潮信息", 0.84),
            ("601138.SH", "工业富联", 0.80),
            ("002371.SZ", "北方华创", 0.73),
        ]:
            conn.execute(
                """
                INSERT INTO candidate_pool (
                  as_of_date, ticker, ticker_name, source, sector_id, sector_name,
                  theme, event_heat_score, sector_heat_score, stock_score,
                  user_priority, risk_flag, included, reason, created_at
                )
                VALUES (
                  DATE '2026-06-22', ?, ?, 'sector_radar', 'theme_ai_compute',
                  'AI算力', 'AI算力', 0.82, 0.78, ?, 0, 'normal', true,
                  'AI 算力主题映射候选。', now()
                )
                """,
                [ticker, name, score],
            )


def test_generate_strategy_ideas_writes_auditable_cards(
    store: AShareDataStore,
    service: StrategyIdeaService,
) -> None:
    _seed_hotspot_inputs(store)

    result = service.generate_ideas(
        theme="AI算力",
        as_of_date="2026-06-22",
        risk_preference="balanced",
        max_ideas=8,
    )
    listed = service.list_ideas(theme="AI算力", as_of_date="2026-06-22")

    assert result["idea_count"] == 8
    assert len(listed) == 8
    assert {idea["strategy_type"] for idea in listed}.issuperset(
        {"hot_sector_equal_weight", "catch_up_spread", "overheated_avoidance"}
    )
    assert all(idea["research_only"] is True for idea in listed)
    assert all(idea["live_trading"] is False for idea in listed)
    first = listed[0]
    assert first["theme"] == "AI算力"
    assert first["candidate_tickers"]
    assert first["entry_rules"][0] == "主题限定为 AI算力"
    assert first["params"]["execution_mode"] == "research_only"
    assert "evt_ai_compute_001" in first["source_event_ids"]


def test_generate_strategy_ideas_returns_chinese_error_without_candidates(service: StrategyIdeaService) -> None:
    with pytest.raises(StrategyIdeaError, match="没有可生成策略想法的候选股票"):
        service.generate_ideas(theme="AI算力", as_of_date="2026-06-22")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_strategy_ideas_api_generate_list_and_detail(client: TestClient) -> None:
    _seed_hotspot_inputs(AShareDataStore())

    generate = client.post(
        "/api/strategy-ideas/generate",
        json={
            "theme": "AI算力",
            "as_of_date": "2026-06-22",
            "risk_preference": "balanced",
            "max_ideas": 8,
        },
    )
    assert generate.status_code == 200
    assert generate.json()["idea_count"] == 8

    listed = client.get("/api/strategy-ideas", params={"theme": "AI算力", "as_of_date": "2026-06-22"})
    assert listed.status_code == 200
    body = listed.json()
    assert body["idea_count"] == 8
    idea_id = body["ideas"][0]["idea_id"]

    detail = client.get(f"/api/strategy-ideas/{idea_id}")
    assert detail.status_code == 200
    assert detail.json()["idea_id"] == idea_id
    assert detail.json()["research_only"] is True
