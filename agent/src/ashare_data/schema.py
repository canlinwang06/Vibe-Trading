"""DuckDB schema for the PR-03 A-share local research data store."""

from __future__ import annotations

from dataclasses import dataclass

PR03_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TableSpec:
    """Declarative schema unit for one PR-03 core table."""

    name: str
    sql: str


PR03_CORE_TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "assets",
        """
        CREATE TABLE IF NOT EXISTS assets (
          ticker VARCHAR PRIMARY KEY,
          ticker_name VARCHAR,
          market VARCHAR DEFAULT 'CN_A',
          exchange VARCHAR,
          asset_type VARCHAR,
          listed_date DATE,
          delisted_date DATE,
          active BOOLEAN,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "source_registry",
        """
        CREATE TABLE IF NOT EXISTS source_registry (
          source_id VARCHAR PRIMARY KEY,
          source_name VARCHAR,
          source_type VARCHAR,
          endpoint_type VARCHAR,
          url_or_route TEXT,
          fetch_interval_minutes INTEGER,
          parser VARCHAR,
          credibility DOUBLE,
          legal_mode VARCHAR,
          enabled BOOLEAN,
          last_fetch_time TIMESTAMP,
          created_at TIMESTAMP,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "raw_documents",
        """
        CREATE TABLE IF NOT EXISTS raw_documents (
          doc_id VARCHAR PRIMARY KEY,
          source_id VARCHAR,
          source_name VARCHAR,
          source_type VARCHAR,
          title VARCHAR,
          content TEXT,
          summary TEXT,
          publish_time TIMESTAMP,
          crawl_time TIMESTAMP,
          url TEXT,
          content_hash VARCHAR,
          language VARCHAR,
          author_or_account VARCHAR,
          hot_rank INTEGER,
          hot_value DOUBLE,
          raw_json TEXT,
          credibility DOUBLE,
          created_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "event_clusters",
        """
        CREATE TABLE IF NOT EXISTS event_clusters (
          cluster_id VARCHAR PRIMARY KEY,
          first_seen_time TIMESTAMP,
          last_seen_time TIMESTAMP,
          main_title VARCHAR,
          event_type VARCHAR,
          event_subtype VARCHAR,
          summary TEXT,
          sentiment VARCHAR,
          intensity INTEGER,
          novelty INTEGER,
          hot_score DOUBLE,
          a_share_relevance_score DOUBLE,
          source_count INTEGER,
          mention_count INTEGER,
          cross_platform_score DOUBLE,
          status VARCHAR,
          created_at TIMESTAMP,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "event_mentions",
        """
        CREATE TABLE IF NOT EXISTS event_mentions (
          mention_id VARCHAR PRIMARY KEY,
          cluster_id VARCHAR,
          doc_id VARCHAR,
          source_id VARCHAR,
          source_name VARCHAR,
          publish_time TIMESTAMP,
          crawl_time TIMESTAMP,
          hot_rank INTEGER,
          hot_value DOUBLE,
          mention_weight DOUBLE,
          created_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "events",
        """
        CREATE TABLE IF NOT EXISTS events (
          event_id VARCHAR PRIMARY KEY,
          cluster_id VARCHAR,
          doc_id VARCHAR,
          event_time TIMESTAMP,
          publish_time TIMESTAMP,
          crawl_time TIMESTAMP,
          knowable_time TIMESTAMP,
          tradable_time TIMESTAMP,
          event_type VARCHAR,
          event_subtype VARCHAR,
          summary TEXT,
          sentiment VARCHAR,
          intensity INTEGER,
          novelty INTEGER,
          certainty DOUBLE,
          a_share_relevance_score DOUBLE,
          policy_level VARCHAR,
          created_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "theme_map",
        """
        CREATE TABLE IF NOT EXISTS theme_map (
          theme VARCHAR,
          sub_theme VARCHAR,
          keyword VARCHAR,
          sector_id VARCHAR,
          sector_name VARCHAR,
          ticker VARCHAR,
          ticker_name VARCHAR,
          relevance DOUBLE,
          evidence TEXT,
          source VARCHAR,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "sectors",
        """
        CREATE TABLE IF NOT EXISTS sectors (
          sector_id VARCHAR PRIMARY KEY,
          sector_name VARCHAR,
          sector_type VARCHAR,
          source VARCHAR,
          active BOOLEAN,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "sector_members",
        """
        CREATE TABLE IF NOT EXISTS sector_members (
          sector_id VARCHAR,
          ticker VARCHAR,
          ticker_name VARCHAR,
          weight DOUBLE,
          relevance DOUBLE,
          start_date DATE,
          end_date DATE,
          source VARCHAR,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "event_sector_map",
        """
        CREATE TABLE IF NOT EXISTS event_sector_map (
          event_id VARCHAR,
          cluster_id VARCHAR,
          sector_id VARCHAR,
          sector_name VARCHAR,
          theme VARCHAR,
          sub_theme VARCHAR,
          relevance DOUBLE,
          direction VARCHAR,
          mapping_reason TEXT,
          created_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "event_stock_map",
        """
        CREATE TABLE IF NOT EXISTS event_stock_map (
          event_id VARCHAR,
          cluster_id VARCHAR,
          ticker VARCHAR,
          ticker_name VARCHAR,
          theme VARCHAR,
          sector_id VARCHAR,
          relevance DOUBLE,
          direction VARCHAR,
          mapping_reason TEXT,
          created_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "event_reactions",
        """
        CREATE TABLE IF NOT EXISTS event_reactions (
          reaction_id VARCHAR PRIMARY KEY,
          cluster_id VARCHAR,
          event_id VARCHAR,
          target_type VARCHAR,
          target_id VARCHAR,
          target_name VARCHAR,
          "window" VARCHAR,
          raw_return DOUBLE,
          benchmark_return DOUBLE,
          sector_return DOUBLE,
          abnormal_return DOUBLE,
          max_drawdown DOUBLE,
          volume_change DOUBLE,
          breadth_change DOUBLE,
          calculated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "market_daily",
        """
        CREATE TABLE IF NOT EXISTS market_daily (
          trade_date DATE,
          ticker VARCHAR,
          open DOUBLE,
          high DOUBLE,
          low DOUBLE,
          close DOUBLE,
          volume DOUBLE,
          amount DOUBLE,
          turnover DOUBLE,
          adj_factor DOUBLE,
          limit_status VARCHAR,
          suspended BOOLEAN,
          source VARCHAR,
          created_at TIMESTAMP,
          PRIMARY KEY (trade_date, ticker)
        )
        """,
    ),
    TableSpec(
        "collector_runs",
        """
        CREATE TABLE IF NOT EXISTS collector_runs (
          run_id VARCHAR PRIMARY KEY,
          run_date DATE,
          collector_type VARCHAR,
          source_id VARCHAR,
          status VARCHAR,
          rows_requested INTEGER,
          rows_written INTEGER,
          error_message TEXT,
          metadata_json TEXT,
          started_at TIMESTAMP,
          ended_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "sector_daily",
        """
        CREATE TABLE IF NOT EXISTS sector_daily (
          trade_date DATE,
          sector_id VARCHAR,
          sector_name VARCHAR,
          open DOUBLE,
          high DOUBLE,
          low DOUBLE,
          close DOUBLE,
          return DOUBLE,
          amount DOUBLE,
          turnover DOUBLE,
          up_count INTEGER,
          down_count INTEGER,
          limit_up_count INTEGER,
          member_count INTEGER,
          leading_ticker VARCHAR,
          source VARCHAR,
          created_at TIMESTAMP,
          PRIMARY KEY (trade_date, sector_id)
        )
        """,
    ),
    TableSpec(
        "stock_anomaly_snapshots",
        """
        CREATE TABLE IF NOT EXISTS stock_anomaly_snapshots (
          trade_date DATE,
          ticker VARCHAR,
          ticker_name VARCHAR,
          anomaly_type VARCHAR,
          pct_change DOUBLE,
          amount DOUBLE,
          turnover DOUBLE,
          volume_ratio DOUBLE,
          limit_status VARCHAR,
          sector_name VARCHAR,
          source VARCHAR,
          evidence_json TEXT,
          created_at TIMESTAMP,
          PRIMARY KEY (trade_date, ticker, anomaly_type)
        )
        """,
    ),
    TableSpec(
        "sector_scores",
        """
        CREATE TABLE IF NOT EXISTS sector_scores (
          trade_date DATE,
          sector_id VARCHAR,
          sector_name VARCHAR,
          event_heat DOUBLE,
          market_confirm DOUBLE,
          breadth_score DOUBLE,
          flow_score DOUBLE,
          persistence_score DOUBLE,
          crowding_risk DOUBLE,
          sector_heat_score DOUBLE,
          cycle_stage VARCHAR,
          created_at TIMESTAMP,
          PRIMARY KEY (trade_date, sector_id)
        )
        """,
    ),
    TableSpec(
        "candidate_pool",
        """
        CREATE TABLE IF NOT EXISTS candidate_pool (
          as_of_date DATE,
          ticker VARCHAR,
          ticker_name VARCHAR,
          market VARCHAR DEFAULT 'CN_A',
          source VARCHAR,
          sector_id VARCHAR,
          sector_name VARCHAR,
          theme VARCHAR,
          event_heat_score DOUBLE,
          sector_heat_score DOUBLE,
          stock_score DOUBLE,
          user_priority INTEGER,
          risk_flag VARCHAR,
          included BOOLEAN,
          reason TEXT,
          created_at TIMESTAMP,
          PRIMARY KEY (as_of_date, ticker)
        )
        """,
    ),
    TableSpec(
        "strategy_specs",
        """
        CREATE TABLE IF NOT EXISTS strategy_specs (
          strategy_id VARCHAR PRIMARY KEY,
          strategy_name VARCHAR,
          market VARCHAR DEFAULT 'CN_A',
          strategy_type VARCHAR,
          params_json TEXT,
          rebalance_freq VARCHAR,
          holding_period INTEGER,
          max_position DOUBLE,
          max_sector_exposure DOUBLE,
          max_total_exposure DOUBLE,
          stop_loss DOUBLE,
          take_profit DOUBLE,
          enabled BOOLEAN,
          created_at TIMESTAMP,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "strategy_ideas",
        """
        CREATE TABLE IF NOT EXISTS strategy_ideas (
          idea_id VARCHAR PRIMARY KEY,
          as_of_date DATE,
          theme VARCHAR,
          strategy_type VARCHAR,
          strategy_name VARCHAR,
          strategy_family VARCHAR,
          idea_category VARCHAR,
          risk_preference VARCHAR,
          holding_period INTEGER,
          rebalance_freq VARCHAR,
          idea_score DOUBLE,
          status VARCHAR,
          thesis TEXT,
          candidate_tickers_json TEXT,
          sector_ids_json TEXT,
          source_event_ids_json TEXT,
          entry_rules_json TEXT,
          exit_rules_json TEXT,
          risk_controls_json TEXT,
          params_json TEXT,
          evidence_json TEXT,
          created_at TIMESTAMP,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "backtest_runs",
        """
        CREATE TABLE IF NOT EXISTS backtest_runs (
          run_id VARCHAR PRIMARY KEY,
          strategy_id VARCHAR,
          market VARCHAR DEFAULT 'CN_A',
          start_date DATE,
          end_date DATE,
          universe_id VARCHAR,
          benchmark VARCHAR DEFAULT '000300.SH',
          total_return DOUBLE,
          annual_return DOUBLE,
          max_drawdown DOUBLE,
          sharpe DOUBLE,
          sortino DOUBLE,
          calmar DOUBLE,
          win_rate DOUBLE,
          profit_loss_ratio DOUBLE,
          turnover DOUBLE,
          trade_count INTEGER,
          avg_holding_days DOUBLE,
          excess_return DOUBLE,
          information_ratio DOUBLE,
          status VARCHAR,
          artifacts_path TEXT,
          created_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "strategy_allocations",
        """
        CREATE TABLE IF NOT EXISTS strategy_allocations (
          as_of_date DATE,
          portfolio_id VARCHAR,
          strategy_id VARCHAR,
          strategy_score DOUBLE,
          risk_score DOUBLE,
          volatility DOUBLE,
          correlation_penalty DOUBLE,
          allocated_weight DOUBLE,
          reason TEXT,
          created_at TIMESTAMP,
          PRIMARY KEY (as_of_date, portfolio_id, strategy_id)
        )
        """,
    ),
    TableSpec(
        "execution_signals",
        """
        CREATE TABLE IF NOT EXISTS execution_signals (
          signal_id VARCHAR PRIMARY KEY,
          signal_date DATE,
          valid_for DATE,
          portfolio_id VARCHAR,
          ticker VARCHAR,
          ticker_name VARCHAR,
          target_weight DOUBLE,
          current_weight DOUBLE,
          action VARCHAR,
          strategy_sources TEXT,
          theme VARCHAR,
          reason TEXT,
          risk TEXT,
          status VARCHAR,
          created_at TIMESTAMP,
          approved_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "jq_execution_reports",
        """
        CREATE TABLE IF NOT EXISTS jq_execution_reports (
          report_id VARCHAR PRIMARY KEY,
          signal_date DATE,
          trade_date DATE,
          portfolio_id VARCHAR,
          ticker VARCHAR,
          planned_weight DOUBLE,
          executed_weight DOUBLE,
          order_status VARCHAR,
          fill_price DOUBLE,
          fill_amount DOUBLE,
          error_message TEXT,
          raw_report TEXT,
          created_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "jq_orchestration_tasks",
        """
        CREATE TABLE IF NOT EXISTS jq_orchestration_tasks (
          task_id VARCHAR PRIMARY KEY,
          source_strategy_id VARCHAR,
          source_idea_id VARCHAR,
          portfolio_id VARCHAR,
          signal_date DATE,
          task_type VARCHAR,
          status VARCHAR,
          task_package_json TEXT,
          result_summary_json TEXT,
          evidence_json TEXT,
          error_message TEXT,
          fallback_instruction TEXT,
          created_by VARCHAR,
          created_at TIMESTAMP,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "strategy_lifecycle",
        """
        CREATE TABLE IF NOT EXISTS strategy_lifecycle (
          strategy_id VARCHAR PRIMARY KEY,
          idea_id VARCHAR,
          strategy_name VARCHAR,
          theme VARCHAR,
          lifecycle_state VARCHAR,
          health_score DOUBLE,
          recommendation VARCHAR,
          reason TEXT,
          first_seen_date DATE,
          last_review_date DATE,
          paper_days INTEGER,
          signal_count INTEGER,
          backtest_count INTEGER,
          best_annual_return DOUBLE,
          worst_max_drawdown DOUBLE,
          avg_sharpe DOUBLE,
          win_rate DOUBLE,
          evidence_json TEXT,
          research_only BOOLEAN,
          live_trading BOOLEAN,
          created_at TIMESTAMP,
          updated_at TIMESTAMP
        )
        """,
    ),
    TableSpec(
        "strategy_lifecycle_events",
        """
        CREATE TABLE IF NOT EXISTS strategy_lifecycle_events (
          event_id VARCHAR PRIMARY KEY,
          strategy_id VARCHAR,
          event_time TIMESTAMP,
          from_state VARCHAR,
          to_state VARCHAR,
          reason TEXT,
          evidence_json TEXT,
          created_by VARCHAR,
          research_only BOOLEAN,
          live_trading BOOLEAN
        )
        """,
    ),
)

PR03_CORE_TABLE_NAMES = tuple(table.name for table in PR03_CORE_TABLES)
