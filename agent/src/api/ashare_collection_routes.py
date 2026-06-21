"""A-share public-data collection routes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.ashare_data.collection import AShareDataCollectionError, AShareDataCollectionService
from src.event_radar.source_ingestion import RawDocumentRecord

AuthDep = Callable[..., Awaitable[Any] | Any]


class StockSnapshotPayload(BaseModel):
    trade_date: str | None = Field(default=None, min_length=10, max_length=10)
    ticker: str = Field(..., min_length=6, max_length=12)
    ticker_name: str = Field(..., min_length=1, max_length=80)
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float = 0.0
    amount: float | None = None
    turnover: float | None = None
    pct_change: float | None = None
    volume_ratio: float | None = None
    sector_name: str | None = Field(default=None, max_length=80)
    source: str = Field(default="manual_payload", max_length=80)
    raw_json: dict[str, Any] | None = None

    def to_raw(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class SectorSnapshotPayload(BaseModel):
    trade_date: str | None = Field(default=None, min_length=10, max_length=10)
    sector_id: str | None = Field(default=None, max_length=120)
    sector_name: str = Field(..., min_length=1, max_length=80)
    sector_type: str = Field(default="concept", max_length=40)
    close: float | None = None
    return_: float | None = Field(default=None, alias="return")
    amount: float | None = None
    turnover: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    limit_up_count: int | None = None
    member_count: int | None = None
    leading_ticker: str | None = Field(default=None, max_length=80)
    source: str = Field(default="manual_payload", max_length=80)
    raw_json: dict[str, Any] | None = None

    def to_raw(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True, by_alias=True)
        if "return_" in payload:
            payload["return"] = payload.pop("return_")
        return payload


class RawDocumentPayload(BaseModel):
    source_id: str = Field(..., min_length=3, max_length=64)
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=20000)
    publish_time: str = Field(..., min_length=10, max_length=40)
    summary: str | None = Field(default=None, max_length=1000)
    crawl_time: str | None = Field(default=None, min_length=10, max_length=40)
    url: str | None = Field(default=None, max_length=1000)
    language: str = Field(default="zh-CN", min_length=2, max_length=16)
    author_or_account: str | None = Field(default=None, max_length=120)
    hot_rank: int | None = Field(default=None, ge=1, le=10000)
    hot_value: float | None = Field(default=None, ge=0)
    raw_json: dict[str, Any] | None = None

    def to_record(self) -> RawDocumentRecord:
        return RawDocumentRecord(**self.model_dump())


class AShareCollectionRunRequest(BaseModel):
    trade_date: str | None = Field(default=None, min_length=10, max_length=10)
    include_market: bool = True
    include_sector: bool = True
    include_news: bool = True
    include_announcements: bool = True
    stock_limit: int = Field(default=500, ge=1, le=3000)
    sector_limit: int = Field(default=120, ge=1, le=500)
    anomaly_limit: int = Field(default=120, ge=1, le=500)
    document_limit: int = Field(default=80, ge=1, le=500)
    symbols: list[str] | None = Field(default=None, max_length=50)
    keywords: list[str] | None = Field(default=None, max_length=20)
    extract_events: bool = True
    continue_on_error: bool = True
    market_records: list[StockSnapshotPayload] | None = Field(default=None, max_length=3000)
    sector_records: list[SectorSnapshotPayload] | None = Field(default=None, max_length=500)
    anomaly_source_records: list[StockSnapshotPayload] | None = Field(default=None, max_length=3000)
    documents: list[RawDocumentPayload] | None = Field(default=None, max_length=500)


def _service() -> AShareDataCollectionService:
    return AShareDataCollectionService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_ashare_collection_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: AShareDataCollectionError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_ashare_collection_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount Codex-facing public-data collection APIs."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/ashare/collection/run", dependencies=[Depends(auth)])
    def run_ashare_collection(payload: AShareCollectionRunRequest) -> dict[str, Any]:
        service = _service()
        try:
            steps: list[dict[str, Any]] = []
            if payload.market_records is not None:
                market = service.collect_market_snapshot(
                    trade_date=payload.trade_date,
                    records=[row.to_raw() for row in payload.market_records],
                    limit=payload.stock_limit,
                )
                steps.append({"name": "market_snapshot", "status": market["status"], "message": market["message"], "metrics": market})
            if payload.sector_records is not None or payload.anomaly_source_records is not None:
                sector = service.collect_sector_and_anomalies(
                    trade_date=payload.trade_date,
                    sector_records=[row.to_raw() for row in payload.sector_records or []],
                    stock_records=[row.to_raw() for row in payload.anomaly_source_records or []],
                    sector_limit=payload.sector_limit,
                    anomaly_limit=payload.anomaly_limit,
                )
                steps.append({"name": "sector_anomalies", "status": sector["status"], "message": sector["message"], "metrics": sector})
            if payload.documents is not None:
                news = service.collect_news_documents(
                    trade_date=payload.trade_date,
                    documents=[row.to_record() for row in payload.documents],
                    symbols=payload.symbols,
                    keywords=payload.keywords,
                    limit=payload.document_limit,
                    include_news=payload.include_news,
                    include_announcements=payload.include_announcements,
                    extract_events=payload.extract_events,
                )
                steps.append({"name": "news_documents", "status": news["status"], "message": news["message"], "metrics": news})
            if steps:
                return {
                    "status": "ok",
                    "trade_date": payload.trade_date,
                    "step_count": len(steps),
                    "failed_step_count": 0,
                    "rows_written": sum(int(step["metrics"].get("rows_written", 0) or 0) for step in steps),
                    "steps": steps,
                    "research_only": True,
                    "live_trading": False,
                }
            return service.collect_daily_package(
                trade_date=payload.trade_date,
                include_market=payload.include_market,
                include_sector=payload.include_sector,
                include_news=payload.include_news,
                include_announcements=payload.include_announcements,
                stock_limit=payload.stock_limit,
                sector_limit=payload.sector_limit,
                anomaly_limit=payload.anomaly_limit,
                document_limit=payload.document_limit,
                symbols=payload.symbols,
                keywords=payload.keywords,
                extract_events=payload.extract_events,
                continue_on_error=payload.continue_on_error,
            )
        except AShareDataCollectionError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/ashare/market-snapshot", dependencies=[Depends(auth)])
    def get_market_snapshot(
        trade_date: str | None = Query(default=None, min_length=10, max_length=10),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            return _service().market_snapshot(trade_date=trade_date, limit=limit)
        except AShareDataCollectionError as exc:
            raise _http_error(exc, status_code=404) from exc

    @app.get("/api/ashare/sector-anomalies", dependencies=[Depends(auth)])
    def get_sector_anomalies(
        trade_date: str | None = Query(default=None, min_length=10, max_length=10),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        try:
            return _service().sector_anomaly_snapshot(trade_date=trade_date, limit=limit)
        except AShareDataCollectionError as exc:
            raise _http_error(exc, status_code=404) from exc
