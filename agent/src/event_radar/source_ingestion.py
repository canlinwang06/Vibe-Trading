"""Source registry and raw-document ingestion for the A-share event radar."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from src.ashare_data.store import AShareDataStore


class EventSourceIngestionError(RuntimeError):
    """Raised when PR-05 source or raw-document ingestion cannot continue."""


@dataclass(frozen=True)
class EventSourceRecord:
    source_id: str
    source_name: str
    source_type: str
    endpoint_type: str
    url_or_route: str
    fetch_interval_minutes: int
    parser: str
    credibility: float
    legal_mode: str
    enabled: bool = True


@dataclass(frozen=True)
class RawDocumentRecord:
    source_id: str
    title: str
    content: str
    publish_time: str | datetime
    summary: str | None = None
    crawl_time: str | datetime | None = None
    url: str | None = None
    language: str = "zh-CN"
    author_or_account: str | None = None
    hot_rank: int | None = None
    hot_value: float | None = None
    raw_json: dict[str, Any] | None = None


SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
SOURCE_TYPES = frozenset({
    "policy",
    "regulatory",
    "exchange",
    "announcement",
    "market_data",
    "finance_news",
    "social_hot",
    "international_news",
})
ENDPOINT_TYPES = frozenset({"rss", "api", "html", "vendor", "local", "manual"})
LEGAL_MODES = frozenset({"official_api", "rss", "public_page", "licensed_vendor", "manual", "open_data"})


DEFAULT_EVENT_SOURCES: tuple[EventSourceRecord, ...] = (
    EventSourceRecord(
        source_id="gov_policy_cn",
        source_name="国务院政策文件",
        source_type="policy",
        endpoint_type="html",
        url_or_route="https://www.gov.cn/zhengce/",
        fetch_interval_minutes=240,
        parser="public_page_list",
        credibility=1.0,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="ndrc_policy_cn",
        source_name="国家发改委政策发布",
        source_type="policy",
        endpoint_type="html",
        url_or_route="https://www.ndrc.gov.cn/",
        fetch_interval_minutes=240,
        parser="public_page_list",
        credibility=1.0,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="csrc_policy_cn",
        source_name="证监会政策公告",
        source_type="regulatory",
        endpoint_type="html",
        url_or_route="https://www.csrc.gov.cn/",
        fetch_interval_minutes=240,
        parser="public_page_list",
        credibility=1.0,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="sse_disclosure",
        source_name="上交所公告与监管信息",
        source_type="exchange",
        endpoint_type="html",
        url_or_route="https://www.sse.com.cn/disclosure/",
        fetch_interval_minutes=120,
        parser="public_page_list",
        credibility=0.98,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="szse_disclosure",
        source_name="深交所公告与监管信息",
        source_type="exchange",
        endpoint_type="html",
        url_or_route="https://www.szse.cn/disclosure/",
        fetch_interval_minutes=120,
        parser="public_page_list",
        credibility=0.98,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="cninfo_announcement",
        source_name="巨潮资讯上市公司公告",
        source_type="announcement",
        endpoint_type="html",
        url_or_route="https://www.cninfo.com.cn/",
        fetch_interval_minutes=120,
        parser="public_page_list",
        credibility=1.0,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="eastmoney_market",
        source_name="东方财富行情与板块数据",
        source_type="market_data",
        endpoint_type="html",
        url_or_route="https://quote.eastmoney.com/",
        fetch_interval_minutes=30,
        parser="public_market_snapshot",
        credibility=0.82,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="tencent_market",
        source_name="腾讯行情公开数据",
        source_type="market_data",
        endpoint_type="api",
        url_or_route="https://qt.gtimg.cn/",
        fetch_interval_minutes=30,
        parser="public_market_snapshot",
        credibility=0.8,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="akshare_local",
        source_name="AKShare 本地公开数据桥",
        source_type="market_data",
        endpoint_type="local",
        url_or_route="akshare://local-python",
        fetch_interval_minutes=60,
        parser="akshare_loader",
        credibility=0.78,
        legal_mode="open_data",
    ),
    EventSourceRecord(
        source_id="finance_news_manual",
        source_name="财经新闻手动导入",
        source_type="finance_news",
        endpoint_type="manual",
        url_or_route="/api/event-radar/collect/run",
        fetch_interval_minutes=180,
        parser="manual_json",
        credibility=0.7,
        legal_mode="manual",
    ),
    EventSourceRecord(
        source_id="eastmoney_news",
        source_name="东方财富财经新闻",
        source_type="finance_news",
        endpoint_type="html",
        url_or_route="https://finance.eastmoney.com/",
        fetch_interval_minutes=90,
        parser="public_page_list",
        credibility=0.72,
        legal_mode="public_page",
    ),
    EventSourceRecord(
        source_id="social_hot_manual",
        source_name="公开热榜手动导入",
        source_type="social_hot",
        endpoint_type="manual",
        url_or_route="/api/event-radar/collect/run",
        fetch_interval_minutes=120,
        parser="manual_json",
        credibility=0.6,
        legal_mode="manual",
    ),
    EventSourceRecord(
        source_id="public_social_hot",
        source_name="公开社交热榜线索",
        source_type="social_hot",
        endpoint_type="manual",
        url_or_route="/api/event-radar/collect/run",
        fetch_interval_minutes=120,
        parser="manual_json",
        credibility=0.45,
        legal_mode="manual",
    ),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_datetime(value: str | datetime, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    raw = str(value).strip()
    if not raw:
        raise EventSourceIngestionError(f"{field_name} 不能为空")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventSourceIngestionError(f"{field_name} 时间格式无效: {value}") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _validate_source_id(source_id: str) -> str:
    normalized = source_id.strip().lower()
    if not SOURCE_ID_RE.fullmatch(normalized):
        raise EventSourceIngestionError("source_id 只能使用小写字母、数字、下划线或连字符，并且以字母开头")
    return normalized


def _validate_source(source: EventSourceRecord) -> EventSourceRecord:
    source_id = _validate_source_id(source.source_id)
    source_type = source.source_type.strip().lower()
    endpoint_type = source.endpoint_type.strip().lower()
    legal_mode = source.legal_mode.strip().lower()
    if source_type not in SOURCE_TYPES:
        raise EventSourceIngestionError(f"source_type 不支持: {source.source_type}")
    if endpoint_type not in ENDPOINT_TYPES:
        raise EventSourceIngestionError(f"endpoint_type 不支持: {source.endpoint_type}")
    if legal_mode not in LEGAL_MODES:
        raise EventSourceIngestionError(f"legal_mode 不支持: {source.legal_mode}")
    if not source.source_name.strip():
        raise EventSourceIngestionError("source_name 不能为空")
    if source.fetch_interval_minutes <= 0:
        raise EventSourceIngestionError("fetch_interval_minutes 必须大于 0")
    if not 0 <= source.credibility <= 1:
        raise EventSourceIngestionError("credibility 必须在 0 到 1 之间")
    return EventSourceRecord(
        source_id=source_id,
        source_name=source.source_name.strip(),
        source_type=source_type,
        endpoint_type=endpoint_type,
        url_or_route=source.url_or_route.strip(),
        fetch_interval_minutes=source.fetch_interval_minutes,
        parser=source.parser.strip(),
        credibility=float(source.credibility),
        legal_mode=legal_mode,
        enabled=bool(source.enabled),
    )


def _content_hash(*, title: str, content: str, url: str | None, publish_time: datetime) -> str:
    material = "\n".join(
        part.strip()
        for part in (
            title,
            content,
            url or "",
            publish_time.isoformat(timespec="seconds"),
        )
        if part and part.strip()
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _json_dumps(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row_to_source(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "source_id": row[0],
        "source_name": row[1],
        "source_type": row[2],
        "endpoint_type": row[3],
        "url_or_route": row[4],
        "fetch_interval_minutes": row[5],
        "parser": row[6],
        "credibility": row[7],
        "legal_mode": row[8],
        "enabled": bool(row[9]),
        "last_fetch_time": row[10].isoformat() if row[10] else None,
        "created_at": row[11].isoformat() if row[11] else None,
        "updated_at": row[12].isoformat() if row[12] else None,
    }


def _row_to_document(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "doc_id": row[0],
        "source_id": row[1],
        "source_name": row[2],
        "source_type": row[3],
        "title": row[4],
        "content": row[5],
        "summary": row[6],
        "publish_time": row[7].isoformat() if row[7] else None,
        "crawl_time": row[8].isoformat() if row[8] else None,
        "url": row[9],
        "content_hash": row[10],
        "language": row[11],
        "author_or_account": row[12],
        "hot_rank": row[13],
        "hot_value": row[14],
        "raw_json": json.loads(row[15] or "{}"),
        "credibility": row[16],
        "created_at": row[17].isoformat() if row[17] else None,
    }


class EventSourceIngestionService:
    """Manage source metadata and raw documents for PR-05."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def ensure_default_sources(self) -> tuple[EventSourceRecord, ...]:
        self.store.initialize()
        self.upsert_sources(DEFAULT_EVENT_SOURCES)
        return DEFAULT_EVENT_SOURCES

    def upsert_sources(self, sources: Iterable[EventSourceRecord]) -> int:
        rows = [_validate_source(source) for source in sources]
        now = _utc_now()
        with self.store.connect() as conn:
            for source in rows:
                existing = conn.execute(
                    "SELECT last_fetch_time, created_at FROM source_registry WHERE source_id = ?",
                    [source.source_id],
                ).fetchone()
                last_fetch_time = existing[0] if existing else None
                created_at = existing[1] if existing and existing[1] else now
                conn.execute("DELETE FROM source_registry WHERE source_id = ?", [source.source_id])
                conn.execute(
                    """
                    INSERT INTO source_registry (
                      source_id, source_name, source_type, endpoint_type, url_or_route,
                      fetch_interval_minutes, parser, credibility, legal_mode, enabled,
                      last_fetch_time, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        source.source_id,
                        source.source_name,
                        source.source_type,
                        source.endpoint_type,
                        source.url_or_route,
                        source.fetch_interval_minutes,
                        source.parser,
                        source.credibility,
                        source.legal_mode,
                        source.enabled,
                        last_fetch_time,
                        created_at,
                        now,
                    ],
                )
        return len(rows)

    def list_sources(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        self.ensure_default_sources()
        where = "WHERE enabled = true" if enabled_only else ""
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT source_id, source_name, source_type, endpoint_type, url_or_route,
                       fetch_interval_minutes, parser, credibility, legal_mode, enabled,
                       last_fetch_time, created_at, updated_at
                FROM source_registry
                {where}
                ORDER BY source_type, source_id
                """
            ).fetchall()
        return [_row_to_source(row) for row in rows]

    def get_source(self, source_id: str) -> dict[str, Any]:
        normalized = _validate_source_id(source_id)
        self.ensure_default_sources()
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT source_id, source_name, source_type, endpoint_type, url_or_route,
                       fetch_interval_minutes, parser, credibility, legal_mode, enabled,
                       last_fetch_time, created_at, updated_at
                FROM source_registry
                WHERE source_id = ?
                """,
                [normalized],
            ).fetchone()
        if row is None:
            raise EventSourceIngestionError(f"未找到信息源: {normalized}")
        return _row_to_source(row)

    def ingest_documents(self, documents: Iterable[RawDocumentRecord]) -> dict[str, Any]:
        self.ensure_default_sources()
        records = list(documents)
        if not records:
            raise EventSourceIngestionError("请至少提供一条原始文档")

        inserted: list[str] = []
        duplicates: list[str] = []
        touched_sources: set[str] = set()
        crawl_time = _utc_now()

        with self.store.connect() as conn:
            for record in records:
                source = self._load_source(conn, record.source_id)
                title = record.title.strip()
                content = record.content.strip()
                if not title:
                    raise EventSourceIngestionError("原始文档标题不能为空")
                if not content:
                    raise EventSourceIngestionError("原始文档正文不能为空")
                publish_time = _parse_datetime(record.publish_time, field_name="publish_time")
                doc_crawl_time = (
                    _parse_datetime(record.crawl_time, field_name="crawl_time")
                    if record.crawl_time is not None
                    else crawl_time
                )
                content_hash = _content_hash(
                    title=title,
                    content=content,
                    url=record.url,
                    publish_time=publish_time,
                )
                existing = conn.execute(
                    "SELECT doc_id FROM raw_documents WHERE content_hash = ?",
                    [content_hash],
                ).fetchone()
                if existing is not None:
                    duplicates.append(str(existing[0]))
                    continue

                doc_id = f"raw_{content_hash[:20]}"
                try:
                    conn.execute(
                        """
                        INSERT INTO raw_documents (
                          doc_id, source_id, source_name, source_type, title, content,
                          summary, publish_time, crawl_time, url, content_hash, language,
                          author_or_account, hot_rank, hot_value, raw_json, credibility, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            doc_id,
                            source["source_id"],
                            source["source_name"],
                            source["source_type"],
                            title,
                            content,
                            record.summary.strip() if record.summary else None,
                            publish_time,
                            doc_crawl_time,
                            record.url.strip() if record.url else None,
                            content_hash,
                            record.language.strip() or "zh-CN",
                            record.author_or_account.strip() if record.author_or_account else None,
                            record.hot_rank,
                            record.hot_value,
                            _json_dumps(record.raw_json),
                            source["credibility"],
                            crawl_time,
                        ],
                    )
                except Exception:
                    existing_after_conflict = conn.execute(
                        "SELECT doc_id FROM raw_documents WHERE doc_id = ? OR content_hash = ?",
                        [doc_id, content_hash],
                    ).fetchone()
                    if existing_after_conflict is None:
                        raise
                    duplicates.append(str(existing_after_conflict[0]))
                    continue
                inserted.append(doc_id)
                touched_sources.add(source["source_id"])

            for source_id in touched_sources:
                conn.execute(
                    """
                    UPDATE source_registry
                    SET last_fetch_time = ?, updated_at = ?
                    WHERE source_id = ?
                    """,
                    [crawl_time, crawl_time, source_id],
                )

        return {
            "status": "ok",
            "requested": len(records),
            "inserted": len(inserted),
            "duplicates": len(duplicates),
            "doc_ids": inserted,
            "duplicate_doc_ids": duplicates,
            "source_ids": sorted(touched_sources),
            "crawl_time": crawl_time.isoformat(timespec="seconds"),
        }

    def list_raw_documents(
        self,
        *,
        limit: int = 50,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 200)
        filters: list[str] = []
        params: list[Any] = []
        if source_type:
            normalized_type = source_type.strip().lower()
            if normalized_type not in SOURCE_TYPES:
                raise EventSourceIngestionError(f"source_type 不支持: {source_type}")
            filters.append("source_type = ?")
            params.append(normalized_type)
        if source_id:
            filters.append("source_id = ?")
            params.append(_validate_source_id(source_id))
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT doc_id, source_id, source_name, source_type, title, content,
                       summary, publish_time, crawl_time, url, content_hash, language,
                       author_or_account, hot_rank, hot_value, raw_json, credibility, created_at
                FROM raw_documents
                {where}
                ORDER BY publish_time DESC, crawl_time DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_document(row) for row in rows]

    @staticmethod
    def _load_source(conn: Any, source_id: str) -> dict[str, Any]:
        normalized = _validate_source_id(source_id)
        row = conn.execute(
            """
            SELECT source_id, source_name, source_type, endpoint_type, url_or_route,
                   fetch_interval_minutes, parser, credibility, legal_mode, enabled,
                   last_fetch_time, created_at, updated_at
            FROM source_registry
            WHERE source_id = ?
            """,
            [normalized],
        ).fetchone()
        if row is None:
            raise EventSourceIngestionError(f"未找到信息源: {normalized}")
        source = _row_to_source(row)
        if not source["enabled"]:
            raise EventSourceIngestionError(f"信息源已禁用: {normalized}")
        return source
