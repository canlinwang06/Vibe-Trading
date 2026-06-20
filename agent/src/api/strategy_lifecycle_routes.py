"""Strategy lifecycle dashboard routes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query

from src.strategy_lifecycle.service import StrategyLifecycleError, StrategyLifecycleService

AuthDep = Callable[..., Awaitable[Any] | Any]


def _service() -> StrategyLifecycleService:
    return StrategyLifecycleService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_strategy_lifecycle_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: StrategyLifecycleError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_strategy_lifecycle_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount lifecycle overview endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.get("/api/strategy-lifecycle/overview", dependencies=[Depends(auth)])
    def overview(
        refresh: bool = Query(True),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        try:
            return _service().overview(refresh=refresh, limit=limit)
        except StrategyLifecycleError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/strategy-lifecycle/refresh", dependencies=[Depends(auth)])
    def refresh() -> dict[str, Any]:
        try:
            rows = _service().refresh_lifecycle()
        except StrategyLifecycleError as exc:
            raise _http_error(exc) from exc
        return {"status": "ok", "strategy_count": len(rows), "strategies": rows, "research_only": True, "live_trading": False}
