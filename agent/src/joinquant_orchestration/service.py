"""Codex-facing JoinQuant task orchestration service."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore
from src.joinquant_adapter.service import JoinQuantExportError, JoinQuantExportService
from src.joinquant_orchestration.backtest_adapter import (
    build_browser_automation_steps,
    build_joinquant_research_script,
    default_backtest_window,
)


class JoinQuantTaskError(RuntimeError):
    """Raised when a JoinQuant orchestration task cannot be processed."""


TASK_STATUSES = {"draft", "waiting_confirm", "running", "completed", "failed", "cancelled"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None, field_name: str) -> date:
    if value is None:
        return _utc_now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise JoinQuantTaskError(f"{field_name} 必须是 YYYY-MM-DD 格式") from exc


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _task_id(*, source_strategy_id: str | None, source_idea_id: str | None, portfolio_id: str, signal_date: date, task_type: str) -> str:
    material = "|".join([source_strategy_id or "", source_idea_id or "", portfolio_id, signal_date.isoformat(), task_type])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"jqtask_{digest}"


class JoinQuantTaskService:
    """Persist JoinQuant backtest/simulation tasks that Codex can orchestrate."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def create_task(
        self,
        *,
        source_strategy_id: str | None = None,
        source_idea_id: str | None = None,
        portfolio_id: str = "cn_a_main",
        signal_date: str | date | datetime | None = None,
        task_type: str = "backtest",
        created_by: str = "codex",
    ) -> dict[str, Any]:
        self.store.initialize()
        as_of = _parse_date(signal_date, "signal_date")
        clean_strategy_id = source_strategy_id.strip() if source_strategy_id else None
        clean_idea_id = source_idea_id.strip() if source_idea_id else None
        if not clean_strategy_id and not clean_idea_id:
            raise JoinQuantTaskError("请提供 source_strategy_id 或 source_idea_id")
        if task_type not in {"backtest", "paper_simulation"}:
            raise JoinQuantTaskError("task_type 只支持 backtest 或 paper_simulation")

        task_package = self._build_task_package(
            source_strategy_id=clean_strategy_id,
            source_idea_id=clean_idea_id,
            portfolio_id=portfolio_id,
            signal_date=as_of,
            task_type=task_type,
        )
        now = _utc_now()
        task_id = _task_id(
            source_strategy_id=clean_strategy_id,
            source_idea_id=clean_idea_id,
            portfolio_id=portfolio_id,
            signal_date=as_of,
            task_type=task_type,
        )
        with self.store.connect() as conn:
            conn.execute("DELETE FROM jq_orchestration_tasks WHERE task_id = ?", [task_id])
            conn.execute(
                """
                INSERT INTO jq_orchestration_tasks (
                  task_id, source_strategy_id, source_idea_id, portfolio_id,
                  signal_date, task_type, status, task_package_json,
                  result_summary_json, evidence_json, error_message,
                  fallback_instruction, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    task_id,
                    clean_strategy_id,
                    clean_idea_id,
                    portfolio_id,
                    as_of,
                    task_type,
                    "waiting_confirm",
                    _json(task_package),
                    _json({}),
                    _json([]),
                    None,
                    "若聚宽自动化失败，请下载复制包或手动复制 strategy.py 到聚宽研究环境运行。",
                    created_by,
                    now,
                    now,
                ],
            )
        return self.get_task(task_id)

    def list_tasks(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        self.store.initialize()
        filters: list[str] = []
        params: list[Any] = []
        if status:
            filters.append("status = ?")
            params.append(_normalize_status(status))
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(min(max(int(limit), 1), 200))
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT task_id, source_strategy_id, source_idea_id, portfolio_id,
                       signal_date, task_type, status, task_package_json,
                       result_summary_json, evidence_json, error_message,
                       fallback_instruction, created_by, created_at, updated_at
                FROM jq_orchestration_tasks
                {where}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_task(row) for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any]:
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT task_id, source_strategy_id, source_idea_id, portfolio_id,
                       signal_date, task_type, status, task_package_json,
                       result_summary_json, evidence_json, error_message,
                       fallback_instruction, created_by, created_at, updated_at
                FROM jq_orchestration_tasks
                WHERE task_id = ?
                """,
                [task_id.strip()],
            ).fetchone()
        if row is None:
            raise JoinQuantTaskError(f"未找到聚宽任务: {task_id}")
        return _row_to_task(row)

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        result_summary: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_task(task_id)
        next_status = _normalize_status(status) if status else current["status"]
        next_summary = result_summary if result_summary is not None else current["result_summary"]
        next_evidence = evidence if evidence is not None else current["evidence"]
        now = _utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE jq_orchestration_tasks
                SET status = ?, result_summary_json = ?, evidence_json = ?,
                    error_message = ?, updated_at = ?
                WHERE task_id = ?
                """,
                [
                    next_status,
                    _json(next_summary),
                    _json(next_evidence),
                    error_message,
                    now,
                    task_id.strip(),
                ],
            )
        return self.get_task(task_id)

    def automation_plan(
        self,
        task_id: str,
        *,
        start_date: str | date | datetime | None = None,
        end_date: str | date | datetime | None = None,
        initial_cash: float = 1_000_000,
    ) -> dict[str, Any]:
        """Return Codex-readable artifacts for a human-authorized JoinQuant backtest."""
        task = self.get_task(task_id)
        if task["task_type"] != "backtest":
            raise JoinQuantTaskError("当前自动回测适配器仅支持 backtest 任务。")
        default_start, default_end = default_backtest_window(task["signal_date"])
        resolved_start = _parse_date(start_date, "start_date") if start_date else default_start
        resolved_end = _parse_date(end_date, "end_date") if end_date else default_end
        if resolved_start > resolved_end:
            raise JoinQuantTaskError("start_date 不能晚于 end_date。")
        if initial_cash <= 0:
            raise JoinQuantTaskError("initial_cash 必须大于 0。")
        script = build_joinquant_research_script(
            task=task,
            start_date=resolved_start,
            end_date=resolved_end,
            initial_cash=initial_cash,
        )
        return {
            "status": "ok",
            "task_id": task["task_id"],
            "task": task,
            "automation_mode": "codex_human_authorized",
            "backtest_window": {
                "start_date": resolved_start.isoformat(),
                "end_date": resolved_end.isoformat(),
                "initial_cash": float(initial_cash),
            },
            "joinquant_research_script": script,
            "browser_steps": build_browser_automation_steps(task=task),
            "fallback_instruction": task["fallback_instruction"],
            "safety_guardrails": {
                "stores_joinquant_password": False,
                "bypasses_captcha": False,
                "submits_live_orders": False,
                "requires_user_logged_in_browser": True,
                "requires_human_confirmation": True,
            },
            "research_only": True,
            "live_trading": False,
        }

    def _build_task_package(
        self,
        *,
        source_strategy_id: str | None,
        source_idea_id: str | None,
        portfolio_id: str,
        signal_date: date,
        task_type: str,
    ) -> dict[str, Any]:
        package: dict[str, Any]
        try:
            package = JoinQuantExportService(store=self.store).export_copy_package(
                portfolio_id=portfolio_id,
                signal_date=signal_date.isoformat(),
                strategy_id=source_strategy_id,
                require_approved=False,
            )
            package_status = "copy_package_ready"
        except JoinQuantExportError as exc:
            package = {
                "status": "manual_prepare_required",
                "error": str(exc),
                "files": [],
                "manifest": {
                    "strategy_id": source_strategy_id or source_idea_id,
                    "portfolio_id": portfolio_id,
                    "signal_date": signal_date.isoformat(),
                    "manual_confirmation_required": True,
                    "live_trading": False,
                },
            }
            package_status = "needs_signal_package"

        return {
            "package_status": package_status,
            "task_type": task_type,
            "source_strategy_id": source_strategy_id,
            "source_idea_id": source_idea_id,
            "portfolio_id": portfolio_id,
            "signal_date": signal_date.isoformat(),
            "joinquant_package": package,
            "codex_steps": [
                "确认用户已在浏览器登录聚宽。",
                "打开聚宽研究环境，创建或更新回测脚本。",
                "运行回测并等待结果完成。",
                "截图留证，读取指标后写回本地任务。",
            ],
            "safety_guardrails": {
                "stores_joinquant_password": False,
                "bypasses_captcha": False,
                "submits_live_orders": False,
                "requires_human_confirmation": True,
            },
            "research_only": True,
            "live_trading": False,
        }


def _normalize_status(status: str) -> str:
    clean = status.strip()
    if clean not in TASK_STATUSES:
        raise JoinQuantTaskError(f"任务状态不支持: {status}")
    return clean


def _row_to_task(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "task_id": row[0],
        "source_strategy_id": row[1],
        "source_idea_id": row[2],
        "portfolio_id": row[3],
        "signal_date": _iso(row[4]),
        "task_type": row[5],
        "status": row[6],
        "task_package": _loads(row[7], {}),
        "result_summary": _loads(row[8], {}),
        "evidence": _loads(row[9], []),
        "error_message": row[10],
        "fallback_instruction": row[11],
        "created_by": row[12],
        "created_at": _iso(row[13]),
        "updated_at": _iso(row[14]),
        "research_only": True,
        "live_trading": False,
    }
