"""Tests for Codex-facing JoinQuant orchestration tasks."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ashare_data.store import AShareDataStore
from src.joinquant_orchestration.service import JoinQuantTaskError, JoinQuantTaskService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


def test_joinquant_task_service_creates_fallback_task_and_lists_it(store: AShareDataStore) -> None:
    service = JoinQuantTaskService(store=store)

    task = service.create_task(
        source_idea_id="idea_ai",
        portfolio_id="cn_a_main",
        signal_date="2026-06-21",
        task_type="backtest",
    )
    listed = service.list_tasks()

    assert task["status"] == "waiting_confirm"
    assert task["source_idea_id"] == "idea_ai"
    assert task["task_package"]["package_status"] in {"copy_package_ready", "needs_signal_package"}
    assert task["task_package"]["safety_guardrails"]["submits_live_orders"] is False
    assert listed[0]["task_id"] == task["task_id"]
    assert listed[0]["research_only"] is True
    assert listed[0]["live_trading"] is False


def test_joinquant_task_service_updates_status_and_result_summary(store: AShareDataStore) -> None:
    service = JoinQuantTaskService(store=store)
    task = service.create_task(source_strategy_id="spec_ai", signal_date="2026-06-21")

    updated = service.update_task(
        task["task_id"],
        status="completed",
        result_summary={"annual_return": 0.18, "max_drawdown": -0.09},
        evidence=[{"type": "screenshot", "path": "local://joinquant/result.png"}],
    )

    assert updated["status"] == "completed"
    assert updated["result_summary"]["annual_return"] == pytest.approx(0.18)
    assert updated["evidence"][0]["type"] == "screenshot"


def test_joinquant_task_service_rejects_missing_source(store: AShareDataStore) -> None:
    service = JoinQuantTaskService(store=store)

    with pytest.raises(JoinQuantTaskError, match="请提供 source_strategy_id 或 source_idea_id"):
        service.create_task(signal_date="2026-06-21")
