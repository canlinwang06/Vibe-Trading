"""Local event reaction study for A-share events."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Sequence

from src.ashare_data.store import AShareDataStore

DEFAULT_REACTION_WINDOWS = ("T+1", "T+5", "T+20", "T+60")
TARGET_TYPES = {"sector", "stock"}


class EventReactionError(RuntimeError):
    """Raised when event reaction calculations cannot be completed."""


@dataclass(frozen=True)
class ReactionTarget:
    event_id: str
    cluster_id: str
    event_date: date
    target_type: str
    target_id: str
    target_name: str
    sector_id: str | None


@dataclass(frozen=True)
class PricePoint:
    trade_date: date
    close: float
    volume_or_amount: float | None = None
    breadth: float | None = None


class EventReactionService:
    """Calculate post-event stock and sector reactions from local daily bars."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def calculate_reactions(
        self,
        *,
        event_id: str | None = None,
        cluster_id: str | None = None,
        windows: Sequence[str] | None = None,
        target_types: Sequence[str] | None = None,
        limit: int = 100,
        replace: bool = True,
    ) -> dict[str, Any]:
        selected_windows = _normalize_windows(windows)
        selected_targets = _normalize_target_types(target_types)
        capped_limit = min(max(int(limit), 1), 500)
        now = _utc_now()
        self.store.initialize()

        with self.store.connect() as conn:
            targets = self._load_targets(
                conn,
                event_id=event_id,
                cluster_id=cluster_id,
                target_types=selected_targets,
                limit=capped_limit,
            )
            if not targets:
                raise EventReactionError("没有可计算的事件映射，请先运行事件映射。")

            written = 0
            skipped_existing = 0
            skipped_insufficient_data = 0
            for target in targets:
                for window in selected_windows:
                    offset = _window_offset(window)
                    reaction = self._build_reaction(conn, target=target, window=window, offset=offset, now=now)
                    if reaction is None:
                        skipped_insufficient_data += 1
                        continue
                    exists = conn.execute(
                        "SELECT 1 FROM event_reactions WHERE reaction_id = ?",
                        [reaction["reaction_id"]],
                    ).fetchone()
                    if exists is not None and not replace:
                        skipped_existing += 1
                        continue
                    conn.execute(
                        "DELETE FROM event_reactions WHERE reaction_id = ?",
                        [reaction["reaction_id"]],
                    )
                    conn.execute(
                        """
                        INSERT INTO event_reactions (
                          reaction_id, cluster_id, event_id, target_type, target_id,
                          target_name, "window", raw_return, benchmark_return,
                          sector_return, abnormal_return, max_drawdown,
                          volume_change, breadth_change, calculated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            reaction["reaction_id"],
                            reaction["cluster_id"],
                            reaction["event_id"],
                            reaction["target_type"],
                            reaction["target_id"],
                            reaction["target_name"],
                            reaction["window"],
                            reaction["raw_return"],
                            reaction["benchmark_return"],
                            reaction["sector_return"],
                            reaction["abnormal_return"],
                            reaction["max_drawdown"],
                            reaction["volume_change"],
                            reaction["breadth_change"],
                            now,
                        ],
                    )
                    written += 1

        if written == 0:
            raise EventReactionError("没有可写入的事件反应，请确认事件后行情数据是否足够。")

        return {
            "status": "ok",
            "requested_targets": len(targets),
            "windows": list(selected_windows),
            "target_types": list(selected_targets),
            "reactions_written": written,
            "skipped_existing": skipped_existing,
            "skipped_insufficient_data": skipped_insufficient_data,
            "research_only": True,
            "live_trading": False,
        }

    def list_reactions(
        self,
        *,
        event_id: str | None = None,
        cluster_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        window: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        filters: list[str] = []
        params: list[Any] = []
        if event_id:
            filters.append("event_id = ?")
            params.append(event_id.strip())
        if cluster_id:
            filters.append("cluster_id = ?")
            params.append(cluster_id.strip())
        if target_type:
            normalized_type = _normalize_target_type(target_type)
            filters.append("target_type = ?")
            params.append(normalized_type)
        if target_id:
            filters.append("target_id = ?")
            params.append(target_id.strip())
        if window:
            filters.append('"window" = ?')
            params.append(_normalize_window(window))
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(min(max(int(limit), 1), 500))
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT reaction_id, cluster_id, event_id, target_type, target_id,
                       target_name, "window", raw_return, benchmark_return,
                       sector_return, abnormal_return, max_drawdown,
                       volume_change, breadth_change, calculated_at
                FROM event_reactions
                {where}
                ORDER BY calculated_at DESC, event_id, target_type, target_id, "window"
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_reaction(row) for row in rows]

    def summary(
        self,
        *,
        event_subtype: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        window: str = "T+5",
    ) -> dict[str, Any]:
        self.store.initialize()
        filters = ['r."window" = ?']
        params: list[Any] = [_normalize_window(window)]
        if event_subtype:
            filters.append("e.event_subtype = ?")
            params.append(event_subtype.strip())
        if target_type:
            filters.append("r.target_type = ?")
            params.append(_normalize_target_type(target_type))
        if target_id:
            filters.append("r.target_id = ?")
            params.append(target_id.strip())
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT r.target_type, r."window", COUNT(*),
                       AVG(r.raw_return), AVG(r.benchmark_return),
                       AVG(r.sector_return), AVG(r.abnormal_return),
                       AVG(r.max_drawdown), AVG(r.volume_change),
                       AVG(r.breadth_change)
                FROM event_reactions r
                LEFT JOIN events e ON e.event_id = r.event_id
                WHERE {' AND '.join(filters)}
                GROUP BY r.target_type, r."window"
                ORDER BY r.target_type, r."window"
                """,
                params,
            ).fetchall()
        summaries = [
            {
                "target_type": row[0],
                "window": row[1],
                "reaction_count": int(row[2] or 0),
                "avg_raw_return": _round_or_none(row[3]),
                "avg_benchmark_return": _round_or_none(row[4]),
                "avg_sector_return": _round_or_none(row[5]),
                "avg_abnormal_return": _round_or_none(row[6]),
                "avg_max_drawdown": _round_or_none(row[7]),
                "avg_volume_change": _round_or_none(row[8]),
                "avg_breadth_change": _round_or_none(row[9]),
            }
            for row in rows
        ]
        return {
            "status": "ok",
            "event_subtype": event_subtype,
            "target_type": target_type,
            "target_id": target_id,
            "window": _normalize_window(window),
            "summaries": summaries,
            "summary_count": len(summaries),
            "research_only": True,
            "live_trading": False,
        }

    def _load_targets(
        self,
        conn: Any,
        *,
        event_id: str | None,
        cluster_id: str | None,
        target_types: Sequence[str],
        limit: int,
    ) -> list[ReactionTarget]:
        targets: list[ReactionTarget] = []
        if "sector" in target_types:
            targets.extend(self._load_sector_targets(conn, event_id=event_id, cluster_id=cluster_id, limit=limit))
        if "stock" in target_types:
            targets.extend(self._load_stock_targets(conn, event_id=event_id, cluster_id=cluster_id, limit=limit))
        targets.sort(key=lambda item: (item.event_date, item.event_id, item.target_type, item.target_id))
        return targets[:limit]

    @staticmethod
    def _load_sector_targets(
        conn: Any,
        *,
        event_id: str | None,
        cluster_id: str | None,
        limit: int,
    ) -> list[ReactionTarget]:
        filters: list[str] = []
        params: list[Any] = []
        if event_id:
            filters.append("e.event_id = ?")
            params.append(event_id.strip())
        if cluster_id:
            filters.append("e.cluster_id = ?")
            params.append(cluster_id.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT DISTINCT e.event_id, e.cluster_id, CAST(e.tradable_time AS DATE),
                   m.sector_id, m.sector_name
            FROM event_sector_map m
            JOIN events e ON e.event_id = m.event_id
            {where}
            ORDER BY CAST(e.tradable_time AS DATE), e.event_id, m.sector_id
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            ReactionTarget(
                event_id=row[0],
                cluster_id=row[1],
                event_date=_row_date(row[2]),
                target_type="sector",
                target_id=row[3],
                target_name=row[4],
                sector_id=row[3],
            )
            for row in rows
        ]

    @staticmethod
    def _load_stock_targets(
        conn: Any,
        *,
        event_id: str | None,
        cluster_id: str | None,
        limit: int,
    ) -> list[ReactionTarget]:
        filters: list[str] = []
        params: list[Any] = []
        if event_id:
            filters.append("e.event_id = ?")
            params.append(event_id.strip())
        if cluster_id:
            filters.append("e.cluster_id = ?")
            params.append(cluster_id.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT DISTINCT e.event_id, e.cluster_id, CAST(e.tradable_time AS DATE),
                   m.ticker, m.ticker_name, m.sector_id
            FROM event_stock_map m
            JOIN events e ON e.event_id = m.event_id
            {where}
            ORDER BY CAST(e.tradable_time AS DATE), e.event_id, m.ticker
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            ReactionTarget(
                event_id=row[0],
                cluster_id=row[1],
                event_date=_row_date(row[2]),
                target_type="stock",
                target_id=row[3],
                target_name=row[4],
                sector_id=row[5],
            )
            for row in rows
        ]

    def _build_reaction(
        self,
        conn: Any,
        *,
        target: ReactionTarget,
        window: str,
        offset: int,
        now: datetime,
    ) -> dict[str, Any] | None:
        prices = self._load_price_points(conn, target=target, offset=offset)
        if len(prices) <= offset:
            return None
        benchmark = self._load_benchmark_points(conn, event_date=target.event_date, offset=offset)
        sector = self._load_sector_points(conn, sector_id=target.sector_id, event_date=target.event_date, offset=offset)
        raw_return = _period_return(prices, offset)
        if raw_return is None:
            return None
        benchmark_return = _period_return(benchmark, offset)
        sector_return = raw_return if target.target_type == "sector" else _period_return(sector, offset)
        abnormal_base = benchmark_return if benchmark_return is not None else sector_return
        abnormal_return = raw_return - abnormal_base if abnormal_base is not None else None
        return {
            "reaction_id": _reaction_id(target.event_id, target.target_type, target.target_id, window),
            "cluster_id": target.cluster_id,
            "event_id": target.event_id,
            "target_type": target.target_type,
            "target_id": target.target_id,
            "target_name": target.target_name,
            "window": window,
            "raw_return": _round(raw_return),
            "benchmark_return": _round_or_none(benchmark_return),
            "sector_return": _round_or_none(sector_return),
            "abnormal_return": _round_or_none(abnormal_return),
            "max_drawdown": _round_or_none(_max_drawdown(prices[: offset + 1])),
            "volume_change": _round_or_none(_volume_change(prices, offset)),
            "breadth_change": _round_or_none(_breadth_change(sector, offset)),
            "calculated_at": now,
        }

    @staticmethod
    def _load_price_points(conn: Any, *, target: ReactionTarget, offset: int) -> list[PricePoint]:
        if target.target_type == "sector":
            return _load_sector_points(conn, sector_id=target.target_id, event_date=target.event_date, offset=offset)
        rows = conn.execute(
            """
            SELECT trade_date, close, volume
            FROM market_daily
            WHERE ticker = ? AND trade_date >= ? AND close IS NOT NULL
            ORDER BY trade_date ASC
            LIMIT ?
            """,
            [target.target_id, target.event_date, offset + 1],
        ).fetchall()
        return [
            PricePoint(trade_date=_row_date(row[0]), close=_float(row[1]), volume_or_amount=_float_or_none(row[2]))
            for row in rows
        ]

    @staticmethod
    def _load_benchmark_points(conn: Any, *, event_date: date, offset: int) -> list[PricePoint]:
        rows = conn.execute(
            """
            SELECT trade_date, close, volume
            FROM market_daily
            WHERE ticker = '000300.SH' AND trade_date >= ? AND close IS NOT NULL
            ORDER BY trade_date ASC
            LIMIT ?
            """,
            [event_date, offset + 1],
        ).fetchall()
        return [
            PricePoint(trade_date=_row_date(row[0]), close=_float(row[1]), volume_or_amount=_float_or_none(row[2]))
            for row in rows
        ]

    @staticmethod
    def _load_sector_points(conn: Any, *, sector_id: str | None, event_date: date, offset: int) -> list[PricePoint]:
        return _load_sector_points(conn, sector_id=sector_id, event_date=event_date, offset=offset)


def _load_sector_points(conn: Any, *, sector_id: str | None, event_date: date, offset: int) -> list[PricePoint]:
    if not sector_id:
        return []
    rows = conn.execute(
        """
        SELECT trade_date, close, amount, up_count, down_count
        FROM sector_daily
        WHERE sector_id = ? AND trade_date >= ? AND close IS NOT NULL
        ORDER BY trade_date ASC
        LIMIT ?
        """,
        [sector_id, event_date, offset + 1],
    ).fetchall()
    return [
        PricePoint(
            trade_date=_row_date(row[0]),
            close=_float(row[1]),
            volume_or_amount=_float_or_none(row[2]),
            breadth=_breadth(row[3], row[4]),
        )
        for row in rows
    ]


def _normalize_windows(windows: Sequence[str] | None) -> tuple[str, ...]:
    if windows is None:
        return DEFAULT_REACTION_WINDOWS
    normalized = tuple(_normalize_window(window) for window in windows if str(window).strip())
    if not normalized:
        raise EventReactionError("windows 至少需要包含一个观察窗口。")
    duplicates = sorted({window for window in normalized if normalized.count(window) > 1})
    if duplicates:
        raise EventReactionError(f"观察窗口不能重复: {', '.join(duplicates)}")
    return normalized


def _normalize_window(window: str) -> str:
    normalized = str(window).strip().upper()
    if normalized not in DEFAULT_REACTION_WINDOWS:
        raise EventReactionError("观察窗口只支持 T+1、T+5、T+20、T+60。")
    return normalized


def _window_offset(window: str) -> int:
    return int(window.split("+", 1)[1])


def _normalize_target_types(target_types: Sequence[str] | None) -> tuple[str, ...]:
    if target_types is None:
        return ("sector", "stock")
    normalized = tuple(_normalize_target_type(value) for value in target_types if str(value).strip())
    if not normalized:
        raise EventReactionError("target_types 至少需要包含 sector 或 stock。")
    duplicates = sorted({value for value in normalized if normalized.count(value) > 1})
    if duplicates:
        raise EventReactionError(f"target_types 不能重复: {', '.join(duplicates)}")
    return normalized


def _normalize_target_type(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in TARGET_TYPES:
        raise EventReactionError("target_type 只支持 sector 或 stock。")
    return normalized


def _reaction_id(event_id: str, target_type: str, target_id: str, window: str) -> str:
    raw = f"{event_id}|{target_type}|{target_id}|{window}"
    return f"rxn_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _period_return(points: Sequence[PricePoint], offset: int) -> float | None:
    if len(points) <= offset:
        return None
    start = points[0].close
    end = points[offset].close
    if start == 0:
        return None
    return end / start - 1.0


def _max_drawdown(points: Sequence[PricePoint]) -> float | None:
    if not points:
        return None
    peak = points[0].close
    drawdown = 0.0
    for point in points:
        peak = max(peak, point.close)
        if peak:
            drawdown = min(drawdown, point.close / peak - 1.0)
    return drawdown


def _volume_change(points: Sequence[PricePoint], offset: int) -> float | None:
    if len(points) <= offset:
        return None
    start = points[0].volume_or_amount
    end = points[offset].volume_or_amount
    if start is None or end is None or start == 0:
        return None
    return end / start - 1.0


def _breadth_change(points: Sequence[PricePoint], offset: int) -> float | None:
    if len(points) <= offset:
        return None
    start = points[0].breadth
    end = points[offset].breadth
    if start is None or end is None:
        return None
    return end - start


def _breadth(up_count: Any, down_count: Any) -> float | None:
    up = _float_or_none(up_count)
    down = _float_or_none(down_count)
    if up is None or down is None or up + down <= 0:
        return None
    return up / (up + down)


def _row_to_reaction(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "reaction_id": row[0],
        "cluster_id": row[1],
        "event_id": row[2],
        "target_type": row[3],
        "target_id": row[4],
        "target_name": row[5],
        "window": row[6],
        "raw_return": _round_or_none(row[7]),
        "benchmark_return": _round_or_none(row[8]),
        "sector_return": _round_or_none(row[9]),
        "abnormal_return": _round_or_none(row[10]),
        "max_drawdown": _round_or_none(row[11]),
        "volume_change": _round_or_none(row[12]),
        "breadth_change": _round_or_none(row[13]),
        "calculated_at": row[14].isoformat() if row[14] else None,
    }


def _row_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _float(value: Any) -> float:
    return float(value or 0.0)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _round(value: float) -> float:
    return round(float(value), 6)


def _round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return _round(float(value))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
