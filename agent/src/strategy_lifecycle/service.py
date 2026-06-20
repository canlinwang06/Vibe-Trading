"""Lifecycle scoring for strategy ideas, backtests, and JoinQuant tasks."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore


class StrategyLifecycleError(RuntimeError):
    """Raised when lifecycle summaries cannot be calculated."""


STATE_ORDER = (
    "idea",
    "candidate",
    "backtesting",
    "backtested",
    "qualified",
    "paper_trading",
    "paused",
    "rejected",
    "retired",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _event_id(strategy_id: str, to_state: str, reason: str) -> str:
    digest = hashlib.sha256(f"{strategy_id}|{to_state}|{reason}".encode("utf-8")).hexdigest()[:16]
    return f"lifeevt_{digest}"


class StrategyLifecycleService:
    """Build and persist strategy lifecycle overview rows."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def overview(self, *, refresh: bool = True, limit: int = 50) -> dict[str, Any]:
        self.store.initialize()
        if refresh:
            self.refresh_lifecycle()
        rows = self.list_lifecycle(limit=limit)
        if not rows:
            rows = _sample_lifecycle_rows()
        events = self.list_events(limit=100)
        if not events:
            events = _sample_lifecycle_events()
        funnel = _funnel(rows)
        return {
            "status": "ok",
            "data_mode": "sample" if rows and rows[0].get("strategy_id") == "sample_ai_momentum" else "local",
            "funnel": funnel,
            "health_distribution": _health_distribution(rows),
            "strategies": rows,
            "events": events,
            "recommendations": _recommendations(rows),
            "research_only": True,
            "live_trading": False,
        }

    def refresh_lifecycle(self) -> list[dict[str, Any]]:
        self.store.initialize()
        now = _utc_now()
        with self.store.connect() as conn:
            idea_rows = conn.execute(
                """
                SELECT idea_id, as_of_date, theme, strategy_name, strategy_type,
                       idea_score, status, thesis, created_at, updated_at
                FROM strategy_ideas
                ORDER BY as_of_date DESC, idea_score DESC
                """
            ).fetchall()
            spec_rows = conn.execute(
                """
                SELECT strategy_id, strategy_name, strategy_type, params_json,
                       enabled, created_at, updated_at
                FROM strategy_specs
                ORDER BY updated_at DESC
                """
            ).fetchall()
            backtest_rows = conn.execute(
                """
                SELECT strategy_id, COUNT(*), MAX(annual_return), MIN(max_drawdown),
                       AVG(sharpe), AVG(win_rate), MAX(created_at)
                FROM backtest_runs
                WHERE market = 'CN_A'
                GROUP BY strategy_id
                """
            ).fetchall()
            task_rows = conn.execute(
                """
                SELECT source_strategy_id, source_idea_id, status, COUNT(*), MAX(updated_at)
                FROM jq_orchestration_tasks
                GROUP BY source_strategy_id, source_idea_id, status
                """
            ).fetchall()

            backtests = {row[0]: row for row in backtest_rows if row[0]}
            task_statuses = _task_statuses(task_rows)
            rows = []
            for idea in idea_rows:
                strategy_id = _strategy_id_for_idea(idea[0], spec_rows)
                rows.append(self._build_lifecycle_row_from_idea(idea, strategy_id, backtests.get(strategy_id), task_statuses, now))
            for spec in spec_rows:
                strategy_id = spec[0]
                if any(row["strategy_id"] == strategy_id for row in rows):
                    continue
                rows.append(self._build_lifecycle_row_from_spec(spec, backtests.get(strategy_id), task_statuses, now))

            for row in rows:
                self._upsert_lifecycle(conn, row)
                self._ensure_event(conn, row)
        return rows

    def list_lifecycle(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT strategy_id, idea_id, strategy_name, theme, lifecycle_state,
                       health_score, recommendation, reason, first_seen_date,
                       last_review_date, paper_days, signal_count, backtest_count,
                       best_annual_return, worst_max_drawdown, avg_sharpe, win_rate,
                       evidence_json, research_only, live_trading, created_at, updated_at
                FROM strategy_lifecycle
                ORDER BY health_score DESC, updated_at DESC
                LIMIT ?
                """,
                [min(max(int(limit), 1), 200)],
            ).fetchall()
        return [_row_to_lifecycle(row) for row in rows]

    def list_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT event_id, strategy_id, event_time, from_state, to_state,
                       reason, evidence_json, created_by, research_only, live_trading
                FROM strategy_lifecycle_events
                ORDER BY event_time DESC
                LIMIT ?
                """,
                [min(max(int(limit), 1), 500)],
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    @staticmethod
    def _build_lifecycle_row_from_idea(
        idea: tuple[Any, ...],
        strategy_id: str,
        backtest: tuple[Any, ...] | None,
        task_statuses: dict[str, Counter[str]],
        now: datetime,
    ) -> dict[str, Any]:
        idea_id, as_of_date, theme, strategy_name, strategy_type, idea_score, status, thesis, created_at, updated_at = idea
        state = _state_for(status=status, backtest=backtest, task_counter=task_statuses.get(strategy_id) or task_statuses.get(idea_id))
        health = _health_score(_float(idea_score) / 100, backtest, state)
        recommendation, reason = _recommendation(state, health, backtest, thesis)
        return {
            "strategy_id": strategy_id,
            "idea_id": idea_id,
            "strategy_name": strategy_name,
            "theme": theme,
            "lifecycle_state": state,
            "health_score": health,
            "recommendation": recommendation,
            "reason": reason,
            "first_seen_date": as_of_date,
            "last_review_date": now.date(),
            "paper_days": _paper_days(task_statuses.get(strategy_id) or task_statuses.get(idea_id)),
            "signal_count": 0,
            "backtest_count": int(backtest[1]) if backtest else 0,
            "best_annual_return": _float(backtest[2]) if backtest else None,
            "worst_max_drawdown": _float(backtest[3]) if backtest else None,
            "avg_sharpe": _float(backtest[4]) if backtest else None,
            "win_rate": _float(backtest[5]) if backtest else None,
            "evidence": {"idea_status": status, "strategy_type": strategy_type, "thesis": thesis},
            "research_only": True,
            "live_trading": False,
            "created_at": created_at or now,
            "updated_at": updated_at or now,
        }

    @staticmethod
    def _build_lifecycle_row_from_spec(
        spec: tuple[Any, ...],
        backtest: tuple[Any, ...] | None,
        task_statuses: dict[str, Counter[str]],
        now: datetime,
    ) -> dict[str, Any]:
        strategy_id, strategy_name, strategy_type, params_json, enabled, created_at, updated_at = spec
        params = _loads(params_json, {})
        task_counter = task_statuses.get(strategy_id)
        state = _state_for(status="saved_to_strategy_lab" if enabled else "paused", backtest=backtest, task_counter=task_counter)
        health = _health_score(0.62, backtest, state)
        recommendation, reason = _recommendation(state, health, backtest, strategy_name)
        return {
            "strategy_id": strategy_id,
            "idea_id": params.get("source_strategy_idea_id"),
            "strategy_name": strategy_name,
            "theme": params.get("theme") or "综合策略",
            "lifecycle_state": state,
            "health_score": health,
            "recommendation": recommendation,
            "reason": reason,
            "first_seen_date": created_at.date() if isinstance(created_at, datetime) else now.date(),
            "last_review_date": now.date(),
            "paper_days": _paper_days(task_counter),
            "signal_count": 0,
            "backtest_count": int(backtest[1]) if backtest else 0,
            "best_annual_return": _float(backtest[2]) if backtest else None,
            "worst_max_drawdown": _float(backtest[3]) if backtest else None,
            "avg_sharpe": _float(backtest[4]) if backtest else None,
            "win_rate": _float(backtest[5]) if backtest else None,
            "evidence": {"strategy_type": strategy_type, "enabled": bool(enabled), "params": params},
            "research_only": True,
            "live_trading": False,
            "created_at": created_at or now,
            "updated_at": updated_at or now,
        }

    @staticmethod
    def _upsert_lifecycle(conn: Any, row: dict[str, Any]) -> None:
        conn.execute("DELETE FROM strategy_lifecycle WHERE strategy_id = ?", [row["strategy_id"]])
        conn.execute(
            """
            INSERT INTO strategy_lifecycle (
              strategy_id, idea_id, strategy_name, theme, lifecycle_state,
              health_score, recommendation, reason, first_seen_date,
              last_review_date, paper_days, signal_count, backtest_count,
              best_annual_return, worst_max_drawdown, avg_sharpe, win_rate,
              evidence_json, research_only, live_trading, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["strategy_id"],
                row["idea_id"],
                row["strategy_name"],
                row["theme"],
                row["lifecycle_state"],
                row["health_score"],
                row["recommendation"],
                row["reason"],
                row["first_seen_date"],
                row["last_review_date"],
                row["paper_days"],
                row["signal_count"],
                row["backtest_count"],
                row["best_annual_return"],
                row["worst_max_drawdown"],
                row["avg_sharpe"],
                row["win_rate"],
                _json(row["evidence"]),
                row["research_only"],
                row["live_trading"],
                row["created_at"],
                row["updated_at"],
            ],
        )

    @staticmethod
    def _ensure_event(conn: Any, row: dict[str, Any]) -> None:
        event_id = _event_id(row["strategy_id"], row["lifecycle_state"], row["reason"])
        existing = conn.execute("SELECT event_id FROM strategy_lifecycle_events WHERE event_id = ?", [event_id]).fetchone()
        if existing:
            return
        conn.execute(
            """
            INSERT INTO strategy_lifecycle_events (
              event_id, strategy_id, event_time, from_state, to_state,
              reason, evidence_json, created_by, research_only, live_trading
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_id,
                row["strategy_id"],
                _utc_now(),
                None,
                row["lifecycle_state"],
                row["reason"],
                _json(row["evidence"]),
                "system",
                True,
                False,
            ],
        )


def _strategy_id_for_idea(idea_id: str, specs: list[tuple[Any, ...]]) -> str:
    for spec in specs:
        params = _loads(spec[3], {})
        if params.get("source_strategy_idea_id") == idea_id:
            return str(spec[0])
    return idea_id


def _task_statuses(rows: list[tuple[Any, ...]]) -> dict[str, Counter[str]]:
    statuses: dict[str, Counter[str]] = {}
    for strategy_id, idea_id, status, count, _updated_at in rows:
        for key in (strategy_id, idea_id):
            if key:
                statuses.setdefault(str(key), Counter())[str(status)] += int(count)
    return statuses


def _state_for(*, status: str | None, backtest: tuple[Any, ...] | None, task_counter: Counter[str] | None) -> str:
    task_counter = task_counter or Counter()
    if task_counter.get("running"):
        return "backtesting"
    if task_counter.get("completed"):
        return "paper_trading"
    if task_counter.get("failed"):
        return "paused"
    if backtest:
        annual = _float(backtest[2])
        drawdown = _float(backtest[3])
        sharpe = _float(backtest[4])
        if annual > 0.08 and drawdown > -0.18 and sharpe >= 1.0:
            return "qualified"
        return "backtested"
    if status == "saved_to_strategy_lab":
        return "candidate"
    if status in {"paused", "rejected", "retired"}:
        return status
    return "idea"


def _health_score(base: float, backtest: tuple[Any, ...] | None, state: str) -> float:
    score = base * 55
    if backtest:
        annual = _float(backtest[2])
        drawdown = abs(_float(backtest[3]))
        sharpe = _float(backtest[4])
        win_rate = _float(backtest[5])
        score += min(max(annual, -0.2), 0.5) * 35
        score += min(max(sharpe, 0), 2.5) * 10
        score += min(max(win_rate, 0), 0.8) * 10
        score -= min(max(drawdown, 0), 0.5) * 30
    if state in {"qualified", "paper_trading"}:
        score += 8
    if state in {"paused", "rejected", "retired"}:
        score -= 18
    return round(min(max(score, 0), 100), 1)


def _recommendation(state: str, health: float, backtest: tuple[Any, ...] | None, reason_source: str) -> tuple[str, str]:
    if state == "paper_trading":
        return "继续观察", "已进入模拟观察，继续跟踪执行偏差和回撤。"
    if state == "qualified" and health >= 70:
        return "小仓模拟", "回测质量达到候选标准，可进入小仓模拟观察。"
    if state == "backtested" and backtest:
        return "复测确认", "已有回测结果但稳定性不足，建议换窗口复测。"
    if state == "paused":
        return "暂停", "任务失败或风险条件触发，暂停新增回测。"
    if state == "candidate":
        return "送聚宽验证", "已保存策略规格，下一步适合创建聚宽任务。"
    return "继续生成证据", f"仍处于想法阶段，需要更多候选股票和规则证据：{str(reason_source)[:60]}"


def _paper_days(task_counter: Counter[str] | None) -> int:
    if not task_counter:
        return 0
    return int(task_counter.get("completed", 0)) * 5


def _row_to_lifecycle(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "strategy_id": row[0],
        "idea_id": row[1],
        "strategy_name": row[2],
        "theme": row[3],
        "lifecycle_state": row[4],
        "health_score": _float(row[5]),
        "recommendation": row[6],
        "reason": row[7],
        "first_seen_date": _iso(row[8]),
        "last_review_date": _iso(row[9]),
        "paper_days": int(row[10] or 0),
        "signal_count": int(row[11] or 0),
        "backtest_count": int(row[12] or 0),
        "best_annual_return": row[13],
        "worst_max_drawdown": row[14],
        "avg_sharpe": row[15],
        "win_rate": row[16],
        "evidence": _loads(row[17], {}),
        "research_only": bool(row[18]),
        "live_trading": bool(row[19]),
        "created_at": _iso(row[20]),
        "updated_at": _iso(row[21]),
    }


def _row_to_event(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "event_id": row[0],
        "strategy_id": row[1],
        "event_time": _iso(row[2]),
        "from_state": row[3],
        "to_state": row[4],
        "reason": row[5],
        "evidence": _loads(row[6], {}),
        "created_by": row[7],
        "research_only": bool(row[8]),
        "live_trading": bool(row[9]),
    }


def _funnel(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(row["lifecycle_state"] for row in rows)
    return [{"state": state, "label": _state_label(state), "count": counts.get(state, 0)} for state in STATE_ORDER]


def _health_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = [
        ("稳定观察", 70, 100),
        ("继续小样本", 55, 69.999),
        ("拥挤风险", 40, 54.999),
        ("建议暂停", 0, 39.999),
    ]
    return [
        {
            "label": label,
            "count": sum(1 for row in rows if low <= _float(row["health_score"]) <= high),
            "min_score": low,
            "max_score": high,
        }
        for label, low, high in buckets
    ]


def _recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=lambda row: (-_float(row["health_score"]), row["strategy_name"]))
    return [
        {
            "strategy_id": row["strategy_id"],
            "strategy_name": row["strategy_name"],
            "recommendation": row["recommendation"],
            "reason": row["reason"],
            "health_score": row["health_score"],
        }
        for row in ranked[:5]
    ]


def _state_label(state: str) -> str:
    return {
        "idea": "想法",
        "candidate": "候选",
        "backtesting": "回测中",
        "backtested": "已回测",
        "qualified": "合格",
        "paper_trading": "模拟盘",
        "paused": "暂停",
        "rejected": "淘汰",
        "retired": "退役",
    }.get(state, state)


def _sample_lifecycle_rows() -> list[dict[str, Any]]:
    now = _utc_now().isoformat()
    return [
        {"strategy_id": "sample_ai_momentum", "idea_id": "sample_hot_momentum", "strategy_name": "AI算力热点动量", "theme": "AI算力", "lifecycle_state": "paper_trading", "health_score": 78.0, "recommendation": "继续观察", "reason": "模拟盘观察第 3 周，仍需控制仓位。", "first_seen_date": "2026-06-02", "last_review_date": "2026-06-20", "paper_days": 15, "signal_count": 6, "backtest_count": 3, "best_annual_return": 0.186, "worst_max_drawdown": -0.098, "avg_sharpe": 1.42, "win_rate": 0.54, "evidence": {}, "research_only": True, "live_trading": False, "created_at": now, "updated_at": now},
        {"strategy_id": "sample_optical_event", "idea_id": "sample_event_confirm", "strategy_name": "光模块事件确认", "theme": "光模块", "lifecycle_state": "qualified", "health_score": 71.0, "recommendation": "降权观察", "reason": "最近拥挤度升高，建议降低观察权重。", "first_seen_date": "2026-06-04", "last_review_date": "2026-06-20", "paper_days": 0, "signal_count": 4, "backtest_count": 2, "best_annual_return": 0.142, "worst_max_drawdown": -0.12, "avg_sharpe": 1.18, "win_rate": 0.51, "evidence": {}, "research_only": True, "live_trading": False, "created_at": now, "updated_at": now},
        {"strategy_id": "sample_liquid_order", "idea_id": "sample_pullback", "strategy_name": "液冷订单催化", "theme": "液冷", "lifecycle_state": "paused", "health_score": 36.0, "recommendation": "暂停", "reason": "证据不足，先暂停新增。", "first_seen_date": "2026-06-07", "last_review_date": "2026-06-20", "paper_days": 0, "signal_count": 1, "backtest_count": 1, "best_annual_return": -0.02, "worst_max_drawdown": -0.2, "avg_sharpe": 0.3, "win_rate": 0.42, "evidence": {}, "research_only": True, "live_trading": False, "created_at": now, "updated_at": now},
    ]


def _sample_lifecycle_events() -> list[dict[str, Any]]:
    return [
        {"event_id": "sample_evt_life_1", "strategy_id": "sample_ai_momentum", "event_time": "2026-06-02T09:30:00", "from_state": None, "to_state": "candidate", "reason": "Codex 基于热点生成策略卡", "evidence": {}, "created_by": "sample", "research_only": True, "live_trading": False},
        {"event_id": "sample_evt_life_2", "strategy_id": "sample_ai_momentum", "event_time": "2026-06-04T15:00:00", "from_state": "candidate", "to_state": "backtested", "reason": "聚宽首次回测结果入库", "evidence": {}, "created_by": "sample", "research_only": True, "live_trading": False},
        {"event_id": "sample_evt_life_3", "strategy_id": "sample_ai_momentum", "event_time": "2026-06-10T15:00:00", "from_state": "qualified", "to_state": "paper_trading", "reason": "纳入纸面组合观察", "evidence": {}, "created_by": "sample", "research_only": True, "live_trading": False},
    ]
