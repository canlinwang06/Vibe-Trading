"""Local rule-based event extraction and clustering for the A-share event radar."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore


class EventExtractionError(RuntimeError):
    """Raised when PR-06 event extraction cannot be completed."""


@dataclass(frozen=True)
class ExtractedEvent:
    doc_id: str
    cluster_id: str
    event_id: str
    event_time: datetime
    publish_time: datetime
    crawl_time: datetime
    knowable_time: datetime
    tradable_time: datetime
    event_type: str
    event_subtype: str
    summary: str
    sentiment: str
    intensity: int
    novelty: int
    certainty: float
    a_share_relevance_score: float
    policy_level: str | None
    source_id: str
    source_name: str
    hot_rank: int | None
    hot_value: float | None
    mention_weight: float


POSITIVE_KEYWORDS = ("利好", "增长", "提升", "突破", "回购", "增持", "预增", "中标", "签约", "扩产", "支持")
NEGATIVE_KEYWORDS = ("处罚", "下滑", "暴雷", "减持", "解禁", "事故", "冲突", "制裁", "亏损", "风险", "召回")
POLICY_KEYWORDS = ("政策", "国务院", "发改委", "工信部", "财政部", "央行", "证监会", "交易所", "发布", "意见")
MACRO_KEYWORDS = ("降准", "降息", "利率", "汇率", "信贷", "社融", "通胀", "货币", "财政")
AI_KEYWORDS = ("AI", "人工智能", "算力", "数据中心", "光模块", "液冷", "服务器", "大模型")
ROBOT_KEYWORDS = ("机器人", "人形机器人", "智能制造", "自动化")
SEMI_KEYWORDS = ("芯片", "半导体", "国产替代", "先进封装", "晶圆")
EV_KEYWORDS = ("新能源车", "电池", "储能", "光伏", "锂电", "固态电池")
CONSUMER_KEYWORDS = ("消费", "文旅", "旅游", "票房", "影视", "游戏", "白酒", "餐饮")
CONFLICT_KEYWORDS = ("冲突", "地缘", "军事", "战争", "制裁", "红海", "中东")
CONTRACT_KEYWORDS = ("重大合同", "中标", "签订合同", "签约")
MNA_KEYWORDS = ("并购", "重组", "收购", "资产注入")
BUYBACK_KEYWORDS = ("回购", "增持")
REDUCE_KEYWORDS = ("减持", "解禁")
PUNISH_KEYWORDS = ("处罚", "立案", "监管函", "问询函")
EARNINGS_UP_KEYWORDS = ("业绩预增", "预增", "扭亏", "净利润增长")
EARNINGS_DOWN_KEYWORDS = ("业绩暴雷", "亏损", "预亏", "净利润下滑")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _event_id(doc_id: str) -> str:
    digest = hashlib.sha256(doc_id.encode("utf-8")).hexdigest()[:20]
    return f"evt_{digest}"


def _cluster_id(event_type: str, event_subtype: str, knowable_time: datetime) -> str:
    raw = f"{event_type}|{event_subtype}|{knowable_time.date().isoformat()}"
    return f"clu_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _mention_id(cluster_id: str, doc_id: str) -> str:
    raw = f"{cluster_id}|{doc_id}"
    return f"men_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _short_summary(title: str, content: str, fallback: str | None = None) -> str:
    if fallback and fallback.strip():
        return fallback.strip()[:500]
    cleaned = re.sub(r"\s+", " ", content).strip()
    if cleaned:
        return cleaned[:180]
    return title.strip()[:180]


def _normalize_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if value is None:
        raise EventExtractionError("原始文档缺少发布时间或抓取时间")
    raw = str(value).strip()
    if not raw:
        raise EventExtractionError("原始文档缺少发布时间或抓取时间")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _next_weekday(value: datetime) -> datetime:
    candidate = value
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _tradable_time(knowable_time: datetime) -> datetime:
    morning_open = time(9, 30)
    candidate = _next_weekday(knowable_time)
    if candidate.date() != knowable_time.date():
        return datetime.combine(candidate.date(), morning_open)
    if knowable_time.time() < morning_open:
        return datetime.combine(candidate.date(), morning_open)
    next_day = _next_weekday(candidate + timedelta(days=1))
    return datetime.combine(next_day.date(), morning_open)


def _classify_event(source_type: str, text: str) -> tuple[str, str, str | None]:
    if _contains_any(text, EARNINGS_UP_KEYWORDS):
        return "业绩预增", "业绩预增", None
    if _contains_any(text, EARNINGS_DOWN_KEYWORDS):
        return "业绩暴雷", "业绩暴雷", None
    if _contains_any(text, CONTRACT_KEYWORDS):
        return "重大合同", "重大合同", None
    if _contains_any(text, MNA_KEYWORDS):
        return "并购重组", "并购重组", None
    if _contains_any(text, BUYBACK_KEYWORDS):
        return "回购增持", "回购增持", None
    if _contains_any(text, REDUCE_KEYWORDS):
        return "减持解禁", "减持解禁", None
    if _contains_any(text, PUNISH_KEYWORDS):
        return "监管处罚", "监管处罚", None
    if source_type == "announcement" or "公告" in text:
        return "公司公告", "上市公司公告", None
    if source_type == "policy" or _contains_any(text, POLICY_KEYWORDS):
        subtype = "AI算力" if _contains_any(text, AI_KEYWORDS) else "产业政策"
        policy_level = "national" if _contains_any(text, ("国务院", "国家", "部委", "证监会")) else "local_or_industry"
        return "政策", subtype, policy_level
    if _contains_any(text, MACRO_KEYWORDS):
        return "宏观金融", "宏观流动性", None
    if _contains_any(text, CONFLICT_KEYWORDS):
        return "军事地缘", "地缘冲突", None
    if _contains_any(text, AI_KEYWORDS):
        return "产业新闻", "AI算力", None
    if _contains_any(text, ROBOT_KEYWORDS):
        return "产业新闻", "机器人", None
    if _contains_any(text, SEMI_KEYWORDS):
        return "技术突破", "半导体", None
    if _contains_any(text, EV_KEYWORDS):
        return "产业新闻", "新能源", None
    if source_type == "social_hot" or _contains_any(text, CONSUMER_KEYWORDS):
        subtype = "文娱消费" if _contains_any(text, CONSUMER_KEYWORDS) else "公开热榜"
        return "社会热点", subtype, None
    if source_type == "international_news":
        return "国际冲突", "海外事件", None
    return "产业新闻", "综合事件", None


def _sentiment(text: str) -> str:
    positive = _contains_any(text, POSITIVE_KEYWORDS)
    negative = _contains_any(text, NEGATIVE_KEYWORDS)
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "neutral"


def _intensity(source_type: str, hot_rank: int | None, hot_value: float | None, text: str) -> int:
    score = 2
    if source_type in {"policy", "announcement"}:
        score += 1
    if hot_rank is not None and hot_rank <= 10:
        score += 1
    if hot_value is not None and hot_value >= 80:
        score += 1
    if _contains_any(text, ("重大", "国家级", "首次", "突破", "暴雷", "处罚")):
        score += 1
    return max(1, min(score, 5))


def _novelty(text: str) -> int:
    if _contains_any(text, ("首次", "突破", "新规", "试点", "首个", "重磅")):
        return 5
    if _contains_any(text, ("发布", "启动", "中标", "签约")):
        return 4
    return 3


def _a_share_relevance(source_type: str, event_type: str, event_subtype: str, text: str) -> float:
    score = 0.35
    if source_type in {"policy", "announcement", "finance_news"}:
        score += 0.2
    if event_type in {"政策", "产业新闻", "技术突破", "公司公告", "业绩预增", "业绩暴雷", "重大合同", "并购重组"}:
        score += 0.2
    if event_subtype in {"AI算力", "机器人", "半导体", "新能源", "产业政策"}:
        score += 0.2
    if re.search(r"\b\d{6}\.(SH|SZ)\b", text, flags=re.IGNORECASE):
        score += 0.15
    if _contains_any(text, ("A股", "板块", "上市公司", "产业链", "概念", "股票")):
        score += 0.15
    if event_type in {"社会热点", "娱乐热点"} and score < 0.45:
        score = 0.45 if _contains_any(text, CONSUMER_KEYWORDS) else score
    return round(min(score, 1.0), 2)


def _certainty(source_type: str, relevance: float, content: str) -> float:
    score = 0.55 + min(len(content), 800) / 4000
    if source_type in {"policy", "announcement"}:
        score += 0.15
    score += relevance * 0.15
    return round(min(score, 0.95), 2)


def _mention_weight(credibility: float | None, hot_rank: int | None, hot_value: float | None) -> float:
    score = float(credibility or 0.5)
    if hot_rank is not None:
        score += max(0.0, (50 - min(hot_rank, 50)) / 100)
    if hot_value is not None:
        score += min(float(hot_value), 100.0) / 200
    return round(min(score, 1.5), 3)


def _row_to_event(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "event_id": row[0],
        "cluster_id": row[1],
        "doc_id": row[2],
        "event_time": row[3].isoformat() if row[3] else None,
        "publish_time": row[4].isoformat() if row[4] else None,
        "crawl_time": row[5].isoformat() if row[5] else None,
        "knowable_time": row[6].isoformat() if row[6] else None,
        "tradable_time": row[7].isoformat() if row[7] else None,
        "event_type": row[8],
        "event_subtype": row[9],
        "summary": row[10],
        "sentiment": row[11],
        "intensity": row[12],
        "novelty": row[13],
        "certainty": row[14],
        "a_share_relevance_score": row[15],
        "policy_level": row[16],
        "created_at": row[17].isoformat() if row[17] else None,
    }


def _row_to_cluster(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "cluster_id": row[0],
        "first_seen_time": row[1].isoformat() if row[1] else None,
        "last_seen_time": row[2].isoformat() if row[2] else None,
        "main_title": row[3],
        "event_type": row[4],
        "event_subtype": row[5],
        "summary": row[6],
        "sentiment": row[7],
        "intensity": row[8],
        "novelty": row[9],
        "hot_score": row[10],
        "a_share_relevance_score": row[11],
        "source_count": row[12],
        "mention_count": row[13],
        "cross_platform_score": row[14],
        "status": row[15],
        "created_at": row[16].isoformat() if row[16] else None,
        "updated_at": row[17].isoformat() if row[17] else None,
    }


class EventExtractionService:
    """Extract structured events and clusters from PR-05 raw documents."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def extract_events(self, *, limit: int = 100, min_relevance: float = 0.0) -> dict[str, Any]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 500)
        min_score = min(max(float(min_relevance), 0.0), 1.0)
        now = _utc_now()
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT rd.doc_id, rd.source_id, rd.source_name, rd.source_type,
                       rd.title, rd.content, rd.summary, rd.publish_time, rd.crawl_time,
                       rd.hot_rank, rd.hot_value, rd.credibility
                FROM raw_documents rd
                LEFT JOIN events e ON e.doc_id = rd.doc_id
                WHERE e.event_id IS NULL
                ORDER BY rd.publish_time ASC, rd.crawl_time ASC
                LIMIT ?
                """,
                [capped_limit],
            ).fetchall()
            if not rows:
                raise EventExtractionError("没有可抽取的原始文档，请先运行事件采集。")

            extracted = [self._extract_from_raw_row(row) for row in rows]
            eligible = [event for event in extracted if event.a_share_relevance_score >= min_score]
            for event in eligible:
                self._upsert_event(conn, event, now)
                self._upsert_mention(conn, event, now)
                self._refresh_cluster(conn, event.cluster_id, now)

        return {
            "status": "ok",
            "requested": len(rows),
            "extracted": len(eligible),
            "skipped_low_relevance": len(extracted) - len(eligible),
            "event_ids": [event.event_id for event in eligible],
            "cluster_ids": sorted({event.cluster_id for event in eligible}),
        }

    def list_events(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
        min_relevance: float = 0.0,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 200)
        min_score = min(max(float(min_relevance), 0.0), 1.0)
        filters = ["a_share_relevance_score >= ?"]
        params: list[Any] = [min_score]
        if event_type:
            filters.append("event_type = ?")
            params.append(event_type.strip())
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, cluster_id, doc_id, event_time, publish_time, crawl_time,
                       knowable_time, tradable_time, event_type, event_subtype, summary,
                       sentiment, intensity, novelty, certainty, a_share_relevance_score,
                       policy_level, created_at
                FROM events
                WHERE {' AND '.join(filters)}
                ORDER BY knowable_time DESC, event_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def list_clusters(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        min_relevance: float = 0.0,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 200)
        min_score = min(max(float(min_relevance), 0.0), 1.0)
        filters = ["a_share_relevance_score >= ?"]
        params: list[Any] = [min_score]
        if status:
            normalized = status.strip().lower()
            if normalized not in {"active", "fading", "archived"}:
                raise EventExtractionError("cluster status 只支持 active、fading 或 archived")
            filters.append("status = ?")
            params.append(normalized)
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT cluster_id, first_seen_time, last_seen_time, main_title,
                       event_type, event_subtype, summary, sentiment, intensity,
                       novelty, hot_score, a_share_relevance_score, source_count,
                       mention_count, cross_platform_score, status, created_at, updated_at
                FROM event_clusters
                WHERE {' AND '.join(filters)}
                ORDER BY last_seen_time DESC, hot_score DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_cluster(row) for row in rows]

    def get_cluster(self, cluster_id: str) -> dict[str, Any]:
        normalized = cluster_id.strip()
        if not normalized.startswith("clu_") or len(normalized) > 64:
            raise EventExtractionError("cluster_id 格式无效")
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            cluster = conn.execute(
                """
                SELECT cluster_id, first_seen_time, last_seen_time, main_title,
                       event_type, event_subtype, summary, sentiment, intensity,
                       novelty, hot_score, a_share_relevance_score, source_count,
                       mention_count, cross_platform_score, status, created_at, updated_at
                FROM event_clusters
                WHERE cluster_id = ?
                """,
                [normalized],
            ).fetchone()
            if cluster is None:
                raise EventExtractionError(f"未找到事件聚类: {normalized}")
            events = conn.execute(
                """
                SELECT event_id, cluster_id, doc_id, event_time, publish_time, crawl_time,
                       knowable_time, tradable_time, event_type, event_subtype, summary,
                       sentiment, intensity, novelty, certainty, a_share_relevance_score,
                       policy_level, created_at
                FROM events
                WHERE cluster_id = ?
                ORDER BY knowable_time, event_id
                """,
                [normalized],
            ).fetchall()
        body = _row_to_cluster(cluster)
        body["events"] = [_row_to_event(row) for row in events]
        return body

    @staticmethod
    def _extract_from_raw_row(row: tuple[Any, ...]) -> ExtractedEvent:
        (
            doc_id,
            source_id,
            source_name,
            source_type,
            title,
            content,
            source_summary,
            publish_time_raw,
            crawl_time_raw,
            hot_rank,
            hot_value,
            credibility,
        ) = row
        title = str(title or "").strip()
        content = str(content or "").strip()
        if not title or not content:
            raise EventExtractionError(f"原始文档缺少标题或正文: {doc_id}")
        publish_time = _normalize_time(publish_time_raw)
        crawl_time = _normalize_time(crawl_time_raw)
        knowable_time = max(publish_time, crawl_time)
        tradable_time = _tradable_time(knowable_time)
        text = f"{title}\n{content}"
        event_type, event_subtype, policy_level = _classify_event(str(source_type or ""), text)
        relevance = _a_share_relevance(str(source_type or ""), event_type, event_subtype, text)
        cluster_id = _cluster_id(event_type, event_subtype, knowable_time)
        return ExtractedEvent(
            doc_id=str(doc_id),
            cluster_id=cluster_id,
            event_id=_event_id(str(doc_id)),
            event_time=publish_time,
            publish_time=publish_time,
            crawl_time=crawl_time,
            knowable_time=knowable_time,
            tradable_time=tradable_time,
            event_type=event_type,
            event_subtype=event_subtype,
            summary=_short_summary(title, content, source_summary),
            sentiment=_sentiment(text),
            intensity=_intensity(str(source_type or ""), hot_rank, hot_value, text),
            novelty=_novelty(text),
            certainty=_certainty(str(source_type or ""), relevance, content),
            a_share_relevance_score=relevance,
            policy_level=policy_level,
            source_id=str(source_id),
            source_name=str(source_name),
            hot_rank=hot_rank,
            hot_value=hot_value,
            mention_weight=_mention_weight(credibility, hot_rank, hot_value),
        )

    @staticmethod
    def _upsert_event(conn: Any, event: ExtractedEvent, now: datetime) -> None:
        try:
            conn.execute(
                """
                INSERT INTO events (
                  event_id, cluster_id, doc_id, event_time, publish_time, crawl_time,
                  knowable_time, tradable_time, event_type, event_subtype, summary,
                  sentiment, intensity, novelty, certainty, a_share_relevance_score,
                  policy_level, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    event.event_id,
                    event.cluster_id,
                    event.doc_id,
                    event.event_time,
                    event.publish_time,
                    event.crawl_time,
                    event.knowable_time,
                    event.tradable_time,
                    event.event_type,
                    event.event_subtype,
                    event.summary,
                    event.sentiment,
                    event.intensity,
                    event.novelty,
                    event.certainty,
                    event.a_share_relevance_score,
                    event.policy_level,
                    now,
                ],
            )
        except Exception:
            existing = conn.execute("SELECT event_id FROM events WHERE event_id = ?", [event.event_id]).fetchone()
            if existing is None:
                raise

    @staticmethod
    def _upsert_mention(conn: Any, event: ExtractedEvent, now: datetime) -> None:
        mention_id = _mention_id(event.cluster_id, event.doc_id)
        try:
            conn.execute(
                """
                INSERT INTO event_mentions (
                  mention_id, cluster_id, doc_id, source_id, source_name,
                  publish_time, crawl_time, hot_rank, hot_value, mention_weight, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    mention_id,
                    event.cluster_id,
                    event.doc_id,
                    event.source_id,
                    event.source_name,
                    event.publish_time,
                    event.crawl_time,
                    event.hot_rank,
                    event.hot_value,
                    event.mention_weight,
                    now,
                ],
            )
        except Exception:
            existing = conn.execute("SELECT mention_id FROM event_mentions WHERE mention_id = ?", [mention_id]).fetchone()
            if existing is None:
                raise

    @staticmethod
    def _refresh_cluster(conn: Any, cluster_id: str, now: datetime) -> None:
        event_rows = conn.execute(
            """
            SELECT event_type, event_subtype, summary, sentiment, intensity, novelty,
                   a_share_relevance_score, knowable_time
            FROM events
            WHERE cluster_id = ?
            ORDER BY knowable_time, event_id
            """,
            [cluster_id],
        ).fetchall()
        if not event_rows:
            return
        mention_rows = conn.execute(
            """
            SELECT source_id, mention_weight, publish_time
            FROM event_mentions
            WHERE cluster_id = ?
            """,
            [cluster_id],
        ).fetchall()
        source_count = len({row[0] for row in mention_rows})
        mention_count = len(mention_rows)
        hot_score = round(sum(float(row[1] or 0) for row in mention_rows), 3)
        cross_platform_score = round(min(1.0, source_count / 3), 3)
        first_seen = min(row[7] for row in event_rows if row[7] is not None)
        last_seen = max(row[7] for row in event_rows if row[7] is not None)
        primary = max(event_rows, key=lambda row: (float(row[6] or 0), int(row[4] or 0), int(row[5] or 0)))
        status = "active" if now - last_seen <= timedelta(days=2) else "fading"
        existing = conn.execute("SELECT cluster_id, created_at FROM event_clusters WHERE cluster_id = ?", [cluster_id]).fetchone()
        created_at = existing[1] if existing and existing[1] else now
        if existing is not None:
            conn.execute("DELETE FROM event_clusters WHERE cluster_id = ?", [cluster_id])
        cluster_sql = """
            INSERT INTO event_clusters (
              cluster_id, first_seen_time, last_seen_time, main_title,
              event_type, event_subtype, summary, sentiment, intensity, novelty,
              hot_score, a_share_relevance_score, source_count, mention_count,
              cross_platform_score, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        cluster_values = [
            cluster_id,
            first_seen,
            last_seen,
            str(primary[2])[:120],
            primary[0],
            primary[1],
            primary[2],
            primary[3],
            max(int(row[4] or 1) for row in event_rows),
            max(int(row[5] or 1) for row in event_rows),
            hot_score,
            round(max(float(row[6] or 0) for row in event_rows), 2),
            source_count,
            mention_count,
            cross_platform_score,
            status,
            created_at,
            now,
        ]
        try:
            conn.execute(cluster_sql, cluster_values)
        except Exception:
            if conn.execute("SELECT cluster_id FROM event_clusters WHERE cluster_id = ?", [cluster_id]).fetchone() is None:
                raise
            conn.execute("DELETE FROM event_clusters WHERE cluster_id = ?", [cluster_id])
            conn.execute(cluster_sql, cluster_values)
