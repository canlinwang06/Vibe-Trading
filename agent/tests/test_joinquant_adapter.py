"""PR-15 tests for JoinQuant mapping and signal export preflight."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.store import AShareDataStore
from src.joinquant_adapter.mapper.code_mapper import JoinQuantMappingError, map_ticker, unmap_ticker
from src.joinquant_adapter.service import JoinQuantExportError, JoinQuantExportService
from src.joinquant_orchestration.service import JoinQuantTaskService

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


def _seed_signal_batch(
    store: AShareDataStore,
    *,
    signal_date: str,
    valid_for: str,
    suffix: str,
    status: str = "approved",
) -> None:
    store.initialize()
    tickers = [
        ("600519.SH", "贵州茅台", 0.08, "buy", "白酒消费"),
        ("300750.SZ", "宁德时代", 0.07, "increase", "新能源"),
        ("000001.SH", "上证指数", 0.04, "hold", "宽基观察"),
    ]
    with store.connect() as conn:
        for idx, (ticker, ticker_name, target_weight, action, theme) in enumerate(tickers):
            conn.execute(
                """
                INSERT INTO execution_signals (
                  signal_id, signal_date, valid_for, portfolio_id, ticker,
                  ticker_name, target_weight, current_weight, action,
                  strategy_sources, theme, reason, risk, status,
                  created_at, approved_at
                )
                VALUES (?, ?, ?, 'cn_a_main',
                        ?, ?, ?, 0.0, ?, '["ai_sector_momentum_v1"]',
                        ?, 'PR-20 模拟盘准备度测试', '模拟信号，非实盘指令', ?, now(), now())
                """,
                [
                    f"sig_pr20_{suffix}_{idx}",
                    signal_date,
                    valid_for,
                    ticker,
                    ticker_name,
                    target_weight,
                    action,
                    theme,
                    status,
                ],
            )


def _seed_backtest_runs(store: AShareDataStore, *, max_drawdown: float = -0.06) -> None:
    store.initialize()
    with store.connect() as conn:
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
              'bt_pr20_ai_sector', 'ai_sector_momentum_v1', 'CN_A',
              DATE '2026-01-01', DATE '2026-06-20', 'cn_a_core',
              '000300.SH', 0.12, 0.24, ?, 1.35,
              1.1, 2.0, 0.56, 1.4, 0.32,
              42, 5.0, 0.04, 0.8, 'completed', '', now()
            )
            """,
            [max_drawdown],
        )


def test_joinquant_ticker_mapping_examples() -> None:
    assert map_ticker("600519.SH") == "600519.XSHG"
    assert map_ticker("300750.SZ") == "300750.XSHE"
    assert map_ticker("000001.SH") == "000001.XSHG"
    assert map_ticker("600519.XSHG") == "600519.XSHG"
    assert unmap_ticker("600519.XSHG") == "600519.SH"
    assert unmap_ticker("300750.XSHE") == "300750.SZ"
    assert unmap_ticker("000001.SH") == "000001.SH"

    with pytest.raises(JoinQuantMappingError, match="暂不支持"):
        map_ticker("830000.BJ")
    with pytest.raises(JoinQuantMappingError, match="暂不支持"):
        unmap_ticker("830000.XBSE")


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


def test_import_execution_reports_maps_joinquant_tickers_and_summarizes(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    imported = exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
        reports=[
            {
                "ticker": "600519.XSHG",
                "order_status": "filled",
                "executed_weight": 0.08,
                "fill_price": 1688.5,
                "fill_amount": 8000,
            },
            {
                "ticker": "300750.XSHE",
                "order_status": "rejected",
                "executed_weight": 0,
                "error_message": "涨停无法买入",
            },
            {
                "ticker": "000001.XSHG",
                "order_status": "held",
                "executed_weight": 0.04,
            },
        ],
    )
    reports = exporter.list_execution_reports(portfolio_id="cn_a_main", signal_date="2026-06-23")
    summary = exporter.execution_report_summary(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
    )

    assert imported["status"] == "needs_review"
    assert imported["imported_count"] == 3
    assert {row["ticker"] for row in reports} == {"600519.SH", "300750.SZ", "000001.SH"}
    assert reports[0]["raw_report"]
    assert summary["failed_count"] == 1
    assert summary["matched_signal_count"] == 3
    assert summary["missing_report_count"] == 0
    assert summary["max_abs_weight_diff"] == pytest.approx(0.07)
    assert summary["action_required"] is True
    assert summary["research_only"] is True
    assert summary["live_trading"] is False

    with store.connect(read_only=True) as conn:
        signal_rows = conn.execute(
            """
            SELECT ticker, status
            FROM execution_signals
            WHERE portfolio_id = 'cn_a_main' AND signal_date = DATE '2026-06-23'
            """
        ).fetchall()
    signals = {row[0]: row[1] for row in signal_rows}
    assert signals["600519.SH"] == "executed"
    assert signals["000001.SH"] == "executed"
    assert signals["300750.SZ"] == "approved"


def test_import_execution_reports_can_write_back_to_joinquant_task(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)
    task_service = JoinQuantTaskService(store=store)
    task = task_service.create_task(
        source_strategy_id="ai_sector_momentum_v1",
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
    )

    imported = exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
        jq_task_id=task["task_id"],
        reports=[
            {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
            {"ticker": "300750.XSHE", "order_status": "held", "executed_weight": 0.07},
            {"ticker": "000001.XSHG", "order_status": "held", "executed_weight": 0.04},
        ],
    )
    updated_task = task_service.get_task(task["task_id"])

    assert imported["jq_task_id"] == task["task_id"]
    assert updated_task["status"] == "completed"
    assert updated_task["result_summary"]["source"] == "joinquant_execution_report_import"
    assert updated_task["result_summary"]["summary"]["report_count"] == 3
    assert updated_task["evidence"][0]["type"] == "joinquant_execution_reports"


def test_import_execution_reports_can_replace_existing_trade_date(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
        reports=[
            {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
            {"ticker": "300750.XSHE", "order_status": "filled", "executed_weight": 0.07},
        ],
    )
    replaced = exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
        replace=True,
        reports=[
            {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
        ],
    )
    reports = exporter.list_execution_reports(portfolio_id="cn_a_main", signal_date="2026-06-23")

    assert replaced["replace"] is True
    assert len(reports) == 1
    assert reports[0]["ticker"] == "600519.SH"


def test_import_execution_reports_rejects_unmapped_ticker(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    with pytest.raises(JoinQuantExportError, match="暂不支持"):
        exporter.import_execution_reports(
            portfolio_id="cn_a_main",
            signal_date="2026-06-23",
            trade_date="2026-06-24",
            reports=[{"ticker": "830000.XBSE", "order_status": "filled", "executed_weight": 0.01}],
        )


def test_import_execution_reports_rejects_mixed_batches(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signals(store)

    with pytest.raises(JoinQuantExportError, match="同一 portfolio_id、signal_date 和 trade_date"):
        exporter.import_execution_reports(
            portfolio_id="cn_a_main",
            signal_date="2026-06-23",
            trade_date="2026-06-24",
            reports=[
                {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
                {
                    "ticker": "300750.XSHE",
                    "signal_date": "2026-06-23",
                    "trade_date": "2026-06-25",
                    "order_status": "filled",
                    "executed_weight": 0.07,
                },
            ],
        )


def test_simulation_readiness_report_ready_for_clean_simulation(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signal_batch(store, signal_date="2026-06-23", valid_for="2026-06-24", suffix="clean")
    _seed_backtest_runs(store, max_drawdown=-0.06)
    exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
        reports=[
            {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
            {"ticker": "300750.XSHE", "order_status": "filled", "executed_weight": 0.07},
            {"ticker": "000001.XSHG", "order_status": "held", "executed_weight": 0.04},
        ],
    )

    report = exporter.simulation_readiness_report(
        portfolio_id="cn_a_main",
        lookback_days=10,
        min_batches=1,
    )

    assert report["status"] == "ready"
    assert report["recommendation"] == "continue_simulation"
    assert report["observed_batch_count"] == 1
    assert report["totals"]["failed_count"] == 0
    assert report["backtest_risk"]["status"] == "ok"
    assert report["live_trading"] is False


def test_simulation_readiness_report_requires_observation_window(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signal_batch(store, signal_date="2026-06-23", valid_for="2026-06-24", suffix="short")
    _seed_backtest_runs(store, max_drawdown=-0.04)
    exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
        reports=[
            {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
            {"ticker": "300750.XSHE", "order_status": "filled", "executed_weight": 0.07},
            {"ticker": "000001.XSHG", "order_status": "held", "executed_weight": 0.04},
        ],
    )

    report = exporter.simulation_readiness_report(
        portfolio_id="cn_a_main",
        lookback_days=10,
        min_batches=3,
    )

    assert report["status"] == "needs_more_data"
    assert report["recommendation"] == "extend_observation"
    assert any(item["name"] == "observation_window" and item["status"] == "warning" for item in report["checks"])
    assert "继续积累样本" in "；".join(report["findings"])


def test_simulation_readiness_report_flags_execution_and_backtest_risk(
    exporter: JoinQuantExportService,
    store: AShareDataStore,
) -> None:
    _seed_signal_batch(store, signal_date="2026-06-23", valid_for="2026-06-24", suffix="risk_a")
    _seed_signal_batch(store, signal_date="2026-06-24", valid_for="2026-06-25", suffix="risk_b")
    _seed_backtest_runs(store, max_drawdown=-0.12)
    exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-23",
        trade_date="2026-06-24",
        reports=[
            {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
            {
                "ticker": "300750.XSHE",
                "order_status": "rejected",
                "executed_weight": 0,
                "error_message": "涨停无法买入",
            },
            {"ticker": "000001.XSHG", "order_status": "held", "executed_weight": 0.04},
        ],
    )
    exporter.import_execution_reports(
        portfolio_id="cn_a_main",
        signal_date="2026-06-24",
        trade_date="2026-06-25",
        reports=[
            {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
            {"ticker": "300750.XSHE", "order_status": "filled", "executed_weight": 0.02},
            {"ticker": "000001.XSHG", "order_status": "held", "executed_weight": 0.04},
        ],
    )

    report = exporter.simulation_readiness_report(
        portfolio_id="cn_a_main",
        lookback_days=10,
        min_batches=2,
        tolerance=0.01,
    )

    assert report["status"] == "needs_review"
    assert report["recommendation"] == "fix_before_live"
    assert report["totals"]["failed_count"] == 1
    assert report["totals"]["deviation_count"] >= 1
    assert report["totals"]["limit_or_suspend_issue_count"] == 1
    assert report["backtest_risk"]["status"] == "needs_review"
    assert any(item["name"] == "backtest_drawdown" and item["status"] == "fail" for item in report["checks"])
    assert "需要定位聚宽侧原因" in "；".join(report["findings"])


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_joinquant_export_api_round_trip(client: TestClient) -> None:
    store = AShareDataStore()
    _seed_signals(store)
    _seed_backtest_runs(store, max_drawdown=-0.06)

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

    report_import = client.post(
        "/api/joinquant/execution-reports/import",
        json={
            "portfolio_id": "cn_a_main",
            "signal_date": "2026-06-23",
            "trade_date": "2026-06-24",
            "reports": [
                {"ticker": "600519.XSHG", "order_status": "filled", "executed_weight": 0.08},
                {"ticker": "300750.XSHE", "order_status": "filled", "executed_weight": 0.07},
                {"ticker": "000001.XSHG", "order_status": "held", "executed_weight": 0.04},
            ],
        },
    )
    assert report_import.status_code == 200
    assert report_import.json()["summary"]["status"] == "ok"
    assert report_import.json()["live_trading"] is False

    report_list = client.get(
        "/api/joinquant/execution-reports",
        params={"portfolio_id": "cn_a_main", "signal_date": "2026-06-23"},
    )
    assert report_list.status_code == 200
    assert report_list.json()["count"] == 3

    report_summary = client.get(
        "/api/joinquant/execution-reports/summary",
        params={
            "portfolio_id": "cn_a_main",
            "signal_date": "2026-06-23",
            "trade_date": "2026-06-24",
        },
    )
    assert report_summary.status_code == 200
    assert report_summary.json()["action_required"] is False

    readiness = client.get(
        "/api/joinquant/simulation-readiness",
        params={"portfolio_id": "cn_a_main", "lookback_days": 10, "min_batches": 1},
    )
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    assert readiness.json()["observed_batch_count"] == 1
    assert readiness.json()["live_trading"] is False
