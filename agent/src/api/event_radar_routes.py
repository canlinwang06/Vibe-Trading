"""Event radar source, raw-document, and extraction routes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.event_radar.event_extraction import EventExtractionError, EventExtractionService
from src.event_radar.event_mapping import EventMappingError, EventMappingService
from src.event_radar.source_ingestion import (
    EventSourceIngestionError,
    EventSourceIngestionService,
    RawDocumentRecord,
)

AuthDep = Callable[..., Awaitable[Any] | Any]


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
        return RawDocumentRecord(
            source_id=self.source_id,
            title=self.title,
            content=self.content,
            publish_time=self.publish_time,
            summary=self.summary,
            crawl_time=self.crawl_time,
            url=self.url,
            language=self.language,
            author_or_account=self.author_or_account,
            hot_rank=self.hot_rank,
            hot_value=self.hot_value,
            raw_json=self.raw_json,
        )


class CollectRunRequest(BaseModel):
    documents: list[RawDocumentPayload] = Field(..., min_length=1, max_length=100)


class ExtractRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    min_relevance: float = Field(default=0.0, ge=0, le=1)


class MapRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    min_relevance: float = Field(default=0.45, ge=0, le=1)


def _service() -> EventSourceIngestionService:
    return EventSourceIngestionService()


def _extractor() -> EventExtractionService:
    return EventExtractionService()


def _mapper() -> EventMappingService:
    return EventMappingService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_event_radar_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: EventSourceIngestionError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def _event_http_error(exc: EventExtractionError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def _mapping_http_error(exc: EventMappingError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_event_radar_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount event radar collection, extraction, and query endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.get("/api/event-radar/sources", dependencies=[Depends(auth)])
    def list_event_sources(enabled_only: bool = Query(False)) -> dict[str, Any]:
        try:
            sources = _service().list_sources(enabled_only=enabled_only)
        except EventSourceIngestionError as exc:
            raise _http_error(exc) from exc
        return {"sources": sources, "source_count": len(sources)}

    @app.get("/api/event-radar/raw-documents", dependencies=[Depends(auth)])
    def list_raw_documents(
        limit: int = Query(50, ge=1, le=200),
        source_type: str | None = Query(None),
        source_id: str | None = Query(None),
    ) -> dict[str, Any]:
        try:
            documents = _service().list_raw_documents(
                limit=limit,
                source_type=source_type,
                source_id=source_id,
            )
        except EventSourceIngestionError as exc:
            raise _http_error(exc) from exc
        return {"documents": documents, "document_count": len(documents)}

    @app.post("/api/event-radar/collect/run", dependencies=[Depends(auth)])
    def run_event_collection(payload: CollectRunRequest) -> dict[str, Any]:
        try:
            return _service().ingest_documents(document.to_record() for document in payload.documents)
        except EventSourceIngestionError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/event-radar/extract/run", dependencies=[Depends(auth)])
    def run_event_extraction(payload: ExtractRunRequest) -> dict[str, Any]:
        try:
            return _extractor().extract_events(limit=payload.limit, min_relevance=payload.min_relevance)
        except EventExtractionError as exc:
            raise _event_http_error(exc) from exc

    @app.get("/api/event-radar/events", dependencies=[Depends(auth)])
    def list_events(
        limit: int = Query(50, ge=1, le=200),
        event_type: str | None = Query(None),
        min_relevance: float = Query(0.0, ge=0, le=1),
    ) -> dict[str, Any]:
        try:
            events = _extractor().list_events(
                limit=limit,
                event_type=event_type,
                min_relevance=min_relevance,
            )
        except EventExtractionError as exc:
            raise _event_http_error(exc) from exc
        return {"events": events, "event_count": len(events)}

    @app.get("/api/event-radar/clusters", dependencies=[Depends(auth)])
    def list_clusters(
        limit: int = Query(50, ge=1, le=200),
        status: str | None = Query(None),
        min_relevance: float = Query(0.0, ge=0, le=1),
    ) -> dict[str, Any]:
        try:
            clusters = _extractor().list_clusters(
                limit=limit,
                status=status,
                min_relevance=min_relevance,
            )
        except EventExtractionError as exc:
            raise _event_http_error(exc) from exc
        return {"clusters": clusters, "cluster_count": len(clusters)}

    @app.get("/api/event-radar/clusters/{cluster_id}", dependencies=[Depends(auth)])
    def get_cluster(cluster_id: str) -> dict[str, Any]:
        try:
            return _extractor().get_cluster(cluster_id)
        except EventExtractionError as exc:
            raise _event_http_error(exc, status_code=404) from exc

    @app.get("/api/event-radar/theme-map", dependencies=[Depends(auth)])
    def list_theme_map(theme: str | None = Query(None)) -> dict[str, Any]:
        try:
            rows = _mapper().list_theme_map(theme=theme)
        except EventMappingError as exc:
            raise _mapping_http_error(exc) from exc
        return {"theme_map": rows, "row_count": len(rows)}

    @app.post("/api/event-radar/map/run", dependencies=[Depends(auth)])
    def run_event_mapping(payload: MapRunRequest) -> dict[str, Any]:
        try:
            return _mapper().map_events(
                min_relevance=payload.min_relevance,
                limit=payload.limit,
            )
        except EventMappingError as exc:
            raise _mapping_http_error(exc) from exc

    @app.get("/api/event-radar/mappings/sectors", dependencies=[Depends(auth)])
    def list_event_sector_maps(
        event_id: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            rows = _mapper().list_event_sector_maps(event_id=event_id, limit=limit)
        except EventMappingError as exc:
            raise _mapping_http_error(exc) from exc
        return {"sector_mappings": rows, "row_count": len(rows)}

    @app.get("/api/event-radar/mappings/stocks", dependencies=[Depends(auth)])
    def list_event_stock_maps(
        event_id: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            rows = _mapper().list_event_stock_maps(event_id=event_id, limit=limit)
        except EventMappingError as exc:
            raise _mapping_http_error(exc) from exc
        return {"stock_mappings": rows, "row_count": len(rows)}
