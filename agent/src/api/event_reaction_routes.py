"""Event reaction study routes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.event_reactions.service import EventReactionError, EventReactionService

AuthDep = Callable[..., Awaitable[Any] | Any]


class EventReactionCalculateRequest(BaseModel):
    event_id: str | None = Field(default=None, max_length=80)
    cluster_id: str | None = Field(default=None, max_length=80)
    windows: list[str] | None = Field(default=None, max_length=4)
    target_types: list[str] | None = Field(default=None, max_length=2)
    limit: int = Field(default=100, ge=1, le=500)
    replace: bool = True


def _service() -> EventReactionService:
    return EventReactionService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_event_reaction_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: EventReactionError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_event_reaction_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount event reaction calculation and query endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/event-reactions/calculate", dependencies=[Depends(auth)])
    def calculate_event_reactions(payload: EventReactionCalculateRequest) -> dict[str, Any]:
        try:
            return _service().calculate_reactions(
                event_id=payload.event_id,
                cluster_id=payload.cluster_id,
                windows=payload.windows,
                target_types=payload.target_types,
                limit=payload.limit,
                replace=payload.replace,
            )
        except EventReactionError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/event-reactions", dependencies=[Depends(auth)])
    def list_event_reactions(
        event_id: str | None = Query(None, max_length=80),
        cluster_id: str | None = Query(None, max_length=80),
        target_type: str | None = Query(None, max_length=20),
        target_id: str | None = Query(None, max_length=80),
        window: str | None = Query(None, max_length=4),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            rows = _service().list_reactions(
                event_id=event_id,
                cluster_id=cluster_id,
                target_type=target_type,
                target_id=target_id,
                window=window,
                limit=limit,
            )
        except EventReactionError as exc:
            raise _http_error(exc) from exc
        return {"status": "ok", "reactions": rows, "reaction_count": len(rows)}

    @app.get("/api/event-reactions/summary", dependencies=[Depends(auth)])
    def summarize_event_reactions(
        event_subtype: str | None = Query(None, max_length=80),
        target_type: str | None = Query(None, max_length=20),
        target_id: str | None = Query(None, max_length=80),
        window: str = Query("T+5", max_length=4),
    ) -> dict[str, Any]:
        try:
            return _service().summary(
                event_subtype=event_subtype,
                target_type=target_type,
                target_id=target_id,
                window=window,
            )
        except EventReactionError as exc:
            raise _http_error(exc) from exc
