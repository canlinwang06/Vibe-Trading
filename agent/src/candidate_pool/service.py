"""Local A-share candidate-pool generation and manual review controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore
from src.market_policy import is_a_share_code, normalize_a_share_code


class CandidatePoolError(RuntimeError):
    """Raised when PR-09 candidate-pool operations cannot be completed."""


@dataclass(frozen=True)
class CandidateRow:
    as_of_date: date
    ticker: str
    ticker_name: str
    source: str
    sector_id: str | None
    sector_name: str | None
    theme: str | None
    event_heat_score: float
    sector_heat_score: float
    stock_score: float
    user_priority: int
    risk_flag: str
    included: bool
    reason: str


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
        raise CandidatePoolError(f"候选池日期格式无效: {value}") from exc


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


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(max(value, lower), upper)


def _round_score(value: float) -> float:
    return round(_clamp(value), 3)


def _normalize_ticker(ticker: str) -> str:
    normalized = normalize_a_share_code(ticker)
    if not is_a_share_code(normalized):
        raise CandidatePoolError(f"候选池只支持沪深 A 股代码: {ticker}")
    return normalized


def _candidate_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "as_of_date": row[0].isoformat() if row[0] else None,
        "ticker": row[1],
        "ticker_name": row[2],
        "market": row[3],
        "source": row[4],
        "sector_id": row[5],
        "sector_name": row[6],
        "theme": row[7],
        "event_heat_score": row[8],
        "sector_heat_score": row[9],
        "stock_score": row[10],
        "user_priority": row[11],
        "risk_flag": row[12],
        "included": bool(row[13]),
        "reason": row[14],
        "created_at": row[15].isoformat() if row[15] else None,
    }


class CandidatePoolService:
    """Build and manage the local A-share research candidate pool."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def build_candidate_pool(
        self,
        *,
        as_of_date: str | date | datetime | None = None,
        limit: int = 50,
        min_sector_score: float = 0.0,
    ) -> dict[str, Any]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 200)
        min_score = _clamp(float(min_sector_score))
        as_of = _parse_date(as_of_date)
        with self.store.connect() as conn:
            if as_of is None:
                as_of = self._latest_sector_score_date(conn)
            if as_of is None:
                raise CandidatePoolError("没有可生成候选池的板块评分，请先运行板块评分。")
            if not self._has_sector_scores(conn, as_of=as_of, min_sector_score=min_score):
                raise CandidatePoolError("没有可生成候选池的板块评分，请先运行板块评分。")

            mapped_rows = self._load_mapped_stock_rows(conn, as_of=as_of, min_sector_score=min_score)
            if not mapped_rows:
                raise CandidatePoolError(
                    "没有可生成候选池的股票映射，请先运行事件映射和板块评分。"
                )

            candidates = [
                self._build_system_candidate(conn, as_of=as_of, row=row)
                for row in mapped_rows
            ]
            candidates.sort(key=lambda item: (-item.stock_score, item.ticker))
            selected = candidates[:capped_limit]
            for candidate in selected:
                self._upsert_candidate(conn, candidate)

        return {
            "status": "ok",
            "as_of_date": as_of.isoformat(),
            "rows_written": len(selected),
            "candidate_count": len(selected),
            "candidates": [
                {
                    "ticker": item.ticker,
                    "ticker_name": item.ticker_name,
                    "source": item.source,
                    "theme": item.theme,
                    "sector_id": item.sector_id,
                    "sector_name": item.sector_name,
                    "event_heat_score": item.event_heat_score,
                    "sector_heat_score": item.sector_heat_score,
                    "stock_score": item.stock_score,
                    "risk_flag": item.risk_flag,
                    "included": item.included,
                    "reason": item.reason,
                }
                for item in selected
            ],
        }

    def list_candidates(
        self,
        *,
        as_of_date: str | date | datetime | None = None,
        limit: int = 100,
        source: str | None = None,
        included: bool | None = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        as_of = _parse_date(as_of_date)
        capped_limit = min(max(int(limit), 1), 500)
        score_floor = _clamp(float(min_score))
        filters = ["stock_score >= ?"]
        params: list[Any] = [score_floor]
        with self.store.connect(read_only=True) as conn:
            if as_of is None:
                as_of = self._latest_candidate_date(conn)
            if as_of is None:
                return []
            filters.append("as_of_date = ?")
            params.append(as_of)
            if source:
                filters.append("source = ?")
                params.append(source.strip())
            if included is not None:
                filters.append("included = ?")
                params.append(bool(included))
            params.append(capped_limit)
            where = " AND ".join(filters)
            rows = conn.execute(
                f"""
                SELECT as_of_date, ticker, ticker_name, market, source, sector_id,
                       sector_name, theme, event_heat_score, sector_heat_score,
                       stock_score, user_priority, risk_flag, included, reason, created_at
                FROM candidate_pool
                WHERE {where}
                ORDER BY included DESC, user_priority DESC, stock_score DESC, ticker
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_candidate_to_dict(row) for row in rows]

    def add_user_candidate(
        self,
        *,
        ticker: str,
        ticker_name: str | None = None,
        as_of_date: str | date | datetime | None = None,
        theme: str | None = None,
        sector_id: str | None = None,
        sector_name: str | None = None,
        reason: str | None = None,
        user_priority: int = 100,
    ) -> dict[str, Any]:
        self.store.initialize()
        normalized = _normalize_ticker(ticker)
        priority = min(max(int(user_priority), 0), 999)
        as_of = _parse_date(as_of_date) or date.today()
        with self.store.connect() as conn:
            inferred = self._infer_candidate_context(
                conn,
                ticker=normalized,
                as_of=as_of,
                theme=theme,
                sector_id=sector_id,
                sector_name=sector_name,
            )
            name = (
                ticker_name
                or inferred.get("ticker_name")
                or self._asset_name(conn, normalized)
                or normalized
            ).strip()
            risk_flag, included = self._risk_gate(
                ticker=normalized,
                ticker_name=name,
                market_rows=self._load_market_daily(conn, normalized, as_of),
            )
            candidate = CandidateRow(
                as_of_date=as_of,
                ticker=normalized,
                ticker_name=name,
                source="user_added",
                sector_id=inferred.get("sector_id"),
                sector_name=inferred.get("sector_name"),
                theme=inferred.get("theme"),
                event_heat_score=_float(inferred.get("event_heat_score")),
                sector_heat_score=_float(inferred.get("sector_heat_score")),
                stock_score=0.65 if included else 0.25,
                user_priority=priority,
                risk_flag=risk_flag,
                included=included,
                reason=(reason or "用户手动加入候选池。").strip(),
            )
            self._upsert_candidate(conn, candidate)
            inserted = self._get_candidate(conn, as_of=as_of, ticker=normalized)
        return inserted or {}

    def set_included(
        self,
        *,
        ticker: str,
        included: bool,
        as_of_date: str | date | datetime | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        self.store.initialize()
        normalized = _normalize_ticker(ticker)
        as_of = _parse_date(as_of_date)
        with self.store.connect() as conn:
            if as_of is None:
                as_of = self._latest_candidate_date(conn)
            if as_of is None:
                raise CandidatePoolError("候选池为空，请先生成候选池或手动加入股票。")
            existing = conn.execute(
                """
                SELECT reason
                FROM candidate_pool
                WHERE as_of_date = ? AND ticker = ?
                """,
                [as_of, normalized],
            ).fetchone()
            if existing is None:
                raise CandidatePoolError(f"候选池中未找到股票: {normalized}")
            next_reason = (reason or existing[0] or "").strip()
            conn.execute(
                """
                UPDATE candidate_pool
                SET included = ?, reason = ?
                WHERE as_of_date = ? AND ticker = ?
                """,
                [bool(included), next_reason, as_of, normalized],
            )
            updated = self._get_candidate(conn, as_of=as_of, ticker=normalized)
        if updated is None:
            raise CandidatePoolError(f"候选池中未找到股票: {normalized}")
        return updated

    @staticmethod
    def _latest_sector_score_date(conn: Any) -> date | None:
        row = conn.execute("SELECT MAX(trade_date) FROM sector_scores").fetchone()
        return _row_date(row[0]) if row and row[0] else None

    @staticmethod
    def _latest_candidate_date(conn: Any) -> date | None:
        row = conn.execute("SELECT MAX(as_of_date) FROM candidate_pool").fetchone()
        return _row_date(row[0]) if row and row[0] else None

    @staticmethod
    def _has_sector_scores(conn: Any, *, as_of: date, min_sector_score: float) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM sector_scores
            WHERE trade_date = ? AND sector_heat_score >= ?
            LIMIT 1
            """,
            [as_of, min_sector_score],
        ).fetchone()
        return row is not None

    @staticmethod
    def _asset_name(conn: Any, ticker: str) -> str | None:
        row = conn.execute("SELECT ticker_name FROM assets WHERE ticker = ?", [ticker]).fetchone()
        return str(row[0]) if row and row[0] else None

    @staticmethod
    def _get_candidate(conn: Any, *, as_of: date, ticker: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT as_of_date, ticker, ticker_name, market, source, sector_id,
                   sector_name, theme, event_heat_score, sector_heat_score,
                   stock_score, user_priority, risk_flag, included, reason, created_at
            FROM candidate_pool
            WHERE as_of_date = ? AND ticker = ?
            """,
            [as_of, ticker],
        ).fetchone()
        return _candidate_to_dict(row) if row else None

    @staticmethod
    def _load_mapped_stock_rows(conn: Any, *, as_of: date, min_sector_score: float) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT sm.ticker, sm.ticker_name, sm.theme, sm.sector_id, ss.sector_name,
                   MAX(sm.relevance), MAX(ss.event_heat), MAX(ss.sector_heat_score),
                   MAX(sm.mapping_reason)
            FROM event_stock_map sm
            JOIN events e ON e.event_id = sm.event_id
            JOIN sector_scores ss ON ss.sector_id = sm.sector_id AND ss.trade_date = ?
            WHERE CAST(e.tradable_time AS DATE) <= ? AND ss.sector_heat_score >= ?
            GROUP BY sm.ticker, sm.ticker_name, sm.theme, sm.sector_id, ss.sector_name
            ORDER BY MAX(ss.sector_heat_score) DESC, MAX(sm.relevance) DESC, sm.ticker
            LIMIT 1000
            """,
            [as_of, as_of, min_sector_score],
        ).fetchall()
        return [
            {
                "ticker": row[0],
                "ticker_name": row[1],
                "theme": row[2],
                "sector_id": row[3],
                "sector_name": row[4],
                "mapping_relevance": _float(row[5]),
                "event_heat_score": _float(row[6]),
                "sector_heat_score": _float(row[7]),
                "mapping_reason": row[8],
            }
            for row in rows
        ]

    def _build_system_candidate(self, conn: Any, *, as_of: date, row: dict[str, Any]) -> CandidateRow:
        ticker = _normalize_ticker(str(row["ticker"]))
        ticker_name = str(row.get("ticker_name") or self._asset_name(conn, ticker) or ticker)
        stock_rows = self._load_market_daily(conn, ticker, as_of)
        sector_rows = self._load_sector_daily(conn, str(row["sector_id"]), as_of)
        risk_flag, included = self._risk_gate(ticker=ticker, ticker_name=ticker_name, market_rows=stock_rows)
        risk_deduction = 0.0 if risk_flag == "normal" else 0.35
        stock_score = _round_score(
            _float(row["sector_heat_score"]) * 0.20
            + _float(row["mapping_relevance"]) * 0.20
            + self._relative_strength(stock_rows, sector_rows) * 0.20
            + self._price_volume_confirm(stock_rows) * 0.15
            + self._liquidity_score(stock_rows) * 0.10
            + _float(row["mapping_relevance"]) * 0.10
            + 0.50 * 0.05
            - risk_deduction
        )
        return CandidateRow(
            as_of_date=as_of,
            ticker=ticker,
            ticker_name=ticker_name,
            source="sector_radar",
            sector_id=str(row["sector_id"]),
            sector_name=str(row["sector_name"]),
            theme=str(row["theme"]),
            event_heat_score=_round_score(_float(row["event_heat_score"])),
            sector_heat_score=_round_score(_float(row["sector_heat_score"])),
            stock_score=stock_score,
            user_priority=0,
            risk_flag=risk_flag,
            included=included,
            reason=(
                f"{row['theme']} 主题映射；板块热度 {row['sector_heat_score']:.2f}；"
                f"主题相关度 {row['mapping_relevance']:.2f}。"
            ),
        )

    @staticmethod
    def _upsert_candidate(conn: Any, candidate: CandidateRow) -> None:
        existing = conn.execute(
            """
            SELECT source, user_priority, included, reason
            FROM candidate_pool
            WHERE as_of_date = ? AND ticker = ?
            """,
            [candidate.as_of_date, candidate.ticker],
        ).fetchone()
        source = candidate.source
        user_priority = candidate.user_priority
        included = candidate.included
        reason = candidate.reason
        if existing and existing[0] == "user_added" and candidate.source != "user_added":
            source = "user_added"
            user_priority = int(existing[1] or 100)
            included = bool(existing[2])
            reason = f"{existing[3] or '用户手动加入候选池。'}；系统评分已更新。"

        conn.execute(
            "DELETE FROM candidate_pool WHERE as_of_date = ? AND ticker = ?",
            [candidate.as_of_date, candidate.ticker],
        )
        conn.execute(
            """
            INSERT INTO candidate_pool (
              as_of_date, ticker, ticker_name, market, source, sector_id, sector_name,
              theme, event_heat_score, sector_heat_score, stock_score, user_priority,
              risk_flag, included, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                candidate.as_of_date,
                candidate.ticker,
                candidate.ticker_name,
                "CN_A",
                source,
                candidate.sector_id,
                candidate.sector_name,
                candidate.theme,
                candidate.event_heat_score,
                candidate.sector_heat_score,
                candidate.stock_score,
                user_priority,
                candidate.risk_flag,
                included,
                reason,
                _utc_now(),
            ],
        )

    @staticmethod
    def _infer_candidate_context(
        conn: Any,
        *,
        ticker: str,
        as_of: date,
        theme: str | None,
        sector_id: str | None,
        sector_name: str | None,
    ) -> dict[str, Any]:
        if theme or sector_id or sector_name:
            score = None
            if sector_id:
                score = conn.execute(
                    """
                    SELECT sector_name, event_heat, sector_heat_score
                    FROM sector_scores
                    WHERE trade_date = ? AND sector_id = ?
                    """,
                    [as_of, sector_id],
                ).fetchone()
            return {
                "ticker_name": None,
                "theme": theme,
                "sector_id": sector_id,
                "sector_name": sector_name or (score[0] if score else None),
                "event_heat_score": score[1] if score else 0.0,
                "sector_heat_score": score[2] if score else 0.0,
            }

        row = conn.execute(
            """
            SELECT sm.ticker_name, sm.theme, sm.sector_id, ss.sector_name,
                   ss.event_heat, ss.sector_heat_score
            FROM event_stock_map sm
            LEFT JOIN sector_scores ss ON ss.sector_id = sm.sector_id AND ss.trade_date = ?
            WHERE sm.ticker = ?
            ORDER BY COALESCE(ss.sector_heat_score, 0) DESC, sm.relevance DESC
            LIMIT 1
            """,
            [as_of, ticker],
        ).fetchone()
        if row is None:
            return {
                "ticker_name": None,
                "theme": None,
                "sector_id": None,
                "sector_name": None,
                "event_heat_score": 0.0,
                "sector_heat_score": 0.0,
            }
        return {
            "ticker_name": row[0],
            "theme": row[1],
            "sector_id": row[2],
            "sector_name": row[3],
            "event_heat_score": row[4],
            "sector_heat_score": row[5],
        }

    @staticmethod
    def _load_market_daily(conn: Any, ticker: str, as_of: date) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT trade_date, close, volume, amount, turnover, limit_status, suspended
            FROM market_daily
            WHERE ticker = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 20
            """,
            [ticker, as_of],
        ).fetchall()
        return [
            {
                "trade_date": _row_date(row[0]),
                "close": _float(row[1]) if row[1] is not None else None,
                "volume": _float(row[2]) if row[2] is not None else None,
                "amount": _float(row[3]) if row[3] is not None else None,
                "turnover": _float(row[4]) if row[4] is not None else None,
                "limit_status": row[5],
                "suspended": bool(row[6]),
            }
            for row in rows
        ]

    @staticmethod
    def _load_sector_daily(conn: Any, sector_id: str, as_of: date) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT trade_date, close, "return", amount, turnover
            FROM sector_daily
            WHERE sector_id = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 20
            """,
            [sector_id, as_of],
        ).fetchall()
        return [
            {
                "trade_date": _row_date(row[0]),
                "close": _float(row[1]) if row[1] is not None else None,
                "return": _float(row[2]) if row[2] is not None else None,
                "amount": _float(row[3]) if row[3] is not None else None,
                "turnover": _float(row[4]) if row[4] is not None else None,
            }
            for row in rows
        ]

    @staticmethod
    def _period_return(rows: list[dict[str, Any]], lookback: int) -> float | None:
        closes = [row["close"] for row in rows if row.get("close") is not None]
        if len(closes) < 2:
            return None
        start = closes[min(lookback - 1, len(closes) - 1)]
        end = closes[0]
        if not start:
            return None
        return float(end) / float(start) - 1.0

    def _relative_strength(self, stock_rows: list[dict[str, Any]], sector_rows: list[dict[str, Any]]) -> float:
        stock_ret_5 = self._period_return(stock_rows, 5)
        stock_ret_20 = self._period_return(stock_rows, 20)
        sector_ret_5 = sum(_float(row.get("return")) for row in sector_rows[:5]) if sector_rows else None
        sector_ret_20 = sum(_float(row.get("return")) for row in sector_rows[:20]) if sector_rows else None
        if stock_ret_5 is None:
            return 0.5
        score = 0.5
        if sector_ret_5 is not None:
            score += _clamp(stock_ret_5 - sector_ret_5, -0.12, 0.12) * 2.0
        if stock_ret_20 is not None and sector_ret_20 is not None:
            score += _clamp(stock_ret_20 - sector_ret_20, -0.20, 0.20) * 0.7
        return _round_score(score)

    @staticmethod
    def _price_volume_confirm(rows: list[dict[str, Any]]) -> float:
        if len(rows) < 2:
            return 0.5
        latest_close = rows[0].get("close") or 0.0
        previous_close = rows[1].get("close") or 0.0
        momentum = 0.6 if previous_close and latest_close > previous_close else 0.4
        amounts = [row["amount"] for row in rows if row.get("amount")]
        volume_score = 0.5
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            volume_score = _clamp((rows[0].get("amount") or avg_amount) / avg_amount / 2)
        return _round_score(momentum * 0.55 + volume_score * 0.45)

    @staticmethod
    def _liquidity_score(rows: list[dict[str, Any]]) -> float:
        amounts = [row["amount"] for row in rows if row.get("amount")]
        if not amounts:
            return 0.5
        avg_amount = sum(amounts) / len(amounts)
        return _round_score(min(avg_amount / 300_000_000, 1.0))

    @staticmethod
    def _risk_gate(*, ticker: str, ticker_name: str, market_rows: list[dict[str, Any]]) -> tuple[str, bool]:
        name = ticker_name.upper()
        if "ST" in name or "退" in ticker_name:
            return "st_or_delisting_risk", False
        if market_rows and market_rows[0].get("suspended"):
            return "suspended", False
        ret_5 = CandidatePoolService._period_return(market_rows, 5)
        if ret_5 is not None and ret_5 >= 0.35:
            return "short_term_extreme_gain", True
        if market_rows and market_rows[0].get("limit_status") == "limit_up":
            return "limit_up_crowding", True
        return "normal", True
