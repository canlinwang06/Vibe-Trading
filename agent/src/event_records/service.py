"""Unified event record read model for objective A-share event history."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Iterable

from src.ashare_data.store import AShareDataStore


class EventRecordError(RuntimeError):
    """Raised when event records cannot be listed."""


IMPACT_WINDOWS = ("T+1", "T+5", "T+20", "T+60")


class EventRecordService:
    """Build reader-facing event records from raw documents, events, mappings, and reactions."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def list_records(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
        event_subtype: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        min_relevance: float = 0.0,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 200)
        min_score = min(max(float(min_relevance), 0.0), 1.0)
        start = _parse_date(from_date, "from_date") if from_date else None
        end = _parse_date(to_date, "to_date") if to_date else None
        if start and end and start > end:
            raise EventRecordError("from_date 不能晚于 to_date")

        filters = ["e.a_share_relevance_score >= ?"]
        params: list[Any] = [min_score]
        if event_type:
            filters.append("e.event_type = ?")
            params.append(event_type.strip())
        if event_subtype:
            filters.append("e.event_subtype = ?")
            params.append(event_subtype.strip())
        if start:
            filters.append("CAST(e.knowable_time AS DATE) >= ?")
            params.append(start)
        if end:
            filters.append("CAST(e.knowable_time AS DATE) <= ?")
            params.append(end)
        params.append(capped_limit)

        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT e.event_id, e.cluster_id, e.doc_id, e.event_time, e.publish_time,
                       e.crawl_time, e.knowable_time, e.tradable_time, e.event_type,
                       e.event_subtype, e.summary, e.sentiment, e.intensity, e.novelty,
                       e.certainty, e.a_share_relevance_score, e.policy_level, e.created_at,
                       rd.source_id, rd.source_name, rd.source_type, rd.title,
                       rd.summary, rd.url, rd.credibility, rd.hot_rank, rd.hot_value
                FROM events e
                LEFT JOIN raw_documents rd ON rd.doc_id = e.doc_id
                WHERE {' AND '.join(filters)}
                ORDER BY e.knowable_time DESC, e.event_id
                LIMIT ?
                """,
                params,
            ).fetchall()

            event_ids = [str(row[0]) for row in rows]
            sectors = _load_sector_maps(conn, event_ids)
            stocks = _load_stock_maps(conn, event_ids)
            reactions = _load_reactions(conn, event_ids)

        records = []
        for row in rows:
            event_id = str(row[0])
            record = _row_to_record(row)
            record["related_sectors"] = sectors.get(event_id, [])
            record["related_stocks"] = stocks.get(event_id, [])
            impact = _impact_summary(reactions.get(event_id, []))
            record["impact"] = impact
            record["impact_t1"] = impact["T+1"]
            record["impact_t5"] = impact["T+5"]
            record["impact_t20"] = impact["T+20"]
            record["impact_t60"] = impact["T+60"]
            records.append(record)
        return records


def _parse_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise EventRecordError(f"{field_name} 必须是 YYYY-MM-DD 格式") from exc


def _load_sector_maps(conn: Any, event_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not event_ids:
        return {}
    rows = conn.execute(
        f"""
        SELECT event_id, cluster_id, sector_id, sector_name, theme, sub_theme,
               relevance, direction, mapping_reason, created_at
        FROM event_sector_map
        WHERE event_id IN ({_placeholders(event_ids)})
        ORDER BY relevance DESC, sector_name
        """,
        event_ids,
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[0])].append(
            {
                "event_id": row[0],
                "cluster_id": row[1],
                "sector_id": row[2],
                "sector_name": row[3],
                "theme": row[4],
                "sub_theme": row[5],
                "relevance": row[6],
                "direction": row[7],
                "mapping_reason": row[8],
                "created_at": _iso(row[9]),
            }
        )
    return dict(grouped)


def _load_stock_maps(conn: Any, event_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not event_ids:
        return {}
    rows = conn.execute(
        f"""
        SELECT event_id, cluster_id, ticker, ticker_name, theme, sector_id,
               relevance, direction, mapping_reason, created_at
        FROM event_stock_map
        WHERE event_id IN ({_placeholders(event_ids)})
        ORDER BY relevance DESC, ticker
        """,
        event_ids,
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[0])].append(
            {
                "event_id": row[0],
                "cluster_id": row[1],
                "ticker": row[2],
                "ticker_name": row[3],
                "theme": row[4],
                "sector_id": row[5],
                "relevance": row[6],
                "direction": row[7],
                "mapping_reason": row[8],
                "created_at": _iso(row[9]),
            }
        )
    return dict(grouped)


def _load_reactions(conn: Any, event_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not event_ids:
        return {}
    rows = conn.execute(
        f"""
        SELECT event_id, "window", target_type, target_id, target_name,
               raw_return, abnormal_return, max_drawdown, calculated_at
        FROM event_reactions
        WHERE event_id IN ({_placeholders(event_ids)})
        ORDER BY event_id, "window", target_type, target_id
        """,
        event_ids,
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[0])].append(
            {
                "event_id": row[0],
                "window": row[1],
                "target_type": row[2],
                "target_id": row[3],
                "target_name": row[4],
                "raw_return": _round_or_none(row[5]),
                "abnormal_return": _round_or_none(row[6]),
                "max_drawdown": _round_or_none(row[7]),
                "calculated_at": _iso(row[8]),
            }
        )
    return dict(grouped)


def _row_to_record(row: tuple[Any, ...]) -> dict[str, Any]:
    source_url = row[23]
    local_ref = f"raw_documents:{row[2]}" if row[2] else None
    evidence = {
        "doc_id": row[2],
        "title": row[21],
        "summary": row[22],
        "source_id": row[18],
        "source_name": row[19],
        "source_type": row[20],
        "url": source_url,
        "local_document_ref": local_ref,
        "credibility": row[24],
        "hot_rank": row[25],
        "hot_value": row[26],
    }
    return {
        "event_id": row[0],
        "cluster_id": row[1],
        "doc_id": row[2],
        "event_time": _iso(row[3]),
        "publish_time": _iso(row[4]),
        "crawl_time": _iso(row[5]),
        "knowable_time": _iso(row[6]),
        "tradable_time": _iso(row[7]),
        "event_type": row[8],
        "event_subtype": row[9],
        "summary": row[10],
        "sentiment": row[11],
        "intensity": row[12],
        "novelty": row[13],
        "certainty": row[14],
        "a_share_relevance_score": row[15],
        "policy_level": row[16],
        "created_at": _iso(row[17]),
        "source_id": row[18],
        "source_name": row[19],
        "source_type": row[20],
        "source_url": source_url,
        "local_document_ref": local_ref,
        "evidence": evidence,
    }


def _impact_summary(reactions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for reaction in reactions:
        by_window[str(reaction["window"])].append(reaction)

    summary = {window: _empty_impact(window) for window in IMPACT_WINDOWS}
    for window, rows in by_window.items():
        if window not in summary:
            continue
        summary[window] = {
            "window": window,
            "status": "available",
            "reaction_count": len(rows),
            "sector_count": sum(1 for row in rows if row["target_type"] == "sector"),
            "stock_count": sum(1 for row in rows if row["target_type"] == "stock"),
            "avg_raw_return": _average(row["raw_return"] for row in rows),
            "avg_abnormal_return": _average(row["abnormal_return"] for row in rows),
            "worst_max_drawdown": _minimum(row["max_drawdown"] for row in rows),
            "calculated_at": max((row["calculated_at"] for row in rows if row["calculated_at"]), default=None),
        }
    return summary


def _empty_impact(window: str) -> dict[str, Any]:
    return {
        "window": window,
        "status": "pending",
        "reaction_count": 0,
        "sector_count": 0,
        "stock_count": 0,
        "avg_raw_return": None,
        "avg_abnormal_return": None,
        "worst_max_drawdown": None,
        "calculated_at": None,
    }


def _average(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 6)


def _minimum(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return min(clean)


def _placeholders(values: list[str]) -> str:
    return ", ".join("?" for _ in values)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)
