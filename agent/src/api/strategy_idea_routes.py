"""Strategy idea generation routes for the A-share research workflow."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.strategy_ideas.service import StrategyIdeaError, StrategyIdeaService

AuthDep = Callable[..., Awaitable[Any] | Any]


class StrategyIdeaGenerateRequest(BaseModel):
    theme: str | None = Field(default=None, max_length=80)
    as_of_date: str | None = Field(default=None, min_length=10, max_length=10)
    risk_preference: str = Field(default="balanced", max_length=20)
    max_ideas: int = Field(default=8, ge=1, le=20)
    min_candidate_score: float = Field(default=0.0, ge=0, le=1)
    strategy_types: list[str] | None = Field(default=None, max_length=20)


class StrategyIdeaSaveSpecRequest(BaseModel):
    enabled: bool = True


def _service() -> StrategyIdeaService:
    return StrategyIdeaService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_strategy_idea_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: StrategyIdeaError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_strategy_idea_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount strategy idea generation and query endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/strategy-ideas/generate", dependencies=[Depends(auth)])
    def generate_strategy_ideas(payload: StrategyIdeaGenerateRequest) -> dict[str, Any]:
        try:
            return _service().generate_ideas(
                theme=payload.theme,
                as_of_date=payload.as_of_date,
                risk_preference=payload.risk_preference,
                max_ideas=payload.max_ideas,
                min_candidate_score=payload.min_candidate_score,
                strategy_types=payload.strategy_types,
            )
        except StrategyIdeaError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/strategy-ideas", dependencies=[Depends(auth)])
    def list_strategy_ideas(
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        theme: str | None = Query(None, max_length=80),
        strategy_type: str | None = Query(None, max_length=80),
        status: str | None = Query(None, max_length=40),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        try:
            ideas = _service().list_ideas(
                as_of_date=as_of_date,
                theme=theme,
                strategy_type=strategy_type,
                status=status,
                limit=limit,
            )
        except StrategyIdeaError as exc:
            raise _http_error(exc) from exc
        return {
            "status": "ok",
            "ideas": ideas,
            "idea_count": len(ideas),
            "research_only": True,
            "live_trading": False,
        }

    @app.get("/api/strategy-ideas/{idea_id}", dependencies=[Depends(auth)])
    def get_strategy_idea(idea_id: str) -> dict[str, Any]:
        try:
            return _service().get_idea(idea_id)
        except StrategyIdeaError as exc:
            raise _http_error(exc, status_code=404) from exc

    @app.post("/api/strategy-ideas/{idea_id}/save-spec", dependencies=[Depends(auth)])
    def save_strategy_idea_as_spec(idea_id: str, payload: StrategyIdeaSaveSpecRequest) -> dict[str, Any]:
        try:
            return _service().save_idea_as_strategy_spec(idea_id=idea_id, enabled=payload.enabled)
        except StrategyIdeaError as exc:
            raise _http_error(exc) from exc
