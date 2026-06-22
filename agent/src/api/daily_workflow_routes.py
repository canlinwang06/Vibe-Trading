"""Daily workflow routes for manual local A-share research orchestration."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.daily_workflow.service import DailyWorkflowError, DailyWorkflowService
from src.event_radar.source_ingestion import RawDocumentRecord

AuthDep = Callable[..., Awaitable[Any] | Any]


class WorkflowDocumentPayload(BaseModel):
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


class DailyWorkflowRunRequest(BaseModel):
    workflow_date: str | None = Field(default=None, min_length=10, max_length=10)
    portfolio_id: str = Field(default="cn_a_main", min_length=3, max_length=80)
    steps: list[str] | None = Field(default=None, max_length=12)
    documents: list[WorkflowDocumentPayload] = Field(default_factory=list, max_length=100)
    dry_run: bool = False
    continue_on_error: bool = False
    event_limit: int = Field(default=100, ge=1, le=500)
    min_event_relevance: float = Field(default=0.0, ge=0, le=1)
    map_limit: int = Field(default=100, ge=1, le=500)
    min_mapping_relevance: float = Field(default=0.45, ge=0, le=1)
    sector_limit: int = Field(default=10, ge=1, le=50)
    candidate_limit: int = Field(default=50, ge=1, le=200)
    min_sector_score: float = Field(default=0.0, ge=0, le=1)
    seed_strategy_specs: bool = True
    backtest_start_date: str | None = Field(default=None, min_length=10, max_length=10)
    backtest_end_date: str | None = Field(default=None, min_length=10, max_length=10)
    backtest_limit: int = Field(default=24, ge=1, le=100)
    ranking_limit: int = Field(default=20, ge=1, le=500)
    top_n: int = Field(default=5, ge=3, le=5)
    market_regime: str = Field(default="normal", min_length=4, max_length=40)
    current_drawdown: float = Field(default=0.0, ge=-1.0, le=0.0)
    signal_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    replace_signals: bool = True
    event_reaction_windows: list[str] | None = Field(default=None, max_length=4)
    event_reaction_target_types: list[str] | None = Field(default=None, max_length=2)
    event_reaction_limit: int = Field(default=100, ge=1, le=500)
    replace_event_reactions: bool = True


def _service() -> DailyWorkflowService:
    return DailyWorkflowService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_daily_workflow_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: DailyWorkflowError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_daily_workflow_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount manual daily workflow endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/daily-workflow/run", dependencies=[Depends(auth)])
    def run_daily_workflow(payload: DailyWorkflowRunRequest) -> dict[str, Any]:
        try:
            return _service().run(
                workflow_date=payload.workflow_date,
                portfolio_id=payload.portfolio_id,
                steps=payload.steps,
                documents=[document.to_record() for document in payload.documents],
                dry_run=payload.dry_run,
                continue_on_error=payload.continue_on_error,
                event_limit=payload.event_limit,
                min_event_relevance=payload.min_event_relevance,
                map_limit=payload.map_limit,
                min_mapping_relevance=payload.min_mapping_relevance,
                sector_limit=payload.sector_limit,
                candidate_limit=payload.candidate_limit,
                min_sector_score=payload.min_sector_score,
                seed_strategy_specs=payload.seed_strategy_specs,
                backtest_start_date=payload.backtest_start_date,
                backtest_end_date=payload.backtest_end_date,
                backtest_limit=payload.backtest_limit,
                ranking_limit=payload.ranking_limit,
                top_n=payload.top_n,
                market_regime=payload.market_regime,
                current_drawdown=payload.current_drawdown,
                signal_confidence=payload.signal_confidence,
                replace_signals=payload.replace_signals,
                event_reaction_windows=payload.event_reaction_windows,
                event_reaction_target_types=payload.event_reaction_target_types,
                event_reaction_limit=payload.event_reaction_limit,
                replace_event_reactions=payload.replace_event_reactions,
            )
        except DailyWorkflowError as exc:
            raise _http_error(exc) from exc
