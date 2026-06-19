"""Candidate-pool routes for PR-09 A-share research workflows."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.candidate_pool.service import CandidatePoolError, CandidatePoolService

AuthDep = Callable[..., Awaitable[Any] | Any]


class CandidatePoolBuildRequest(BaseModel):
    as_of_date: str | None = Field(default=None, min_length=10, max_length=10)
    limit: int = Field(default=50, ge=1, le=200)
    min_sector_score: float = Field(default=0.0, ge=0, le=1)


class UserCandidateRequest(BaseModel):
    ticker: str = Field(..., min_length=9, max_length=9)
    ticker_name: str | None = Field(default=None, min_length=1, max_length=80)
    as_of_date: str | None = Field(default=None, min_length=10, max_length=10)
    theme: str | None = Field(default=None, max_length=80)
    sector_id: str | None = Field(default=None, max_length=80)
    sector_name: str | None = Field(default=None, max_length=80)
    reason: str | None = Field(default=None, max_length=500)
    user_priority: int = Field(default=100, ge=0, le=999)


class CandidateDecisionRequest(BaseModel):
    ticker: str = Field(..., min_length=9, max_length=9)
    as_of_date: str | None = Field(default=None, min_length=10, max_length=10)
    reason: str | None = Field(default=None, max_length=500)


def _service() -> CandidatePoolService:
    return CandidatePoolService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_candidate_pool_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: CandidatePoolError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_candidate_pool_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount PR-09 candidate-pool endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.get("/api/candidate-pool", dependencies=[Depends(auth)])
    def list_candidate_pool(
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        limit: int = Query(100, ge=1, le=500),
        source: str | None = Query(None, max_length=40),
        included: bool | None = Query(None),
        min_score: float = Query(0.0, ge=0, le=1),
    ) -> dict[str, Any]:
        try:
            rows = _service().list_candidates(
                as_of_date=as_of_date,
                limit=limit,
                source=source,
                included=included,
                min_score=min_score,
            )
        except CandidatePoolError as exc:
            raise _http_error(exc) from exc
        return {"candidates": rows, "candidate_count": len(rows)}

    @app.post("/api/candidate-pool/build", dependencies=[Depends(auth)])
    def build_candidate_pool(payload: CandidatePoolBuildRequest) -> dict[str, Any]:
        try:
            return _service().build_candidate_pool(
                as_of_date=payload.as_of_date,
                limit=payload.limit,
                min_sector_score=payload.min_sector_score,
            )
        except CandidatePoolError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/candidate-pool/user-add", dependencies=[Depends(auth)])
    def add_user_candidate(payload: UserCandidateRequest) -> dict[str, Any]:
        try:
            return _service().add_user_candidate(
                ticker=payload.ticker,
                ticker_name=payload.ticker_name,
                as_of_date=payload.as_of_date,
                theme=payload.theme,
                sector_id=payload.sector_id,
                sector_name=payload.sector_name,
                reason=payload.reason,
                user_priority=payload.user_priority,
            )
        except CandidatePoolError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/candidate-pool/include", dependencies=[Depends(auth)])
    def include_candidate(payload: CandidateDecisionRequest) -> dict[str, Any]:
        try:
            return _service().set_included(
                ticker=payload.ticker,
                as_of_date=payload.as_of_date,
                included=True,
                reason=payload.reason,
            )
        except CandidatePoolError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/candidate-pool/exclude", dependencies=[Depends(auth)])
    def exclude_candidate(payload: CandidateDecisionRequest) -> dict[str, Any]:
        try:
            return _service().set_included(
                ticker=payload.ticker,
                as_of_date=payload.as_of_date,
                included=False,
                reason=payload.reason,
            )
        except CandidatePoolError as exc:
            raise _http_error(exc) from exc
