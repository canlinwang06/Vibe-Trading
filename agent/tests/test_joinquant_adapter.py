"""PR-15 tests for JoinQuant mapping and signal export preflight."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.joinquant_adapter.mapper.code_mapper import JoinQuantMappingError, map_ticker
from src.joinquant_adapter.service import JoinQuantExportError, JoinQuantExportService

pytest.importorskip("duckdb")


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def exporter(store: AShareDataStore) -> JoinQuantExportService:
    return JoinQuantExportService(store=store)


def _seed_signals(store: AShareDataStore, *, status: str = "approved", unsupported: bool = False) -> None:
    store.initialize()
    tickers = [
        ("600519.SH", "贵州茅台", 0.08, "buy", "白酒消费"),
        ("300750.SZ", "宁德时代", 0.07, "increase", "新能源"),
        ("000001.SH", "上证指数", 0.04, "hold", "宽基观察"),
    ]
    if unsupported:
        tickers = [("830000.BJ", "北交所样例", 0.03, "buy", "北交所")]
    with store.connect() as conn:
        for strategy_id, weight in [("ai_sector_momentum_v1", 0.20), ("defensive_cash_v1", 0.10)]:
            conn.execute(
                """
                INSERT INTO strategy_allocations (
                  as_of_date, portfolio_id, strategy_id, strategy_score,
                  risk_score, volatility, correlation_penalty,
                  allocated_weight, reason, created_at
                )
                VALUES (DATE '2026-06-23', 'cn_a_main', ?, 78.0, 22.0, 0.12, 0.1, ?, 'PR-15 test', now())
                """,
                [strategy_id, weight],
            )
        for idx, (ticker, ticker_name, target_weight, action, theme) in enumerate(tickers):
            conn.execute(
                """
                INSERT INTO execution_signals (
                  signal_id, signal_date, valid_for, portfolio_id, ticker,
                  ticker_name, target_weight, current_weight, action,
                  strategy_sources, theme, reason, risk, status,
                  created_at, approved_at
                )
                VALUES (?, DATE '2026-06-23', DATE '2026-06-24', 'cn_a_main',
                        ?, ?, ?, 0.0, ?, '["ai_sector_momentum_v1"]',
                        ?, 'PR-15 导出测试', '模拟信号，非实盘指令', ?, now(), now())
                """,
                [f"sig_pr15_{idx}", ticker, ticker_name, target_weight, action, theme, status],
            )


def test_joinquant_ticker_mapping_examples() -> None:
    assert map_ticker("600519.SH") == "600519.XSHG"
    assert map_ticker("300750.SZ") == "300750.XSHE"
    assert map_ticker("000001.SH") == "000001.XSHG"
    assert map_ticker("600519.XSHG") == "600519.XSHG"

    with pytest.raises(JoinQuantMappingError, match="暂不支持"):
        map_ticker("830000.BJ")


def test_export_signals_json_maps_approved_targets(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    exported = exporter.export_signals_json(portfolio_id="cn_a_main", signal_date="2026-06-23")
    payload = exported["payload"]
    tickers = {row["ticker"] for row in payload["targets"]}

    assert exported["status"] == "ok"
    assert exported["validation"]["status"] == "ok"
    assert payload["portfolio_id"] == "cn_a_main"
    assert payload["signal_date"] == "2026-06-23"
    assert payload["valid_for"] == "2026-06-24"
    assert payload["total_exposure"] == pytest.approx(0.19)
    assert {"600519.XSHG", "300750.XSHE", "000001.XSHG"} == tickers
    assert "600519.XSHG" in exported["json_text"]
    assert exported["live_trading"] is False


def test_export_signals_csv_contains_joinquant_tickers(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    exported = exporter.export_signals_csv(portfolio_id="cn_a_main", signal_date="2026-06-23")

    assert exported["status"] == "ok"
    assert exported["row_count"] == 3
    assert "ticker,source_ticker" in exported["csv_text"]
    assert "300750.XSHE,300750.SZ" in exported["csv_text"]
    assert "模拟信号，非实盘指令" in exported["csv_text"]


def test_draft_signals_are_blocked_before_export(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store, status="draft")

    preflight = exporter.preflight(portfolio_id="cn_a_main", signal_date="2026-06-23")

    assert preflight["copy_ready"] is False
    assert preflight["validation"]["status"] == "blocked"
    assert "只有 approved 状态可以导出" in "；".join(preflight["validation"]["errors"])
    with pytest.raises(JoinQuantExportError, match="导出前校验未通过"):
        exporter.export_signals_json(portfolio_id="cn_a_main", signal_date="2026-06-23")


def test_unsupported_ticker_blocks_joinquant_export(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store, unsupported=True)

    preflight = exporter.preflight(portfolio_id="cn_a_main", signal_date="2026-06-23")

    assert preflight["validation"]["status"] == "blocked"
    assert "暂不支持该交易所代码映射" in "；".join(preflight["validation"]["errors"])


def test_export_strategy_code_is_complete_copyable_template(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    exported = exporter.export_strategy_code(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        strategy_id="cn_a_main_jq_test",
    )
    code = exported["python_code"]

    assert exported["status"] == "ok"
    assert exported["copy_ready"] is True
    assert exported["live_trading"] is False
    assert "# generated_by: Vibe-Trading Codex local JoinQuant adapter" in code
    assert "# strategy_id: cn_a_main_jq_test" in code
    assert "# risk_notice:" in code
    assert "def initialize(context):" in code
    assert "def before_trading_start(context):" in code
    assert "def handle_data(context, data):" in code
    assert "def map_a_share_ticker(ticker):" in code
    assert "def _risk_gate(context):" in code
    assert "def _can_trade(security, data):" in code
    assert "SIGNAL_JSON" in code
    assert "600519.XSHG" in code
    assert "order_target_percent" in code


def test_export_copy_package_contains_strategy_json_csv_and_readme(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    package = exporter.export_copy_package(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        strategy_id="cn_a_main_jq_test",
    )
    filenames = {item["filename"] for item in package["files"]}
    manifest_names = {item["filename"] for item in package["manifest"]["files"]}

    assert package["status"] == "ok"
    assert package["copy_ready"] is True
    assert package["manual_confirmation_required"] is True
    assert package["live_trading"] is False
    assert filenames == {"strategy.py", "signals.json", "signals.csv", "README.md"}
    assert manifest_names == filenames
    assert package["manifest"]["target_count"] == 3
    assert package["manifest"]["manual_confirmation_required"] is True
    assert package["clipboard_text"] == next(
        item["content"] for item in package["files"] if item["filename"] == "strategy.py"
    )
    assert "不会自动登录聚宽" in next(
        item["content"] for item in package["files"] if item["filename"] == "README.md"
    )


def test_strategy_code_export_blocks_draft_signals(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store, status="draft")

    with pytest.raises(JoinQuantExportError, match="导出前校验未通过"):
        exporter.export_strategy_code(portfolio_id="cn_a_main", signal_date="2026-06-23")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_joinquant_export_api_round_trip(client: TestClient) -> None:
    store = AShareDataStore()
    _seed_signals(store)

    preflight = client.post(
        "/api/joinquant/export/preflight",
        json={"portfolio_id": "cn_a_main", "signal_date": "2026-06-23"},
    )
    assert preflight.status_code == 200
    assert preflight.json()["copy_ready"] is True

    json_export = client.post(
        "/api/joinquant/export/signals-json",
        json={"portfolio_id": "cn_a_main", "signal_date": "2026-06-23"},
    )
    assert json_export.status_code == 200
    assert json_export.json()["payload"]["targets"][0]["ticker"].endswith((".XSHG", ".XSHE"))

    csv_export = client.post(
        "/api/joinquant/export/signals-csv",
        json={"portfolio_id": "cn_a_main", "signal_date": "2026-06-23"},
    )
    assert csv_export.status_code == 200
    assert csv_export.json()["row_count"] == 3

    strategy_code = client.post(
        "/api/joinquant/export/strategy-code",
        json={
            "portfolio_id": "cn_a_main",
            "signal_date": "2026-06-23",
            "strategy_id": "cn_a_main_jq_test",
        },
    )
    assert strategy_code.status_code == 200
    assert "def initialize(context):" in strategy_code.json()["python_code"]

    copy_package = client.post(
        "/api/joinquant/export/copy-package",
        json={
            "portfolio_id": "cn_a_main",
            "signal_date": "2026-06-23",
            "strategy_id": "cn_a_main_jq_test",
        },
    )
    assert copy_package.status_code == 200
    assert copy_package.json()["manifest"]["target_count"] == 3
    assert copy_package.json()["manifest"]["live_trading"] is False
