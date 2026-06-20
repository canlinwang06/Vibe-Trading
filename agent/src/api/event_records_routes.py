"""Unified event record routes for the A-share research workbench."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query

from src.event_records.service import EventRecordError, EventRecordService, IMPACT_WINDOWS

AuthDep = Callable[..., Awaitable[Any] | Any]


def _service() -> EventRecordService:
    return EventRecordService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_event_records_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: EventRecordError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_event_records_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount objective event record list endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.get("/api/event-records", dependencies=[Depends(auth)])
    def list_event_records(
        limit: int = Query(50, ge=1, le=200),
        event_type: str | None = Query(None, max_length=80),
        event_subtype: str | None = Query(None, max_length=80),
        from_date: str | None = Query(None, min_length=10, max_length=10),
        to_date: str | None = Query(None, min_length=10, max_length=10),
        min_relevance: float = Query(0.0, ge=0, le=1),
    ) -> dict[str, Any]:
        try:
            records = _service().list_records(
                limit=limit,
                event_type=event_type,
                event_subtype=event_subtype,
                from_date=from_date,
                to_date=to_date,
                min_relevance=min_relevance,
            )
        except EventRecordError as exc:
            raise _http_error(exc) from exc
        return {
            "status": "ok",
            "records": records,
            "record_count": len(records),
            "impact_windows": list(IMPACT_WINDOWS),
            "research_only": True,
            "live_trading": False,
        }
