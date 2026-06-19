"""Portfolio-risk routes for A-share research allocations."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.portfolio_risk.service import PortfolioRiskError, PortfolioRiskService

AuthDep = Callable[..., Awaitable[Any] | Any]


class PortfolioAllocateRequest(BaseModel):
    portfolio_id: str = Field(default="cn_a_main", min_length=3, max_length=80)
    as_of_date: str | None = Field(default=None, min_length=10, max_length=10)
    top_n: int = Field(default=5, ge=3, le=5)
    market_regime: str = Field(default="normal", min_length=4, max_length=40)
    current_drawdown: float = Field(default=0.0, ge=-1.0, le=0.0)
    signal_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    max_strategy_weight: float = Field(default=0.30, ge=0.05, le=0.50)
    min_strategy_weight: float = Field(default=0.05, ge=0.0, le=0.20)
    max_strategy_type_weight: float = Field(default=0.50, ge=0.10, le=1.0)
    min_strategy_score: float = Field(default=0.0, ge=0.0, le=100.0)


def _service() -> PortfolioRiskService:
    return PortfolioRiskService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_portfolio_risk_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: PortfolioRiskError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_portfolio_risk_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount PR-13 portfolio-risk endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/portfolio-risk/allocate", dependencies=[Depends(auth)])
    def allocate_strategy_portfolio(payload: PortfolioAllocateRequest) -> dict[str, Any]:
        try:
            return _service().allocate(
                portfolio_id=payload.portfolio_id,
                as_of_date=payload.as_of_date,
                top_n=payload.top_n,
                market_regime=payload.market_regime,
                current_drawdown=payload.current_drawdown,
                signal_confidence=payload.signal_confidence,
                max_strategy_weight=payload.max_strategy_weight,
                min_strategy_weight=payload.min_strategy_weight,
                max_strategy_type_weight=payload.max_strategy_type_weight,
                min_strategy_score=payload.min_strategy_score,
            )
        except PortfolioRiskError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/portfolio-risk/allocations", dependencies=[Depends(auth)])
    def list_strategy_allocations(
        portfolio_id: str | None = Query(None, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            allocations = _service().list_allocations(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                limit=limit,
            )
        except PortfolioRiskError as exc:
            raise _http_error(exc) from exc
        return {"strategy_allocations": allocations, "allocation_count": len(allocations)}

    @app.get("/api/portfolio-risk/trade-plan", dependencies=[Depends(auth)])
    def get_trade_plan(
        portfolio_id: str = Query("cn_a_main", min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        max_single_stock_weight: float = Query(0.12, ge=0.01, le=0.30),
        max_sector_weight: float = Query(0.40, ge=0.05, le=0.80),
    ) -> dict[str, Any]:
        try:
            return _service().trade_plan(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                max_single_stock_weight=max_single_stock_weight,
                max_sector_weight=max_sector_weight,
            )
        except PortfolioRiskError as exc:
            raise _http_error(exc) from exc
