"""PR-01 A-share-only research policy guardrails."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

import api_server
from backtest.correlation import compute_correlation_matrix
from backtest.runner import BacktestConfigSchema
from src.market_policy import (
    MarketPolicyError,
    agent_market_boundary_prompt,
    validate_a_share_codes,
    validate_backtest_config,
)
from src.tools.backtest_tool import run_backtest
from src.tools.propose_mandate_tool import ProposeMandateProfilesTool


@pytest.fixture(autouse=True)
def enable_cn_a_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR-01 default product mode is A-share research-only."""
    monkeypatch.setenv("CN_A_ONLY", "1")


def test_a_share_codes_are_normalized_and_allowed() -> None:
    assert validate_a_share_codes(["600519.sh", "300750.SZ", "000001.sz"]) == [
        "600519.SH",
        "300750.SZ",
        "000001.SZ",
    ]


@pytest.mark.parametrize("code", ["AAPL.US", "0700.HK", "BTC-USDT"])
def test_non_a_share_symbols_are_rejected(code: str) -> None:
    with pytest.raises(MarketPolicyError, match="CN_A_ONLY"):
        validate_a_share_codes([code], surface="research")


def test_backtest_config_is_daily_long_only_cash_only_and_draft() -> None:
    checked = validate_backtest_config(
        {
            "codes": ["600519.sh"],
            "source": "tushare",
            "engine": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
    )

    assert checked["codes"] == ["600519.SH"]
    assert checked["source"] == "tushare"
    assert checked["engine"] == "daily"
    assert checked["leverage"] == 1.0
    assert checked["trade_plan_status"] == "draft"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", "okx"),
        ("source", "yfinance"),
        ("engine", "options"),
        ("leverage", 2),
        ("allow_short", True),
        ("crypto", True),
        ("futures", True),
        ("forex", True),
    ],
)
def test_backtest_config_rejects_disabled_markets_and_trade_modes(field: str, value: object) -> None:
    config = {
        "codes": ["600519.SH"],
        "source": "tushare",
        "engine": "daily",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        field: value,
    }

    with pytest.raises(MarketPolicyError, match="CN_A_ONLY"):
        validate_backtest_config(config)


def test_backtest_schema_applies_policy_before_runner_execution() -> None:
    schema = BacktestConfigSchema(
        codes=["600519.sh"],
        source="tushare",
        start_date="2024-01-01",
        end_date="2024-01-05",
    )

    assert schema.codes == ["600519.SH"]
    assert schema.source == "tushare"
    assert schema.model_dump(mode="python")["trade_plan_status"] == "draft"
    assert schema.model_dump(mode="python")["leverage"] == 1.0

    with pytest.raises(ValueError, match="CN_A_ONLY"):
        BacktestConfigSchema(
            codes=["AAPL.US"],
            source="yfinance",
            start_date="2024-01-01",
            end_date="2024-01-05",
        )


def test_backtest_tool_rejects_crypto_before_generated_code_runs(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "code").mkdir(parents=True)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "source": "okx",
                "codes": ["BTC-USDT"],
                "start_date": "2024-01-01",
                "end_date": "2024-01-05",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "code" / "signal_engine.py").write_text(
        "class SignalEngine:\n    def generate(self, data_map):\n        raise AssertionError('should not run')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))

    body = json.loads(run_backtest(str(run_dir)))

    assert body["status"] == "error"
    assert "CN_A_ONLY" in body["error"]


def test_correlation_rejects_non_a_share_before_fetching_data() -> None:
    with pytest.raises(MarketPolicyError, match="CN_A_ONLY"):
        compute_correlation_matrix(["BTC-USDT", "ETH-USDT"], days=30)


def test_agent_prompt_states_research_only_boundary() -> None:
    prompt = agent_market_boundary_prompt()

    assert "CN_A_ONLY is enabled" in prompt
    assert "600519.SH" in prompt
    assert "AAPL.US" in prompt
    assert "BTC-USDT" in prompt
    assert "No automatic order placement" in prompt
    assert "no short selling, no leverage, no derivatives" in prompt


def test_live_enablement_is_blocked_by_default() -> None:
    for action in ("live.authorize", "mandate.commit", "live.resume", "live.runner.start"):
        with pytest.raises(HTTPException) as exc:
            api_server._deny_live_action_in_cn_a_only(action)
        assert exc.value.status_code == 403
        assert "research mode" in exc.value.detail


def test_mandate_proposal_tool_is_disabled_in_research_mode() -> None:
    payload = json.loads(
        ProposeMandateProfilesTool().execute(
            broker="robinhood",
            ceilings={"account_funding_usd": 1000, "max_total_exposure_usd": 1000},
        )
    )

    assert payload["status"] == "error"
    assert "CN_A_ONLY" in payload["error"]
