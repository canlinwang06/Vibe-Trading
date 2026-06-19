"""PR-10 tests for auditable A-share strategy templates."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.strategy_lab.service import STRATEGY_TEMPLATES, StrategyLabError, StrategyLabService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def strategy_lab(store: AShareDataStore) -> StrategyLabService:
    return StrategyLabService(store=store)


def test_strategy_templates_expose_eight_auditable_templates(strategy_lab: StrategyLabService) -> None:
    templates = strategy_lab.list_templates()

    assert len(templates) == 8
    assert {template["strategy_type"] for template in templates} == {
        template.strategy_type for template in STRATEGY_TEMPLATES
    }
    assert all(template["signal_rules"] for template in templates)
    assert all(template["risk_notes"] for template in templates)


def test_seed_strategy_specs_writes_twenty_four_variants(strategy_lab: StrategyLabService) -> None:
    first = strategy_lab.seed_strategy_specs()
    second = strategy_lab.seed_strategy_specs()
    specs = strategy_lab.list_strategy_specs(limit=100)

    assert first["strategy_specs_written"] == 24
    assert first["total_expected_specs"] == 24
    assert second["strategy_specs_written"] == 0
    assert second["strategy_specs_skipped"] == 24
    assert len(specs) == 24
    assert {spec["params"]["execution_mode"] for spec in specs} == {"research_only"}
    assert all(spec["market"] == "CN_A" for spec in specs)
    assert all(spec["enabled"] is True for spec in specs)


def test_create_strategy_spec_validates_template_and_risk_bounds(strategy_lab: StrategyLabService) -> None:
    created = strategy_lab.create_strategy_spec(
        strategy_type="hot_sector_equal_weight",
        strategy_name="S01 自定义均衡策略",
        params={"top_sectors": 3, "top_stocks_per_sector": 4},
        rebalance_freq="weekly",
        holding_period=5,
        max_position=0.08,
        max_sector_exposure=0.35,
        max_total_exposure=0.65,
        stop_loss=0.08,
        take_profit=0.18,
    )

    assert created["strategy_type"] == "hot_sector_equal_weight"
    assert created["params"]["execution_mode"] == "research_only"
    assert created["params"]["data_inputs"] == ["candidate_pool", "sector_scores"]

    with pytest.raises(StrategyLabError, match="不支持的策略模板类型"):
        strategy_lab.create_strategy_spec(
            strategy_type="random_ai_strategy",
            strategy_name="不可审计随机策略",
            params={},
            rebalance_freq="daily",
            holding_period=5,
            max_position=0.08,
            max_sector_exposure=0.35,
            max_total_exposure=0.65,
            stop_loss=0.08,
            take_profit=0.18,
        )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_strategy_lab_api_seed_list_and_create_round_trip(client: TestClient) -> None:
    templates = client.get("/api/strategy-lab/templates")
    assert templates.status_code == 200
    assert templates.json()["template_count"] == 8

    seed = client.post("/api/strategy-lab/specs/seed", json={"replace": False})
    assert seed.status_code == 200
    assert seed.json()["strategy_specs_written"] == 24

    specs = client.get("/api/strategy-lab/specs")
    assert specs.status_code == 200
    assert specs.json()["spec_count"] == 24
    assert specs.json()["strategy_specs"][0]["params"]["execution_mode"] == "research_only"

    create = client.post(
        "/api/strategy-lab/specs",
        json={
            "strategy_type": "defensive_cash",
            "strategy_name": "S08 自定义防守现金策略",
            "params": {"cash_floor": 0.4},
            "rebalance_freq": "weekly",
            "holding_period": 5,
            "max_position": 0.04,
            "max_sector_exposure": 0.18,
            "max_total_exposure": 0.3,
            "stop_loss": 0.04,
            "take_profit": 0.08,
        },
    )
    assert create.status_code == 200
    assert create.json()["strategy_type"] == "defensive_cash"


def test_strategy_lab_api_returns_chinese_error_for_unknown_template(client: TestClient) -> None:
    response = client.post(
        "/api/strategy-lab/specs",
        json={
            "strategy_type": "random_ai_strategy",
            "strategy_name": "不可审计随机策略",
            "params": {},
            "rebalance_freq": "daily",
            "holding_period": 5,
            "max_position": 0.08,
            "max_sector_exposure": 0.35,
            "max_total_exposure": 0.65,
            "stop_loss": 0.08,
            "take_profit": 0.18,
        },
    )

    assert response.status_code == 400
    assert "不支持的策略模板类型" in response.json()["detail"]
