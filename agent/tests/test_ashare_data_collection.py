"""Tests for public A-share data collection and snapshot APIs."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.collection import AShareDataCollectionService
from src.ashare_data.store import AShareDataStore
from src.event_radar.source_ingestion import EventSourceIngestionService, RawDocumentRecord

pytest.importorskip("duckdb")


class _FakePublicFetcher:
    def fetch_stock_snapshot(self, *, limit: int = 500) -> list[dict[str, object]]:
        return [
            {
                "代码": "300308",
                "名称": "中际旭创",
                "今开": 100,
                "最高": 121,
                "最低": 99,
                "最新价": 120,
                "成交量": 1_000_000,
                "成交额": 1_500_000_000,
                "换手率": 5.2,
                "涨跌幅": 20.0,
                "量比": 2.6,
                "所属行业": "AI算力",
            },
            {
                "代码": "000977",
                "名称": "浪潮信息",
                "今开": 40,
                "最高": 44,
                "最低": 39,
                "最新价": 43.2,
                "成交量": 800_000,
                "成交额": 980_000_000,
                "换手率": 3.1,
                "涨跌幅": 8.0,
                "量比": 1.8,
                "所属行业": "服务器",
            },
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "今开": 1600,
                "最高": 1610,
                "最低": 1440,
                "最新价": 1440,
                "成交量": 100_000,
                "成交额": 900_000_000,
                "换手率": 0.3,
                "涨跌幅": -10.0,
                "量比": 1.2,
                "所属行业": "消费",
            },
        ][:limit]

    def fetch_sector_snapshot(self, *, limit: int = 120) -> list[dict[str, object]]:
        return [
            {
                "板块名称": "AI算力",
                "sector_type": "concept",
                "最新价": 106.5,
                "涨跌幅": 3.6,
                "成交额": 2_600_000_000,
                "换手率": 4.2,
                "上涨家数": 28,
                "下跌家数": 5,
                "涨停家数": 2,
                "股票家数": 40,
                "领涨股票": "300308.SZ",
            }
        ][:limit]

    def fetch_news_documents(self, *, symbols=None, keywords=None, limit: int = 50) -> list[RawDocumentRecord]:
        return [
            RawDocumentRecord(
                source_id="eastmoney_news",
                title="AI 算力产业链景气度提升",
                content="AI 算力、光模块、服务器产业链受到资金关注，A股板块热度提升。",
                publish_time="2026-06-21T09:30:00+08:00",
                summary="AI 算力热度提升。",
                url="https://example.com/ai-compute-news",
                hot_rank=3,
                hot_value=92,
            )
        ][:limit]

    def fetch_announcement_documents(self, *, symbols, start_date, end_date, limit: int = 50) -> list[RawDocumentRecord]:
        return [
            RawDocumentRecord(
                source_id="cninfo_announcement",
                title="中际旭创公告重大合同进展",
                content="300308.SZ 中际旭创 公告重大合同进展，涉及 AI 算力光模块订单。",
                publish_time="2026-06-21T20:00:00+08:00",
                summary="AI 算力订单公告。",
                url="https://example.com/cninfo-300308",
            )
        ][:limit]


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


def test_daily_public_collection_writes_market_sector_anomalies_and_documents(store: AShareDataStore) -> None:
    service = AShareDataCollectionService(store=store, fetcher=_FakePublicFetcher())

    result = service.collect_daily_package(trade_date="2026-06-21", symbols=["300308.SZ"], extract_events=True)
    market = service.market_snapshot(trade_date="2026-06-21", limit=10)
    sector = service.sector_anomaly_snapshot(trade_date="2026-06-21", limit=10)
    documents = EventSourceIngestionService(store=store).list_raw_documents(limit=10)

    assert result["status"] == "ok"
    assert result["failed_step_count"] == 0
    assert market["row_count"] == 3
    assert market["summary"]["limit_up_count"] == 1
    assert market["summary"]["anomaly_counts"]["high_turnover"] == 1
    assert sector["sector_count"] == 1
    assert {row["anomaly_type"] for row in sector["anomalies"]} >= {"limit_up", "limit_down", "volume_spike"}
    assert len(documents) == 2
    assert all(document["url"] for document in documents)

    with store.connect(read_only=True) as conn:
        run_rows = conn.execute(
            "SELECT collector_type, status FROM collector_runs ORDER BY collector_type"
        ).fetchall()
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        market_source = conn.execute(
            "SELECT last_fetch_time FROM source_registry WHERE source_id = 'akshare_local'"
        ).fetchone()

    assert {row[0] for row in run_rows} == {"market_snapshot", "news_documents", "sector_anomalies"}
    assert {row[1] for row in run_rows} == {"ok"}
    assert event_count >= 1
    assert market_source[0] is not None


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_ashare_collection_api_accepts_codex_payload_and_returns_snapshots(client: TestClient) -> None:
    response = client.post(
        "/api/ashare/collection/run",
        json={
            "trade_date": "2026-06-21",
            "market_records": [
                {
                    "ticker": "300308.SZ",
                    "ticker_name": "中际旭创",
                    "open": 100,
                    "high": 121,
                    "low": 99,
                    "close": 120,
                    "volume": 1_000_000,
                    "amount": 1_500_000_000,
                    "turnover": 0.052,
                    "pct_change": 0.20,
                    "volume_ratio": 2.6,
                    "sector_name": "AI算力",
                }
            ],
            "sector_records": [
                {
                    "sector_name": "AI算力",
                    "sector_type": "concept",
                    "close": 106.5,
                    "return": 0.036,
                    "amount": 2_600_000_000,
                    "up_count": 28,
                    "down_count": 5,
                    "limit_up_count": 2,
                    "member_count": 40,
                    "leading_ticker": "300308.SZ",
                }
            ],
            "anomaly_source_records": [
                {
                    "ticker": "300308.SZ",
                    "ticker_name": "中际旭创",
                    "close": 120,
                    "pct_change": 0.20,
                    "amount": 1_500_000_000,
                    "volume_ratio": 2.6,
                    "sector_name": "AI算力",
                }
            ],
            "documents": [
                {
                    "source_id": "eastmoney_news",
                    "title": "AI 算力板块热度提升",
                    "content": "AI 算力、服务器和光模块产业链受到关注，A股板块热度提升。",
                    "publish_time": "2026-06-21T09:30:00+08:00",
                    "url": "https://example.com/ai-compute",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["rows_written"] >= 3

    market = client.get("/api/ashare/market-snapshot", params={"trade_date": "2026-06-21"})
    anomalies = client.get("/api/ashare/sector-anomalies", params={"trade_date": "2026-06-21"})

    assert market.status_code == 200
    assert market.json()["rows"][0]["ticker"] == "300308.SZ"
    assert anomalies.status_code == 200
    assert anomalies.json()["sector_count"] == 1
    assert anomalies.json()["anomaly_count"] >= 1
