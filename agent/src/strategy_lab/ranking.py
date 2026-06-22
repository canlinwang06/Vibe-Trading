"""Strategy ranking service for local A-share backtest results."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from typing import Any

from src.ashare_data.store import AShareDataStore


class StrategyRankingError(RuntimeError):
    """Raised when local backtest rankings cannot be produced."""


def _parse_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round(value: float, digits: int = 2) -> float:
    return round(max(0.0, min(100.0, value)), digits)


def _score_range(value: float, low: float, high: float, *, reverse: bool = False) -> float:
    if high <= low:
        return 0.0
    score = (value - low) / (high - low) * 100
    score = max(0.0, min(100.0, score))
    return 100.0 - score if reverse else score


def _row_to_candidate(row: tuple[Any, ...]) -> dict[str, Any]:
    start = _to_date(row[3])
    end = _to_date(row[4])
    sample_days = (end - start).days + 1 if start and end and end >= start else 0
    return {
        "run_id": row[0],
        "strategy_id": row[1],
        "strategy_name": row[2] or row[1],
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "sample_days": sample_days,
        "market": row[5],
        "benchmark": row[6],
        "total_return": _float(row[7]),
        "annual_return": _float(row[8]),
        "max_drawdown": _float(row[9]),
        "sharpe": _float(row[10]),
        "sortino": _float(row[11]),
        "calmar": _float(row[12]),
        "win_rate": _float(row[13]),
        "profit_loss_ratio": _float(row[14]),
        "turnover": _float(row[15]),
        "trade_count": int(row[16] or 0),
        "avg_holding_days": _float(row[17]),
        "excess_return": _float(row[18]),
        "information_ratio": _float(row[19]),
        "status": row[20],
        "artifacts_path": row[21],
        "created_at": row[22].isoformat() if row[22] else None,
        "strategy_type": row[23] or "unknown",
        "params": _parse_json(row[24]),
        "rebalance_freq": row[25],
        "holding_period": int(row[26] or 0),
    }


class StrategyRankingService:
    """Score completed strategy backtests without external APIs or live trading."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def list_rankings(
        self,
        *,
        limit: int = 50,
        status: str = "completed",
        strategy_type: str | None = None,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 500)
        rows = self._load_runs(status=status, strategy_type=strategy_type)
        if not rows:
            raise StrategyRankingError("没有可排名的回测结果，请先运行批量回测。")

        type_counts = Counter(row["strategy_type"] for row in rows)
        ranked = [self._score_run(row, type_counts=type_counts) for row in rows]
        if min_score is not None:
            ranked = [row for row in ranked if row["strategy_score"] >= float(min_score)]
        ranked.sort(
            key=lambda row: (
                -row["strategy_score"],
                row["risk_score"],
                -row["total_return"],
                row["strategy_id"],
            )
        )
        for idx, row in enumerate(ranked, start=1):
            row["rank"] = idx
        return ranked[:capped_limit]

    def top_summary(self, *, limit: int = 5) -> dict[str, Any]:
        rankings = self.list_rankings(limit=limit)
        return {
            "top_strategies": rankings,
            "ranking_count": len(rankings),
            "research_only": True,
            "live_trading": False,
            "scoring_model": self.scoring_model(),
        }

    @staticmethod
    def scoring_model() -> dict[str, Any]:
        return {
            "version": "pr-12-local-backtest-ranking-v1",
            "weights": {
                "recent_return": 0.20,
                "medium_stability": 0.20,
                "drawdown_control": 0.20,
                "risk_adjusted_return": 0.15,
                "correlation_control": 0.10,
                "turnover_control": 0.05,
                "sample_stability": 0.10,
            },
            "notes": [
                "仅基于本地 backtest_runs 与 strategy_specs 计算。",
                "相关性控制在 PR-12 使用策略类型拥挤度近似。",
                "真实组合相关性留给组合风控 PR。",
                "输出只用于研究、模拟和回测验收，不代表实盘交易指令。",
            ],
        }

    def _load_runs(self, *, status: str, strategy_type: str | None) -> list[dict[str, Any]]:
        filters = ["br.status = ?"]
        params: list[Any] = [status.strip() or "completed"]
        if strategy_type:
            filters.append("ss.strategy_type = ?")
            params.append(strategy_type.strip())
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT
                  br.run_id, br.strategy_id, ss.strategy_name,
                  br.start_date, br.end_date, br.market, br.benchmark,
                  br.total_return, br.annual_return, br.max_drawdown,
                  br.sharpe, br.sortino, br.calmar, br.win_rate,
                  br.profit_loss_ratio, br.turnover, br.trade_count,
                  br.avg_holding_days, br.excess_return, br.information_ratio,
                  br.status, br.artifacts_path, br.created_at,
                  ss.strategy_type, ss.params_json, ss.rebalance_freq,
                  ss.holding_period
                FROM backtest_runs br
                LEFT JOIN strategy_specs ss ON ss.strategy_id = br.strategy_id
                WHERE {' AND '.join(filters)}
                ORDER BY br.created_at DESC, br.sharpe DESC, br.total_return DESC
                """,
                params,
            ).fetchall()
        return [_row_to_candidate(row) for row in rows]

    def _score_run(self, row: dict[str, Any], *, type_counts: Counter[str]) -> dict[str, Any]:
        components = self._component_scores(row, type_counts=type_counts)
        weights = self.scoring_model()["weights"]
        score = sum(components[key] * weight * 100 for key, weight in weights.items())
        risk_score = self._risk_score(row)
        recommendation = self._recommendation(score, risk_score)
        return {
            **row,
            "strategy_score": round(score, 2),
            "risk_score": risk_score,
            "score_components": {key: _round(value * 100) for key, value in components.items()},
            "recommendation": recommendation,
            "reason": self._reason(row, recommendation),
            "research_only": True,
            "live_trading": False,
        }

    def _component_scores(self, row: dict[str, Any], *, type_counts: Counter[str]) -> dict[str, float]:
        recent_return = _score_range(row["total_return"], -0.08, 0.25) / 100
        win_rate_score = _score_range(row["win_rate"], 0.35, 0.65) / 100
        payoff_score = _score_range(row["profit_loss_ratio"], 0.8, 2.0) / 100
        medium_stability = win_rate_score * 0.65 + payoff_score * 0.35
        drawdown_control = _score_range(abs(row["max_drawdown"]), 0.02, 0.35, reverse=True) / 100
        sharpe_score = _score_range(row["sharpe"], -0.5, 2.5) / 100
        calmar_score = _score_range(row["calmar"], -0.5, 3.0) / 100
        risk_adjusted_return = sharpe_score * 0.6 + calmar_score * 0.4
        same_type_count = max(type_counts.get(row["strategy_type"], 1), 1)
        correlation_control = max(0.55, 1.0 - min(same_type_count - 1, 5) * 0.07)
        turnover_control = _score_range(row["turnover"], 0.5, 2.0, reverse=True) / 100
        days_score = _score_range(row["sample_days"], 60, 500) / 100
        trade_score = _score_range(row["trade_count"], 4, 40) / 100
        sample_stability = days_score * 0.55 + trade_score * 0.45
        return {
            "recent_return": recent_return,
            "medium_stability": medium_stability,
            "drawdown_control": drawdown_control,
            "risk_adjusted_return": risk_adjusted_return,
            "correlation_control": correlation_control,
            "turnover_control": turnover_control,
            "sample_stability": sample_stability,
        }

    @staticmethod
    def _risk_score(row: dict[str, Any]) -> float:
        drawdown_risk = _score_range(abs(row["max_drawdown"]), 0.02, 0.35)
        turnover_risk = _score_range(row["turnover"], 0.5, 2.0)
        loss_risk = _score_range(-row["total_return"], 0.0, 0.2)
        sample_risk = _score_range(row["sample_days"], 60, 500, reverse=True)
        return _round(drawdown_risk * 0.45 + turnover_risk * 0.25 + loss_risk * 0.20 + sample_risk * 0.10)

    @staticmethod
    def _recommendation(score: float, risk_score: float) -> str:
        if score >= 80 and risk_score <= 35:
            return "优先观察"
        if score >= 65 and risk_score <= 55:
            return "小仓验证"
        if score >= 50:
            return "继续跟踪"
        return "暂不纳入"

    @staticmethod
    def _reason(row: dict[str, Any], recommendation: str) -> str:
        return (
            f"{recommendation}: 收益 {row['total_return']:.2%}, "
            f"最大回撤 {row['max_drawdown']:.2%}, "
            f"Sharpe {row['sharpe']:.2f}, 换手率 {row['turnover']:.2f}。"
        )
