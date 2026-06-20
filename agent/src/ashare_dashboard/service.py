"""Presentation-layer summaries for the Codex-commanded A-share workflow."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore
from src.event_radar.source_ingestion import EventSourceIngestionService


class AShareDashboardError(RuntimeError):
    """Raised when dashboard summaries cannot be built."""


def _today() -> date:
    return datetime.now(timezone.utc).date()


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
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise AShareDashboardError(f"{field_name} 必须是 YYYY-MM-DD 格式") from exc


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


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value * 100, 2)


class AShareDashboardService:
    """Build dashboard payloads for low-interaction, chart-first pages."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def daily_intelligence(self, *, as_of_date: str | date | datetime | None = None) -> dict[str, Any]:
        """Return today's market intelligence summary for the home page."""
        self.store.initialize()
        EventSourceIngestionService(store=self.store).ensure_default_sources()
        as_of = _parse_date(as_of_date, "as_of_date")
        with self.store.connect(read_only=True) as conn:
            effective_date = as_of or self._latest_activity_date(conn) or _today()
            sector_rows = self._sector_scores(conn, effective_date)
            event_rows = self._recent_events(conn, effective_date, limit=6)
            source_rows = self._sources(conn)
            market_rows = self._market_metrics(conn, effective_date)

        sample_mode = not sector_rows and not event_rows and not market_rows
        sectors = sector_rows or _sample_sector_heat(effective_date)
        events = event_rows or _sample_events(effective_date)
        metrics = market_rows or _sample_market_metrics()
        temperature = _market_temperature(sectors=sectors, events=events)
        source_freshness = _source_freshness(source_rows)

        return {
            "status": "ok",
            "as_of_date": effective_date.isoformat(),
            "data_mode": "sample" if sample_mode else "local",
            "headline": _headline(temperature, sectors),
            "market_temperature": temperature,
            "market_metrics": metrics,
            "sector_heat": sectors,
            "event_timeline": events,
            "source_freshness": source_freshness,
            "codex_actions": [
                "让 Codex 基于今日热点生成候选策略卡",
                "让 Codex 将候选策略送入聚宽任务中心",
                "让 Codex 汇总缺失数据源并给出补采建议",
            ],
            "warnings": _warnings(sample_mode, source_freshness),
            "research_only": True,
            "live_trading": False,
        }

    def sector_stock_analysis(self, *, as_of_date: str | date | datetime | None = None, theme: str | None = None) -> dict[str, Any]:
        """Return sector, candidate-stock, and strategy-card presentation data."""
        self.store.initialize()
        as_of = _parse_date(as_of_date, "as_of_date")
        clean_theme = theme.strip() if theme else None
        with self.store.connect(read_only=True) as conn:
            effective_date = as_of or self._latest_candidate_or_sector_date(conn) or _today()
            sector_rows = self._sector_scores(conn, effective_date)
            candidate_rows = self._candidate_pool(conn, effective_date, clean_theme)
            idea_rows = self._strategy_ideas(conn, effective_date, clean_theme)

        sample_mode = not sector_rows and not candidate_rows and not idea_rows
        sectors = sector_rows or _sample_sector_heat(effective_date)
        candidates = candidate_rows or _sample_candidates()
        ideas = idea_rows or _sample_ideas(effective_date, clean_theme or "AI算力")
        selected_theme = clean_theme or _dominant_theme(candidates, sectors)

        return {
            "status": "ok",
            "as_of_date": effective_date.isoformat(),
            "theme": selected_theme,
            "data_mode": "sample" if sample_mode else "local",
            "sector_score": _sector_score(selected_theme, sectors),
            "sector_rankings": sectors,
            "candidate_matrix": _candidate_matrix(candidates),
            "candidate_pool": candidates,
            "strategy_ideas": ideas,
            "codex_actions": [
                "让 Codex 生成多类型候选策略",
                "让 Codex 选择 3 张策略卡创建聚宽任务",
                "让 Codex 解释候选股票进入观察池的证据链",
            ],
            "research_only": True,
            "live_trading": False,
        }

    @staticmethod
    def _latest_activity_date(conn: Any) -> date | None:
        for sql in (
            "SELECT MAX(trade_date) FROM sector_scores",
            "SELECT MAX(knowable_time::DATE) FROM events",
            "SELECT MAX(trade_date) FROM market_daily",
        ):
            row = conn.execute(sql).fetchone()
            if row and row[0]:
                return row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0])[:10])
        return None

    @staticmethod
    def _latest_candidate_or_sector_date(conn: Any) -> date | None:
        for sql in (
            "SELECT MAX(as_of_date) FROM candidate_pool",
            "SELECT MAX(trade_date) FROM sector_scores",
        ):
            row = conn.execute(sql).fetchone()
            if row and row[0]:
                return row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0])[:10])
        return None

    @staticmethod
    def _sector_scores(conn: Any, as_of: date) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT sector_id, sector_name, event_heat, market_confirm, breadth_score,
                   flow_score, persistence_score, crowding_risk, sector_heat_score,
                   cycle_stage, created_at
            FROM sector_scores
            WHERE trade_date = ?
            ORDER BY sector_heat_score DESC, sector_name
            LIMIT 12
            """,
            [as_of],
        ).fetchall()
        return [
            {
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
                "created_at": _iso(row[10]),
            }
            for row in rows
        ]

    @staticmethod
    def _recent_events(conn: Any, as_of: date, *, limit: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT e.event_id, e.event_subtype, e.summary, e.knowable_time,
                   e.a_share_relevance_score, e.certainty,
                   rd.source_name, rd.source_type, rd.url
            FROM events e
            LEFT JOIN raw_documents rd ON rd.doc_id = e.doc_id
            WHERE e.knowable_time::DATE <= ?
            ORDER BY e.knowable_time DESC, e.a_share_relevance_score DESC
            LIMIT ?
            """,
            [as_of, min(max(limit, 1), 20)],
        ).fetchall()
        return [
            {
                "event_id": row[0],
                "theme": row[1],
                "summary": row[2],
                "time": _iso(row[3]),
                "relevance": _float(row[4]),
                "certainty": _float(row[5]),
                "source_name": row[6] or "本地事件库",
                "source_type": row[7] or "local",
                "source_url": row[8],
                "verification_status": "已核验" if _float(row[5]) >= 0.7 else "待核验",
            }
            for row in rows
        ]

    @staticmethod
    def _sources(conn: Any) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT source_id, source_name, source_type, credibility, enabled, last_fetch_time
            FROM source_registry
            ORDER BY source_type, source_id
            """
        ).fetchall()
        return [
            {
                "source_id": row[0],
                "source_name": row[1],
                "source_type": row[2],
                "credibility": _float(row[3]),
                "enabled": bool(row[4]),
                "last_fetch_time": _iso(row[5]),
            }
            for row in rows
        ]

    @staticmethod
    def _market_metrics(conn: Any, as_of: date) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT ticker, close, volume, amount, limit_status, source
            FROM market_daily
            WHERE trade_date = ?
            ORDER BY amount DESC NULLS LAST
            LIMIT 200
            """,
            [as_of],
        ).fetchall()
        if not rows:
            return []
        limit_up = sum(1 for row in rows if row[4] == "limit_up")
        return [
            {"label": "样本股票", "value": str(len(rows)), "delta": "本地", "tone": "info"},
            {"label": "涨停数量", "value": str(limit_up), "delta": "已入库", "tone": "success"},
            {"label": "成交额样本", "value": f"{round(sum(_float(row[3]) for row in rows) / 100000000, 1)}亿", "delta": rows[0][5] or "local", "tone": "info"},
            {"label": "数据新鲜度", "value": as_of.isoformat(), "delta": "T日", "tone": "success"},
        ]

    @staticmethod
    def _candidate_pool(conn: Any, as_of: date, theme: str | None) -> list[dict[str, Any]]:
        filters = ["as_of_date = ?"]
        params: list[Any] = [as_of]
        if theme:
            filters.append("theme = ?")
            params.append(theme)
        rows = conn.execute(
            f"""
            SELECT ticker, ticker_name, sector_id, sector_name, theme,
                   event_heat_score, sector_heat_score, stock_score,
                   risk_flag, included, reason, source
            FROM candidate_pool
            WHERE {' AND '.join(filters)}
            ORDER BY included DESC, stock_score DESC, ticker
            LIMIT 20
            """,
            params,
        ).fetchall()
        return [
            {
                "ticker": row[0],
                "ticker_name": row[1],
                "sector_id": row[2],
                "sector_name": row[3],
                "theme": row[4],
                "event_heat_score": _float(row[5]),
                "sector_heat_score": _float(row[6]),
                "stock_score": _float(row[7]),
                "risk_flag": row[8] or "normal",
                "included": bool(row[9]),
                "reason": row[10] or "",
                "source": row[11] or "local",
            }
            for row in rows
        ]

    @staticmethod
    def _strategy_ideas(conn: Any, as_of: date, theme: str | None) -> list[dict[str, Any]]:
        filters = ["as_of_date = ?"]
        params: list[Any] = [as_of]
        if theme:
            filters.append("theme = ?")
            params.append(theme)
        rows = conn.execute(
            f"""
            SELECT idea_id, theme, strategy_type, strategy_name, strategy_family,
                   idea_category, idea_score, status, thesis, candidate_tickers_json,
                   entry_rules_json, exit_rules_json, risk_controls_json
            FROM strategy_ideas
            WHERE {' AND '.join(filters)}
            ORDER BY idea_score DESC, strategy_type
            LIMIT 12
            """,
            params,
        ).fetchall()
        return [
            {
                "idea_id": row[0],
                "theme": row[1],
                "strategy_type": row[2],
                "strategy_name": row[3],
                "strategy_family": row[4],
                "idea_category": row[5],
                "idea_score": _float(row[6]),
                "status": row[7],
                "thesis": row[8],
                "candidate_tickers": _json_loads(row[9], []),
                "entry_rules": _json_loads(row[10], []),
                "exit_rules": _json_loads(row[11], []),
                "risk_controls": _json_loads(row[12], []),
            }
            for row in rows
        ]


def _market_temperature(*, sectors: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    heat = sum(_float(row.get("sector_heat_score")) for row in sectors[:5]) / max(min(len(sectors), 5), 1)
    relevance = sum(_float(row.get("relevance")) for row in events[:5]) / max(min(len(events), 5), 1)
    score = round(min(100, max(0, heat * 78 + relevance * 22)), 1)
    if score >= 80:
        label = "高热，需要防追高"
    elif score >= 65:
        label = "偏热，适合生成候选策略"
    elif score >= 45:
        label = "中性，等待确认"
    else:
        label = "偏冷，控制交易频率"
    return {"score": score, "label": label, "heat": heat, "event_relevance": relevance}


def _headline(temperature: dict[str, Any], sectors: list[dict[str, Any]]) -> str:
    leader = sectors[0]["sector_name"] if sectors else "A股市场"
    return f"{leader}处于{temperature['label']}状态，建议先形成候选策略并送聚宽验证。"


def _warnings(sample_mode: bool, source_freshness: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if sample_mode:
        warnings.append("当前页面使用样例结构数据；请先完成数据采集后再作为研究依据。")
    stale = [row["source_name"] for row in source_freshness if row["status"] == "待采集"]
    if stale:
        warnings.append(f"{len(stale)} 个信息源尚未采集，Codex 可先执行补采任务。")
    return warnings


def _source_freshness(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        grouped.setdefault(str(source["source_type"]), []).append(source)
    freshness = []
    for source_type, rows in sorted(grouped.items()):
        enabled = [row for row in rows if row["enabled"]]
        fetched = [row for row in enabled if row["last_fetch_time"]]
        avg_credibility = sum(row["credibility"] for row in rows) / max(len(rows), 1)
        freshness.append({
            "source_type": source_type,
            "source_name": _source_type_label(source_type),
            "enabled_count": len(enabled),
            "source_count": len(rows),
            "fetched_count": len(fetched),
            "credibility": round(avg_credibility, 2),
            "status": "正常" if fetched else "待采集",
        })
    return freshness


def _source_type_label(source_type: str) -> str:
    return {
        "policy": "官方政策",
        "regulatory": "监管公告",
        "exchange": "交易所信息",
        "announcement": "公司公告",
        "market_data": "行情板块",
        "finance_news": "财经媒体",
        "social_hot": "社交线索",
        "international_news": "国际新闻",
    }.get(source_type, source_type)


def _sector_score(theme: str, sectors: list[dict[str, Any]]) -> dict[str, Any]:
    selected = next((row for row in sectors if row["sector_name"] == theme or row["sector_id"] == theme), sectors[0])
    score = round(_float(selected["sector_heat_score"]) * 100, 1)
    return {
        "theme": selected["sector_name"],
        "score": score,
        "summary": f"{selected['sector_name']}热度较高，适合先生成候选策略卡，再通过聚宽验证规则。",
        "badges": ["事件驱动强", "板块扩散中", "需防追高" if _float(selected["crowding_risk"]) >= 0.55 else "风险可控"],
    }


def _dominant_theme(candidates: list[dict[str, Any]], sectors: list[dict[str, Any]]) -> str:
    counts = Counter(row.get("theme") or row.get("sector_name") for row in candidates)
    if counts:
        return str(counts.most_common(1)[0][0])
    return sectors[0]["sector_name"] if sectors else "AI算力"


def _candidate_matrix(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in candidates[:12]:
        score = _float(item.get("stock_score"))
        rows.append({
            "ticker": item["ticker"],
            "ticker_name": item["ticker_name"],
            "sector_name": item.get("sector_name") or item.get("theme") or "综合",
            "leader_score": round(score * 0.95, 3),
            "order_score": round(_float(item.get("event_heat_score")) * 0.9, 3),
            "catch_up_score": round((1 - min(score, 1)) * _float(item.get("sector_heat_score")), 3),
            "crowding_flag": item.get("risk_flag") != "normal",
        })
    return rows


def _sample_market_metrics() -> list[dict[str, Any]]:
    return [
        {"label": "上证指数", "value": "样例", "delta": "待采集", "tone": "warning"},
        {"label": "沪深300", "value": "样例", "delta": "待采集", "tone": "warning"},
        {"label": "成交额", "value": "样例", "delta": "待采集", "tone": "warning"},
        {"label": "涨停数量", "value": "样例", "delta": "待采集", "tone": "warning"},
    ]


def _sample_sector_heat(as_of: date) -> list[dict[str, Any]]:
    names = [
        ("theme_ai_compute", "AI算力", 0.88, 0.72, 0.64, 0.58),
        ("theme_optical_module", "光模块", 0.81, 0.68, 0.59, 0.62),
        ("theme_server", "服务器", 0.73, 0.61, 0.55, 0.44),
        ("theme_robotics", "机器人", 0.58, 0.52, 0.48, 0.36),
        ("theme_innovative_drug", "创新药", 0.46, 0.42, 0.38, 0.28),
    ]
    return [
        {
            "sector_id": sector_id,
            "sector_name": name,
            "event_heat": heat,
            "market_confirm": confirm,
            "breadth_score": breadth,
            "flow_score": round((heat + confirm) / 2, 3),
            "persistence_score": round((heat + breadth) / 2, 3),
            "crowding_risk": crowding,
            "sector_heat_score": heat,
            "cycle_stage": "sample",
            "created_at": as_of.isoformat(),
        }
        for sector_id, name, heat, confirm, breadth, crowding in names
    ]


def _sample_events(as_of: date) -> list[dict[str, Any]]:
    return [
        {"event_id": "sample_evt_ai_1", "theme": "AI算力", "summary": "国产算力招标扩容进入市场关注区。", "time": f"{as_of.isoformat()}T09:45:00", "relevance": 0.88, "certainty": 0.72, "source_name": "样例事件库", "source_type": "sample", "source_url": None, "verification_status": "样例"},
        {"event_id": "sample_evt_ai_2", "theme": "光模块", "summary": "海外AI芯片需求预期上修带动光模块关注。", "time": f"{as_of.isoformat()}T10:30:00", "relevance": 0.82, "certainty": 0.68, "source_name": "样例事件库", "source_type": "sample", "source_url": None, "verification_status": "样例"},
        {"event_id": "sample_evt_ai_3", "theme": "液冷", "summary": "液冷服务器订单线索等待二次核验。", "time": f"{as_of.isoformat()}T13:15:00", "relevance": 0.64, "certainty": 0.52, "source_name": "样例事件库", "source_type": "sample", "source_url": None, "verification_status": "待核验"},
    ]


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {"ticker": "300308.SZ", "ticker_name": "中际旭创", "sector_id": "theme_optical_module", "sector_name": "光模块", "theme": "AI算力", "event_heat_score": 0.88, "sector_heat_score": 0.81, "stock_score": 0.91, "risk_flag": "normal", "included": True, "reason": "光模块龙头，AI算力链高相关。", "source": "sample"},
        {"ticker": "300502.SZ", "ticker_name": "新易盛", "sector_id": "theme_optical_module", "sector_name": "光模块", "theme": "AI算力", "event_heat_score": 0.84, "sector_heat_score": 0.80, "stock_score": 0.88, "risk_flag": "normal", "included": True, "reason": "业绩弹性与光模块景气相关。", "source": "sample"},
        {"ticker": "000977.SZ", "ticker_name": "浪潮信息", "sector_id": "theme_server", "sector_name": "服务器", "theme": "AI算力", "event_heat_score": 0.76, "sector_heat_score": 0.73, "stock_score": 0.82, "risk_flag": "normal", "included": True, "reason": "服务器产业链代表性标的。", "source": "sample"},
        {"ticker": "601138.SH", "ticker_name": "工业富联", "sector_id": "theme_server", "sector_name": "服务器", "theme": "AI算力", "event_heat_score": 0.72, "sector_heat_score": 0.70, "stock_score": 0.78, "risk_flag": "normal", "included": True, "reason": "AI服务器链条关注度较高。", "source": "sample"},
        {"ticker": "688256.SH", "ticker_name": "寒武纪", "sector_id": "theme_ai_compute", "sector_name": "AI算力", "theme": "AI算力", "event_heat_score": 0.82, "sector_heat_score": 0.88, "stock_score": 0.74, "risk_flag": "high_volatility", "included": True, "reason": "算力芯片弹性高，波动也高。", "source": "sample"},
    ]


def _sample_ideas(as_of: date, theme: str) -> list[dict[str, Any]]:
    return [
        {"idea_id": "sample_hot_momentum", "theme": theme, "strategy_type": "hot_sector_momentum", "strategy_name": f"{theme}热点板块动量", "strategy_family": "板块轮动", "idea_category": "热点板块动量", "idea_score": 82.0, "status": "candidate", "thesis": "高热板块内选择强势股，严格控制仓位。", "candidate_tickers": _sample_candidates()[:3], "entry_rules": ["板块热度排名前 3", "股票强度排名前 5"], "exit_rules": ["持有 5 个交易日后复评"], "risk_controls": ["单股不超过 8%", "高拥挤时暂停新增"]},
        {"idea_id": "sample_event_confirm", "theme": theme, "strategy_type": "event_confirm_follow", "strategy_name": f"{theme}事件确认后跟随", "strategy_family": "事件驱动", "idea_category": "事件确认", "idea_score": 76.0, "status": "candidate", "thesis": "事件入库后等待价格确认再进入观察。", "candidate_tickers": _sample_candidates()[1:4], "entry_rules": ["事件已核验", "价格突破近期平台"], "exit_rules": ["事件热度回落退出"], "risk_controls": ["未核验线索不参与"]},
        {"idea_id": "sample_pullback", "theme": theme, "strategy_type": "pullback_restart", "strategy_name": f"{theme}高热回调再启动", "strategy_family": "趋势回调", "idea_category": "回调再启动", "idea_score": 71.0, "status": "candidate", "thesis": "等待热点板块回调到均线附近后观察再启动信号。", "candidate_tickers": _sample_candidates()[2:], "entry_rules": ["板块热度保持前 5", "个股回调但未破趋势"], "exit_rules": ["跌破风控线"], "risk_controls": ["不追高买入"]},
    ]
