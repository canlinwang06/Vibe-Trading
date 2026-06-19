"""PR-09 tests for A-share candidate-pool generation and review controls."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.candidate_pool.service import CandidatePoolError, CandidatePoolService
from src.event_radar.event_extraction import EventExtractionService
from src.event_radar.event_mapping import EventMappingService
from src.event_radar.sector_scoring import SectorScoringService
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
def sector_scorer(store: AShareDataStore) -> SectorScoringService:
    return SectorScoringService(store=store)


@pytest.fixture
def candidate_service(store: AShareDataStore) -> CandidatePoolService:
    return CandidatePoolService(store=store)


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
        url="https://example.com/ai-policy-candidate",
    )


def _seed_sector_daily(store: AShareDataStore) -> None:
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
                VALUES (?, 'theme_ai_compute', 'AI算力', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unit_test', now())
                """,
                [
                    row[0],
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
                ],
            )


def _seed_market_daily(store: AShareDataStore) -> None:
    store.initialize()
    tickers = {
        "300308.SZ": "中际旭创",
        "000977.SZ": "浪潮信息",
        "601138.SH": "工业富联",
    }
    dates = [date(2026, 6, 16), date(2026, 6, 17), date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22)]
    with store.connect() as conn:
        for offset, (ticker, name) in enumerate(tickers.items()):
            conn.execute(
                """
                INSERT INTO assets (ticker, ticker_name, exchange, asset_type, active)
                VALUES (?, ?, ?, 'stock', true)
                """,
                [ticker, name, ticker.split(".")[1]],
            )
            for idx, trade_date in enumerate(dates):
                close = 40 + offset * 5 + idx * (1.2 + offset * 0.2)
                amount = 220_000_000 + idx * 35_000_000 + offset * 20_000_000
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
                        close * 0.98,
                        close * 1.02,
                        close * 0.97,
                        close,
                        1_000_000 + idx * 100_000,
                        amount,
                        0.02 + idx * 0.002,
                    ],
                )


def _prepare_candidate_inputs(
    ingestion: EventSourceIngestionService,
    extractor: EventExtractionService,
    mapper: EventMappingService,
    sector_scorer: SectorScoringService,
    store: AShareDataStore,
) -> None:
    ingestion.ingest_documents([_ai_policy_doc()])
    extractor.extract_events()
    mapper.map_events()
    _seed_sector_daily(store)
    _seed_market_daily(store)
    sector_scorer.score_sectors(trade_date="2026-06-22")


def test_build_candidate_pool_from_sector_scores_and_stock_maps(
    ingestion: EventSourceIngestionService,
    extractor: EventExtractionService,
    mapper: EventMappingService,
    sector_scorer: SectorScoringService,
    candidate_service: CandidatePoolService,
    store: AShareDataStore,
) -> None:
    _prepare_candidate_inputs(ingestion, extractor, mapper, sector_scorer, store)

    result = candidate_service.build_candidate_pool(as_of_date="2026-06-22", limit=20)
    rows = candidate_service.list_candidates(as_of_date="2026-06-22", limit=20)

    assert result["rows_written"] >= 2
    assert {row["ticker"] for row in rows}.issuperset({"300308.SZ", "000977.SZ"})
    assert rows[0]["source"] == "sector_radar"
    assert rows[0]["theme"] == "AI算力"
    assert rows[0]["sector_heat_score"] > 0
    assert rows[0]["stock_score"] > 0.35
    assert rows[0]["included"] is True
    assert rows[0]["risk_flag"] == "normal"


def test_user_add_include_and_exclude_candidate(candidate_service: CandidatePoolService) -> None:
    added = candidate_service.add_user_candidate(
        ticker="600519.SH",
        ticker_name="贵州茅台",
        as_of_date="2026-06-22",
        theme="文娱消费",
        sector_id="theme_media_consumption",
        sector_name="文娱消费",
        reason="用户关注消费修复。",
    )
    excluded = candidate_service.set_included(
        ticker="600519.SH",
        as_of_date="2026-06-22",
        included=False,
        reason="估值偏高，暂不纳入。",
    )
    included = candidate_service.set_included(
        ticker="600519.SH",
        as_of_date="2026-06-22",
        included=True,
        reason="重新纳入观察。",
    )

    assert added["source"] == "user_added"
    assert added["included"] is True
    assert excluded["included"] is False
    assert included["included"] is True


def test_candidate_pool_returns_chinese_error_without_sector_scores(candidate_service: CandidatePoolService) -> None:
    with pytest.raises(CandidatePoolError, match="没有可生成候选池的板块评分"):
        candidate_service.build_candidate_pool(as_of_date="2026-06-22")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_candidate_pool_api_round_trip(client: TestClient) -> None:
    collect = client.post(
        "/api/event-radar/collect/run",
        json={
            "documents": [
                {
                    "source_id": "finance_news_manual",
                    "title": "AI 算力板块候选股扩散",
                    "content": (
                        "财经新闻称数据中心、光模块、服务器和液冷产业链景气度提升，"
                        "A股 AI 算力候选股票受到关注。"
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
    assert client.post("/api/event-radar/sector-scores/run", json={"trade_date": "2026-06-19"}).status_code == 200

    build = client.post("/api/candidate-pool/build", json={"as_of_date": "2026-06-19", "limit": 20})
    assert build.status_code == 200
    assert build.json()["rows_written"] >= 1

    candidates = client.get("/api/candidate-pool", params={"as_of_date": "2026-06-19"})
    assert candidates.status_code == 200
    assert candidates.json()["candidate_count"] >= 1

    add = client.post(
        "/api/candidate-pool/user-add",
        json={
            "ticker": "600519.SH",
            "ticker_name": "贵州茅台",
            "as_of_date": "2026-06-19",
            "theme": "文娱消费",
            "reason": "用户手动观察。",
        },
    )
    assert add.status_code == 200
    assert add.json()["source"] == "user_added"

    exclude = client.post(
        "/api/candidate-pool/exclude",
        json={"ticker": "600519.SH", "as_of_date": "2026-06-19", "reason": "暂不纳入策略池。"},
    )
    assert exclude.status_code == 200
    assert exclude.json()["included"] is False

    include = client.post(
        "/api/candidate-pool/include",
        json={"ticker": "600519.SH", "as_of_date": "2026-06-19", "reason": "重新纳入观察。"},
    )
    assert include.status_code == 200
    assert include.json()["included"] is True


def test_candidate_pool_api_returns_chinese_error_without_sector_scores(client: TestClient) -> None:
    response = client.post("/api/candidate-pool/build", json={"as_of_date": "2026-06-22"})

    assert response.status_code == 400
    assert "没有可生成候选池的板块评分" in response.json()["detail"]
