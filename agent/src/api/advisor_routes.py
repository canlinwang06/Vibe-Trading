"""Advisor ledger routes for Codex-directed research holdings."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.advisor.service import DEFAULT_PORTFOLIO_ID, AdvisorError, AdvisorService

AuthDep = Callable[..., Awaitable[Any] | Any]


class AdvisorTransactionRequest(BaseModel):
    portfolio_id: str = Field(default=DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80)
    ticker: str = Field(..., min_length=9, max_length=9)
    ticker_name: str | None = Field(default=None, min_length=1, max_length=80)
    action: str = Field(..., min_length=1, max_length=20)
    price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    trade_date: str | None = Field(default=None, min_length=10, max_length=10)
    fees: float = Field(default=0.0, ge=0)
    strategy_type: str | None = Field(default=None, max_length=80)
    strategy_cycle: str | None = Field(default=None, max_length=80)
    thesis: str | None = Field(default=None, max_length=2000)
    buy_reason: str | None = Field(default=None, max_length=2000)
    expected_catalysts: str | None = Field(default=None, max_length=2000)
    invalidation_conditions: str | None = Field(default=None, max_length=2000)
    stop_loss_price: float | None = Field(default=None, gt=0)
    take_profit_price: float | None = Field(default=None, gt=0)
    max_position_pct: float | None = Field(default=None, ge=0, le=1)
    target_holding_days: int | None = Field(default=None, ge=1, le=3650)
    reason: str | None = Field(default=None, max_length=2000)
    source_command: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=160)
    created_by: str = Field(default="codex", min_length=1, max_length=80)
    evidence: dict[str, Any] | None = None


def _service() -> AdvisorService:
    return AdvisorService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_advisor_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: AdvisorError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_advisor_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount research-only advisor endpoints for Codex local commands."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/advisor/transactions", dependencies=[Depends(auth)])
    def record_transaction(payload: AdvisorTransactionRequest) -> dict[str, Any]:
        try:
            return _service().record_transaction(
                portfolio_id=payload.portfolio_id,
                ticker=payload.ticker,
                ticker_name=payload.ticker_name,
                action=payload.action,
                price=payload.price,
                quantity=payload.quantity,
                trade_date=payload.trade_date,
                fees=payload.fees,
                strategy_type=payload.strategy_type,
                strategy_cycle=payload.strategy_cycle,
                thesis=payload.thesis,
                buy_reason=payload.buy_reason,
                expected_catalysts=payload.expected_catalysts,
                invalidation_conditions=payload.invalidation_conditions,
                stop_loss_price=payload.stop_loss_price,
                take_profit_price=payload.take_profit_price,
                max_position_pct=payload.max_position_pct,
                target_holding_days=payload.target_holding_days,
                reason=payload.reason,
                source_command=payload.source_command,
                idempotency_key=payload.idempotency_key,
                created_by=payload.created_by,
                evidence=payload.evidence,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/portfolio-summary", dependencies=[Depends(auth)])
    def get_portfolio_summary(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
    ) -> dict[str, Any]:
        try:
            return _service().portfolio_summary(portfolio_id=portfolio_id)
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/positions", dependencies=[Depends(auth)])
    def list_positions(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        include_closed: bool = Query(False),
    ) -> dict[str, Any]:
        try:
            positions = _service().list_positions(
                portfolio_id=portfolio_id,
                include_closed=include_closed,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc
        return {
            "portfolio_id": portfolio_id,
            "positions": positions,
            "position_count": len(positions),
            "research_only": True,
            "live_trading": False,
        }

