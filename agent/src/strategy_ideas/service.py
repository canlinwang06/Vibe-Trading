"""Generate auditable strategy idea cards from hotspot sectors and candidates."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable

from src.ashare_data.store import AShareDataStore
from src.strategy_lab.service import StrategyLabError, StrategyLabService
from src.strategy_lab.service import STRATEGY_TEMPLATES, StrategyTemplate


class StrategyIdeaError(RuntimeError):
    """Raised when strategy idea generation cannot be completed."""


@dataclass(frozen=True)
class CandidateSnapshot:
    ticker: str
    ticker_name: str
    source: str
    sector_id: str | None
    sector_name: str | None
    theme: str | None
    event_heat_score: float
    sector_heat_score: float
    stock_score: float
    risk_flag: str
    reason: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None, field_name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError as exc:
        raise StrategyIdeaError(f"{field_name} 日期格式无效: {value}") from exc


def _row_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_score(value: float) -> float:
    return round(min(max(value, 0.0), 100.0), 2)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _idea_id(as_of: date, theme: str, strategy_type: str, risk_preference: str) -> str:
    raw = f"{as_of.isoformat()}|{theme}|{strategy_type}|{risk_preference}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:18]
    return f"idea_{digest}"


class StrategyIdeaService:
    """Create and list strategy idea cards from local A-share research data."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def generate_ideas(
        self,
        *,
        theme: str | None = None,
        as_of_date: str | date | datetime | None = None,
        risk_preference: str = "balanced",
        max_ideas: int = 8,
        min_candidate_score: float = 0.0,
        strategy_types: list[str] | None = None,
    ) -> dict[str, Any]:
        self.store.initialize()
        normalized_risk = _normalize_risk_preference(risk_preference)
        capped_max = min(max(int(max_ideas), 1), 20)
        score_floor = min(max(float(min_candidate_score), 0.0), 1.0)
        allowed_types = set(strategy_types or [])
        unknown = allowed_types - {template.strategy_type for template in STRATEGY_TEMPLATES}
        if unknown:
            raise StrategyIdeaError(f"不支持的策略模板类型: {', '.join(sorted(unknown))}")

        with self.store.connect() as conn:
            as_of = _parse_date(as_of_date, "as_of_date") or self._latest_candidate_date(conn)
            if as_of is None:
                raise StrategyIdeaError("没有可生成策略想法的候选股票池，请先生成候选股票池。")
            candidates = self._load_candidates(conn, as_of=as_of, theme=theme, min_score=score_floor)
            if not candidates:
                raise StrategyIdeaError("没有可生成策略想法的候选股票，请先生成或纳入候选股票。")
            selected_theme = (theme or self._dominant_theme(candidates)).strip()
            sector_scores = self._load_sector_scores(conn, as_of=as_of)
            source_events = self._load_source_events(conn, theme=selected_theme, limit=8)

            templates = [
                template for template in STRATEGY_TEMPLATES
                if template.generator_enabled and (not allowed_types or template.strategy_type in allowed_types)
            ][:capped_max]
            now = _utc_now()
            ideas = [
                self._build_idea(
                    template=template,
                    as_of=as_of,
                    theme=selected_theme,
                    risk_preference=normalized_risk,
                    candidates=candidates,
                    sector_scores=sector_scores,
                    source_events=source_events,
                    now=now,
                )
                for template in templates
            ]
            ideas.sort(key=lambda item: (-item["idea_score"], item["strategy_type"]))
            for idea in ideas:
                self._upsert_idea(conn, idea)

        return {
            "status": "ok",
            "as_of_date": as_of.isoformat(),
            "theme": selected_theme,
            "risk_preference": normalized_risk,
            "idea_count": len(ideas),
            "ideas": ideas,
            "research_only": True,
            "live_trading": False,
        }

    def list_ideas(
        self,
        *,
        as_of_date: str | date | datetime | None = None,
        theme: str | None = None,
        strategy_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        as_of = _parse_date(as_of_date, "as_of_date")
        capped_limit = min(max(int(limit), 1), 200)
        filters: list[str] = []
        params: list[Any] = []
        if as_of:
            filters.append("as_of_date = ?")
            params.append(as_of)
        if theme:
            filters.append("theme = ?")
            params.append(theme.strip())
        if strategy_type:
            filters.append("strategy_type = ?")
            params.append(strategy_type.strip())
        if status:
            filters.append("status = ?")
            params.append(status.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT idea_id, as_of_date, theme, strategy_type, strategy_name,
                       strategy_family, idea_category, risk_preference, holding_period,
                       rebalance_freq, idea_score, status, thesis, candidate_tickers_json,
                       sector_ids_json, source_event_ids_json, entry_rules_json,
                       exit_rules_json, risk_controls_json, params_json, evidence_json,
                       created_at, updated_at
                FROM strategy_ideas
                {where}
                ORDER BY as_of_date DESC, idea_score DESC, strategy_type
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_idea(row) for row in rows]

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT idea_id, as_of_date, theme, strategy_type, strategy_name,
                       strategy_family, idea_category, risk_preference, holding_period,
                       rebalance_freq, idea_score, status, thesis, candidate_tickers_json,
                       sector_ids_json, source_event_ids_json, entry_rules_json,
                       exit_rules_json, risk_controls_json, params_json, evidence_json,
                       created_at, updated_at
                FROM strategy_ideas
                WHERE idea_id = ?
                """,
                [idea_id.strip()],
            ).fetchone()
        if row is None:
            raise StrategyIdeaError(f"未找到策略想法: {idea_id}")
        return _row_to_idea(row)

    def save_idea_as_strategy_spec(self, *, idea_id: str, enabled: bool = True) -> dict[str, Any]:
        idea = self.get_idea(idea_id)
        params = dict(idea["params"])
        params["source_strategy_idea_id"] = idea["idea_id"]
        params["source_strategy_idea_status"] = idea["status"]
        params["theme"] = idea["theme"]
        params["candidate_tickers"] = idea["candidate_tickers"]
        params["source_event_ids"] = idea["source_event_ids"]
        params["entry_rules"] = idea["entry_rules"]
        params["exit_rules"] = idea["exit_rules"]
        params["risk_controls"] = idea["risk_controls"]
        params["evidence"] = idea["evidence"]
        try:
            spec = StrategyLabService(store=self.store).create_strategy_spec(
                strategy_type=idea["strategy_type"],
                strategy_name=idea["strategy_name"],
                params=params,
                rebalance_freq=str(params.get("rebalance_freq") or idea["rebalance_freq"]),
                holding_period=int(params.get("holding_period") or idea["holding_period"]),
                max_position=float(params.get("max_position") or 0.08),
                max_sector_exposure=float(params.get("max_sector_exposure") or 0.35),
                max_total_exposure=float(params.get("max_total_exposure") or 0.65),
                stop_loss=float(params.get("stop_loss") or 0.08),
                take_profit=float(params.get("take_profit") or 0.18),
                enabled=enabled,
            )
        except StrategyLabError as exc:
            raise StrategyIdeaError(str(exc)) from exc

        now = _utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE strategy_ideas
                SET status = ?, updated_at = ?
                WHERE idea_id = ?
                """,
                ["saved_to_strategy_lab", now, idea["idea_id"]],
            )
        return {
            "status": "ok",
            "idea_id": idea["idea_id"],
            "strategy_spec": spec,
            "research_only": True,
            "live_trading": False,
        }

    @staticmethod
    def _latest_candidate_date(conn: Any) -> date | None:
        row = conn.execute("SELECT MAX(as_of_date) FROM candidate_pool").fetchone()
        return _row_date(row[0]) if row and row[0] else None

    @staticmethod
    def _load_candidates(conn: Any, *, as_of: date, theme: str | None, min_score: float) -> list[CandidateSnapshot]:
        filters = ["as_of_date = ?", "included = true", "stock_score >= ?"]
        params: list[Any] = [as_of, min_score]
        if theme:
            filters.append("theme = ?")
            params.append(theme.strip())
        rows = conn.execute(
            f"""
            SELECT ticker, ticker_name, source, sector_id, sector_name, theme,
                   event_heat_score, sector_heat_score, stock_score, risk_flag, reason
            FROM candidate_pool
            WHERE {' AND '.join(filters)}
            ORDER BY stock_score DESC, ticker
            """,
            params,
        ).fetchall()
        return [
            CandidateSnapshot(
                ticker=row[0],
                ticker_name=row[1],
                source=row[2],
                sector_id=row[3],
                sector_name=row[4],
                theme=row[5],
                event_heat_score=_float(row[6]),
                sector_heat_score=_float(row[7]),
                stock_score=_float(row[8]),
                risk_flag=row[9] or "normal",
                reason=row[10] or "",
            )
            for row in rows
        ]

    @staticmethod
    def _load_sector_scores(conn: Any, *, as_of: date) -> dict[str, dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT sector_id, sector_name, event_heat, market_confirm, breadth_score,
                   flow_score, persistence_score, crowding_risk, sector_heat_score, cycle_stage
            FROM sector_scores
            WHERE trade_date = ?
            """,
            [as_of],
        ).fetchall()
        return {
            row[0]: {
                "sector_id": row[0],
                "sector_name": row[1],
                "event_heat": _float(row[2]),
                "market_confirm": _float(row[3]),
                "breadth_score": _float(row[4]),
                "flow_score": _float(row[5]),
                "persistence_score": _float(row[6]),
                "crowding_risk": _float(row[7]),
                "sector_heat_score": _float(row[8]),
                "cycle_stage": row[9] or "unknown",
            }
            for row in rows
        }

    @staticmethod
    def _load_source_events(conn: Any, *, theme: str, limit: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT event_id, event_type, event_subtype, summary, a_share_relevance_score, knowable_time
            FROM events
            WHERE event_subtype = ? OR summary LIKE ?
            ORDER BY knowable_time DESC, a_share_relevance_score DESC
            LIMIT ?
            """,
            [theme, f"%{theme}%", min(max(limit, 1), 50)],
        ).fetchall()
        return [
            {
                "event_id": row[0],
                "event_type": row[1],
                "event_subtype": row[2],
                "summary": row[3],
                "a_share_relevance_score": _float(row[4]),
                "knowable_time": row[5].isoformat() if row[5] else None,
            }
            for row in rows
        ]

    @staticmethod
    def _dominant_theme(candidates: list[CandidateSnapshot]) -> str:
        counts: dict[str, int] = defaultdict(int)
        for item in candidates:
            counts[item.theme or "综合热点"] += 1
        return max(counts.items(), key=lambda pair: (pair[1], pair[0]))[0]

    def _build_idea(
        self,
        *,
        template: StrategyTemplate,
        as_of: date,
        theme: str,
        risk_preference: str,
        candidates: list[CandidateSnapshot],
        sector_scores: dict[str, dict[str, Any]],
        source_events: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        chosen = _rank_candidates_for_template(template.strategy_type, candidates)
        sector_ids = sorted({item.sector_id for item in chosen if item.sector_id})
        avg_stock_score = sum(item.stock_score for item in chosen) / max(len(chosen), 1)
        avg_sector_score = sum(item.sector_heat_score for item in chosen) / max(len(chosen), 1)
        avg_event_heat = sum(item.event_heat_score for item in chosen) / max(len(chosen), 1)
        sector_crowding = max(
            (sector_scores.get(sector_id, {}).get("crowding_risk", 0.0) for sector_id in sector_ids),
            default=0.0,
        )
        confidence = 0.35 * avg_stock_score + 0.30 * avg_sector_score + 0.20 * avg_event_heat
        confidence += 0.10 if source_events else 0.0
        confidence += 0.05 if risk_preference in template.market_regimes else 0.0
        penalty = 0.15 * sector_crowding if template.strategy_type != "overheated_avoidance" else 0.0
        if template.strategy_type == "overheated_avoidance":
            confidence = max(confidence, 0.58 + sector_crowding * 0.2)
        idea_score = _round_score((confidence - penalty) * 100)

        params = _params_for_template(template, risk_preference)
        entry_rules = _entry_rules(template, theme)
        exit_rules = _exit_rules(template)
        risk_controls = _risk_controls(template, risk_preference)
        evidence = {
            "theme": theme,
            "source": "candidate_pool+sector_scores+event_records",
            "candidate_count": len(chosen),
            "candidate_reasons": {item.ticker: item.reason for item in chosen[:8]},
            "sector_scores": {sector_id: sector_scores.get(sector_id, {}) for sector_id in sector_ids},
            "source_events": source_events,
            "template_prompt": template.idea_prompt,
        }
        tickers = [
            {"ticker": item.ticker, "ticker_name": item.ticker_name, "stock_score": item.stock_score}
            for item in chosen
        ]
        idea_id = _idea_id(as_of, theme, template.strategy_type, risk_preference)
        return {
            "idea_id": idea_id,
            "as_of_date": as_of.isoformat(),
            "theme": theme,
            "strategy_type": template.strategy_type,
            "strategy_name": f"{theme} - {template.template_name}",
            "strategy_family": template.strategy_family,
            "idea_category": template.idea_category,
            "risk_preference": risk_preference,
            "holding_period": params["holding_period"],
            "rebalance_freq": params["rebalance_freq"],
            "idea_score": idea_score,
            "status": "generated",
            "thesis": f"{theme} 当前具备 {template.idea_category} 回测条件：{template.description}",
            "candidate_tickers": tickers,
            "sector_ids": sector_ids,
            "source_event_ids": [event["event_id"] for event in source_events],
            "entry_rules": entry_rules,
            "exit_rules": exit_rules,
            "risk_controls": risk_controls,
            "params": params,
            "evidence": evidence,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "research_only": True,
            "live_trading": False,
        }

    @staticmethod
    def _upsert_idea(conn: Any, idea: dict[str, Any]) -> None:
        conn.execute("DELETE FROM strategy_ideas WHERE idea_id = ?", [idea["idea_id"]])
        conn.execute(
            """
            INSERT INTO strategy_ideas (
              idea_id, as_of_date, theme, strategy_type, strategy_name,
              strategy_family, idea_category, risk_preference, holding_period,
              rebalance_freq, idea_score, status, thesis, candidate_tickers_json,
              sector_ids_json, source_event_ids_json, entry_rules_json,
              exit_rules_json, risk_controls_json, params_json, evidence_json,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                idea["idea_id"],
                date.fromisoformat(idea["as_of_date"]),
                idea["theme"],
                idea["strategy_type"],
                idea["strategy_name"],
                idea["strategy_family"],
                idea["idea_category"],
                idea["risk_preference"],
                idea["holding_period"],
                idea["rebalance_freq"],
                idea["idea_score"],
                idea["status"],
                idea["thesis"],
                _json(idea["candidate_tickers"]),
                _json(idea["sector_ids"]),
                _json(idea["source_event_ids"]),
                _json(idea["entry_rules"]),
                _json(idea["exit_rules"]),
                _json(idea["risk_controls"]),
                _json(idea["params"]),
                _json(idea["evidence"]),
                datetime.fromisoformat(idea["created_at"]),
                datetime.fromisoformat(idea["updated_at"]),
            ],
        )


def _normalize_risk_preference(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"conservative", "balanced", "aggressive"}:
        return normalized
    raise StrategyIdeaError("risk_preference 只支持 conservative、balanced 或 aggressive")


def _rank_candidates_for_template(strategy_type: str, candidates: list[CandidateSnapshot]) -> list[CandidateSnapshot]:
    if strategy_type == "leader_breakout":
        key = lambda item: (-item.stock_score, -item.sector_heat_score, item.ticker)
    elif strategy_type == "catch_up_spread":
        key = lambda item: (item.stock_score, -item.sector_heat_score, item.ticker)
    elif strategy_type in {"low_vol_core", "overheated_avoidance"}:
        key = lambda item: (item.risk_flag != "normal", -item.stock_score, item.ticker)
    elif strategy_type == "event_heat_volume_confirm":
        key = lambda item: (-item.event_heat_score, -item.stock_score, item.ticker)
    else:
        key = lambda item: (-item.sector_heat_score, -item.stock_score, item.ticker)
    ranked = sorted(candidates, key=key)
    return ranked[:8]


def _params_for_template(template: StrategyTemplate, risk_preference: str) -> dict[str, Any]:
    risk_scale = {
        "conservative": {"top_sectors": 2, "top_stocks_per_sector": 3, "exposure": 0.45},
        "balanced": {"top_sectors": 3, "top_stocks_per_sector": 5, "exposure": 0.65},
        "aggressive": {"top_sectors": 5, "top_stocks_per_sector": 8, "exposure": 0.80},
    }[risk_preference]
    return {
        "template_name": template.template_name,
        "strategy_family": template.strategy_family,
        "idea_category": template.idea_category,
        "signal_source": template.signal_source,
        "top_sectors": risk_scale["top_sectors"],
        "top_stocks_per_sector": risk_scale["top_stocks_per_sector"],
        "rebalance_freq": template.default_rebalance_freq,
        "holding_period": template.default_holding_period,
        "max_position": template.default_max_position,
        "max_sector_exposure": min(template.default_max_sector_exposure, risk_scale["exposure"]),
        "max_total_exposure": min(template.default_max_total_exposure, risk_scale["exposure"]),
        "stop_loss": template.default_stop_loss,
        "take_profit": template.default_take_profit,
        "execution_mode": "research_only",
        "data_inputs": ["strategy_ideas", "candidate_pool", "sector_scores", "event_records"],
    }


def _entry_rules(template: StrategyTemplate, theme: str) -> list[str]:
    return [f"主题限定为 {theme}", *template.signal_rules]


def _exit_rules(template: StrategyTemplate) -> list[str]:
    rules = [f"持有 {template.default_holding_period} 个交易日后重新评估"]
    if template.strategy_type == "overheated_avoidance":
        rules.append("板块从 climax/fading 回到 confirmed 前不新增仓位")
    else:
        rules.append("板块热度退潮或拥挤风险升高时退出观察")
    return rules


def _risk_controls(template: StrategyTemplate, risk_preference: str) -> list[str]:
    return [
        f"单股最大仓位 {template.default_max_position:.0%}",
        f"单板块最大仓位 {template.default_max_sector_exposure:.0%}",
        f"总暴露不超过 {template.default_max_total_exposure:.0%}",
        f"风险偏好：{risk_preference}",
        "仅用于研究、模拟和聚宽回测，不生成实盘指令",
    ]


def _row_to_idea(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "idea_id": row[0],
        "as_of_date": row[1].isoformat() if row[1] else None,
        "theme": row[2],
        "strategy_type": row[3],
        "strategy_name": row[4],
        "strategy_family": row[5],
        "idea_category": row[6],
        "risk_preference": row[7],
        "holding_period": row[8],
        "rebalance_freq": row[9],
        "idea_score": row[10],
        "status": row[11],
        "thesis": row[12],
        "candidate_tickers": _loads(row[13], []),
        "sector_ids": _loads(row[14], []),
        "source_event_ids": _loads(row[15], []),
        "entry_rules": _loads(row[16], []),
        "exit_rules": _loads(row[17], []),
        "risk_controls": _loads(row[18], []),
        "params": _loads(row[19], {}),
        "evidence": _loads(row[20], {}),
        "created_at": row[21].isoformat() if row[21] else None,
        "updated_at": row[22].isoformat() if row[22] else None,
        "research_only": True,
        "live_trading": False,
    }
