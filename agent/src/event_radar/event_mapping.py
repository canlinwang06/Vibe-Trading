"""Event-to-theme, sector, and stock mapping for the A-share event radar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable

from src.ashare_data.store import AShareDataStore
from src.market_policy import is_a_share_code, normalize_a_share_code


class EventMappingError(RuntimeError):
    """Raised when PR-07 event mapping cannot be completed."""


@dataclass(frozen=True)
class ThemeMapRecord:
    theme: str
    sub_theme: str
    keyword: str
    sector_id: str
    sector_name: str
    ticker: str
    ticker_name: str
    relevance: float
    evidence: str
    source: str = "manual"


DEFAULT_THEME_MAP: tuple[ThemeMapRecord, ...] = (
    ThemeMapRecord("AI算力", "光模块", "AI 算力 光模块 数据中心", "theme_ai_compute", "AI算力", "300308.SZ", "中际旭创", 0.92, "光模块是 AI 算力基础设施上游核心环节"),
    ThemeMapRecord("AI算力", "服务器", "服务器 数据中心 液冷 算力", "theme_ai_compute", "AI算力", "000977.SZ", "浪潮信息", 0.86, "服务器和数据中心受算力建设需求驱动"),
    ThemeMapRecord("AI算力", "工业互联网", "AI 服务器 云计算", "theme_ai_compute", "AI算力", "601138.SH", "工业富联", 0.82, "AI 服务器产业链代表公司"),
    ThemeMapRecord("人形机器人", "机器人本体", "机器人 人形机器人 智能制造 自动化", "theme_robotics", "人形机器人", "300024.SZ", "机器人", 0.9, "机器人主题代表公司"),
    ThemeMapRecord("人形机器人", "运动控制", "机器人 自动化 伺服 控制器", "theme_robotics", "人形机器人", "002747.SZ", "埃斯顿", 0.82, "运动控制和自动化环节代表公司"),
    ThemeMapRecord("半导体", "国产芯片", "芯片 半导体 国产替代 先进封装", "theme_semiconductor", "半导体", "688981.SH", "中芯国际", 0.88, "国产晶圆制造代表公司"),
    ThemeMapRecord("半导体", "半导体设备", "半导体设备 刻蚀 设备 国产替代", "theme_semiconductor", "半导体", "002371.SZ", "北方华创", 0.86, "半导体设备代表公司"),
    ThemeMapRecord("新能源", "动力电池", "新能源 电池 锂电 固态电池 储能", "theme_new_energy", "新能源", "300750.SZ", "宁德时代", 0.9, "动力电池和储能代表公司"),
    ThemeMapRecord("新能源", "新能源汽车", "新能源车 电池 储能", "theme_new_energy", "新能源", "002594.SZ", "比亚迪", 0.84, "新能源汽车产业链代表公司"),
    ThemeMapRecord("文娱消费", "传媒娱乐", "消费 文旅 旅游 票房 影视 游戏", "theme_media_consumption", "文娱消费", "300413.SZ", "芒果超媒", 0.78, "文娱消费和传媒热度代表公司"),
    ThemeMapRecord("文娱消费", "大众消费", "消费 白酒 餐饮", "theme_media_consumption", "文娱消费", "600519.SH", "贵州茅台", 0.72, "消费情绪代表公司"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _row_to_sector_map(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "event_id": row[0],
        "cluster_id": row[1],
        "sector_id": row[2],
        "sector_name": row[3],
        "theme": row[4],
        "sub_theme": row[5],
        "relevance": row[6],
        "direction": row[7],
        "mapping_reason": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
    }


def _row_to_stock_map(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "event_id": row[0],
        "cluster_id": row[1],
        "ticker": row[2],
        "ticker_name": row[3],
        "theme": row[4],
        "sector_id": row[5],
        "relevance": row[6],
        "direction": row[7],
        "mapping_reason": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
    }


def _validate_theme_record(record: ThemeMapRecord) -> ThemeMapRecord:
    ticker = normalize_a_share_code(record.ticker)
    if not is_a_share_code(ticker):
        raise EventMappingError(f"主题映射只支持沪深 A 股代码: {record.ticker}")
    if not 0 <= record.relevance <= 1:
        raise EventMappingError("主题映射 relevance 必须在 0 到 1 之间")
    return ThemeMapRecord(
        theme=record.theme.strip(),
        sub_theme=record.sub_theme.strip(),
        keyword=record.keyword.strip(),
        sector_id=record.sector_id.strip(),
        sector_name=record.sector_name.strip(),
        ticker=ticker,
        ticker_name=record.ticker_name.strip(),
        relevance=float(record.relevance),
        evidence=record.evidence.strip(),
        source=record.source.strip() or "manual",
    )


def _direction(sentiment: str | None) -> str:
    if sentiment in {"positive", "negative", "neutral"}:
        return sentiment
    return "neutral"


def _event_text(event: dict[str, Any]) -> str:
    return " ".join(
        str(part or "")
        for part in (
            event.get("event_type"),
            event.get("event_subtype"),
            event.get("summary"),
        )
    )


def _score_record(event: dict[str, Any], record: dict[str, Any]) -> float:
    text = _event_text(event).lower()
    score = float(record["relevance"]) * 0.65 + float(event.get("a_share_relevance_score") or 0) * 0.35
    if str(event.get("event_subtype") or "") in {record["theme"], record["sub_theme"], record["sector_name"]}:
        score += 0.12
    for keyword in str(record["keyword"] or "").split():
        if keyword.lower() and keyword.lower() in text:
            score += 0.08
    return round(min(score, 1.0), 3)


class EventMappingService:
    """Seed theme mappings and map extracted events to sectors/stocks."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def ensure_default_theme_map(self) -> tuple[ThemeMapRecord, ...]:
        self.store.initialize()
        records = [_validate_theme_record(record) for record in DEFAULT_THEME_MAP]
        now = _utc_now()
        with self.store.connect() as conn:
            for record in records:
                conn.execute(
                    """
                    DELETE FROM theme_map
                    WHERE theme = ? AND sub_theme = ? AND keyword = ? AND ticker = ?
                    """,
                    [record.theme, record.sub_theme, record.keyword, record.ticker],
                )
                conn.execute(
                    """
                    INSERT INTO theme_map (
                      theme, sub_theme, keyword, sector_id, sector_name, ticker,
                      ticker_name, relevance, evidence, source, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        record.theme,
                        record.sub_theme,
                        record.keyword,
                        record.sector_id,
                        record.sector_name,
                        record.ticker,
                        record.ticker_name,
                        record.relevance,
                        record.evidence,
                        record.source,
                        now,
                    ],
                )
                conn.execute(
                    "DELETE FROM sectors WHERE sector_id = ?",
                    [record.sector_id],
                )
                conn.execute(
                    """
                    INSERT INTO sectors (sector_id, sector_name, sector_type, source, active, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [record.sector_id, record.sector_name, "custom_theme", "manual", True, now],
                )
                conn.execute(
                    """
                    DELETE FROM sector_members
                    WHERE sector_id = ? AND ticker = ?
                    """,
                    [record.sector_id, record.ticker],
                )
                conn.execute(
                    """
                    INSERT INTO sector_members (
                      sector_id, ticker, ticker_name, weight, relevance,
                      start_date, end_date, source, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        record.sector_id,
                        record.ticker,
                        record.ticker_name,
                        record.relevance,
                        record.relevance,
                        date(2026, 1, 1),
                        None,
                        "manual",
                        now,
                    ],
                )
        return DEFAULT_THEME_MAP

    def list_theme_map(self, *, theme: str | None = None) -> list[dict[str, Any]]:
        self.ensure_default_theme_map()
        filters: list[str] = []
        params: list[Any] = []
        if theme:
            filters.append("theme = ?")
            params.append(theme.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT theme, sub_theme, keyword, sector_id, sector_name, ticker,
                       ticker_name, relevance, evidence, source, updated_at
                FROM theme_map
                {where}
                ORDER BY theme, sub_theme, relevance DESC, ticker
                """,
                params,
            ).fetchall()
        return [
            {
                "theme": row[0],
                "sub_theme": row[1],
                "keyword": row[2],
                "sector_id": row[3],
                "sector_name": row[4],
                "ticker": row[5],
                "ticker_name": row[6],
                "relevance": row[7],
                "evidence": row[8],
                "source": row[9],
                "updated_at": row[10].isoformat() if row[10] else None,
            }
            for row in rows
        ]

    def map_events(self, *, min_relevance: float = 0.45, limit: int = 100) -> dict[str, Any]:
        self.ensure_default_theme_map()
        min_score = min(max(float(min_relevance), 0.0), 1.0)
        capped_limit = min(max(int(limit), 1), 500)
        now = _utc_now()
        with self.store.connect() as conn:
            event_rows = conn.execute(
                """
                SELECT event_id, cluster_id, event_type, event_subtype, summary,
                       sentiment, a_share_relevance_score
                FROM events
                WHERE a_share_relevance_score >= ?
                ORDER BY knowable_time DESC, event_id
                LIMIT ?
                """,
                [min_score, capped_limit],
            ).fetchall()
            if not event_rows:
                raise EventMappingError("没有可映射的事件，请先运行事件抽取。")
            theme_rows = self._load_theme_rows(conn)
            if not theme_rows:
                raise EventMappingError("主题映射表为空，请先初始化 theme_map。")

            mapped_event_ids: list[str] = []
            sector_rows_written = 0
            stock_rows_written = 0
            for row in event_rows:
                event = {
                    "event_id": row[0],
                    "cluster_id": row[1],
                    "event_type": row[2],
                    "event_subtype": row[3],
                    "summary": row[4],
                    "sentiment": row[5],
                    "a_share_relevance_score": row[6],
                }
                matches = self._rank_matches(event, theme_rows)
                if not matches:
                    continue
                conn.execute("DELETE FROM event_sector_map WHERE event_id = ?", [event["event_id"]])
                conn.execute("DELETE FROM event_stock_map WHERE event_id = ?", [event["event_id"]])
                sector_rows_written += self._write_sector_maps(conn, event, matches, now)
                stock_rows_written += self._write_stock_maps(conn, event, matches, now)
                mapped_event_ids.append(event["event_id"])

        return {
            "status": "ok",
            "requested_events": len(event_rows),
            "mapped_events": len(mapped_event_ids),
            "sector_rows_written": sector_rows_written,
            "stock_rows_written": stock_rows_written,
            "event_ids": mapped_event_ids,
        }

    def list_event_sector_maps(self, *, event_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        self.store.initialize()
        filters: list[str] = []
        params: list[Any] = []
        if event_id:
            filters.append("event_id = ?")
            params.append(event_id.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(min(max(int(limit), 1), 500))
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, cluster_id, sector_id, sector_name, theme, sub_theme,
                       relevance, direction, mapping_reason, created_at
                FROM event_sector_map
                {where}
                ORDER BY relevance DESC, event_id, sector_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_sector_map(row) for row in rows]

    def list_event_stock_maps(self, *, event_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        self.store.initialize()
        filters: list[str] = []
        params: list[Any] = []
        if event_id:
            filters.append("event_id = ?")
            params.append(event_id.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(min(max(int(limit), 1), 500))
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, cluster_id, ticker, ticker_name, theme, sector_id,
                       relevance, direction, mapping_reason, created_at
                FROM event_stock_map
                {where}
                ORDER BY relevance DESC, event_id, ticker
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_stock_map(row) for row in rows]

    @staticmethod
    def _load_theme_rows(conn: Any) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT theme, sub_theme, keyword, sector_id, sector_name, ticker,
                   ticker_name, relevance, evidence
            FROM theme_map
            ORDER BY relevance DESC
            """
        ).fetchall()
        return [
            {
                "theme": row[0],
                "sub_theme": row[1],
                "keyword": row[2],
                "sector_id": row[3],
                "sector_name": row[4],
                "ticker": row[5],
                "ticker_name": row[6],
                "relevance": row[7],
                "evidence": row[8],
            }
            for row in rows
        ]

    @staticmethod
    def _rank_matches(event: dict[str, Any], theme_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scored: list[dict[str, Any]] = []
        text = _event_text(event).lower()
        for record in theme_rows:
            keyword_hit = any(keyword.lower() in text for keyword in str(record["keyword"]).split() if keyword)
            subtype_hit = str(event.get("event_subtype") or "") in {record["theme"], record["sub_theme"], record["sector_name"]}
            theme_hit = str(record["theme"]).lower() in text or str(record["sub_theme"]).lower() in text
            if not (keyword_hit or subtype_hit or theme_hit):
                continue
            scored_record = dict(record)
            scored_record["mapping_relevance"] = _score_record(event, record)
            scored.append(scored_record)
        scored.sort(key=lambda item: (-item["mapping_relevance"], item["theme"], item["ticker"]))
        return scored[:8]

    @staticmethod
    def _write_sector_maps(conn: Any, event: dict[str, Any], matches: list[dict[str, Any]], now: datetime) -> int:
        by_sector: dict[str, dict[str, Any]] = {}
        for match in matches:
            current = by_sector.get(match["sector_id"])
            if current is None or match["mapping_relevance"] > current["mapping_relevance"]:
                by_sector[match["sector_id"]] = match
        for match in by_sector.values():
            conn.execute(
                """
                INSERT INTO event_sector_map (
                  event_id, cluster_id, sector_id, sector_name, theme, sub_theme,
                  relevance, direction, mapping_reason, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    event["event_id"],
                    event["cluster_id"],
                    match["sector_id"],
                    match["sector_name"],
                    match["theme"],
                    match["sub_theme"],
                    match["mapping_relevance"],
                    _direction(event.get("sentiment")),
                    f"事件 subtype/summary 命中主题词: {match['keyword']}",
                    now,
                ],
            )
        return len(by_sector)

    @staticmethod
    def _write_stock_maps(conn: Any, event: dict[str, Any], matches: list[dict[str, Any]], now: datetime) -> int:
        for match in matches:
            conn.execute(
                """
                INSERT INTO event_stock_map (
                  event_id, cluster_id, ticker, ticker_name, theme, sector_id,
                  relevance, direction, mapping_reason, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    event["event_id"],
                    event["cluster_id"],
                    match["ticker"],
                    match["ticker_name"],
                    match["theme"],
                    match["sector_id"],
                    match["mapping_relevance"],
                    _direction(event.get("sentiment")),
                    match["evidence"],
                    now,
                ],
            )
        return len(matches)
