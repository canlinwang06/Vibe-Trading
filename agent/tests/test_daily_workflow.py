"""PR-22 tests for manual daily A-share research workflow orchestration."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.daily_workflow.service import DailyWorkflowError, DailyWorkflowService
from src.event_radar.source_ingestion import RawDocumentRecord

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def service(store: AShareDataStore) -> DailyWorkflowService:
    return DailyWorkflowService(store=store)


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
        url="https://example.com/pr-22-ai-policy",
        hot_rank=2,
        hot_value=98,
    )


def _trading_dates() -> list[date]:
    start = date(2026, 6, 16)
    return [start + timedelta(days=idx) for idx in range(8)]


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
        "000300.SH": "沪深300",
    }
    with store.connect() as conn:
        for offset, (ticker, name) in enumerate(tickers.items()):
            conn.execute(
                """
                INSERT INTO assets (ticker, ticker_name, exchange, asset_type, active)
                VALUES (?, ?, ?, 'stock', true)
                """,
                [ticker, name, ticker.split(".")[1]],
            )
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
                        220_000_000 + offset * 35_000_000 + idx * 12_000_000,
                        0.02 + idx * 0.001,
                    ],
                )


def test_daily_workflow_dry_run_lists_planned_steps(service: DailyWorkflowService) -> None:
    result = service.run(
        workflow_date="2026-06-22",
        steps=["collect_documents", "generate_draft_signals"],
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["workflow_date"] == "2026-06-22"
    assert result["research_only"] is True
    assert result["live_trading"] is False
    assert [step["status"] for step in result["steps"]] == ["planned", "planned"]
    assert "不会审批或交易" in result["steps"][1]["message"]


def test_daily_workflow_runs_full_local_research_chain(
    service: DailyWorkflowService,
    store: AShareDataStore,
) -> None:
    _seed_sector_daily(store)
    _seed_market_daily(store)

    result = service.run(
        workflow_date="2026-06-22",
        portfolio_id="cn_a_main",
        documents=[_ai_policy_doc()],
        backtest_start_date="2026-06-16",
        backtest_end_date="2026-06-23",
        backtest_limit=4,
        ranking_limit=4,
    )

    steps = {step["name"]: step for step in result["steps"]}
    assert result["status"] == "ok"
    assert result["blocked_step"] is None
    assert result["completed_step_count"] == 10
    assert result["research_only"] is True
    assert result["live_trading"] is False
    assert steps["collect_documents"]["metrics"]["inserted"] == 1
    assert steps["extract_events"]["metrics"]["extracted"] >= 1
    assert steps["map_events"]["metrics"]["mapped_events"] >= 1
    assert steps["score_sectors"]["metrics"]["scored_sectors"] >= 1
    assert steps["build_candidates"]["metrics"]["candidate_count"] >= 2
    assert steps["run_backtests"]["metrics"]["runs_written"] == 4
    assert steps["rank_backtests"]["metrics"]["ranking_count"] == 4
    assert steps["allocate_portfolio"]["metrics"]["allocation_count"] >= 1
    assert steps["generate_draft_signals"]["metrics"]["signals_written"] >= 1

    with store.connect(read_only=True) as conn:
        statuses = conn.execute(
            "SELECT DISTINCT status FROM execution_signals ORDER BY status"
        ).fetchall()
    assert statuses == [("draft",)]


def test_daily_workflow_blocks_when_prerequisites_are_missing(service: DailyWorkflowService) -> None:
    result = service.run(workflow_date="2026-06-22", steps=["build_candidates"])

    assert result["status"] == "blocked"
    assert result["blocked_step"] == "build_candidates"
    assert result["completed_step_count"] == 0
    assert "没有可生成候选池的板块评分" in result["steps"][0]["message"]
    assert result["live_trading"] is False


def test_daily_workflow_validates_steps(service: DailyWorkflowService) -> None:
    with pytest.raises(DailyWorkflowError, match="不支持的工作流步骤"):
        service.run(workflow_date="2026-06-22", steps=["collect_documents", "approve_plan"])


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_daily_workflow_api_dry_run_round_trip(client: TestClient) -> None:
    response = client.post(
        "/api/daily-workflow/run",
        json={
            "workflow_date": "2026-06-22",
            "steps": ["collect_documents", "extract_events"],
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "dry_run"
    assert payload["requested_steps"] == ["collect_documents", "extract_events"]
    assert payload["steps"][0]["status"] == "planned"
    assert payload["research_only"] is True
    assert payload["live_trading"] is False


def test_daily_workflow_api_returns_chinese_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/daily-workflow/run",
        json={"workflow_date": "2026-06-22", "steps": ["approve_plan"]},
    )

    assert response.status_code == 400
    assert "不支持的工作流步骤" in response.json()["detail"]
