"""Codex-facing JoinQuant orchestration task routes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.joinquant_orchestration.service import JoinQuantTaskError, JoinQuantTaskService

AuthDep = Callable[..., Awaitable[Any] | Any]


class JoinQuantTaskCreateRequest(BaseModel):
    source_strategy_id: str | None = Field(default=None, max_length=120)
    source_idea_id: str | None = Field(default=None, max_length=120)
    portfolio_id: str = Field(default="cn_a_main", min_length=3, max_length=80)
    signal_date: str | None = Field(default=None, min_length=10, max_length=10)
    task_type: str = Field(default="backtest", max_length=40)
    created_by: str = Field(default="codex", max_length=40)


class JoinQuantTaskUpdateRequest(BaseModel):
    status: str | None = Field(default=None, max_length=40)
    result_summary: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] | None = None
    error_message: str | None = Field(default=None, max_length=1000)


def _service() -> JoinQuantTaskService:
    return JoinQuantTaskService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_joinquant_task_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: JoinQuantTaskError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_joinquant_task_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount task APIs used by Codex to coordinate JoinQuant work."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/joinquant/tasks", dependencies=[Depends(auth)])
    def create_task(payload: JoinQuantTaskCreateRequest) -> dict[str, Any]:
        try:
            task = _service().create_task(
                source_strategy_id=payload.source_strategy_id,
                source_idea_id=payload.source_idea_id,
                portfolio_id=payload.portfolio_id,
                signal_date=payload.signal_date,
                task_type=payload.task_type,
                created_by=payload.created_by,
            )
        except JoinQuantTaskError as exc:
            raise _http_error(exc) from exc
        return {"status": "ok", "task": task, "research_only": True, "live_trading": False}

    @app.get("/api/joinquant/tasks", dependencies=[Depends(auth)])
    def list_tasks(
        status: str | None = Query(None, max_length=40),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        try:
            tasks = _service().list_tasks(status=status, limit=limit)
        except JoinQuantTaskError as exc:
            raise _http_error(exc) from exc
        return {"status": "ok", "task_count": len(tasks), "tasks": tasks, "research_only": True, "live_trading": False}

    @app.get("/api/joinquant/tasks/{task_id}", dependencies=[Depends(auth)])
    def get_task(task_id: str) -> dict[str, Any]:
        try:
            return {"status": "ok", "task": _service().get_task(task_id)}
        except JoinQuantTaskError as exc:
            raise _http_error(exc, status_code=404) from exc

    @app.patch("/api/joinquant/tasks/{task_id}", dependencies=[Depends(auth)])
    def update_task(task_id: str, payload: JoinQuantTaskUpdateRequest) -> dict[str, Any]:
        try:
            task = _service().update_task(
                task_id,
                status=payload.status,
                result_summary=payload.result_summary,
                evidence=payload.evidence,
                error_message=payload.error_message,
            )
        except JoinQuantTaskError as exc:
            raise _http_error(exc) from exc
        return {"status": "ok", "task": task, "research_only": True, "live_trading": False}
