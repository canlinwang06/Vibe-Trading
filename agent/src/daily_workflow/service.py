"""Manual daily A-share research workflow orchestration.

The workflow only coordinates local research services. It does not approve
signals, export orders, call brokers, or place live trades.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable, Sequence

from src.ashare_data.store import AShareDataStore
from src.candidate_pool.service import CandidatePoolError, CandidatePoolService
from src.event_radar.event_extraction import EventExtractionError, EventExtractionService
from src.event_radar.event_mapping import EventMappingError, EventMappingService
from src.event_radar.sector_scoring import SectorScoringError, SectorScoringService
from src.event_radar.source_ingestion import (
    EventSourceIngestionError,
    EventSourceIngestionService,
    RawDocumentRecord,
)
from src.event_reactions.service import EventReactionError, EventReactionService
from src.portfolio_risk.service import PortfolioRiskError, PortfolioRiskService
from src.strategy_lab.backtest_factory import BacktestFactoryError, BacktestFactoryService
from src.strategy_lab.ranking import StrategyRankingError, StrategyRankingService
from src.strategy_lab.service import StrategyLabError, StrategyLabService

ALLOWED_WORKFLOW_STEPS: tuple[str, ...] = (
    "collect_documents",
    "extract_events",
    "map_events",
    "score_sectors",
    "build_candidates",
    "prepare_joinquant_strategy",
    "seed_strategy_specs",
    "run_backtests",
    "rank_backtests",
    "allocate_portfolio",
    "generate_draft_signals",
    "calculate_event_reactions",
)

DEFAULT_WORKFLOW_STEPS: tuple[str, ...] = (
    "collect_documents",
    "extract_events",
    "map_events",
    "score_sectors",
    "build_candidates",
    "prepare_joinquant_strategy",
)

WORKFLOW_ERRORS = (
    EventSourceIngestionError,
    EventExtractionError,
    EventMappingError,
    SectorScoringError,
    CandidatePoolError,
    StrategyLabError,
    BacktestFactoryError,
    StrategyRankingError,
    PortfolioRiskError,
    EventReactionError,
)

LARGE_RESULT_KEYS = {
    "doc_ids",
    "duplicate_doc_ids",
    "event_ids",
    "cluster_ids",
    "top_sectors",
    "candidates",
    "top_runs",
    "top_strategies",
    "rankings",
    "strategy_allocations",
    "execution_signals",
}


class DailyWorkflowError(ValueError):
    """Raised when a workflow request is invalid."""


class DailyWorkflowService:
    """Run a manual local research chain across existing PR modules."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def run(
        self,
        *,
        workflow_date: str | date | datetime | None = None,
        portfolio_id: str = "cn_a_main",
        steps: Sequence[str] | None = None,
        documents: Iterable[RawDocumentRecord] | None = None,
        dry_run: bool = False,
        continue_on_error: bool = False,
        event_limit: int = 100,
        min_event_relevance: float = 0.0,
        map_limit: int = 100,
        min_mapping_relevance: float = 0.45,
        sector_limit: int = 10,
        candidate_limit: int = 50,
        min_sector_score: float = 0.0,
        seed_strategy_specs: bool = True,
        backtest_start_date: str | date | datetime | None = None,
        backtest_end_date: str | date | datetime | None = None,
        backtest_limit: int = 24,
        ranking_limit: int = 20,
        top_n: int = 5,
        market_regime: str = "normal",
        current_drawdown: float = 0.0,
        signal_confidence: float = 1.0,
        replace_signals: bool = True,
        event_reaction_windows: Sequence[str] | None = None,
        event_reaction_target_types: Sequence[str] | None = None,
        event_reaction_limit: int = 100,
        replace_event_reactions: bool = True,
    ) -> dict[str, Any]:
        self.store.initialize()
        as_of = _parse_date(workflow_date, field_name="workflow_date") or date.today()
        selected_steps = _resolve_steps(steps)
        records = tuple(documents or ())

        if dry_run:
            return self._dry_run_response(
                workflow_date=as_of,
                portfolio_id=portfolio_id,
                steps=selected_steps,
            )

        context = {
            "workflow_date": as_of,
            "portfolio_id": _clean_portfolio_id(portfolio_id),
            "documents": records,
            "event_limit": _clamp_int(event_limit, minimum=1, maximum=500),
            "min_event_relevance": _clamp_float(min_event_relevance, minimum=0.0, maximum=1.0),
            "map_limit": _clamp_int(map_limit, minimum=1, maximum=500),
            "min_mapping_relevance": _clamp_float(min_mapping_relevance, minimum=0.0, maximum=1.0),
            "sector_limit": _clamp_int(sector_limit, minimum=1, maximum=50),
            "candidate_limit": _clamp_int(candidate_limit, minimum=1, maximum=200),
            "min_sector_score": _clamp_float(min_sector_score, minimum=0.0, maximum=1.0),
            "seed_strategy_specs": bool(seed_strategy_specs),
            "backtest_start_date": _parse_date(backtest_start_date, field_name="backtest_start_date"),
            "backtest_end_date": _parse_date(backtest_end_date, field_name="backtest_end_date") or as_of,
            "backtest_limit": _clamp_int(backtest_limit, minimum=1, maximum=100),
            "ranking_limit": _clamp_int(ranking_limit, minimum=1, maximum=500),
            "top_n": _clamp_int(top_n, minimum=3, maximum=5),
            "market_regime": (market_regime or "normal").strip() or "normal",
            "current_drawdown": _clamp_float(current_drawdown, minimum=-1.0, maximum=0.0),
            "signal_confidence": _clamp_float(signal_confidence, minimum=0.0, maximum=1.0),
            "replace_signals": bool(replace_signals),
            "event_reaction_windows": tuple(event_reaction_windows) if event_reaction_windows else None,
            "event_reaction_target_types": tuple(event_reaction_target_types) if event_reaction_target_types else None,
            "event_reaction_limit": _clamp_int(event_reaction_limit, minimum=1, maximum=500),
            "replace_event_reactions": bool(replace_event_reactions),
        }

        results: list[dict[str, Any]] = []
        blocked_step: str | None = None
        for step_name in selected_steps:
            try:
                step = self._run_step(step_name, context)
            except WORKFLOW_ERRORS as exc:
                step = _blocked_step(step_name, str(exc))
            results.append(step)
            if step["status"] == "blocked":
                blocked_step = blocked_step or step_name
                if not continue_on_error:
                    break

        return {
            "status": "blocked" if blocked_step else "ok",
            "workflow_date": context["workflow_date"].isoformat(),
            "portfolio_id": context["portfolio_id"],
            "requested_steps": list(selected_steps),
            "completed_step_count": sum(1 for item in results if item["status"] == "ok"),
            "skipped_step_count": sum(1 for item in results if item["status"] == "skipped"),
            "blocked_step": blocked_step,
            "steps": results,
            "research_only": True,
            "live_trading": False,
        }

    def _dry_run_response(
        self,
        *,
        workflow_date: date,
        portfolio_id: str,
        steps: Sequence[str],
    ) -> dict[str, Any]:
        return {
            "status": "dry_run",
            "workflow_date": workflow_date.isoformat(),
            "portfolio_id": _clean_portfolio_id(portfolio_id),
            "requested_steps": list(steps),
            "completed_step_count": 0,
            "skipped_step_count": 0,
            "blocked_step": None,
            "steps": [
                {
                    "name": step,
                    "status": "planned",
                    "message": _planned_message(step),
                    "metrics": {},
                }
                for step in steps
            ],
            "research_only": True,
            "live_trading": False,
        }

    def _run_step(self, step_name: str, context: dict[str, Any]) -> dict[str, Any]:
        runners: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "collect_documents": self._collect_documents,
            "extract_events": self._extract_events,
            "map_events": self._map_events,
            "score_sectors": self._score_sectors,
            "build_candidates": self._build_candidates,
            "prepare_joinquant_strategy": self._prepare_joinquant_strategy,
            "seed_strategy_specs": self._seed_strategy_specs,
            "run_backtests": self._run_backtests,
            "rank_backtests": self._rank_backtests,
            "allocate_portfolio": self._allocate_portfolio,
            "generate_draft_signals": self._generate_draft_signals,
            "calculate_event_reactions": self._calculate_event_reactions,
        }
        return runners[step_name](context)

    def _collect_documents(self, context: dict[str, Any]) -> dict[str, Any]:
        service = EventSourceIngestionService(store=self.store)
        sources = service.ensure_default_sources()
        records: tuple[RawDocumentRecord, ...] = context["documents"]
        if not records:
            return _skipped_step(
                "collect_documents",
                "没有传入新文档，已确认默认信息源。",
                {"source_count": len(sources), "document_count": 0},
            )

        result = service.ingest_documents(records)
        metrics = _summarize_result(result)
        metrics["source_count"] = len(sources)
        return _ok_step(
            "collect_documents",
            f"已导入 {result['inserted']} 条原始文档，重复 {result['duplicates']} 条。",
            metrics,
        )

    def _extract_events(self, context: dict[str, Any]) -> dict[str, Any]:
        try:
            result = EventExtractionService(store=self.store).extract_events(
                limit=context["event_limit"],
                min_relevance=context["min_event_relevance"],
            )
        except EventExtractionError:
            existing = self._existing_event_count()
            if existing <= 0:
                raise
            return _ok_step(
                "extract_events",
                f"没有新文档需要抽取，继续使用已有 {existing} 个事件。",
                {"existing_events": existing},
            )
        return _ok_step(
            "extract_events",
            f"已抽取 {result['extracted']} 个事件。",
            _summarize_result(result),
        )

    def _map_events(self, context: dict[str, Any]) -> dict[str, Any]:
        service = EventMappingService(store=self.store)
        service.ensure_default_theme_map()
        result = service.map_events(
            min_relevance=context["min_mapping_relevance"],
            limit=context["map_limit"],
        )
        self._align_workflow_date_to_latest_mapped_event(context)
        return _ok_step(
            "map_events",
            f"已映射 {result['mapped_events']} 个事件。",
            _summarize_result(result),
        )

    def _score_sectors(self, context: dict[str, Any]) -> dict[str, Any]:
        result = SectorScoringService(store=self.store).score_sectors(
            trade_date=context["workflow_date"],
            limit=context["sector_limit"],
            min_relevance=context["min_mapping_relevance"],
        )
        return _ok_step(
            "score_sectors",
            f"已为 {result['scored_sectors']} 个板块生成热度评分。",
            _summarize_result(result),
        )

    def _build_candidates(self, context: dict[str, Any]) -> dict[str, Any]:
        result = CandidatePoolService(store=self.store).build_candidate_pool(
            as_of_date=context["workflow_date"],
            limit=context["candidate_limit"],
            min_sector_score=context["min_sector_score"],
        )
        return _ok_step(
            "build_candidates",
            f"已生成 {result['candidate_count']} 条候选股票。",
            _summarize_result(result),
        )

    def _prepare_joinquant_strategy(self, context: dict[str, Any]) -> dict[str, Any]:
        result = PortfolioRiskService(store=self.store).generate_candidate_draft_signals(
            portfolio_id=context["portfolio_id"],
            signal_date=context["workflow_date"],
            replace=context["replace_signals"],
            candidate_limit=context["candidate_limit"],
        )
        return _ok_step(
            "prepare_joinquant_strategy",
            f"已生成 {result['signals_written']} 条聚宽模拟策略草案信号。",
            _summarize_result(result),
        )

    def _seed_strategy_specs(self, context: dict[str, Any]) -> dict[str, Any]:
        if not context["seed_strategy_specs"]:
            return _skipped_step(
                "seed_strategy_specs",
                "已按请求跳过策略规格初始化。",
                {"strategy_specs_written": 0},
            )
        result = StrategyLabService(store=self.store).seed_strategy_specs(replace=False)
        total = result["strategy_specs_written"] + result["strategy_specs_skipped"]
        return _ok_step(
            "seed_strategy_specs",
            f"已确认 {total} 个本地策略规格。",
            _summarize_result(result),
        )

    def _run_backtests(self, context: dict[str, Any]) -> dict[str, Any]:
        start = context["backtest_start_date"] or context["workflow_date"] - timedelta(days=30)
        end = context["backtest_end_date"]
        result = BacktestFactoryService(store=self.store).run_backtest_batch(
            start_date=start,
            end_date=end,
            as_of_date=context["workflow_date"],
            limit=context["backtest_limit"],
        )
        return _ok_step(
            "run_backtests",
            f"已写入 {result['runs_written']} 个本地回测结果。",
            _summarize_result(result),
        )

    def _rank_backtests(self, context: dict[str, Any]) -> dict[str, Any]:
        result = StrategyRankingService(store=self.store).top_summary(limit=context["ranking_limit"])
        return _ok_step(
            "rank_backtests",
            f"已完成 {result['ranking_count']} 个回测排名。",
            _summarize_result(result),
        )

    def _allocate_portfolio(self, context: dict[str, Any]) -> dict[str, Any]:
        result = PortfolioRiskService(store=self.store).allocate(
            portfolio_id=context["portfolio_id"],
            as_of_date=context["workflow_date"],
            top_n=context["top_n"],
            market_regime=context["market_regime"],
            current_drawdown=context["current_drawdown"],
            signal_confidence=context["signal_confidence"],
        )
        return _ok_step(
            "allocate_portfolio",
            f"已生成 {result['allocation_count']} 条策略权重草案。",
            _summarize_result(result),
        )

    def _generate_draft_signals(self, context: dict[str, Any]) -> dict[str, Any]:
        result = PortfolioRiskService(store=self.store).generate_draft_signals(
            portfolio_id=context["portfolio_id"],
            signal_date=context["workflow_date"],
            replace=context["replace_signals"],
        )
        return _ok_step(
            "generate_draft_signals",
            f"已生成 {result['signals_written']} 条执行信号草案，仍需人工确认。",
            _summarize_result(result),
        )

    def _calculate_event_reactions(self, context: dict[str, Any]) -> dict[str, Any]:
        result = EventReactionService(store=self.store).calculate_reactions(
            windows=context["event_reaction_windows"],
            target_types=context["event_reaction_target_types"],
            limit=context["event_reaction_limit"],
            replace=context["replace_event_reactions"],
        )
        return _ok_step(
            "calculate_event_reactions",
            f"已更新 {result['reactions_written']} 条事件反应研究结果。",
            _summarize_result(result),
        )

    def _existing_event_count(self) -> int:
        with self.store.connect(read_only=True) as conn:
            row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0] or 0) if row else 0

    def _align_workflow_date_to_latest_mapped_event(self, context: dict[str, Any]) -> None:
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT MAX(CAST(e.tradable_time AS DATE))
                FROM event_sector_map m
                JOIN events e ON e.event_id = m.event_id
                """
            ).fetchone()
        latest = _row_date(row[0]) if row and row[0] else None
        if latest and latest > context["workflow_date"]:
            context["workflow_date"] = latest


def _resolve_steps(steps: Sequence[str] | None) -> tuple[str, ...]:
    if steps is None:
        return DEFAULT_WORKFLOW_STEPS
    normalized = tuple(step.strip() for step in steps if step and step.strip())
    if not normalized:
        raise DailyWorkflowError("steps 至少需要包含一个工作流步骤。")
    unknown = [step for step in normalized if step not in ALLOWED_WORKFLOW_STEPS]
    if unknown:
        allowed = ", ".join(ALLOWED_WORKFLOW_STEPS)
        raise DailyWorkflowError(f"不支持的工作流步骤: {', '.join(unknown)}。可选步骤: {allowed}")
    duplicates = sorted({step for step in normalized if normalized.count(step) > 1})
    if duplicates:
        raise DailyWorkflowError(f"工作流步骤不能重复: {', '.join(duplicates)}")
    return normalized


def _parse_date(value: str | date | datetime | None, *, field_name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise DailyWorkflowError(f"{field_name} 必须是 YYYY-MM-DD 格式。") from exc


def _row_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    return datetime.fromisoformat(str(value)).date()


def _clean_portfolio_id(value: str) -> str:
    text = (value or "").strip()
    if len(text) < 3 or len(text) > 80:
        raise DailyWorkflowError("portfolio_id 长度必须在 3 到 80 个字符之间。")
    return text


def _clamp_int(value: int, *, minimum: int, maximum: int) -> int:
    return min(max(int(value), minimum), maximum)


def _clamp_float(value: float, *, minimum: float, maximum: float) -> float:
    return min(max(float(value), minimum), maximum)


def _ok_step(name: str, message: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": "ok", "message": message, "metrics": metrics}


def _skipped_step(name: str, message: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": "skipped", "message": message, "metrics": metrics}


def _blocked_step(name: str, message: str) -> dict[str, Any]:
    return {"name": name, "status": "blocked", "message": message, "metrics": {}}


def _planned_message(step: str) -> str:
    return {
        "collect_documents": "将确认默认信息源，并在有手工文档时导入本地库。",
        "extract_events": "将从本地原始文档抽取结构化事件。",
        "map_events": "将用本地主题映射把事件关联到板块和股票。",
        "score_sectors": "将基于事件和本地行情生成板块热度评分。",
        "build_candidates": "将基于板块评分生成候选股票池。",
        "prepare_joinquant_strategy": "将从观察股票池生成可复制到聚宽的模拟策略草案。",
        "seed_strategy_specs": "将确认本地策略规格模板。",
        "run_backtests": "将运行本地批量回测。",
        "rank_backtests": "将对本地回测结果排序评分。",
        "allocate_portfolio": "将生成研究组合权重草案。",
        "generate_draft_signals": "将生成执行信号草案，但不会审批或交易。",
        "calculate_event_reactions": "将基于本地行情计算事件后 T+1/T+5/T+20/T+60 表现。",
    }[step]


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key, value in result.items():
        if key in LARGE_RESULT_KEYS:
            if isinstance(value, list):
                metrics[f"{key}_count"] = len(value)
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            metrics[key] = value
        elif isinstance(value, list):
            metrics[f"{key}_count"] = len(value)
        elif isinstance(value, dict) and _is_small_metric_dict(value):
            metrics[key] = value
    return metrics


def _is_small_metric_dict(value: dict[str, Any]) -> bool:
    if len(value) > 8:
        return False
    return all(isinstance(item, (str, int, float, bool)) or item is None for item in value.values())
