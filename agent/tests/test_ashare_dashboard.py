"""Tests for chart-first A-share dashboard presentation services."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ashare_data.store import AShareDataStore
from src.ashare_dashboard.service import AShareDashboardService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


def _seed_dashboard_inputs(store: AShareDataStore) -> None:
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
              DATE '2026-06-21', 'theme_ai_compute', 'AI算力', 0.88, 0.72,
              0.64, 0.80, 0.76, 0.58, 0.86, 'rising', now()
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
              'evt_ai', 'cluster_ai', 'doc_ai', TIMESTAMP '2026-06-21 09:45:00',
              TIMESTAMP '2026-06-21 09:45:00', TIMESTAMP '2026-06-21 09:50:00',
              TIMESTAMP '2026-06-21 09:50:00', TIMESTAMP '2026-06-21 09:50:00',
              'industry', 'AI算力', '国产算力招标扩容进入市场关注区。',
              'positive', 82, 70, 0.76, 0.88, NULL, now()
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_documents (
              doc_id, source_id, source_name, source_type, title, content,
              summary, publish_time, crawl_time, url, content_hash, language,
              author_or_account, hot_rank, hot_value, raw_json, credibility, created_at
            )
            VALUES (
              'doc_ai', 'eastmoney_news', '东方财富财经', 'finance_news',
              'AI 算力产业链热度提升', 'AI 算力、光模块和服务器受到关注。',
              'AI 算力热度提升。', TIMESTAMP '2026-06-21 09:45:00',
              TIMESTAMP '2026-06-21 09:50:00', 'https://example.com/ai',
              'hash_ai', 'zh-CN', NULL, 1, 99.0, '{}', 0.8, now()
            )
            """
        )
        conn.execute(
            """
            INSERT INTO candidate_pool (
              as_of_date, ticker, ticker_name, source, sector_id, sector_name,
              theme, event_heat_score, sector_heat_score, stock_score,
              user_priority, risk_flag, included, reason, created_at
            )
            VALUES (
              DATE '2026-06-21', '300308.SZ', '中际旭创', 'sector_radar',
              'theme_optical_module', '光模块', 'AI算力', 0.88, 0.81,
              0.91, 0, 'normal', true, '光模块龙头，AI算力链高相关。', now()
            )
            """
        )
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
              'balanced', 5, 'weekly', 82.5, 'generated',
              'AI算力 当前具备热点板块等权回测条件。',
              ?, ?, ?, ?, ?, ?, ?, ?, now(), now()
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


def test_daily_intelligence_summarizes_local_events_and_sector_heat(store: AShareDataStore) -> None:
    _seed_dashboard_inputs(store)
    result = AShareDashboardService(store=store).daily_intelligence(as_of_date="2026-06-21")

    assert result["data_mode"] == "local"
    assert result["research_only"] is True
    assert result["live_trading"] is False
    assert result["market_temperature"]["score"] > 0
    assert result["sector_heat"][0]["sector_name"] == "AI算力"
    assert result["event_timeline"][0]["source_url"] == "https://example.com/ai"
    assert any(action.startswith("让 Codex") for action in result["codex_actions"])


def test_sector_stock_analysis_returns_candidate_matrix_and_strategy_cards(store: AShareDataStore) -> None:
    _seed_dashboard_inputs(store)
    result = AShareDashboardService(store=store).sector_stock_analysis(
        as_of_date="2026-06-21",
        theme="AI算力",
    )

    assert result["data_mode"] == "local"
    assert result["sector_score"]["theme"] == "AI算力"
    assert result["candidate_pool"][0]["ticker_name"] == "中际旭创"
    assert result["candidate_matrix"][0]["ticker"] == "300308.SZ"
    assert result["candidate_matrix"][0]["leader_score"] > 0.8
    assert result["strategy_ideas"][0]["strategy_name"] == "AI算力热点板块等权策略"
