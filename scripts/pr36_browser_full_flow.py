#!/usr/bin/env python3
"""PR-36 browser QA for the local A-share AI industry-chain flow."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent"
sys.path.insert(0, str(AGENT_ROOT))

from src.ashare_data.store import AShareDataStore  # noqa: E402

BACKEND_URL = os.environ.get("VIBE_PR36_BACKEND_URL", "http://127.0.0.1:18999").rstrip("/")
FRONTEND_URL = os.environ.get("VIBE_PR36_FRONTEND_URL", "http://127.0.0.1:15899").rstrip("/")
WORKFLOW_DATE = os.environ.get("VIBE_PR36_WORKFLOW_DATE", "2026-06-24")
BACKTEST_START = "2026-05-20"
BACKTEST_END = "2026-06-24"

AI_TASK_TITLE = "AI 产业链事件跟踪"
AI_TASK_CONTENT = (
    "国家政策、云厂商和产业资本继续支持 AI 人工智能算力、数据中心、光模块、"
    "服务器、液冷和大模型基础设施建设。A 股 AI 算力产业链景气度提升，"
    "光模块、服务器、工业互联网和数据中心板块受益，但仍需通过本地回测、"
    "风控组合和聚宽模拟复制包验证，不能直接用于实盘。"
)


def _business_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def seed_local_ai_fixture() -> None:
    """Seed deterministic local market data for the PR-36 isolated QA store."""

    store = AShareDataStore()
    store.initialize()
    tickers = {
        "300308.SZ": "中际旭创",
        "000977.SZ": "浪潮信息",
        "601138.SH": "工业富联",
        "300024.SZ": "机器人",
        "002747.SZ": "埃斯顿",
        "688981.SH": "中芯国际",
        "002371.SZ": "北方华创",
        "300750.SZ": "宁德时代",
        "002594.SZ": "比亚迪",
        "300413.SZ": "芒果超媒",
        "600519.SH": "贵州茅台",
        "000300.SH": "沪深300",
    }
    sectors = {
        "theme_ai_compute": "AI算力",
        "theme_robotics": "人形机器人",
        "theme_semiconductor": "半导体",
        "theme_new_energy": "新能源",
        "theme_media_consumption": "文娱消费",
    }
    days = _business_days(date(2026, 5, 15), date(2026, 6, 24))
    created_at = datetime(2026, 6, 20, 9, 0, 0)

    with store.connect() as conn:
        for ticker, name in tickers.items():
          exchange = ticker.split(".")[1] if "." in ticker else ""
          conn.execute("DELETE FROM assets WHERE ticker = ?", [ticker])
          conn.execute(
              """
              INSERT INTO assets (
                ticker, ticker_name, market, exchange, asset_type,
                listed_date, delisted_date, active, updated_at
              )
              VALUES (?, ?, 'CN_A', ?, 'stock', ?, NULL, true, ?)
              """,
              [ticker, name, exchange, date(2010, 1, 1), created_at],
          )

        for day_index, trade_date in enumerate(days):
            for ticker_index, (ticker, _name) in enumerate(tickers.items()):
                base = 100 + ticker_index * 8
                drift = 0.0025 if ticker != "000300.SH" else 0.001
                close = round(base * (1 + drift * day_index + ((day_index % 5) - 2) * 0.001), 3)
                conn.execute("DELETE FROM market_daily WHERE trade_date = ? AND ticker = ?", [trade_date, ticker])
                conn.execute(
                    """
                    INSERT INTO market_daily (
                      trade_date, ticker, open, high, low, close, volume, amount,
                      turnover, adj_factor, limit_status, suspended, source, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 'normal', false, 'pr36_fixture', ?)
                    """,
                    [
                        trade_date,
                        ticker,
                        round(close * 0.997, 3),
                        round(close * 1.012, 3),
                        round(close * 0.988, 3),
                        close,
                        1_000_000 + ticker_index * 10_000,
                        400_000_000 + ticker_index * 1_000_000,
                        0.025,
                        created_at,
                    ],
                )

            for sector_index, (sector_id, sector_name) in enumerate(sectors.items()):
                daily_return = (
                    0.006 + (day_index % 4) * 0.001
                    if sector_id == "theme_ai_compute"
                    else 0.002 + (day_index % 3) * 0.0005
                )
                close = round(1000 * (1 + daily_return * day_index / 3 + sector_index * 0.01), 3)
                conn.execute("DELETE FROM sector_daily WHERE trade_date = ? AND sector_id = ?", [trade_date, sector_id])
                conn.execute(
                    """
                    INSERT INTO sector_daily (
                      trade_date, sector_id, sector_name, open, high, low, close, "return",
                      amount, turnover, up_count, down_count, limit_up_count, member_count,
                      leading_ticker, source, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pr36_fixture', ?)
                    """,
                    [
                        trade_date,
                        sector_id,
                        sector_name,
                        round(close * 0.99, 3),
                        round(close * 1.01, 3),
                        round(close * 0.98, 3),
                        close,
                        daily_return,
                        8_000_000_000,
                        0.035,
                        8,
                        2,
                        1,
                        10,
                        "300308.SZ",
                        created_at,
                    ],
                )

    print(f"seeded deterministic A-share fixture: {len(days)} trade days, {len(tickers)} tickers")


def api_json(path: str, payload: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=body if method != "GET" else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def expect_text(page: Page, text: str, *, timeout: int = 30_000) -> None:
    expect(page.get_by_text(text, exact=False).first).to_be_visible(timeout=timeout)


def goto(page: Page, route: str, text: str) -> None:
    page.goto(f"{FRONTEND_URL}{route}", wait_until="networkidle")
    expect_text(page, text)


def field(page: Page, label: str, *, section_text: str | None = None):
    scope = page.locator("body")
    if section_text:
        scope = page.locator("section").filter(has_text=section_text).first
    return scope.locator("label").filter(has_text=label).locator("input, textarea, select").first


def click(page: Page, name: str, *, timeout: int = 30_000) -> None:
    page.get_by_role("button", name=name).click(timeout=timeout)


def run_browser_flow() -> None:
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        goto(page, "/", "A 股事件驱动策略驾驶舱")
        for route, marker in [
            ("/data-sources", "凭据管理"),
            ("/strategy-lab", "策略实验室"),
            ("/backtest-results", "回测结果"),
            ("/risk-portfolio", "风控组合"),
            ("/trade-plan", "交易计划"),
            ("/joinquant-export", "聚宽导出"),
        ]:
            goto(page, route, marker)

        goto(page, "/daily-workflow", "每日研究工作流")
        field(page, "工作日期").fill(WORKFLOW_DATE)
        field(page, "组合 ID").fill("cn_a_main")
        field(page, "发布时间").fill("2026-06-19T08:30:00+08:00")
        field(page, "标题").fill(AI_TASK_TITLE)
        field(page, "正文").fill(AI_TASK_CONTENT)
        field(page, "回测开始").fill(BACKTEST_START)
        field(page, "回测结束").fill(BACKTEST_END)
        field(page, "回测数量").fill("8")
        field(page, "排名数量").fill("8")
        click(page, "试运行")
        expect_text(page, "试运行计划已生成", timeout=60_000)
        click(page, "运行工作流")
        expect_text(page, "工作流已完成", timeout=120_000)
        expect_text(page, "已写入 8 个本地回测结果")
        expect_text(page, "已生成 3 条执行信号草案")
        expect_text(page, "已更新 4 条事件反应研究结果")

        approved = api_json(
            "/api/portfolio-risk/approve-plan",
            {
                "portfolio_id": "cn_a_main",
                "signal_date": WORKFLOW_DATE,
                "confirm_risk": True,
                "simulation_only": True,
            },
        )
        if approved.get("status") != "approved" or int(approved.get("approved_count") or 0) <= 0:
            raise AssertionError(f"simulation approval failed: {approved}")

        goto(page, "/strategy-lab", "策略实验室")
        click(page, "刷新回测")
        expect_text(page, "已加载 8 条回测结果")
        click(page, "刷新排名")
        expect_text(page, "已生成 8 条策略排名")

        goto(page, "/backtest-results", "回测结果")
        click(page, "刷新回测结果")
        expect_text(page, "已加载 8 条回测结果")
        click(page, "刷新策略排名")
        expect_text(page, "已加载 8 条策略排名")

        goto(page, "/risk-portfolio", "风控组合")
        click(page, "刷新策略分配")
        expect_text(page, "已加载 5 条策略分配")
        click(page, "生成交易计划草案")
        expect_text(page, "已生成 3 条草案目标持仓")

        goto(page, "/trade-plan", "交易计划")
        click(page, "刷新交易计划")
        expect_text(page, "已加载 3 条目标持仓")
        expect_text(page, "已模拟审批")

        goto(page, "/joinquant-export", "聚宽导出")
        field(page, "信号日期", section_text="导出参数").fill(WORKFLOW_DATE)
        field(page, "聚宽策略 ID", section_text="导出参数").fill("pr36_ai_chain_sim")
        click(page, "预检查")
        expect_text(page, "预检查通过", timeout=60_000)
        click(page, "生成复制包")
        expect_text(page, "复制包清单", timeout=60_000)
        expect_text(page, "下载完整复制包")
        expect_text(page, "strategy.py")
        expect_text(page, "signals.json")
        expect_text(page, "signals.csv")

        with page.expect_download() as download_info:
            click(page, "下载完整复制包")
        download = download_info.value
        if not download.suggested_filename.endswith("_copy_package.json"):
            raise AssertionError(f"unexpected package filename: {download.suggested_filename}")

        package = api_json(
            "/api/joinquant/export/copy-package",
            {
                "portfolio_id": "cn_a_main",
                "signal_date": WORKFLOW_DATE,
                "strategy_id": "pr36_ai_chain_sim",
                "require_approved": True,
            },
        )
        filenames = {item["filename"] for item in package.get("files", [])}
        required_files = {"strategy.py", "signals.json", "signals.csv", "README.md"}
        if package.get("status") != "ok" or not required_files.issubset(filenames):
            raise AssertionError(f"JoinQuant copy package incomplete: {package}")
        if package.get("manifest", {}).get("target_count", 0) <= 0:
            raise AssertionError("JoinQuant package target_count must be positive")

        if console_errors:
            raise AssertionError("browser console/page errors: " + " | ".join(console_errors[:5]))

        browser.close()

    print("PR-36 browser full-flow QA passed.")
    print(
        json.dumps(
            {
                "workflow_date": WORKFLOW_DATE,
                "task": AI_TASK_TITLE,
                "backtest_runs": 8,
                "approved_signals": approved.get("approved_count"),
                "joinquant_package_files": sorted(required_files),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main() -> int:
    seed_local_ai_fixture()
    run_browser_flow()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
