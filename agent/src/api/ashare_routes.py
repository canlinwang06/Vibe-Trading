"""A-share asset and market-data routes for PR-04."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.ashare_data.market_data import AShareMarketDataError, AShareMarketDataService

AuthDep = Callable[..., Awaitable[Any] | Any]


class MarketDataUpdateRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=20)
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    source: Literal["auto", "local", "akshare"] = "auto"


def _service() -> AShareMarketDataService:
    return AShareMarketDataService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_ashare_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: AShareMarketDataError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_ashare_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount PR-04 A-share asset and market-data endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.get("/ashare/assets/{ticker}", dependencies=[Depends(auth)])
    async def get_ashare_asset(ticker: str) -> dict[str, Any]:
        try:
            return _service().get_asset(ticker)
        except AShareMarketDataError as exc:
            raise _http_error(exc, status_code=404) from exc

    @app.get("/ashare/market-daily", dependencies=[Depends(auth)])
    async def get_ashare_market_daily(
        ticker: str = Query(..., description="A-share ticker, e.g. 600519.SH"),
        start_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
        end_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ) -> dict[str, Any]:
        try:
            rows = _service().get_market_daily(ticker, start_date, end_date)
        except AShareMarketDataError as exc:
            raise _http_error(exc) from exc
        if not rows:
            raise HTTPException(status_code=404, detail="未找到日线行情，请先手动触发行情更新。")
        return {"ticker": ticker.upper(), "rows": rows, "row_count": len(rows)}

    @app.post("/ashare/market-data/update", dependencies=[Depends(auth)])
    async def update_ashare_market_data(payload: MarketDataUpdateRequest) -> dict[str, Any]:
        try:
            return _service().update_market_daily(
                payload.tickers,
                payload.start_date,
                payload.end_date,
                source=payload.source,
            )
        except AShareMarketDataError as exc:
            raise _http_error(exc) from exc
