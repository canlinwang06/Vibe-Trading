"""JoinQuant export routes for local A-share research signals."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.joinquant_adapter.service import JoinQuantExportError, JoinQuantExportService

AuthDep = Callable[..., Awaitable[Any] | Any]
DEFAULT_RISK_NOTICE = "研究/模拟用途；复制到聚宽后必须人工确认风险，不能直接用于实盘。"


class JoinQuantExportRequest(BaseModel):
    portfolio_id: str = Field(default="cn_a_main", min_length=3, max_length=80)
    signal_date: str | None = Field(default=None, min_length=10, max_length=10)
    strategy_id: str | None = Field(default=None, min_length=3, max_length=120)
    risk_notice: str = Field(default=DEFAULT_RISK_NOTICE, max_length=300)
    require_approved: bool = True


class JoinQuantExecutionReportImportRequest(BaseModel):
    portfolio_id: str = Field(default="cn_a_main", min_length=3, max_length=80)
    signal_date: str | None = Field(default=None, min_length=10, max_length=10)
    trade_date: str | None = Field(default=None, min_length=10, max_length=10)
    replace: bool = False
    reports: list[dict[str, Any]] = Field(min_length=1, max_length=500)


def _service() -> JoinQuantExportService:
    return JoinQuantExportService()


def _resolve_auth(require_local_or_auth: AuthDep | None) -> AuthDep:
    if require_local_or_auth is not None:
        return require_local_or_auth

    import sys as _sys

    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:  # pragma: no cover
        raise RuntimeError("register_joinquant_routes: pass require_local_or_auth explicitly")
    return host.require_local_or_auth


def _http_error(exc: JoinQuantExportError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


def register_joinquant_routes(app: FastAPI, require_local_or_auth: AuthDep | None = None) -> None:
    """Mount PR-15 JoinQuant export endpoints."""
    auth = _resolve_auth(require_local_or_auth)

    @app.post("/api/joinquant/export/preflight", dependencies=[Depends(auth)])
    def preflight_export(payload: JoinQuantExportRequest) -> dict[str, Any]:
        try:
            return _service().preflight(
                portfolio_id=payload.portfolio_id,
                signal_date=payload.signal_date,
                require_approved=payload.require_approved,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/joinquant/export/signals-json", dependencies=[Depends(auth)])
    def export_signals_json(payload: JoinQuantExportRequest) -> dict[str, Any]:
        try:
            return _service().export_signals_json(
                portfolio_id=payload.portfolio_id,
                signal_date=payload.signal_date,
                require_approved=payload.require_approved,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/joinquant/export/signals-csv", dependencies=[Depends(auth)])
    def export_signals_csv(payload: JoinQuantExportRequest) -> dict[str, Any]:
        try:
            return _service().export_signals_csv(
                portfolio_id=payload.portfolio_id,
                signal_date=payload.signal_date,
                require_approved=payload.require_approved,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/joinquant/export/strategy-code", dependencies=[Depends(auth)])
    def export_strategy_code(payload: JoinQuantExportRequest) -> dict[str, Any]:
        try:
            return _service().export_strategy_code(
                portfolio_id=payload.portfolio_id,
                signal_date=payload.signal_date,
                strategy_id=payload.strategy_id,
                risk_notice=payload.risk_notice,
                require_approved=payload.require_approved,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/joinquant/export/copy-package", dependencies=[Depends(auth)])
    def export_copy_package(payload: JoinQuantExportRequest) -> dict[str, Any]:
        try:
            return _service().export_copy_package(
                portfolio_id=payload.portfolio_id,
                signal_date=payload.signal_date,
                strategy_id=payload.strategy_id,
                risk_notice=payload.risk_notice,
                require_approved=payload.require_approved,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/joinquant/execution-reports/import", dependencies=[Depends(auth)])
    def import_execution_reports(payload: JoinQuantExecutionReportImportRequest) -> dict[str, Any]:
        try:
            return _service().import_execution_reports(
                portfolio_id=payload.portfolio_id,
                signal_date=payload.signal_date,
                trade_date=payload.trade_date,
                replace=payload.replace,
                reports=payload.reports,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/joinquant/execution-reports", dependencies=[Depends(auth)])
    def list_execution_reports(
        portfolio_id: str | None = Query(default=None, min_length=3, max_length=80),
        signal_date: str | None = Query(default=None, min_length=10, max_length=10),
        trade_date: str | None = Query(default=None, min_length=10, max_length=10),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            reports = _service().list_execution_reports(
                portfolio_id=portfolio_id,
                signal_date=signal_date,
                trade_date=trade_date,
                limit=limit,
            )
            return {"status": "ok", "count": len(reports), "reports": reports}
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/joinquant/execution-reports/summary", dependencies=[Depends(auth)])
    def summarize_execution_reports(
        portfolio_id: str = Query(default="cn_a_main", min_length=3, max_length=80),
        signal_date: str | None = Query(default=None, min_length=10, max_length=10),
        trade_date: str | None = Query(default=None, min_length=10, max_length=10),
        tolerance: float = Query(default=0.01, ge=0.0, le=1.0),
    ) -> dict[str, Any]:
        try:
            return _service().execution_report_summary(
                portfolio_id=portfolio_id,
                signal_date=signal_date,
                trade_date=trade_date,
                tolerance=tolerance,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/joinquant/simulation-readiness", dependencies=[Depends(auth)])
    def simulation_readiness_report(
        portfolio_id: str = Query(default="cn_a_main", min_length=3, max_length=80),
        lookback_days: int = Query(default=90, ge=1, le=365),
        min_batches: int = Query(default=20, ge=1, le=250),
        tolerance: float = Query(default=0.01, ge=0.0, le=1.0),
        max_failed_rate: float = Query(default=0.05, ge=0.0, le=1.0),
        max_missing_rate: float = Query(default=0.05, ge=0.0, le=1.0),
        max_deviation_rate: float = Query(default=0.10, ge=0.0, le=1.0),
        max_signal_delay_days: int = Query(default=3, ge=0, le=30),
    ) -> dict[str, Any]:
        try:
            return _service().simulation_readiness_report(
                portfolio_id=portfolio_id,
                lookback_days=lookback_days,
                min_batches=min_batches,
                tolerance=tolerance,
                max_failed_rate=max_failed_rate,
                max_missing_rate=max_missing_rate,
                max_deviation_rate=max_deviation_rate,
                max_signal_delay_days=max_signal_delay_days,
            )
        except JoinQuantExportError as exc:
            raise _http_error(exc) from exc
