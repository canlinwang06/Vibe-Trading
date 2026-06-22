"""Tests for strategy lifecycle scoring and overview."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ashare_data.store import AShareDataStore
from src.strategy_lifecycle.service import StrategyLifecycleService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


def _seed_lifecycle_inputs(store: AShareDataStore) -> None:
    store.initialize()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO strategy_ideas (
              idea_id, as_of_date, theme, strategy_type, strategy_name,
              strategy_family, idea_category, risk_preference, holding_period,
              rebalance_freq, idea_score, status, thesis, candidate_tickers_json,
              sector_ids_json, source_event_ids_json, entry_rules_json,
              exit_rules_json, risk_controls_json, params_json, evidence_json,
              created_at, updated_at
            )
            VALUES (
              'idea_ai', DATE '2026-06-21', 'AI算力', 'hot_sector_equal_weight',
              'AI算力热点板块等权策略', '板块轮动', '热点板块等权',
              'balanced', 5, 'weekly', 82.5, 'saved_to_strategy_lab',
              'AI算力 当前具备热点板块等权回测条件。',
              ?, ?, ?, ?, ?, ?, ?, ?, TIMESTAMP '2026-06-21 09:30:00',
              TIMESTAMP '2026-06-21 09:30:00'
            )
            """,
            [
                json.dumps([{"ticker": "300308.SZ", "ticker_name": "中际旭创", "stock_score": 0.91}], ensure_ascii=False),
                json.dumps(["theme_ai_compute"], ensure_ascii=False),
                json.dumps(["evt_ai"], ensure_ascii=False),
                json.dumps(["主题限定为 AI算力"], ensure_ascii=False),
                json.dumps(["持有 5 个交易日后重新评估"], ensure_ascii=False),
                json.dumps(["单股最大仓位 8%"], ensure_ascii=False),
                json.dumps({"execution_mode": "research_only"}, ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
            ],
        )
        conn.execute(
            """
            INSERT INTO strategy_specs (
              strategy_id, strategy_name, market, strategy_type, params_json,
              rebalance_freq, holding_period, max_position, max_sector_exposure,
              max_total_exposure, stop_loss, take_profit, enabled,
              created_at, updated_at
            )
            VALUES (
              'spec_ai', 'AI算力热点板块等权策略', 'CN_A',
              'hot_sector_equal_weight', ?, 'weekly', 5, 0.08, 0.35,
              0.65, 0.08, 0.18, true, TIMESTAMP '2026-06-21 09:35:00',
              TIMESTAMP '2026-06-21 09:35:00'
            )
            """,
            [json.dumps({"source_strategy_idea_id": "idea_ai", "theme": "AI算力"}, ensure_ascii=False)],
        )
        conn.execute(
            """
            INSERT INTO backtest_runs (
              run_id, strategy_id, market, start_date, end_date, universe_id,
              benchmark, total_return, annual_return, max_drawdown, sharpe,
              sortino, calmar, win_rate, profit_loss_ratio, turnover,
              trade_count, avg_holding_days, excess_return, information_ratio,
              status, artifacts_path, created_at
            )
            VALUES (
              'run_ai', 'spec_ai', 'CN_A', DATE '2026-01-01', DATE '2026-06-21',
              'cn_a_ai', '000300.SH', 0.12, 0.18, -0.09, 1.32, 1.1, 1.4,
              0.56, 1.2, 0.8, 40, 5.0, 0.08, 0.9, 'ok',
              'artifacts/run_ai', TIMESTAMP '2026-06-21 15:00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO jq_orchestration_tasks (
              task_id, source_strategy_id, source_idea_id, portfolio_id,
              signal_date, task_type, status, task_package_json,
              result_summary_json, evidence_json, error_message,
              fallback_instruction, created_by, created_at, updated_at
            )
            VALUES (
              'jqtask_ai', 'spec_ai', 'idea_ai', 'cn_a_main', DATE '2026-06-21',
              'backtest', 'completed', '{}', '{}', '[]', NULL,
              '手动复制 strategy.py 到聚宽。', 'codex',
              TIMESTAMP '2026-06-21 15:05:00', TIMESTAMP '2026-06-21 15:05:00'
            )
            """
        )


def test_strategy_lifecycle_refreshes_from_idea_backtest_and_joinquant_task(store: AShareDataStore) -> None:
    _seed_lifecycle_inputs(store)
    service = StrategyLifecycleService(store=store)

    rows = service.refresh_lifecycle()
    overview = service.overview(refresh=False)

    assert len(rows) == 1
    row = rows[0]
    assert row["strategy_id"] == "spec_ai"
    assert row["lifecycle_state"] == "paper_trading"
    assert row["backtest_count"] == 1
    assert row["best_annual_return"] == pytest.approx(0.18)
    assert overview["data_mode"] == "local"
    assert overview["funnel"]
    assert overview["recommendations"][0]["strategy_id"] == "spec_ai"
    assert overview["events"][0]["strategy_id"] == "spec_ai"
