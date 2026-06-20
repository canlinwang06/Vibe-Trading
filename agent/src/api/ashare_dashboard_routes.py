"""Presentation dashboard routes for the Codex-commanded A-share workbench."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query

from src.ashare_dashboard.service import AShareDashboardError, AShareDashboardService

AuthDep = Callable[..., Awaitable[Any] | Any]


def _service() -> AShareDashboardService:
    return AShareDashboardService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_ashare_dashboard_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: AShareDashboardError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_ashare_dashboard_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount chart-first dashboard summaries."""
    auth = _resolve_auth(require_local_or_auth)

    @app.get("/api/ashare-dashboard/daily-intelligence", dependencies=[Depends(auth)])
    def daily_intelligence(
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
    ) -> dict[str, Any]:
        try:
            return _service().daily_intelligence(as_of_date=as_of_date)
        except AShareDashboardError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/ashare-dashboard/sector-stock-analysis", dependencies=[Depends(auth)])
    def sector_stock_analysis(
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        theme: str | None = Query(None, max_length=80),
    ) -> dict[str, Any]:
        try:
            return _service().sector_stock_analysis(as_of_date=as_of_date, theme=theme)
        except AShareDashboardError as exc:
            raise _http_error(exc) from exc
