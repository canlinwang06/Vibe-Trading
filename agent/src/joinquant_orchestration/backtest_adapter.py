"""JoinQuant backtest automation artifacts for Codex orchestration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def build_joinquant_research_script(
    *,
    task: dict[str, Any],
    start_date: date,
    end_date: date,
    initial_cash: float,
) -> str:
    """Build a script intended for JoinQuant's research environment."""
    package = task.get("task_package") or {}
    joinquant_package = package.get("joinquant_package") or {}
    files = joinquant_package.get("files") or []
    strategy_code = _file_content(files, "strategy.py")
    strategy_id = task.get("source_strategy_id") or joinquant_package.get("strategy_id") or task.get("source_idea_id") or task["task_id"]
    if not strategy_code:
        strategy_code = (
            "# Vibe-Trading did not find a strategy.py copy package for this task.\n"
            "# Use the fallback copy-package flow, then paste the generated code here.\n"
        )

    return "\n".join(
        [
            "# generated_by: Vibe-Trading Codex JoinQuant backtest adapter",
            "# research_only: true",
            "# live_trading: false",
            "# safety: does not store JoinQuant credentials and does not submit live orders",
            f"TASK_ID = {task['task_id']!r}",
            f"STRATEGY_ID = {str(strategy_id)!r}",
            f"PORTFOLIO_ID = {task['portfolio_id']!r}",
            f"SIGNAL_DATE = {task['signal_date']!r}",
            f"START_DATE = {start_date.isoformat()!r}",
            f"END_DATE = {end_date.isoformat()!r}",
            f"INITIAL_CASH = {float(initial_cash)!r}",
            f"STRATEGY_CODE = {strategy_code!r}",
            "",
            "def run_vibe_backtest():",
            "    if 'create_backtest' not in globals():",
            "        raise RuntimeError('当前聚宽环境未暴露 create_backtest，请改用浏览器复制包兜底流程。')",
            "    kwargs = dict(",
            "        name=f'{STRATEGY_ID}_{SIGNAL_DATE}',",
            "        start_date=START_DATE,",
            "        end_date=END_DATE,",
            "        frequency='daily',",
            "        initial_cash=INITIAL_CASH,",
            "    )",
            "    try:",
            "        backtest = create_backtest(code=STRATEGY_CODE, **kwargs)",
            "    except TypeError:",
            "        backtest = create_backtest(strategy_code=STRATEGY_CODE, **kwargs)",
            "    backtest_id = backtest.get('id') if isinstance(backtest, dict) else backtest",
            "    result = None",
            "    if 'get_backtest' in globals():",
            "        result = get_backtest(backtest_id)",
            "    print({'task_id': TASK_ID, 'backtest_id': backtest_id, 'result': result})",
            "    return backtest_id",
            "",
            "if __name__ == '__main__':",
            "    run_vibe_backtest()",
            "",
        ]
    )


def build_browser_automation_steps(*, task: dict[str, Any]) -> list[dict[str, Any]]:
    """Return human-authorized browser steps that Codex can follow."""
    return [
        {
            "step": "open_joinquant",
            "title": "打开聚宽研究环境或策略编辑器",
            "instruction": "使用用户已经登录的浏览器会话打开聚宽；不要读取、保存或询问聚宽密码。",
        },
        {
            "step": "paste_strategy",
            "title": "粘贴策略代码",
            "instruction": "从任务包读取 strategy.py，粘贴到聚宽回测/研究环境草稿中。",
        },
        {
            "step": "run_backtest",
            "title": "启动回测",
            "instruction": "仅启动回测或模拟验证，不切换到实盘，不提交实盘交易。",
        },
        {
            "step": "capture_result",
            "title": "读取结果并留证",
            "instruction": "读取收益、回撤、Sharpe、胜率、交易次数、基准对比，并保存截图或页面摘要证据。",
        },
        {
            "step": "write_back",
            "title": "写回本地系统",
            "instruction": f"调用本地结果写回 API，关联 task_id={task['task_id']}。",
        },
    ]


def default_backtest_window(signal_date: str | date | datetime) -> tuple[date, date]:
    end = _parse_date(signal_date)
    return end - timedelta(days=180), end


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _file_content(files: list[dict[str, Any]], filename: str) -> str:
    for item in files:
        if item.get("filename") == filename:
            return str(item.get("content") or "")
    return ""
