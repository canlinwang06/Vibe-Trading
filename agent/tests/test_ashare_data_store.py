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
    "event_reactions",
    "market_daily",
    "collector_runs",
    "sector_daily",
    "stock_anomaly_snapshots",
    "sector_scores",
    "candidate_pool",
    "strategy_specs",
    "strategy_ideas",
    "backtest_runs",
    "strategy_allocations",
    "execution_signals",
    "jq_execution_reports",
    "jq_orchestration_tasks",
    "strategy_lifecycle",
    "strategy_lifecycle_events",
    "portfolios",
    "positions",
    "advisor_transactions",
    "position_lots",
    "investment_theses",
    "watchlist_items",
    "advisor_action_recommendations",
    "advisor_action_snapshots",
    "advisor_command_events",
    "external_validation_results",
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


def test_store_reads_tables_while_write_connection_is_open(tmp_path: Path) -> None:
    """The local API may inspect schema while another request holds a write connection."""
    store = AShareDataStore(database_path=tmp_path / "ashare.duckdb")
    store.initialize()

    with store.connect(read_only=False) as conn:
        conn.execute("SELECT 1").fetchone()
        assert store.list_tables() == EXPECTED_PR03_TABLES


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
    assert {"idea_id", "strategy_type", "idea_score", "candidate_tickers_json"}.issubset(
        store.table_columns("strategy_ideas")
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
    assert {"run_id", "collector_type", "rows_written", "error_message"}.issubset(
        store.table_columns("collector_runs")
    )
    assert {"anomaly_type", "pct_change", "volume_ratio", "evidence_json"}.issubset(
        store.table_columns("stock_anomaly_snapshots")
    )
    assert {"reaction_id", "window", "abnormal_return", "max_drawdown"}.issubset(
        store.table_columns("event_reactions")
    )
    assert {"portfolio_id", "research_only", "live_trading"}.issubset(
        store.table_columns("portfolios")
    )
    assert {"position_id", "ticker", "average_cost", "status", "thesis_id"}.issubset(
        store.table_columns("positions")
    )
    assert {"transaction_id", "action", "idempotency_key", "live_trading"}.issubset(
        store.table_columns("advisor_transactions")
    )
    assert {"lot_id", "buy_price", "remaining_quantity", "cost_basis"}.issubset(
        store.table_columns("position_lots")
    )
    assert {
        "thesis_id",
        "invalidation_conditions",
        "entry_conditions",
        "exit_conditions",
        "not_buy_conditions",
        "review_frequency_days",
        "next_review_date",
        "completeness_status",
        "evidence_json",
    }.issubset(
        store.table_columns("investment_theses")
    )
    assert {"item_id", "thesis_id", "trigger_price", "not_buy_conditions"}.issubset(
        store.table_columns("watchlist_items")
    )
    assert {"recommendation_id", "action_type", "evidence_json"}.issubset(
        store.table_columns("advisor_action_recommendations")
    )
    assert {"snapshot_id", "headline", "action_summary_json"}.issubset(
        store.table_columns("advisor_action_snapshots")
    )
    assert {"command_id", "idempotency_key", "request_json", "response_json"}.issubset(
        store.table_columns("advisor_command_events")
    )
    assert {"validation_id", "source", "metrics_json", "raw_result_json"}.issubset(
        store.table_columns("external_validation_results")
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


def test_advisor_schema_supports_core_manual_records(tmp_path: Path) -> None:
    """The advisor tables should support portfolio, lot, watchlist, and advice records."""
    store = AShareDataStore(database_path=tmp_path / "ashare.duckdb")
    store.initialize()

    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO portfolios (
              portfolio_id, portfolio_name, research_only, live_trading, status, created_at, updated_at
            )
            VALUES ('cn_a_main', 'A股投资助手组合', true, false, 'active', now(), now())
            """
        )
        conn.execute(
            """
            INSERT INTO positions (
              position_id, portfolio_id, ticker, ticker_name, total_quantity, available_quantity,
              average_cost, invested_cost, realized_pnl, status, first_buy_date, last_trade_date,
              created_at, updated_at
            )
            VALUES (
              'pos_cn_a_300308', 'cn_a_main', '300308.SZ', '中际旭创', 100, 100,
              10.2, 1020, 0, 'open', DATE '2026-06-21', DATE '2026-06-21', now(), now()
            )
            """
        )
        conn.execute(
            """
            INSERT INTO position_lots (
              lot_id, portfolio_id, position_id, ticker, ticker_name, buy_date,
              buy_price, initial_quantity, remaining_quantity, cost_basis, status,
              created_at, updated_at
            )
            VALUES (
              'lot_cn_a_300308_001', 'cn_a_main', 'pos_cn_a_300308', '300308.SZ',
              '中际旭创', DATE '2026-06-21', 10.2, 100, 100, 1020, 'open', now(), now()
            )
            """
        )
        conn.execute(
            """
            INSERT INTO watchlist_items (
              item_id, portfolio_id, ticker, ticker_name, theme, watch_status,
              trigger_price, not_buy_conditions, reason, created_at, updated_at
            )
            VALUES (
              'watch_ai_compute_001', 'cn_a_main', '000977.SZ', '浪潮信息', 'AI算力',
              'waiting_trigger', 42.5, '板块热度退潮不买', '等待买入条件确认', now(), now()
            )
            """
        )
        conn.execute(
            """
            INSERT INTO advisor_action_recommendations (
              recommendation_id, portfolio_id, as_of_date, action_type, action_label,
              ticker, ticker_name, priority, confidence, reason, evidence_json, status, created_at
            )
            VALUES (
              'rec_ai_compute_001', 'cn_a_main', DATE '2026-06-21', 'prepare_buy',
              '等待买点', '000977.SZ', '浪潮信息', 1, 0.72,
              'AI算力仍在扩散，但需要价格触发。', '{"sources":["unit-test"]}', 'active', now()
            )
            """
        )
        conn.execute(
            """
            INSERT INTO external_validation_results (
              validation_id, portfolio_id, source, source_ref, subject_type, subject_id,
              validation_date, status, metrics_json, summary, raw_result_json, created_by, created_at
            )
            VALUES (
              'validation_jq_001', 'cn_a_main', 'joinquant_manual', 'manual-backtest-001',
              'recommendation', 'rec_ai_compute_001', DATE '2026-06-21', 'reviewed',
              '{"annual_return":0.12}', '外部回测结果由 Codex 写回，仅用于研究展示。',
              '{"source":"manual"}', 'codex', now()
            )
            """
        )
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "portfolios",
                "position_lots",
                "watchlist_items",
                "advisor_action_recommendations",
                "external_validation_results",
            )
        }

    assert counts == {
        "portfolios": 1,
        "position_lots": 1,
        "watchlist_items": 1,
        "advisor_action_recommendations": 1,
        "external_validation_results": 1,
    }
