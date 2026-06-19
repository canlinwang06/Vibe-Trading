"""Strategy-lab routes for PR-10 A-share strategy templates."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.strategy_lab.backtest_factory import BacktestFactoryError, BacktestFactoryService
from src.strategy_lab.service import StrategyLabError, StrategyLabService

AuthDep = Callable[..., Awaitable[Any] | Any]


class StrategySpecSeedRequest(BaseModel):
    replace: bool = False


class StrategySpecCreateRequest(BaseModel):
    strategy_type: str = Field(..., min_length=3, max_length=80)
    strategy_name: str = Field(..., min_length=3, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)
    rebalance_freq: str = Field(..., min_length=3, max_length=40)
    holding_period: int = Field(..., ge=1, le=60)
    max_position: float = Field(..., ge=0, le=1)
    max_sector_exposure: float = Field(..., ge=0, le=1)
    max_total_exposure: float = Field(..., ge=0, le=1)
    stop_loss: float = Field(..., ge=0, le=1)
    take_profit: float = Field(..., ge=0, le=1)
    enabled: bool = True


class BacktestBatchRequest(BaseModel):
    start_date: str = Field(..., min_length=10, max_length=10)
    end_date: str = Field(..., min_length=10, max_length=10)
    as_of_date: str | None = Field(default=None, min_length=10, max_length=10)
    strategy_ids: list[str] | None = Field(default=None, max_length=100)
    limit: int = Field(default=24, ge=1, le=100)
    benchmark: str = Field(default="000300.SH", min_length=9, max_length=9)


def _service() -> StrategyLabService:
    return StrategyLabService()


def _backtest_factory() -> BacktestFactoryService:
    return BacktestFactoryService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_strategy_lab_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: StrategyLabError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def _backtest_http_error(exc: BacktestFactoryError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_strategy_lab_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount PR-10 strategy-lab endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.get("/api/strategy-lab/templates", dependencies=[Depends(auth)])
    def list_strategy_templates() -> dict[str, Any]:
        templates = _service().list_templates()
        return {"templates": templates, "template_count": len(templates)}

    @app.post("/api/strategy-lab/specs/seed", dependencies=[Depends(auth)])
    def seed_strategy_specs(payload: StrategySpecSeedRequest) -> dict[str, Any]:
        try:
            return _service().seed_strategy_specs(replace=payload.replace)
        except StrategyLabError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/strategy-lab/backtest-batch", dependencies=[Depends(auth)])
    def run_backtest_batch(payload: BacktestBatchRequest) -> dict[str, Any]:
        try:
            return _backtest_factory().run_backtest_batch(
                start_date=payload.start_date,
                end_date=payload.end_date,
                as_of_date=payload.as_of_date,
                strategy_ids=payload.strategy_ids,
                limit=payload.limit,
                benchmark=payload.benchmark,
            )
        except BacktestFactoryError as exc:
            raise _backtest_http_error(exc) from exc

    @app.get("/api/strategy-lab/backtest-runs", dependencies=[Depends(auth)])
    def list_backtest_runs(
        strategy_id: str | None = Query(None, max_length=160),
        status: str | None = Query(None, max_length=40),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            runs = _backtest_factory().list_backtest_runs(
                strategy_id=strategy_id,
                status=status,
                limit=limit,
            )
        except BacktestFactoryError as exc:
            raise _backtest_http_error(exc) from exc
        return {"backtest_runs": runs, "run_count": len(runs)}

    @app.get("/api/strategy-lab/backtest-runs/{run_id}", dependencies=[Depends(auth)])
    def get_backtest_run(run_id: str) -> dict[str, Any]:
        try:
            return _backtest_factory().get_backtest_run(run_id)
        except BacktestFactoryError as exc:
            raise _backtest_http_error(exc, status_code=404) from exc

    @app.get("/api/strategy-lab/specs", dependencies=[Depends(auth)])
    def list_strategy_specs(
        strategy_type: str | None = Query(None, max_length=80),
        enabled: bool | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            specs = _service().list_strategy_specs(strategy_type=strategy_type, enabled=enabled, limit=limit)
        except StrategyLabError as exc:
            raise _http_error(exc) from exc
        return {"strategy_specs": specs, "spec_count": len(specs)}

    @app.post("/api/strategy-lab/specs", dependencies=[Depends(auth)])
    def create_strategy_spec(payload: StrategySpecCreateRequest) -> dict[str, Any]:
        try:
            return _service().create_strategy_spec(
                strategy_type=payload.strategy_type,
                strategy_name=payload.strategy_name,
                params=payload.params,
                rebalance_freq=payload.rebalance_freq,
                holding_period=payload.holding_period,
                max_position=payload.max_position,
                max_sector_exposure=payload.max_sector_exposure,
                max_total_exposure=payload.max_total_exposure,
                stop_loss=payload.stop_loss,
                take_profit=payload.take_profit,
                enabled=payload.enabled,
            )
        except StrategyLabError as exc:
            raise _http_error(exc) from exc
