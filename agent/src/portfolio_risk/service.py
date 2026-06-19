"""Research-only portfolio allocation for ranked A-share strategies."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.ashare_data.store import AShareDataStore
from src.strategy_lab.ranking import StrategyRankingError, StrategyRankingService


class PortfolioRiskError(RuntimeError):
    """Raised when portfolio-risk allocation cannot be produced."""


@dataclass(frozen=True)
class AllocationCandidate:
    strategy_id: str
    strategy_name: str
    strategy_type: str
    strategy_score: float
    risk_score: float
    volatility: float
    correlation_penalty: float
    raw_priority: float
    recommendation: str
    reason: str
    run_id: str
    artifacts_path: str | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None, *, field_name: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError as exc:
        raise PortfolioRiskError(f"{field_name} 日期格式无效: {value}") from exc


def _row_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    return datetime.fromisoformat(str(value)).date()


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round_weight(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(max(0.0, value), 6)


class PortfolioRiskService:
    """Allocate strategy capital from local rankings without creating execution signals."""

    REGIME_BASE_EXPOSURE = {
        "strong_trend": 0.80,
        "normal": 0.55,
        "weak": 0.25,
        "extreme_risk": 0.10,
    }

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def allocate(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        as_of_date: str | date | datetime | None = None,
        top_n: int = 5,
        market_regime: str = "normal",
        current_drawdown: float = 0.0,
        signal_confidence: float = 1.0,
        max_strategy_weight: float = 0.30,
        min_strategy_weight: float = 0.05,
        max_strategy_type_weight: float = 0.50,
        min_strategy_score: float = 0.0,
    ) -> dict[str, Any]:
        self.store.initialize()
        as_of = self._resolve_as_of(as_of_date)
        model_exposure = self._target_exposure(
            market_regime=market_regime,
            current_drawdown=current_drawdown,
            signal_confidence=signal_confidence,
        )
        if model_exposure <= 0:
            self._clear_allocations(as_of=as_of, portfolio_id=portfolio_id)
            return {
                "status": "risk_off",
                "portfolio_id": portfolio_id,
                "as_of_date": as_of.isoformat(),
                "market_regime": market_regime,
                "model_total_exposure": 0.0,
                "allocated_exposure": 0.0,
                "cash_weight": 1.0,
                "allocation_count": 0,
                "strategy_allocations": [],
                "constraints": {
                    "max_strategy_weight": max_strategy_weight,
                    "min_strategy_weight": min_strategy_weight,
                    "max_strategy_type_weight": max_strategy_type_weight,
                    "constraints_first": True,
                },
                "risk_rules": self._drawdown_rules(current_drawdown),
                "requires_human_confirmation": True,
                "research_only": True,
                "live_trading": False,
            }
        selected_count = self._effective_top_n(
            top_n=top_n,
            target_exposure=model_exposure,
            min_strategy_weight=min_strategy_weight,
        )
        candidates = self._ranked_candidates(
            limit=max(selected_count * 4, 20),
            min_strategy_score=min_strategy_score,
        )
        selected = self._select_diverse(candidates, top_n=selected_count)
        if not selected:
            raise PortfolioRiskError("没有可分配的策略，请先完成策略回测和排名。")

        weights = self._capital_weights(
            selected,
            target_exposure=model_exposure,
            max_strategy_weight=max_strategy_weight,
            min_strategy_weight=min_strategy_weight,
            max_strategy_type_weight=max_strategy_type_weight,
        )
        allocations = self._write_allocations(
            as_of=as_of,
            portfolio_id=portfolio_id,
            selected=selected,
            weights=weights,
        )
        allocated_exposure = round(sum(row["allocated_weight"] for row in allocations), 6)
        return {
            "status": "draft",
            "portfolio_id": portfolio_id,
            "as_of_date": as_of.isoformat(),
            "market_regime": market_regime,
            "model_total_exposure": round(model_exposure, 6),
            "allocated_exposure": allocated_exposure,
            "cash_weight": round(max(0.0, 1.0 - allocated_exposure), 6),
            "allocation_count": len(allocations),
            "strategy_allocations": allocations,
            "constraints": {
                "max_strategy_weight": max_strategy_weight,
                "min_strategy_weight": min_strategy_weight,
                "max_strategy_type_weight": max_strategy_type_weight,
                "constraints_first": True,
            },
            "risk_rules": self._drawdown_rules(current_drawdown),
            "requires_human_confirmation": True,
            "research_only": True,
            "live_trading": False,
        }

    def list_allocations(
        self,
        *,
        portfolio_id: str | None = None,
        as_of_date: str | date | datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 500)
        filters: list[str] = []
        params: list[Any] = []
        if portfolio_id:
            filters.append("sa.portfolio_id = ?")
            params.append(portfolio_id.strip())
        parsed_as_of = _parse_date(as_of_date, field_name="as_of_date")
        if parsed_as_of:
            filters.append("sa.as_of_date = ?")
            params.append(parsed_as_of)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT sa.as_of_date, sa.portfolio_id, sa.strategy_id,
                       sa.strategy_score, sa.risk_score, sa.volatility,
                       sa.correlation_penalty, sa.allocated_weight,
                       sa.reason, sa.created_at, ss.strategy_name,
                       ss.strategy_type
                FROM strategy_allocations sa
                LEFT JOIN strategy_specs ss ON ss.strategy_id = sa.strategy_id
                {where}
                ORDER BY sa.as_of_date DESC, sa.portfolio_id,
                         sa.allocated_weight DESC, sa.strategy_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_allocation(row) for row in rows]

    def trade_plan(
        self,
        *,
        portfolio_id: str = "cn_a_main",
        as_of_date: str | date | datetime | None = None,
        max_single_stock_weight: float = 0.12,
        max_sector_weight: float = 0.40,
    ) -> dict[str, Any]:
        self.store.initialize()
        as_of = self._resolve_allocation_date(portfolio_id=portfolio_id, as_of_date=as_of_date)
        allocations = self.list_allocations(portfolio_id=portfolio_id, as_of_date=as_of, limit=100)
        if not allocations:
            raise PortfolioRiskError("没有策略分配结果，请先运行组合风控分配。")

        target_positions = self._target_positions(
            allocations,
            max_single_stock_weight=max_single_stock_weight,
            max_sector_weight=max_sector_weight,
        )
        allocated_exposure = round(sum(row["allocated_weight"] for row in allocations), 6)
        position_exposure = round(sum(row["target_weight"] for row in target_positions), 6)
        return {
            "status": "draft",
            "portfolio_id": portfolio_id,
            "as_of_date": as_of.isoformat(),
            "target_total_exposure": position_exposure,
            "strategy_allocated_exposure": allocated_exposure,
            "cash_weight": round(max(0.0, 1.0 - position_exposure), 6),
            "strategy_allocations": allocations,
            "target_positions": target_positions,
            "risk_limits": {
                "max_single_stock_weight": max_single_stock_weight,
                "max_sector_weight": max_sector_weight,
            },
            "requires_human_confirmation": True,
            "approval_status": "not_supported_in_pr_13",
            "research_only": True,
            "live_trading": False,
        }

    def _ranked_candidates(self, *, limit: int, min_strategy_score: float) -> list[AllocationCandidate]:
        try:
            rankings = StrategyRankingService(store=self.store).list_rankings(
                limit=limit,
                min_score=min_strategy_score,
            )
        except StrategyRankingError as exc:
            raise PortfolioRiskError("没有可分配的策略，请先完成策略回测和排名。") from exc
        return [self._ranking_to_candidate(row) for row in rankings]

    def _resolve_as_of(self, as_of_date: str | date | datetime | None) -> date:
        parsed = _parse_date(as_of_date, field_name="as_of_date")
        if parsed:
            return parsed
        with self.store.connect(read_only=True) as conn:
            row = conn.execute("SELECT MAX(end_date) FROM backtest_runs WHERE status = 'completed'").fetchone()
        latest = _row_date(row[0]) if row and row[0] else None
        if latest is None:
            raise PortfolioRiskError("没有可分配的回测结果，请先运行批量回测。")
        return latest

    def _resolve_allocation_date(
        self,
        *,
        portfolio_id: str,
        as_of_date: str | date | datetime | None,
    ) -> date:
        parsed = _parse_date(as_of_date, field_name="as_of_date")
        if parsed:
            return parsed
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                "SELECT MAX(as_of_date) FROM strategy_allocations WHERE portfolio_id = ?",
                [portfolio_id],
            ).fetchone()
        latest = _row_date(row[0]) if row and row[0] else None
        if latest is None:
            raise PortfolioRiskError("没有策略分配结果，请先运行组合风控分配。")
        return latest

    @staticmethod
    def _ranking_to_candidate(row: dict[str, Any]) -> AllocationCandidate:
        drawdown = abs(_float(row.get("max_drawdown")))
        turnover_vol = _float(row.get("turnover")) * 0.04
        risk_vol = _float(row.get("risk_score")) / 400
        volatility = max(0.05, drawdown, turnover_vol, risk_vol)
        correlation_component = _float(row.get("score_components", {}).get("correlation_control"), 100)
        correlation_penalty = _clamp((100 - correlation_component) / 100, 0.0, 1.0)
        raw_priority = _float(row.get("strategy_score")) / volatility
        return AllocationCandidate(
            strategy_id=row["strategy_id"],
            strategy_name=row.get("strategy_name") or row["strategy_id"],
            strategy_type=row.get("strategy_type") or "unknown",
            strategy_score=_float(row.get("strategy_score")),
            risk_score=_float(row.get("risk_score")),
            volatility=round(volatility, 6),
            correlation_penalty=round(correlation_penalty, 6),
            raw_priority=raw_priority,
            recommendation=row.get("recommendation") or "继续跟踪",
            reason=row.get("reason") or "",
            run_id=row.get("run_id") or "",
            artifacts_path=row.get("artifacts_path"),
        )

    @classmethod
    def _target_exposure(
        cls,
        *,
        market_regime: str,
        current_drawdown: float,
        signal_confidence: float,
    ) -> float:
        base = cls.REGIME_BASE_EXPOSURE.get(market_regime, cls.REGIME_BASE_EXPOSURE["normal"])
        drawdown = abs(current_drawdown)
        if drawdown >= 0.10:
            drawdown_multiplier = 0.0
        elif drawdown >= 0.08:
            drawdown_multiplier = 0.25
        elif drawdown >= 0.05:
            drawdown_multiplier = 0.50
        elif drawdown >= 0.03:
            drawdown_multiplier = 0.80
        else:
            drawdown_multiplier = 1.0
        confidence_multiplier = _clamp(signal_confidence, 0.30, 1.00)
        return round(base * drawdown_multiplier * confidence_multiplier, 6)

    @staticmethod
    def _effective_top_n(*, top_n: int, target_exposure: float, min_strategy_weight: float) -> int:
        requested = min(max(int(top_n), 3), 5)
        if target_exposure <= 0:
            return 0
        if min_strategy_weight <= 0:
            return requested
        affordable = max(1, int(target_exposure // min_strategy_weight))
        return max(1, min(requested, affordable))

    @staticmethod
    def _select_diverse(candidates: list[AllocationCandidate], *, top_n: int) -> list[AllocationCandidate]:
        selected: list[AllocationCandidate] = []
        type_counts: defaultdict[str, int] = defaultdict(int)
        for candidate in candidates:
            if len(selected) >= top_n:
                break
            if type_counts[candidate.strategy_type] >= 2:
                continue
            selected.append(candidate)
            type_counts[candidate.strategy_type] += 1
        if len(selected) < top_n:
            selected_ids = {candidate.strategy_id for candidate in selected}
            for candidate in candidates:
                if len(selected) >= top_n:
                    break
                if candidate.strategy_id not in selected_ids:
                    selected.append(candidate)
        return selected

    def _capital_weights(
        self,
        selected: list[AllocationCandidate],
        *,
        target_exposure: float,
        max_strategy_weight: float,
        min_strategy_weight: float,
        max_strategy_type_weight: float,
    ) -> dict[str, float]:
        if target_exposure <= 0:
            return {candidate.strategy_id: 0.0 for candidate in selected}
        raw_total = sum(max(candidate.raw_priority, 0.0) for candidate in selected)
        if raw_total <= 0:
            equal = target_exposure / len(selected)
            weights = {candidate.strategy_id: equal for candidate in selected}
        else:
            weights = {
                candidate.strategy_id: target_exposure * max(candidate.raw_priority, 0.0) / raw_total
                for candidate in selected
            }
        return self._apply_caps(
            selected,
            weights,
            target_exposure=target_exposure,
            max_strategy_weight=max_strategy_weight,
            min_strategy_weight=min_strategy_weight,
            max_strategy_type_weight=max_strategy_type_weight,
        )

    def _apply_caps(
        self,
        selected: list[AllocationCandidate],
        weights: dict[str, float],
        *,
        target_exposure: float,
        max_strategy_weight: float,
        min_strategy_weight: float,
        max_strategy_type_weight: float,
    ) -> dict[str, float]:
        weights = self._cap_strategy_and_type(selected, weights, max_strategy_weight, max_strategy_type_weight)
        if target_exposure >= len(selected) * min_strategy_weight:
            weights = self._lift_min_weights(selected, weights, min_strategy_weight, target_exposure)
        for _ in range(8):
            current = sum(weights.values())
            shortfall = target_exposure - current
            if shortfall <= 0.000001:
                break
            weights = self._redistribute_shortfall(
                selected,
                weights,
                shortfall=shortfall,
                max_strategy_weight=max_strategy_weight,
                max_strategy_type_weight=max_strategy_type_weight,
            )
        return {strategy_id: _round_weight(weight) for strategy_id, weight in weights.items()}

    @staticmethod
    def _cap_strategy_and_type(
        selected: list[AllocationCandidate],
        weights: dict[str, float],
        max_strategy_weight: float,
        max_strategy_type_weight: float,
    ) -> dict[str, float]:
        capped = dict(weights)
        for candidate in selected:
            capped[candidate.strategy_id] = min(capped[candidate.strategy_id], max_strategy_weight)
        type_totals: defaultdict[str, float] = defaultdict(float)
        for candidate in selected:
            type_totals[candidate.strategy_type] += capped[candidate.strategy_id]
        for strategy_type, total in type_totals.items():
            if total <= max_strategy_type_weight or total <= 0:
                continue
            scale = max_strategy_type_weight / total
            for candidate in selected:
                if candidate.strategy_type == strategy_type:
                    capped[candidate.strategy_id] *= scale
        return capped

    @staticmethod
    def _lift_min_weights(
        selected: list[AllocationCandidate],
        weights: dict[str, float],
        min_strategy_weight: float,
        target_exposure: float,
    ) -> dict[str, float]:
        lifted = dict(weights)
        needed = sum(max(0.0, min_strategy_weight - lifted[candidate.strategy_id]) for candidate in selected)
        donors = [
            candidate
            for candidate in selected
            if lifted[candidate.strategy_id] > min_strategy_weight
        ]
        donor_capacity = sum(lifted[candidate.strategy_id] - min_strategy_weight for candidate in donors)
        if needed <= 0 or donor_capacity <= 0 or sum(lifted.values()) > target_exposure + 0.000001:
            return lifted
        for candidate in selected:
            if lifted[candidate.strategy_id] < min_strategy_weight:
                lifted[candidate.strategy_id] = min_strategy_weight
        for candidate in donors:
            reduction = needed * (lifted[candidate.strategy_id] - min_strategy_weight) / donor_capacity
            lifted[candidate.strategy_id] = max(min_strategy_weight, lifted[candidate.strategy_id] - reduction)
        return lifted

    @staticmethod
    def _redistribute_shortfall(
        selected: list[AllocationCandidate],
        weights: dict[str, float],
        *,
        shortfall: float,
        max_strategy_weight: float,
        max_strategy_type_weight: float,
    ) -> dict[str, float]:
        updated = dict(weights)
        type_totals: defaultdict[str, float] = defaultdict(float)
        for candidate in selected:
            type_totals[candidate.strategy_type] += updated[candidate.strategy_id]
        capacities: dict[str, float] = {}
        for candidate in selected:
            type_room = max(0.0, max_strategy_type_weight - type_totals[candidate.strategy_type])
            strategy_room = max(0.0, max_strategy_weight - updated[candidate.strategy_id])
            capacities[candidate.strategy_id] = min(type_room, strategy_room)
        total_capacity = sum(capacities.values())
        if total_capacity <= 0:
            return updated
        for candidate in selected:
            addition = shortfall * capacities[candidate.strategy_id] / total_capacity
            updated[candidate.strategy_id] += min(addition, capacities[candidate.strategy_id])
        return updated

    def _write_allocations(
        self,
        *,
        as_of: date,
        portfolio_id: str,
        selected: list[AllocationCandidate],
        weights: dict[str, float],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        with self.store.connect() as conn:
            conn.execute(
                "DELETE FROM strategy_allocations WHERE as_of_date = ? AND portfolio_id = ?",
                [as_of, portfolio_id],
            )
            for candidate in selected:
                weight = weights.get(candidate.strategy_id, 0.0)
                if weight <= 0:
                    continue
                conn.execute(
                    """
                    INSERT INTO strategy_allocations (
                      as_of_date, portfolio_id, strategy_id, strategy_score,
                      risk_score, volatility, correlation_penalty,
                      allocated_weight, reason, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        as_of,
                        portfolio_id,
                        candidate.strategy_id,
                        candidate.strategy_score,
                        candidate.risk_score,
                        candidate.volatility,
                        candidate.correlation_penalty,
                        weight,
                        self._allocation_reason(candidate, weight),
                        now,
                    ],
                )
        return self.list_allocations(portfolio_id=portfolio_id, as_of_date=as_of, limit=100)

    def _clear_allocations(self, *, as_of: date, portfolio_id: str) -> None:
        with self.store.connect() as conn:
            conn.execute(
                "DELETE FROM strategy_allocations WHERE as_of_date = ? AND portfolio_id = ?",
                [as_of, portfolio_id],
            )

    @staticmethod
    def _allocation_reason(candidate: AllocationCandidate, weight: float) -> str:
        return (
            f"{candidate.recommendation}: strategy_score={candidate.strategy_score:.2f}, "
            f"risk_score={candidate.risk_score:.2f}, volatility={candidate.volatility:.4f}, "
            f"allocated_weight={weight:.2%}。"
        )

    @staticmethod
    def _row_to_allocation(row: tuple[Any, ...]) -> dict[str, Any]:
        as_of = _row_date(row[0])
        return {
            "as_of_date": as_of.isoformat() if as_of else None,
            "portfolio_id": row[1],
            "strategy_id": row[2],
            "strategy_score": _float(row[3]),
            "risk_score": _float(row[4]),
            "volatility": _float(row[5]),
            "correlation_penalty": _float(row[6]),
            "allocated_weight": _float(row[7]),
            "reason": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
            "strategy_name": row[10] or row[2],
            "strategy_type": row[11] or "unknown",
        }

    @staticmethod
    def _drawdown_rules(current_drawdown: float) -> list[dict[str, Any]]:
        drawdown = abs(current_drawdown)
        rules = [
            {"threshold": -0.03, "action": "降低新开仓", "triggered": drawdown >= 0.03},
            {"threshold": -0.05, "action": "总仓位降到 50% 以下", "triggered": drawdown >= 0.05},
            {"threshold": -0.08, "action": "停止进攻策略，只保留防守策略", "triggered": drawdown >= 0.08},
            {"threshold": -0.10, "action": "停止交易，进入复盘模式", "triggered": drawdown >= 0.10},
        ]
        return rules

    def _target_positions(
        self,
        allocations: list[dict[str, Any]],
        *,
        max_single_stock_weight: float,
        max_sector_weight: float,
    ) -> list[dict[str, Any]]:
        metadata = self._candidate_metadata()
        position_weights: defaultdict[str, float] = defaultdict(float)
        position_sources: defaultdict[str, list[str]] = defaultdict(list)
        for allocation in allocations:
            universe = self._strategy_universe(allocation["strategy_id"])
            if not universe:
                universe = list(metadata)[:5]
            if not universe:
                continue
            per_stock_weight = allocation["allocated_weight"] / len(universe)
            for ticker in universe:
                position_weights[ticker] += per_stock_weight
                position_sources[ticker].append(allocation["strategy_id"])

        capped = {ticker: min(weight, max_single_stock_weight) for ticker, weight in position_weights.items()}
        sector_totals: defaultdict[str, float] = defaultdict(float)
        for ticker, weight in capped.items():
            sector = metadata.get(ticker, {}).get("sector_id") or "unknown"
            sector_totals[sector] += weight
        for sector, total in sector_totals.items():
            if total <= max_sector_weight or total <= 0:
                continue
            scale = max_sector_weight / total
            for ticker in list(capped):
                ticker_sector = metadata.get(ticker, {}).get("sector_id") or "unknown"
                if ticker_sector == sector:
                    capped[ticker] *= scale

        rows = []
        for ticker, weight in sorted(capped.items(), key=lambda item: (-item[1], item[0])):
            if weight <= 0:
                continue
            info = metadata.get(ticker, {})
            rows.append(
                {
                    "ticker": ticker,
                    "ticker_name": info.get("ticker_name") or ticker,
                    "target_weight": _round_weight(weight),
                    "current_weight": 0.0,
                    "action": "draft_target",
                    "strategy_sources": sorted(set(position_sources[ticker])),
                    "theme": info.get("theme"),
                    "sector_id": info.get("sector_id"),
                    "sector_name": info.get("sector_name"),
                    "reason": "由策略权重和候选股票池合成的草案目标权重。",
                    "risk": "研究草案，未审批，不能作为实盘指令。",
                }
            )
        return rows

    def _candidate_metadata(self) -> dict[str, dict[str, Any]]:
        with self.store.connect(read_only=True) as conn:
            latest = conn.execute("SELECT MAX(as_of_date) FROM candidate_pool").fetchone()
            as_of = _row_date(latest[0]) if latest and latest[0] else None
            if as_of is None:
                return {}
            rows = conn.execute(
                """
                SELECT ticker, ticker_name, sector_id, sector_name, theme
                FROM candidate_pool
                WHERE as_of_date = ? AND included = true
                ORDER BY stock_score DESC, ticker
                """,
                [as_of],
            ).fetchall()
        return {
            row[0]: {
                "ticker_name": row[1],
                "sector_id": row[2],
                "sector_name": row[3],
                "theme": row[4],
            }
            for row in rows
        }

    def _strategy_universe(self, strategy_id: str) -> list[str]:
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT artifacts_path
                FROM backtest_runs
                WHERE strategy_id = ? AND status = 'completed'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [strategy_id],
            ).fetchone()
        if row is None or not row[0]:
            return []
        path = Path(str(row[0])) / "run.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        universe = payload.get("universe")
        if not isinstance(universe, list):
            return []
        return [str(ticker) for ticker in universe if ticker]
