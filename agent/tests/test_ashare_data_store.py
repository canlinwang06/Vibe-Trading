"""PR-03 tests for the local A-share DuckDB data store."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ashare_data.schema import PR03_CORE_TABLE_NAMES
from src.ashare_data.store import AShareDataStore, initialize_ashare_store

pytest.importorskip("duckdb")


EXPECTED_PR03_TABLES = (
    "assets",
    "source_registry",
    "raw_documents",
    "event_clusters",
    "event_mentions",
    "events",
    "theme_map",
    "sectors",
    "sector_members",
    "event_sector_map",
    "event_stock_map",
    "market_daily",
    "sector_daily",
    "sector_scores",
    "candidate_pool",
    "strategy_specs",
    "backtest_runs",
    "strategy_allocations",
    "execution_signals",
    "jq_execution_reports",
)


def test_pr03_schema_declares_expected_core_tables() -> None:
    """The PR-03 schema should stay scoped to the agreed core table list."""
    assert PR03_CORE_TABLE_NAMES == EXPECTED_PR03_TABLES


def test_initialize_store_creates_database_parquet_dir_and_tables(tmp_path: Path) -> None:
    """One command should prepare the local DuckDB file and all core tables."""
    db_path = tmp_path / "ashare.duckdb"
    parquet_dir = tmp_path / "parquet"

    result = initialize_ashare_store(database_path=db_path, parquet_dir=parquet_dir)

    assert result.database_path == db_path.resolve()
    assert result.parquet_dir == parquet_dir.resolve()
    assert db_path.exists()
    assert parquet_dir.is_dir()
    assert result.tables == EXPECTED_PR03_TABLES


def test_initialize_store_is_idempotent_and_preserves_existing_rows(tmp_path: Path) -> None:
    """Repeated initialization must not wipe user data already written."""
    store = AShareDataStore(database_path=tmp_path / "ashare.duckdb")
    store.initialize()

    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO assets (ticker, ticker_name, exchange, asset_type, active)
            VALUES ('600519.SH', '贵州茅台', 'SH', 'stock', true)
            """
        )

    second = store.initialize()

    assert second.tables == EXPECTED_PR03_TABLES
    with store.connect(read_only=True) as conn:
        row = conn.execute(
            "SELECT ticker, ticker_name, market, active FROM assets WHERE ticker = ?",
            ["600519.SH"],
        ).fetchone()

    assert row == ("600519.SH", "贵州茅台", "CN_A", True)


def test_core_tables_include_requirement_fields(tmp_path: Path) -> None:
    """Tables should expose the key fields from the product requirements."""
    store = AShareDataStore(database_path=tmp_path / "ashare.duckdb")
    store.initialize()

    assert {
        "ticker",
        "ticker_name",
        "market",
        "exchange",
        "asset_type",
        "listed_date",
        "active",
    }.issubset(store.table_columns("assets"))
    assert {"publish_time", "crawl_time", "content_hash", "raw_json"}.issubset(
        store.table_columns("raw_documents")
    )
    assert {
        "knowable_time",
        "tradable_time",
        "a_share_relevance_score",
        "policy_level",
    }.issubset(store.table_columns("events"))
    assert {"as_of_date", "ticker", "event_heat_score", "risk_flag", "included"}.issubset(
        store.table_columns("candidate_pool")
    )
    assert {
        "trade_date",
        "sector_id",
        "event_heat",
        "market_confirm",
        "sector_heat_score",
        "cycle_stage",
    }.issubset(store.table_columns("sector_scores"))
    assert {"signal_id", "status", "target_weight", "approved_at"}.issubset(
        store.table_columns("execution_signals")
    )
    assert {"report_id", "order_status", "raw_report", "error_message"}.issubset(
        store.table_columns("jq_execution_reports")
    )


def test_candidate_pool_round_trip(tmp_path: Path) -> None:
    """The initialized store should support a basic PR-03 read/write flow."""
    store = AShareDataStore(database_path=tmp_path / "ashare.duckdb")
    store.initialize()

    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO candidate_pool (
              as_of_date, ticker, ticker_name, source, sector_id, sector_name,
              theme, stock_score, included, reason
            )
            VALUES (
              DATE '2026-06-19', '300750.SZ', '宁德时代', 'user_added',
              'battery', '电池', '固态电池', 0.82, true, 'PR-03 read/write smoke'
            )
            """
        )
        rows = conn.execute(
            """
            SELECT ticker, ticker_name, market, theme, included
            FROM candidate_pool
            WHERE as_of_date = DATE '2026-06-19'
            """
        ).fetchall()

    assert rows == [("300750.SZ", "宁德时代", "CN_A", "固态电池", True)]
