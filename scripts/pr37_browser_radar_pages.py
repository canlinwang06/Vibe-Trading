#!/usr/bin/env python3
"""PR-37 browser QA for event radar and sector radar pages."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

BACKEND_URL = os.environ.get("VIBE_PR37_BACKEND_URL", "http://127.0.0.1:19999").rstrip("/")
FRONTEND_URL = os.environ.get("VIBE_PR37_FRONTEND_URL", "http://127.0.0.1:15937").rstrip("/")
RADAR_DATE = os.environ.get("VIBE_PR37_RADAR_DATE", "2026-06-19")
SCORE_DATE = os.environ.get("VIBE_PR37_SCORE_DATE", "2026-06-24")

os.environ.setdefault("VIBE_PR36_BACKEND_URL", BACKEND_URL)
os.environ.setdefault("VIBE_PR36_FRONTEND_URL", FRONTEND_URL)

from pr36_browser_full_flow import seed_local_ai_fixture  # noqa: E402


AI_TASK_TITLE = "AI 产业链事件跟踪"
AI_TASK_CONTENT = (
    "国家政策、云厂商和产业资本继续支持 AI 人工智能算力、数据中心、光模块、"
    "服务器、液冷和大模型基础设施建设。A 股 AI 算力产业链景气度提升，"
    "光模块、服务器、工业互联网和数据中心板块受益，但仍需通过本地回测和模拟验证。"
)


def expect_text(page: Page, text: str, *, timeout: int = 30_000) -> None:
    expect(page.get_by_text(text, exact=False).first).to_be_visible(timeout=timeout)


def goto(page: Page, route: str, text: str) -> None:
    page.goto(f"{FRONTEND_URL}{route}", wait_until="domcontentloaded")
    expect_text(page, text)
    body_text = page.locator("body").inner_text()
    if "等待 PR" in body_text or "后续模块接入" in body_text:
        raise AssertionError(f"stale waiting copy is visible on {route}")


def field(page: Page, label: str):
    return page.locator("label").filter(has_text=label).locator("input, textarea, select").first


def click(page: Page, name: str, *, timeout: int = 30_000) -> None:
    button = page.get_by_role("button", name=name)
    expect(button).to_be_enabled(timeout=timeout)
    button.click(timeout=timeout)


def run_browser_flow() -> None:
    console_errors: list[str] = []
    http_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        def record_http_error(response) -> None:
            if response.status < 400:
                return
            try:
                body = response.text()[:400]
            except Exception as exc:  # pragma: no cover - diagnostic fallback
                body = f"<failed to read body: {exc}>"
            http_errors.append(f"{response.status} {response.url}: {body}")

        page.on("response", record_http_error)

        goto(page, "/", "A 股事件驱动策略驾驶舱")
        expect_text(page, "核心研究链路已接入本地事件抽取")

        goto(page, "/event-radar", "事件雷达")
        expect_text(page, "事件输入")
        try:
            expect_text(page, "国务院政策文件", timeout=60_000)
        except AssertionError:
            if http_errors:
                raise AssertionError("HTTP failures before event radar was ready: " + " | ".join(http_errors)) from None
            raise
        field(page, "信息源").fill("gov_policy_cn")
        field(page, "发布时间").fill(f"{RADAR_DATE}T08:30:00+08:00")
        field(page, "标题").fill(AI_TASK_TITLE)
        field(page, "正文").fill(AI_TASK_CONTENT)

        click(page, "导入本地文档")
        expect_text(page, "已导入 1 条文档", timeout=60_000)
        click(page, "抽取事件")
        expect_text(page, "已抽取 1 个事件", timeout=60_000)
        click(page, "映射板块股票")
        expect_text(page, "已映射 1 个事件", timeout=60_000)
        expect_text(page, "AI算力")
        expect_text(page, "中际旭创")

        goto(page, "/sector-radar", "板块雷达")
        expect_text(page, "中际旭创", timeout=60_000)
        field(page, "交易日期").fill(SCORE_DATE)
        field(page, "评分上限").fill("10")
        field(page, "事件映射相关度").fill("0.45")
        field(page, "最低热度").fill("0")
        click(page, "生成板块评分")
        expect_text(page, f"已在 {SCORE_DATE} 写入", timeout=60_000)
        expect_text(page, "板块评分明细")
        expect_text(page, "AI算力")
        expect_text(page, "中际旭创")

        if http_errors:
            raise AssertionError("browser HTTP errors: " + " | ".join(http_errors[:5]))
        if console_errors:
            raise AssertionError("browser console/page errors: " + " | ".join(console_errors[:5]))

        browser.close()

    print("PR-37 browser radar QA passed.")


def main() -> int:
    if os.environ.get("VIBE_PR37_SKIP_SCRIPT_SEED") != "1":
        seed_local_ai_fixture()
    run_browser_flow()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
