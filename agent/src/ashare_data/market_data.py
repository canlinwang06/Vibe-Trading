"""A-share asset master and daily market-data service for PR-04."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd

from src.ashare_data.store import AShareDataStore
from src.market_policy import is_a_share_code, normalize_a_share_code


class AShareMarketDataError(RuntimeError):
    """Raised when PR-04 market-data operations cannot be completed."""


@dataclass(frozen=True)
class AssetRecord:
    ticker: str
    ticker_name: str
    exchange: str
    asset_type: str = "stock"
    market: str = "CN_A"
    listed_date: date | None = None
    delisted_date: date | None = None
    active: bool = True


@dataclass(frozen=True)
class MarketDailyRecord:
    trade_date: date
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float | None = None
    turnover: float | None = None
    adj_factor: float | None = None
    limit_status: str = "normal"
    suspended: bool = False
    source: str = "local"


CORE_ASSETS: tuple[AssetRecord, ...] = (
    AssetRecord("600519.SH", "贵州茅台", "SH"),
    AssetRecord("300750.SZ", "宁德时代", "SZ"),
    AssetRecord("000001.SZ", "平安银行", "SZ"),
    AssetRecord("000300.SH", "沪深300", "SH", asset_type="index"),
    AssetRecord("000985.SH", "中证全指", "SH", asset_type="index"),
    AssetRecord("399006.SZ", "创业板指", "SZ", asset_type="index"),
)


def _now() -> datetime:
    return datetime.now()


def _parse_date(value: str | date | pd.Timestamp) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = pd.Timestamp(value)
    if pd.isna(parsed):
        raise AShareMarketDataError(f"日期格式无效: {value}")
    return parsed.date()


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    normalized = [normalize_a_share_code(ticker) for ticker in tickers]
    invalid = [ticker for ticker in normalized if not is_a_share_code(ticker)]
    if invalid:
        raise AShareMarketDataError(
            "仅支持沪深 A 股股票或指数代码，例如 600519.SH、300750.SZ、000001.SZ；"
            f"无法处理: {', '.join(invalid)}"
        )
    if not normalized:
        raise AShareMarketDataError("请至少提供一个 A 股代码")
    return normalized


def _limit_threshold(ticker: str) -> float:
    code = ticker.split(".", 1)[0]
    if code.startswith(("300", "301", "688")):
        return 0.198
    return 0.098


def _limit_status(ticker: str, close: float, previous_close: float | None) -> str:
    if previous_close is None or previous_close <= 0:
        return "normal"
    pct = close / previous_close - 1.0
    threshold = _limit_threshold(ticker)
    if pct >= threshold:
        return "limit_up"
    if pct <= -threshold:
        return "limit_down"
    return "normal"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


class AShareMarketDataService:
    """Read/write service for PR-04 A-share assets and daily bars."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def ensure_core_assets(self) -> tuple[AssetRecord, ...]:
        """Insert the core PR-04 stocks and benchmark indexes."""
        self.store.initialize()
        self.upsert_assets(CORE_ASSETS)
        return CORE_ASSETS

    def upsert_assets(self, assets: Iterable[AssetRecord]) -> int:
        rows = list(assets)
        now = _now()
        with self.store.connect() as conn:
            for asset in rows:
                ticker = normalize_a_share_code(asset.ticker)
                conn.execute("DELETE FROM assets WHERE ticker = ?", [ticker])
                conn.execute(
                    """
                    INSERT INTO assets (
                      ticker, ticker_name, market, exchange, asset_type,
                      listed_date, delisted_date, active, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ticker,
                        asset.ticker_name,
                        asset.market,
                        asset.exchange,
                        asset.asset_type,
                        asset.listed_date,
                        asset.delisted_date,
                        asset.active,
                        now,
                    ],
                )
        return len(rows)

    def get_asset(self, ticker: str) -> dict[str, Any]:
        normalized = _normalize_tickers([ticker])[0]
        self.ensure_core_assets()
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT ticker, ticker_name, market, exchange, asset_type,
                       listed_date, delisted_date, active, updated_at
                FROM assets
                WHERE ticker = ?
                """,
                [normalized],
            ).fetchone()
        if row is None:
            raise AShareMarketDataError(f"未找到 A 股资产基础信息: {normalized}")
        return {
            "ticker": row[0],
            "ticker_name": row[1],
            "market": row[2],
            "exchange": row[3],
            "asset_type": row[4],
            "listed_date": row[5].isoformat() if row[5] else None,
            "delisted_date": row[6].isoformat() if row[6] else None,
            "active": bool(row[7]),
            "updated_at": row[8].isoformat() if row[8] else None,
        }

    def get_market_daily(self, ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        normalized = _normalize_tickers([ticker])[0]
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        if start > end:
            raise AShareMarketDataError("开始日期不能晚于结束日期")
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT trade_date, ticker, open, high, low, close, volume, amount,
                       turnover, adj_factor, limit_status, suspended, source, created_at
                FROM market_daily
                WHERE ticker = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
                """,
                [normalized, start, end],
            ).fetchall()
        return [
            {
                "trade_date": row[0].isoformat(),
                "ticker": row[1],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
                "amount": row[7],
                "turnover": row[8],
                "adj_factor": row[9],
                "limit_status": row[10],
                "suspended": bool(row[11]),
                "source": row[12],
                "created_at": row[13].isoformat() if row[13] else None,
            }
            for row in rows
        ]

    def update_market_daily(
        self,
        tickers: Iterable[str],
        start_date: str,
        end_date: str,
        *,
        source: str = "auto",
    ) -> dict[str, Any]:
        """Fetch and persist daily market data from local or AKShare loaders."""
        normalized = _normalize_tickers(tickers)
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        if start > end:
            raise AShareMarketDataError("开始日期不能晚于结束日期")

        self.ensure_core_assets()
        frames, used_source = self._fetch_frames(normalized, start.isoformat(), end.isoformat(), source=source)
        if not frames:
            raise AShareMarketDataError("未能获取日线行情，请检查 AKShare 是否可用，或先配置本地数据源。")

        records: list[MarketDailyRecord] = []
        for ticker, frame in frames.items():
            records.extend(self._records_from_frame(ticker, frame, used_source))
        inserted = self.upsert_market_daily(records)
        missing = [ticker for ticker in normalized if ticker not in frames]
        return {
            "status": "ok",
            "source": used_source,
            "requested": normalized,
            "updated_tickers": sorted(frames),
            "missing_tickers": missing,
            "rows_written": inserted,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }

    def upsert_market_daily(self, records: Iterable[MarketDailyRecord]) -> int:
        rows = list(records)
        now = _now()
        with self.store.connect() as conn:
            for record in rows:
                ticker = normalize_a_share_code(record.ticker)
                conn.execute(
                    "DELETE FROM market_daily WHERE trade_date = ? AND ticker = ?",
                    [record.trade_date, ticker],
                )
                conn.execute(
                    """
                    INSERT INTO market_daily (
                      trade_date, ticker, open, high, low, close, volume, amount,
                      turnover, adj_factor, limit_status, suspended, source, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        record.trade_date,
                        ticker,
                        record.open,
                        record.high,
                        record.low,
                        record.close,
                        record.volume,
                        record.amount,
                        record.turnover,
                        record.adj_factor,
                        record.limit_status,
                        record.suspended,
                        record.source,
                        now,
                    ],
                )
        return len(rows)

    def _fetch_frames(self, tickers: list[str], start_date: str, end_date: str, *, source: str) -> tuple[dict[str, pd.DataFrame], str]:
        requested = source.strip().lower()
        if requested not in {"auto", "local", "akshare"}:
            raise AShareMarketDataError("数据源只支持 auto、local 或 akshare")

        sources = ("local", "akshare") if requested == "auto" else (requested,)
        last_error: Exception | None = None
        for candidate in sources:
            try:
                frames = self._loader_for_source(candidate).fetch(tickers, start_date, end_date)
            except Exception as exc:  # noqa: BLE001 - surfaced as a Chinese user error below
                last_error = exc
                frames = {}
            frames = {normalize_a_share_code(k): v for k, v in frames.items() if v is not None and not v.empty}
            if frames:
                return frames, candidate
        if last_error is not None and requested != "auto":
            raise AShareMarketDataError(f"{requested} 数据源获取失败: {last_error}") from last_error
        return {}, requested

    @staticmethod
    def _loader_for_source(source: str):
        if source == "local":
            from backtest.loaders.local_loader import DataLoader

            return DataLoader()
        if source == "akshare":
            from backtest.loaders.akshare_loader import DataLoader

            return DataLoader()
        raise AShareMarketDataError("数据源只支持 auto、local 或 akshare")

    @staticmethod
    def _records_from_frame(ticker: str, frame: pd.DataFrame, source: str) -> list[MarketDailyRecord]:
        if not isinstance(frame.index, pd.DatetimeIndex):
            if "trade_date" in frame.columns:
                frame = frame.set_index(pd.to_datetime(frame["trade_date"]))
            elif "date" in frame.columns:
                frame = frame.set_index(pd.to_datetime(frame["date"]))
            else:
                raise AShareMarketDataError(f"{ticker} 行情缺少 trade_date/date 字段")
        frame = frame.sort_index()
        records: list[MarketDailyRecord] = []
        previous_close: float | None = None
        for idx, row in frame.iterrows():
            open_ = _float_or_none(row.get("open"))
            high = _float_or_none(row.get("high"))
            low = _float_or_none(row.get("low"))
            close = _float_or_none(row.get("close"))
            volume = _float_or_none(row.get("volume")) or 0.0
            if open_ is None or high is None or low is None or close is None:
                continue
            pre_close = _float_or_none(row.get("pre_close")) or previous_close
            suspended = bool(volume <= 0)
            records.append(
                MarketDailyRecord(
                    trade_date=_parse_date(idx),
                    ticker=ticker,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    amount=_float_or_none(row.get("amount")),
                    turnover=_float_or_none(row.get("turnover")),
                    adj_factor=_float_or_none(row.get("adj_factor")) or 1.0,
                    limit_status=_limit_status(ticker, close, pre_close),
                    suspended=suspended,
                    source=source,
                )
            )
            previous_close = close
        return records
