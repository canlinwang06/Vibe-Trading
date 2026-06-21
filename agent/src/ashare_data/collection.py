"""Public-data collectors for the A-share event strategy workbench.

The collectors use free public data adapters first and keep every run local.
They never require an OpenAI API key and never submit trades.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from typing import Any, Iterable, Sequence

from src.ashare_data.market_data import AssetRecord, MarketDailyRecord, AShareMarketDataService
from src.ashare_data.store import AShareDataStore
from src.event_radar.event_extraction import EventExtractionError, EventExtractionService
from src.event_radar.source_ingestion import (
    EventSourceIngestionError,
    EventSourceIngestionService,
    RawDocumentRecord,
)
from src.market_policy import is_a_share_code, normalize_a_share_code


class AShareDataCollectionError(RuntimeError):
    """Raised when public-data collection cannot complete."""


@dataclass(frozen=True)
class StockSnapshotRecord:
    trade_date: date
    ticker: str
    ticker_name: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float | None = None
    turnover: float | None = None
    pct_change: float | None = None
    volume_ratio: float | None = None
    sector_name: str | None = None
    source: str = "akshare_public"
    raw_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class SectorSnapshotRecord:
    trade_date: date
    sector_id: str
    sector_name: str
    sector_type: str = "concept"
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    return_: float | None = None
    amount: float | None = None
    turnover: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    limit_up_count: int | None = None
    member_count: int | None = None
    leading_ticker: str | None = None
    source: str = "akshare_public"
    raw_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class StockAnomalyRecord:
    trade_date: date
    ticker: str
    ticker_name: str
    anomaly_type: str
    pct_change: float | None = None
    amount: float | None = None
    turnover: float | None = None
    volume_ratio: float | None = None
    limit_status: str = "normal"
    sector_name: str | None = None
    source: str = "akshare_public"
    evidence: dict[str, Any] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None, *, field_name: str) -> date:
    if value is None:
        return _utc_now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise AShareDataCollectionError(f"{field_name} 必须是 YYYY-MM-DD 格式。") from exc


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, default=str)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _first(row: dict[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None
    return parsed


def _ratio_or_none(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None:
        return None
    return parsed / 100 if abs(parsed) > 1 else parsed


def _int_or_none(value: Any) -> int | None:
    parsed = _float_or_none(value)
    return None if parsed is None else int(parsed)


def _ticker_from_raw(value: Any) -> str | None:
    text = _clean_text(value).upper()
    if not text:
        return None
    if re.fullmatch(r"\d{6}", text):
        if text.startswith(("6", "9")):
            return f"{text}.SH"
        if text.startswith(("0", "2", "3")):
            return f"{text}.SZ"
        if text.startswith(("4", "8")):
            return f"{text}.BJ"
    try:
        normalized = normalize_a_share_code(text)
    except ValueError:
        return None
    return normalized if is_a_share_code(normalized) else None


def _limit_status_from_pct(ticker: str, pct_change: float | None) -> str:
    if pct_change is None:
        return "normal"
    code = ticker.split(".", 1)[0]
    threshold = 0.198 if code.startswith(("300", "301", "688")) else 0.098
    if pct_change >= threshold:
        return "limit_up"
    if pct_change <= -threshold:
        return "limit_down"
    return "normal"


def _sector_id(name: str, sector_type: str) -> str:
    digest = hashlib.sha256(f"{sector_type}|{name}".encode("utf-8")).hexdigest()[:14]
    return f"{sector_type}_{digest}"


class AksharePublicDataFetcher:
    """Thin AKShare wrapper kept injectable for deterministic tests."""

    def fetch_stock_snapshot(self, *, limit: int = 500) -> list[dict[str, Any]]:
        import akshare as ak

        frame = ak.stock_zh_a_spot_em()
        if frame is None or frame.empty:
            return []
        return frame.head(max(int(limit), 1)).to_dict("records")

    def fetch_sector_snapshot(self, *, limit: int = 120) -> list[dict[str, Any]]:
        import akshare as ak

        frames = []
        for sector_type, loader in (
            ("industry", ak.stock_board_industry_name_em),
            ("concept", ak.stock_board_concept_name_em),
        ):
            try:
                frame = loader()
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            frame = frame.copy()
            frame["sector_type"] = sector_type
            frames.append(frame)
        if not frames:
            return []
        import pandas as pd

        combined = pd.concat(frames, ignore_index=True)
        return combined.head(max(int(limit), 1)).to_dict("records")

    def fetch_news_documents(
        self,
        *,
        symbols: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        limit: int = 50,
    ) -> list[RawDocumentRecord]:
        import akshare as ak

        documents: list[RawDocumentRecord] = []
        documents.extend(self._global_news(ak, limit=max(1, limit // 2)))
        remaining = max(0, limit - len(documents))
        if remaining:
            documents.extend(self._stock_news(ak, symbols=symbols or (), limit=remaining))
        return _filter_documents(documents, keywords=keywords, limit=limit)

    def fetch_announcement_documents(
        self,
        *,
        symbols: Sequence[str],
        start_date: date,
        end_date: date,
        limit: int = 50,
    ) -> list[RawDocumentRecord]:
        import akshare as ak

        records: list[RawDocumentRecord] = []
        for symbol in symbols:
            ticker = _ticker_from_raw(symbol)
            if ticker is None:
                continue
            try:
                frame = ak.stock_zh_a_disclosure_report_cninfo(
                    symbol=ticker.split(".", 1)[0],
                    market="沪深京",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                )
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            for raw in frame.head(max(limit - len(records), 0)).to_dict("records"):
                title = _clean_text(_first(raw, ("公告标题", "标题", "title", "公告名称")))
                if not title:
                    continue
                publish = _first(raw, ("公告时间", "发布时间", "日期", "publish_time")) or end_date.isoformat()
                url = _clean_text(_first(raw, ("公告链接", "链接", "url", "URL")))
                records.append(
                    RawDocumentRecord(
                        source_id="cninfo_announcement",
                        title=title,
                        content=f"{ticker} {title}",
                        summary=title[:180],
                        publish_time=str(publish),
                        url=url or None,
                        raw_json={"ticker": ticker, "source_payload": raw},
                    )
                )
                if len(records) >= limit:
                    return records
        return records

    @staticmethod
    def _global_news(ak: Any, *, limit: int) -> list[RawDocumentRecord]:
        records: list[RawDocumentRecord] = []
        try:
            frame = ak.stock_info_global_cls(symbol="全部")
        except Exception:
            frame = None
        if frame is None or frame.empty:
            try:
                frame = ak.stock_info_global_em()
            except Exception:
                frame = None
        if frame is None or frame.empty:
            return records
        for raw in frame.head(max(limit, 1)).to_dict("records"):
            title = _clean_text(_first(raw, ("标题", "title", "内容标题", "news_title")))
            content = _clean_text(_first(raw, ("内容", "摘要", "summary", "简介"))) or title
            if not title or not content:
                continue
            publish = _first(raw, ("发布时间", "日期", "时间", "publish_time")) or _utc_now().isoformat()
            url = _clean_text(_first(raw, ("链接", "url", "URL", "详情链接")))
            records.append(
                RawDocumentRecord(
                    source_id="eastmoney_news",
                    title=title,
                    content=content,
                    summary=content[:180],
                    publish_time=str(publish),
                    url=url or None,
                    raw_json={"source_payload": raw},
                )
            )
        return records

    @staticmethod
    def _stock_news(ak: Any, *, symbols: Sequence[str], limit: int) -> list[RawDocumentRecord]:
        records: list[RawDocumentRecord] = []
        for symbol in symbols:
            ticker = _ticker_from_raw(symbol)
            if ticker is None:
                continue
            try:
                frame = ak.stock_news_em(symbol=ticker.split(".", 1)[0])
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            for raw in frame.head(max(limit - len(records), 0)).to_dict("records"):
                title = _clean_text(_first(raw, ("新闻标题", "标题", "title")))
                content = _clean_text(_first(raw, ("新闻内容", "内容", "摘要", "summary"))) or title
                if not title:
                    continue
                publish = _first(raw, ("发布时间", "时间", "日期", "publish_time")) or _utc_now().isoformat()
                url = _clean_text(_first(raw, ("新闻链接", "链接", "url", "URL")))
                records.append(
                    RawDocumentRecord(
                        source_id="eastmoney_news",
                        title=title,
                        content=f"{ticker} {content}",
                        summary=content[:180],
                        publish_time=str(publish),
                        url=url or None,
                        raw_json={"ticker": ticker, "source_payload": raw},
                    )
                )
                if len(records) >= limit:
                    return records
        return records


class AShareDataCollectionService:
    """Collect public A-share data and persist it into the local research store."""

    def __init__(
        self,
        store: AShareDataStore | None = None,
        fetcher: AksharePublicDataFetcher | None = None,
    ) -> None:
        self.store = store or AShareDataStore()
        self.fetcher = fetcher or AksharePublicDataFetcher()

    def collect_daily_package(
        self,
        *,
        trade_date: str | date | datetime | None = None,
        include_market: bool = True,
        include_sector: bool = True,
        include_news: bool = True,
        include_announcements: bool = True,
        stock_limit: int = 500,
        sector_limit: int = 120,
        anomaly_limit: int = 120,
        document_limit: int = 80,
        symbols: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        extract_events: bool = True,
        continue_on_error: bool = True,
    ) -> dict[str, Any]:
        run_date = _parse_date(trade_date, field_name="trade_date")
        steps: list[dict[str, Any]] = []
        for name, enabled, runner in (
            ("market_snapshot", include_market, lambda: self.collect_market_snapshot(trade_date=run_date, limit=stock_limit)),
            (
                "sector_anomalies",
                include_sector,
                lambda: self.collect_sector_and_anomalies(
                    trade_date=run_date,
                    sector_limit=sector_limit,
                    anomaly_limit=anomaly_limit,
                ),
            ),
            (
                "news_documents",
                include_news or include_announcements,
                lambda: self.collect_news_documents(
                    trade_date=run_date,
                    symbols=symbols,
                    keywords=keywords,
                    limit=document_limit,
                    include_news=include_news,
                    include_announcements=include_announcements,
                    extract_events=extract_events,
                ),
            ),
        ):
            if not enabled:
                steps.append({"name": name, "status": "skipped", "message": "已按请求跳过。", "metrics": {}})
                continue
            try:
                result = runner()
            except AShareDataCollectionError as exc:
                if not continue_on_error:
                    raise
                steps.append({"name": name, "status": "failed", "message": str(exc), "metrics": {}})
                continue
            steps.append({"name": name, "status": result["status"], "message": result["message"], "metrics": result})

        failed = [step for step in steps if step["status"] == "failed"]
        written = sum(int(step["metrics"].get("rows_written", 0) or 0) for step in steps if isinstance(step.get("metrics"), dict))
        return {
            "status": "partial" if failed else "ok",
            "trade_date": run_date.isoformat(),
            "step_count": len(steps),
            "failed_step_count": len(failed),
            "rows_written": written,
            "steps": steps,
            "research_only": True,
            "live_trading": False,
        }

    def collect_market_snapshot(
        self,
        *,
        trade_date: str | date | datetime | None = None,
        records: Iterable[StockSnapshotRecord | dict[str, Any]] | None = None,
        limit: int = 500,
        source_id: str = "akshare_local",
    ) -> dict[str, Any]:
        as_of = _parse_date(trade_date, field_name="trade_date")
        started = _utc_now()
        raw_rows = list(records) if records is not None else self.fetcher.fetch_stock_snapshot(limit=limit)
        try:
            rows = [self._stock_record(row, as_of) for row in raw_rows]
            rows = [row for row in rows if row is not None]
            if not rows:
                raise AShareDataCollectionError("没有采集到有效的 A 股行情快照。")
            market_service = AShareMarketDataService(store=self.store)
            market_service.ensure_core_assets()
            market_service.upsert_assets(
                AssetRecord(
                    ticker=row.ticker,
                    ticker_name=row.ticker_name,
                    exchange=row.ticker.split(".", 1)[1],
                    asset_type="stock",
                    active=True,
                )
                for row in rows
            )
            written = market_service.upsert_market_daily(
                MarketDailyRecord(
                    trade_date=row.trade_date,
                    ticker=row.ticker,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                    amount=row.amount,
                    turnover=row.turnover,
                    adj_factor=1.0,
                    limit_status=_limit_status_from_pct(row.ticker, row.pct_change),
                    suspended=row.volume <= 0,
                    source=row.source,
                )
                for row in rows
            )
        except Exception as exc:
            self._write_collector_run(
                run_date=as_of,
                collector_type="market_snapshot",
                source_id=source_id,
                status="failed",
                rows_requested=len(raw_rows),
                rows_written=0,
                error_message=str(exc),
                metadata={},
                started_at=started,
            )
            if isinstance(exc, AShareDataCollectionError):
                raise
            raise AShareDataCollectionError(f"每日市场数据采集失败: {exc}") from exc

        run_id = self._write_collector_run(
            run_date=as_of,
            collector_type="market_snapshot",
            source_id=source_id,
            status="ok",
            rows_requested=len(raw_rows),
            rows_written=written,
            error_message=None,
            metadata={"unique_tickers": len({row.ticker for row in rows})},
            started_at=started,
        )
        return {
            "status": "ok",
            "message": f"已写入 {written} 条 A 股行情快照。",
            "run_id": run_id,
            "trade_date": as_of.isoformat(),
            "source_id": source_id,
            "rows_requested": len(raw_rows),
            "rows_written": written,
            "sample_tickers": [row.ticker for row in rows[:8]],
        }

    def collect_sector_and_anomalies(
        self,
        *,
        trade_date: str | date | datetime | None = None,
        sector_records: Iterable[SectorSnapshotRecord | dict[str, Any]] | None = None,
        stock_records: Iterable[StockSnapshotRecord | dict[str, Any]] | None = None,
        sector_limit: int = 120,
        anomaly_limit: int = 120,
        source_id: str = "akshare_local",
    ) -> dict[str, Any]:
        as_of = _parse_date(trade_date, field_name="trade_date")
        started = _utc_now()
        raw_sector_rows = list(sector_records) if sector_records is not None else self.fetcher.fetch_sector_snapshot(limit=sector_limit)
        raw_stock_rows = list(stock_records) if stock_records is not None else self.fetcher.fetch_stock_snapshot(limit=max(anomaly_limit * 2, 100))
        try:
            sectors = [self._sector_record(row, as_of) for row in raw_sector_rows]
            sectors = [row for row in sectors if row is not None]
            stocks = [self._stock_record(row, as_of) for row in raw_stock_rows]
            stocks = [row for row in stocks if row is not None]
            if not sectors and not stocks:
                raise AShareDataCollectionError("没有采集到有效的板块或个股异动数据。")
            sector_written = self._upsert_sector_daily(sectors)
            anomalies = self._build_anomalies(stocks, limit=anomaly_limit)
            anomaly_written = self._upsert_stock_anomalies(anomalies)
        except Exception as exc:
            self._write_collector_run(
                run_date=as_of,
                collector_type="sector_anomalies",
                source_id=source_id,
                status="failed",
                rows_requested=len(raw_sector_rows) + len(raw_stock_rows),
                rows_written=0,
                error_message=str(exc),
                metadata={},
                started_at=started,
            )
            if isinstance(exc, AShareDataCollectionError):
                raise
            raise AShareDataCollectionError(f"板块与个股异动采集失败: {exc}") from exc

        run_id = self._write_collector_run(
            run_date=as_of,
            collector_type="sector_anomalies",
            source_id=source_id,
            status="ok",
            rows_requested=len(raw_sector_rows) + len(raw_stock_rows),
            rows_written=sector_written + anomaly_written,
            error_message=None,
            metadata={"sector_count": sector_written, "anomaly_count": anomaly_written},
            started_at=started,
        )
        return {
            "status": "ok",
            "message": f"已写入 {sector_written} 条板块快照、{anomaly_written} 条个股异动。",
            "run_id": run_id,
            "trade_date": as_of.isoformat(),
            "source_id": source_id,
            "rows_requested": len(raw_sector_rows) + len(raw_stock_rows),
            "rows_written": sector_written + anomaly_written,
            "sector_count": sector_written,
            "anomaly_count": anomaly_written,
            "top_sectors": [row.sector_name for row in sectors[:8]],
        }

    def collect_news_documents(
        self,
        *,
        trade_date: str | date | datetime | None = None,
        documents: Iterable[RawDocumentRecord | dict[str, Any]] | None = None,
        symbols: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        limit: int = 80,
        include_news: bool = True,
        include_announcements: bool = True,
        extract_events: bool = True,
        source_id: str = "public_documents",
    ) -> dict[str, Any]:
        as_of = _parse_date(trade_date, field_name="trade_date")
        started = _utc_now()
        records = list(documents) if documents is not None else []
        if documents is None:
            if include_news:
                records.extend(self.fetcher.fetch_news_documents(symbols=symbols, keywords=keywords, limit=limit))
            if include_announcements:
                default_symbols = tuple(symbols or ("600519.SH", "300750.SZ", "000001.SZ", "601138.SH", "000977.SZ"))
                records.extend(
                    self.fetcher.fetch_announcement_documents(
                        symbols=default_symbols,
                        start_date=as_of,
                        end_date=as_of,
                        limit=max(limit - len(records), 0),
                    )
                )
        try:
            raw_documents = [self._document_record(row) for row in records]
            raw_documents = _filter_documents(raw_documents, keywords=keywords, limit=limit)
            if not raw_documents:
                raise AShareDataCollectionError("没有采集到有效的公告、政策或财经新闻。")
            ingestion = EventSourceIngestionService(store=self.store).ingest_documents(raw_documents)
            extraction: dict[str, Any] | None = None
            if extract_events:
                try:
                    extraction = EventExtractionService(store=self.store).extract_events(limit=limit, min_relevance=0.0)
                except EventExtractionError as exc:
                    extraction = {"status": "blocked", "message": str(exc)}
        except Exception as exc:
            self._write_collector_run(
                run_date=as_of,
                collector_type="news_documents",
                source_id=source_id,
                status="failed",
                rows_requested=len(records),
                rows_written=0,
                error_message=str(exc),
                metadata={},
                started_at=started,
            )
            if isinstance(exc, AShareDataCollectionError):
                raise
            raise AShareDataCollectionError(f"公告、政策和财经新闻采集失败: {exc}") from exc

        rows_written = int(ingestion["inserted"])
        run_id = self._write_collector_run(
            run_date=as_of,
            collector_type="news_documents",
            source_id=source_id,
            status="ok",
            rows_requested=len(records),
            rows_written=rows_written,
            error_message=None,
            metadata={
                "duplicates": ingestion["duplicates"],
                "extracted_events": extraction.get("extracted") if extraction else None,
            },
            started_at=started,
        )
        return {
            "status": "ok",
            "message": f"已导入 {rows_written} 条原始文档，重复 {ingestion['duplicates']} 条。",
            "run_id": run_id,
            "trade_date": as_of.isoformat(),
            "source_id": source_id,
            "rows_requested": len(records),
            "rows_written": rows_written,
            "ingestion": ingestion,
            "extraction": extraction,
        }

    def market_snapshot(self, *, trade_date: str | date | datetime | None = None, limit: int = 50) -> dict[str, Any]:
        self.store.initialize()
        as_of = _parse_date(trade_date, field_name="trade_date") if trade_date else self._latest_market_date()
        if as_of is None:
            raise AShareDataCollectionError("还没有市场快照，请先运行每日市场数据采集。")
        capped = min(max(int(limit), 1), 500)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT md.trade_date, md.ticker, COALESCE(a.ticker_name, md.ticker),
                       md.open, md.high, md.low, md.close, md.volume, md.amount,
                       md.turnover, md.limit_status, md.suspended, md.source, md.created_at
                FROM market_daily md
                LEFT JOIN assets a ON a.ticker = md.ticker
                WHERE md.trade_date = ?
                ORDER BY md.amount DESC NULLS LAST, md.ticker
                LIMIT ?
                """,
                [as_of, capped],
            ).fetchall()
            run_rows = self._collector_runs(conn, run_date=as_of, collector_type=None)
            anomaly_counts = conn.execute(
                """
                SELECT anomaly_type, COUNT(*)
                FROM stock_anomaly_snapshots
                WHERE trade_date = ?
                GROUP BY anomaly_type
                ORDER BY anomaly_type
                """,
                [as_of],
            ).fetchall()
        limit_up = sum(1 for row in rows if row[10] == "limit_up")
        suspended = sum(1 for row in rows if row[11])
        total_amount = round(sum(float(row[8] or 0.0) for row in rows), 2)
        return {
            "status": "ok",
            "trade_date": as_of.isoformat(),
            "row_count": len(rows),
            "summary": {
                "sample_count": len(rows),
                "limit_up_count": limit_up,
                "suspended_count": suspended,
                "total_amount": total_amount,
                "total_amount_yi": round(total_amount / 100000000, 2),
                "anomaly_counts": {row[0]: int(row[1]) for row in anomaly_counts},
            },
            "rows": [self._market_row(row) for row in rows],
            "collector_runs": run_rows,
            "research_only": True,
            "live_trading": False,
        }

    def sector_anomaly_snapshot(self, *, trade_date: str | date | datetime | None = None, limit: int = 50) -> dict[str, Any]:
        self.store.initialize()
        as_of = _parse_date(trade_date, field_name="trade_date") if trade_date else self._latest_sector_or_anomaly_date()
        if as_of is None:
            raise AShareDataCollectionError("还没有板块或异动快照，请先运行板块与个股异动采集。")
        capped = min(max(int(limit), 1), 200)
        with self.store.connect(read_only=True) as conn:
            sectors = conn.execute(
                """
                SELECT trade_date, sector_id, sector_name, return, amount, turnover,
                       up_count, down_count, limit_up_count, member_count,
                       leading_ticker, source, created_at
                FROM sector_daily
                WHERE trade_date = ?
                ORDER BY return DESC NULLS LAST, amount DESC NULLS LAST
                LIMIT ?
                """,
                [as_of, capped],
            ).fetchall()
            anomalies = conn.execute(
                """
                SELECT trade_date, ticker, ticker_name, anomaly_type, pct_change,
                       amount, turnover, volume_ratio, limit_status, sector_name,
                       source, evidence_json, created_at
                FROM stock_anomaly_snapshots
                WHERE trade_date = ?
                ORDER BY pct_change DESC NULLS LAST, amount DESC NULLS LAST, ticker
                LIMIT ?
                """,
                [as_of, capped],
            ).fetchall()
        return {
            "status": "ok",
            "trade_date": as_of.isoformat(),
            "sector_count": len(sectors),
            "anomaly_count": len(anomalies),
            "sectors": [self._sector_row(row) for row in sectors],
            "anomalies": [self._anomaly_row(row) for row in anomalies],
            "research_only": True,
            "live_trading": False,
        }

    def _upsert_sector_daily(self, sectors: Sequence[SectorSnapshotRecord]) -> int:
        if not sectors:
            return 0
        now = _utc_now()
        with self.store.connect() as conn:
            for record in sectors:
                conn.execute("DELETE FROM sectors WHERE sector_id = ?", [record.sector_id])
                conn.execute(
                    """
                    INSERT INTO sectors (sector_id, sector_name, sector_type, source, active, updated_at)
                    VALUES (?, ?, ?, ?, true, ?)
                    """,
                    [record.sector_id, record.sector_name, record.sector_type, record.source, now],
                )
                conn.execute(
                    "DELETE FROM sector_daily WHERE trade_date = ? AND sector_id = ?",
                    [record.trade_date, record.sector_id],
                )
                close = record.close if record.close is not None else 100.0
                conn.execute(
                    """
                    INSERT INTO sector_daily (
                      trade_date, sector_id, sector_name, open, high, low, close,
                      return, amount, turnover, up_count, down_count, limit_up_count,
                      member_count, leading_ticker, source, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        record.trade_date,
                        record.sector_id,
                        record.sector_name,
                        record.open if record.open is not None else close,
                        record.high if record.high is not None else close,
                        record.low if record.low is not None else close,
                        close,
                        record.return_,
                        record.amount,
                        record.turnover,
                        record.up_count,
                        record.down_count,
                        record.limit_up_count,
                        record.member_count,
                        record.leading_ticker,
                        record.source,
                        now,
                    ],
                )
        return len(sectors)

    def _upsert_stock_anomalies(self, anomalies: Sequence[StockAnomalyRecord]) -> int:
        if not anomalies:
            return 0
        now = _utc_now()
        with self.store.connect() as conn:
            for record in anomalies:
                conn.execute(
                    """
                    DELETE FROM stock_anomaly_snapshots
                    WHERE trade_date = ? AND ticker = ? AND anomaly_type = ?
                    """,
                    [record.trade_date, record.ticker, record.anomaly_type],
                )
                conn.execute(
                    """
                    INSERT INTO stock_anomaly_snapshots (
                      trade_date, ticker, ticker_name, anomaly_type, pct_change,
                      amount, turnover, volume_ratio, limit_status, sector_name,
                      source, evidence_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        record.trade_date,
                        record.ticker,
                        record.ticker_name,
                        record.anomaly_type,
                        record.pct_change,
                        record.amount,
                        record.turnover,
                        record.volume_ratio,
                        record.limit_status,
                        record.sector_name,
                        record.source,
                        _json(record.evidence),
                        now,
                    ],
                )
        return len(anomalies)

    def _build_anomalies(self, stocks: Sequence[StockSnapshotRecord], *, limit: int) -> list[StockAnomalyRecord]:
        result: list[StockAnomalyRecord] = []
        for stock in stocks:
            status = _limit_status_from_pct(stock.ticker, stock.pct_change)
            anomaly_types: list[str] = []
            if status == "limit_up":
                anomaly_types.append("limit_up")
            elif status == "limit_down":
                anomaly_types.append("limit_down")
            if stock.pct_change is not None and stock.pct_change >= 0.07 and "limit_up" not in anomaly_types:
                anomaly_types.append("strong_gain")
            if stock.pct_change is not None and stock.pct_change <= -0.07 and "limit_down" not in anomaly_types:
                anomaly_types.append("sharp_drop")
            if stock.volume_ratio is not None and stock.volume_ratio >= 2:
                anomaly_types.append("volume_spike")
            if stock.amount is not None and stock.amount >= 1_000_000_000:
                anomaly_types.append("high_turnover")
            for anomaly_type in anomaly_types:
                result.append(
                    StockAnomalyRecord(
                        trade_date=stock.trade_date,
                        ticker=stock.ticker,
                        ticker_name=stock.ticker_name,
                        anomaly_type=anomaly_type,
                        pct_change=stock.pct_change,
                        amount=stock.amount,
                        turnover=stock.turnover,
                        volume_ratio=stock.volume_ratio,
                        limit_status=status,
                        sector_name=stock.sector_name,
                        source=stock.source,
                        evidence=stock.raw_json,
                    )
                )
                if len(result) >= limit:
                    return result
        return result

    def _stock_record(self, value: StockSnapshotRecord | dict[str, Any], trade_date: date) -> StockSnapshotRecord | None:
        if isinstance(value, StockSnapshotRecord):
            return value
        row = dict(value)
        ticker = _ticker_from_raw(_first(row, ("ticker", "代码", "证券代码", "code", "symbol")))
        if ticker is None or not is_a_share_code(ticker) or ticker.endswith(".BJ"):
            return None
        close = _float_or_none(_first(row, ("close", "最新价", "收盘", "price")))
        if close is None or close <= 0:
            return None
        open_ = _float_or_none(_first(row, ("open", "今开", "开盘"))) or close
        high = _float_or_none(_first(row, ("high", "最高"))) or max(open_, close)
        low = _float_or_none(_first(row, ("low", "最低"))) or min(open_, close)
        return StockSnapshotRecord(
            trade_date=_parse_date(_first(row, ("trade_date", "日期")) or trade_date, field_name="trade_date"),
            ticker=ticker,
            ticker_name=_clean_text(_first(row, ("ticker_name", "名称", "证券简称", "name"))) or ticker,
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=float(_float_or_none(_first(row, ("volume", "成交量", "vol"))) or 0.0),
            amount=_float_or_none(_first(row, ("amount", "成交额", "成交金额"))),
            turnover=_ratio_or_none(_first(row, ("turnover", "换手率"))),
            pct_change=_ratio_or_none(_first(row, ("pct_change", "涨跌幅", "change_pct"))),
            volume_ratio=_float_or_none(_first(row, ("volume_ratio", "量比"))),
            sector_name=_clean_text(_first(row, ("sector_name", "所属行业", "板块"))) or None,
            source=_clean_text(_first(row, ("source", "source_id"))) or "akshare_public",
            raw_json=row,
        )

    def _sector_record(self, value: SectorSnapshotRecord | dict[str, Any], trade_date: date) -> SectorSnapshotRecord | None:
        if isinstance(value, SectorSnapshotRecord):
            return value
        row = dict(value)
        name = _clean_text(_first(row, ("sector_name", "板块名称", "名称", "name")))
        if not name:
            return None
        sector_type = _clean_text(_first(row, ("sector_type", "类型"))) or "concept"
        close = _float_or_none(_first(row, ("close", "最新价", "收盘", "price"))) or 100.0
        leading_ticker = _ticker_from_raw(_first(row, ("leading_ticker", "领涨股票代码", "领涨股代码")))
        return SectorSnapshotRecord(
            trade_date=_parse_date(_first(row, ("trade_date", "日期")) or trade_date, field_name="trade_date"),
            sector_id=_clean_text(_first(row, ("sector_id", "板块代码"))) or _sector_id(name, sector_type),
            sector_name=name,
            sector_type=sector_type,
            open=_float_or_none(_first(row, ("open", "今开", "开盘"))) or close,
            high=_float_or_none(_first(row, ("high", "最高"))) or close,
            low=_float_or_none(_first(row, ("low", "最低"))) or close,
            close=close,
            return_=_ratio_or_none(_first(row, ("return", "涨跌幅", "pct_change"))),
            amount=_float_or_none(_first(row, ("amount", "成交额", "成交金额"))),
            turnover=_ratio_or_none(_first(row, ("turnover", "换手率"))),
            up_count=_int_or_none(_first(row, ("up_count", "上涨家数"))),
            down_count=_int_or_none(_first(row, ("down_count", "下跌家数"))),
            limit_up_count=_int_or_none(_first(row, ("limit_up_count", "涨停家数"))),
            member_count=_int_or_none(_first(row, ("member_count", "股票家数", "成份股数量"))),
            leading_ticker=leading_ticker or _clean_text(_first(row, ("leading_ticker", "领涨股票", "领涨股"))) or None,
            source=_clean_text(_first(row, ("source", "source_id"))) or "akshare_public",
            raw_json=row,
        )

    @staticmethod
    def _document_record(value: RawDocumentRecord | dict[str, Any]) -> RawDocumentRecord:
        if isinstance(value, RawDocumentRecord):
            return value
        return RawDocumentRecord(**value)

    def _write_collector_run(
        self,
        *,
        run_date: date,
        collector_type: str,
        source_id: str,
        status: str,
        rows_requested: int,
        rows_written: int,
        error_message: str | None,
        metadata: dict[str, Any],
        started_at: datetime,
    ) -> str:
        self.store.initialize()
        EventSourceIngestionService(store=self.store).ensure_default_sources()
        ended_at = _utc_now()
        digest = hashlib.sha256(
            f"{run_date}|{collector_type}|{source_id}|{started_at.isoformat()}|{ended_at.isoformat()}".encode("utf-8")
        ).hexdigest()[:18]
        run_id = f"collector_{digest}"
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO collector_runs (
                  run_id, run_date, collector_type, source_id, status,
                  rows_requested, rows_written, error_message, metadata_json,
                  started_at, ended_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    run_date,
                    collector_type,
                    source_id,
                    status,
                    rows_requested,
                    rows_written,
                    error_message,
                    _json(metadata),
                    started_at,
                    ended_at,
                ],
            )
            if status == "ok":
                conn.execute(
                    """
                    UPDATE source_registry
                    SET last_fetch_time = ?, updated_at = ?
                    WHERE source_id = ?
                    """,
                    [ended_at, ended_at, source_id],
                )
        return run_id

    def _latest_market_date(self) -> date | None:
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            row = conn.execute("SELECT MAX(trade_date) FROM market_daily").fetchone()
        return _parse_optional_date(row[0] if row else None)

    def _latest_sector_or_anomaly_date(self) -> date | None:
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT MAX(value)
                FROM (
                  SELECT MAX(trade_date) AS value FROM sector_daily
                  UNION ALL
                  SELECT MAX(trade_date) AS value FROM stock_anomaly_snapshots
                )
                """
            ).fetchone()
        return _parse_optional_date(row[0] if row else None)

    @staticmethod
    def _collector_runs(conn: Any, *, run_date: date, collector_type: str | None) -> list[dict[str, Any]]:
        filters = ["run_date = ?"]
        params: list[Any] = [run_date]
        if collector_type:
            filters.append("collector_type = ?")
            params.append(collector_type)
        rows = conn.execute(
            f"""
            SELECT run_id, run_date, collector_type, source_id, status,
                   rows_requested, rows_written, error_message, metadata_json,
                   started_at, ended_at
            FROM collector_runs
            WHERE {' AND '.join(filters)}
            ORDER BY ended_at DESC
            LIMIT 20
            """,
            params,
        ).fetchall()
        return [
            {
                "run_id": row[0],
                "run_date": _iso(row[1]),
                "collector_type": row[2],
                "source_id": row[3],
                "status": row[4],
                "rows_requested": int(row[5] or 0),
                "rows_written": int(row[6] or 0),
                "error_message": row[7],
                "metadata": _loads(row[8], {}),
                "started_at": _iso(row[9]),
                "ended_at": _iso(row[10]),
            }
            for row in rows
        ]

    @staticmethod
    def _market_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "trade_date": _iso(row[0]),
            "ticker": row[1],
            "ticker_name": row[2],
            "open": float(row[3] or 0.0),
            "high": float(row[4] or 0.0),
            "low": float(row[5] or 0.0),
            "close": float(row[6] or 0.0),
            "volume": float(row[7] or 0.0),
            "amount": None if row[8] is None else float(row[8]),
            "turnover": None if row[9] is None else float(row[9]),
            "limit_status": row[10],
            "suspended": bool(row[11]),
            "source": row[12],
            "created_at": _iso(row[13]),
        }

    @staticmethod
    def _sector_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "trade_date": _iso(row[0]),
            "sector_id": row[1],
            "sector_name": row[2],
            "return": None if row[3] is None else float(row[3]),
            "amount": None if row[4] is None else float(row[4]),
            "turnover": None if row[5] is None else float(row[5]),
            "up_count": row[6],
            "down_count": row[7],
            "limit_up_count": row[8],
            "member_count": row[9],
            "leading_ticker": row[10],
            "source": row[11],
            "created_at": _iso(row[12]),
        }

    @staticmethod
    def _anomaly_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "trade_date": _iso(row[0]),
            "ticker": row[1],
            "ticker_name": row[2],
            "anomaly_type": row[3],
            "pct_change": None if row[4] is None else float(row[4]),
            "amount": None if row[5] is None else float(row[5]),
            "turnover": None if row[6] is None else float(row[6]),
            "volume_ratio": None if row[7] is None else float(row[7]),
            "limit_status": row[8],
            "sector_name": row[9],
            "source": row[10],
            "evidence": _loads(row[11], {}),
            "created_at": _iso(row[12]),
        }


def _parse_optional_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _filter_documents(
    documents: Iterable[RawDocumentRecord],
    *,
    keywords: Sequence[str] | None,
    limit: int,
) -> list[RawDocumentRecord]:
    rows = list(documents)
    clean_keywords = [_clean_text(keyword).lower() for keyword in (keywords or ()) if _clean_text(keyword)]
    if clean_keywords:
        rows = [
            row for row in rows
            if any(keyword in f"{row.title} {row.content} {row.summary or ''}".lower() for keyword in clean_keywords)
        ]
    return rows[:min(max(int(limit), 1), 500)]
