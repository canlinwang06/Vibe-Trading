"""Sector heat scoring for the local A-share event radar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore


class SectorScoringError(RuntimeError):
    """Raised when PR-08 sector scoring cannot be completed."""


@dataclass(frozen=True)
class _SectorEvent:
    event_id: str
    cluster_id: str
    sector_id: str
    sector_name: str
    theme: str
    relevance: float
    tradable_time: datetime
    sentiment: str
    intensity: int
    novelty: int
    a_share_relevance_score: float
    hot_score: float
    cross_platform_score: float


@dataclass(frozen=True)
class _SectorDaily:
    trade_date: date
    close: float | None
    return_: float | None
    amount: float | None
    turnover: float | None
    up_count: int | None
    down_count: int | None
    limit_up_count: int | None
    member_count: int | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None) -> date | None:
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
        raise SectorScoringError(f"评分日期格式无效: {value}") from exc


def _row_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _row_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(max(value, lower), upper)


def _round_score(value: float) -> float:
    return round(_clamp(value), 3)


def _direction_factor(sentiment: str | None) -> float:
    if sentiment == "positive":
        return 1.0
    if sentiment == "mixed":
        return 0.55
    if sentiment == "negative":
        return 0.35
    return 0.7


def _event_signal(event: _SectorEvent, trade_date: date) -> float:
    age_days = max((trade_date - event.tradable_time.date()).days, 0)
    if age_days > 30:
        return 0.0
    time_decay = 1 / (1 + age_days / 5)
    intensity = _clamp(event.intensity / 5)
    novelty = _clamp(event.novelty / 5)
    source_weight = _clamp(0.35 + event.hot_score / 2.5 + event.cross_platform_score * 0.15, 0.35, 1.0)
    return (
        event.relevance
        * event.a_share_relevance_score
        * intensity
        * novelty
        * _direction_factor(event.sentiment)
        * source_weight
        * time_decay
    )


def _row_to_score(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "trade_date": row[0].isoformat() if row[0] else None,
        "sector_id": row[1],
        "sector_name": row[2],
        "event_heat": row[3],
        "market_confirm": row[4],
        "breadth_score": row[5],
        "flow_score": row[6],
        "persistence_score": row[7],
        "crowding_risk": row[8],
        "sector_heat_score": row[9],
        "cycle_stage": row[10],
        "created_at": row[11].isoformat() if row[11] else None,
    }


class SectorScoringService:
    """Compute local sector heat scores from mapped A-share events and market data."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def score_sectors(
        self,
        *,
        trade_date: str | date | datetime | None = None,
        limit: int = 10,
        min_relevance: float = 0.45,
    ) -> dict[str, Any]:
        self.store.initialize()
        as_of = _parse_date(trade_date)
        capped_limit = min(max(int(limit), 1), 50)
        min_score = _clamp(float(min_relevance))
        now = _utc_now()
        with self.store.connect() as conn:
            if as_of is None:
                as_of = self._latest_mapped_trade_date(conn)
            if as_of is None:
                raise SectorScoringError("没有可评分的板块映射，请先运行事件映射。")

            events = self._load_sector_events(conn, as_of=as_of, min_relevance=min_score)
            if not events:
                raise SectorScoringError("没有可评分的板块映射，请先运行事件映射。")

            grouped: dict[str, list[_SectorEvent]] = {}
            for event in events:
                grouped.setdefault(event.sector_id, []).append(event)

            scores = [self._build_sector_score(conn, as_of, sector_events) for sector_events in grouped.values()]
            scores.sort(key=lambda item: (-item["sector_heat_score"], item["sector_id"]))
            selected = scores[:capped_limit]

            for score in selected:
                conn.execute(
                    "DELETE FROM sector_scores WHERE trade_date = ? AND sector_id = ?",
                    [as_of, score["sector_id"]],
                )
                conn.execute(
                    """
                    INSERT INTO sector_scores (
                      trade_date, sector_id, sector_name, event_heat, market_confirm,
                      breadth_score, flow_score, persistence_score, crowding_risk,
                      sector_heat_score, cycle_stage, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        as_of,
                        score["sector_id"],
                        score["sector_name"],
                        score["event_heat"],
                        score["market_confirm"],
                        score["breadth_score"],
                        score["flow_score"],
                        score["persistence_score"],
                        score["crowding_risk"],
                        score["sector_heat_score"],
                        score["cycle_stage"],
                        now,
                    ],
                )

        return {
            "status": "ok",
            "trade_date": as_of.isoformat(),
            "scored_sectors": len(selected),
            "rows_written": len(selected),
            "top_sectors": selected,
        }

    def list_sector_scores(
        self,
        *,
        trade_date: str | date | datetime | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        as_of = _parse_date(trade_date)
        capped_limit = min(max(int(limit), 1), 50)
        min_heat = _clamp(float(min_score))
        with self.store.connect(read_only=True) as conn:
            if as_of is None:
                as_of = self._latest_scored_trade_date(conn)
            if as_of is None:
                return []
            rows = conn.execute(
                """
                SELECT trade_date, sector_id, sector_name, event_heat, market_confirm,
                       breadth_score, flow_score, persistence_score, crowding_risk,
                       sector_heat_score, cycle_stage, created_at
                FROM sector_scores
                WHERE trade_date = ? AND sector_heat_score >= ?
                ORDER BY sector_heat_score DESC, sector_id
                LIMIT ?
                """,
                [as_of, min_heat, capped_limit],
            ).fetchall()
        return [_row_to_score(row) for row in rows]

    @staticmethod
    def _latest_mapped_trade_date(conn: Any) -> date | None:
        row = conn.execute(
            """
            SELECT MAX(CAST(e.tradable_time AS DATE))
            FROM event_sector_map m
            JOIN events e ON e.event_id = m.event_id
            """
        ).fetchone()
        return _row_date(row[0]) if row and row[0] else None

    @staticmethod
    def _latest_scored_trade_date(conn: Any) -> date | None:
        row = conn.execute("SELECT MAX(trade_date) FROM sector_scores").fetchone()
        return _row_date(row[0]) if row and row[0] else None

    @staticmethod
    def _load_sector_events(conn: Any, *, as_of: date, min_relevance: float) -> list[_SectorEvent]:
        rows = conn.execute(
            """
            SELECT m.event_id, m.cluster_id, m.sector_id, m.sector_name, m.theme,
                   m.relevance, e.tradable_time, e.sentiment, e.intensity, e.novelty,
                   e.a_share_relevance_score, COALESCE(c.hot_score, 0),
                   COALESCE(c.cross_platform_score, 0)
            FROM event_sector_map m
            JOIN events e ON e.event_id = m.event_id
            LEFT JOIN event_clusters c ON c.cluster_id = e.cluster_id
            WHERE CAST(e.tradable_time AS DATE) <= ? AND m.relevance >= ?
            ORDER BY e.tradable_time DESC, m.relevance DESC, m.sector_id
            LIMIT 1000
            """,
            [as_of, min_relevance],
        ).fetchall()
        events: list[_SectorEvent] = []
        for row in rows:
            tradable_time = _row_datetime(row[6])
            if (as_of - tradable_time.date()).days > 30:
                continue
            events.append(
                _SectorEvent(
                    event_id=row[0],
                    cluster_id=row[1],
                    sector_id=row[2],
                    sector_name=row[3],
                    theme=row[4],
                    relevance=_float(row[5]),
                    tradable_time=tradable_time,
                    sentiment=str(row[7] or "neutral"),
                    intensity=int(_float(row[8], 1)),
                    novelty=int(_float(row[9], 1)),
                    a_share_relevance_score=_float(row[10]),
                    hot_score=_float(row[11]),
                    cross_platform_score=_float(row[12]),
                )
            )
        return events

    def _build_sector_score(self, conn: Any, trade_date: date, events: list[_SectorEvent]) -> dict[str, Any]:
        market_rows = self._load_sector_daily(conn, events[0].sector_id, trade_date)
        event_heat = _round_score(sum(_event_signal(event, trade_date) for event in events))
        market_confirm = self._market_confirm(market_rows)
        breadth_score = self._breadth_score(market_rows)
        flow_score = self._flow_score(market_rows)
        persistence_score = self._persistence_score(market_rows, event_heat)
        crowding_risk = self._crowding_risk(market_rows)
        sector_heat_score = _round_score(
            event_heat * 0.30
            + market_confirm * 0.30
            + breadth_score * 0.15
            + flow_score * 0.15
            + persistence_score * 0.10
            - crowding_risk * 0.20
        )
        return {
            "trade_date": trade_date.isoformat(),
            "sector_id": events[0].sector_id,
            "sector_name": events[0].sector_name,
            "event_heat": event_heat,
            "market_confirm": market_confirm,
            "breadth_score": breadth_score,
            "flow_score": flow_score,
            "persistence_score": persistence_score,
            "crowding_risk": crowding_risk,
            "sector_heat_score": sector_heat_score,
            "cycle_stage": self._cycle_stage(
                sector_heat_score=sector_heat_score,
                event_heat=event_heat,
                market_confirm=market_confirm,
                persistence_score=persistence_score,
                crowding_risk=crowding_risk,
            ),
        }

    @staticmethod
    def _load_sector_daily(conn: Any, sector_id: str, trade_date: date) -> list[_SectorDaily]:
        rows = conn.execute(
            """
            SELECT trade_date, close, "return", amount, turnover, up_count, down_count,
                   limit_up_count, member_count
            FROM sector_daily
            WHERE sector_id = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 20
            """,
            [sector_id, trade_date],
        ).fetchall()
        return [
            _SectorDaily(
                trade_date=_row_date(row[0]),
                close=_float(row[1]) if row[1] is not None else None,
                return_=_float(row[2]) if row[2] is not None else None,
                amount=_float(row[3]) if row[3] is not None else None,
                turnover=_float(row[4]) if row[4] is not None else None,
                up_count=_int_or_none(row[5]),
                down_count=_int_or_none(row[6]),
                limit_up_count=_int_or_none(row[7]),
                member_count=_int_or_none(row[8]),
            )
            for row in rows
        ]

    @staticmethod
    def _market_confirm(rows: list[_SectorDaily]) -> float:
        if not rows:
            return 0.5
        returns = [row.return_ or 0.0 for row in rows]
        closes = [row.close for row in rows if row.close is not None]
        ret_5 = sum(returns[:5])
        ret_20 = sum(returns[:20])
        latest_close = closes[0] if closes else None
        avg_close = sum(closes) / len(closes) if closes else None
        score = 0.5 + _clamp(ret_5, -0.10, 0.10) * 2.0 + _clamp(ret_20, -0.20, 0.20) * 0.5
        if latest_close is not None and avg_close is not None and latest_close >= avg_close:
            score += 0.08
        return _round_score(score)

    @staticmethod
    def _breadth_score(rows: list[_SectorDaily]) -> float:
        if not rows:
            return 0.5
        latest = rows[0]
        member_count = latest.member_count or (latest.up_count or 0) + (latest.down_count or 0)
        if member_count <= 0:
            return 0.5
        up_ratio = (latest.up_count or 0) / member_count
        limit_ratio = min((latest.limit_up_count or 0) / member_count, 0.25) / 0.25
        return _round_score(up_ratio * 0.8 + limit_ratio * 0.2)

    @staticmethod
    def _flow_score(rows: list[_SectorDaily]) -> float:
        if not rows:
            return 0.5
        latest = rows[0]
        amounts = [row.amount for row in rows if row.amount is not None and row.amount > 0]
        turnovers = [row.turnover for row in rows if row.turnover is not None and row.turnover > 0]
        amount_score = 0.5
        turnover_score = 0.5
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            amount_score = _clamp((latest.amount or avg_amount) / avg_amount / 2)
        if turnovers:
            avg_turnover = sum(turnovers) / len(turnovers)
            turnover_score = _clamp((latest.turnover or avg_turnover) / avg_turnover / 2)
        return _round_score(amount_score * 0.65 + turnover_score * 0.35)

    @staticmethod
    def _persistence_score(rows: list[_SectorDaily], event_heat: float) -> float:
        if not rows:
            return _round_score(0.35 + event_heat * 0.25)
        returns = [row.return_ or 0.0 for row in rows[:10]]
        if not returns:
            return _round_score(0.35 + event_heat * 0.25)
        positive_ratio = sum(1 for value in returns if value > 0) / len(returns)
        recent_momentum = _clamp(sum(returns[:5]), -0.10, 0.10) * 2.5
        return _round_score(0.35 + positive_ratio * 0.35 + recent_momentum + event_heat * 0.10)

    @staticmethod
    def _crowding_risk(rows: list[_SectorDaily]) -> float:
        if not rows:
            return 0.1
        latest = rows[0]
        returns = [row.return_ or 0.0 for row in rows[:10]]
        ret_10 = sum(returns)
        member_count = latest.member_count or (latest.up_count or 0) + (latest.down_count or 0)
        limit_ratio = ((latest.limit_up_count or 0) / member_count) if member_count > 0 else 0.0
        amounts = [row.amount for row in rows if row.amount is not None and row.amount > 0]
        amount_spike = 0.0
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            amount_spike = max(0.0, ((latest.amount or avg_amount) / avg_amount - 1) / 2)
        risk = 0.1 + max(0.0, (ret_10 - 0.12) / 0.30) * 0.45 + min(limit_ratio / 0.25, 1.0) * 0.30 + amount_spike * 0.25
        return _round_score(risk)

    @staticmethod
    def _cycle_stage(
        *,
        sector_heat_score: float,
        event_heat: float,
        market_confirm: float,
        persistence_score: float,
        crowding_risk: float,
    ) -> str:
        if sector_heat_score >= 0.78 and crowding_risk >= 0.55:
            return "climax"
        if sector_heat_score >= 0.70 and market_confirm >= 0.62:
            return "accelerating"
        if sector_heat_score >= 0.58 and market_confirm >= 0.52:
            return "confirmed"
        if sector_heat_score >= 0.42 or event_heat >= 0.45:
            return "warming"
        if persistence_score < 0.35 and event_heat < 0.30:
            return "fading"
        return "cold"
