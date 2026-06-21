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


class AdvisorThesisRequest(BaseModel):
    portfolio_id: str = Field(default=DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80)
    ticker: str = Field(..., min_length=9, max_length=9)
    ticker_name: str | None = Field(default=None, min_length=1, max_length=80)
    thesis_id: str | None = Field(default=None, max_length=120)
    thesis_type: str = Field(default="manual_advisor", min_length=1, max_length=80)
    strategy_type: str | None = Field(default=None, max_length=80)
    strategy_cycle: str | None = Field(default=None, max_length=80)
    thesis: str | None = Field(default=None, max_length=2000)
    buy_reason: str | None = Field(default=None, max_length=2000)
    entry_conditions: str | None = Field(default=None, max_length=2000)
    exit_conditions: str | None = Field(default=None, max_length=2000)
    not_buy_conditions: str | None = Field(default=None, max_length=2000)
    expected_catalysts: str | None = Field(default=None, max_length=2000)
    invalidation_conditions: str | None = Field(default=None, max_length=2000)
    stop_loss_price: float | None = Field(default=None, gt=0)
    take_profit_price: float | None = Field(default=None, gt=0)
    max_position_pct: float | None = Field(default=None, ge=0, le=1)
    target_holding_days: int | None = Field(default=None, ge=1, le=3650)
    review_frequency_days: int | None = Field(default=None, ge=1, le=365)
    as_of_date: str | None = Field(default=None, min_length=10, max_length=10)
    evidence: dict[str, Any] | None = None
    bind_to_position: bool = True
    bind_to_watchlist: bool = True
    created_by: str = Field(default="codex", min_length=1, max_length=80)


class AdvisorWatchlistRequest(BaseModel):
    portfolio_id: str = Field(default=DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80)
    ticker: str = Field(..., min_length=9, max_length=9)
    ticker_name: str | None = Field(default=None, min_length=1, max_length=80)
    theme: str | None = Field(default=None, max_length=80)
    sector_id: str | None = Field(default=None, max_length=80)
    sector_name: str | None = Field(default=None, max_length=80)
    strategy_type: str | None = Field(default=None, max_length=80)
    strategy_cycle: str | None = Field(default=None, max_length=80)
    watch_status: str = Field(default="watching", min_length=1, max_length=80)
    target_buy_price: float | None = Field(default=None, gt=0)
    trigger_price: float | None = Field(default=None, gt=0)
    stop_loss_price: float | None = Field(default=None, gt=0)
    max_position_pct: float | None = Field(default=None, ge=0, le=1)
    not_buy_conditions: str | None = Field(default=None, max_length=2000)
    reason: str | None = Field(default=None, max_length=2000)
    evidence: dict[str, Any] | None = None
    thesis_id: str | None = Field(default=None, max_length=120)
    next_review_date: str | None = Field(default=None, min_length=10, max_length=10)
    created_by: str = Field(default="codex", min_length=1, max_length=80)


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

    @app.post("/api/advisor/theses", dependencies=[Depends(auth)])
    def upsert_thesis(payload: AdvisorThesisRequest) -> dict[str, Any]:
        try:
            return _service().upsert_thesis(
                portfolio_id=payload.portfolio_id,
                ticker=payload.ticker,
                ticker_name=payload.ticker_name,
                thesis_id=payload.thesis_id,
                thesis_type=payload.thesis_type,
                strategy_type=payload.strategy_type,
                strategy_cycle=payload.strategy_cycle,
                thesis=payload.thesis,
                buy_reason=payload.buy_reason,
                entry_conditions=payload.entry_conditions,
                exit_conditions=payload.exit_conditions,
                not_buy_conditions=payload.not_buy_conditions,
                expected_catalysts=payload.expected_catalysts,
                invalidation_conditions=payload.invalidation_conditions,
                stop_loss_price=payload.stop_loss_price,
                take_profit_price=payload.take_profit_price,
                max_position_pct=payload.max_position_pct,
                target_holding_days=payload.target_holding_days,
                review_frequency_days=payload.review_frequency_days,
                as_of_date=payload.as_of_date,
                evidence=payload.evidence,
                bind_to_position=payload.bind_to_position,
                bind_to_watchlist=payload.bind_to_watchlist,
                created_by=payload.created_by,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/theses", dependencies=[Depends(auth)])
    def list_theses(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        ticker: str | None = Query(None, min_length=9, max_length=9),
        include_incomplete: bool = Query(True),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            theses = _service().list_theses(
                portfolio_id=portfolio_id,
                ticker=ticker,
                include_incomplete=include_incomplete,
                limit=limit,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc
        return {
            "portfolio_id": portfolio_id,
            "theses": theses,
            "thesis_count": len(theses),
            "research_only": True,
            "live_trading": False,
        }

    @app.get("/api/advisor/prices", dependencies=[Depends(auth)])
    def resolve_prices(
        ticker: list[str] = Query(default_factory=list),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        stale_after_days: int = Query(5, ge=1, le=30),
    ) -> dict[str, Any]:
        try:
            return _service().resolve_prices(
                tickers=ticker,
                as_of_date=as_of_date,
                stale_after_days=stale_after_days,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/portfolio-prices", dependencies=[Depends(auth)])
    def resolve_portfolio_prices(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        include_watchlist: bool = Query(True),
        stale_after_days: int = Query(5, ge=1, le=30),
    ) -> dict[str, Any]:
        try:
            return _service().resolve_portfolio_prices(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                include_watchlist=include_watchlist,
                stale_after_days=stale_after_days,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/holding-diagnostics", dependencies=[Depends(auth)])
    def diagnose_holdings(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        stale_after_days: int = Query(5, ge=1, le=30),
        persist: bool = Query(True),
    ) -> dict[str, Any]:
        try:
            return _service().diagnose_holdings(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                stale_after_days=stale_after_days,
                persist=persist,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/advisor/watchlist", dependencies=[Depends(auth)])
    def upsert_watchlist_item(payload: AdvisorWatchlistRequest) -> dict[str, Any]:
        try:
            return _service().upsert_watchlist_item(
                portfolio_id=payload.portfolio_id,
                ticker=payload.ticker,
                ticker_name=payload.ticker_name,
                theme=payload.theme,
                sector_id=payload.sector_id,
                sector_name=payload.sector_name,
                strategy_type=payload.strategy_type,
                strategy_cycle=payload.strategy_cycle,
                watch_status=payload.watch_status,
                target_buy_price=payload.target_buy_price,
                trigger_price=payload.trigger_price,
                stop_loss_price=payload.stop_loss_price,
                max_position_pct=payload.max_position_pct,
                not_buy_conditions=payload.not_buy_conditions,
                reason=payload.reason,
                evidence=payload.evidence,
                thesis_id=payload.thesis_id,
                next_review_date=payload.next_review_date,
                created_by=payload.created_by,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/watchlist-candidates", dependencies=[Depends(auth)])
    def build_watchlist_candidates(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        limit: int = Query(50, ge=1, le=200),
        stale_after_days: int = Query(5, ge=1, le=30),
        persist: bool = Query(True),
    ) -> dict[str, Any]:
        try:
            return _service().build_watchlist_candidates(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                limit=limit,
                stale_after_days=stale_after_days,
                persist=persist,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/risk-filters", dependencies=[Depends(auth)])
    def build_risk_filters(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
        limit: int = Query(50, ge=1, le=200),
        stale_after_days: int = Query(5, ge=1, le=30),
    ) -> dict[str, Any]:
        try:
            return _service().build_risk_filters(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                limit=limit,
                stale_after_days=stale_after_days,
            )
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/today-snapshot", dependencies=[Depends(auth)])
    def today_snapshot(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
    ) -> dict[str, Any]:
        try:
            return _service().today_snapshot(portfolio_id=portfolio_id, as_of_date=as_of_date)
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/holdings-snapshot", dependencies=[Depends(auth)])
    def holdings_snapshot(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
    ) -> dict[str, Any]:
        try:
            return _service().holdings_snapshot(portfolio_id=portfolio_id, as_of_date=as_of_date)
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/watchlist-snapshot", dependencies=[Depends(auth)])
    def watchlist_snapshot(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        as_of_date: str | None = Query(None, min_length=10, max_length=10),
    ) -> dict[str, Any]:
        try:
            return _service().watchlist_snapshot(portfolio_id=portfolio_id, as_of_date=as_of_date)
        except AdvisorError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/advisor/journal-snapshot", dependencies=[Depends(auth)])
    def journal_snapshot(
        portfolio_id: str = Query(DEFAULT_PORTFOLIO_ID, min_length=3, max_length=80),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        try:
            return _service().journal_snapshot(portfolio_id=portfolio_id, limit=limit)
        except AdvisorError as exc:
            raise _http_error(exc) from exc
