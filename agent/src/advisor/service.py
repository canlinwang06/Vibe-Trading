"""Local advisor ledger for Codex-directed portfolio facts.

The service records research-only transactions and current holdings. It never
talks to a broker and never places live orders.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore
from src.market_policy import is_a_share_code, normalize_a_share_code


DEFAULT_PORTFOLIO_ID = "cn_a_main"

STRATEGY_TYPE_ALIASES = {
    "long_quality_trend": "long_quality_trend",
    "长期质量趋势": "long_quality_trend",
    "quality_trend": "long_quality_trend",
    "medium_industry_cycle": "medium_industry_cycle",
    "中期景气趋势": "medium_industry_cycle",
    "industry_cycle": "medium_industry_cycle",
    "short_hotspot_momentum": "short_hotspot_momentum",
    "短期热点趋势": "short_hotspot_momentum",
    "hotspot_momentum": "short_hotspot_momentum",
    "event_driven_watch": "event_driven_watch",
    "事件驱动观察": "event_driven_watch",
    "backtest_candidate": "backtest_candidate",
    "回测候选策略": "backtest_candidate",
}

STRATEGY_TYPE_LABELS = {
    "long_quality_trend": "长期质量趋势",
    "medium_industry_cycle": "中期景气趋势",
    "short_hotspot_momentum": "短期热点趋势",
    "event_driven_watch": "事件驱动观察",
    "backtest_candidate": "回测候选策略",
}


class AdvisorError(RuntimeError):
    """Raised when an advisor ledger operation cannot be completed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return date.today()
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError as exc:
        raise AdvisorError(f"交易日期格式无效: {value}") from exc


def _date_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _dt_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _positive_float(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AdvisorError(f"{label}必须是数字") from exc
    if result <= 0:
        raise AdvisorError(f"{label}必须大于 0")
    return result


def _non_negative_float(value: Any, *, label: str) -> float:
    try:
        result = float(value or 0)
    except (TypeError, ValueError) as exc:
        raise AdvisorError(f"{label}必须是数字") from exc
    if result < 0:
        raise AdvisorError(f"{label}不能小于 0")
    return result


def _optional_float(value: Any, *, label: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AdvisorError(f"{label}必须是数字") from exc
    return result


def _normalize_ticker(ticker: str) -> str:
    normalized = normalize_a_share_code(ticker)
    if not is_a_share_code(normalized):
        raise AdvisorError(f"投资助手当前只记录沪深 A 股代码: {ticker}")
    return normalized


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()[:80]


def _new_id(prefix: str, seed: str | None = None) -> str:
    if seed:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _position_id(portfolio_id: str, ticker: str) -> str:
    return _new_id("pos", f"{portfolio_id}:{ticker}")


def _command_id(idempotency_key: str | None) -> str:
    return _new_id("cmd", idempotency_key) if idempotency_key else _new_id("cmd")


def _normalize_strategy_type(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = STRATEGY_TYPE_ALIASES.get(str(value).strip())
    if normalized is None:
        allowed = "、".join(STRATEGY_TYPE_LABELS.values())
        raise AdvisorError(f"策略类型暂只支持: {allowed}")
    return normalized


def _next_review_date(as_of: date, review_frequency_days: int | None) -> date | None:
    if review_frequency_days is None:
        return None
    return as_of + timedelta(days=max(int(review_frequency_days), 1))


def _non_empty(value: Any) -> bool:
    return value not in (None, "", {}, [])


def _thesis_completeness(
    *,
    buy_reason: str | None,
    entry_conditions: str | None,
    exit_conditions: str | None,
    not_buy_conditions: str | None,
    max_position_pct: float | None,
    target_holding_days: int | None,
    review_frequency_days: int | None,
    invalidation_conditions: str | None,
    stop_loss_price: float | None,
) -> tuple[str, list[str], bool]:
    missing: list[str] = []
    if not _non_empty(buy_reason):
        missing.append("买入或观察原因")
    if not _non_empty(entry_conditions):
        missing.append("入场条件")
    has_exit = _non_empty(exit_conditions) or _non_empty(invalidation_conditions) or stop_loss_price is not None
    if not has_exit:
        missing.append("退出条件")
    if not _non_empty(not_buy_conditions):
        missing.append("不买条件")
    if max_position_pct is None:
        missing.append("最大仓位")
    if target_holding_days is None:
        missing.append("预期持有周期")
    if review_frequency_days is None:
        missing.append("复盘频率")
    status = "complete" if not missing else "incomplete"
    return status, missing, has_exit


class AdvisorService:
    """Record user-directed research holdings and expose portfolio summaries."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def record_transaction(
        self,
        *,
        ticker: str,
        action: str,
        price: float,
        quantity: float,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        ticker_name: str | None = None,
        trade_date: str | date | datetime | None = None,
        fees: float = 0.0,
        strategy_type: str | None = None,
        strategy_cycle: str | None = None,
        thesis: str | None = None,
        buy_reason: str | None = None,
        expected_catalysts: str | None = None,
        invalidation_conditions: str | None = None,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
        max_position_pct: float | None = None,
        target_holding_days: int | None = None,
        reason: str | None = None,
        source_command: str | None = None,
        idempotency_key: str | None = None,
        created_by: str = "codex",
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a research-only buy/sell fact and update the local position."""
        self.store.initialize()
        request = {
            "portfolio_id": portfolio_id,
            "ticker": ticker,
            "ticker_name": ticker_name,
            "action": action,
            "price": price,
            "quantity": quantity,
            "trade_date": str(trade_date) if trade_date is not None else None,
            "fees": fees,
            "strategy_type": strategy_type,
            "strategy_cycle": strategy_cycle,
            "thesis": thesis,
            "buy_reason": buy_reason,
            "expected_catalysts": expected_catalysts,
            "invalidation_conditions": invalidation_conditions,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "max_position_pct": max_position_pct,
            "target_holding_days": target_holding_days,
            "reason": reason,
            "source_command": source_command,
            "idempotency_key": idempotency_key,
            "created_by": created_by,
            "evidence": evidence or {},
        }
        normalized_action = self._normalize_action(action)
        normalized_ticker = _normalize_ticker(ticker)
        trade_day = _parse_date(trade_date)
        clean_price = _positive_float(price, label="成交价格")
        clean_quantity = _positive_float(quantity, label="成交数量")
        clean_fees = _non_negative_float(fees, label="交易费用")
        clean_stop = _optional_float(stop_loss_price, label="卖出线")
        clean_take = _optional_float(take_profit_price, label="止盈线")
        clean_max_pct = _optional_float(max_position_pct, label="最大仓位")
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        clean_created_by = (created_by or "codex").strip() or "codex"

        with self.store.connect() as conn:
            replay = self._idempotent_replay(conn, idempotency_key)
            if replay is not None:
                replay["idempotent_replay"] = True
                return replay

            self._ensure_portfolio(conn, clean_portfolio_id)
            resolved_name = (
                ticker_name
                or self._asset_name(conn, normalized_ticker)
                or normalized_ticker
            ).strip()
            now = _utc_now()
            transaction_id = _new_id("txn", idempotency_key)
            thesis_id = self._ensure_thesis(
                conn,
                portfolio_id=clean_portfolio_id,
                ticker=normalized_ticker,
                ticker_name=resolved_name,
                thesis=thesis,
                buy_reason=buy_reason,
                expected_catalysts=expected_catalysts,
                invalidation_conditions=invalidation_conditions,
                strategy_type=strategy_type,
                strategy_cycle=strategy_cycle,
                stop_loss_price=clean_stop,
                take_profit_price=clean_take,
                max_position_pct=clean_max_pct,
                target_holding_days=target_holding_days,
                evidence=evidence,
                created_by=clean_created_by,
                created_at=now,
            )
            position = self._apply_transaction(
                conn,
                transaction_id=transaction_id,
                portfolio_id=clean_portfolio_id,
                ticker=normalized_ticker,
                ticker_name=resolved_name,
                action=normalized_action,
                price=clean_price,
                quantity=clean_quantity,
                trade_date=trade_day,
                trade_time=now,
                fees=clean_fees,
                strategy_type=strategy_type,
                strategy_cycle=strategy_cycle,
                thesis_id=thesis_id,
                reason=reason,
                source_command=source_command,
                idempotency_key=idempotency_key,
                created_by=clean_created_by,
                stop_loss_price=clean_stop,
                take_profit_price=clean_take,
                max_position_pct=clean_max_pct,
                evidence=evidence,
            )
            summary = self._portfolio_summary(conn, clean_portfolio_id)
            response = {
                "status": "ok",
                "transaction": {
                    "transaction_id": transaction_id,
                    "portfolio_id": clean_portfolio_id,
                    "ticker": normalized_ticker,
                    "ticker_name": resolved_name,
                    "action": normalized_action,
                    "price": clean_price,
                    "quantity": clean_quantity,
                    "fees": clean_fees,
                    "trade_date": trade_day.isoformat(),
                    "research_only": True,
                    "live_trading": False,
                },
                "position": position,
                "portfolio_summary": summary,
                "research_only": True,
                "live_trading": False,
            }
            self._record_command_event(
                conn,
                command_id=_command_id(idempotency_key),
                idempotency_key=idempotency_key,
                command_type=f"advisor_transaction_{normalized_action}",
                source="codex",
                portfolio_id=clean_portfolio_id,
                status="succeeded",
                request=request,
                response=response,
                error_message=None,
                created_by=clean_created_by,
                created_at=now,
            )
        return response

    def list_positions(self, *, portfolio_id: str = DEFAULT_PORTFOLIO_ID, include_closed: bool = False) -> list[dict[str, Any]]:
        """Return current research positions for the portfolio."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        with self.store.connect(read_only=True) as conn:
            filters = ["portfolio_id = ?"]
            params: list[Any] = [clean_portfolio_id]
            if not include_closed:
                filters.append("status <> 'closed'")
            rows = conn.execute(
                f"""
                SELECT position_id, portfolio_id, ticker, ticker_name, sector_id, sector_name,
                       strategy_type, strategy_cycle, total_quantity, available_quantity,
                       average_cost, invested_cost, realized_pnl, last_price, market_value,
                       unrealized_pnl, status, first_buy_date, last_trade_date, thesis_id,
                       stop_loss_price, take_profit_price, next_review_date, evidence_json,
                       created_at, updated_at
                FROM positions
                WHERE {" AND ".join(filters)}
                ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, ticker
                """,
                params,
            ).fetchall()
        return [self._position_tuple_to_dict(row) for row in rows]

    def portfolio_summary(self, *, portfolio_id: str = DEFAULT_PORTFOLIO_ID) -> dict[str, Any]:
        """Return a compact portfolio summary for the advisor display."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        with self.store.connect() as conn:
            self._ensure_portfolio(conn, clean_portfolio_id)
            return self._portfolio_summary(conn, clean_portfolio_id)

    def upsert_thesis(
        self,
        *,
        ticker: str,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        ticker_name: str | None = None,
        thesis_id: str | None = None,
        thesis_type: str = "manual_advisor",
        strategy_type: str | None = None,
        strategy_cycle: str | None = None,
        thesis: str | None = None,
        buy_reason: str | None = None,
        entry_conditions: str | None = None,
        exit_conditions: str | None = None,
        not_buy_conditions: str | None = None,
        expected_catalysts: str | None = None,
        invalidation_conditions: str | None = None,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
        max_position_pct: float | None = None,
        target_holding_days: int | None = None,
        review_frequency_days: int | None = None,
        as_of_date: str | date | datetime | None = None,
        evidence: dict[str, Any] | None = None,
        bind_to_position: bool = True,
        bind_to_watchlist: bool = True,
        created_by: str = "codex",
    ) -> dict[str, Any]:
        """Create or update an investment thesis and bind it to local advisor records."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        normalized_ticker = _normalize_ticker(ticker)
        normalized_strategy_type = _normalize_strategy_type(strategy_type)
        clean_stop = _optional_float(stop_loss_price, label="卖出线")
        clean_take = _optional_float(take_profit_price, label="止盈线")
        clean_max_pct = _optional_float(max_position_pct, label="最大仓位")
        clean_target_days = int(target_holding_days) if target_holding_days is not None else None
        clean_review_days = int(review_frequency_days) if review_frequency_days is not None else None
        if clean_target_days is not None and clean_target_days <= 0:
            raise AdvisorError("预期持有周期必须大于 0")
        if clean_review_days is not None and clean_review_days <= 0:
            raise AdvisorError("复盘频率必须大于 0")
        as_of = _parse_date(as_of_date)
        next_review = _next_review_date(as_of, clean_review_days)
        completeness_status, missing_fields, has_exit_condition = _thesis_completeness(
            buy_reason=buy_reason,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            not_buy_conditions=not_buy_conditions,
            max_position_pct=clean_max_pct,
            target_holding_days=clean_target_days,
            review_frequency_days=clean_review_days,
            invalidation_conditions=invalidation_conditions,
            stop_loss_price=clean_stop,
        )
        now = _utc_now()
        with self.store.connect() as conn:
            self._ensure_portfolio(conn, clean_portfolio_id)
            resolved_name = ticker_name or self._asset_name(conn, normalized_ticker) or normalized_ticker
            clean_thesis_id = thesis_id or self._latest_thesis_id(conn, clean_portfolio_id, normalized_ticker)
            if not clean_thesis_id:
                clean_thesis_id = _new_id("thesis", f"{clean_portfolio_id}:{normalized_ticker}:advisor")
            existing_created_at = self._thesis_created_at(conn, clean_thesis_id) or now
            conn.execute("DELETE FROM investment_theses WHERE thesis_id = ?", [clean_thesis_id])
            conn.execute(
                """
                INSERT INTO investment_theses (
                  thesis_id, portfolio_id, ticker, ticker_name, thesis_type, strategy_type,
                  strategy_cycle, thesis, buy_reason, expected_catalysts,
                  invalidation_conditions, stop_loss_price, take_profit_price,
                  max_position_pct, target_holding_days, entry_conditions,
                  exit_conditions, not_buy_conditions, review_frequency_days,
                  next_review_date, completeness_status, entry_rules_json,
                  exit_rules_json, evidence_json, status, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                [
                    clean_thesis_id,
                    clean_portfolio_id,
                    normalized_ticker,
                    resolved_name,
                    thesis_type,
                    normalized_strategy_type,
                    strategy_cycle,
                    thesis,
                    buy_reason,
                    expected_catalysts,
                    invalidation_conditions,
                    clean_stop,
                    clean_take,
                    clean_max_pct,
                    clean_target_days,
                    entry_conditions,
                    exit_conditions,
                    not_buy_conditions,
                    clean_review_days,
                    next_review,
                    completeness_status,
                    _json_dumps({"conditions": entry_conditions}),
                    _json_dumps({"conditions": exit_conditions, "invalidation": invalidation_conditions}),
                    _json_dumps(evidence or {}),
                    created_by,
                    existing_created_at,
                    now,
                ],
            )
            bound_position = None
            if bind_to_position:
                bound_position = self._bind_thesis_to_position(
                    conn,
                    portfolio_id=clean_portfolio_id,
                    ticker=normalized_ticker,
                    thesis_id=clean_thesis_id,
                    strategy_type=normalized_strategy_type,
                    strategy_cycle=strategy_cycle,
                    stop_loss_price=clean_stop,
                    take_profit_price=clean_take,
                    next_review_date=next_review,
                    updated_at=now,
                )
            watchlist_rows = 0
            if bind_to_watchlist:
                watchlist_rows = self._bind_thesis_to_watchlist(
                    conn,
                    portfolio_id=clean_portfolio_id,
                    ticker=normalized_ticker,
                    thesis_id=clean_thesis_id,
                    strategy_type=normalized_strategy_type,
                    strategy_cycle=strategy_cycle,
                    next_review_date=next_review,
                    updated_at=now,
                )
            result = self._fetch_thesis(conn, clean_thesis_id)
        result.update(
            {
                "missing_fields": missing_fields,
                "has_exit_condition": has_exit_condition,
                "can_enter_ready_to_buy": completeness_status == "complete" and has_exit_condition,
                "bound_position": bound_position,
                "bound_watchlist_count": watchlist_rows,
                "research_only": True,
                "live_trading": False,
            }
        )
        return result

    def list_theses(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        ticker: str | None = None,
        include_incomplete: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List advisor investment theses for holdings and watchlist items."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        filters = ["portfolio_id = ?"]
        params: list[Any] = [clean_portfolio_id]
        if ticker:
            filters.append("ticker = ?")
            params.append(_normalize_ticker(ticker))
        if not include_incomplete:
            filters.append("completeness_status = 'complete'")
        params.append(min(max(int(limit), 1), 500))
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT thesis_id
                FROM investment_theses
                WHERE {" AND ".join(filters)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [self._fetch_thesis(conn, str(row[0])) for row in rows]

    def _latest_thesis_id(self, conn: Any, portfolio_id: str, ticker: str) -> str | None:
        row = conn.execute(
            """
            SELECT thesis_id
            FROM investment_theses
            WHERE portfolio_id = ? AND ticker = ? AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [portfolio_id, ticker],
        ).fetchone()
        return str(row[0]) if row else None

    def _thesis_created_at(self, conn: Any, thesis_id: str) -> datetime | None:
        row = conn.execute(
            "SELECT created_at FROM investment_theses WHERE thesis_id = ?",
            [thesis_id],
        ).fetchone()
        return row[0] if row else None

    def _bind_thesis_to_position(
        self,
        conn: Any,
        *,
        portfolio_id: str,
        ticker: str,
        thesis_id: str,
        strategy_type: str | None,
        strategy_cycle: str | None,
        stop_loss_price: float | None,
        take_profit_price: float | None,
        next_review_date: date | None,
        updated_at: datetime,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT position_id
            FROM positions
            WHERE portfolio_id = ? AND ticker = ?
            ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, updated_at DESC
            LIMIT 1
            """,
            [portfolio_id, ticker],
        ).fetchone()
        if row is None:
            return None
        position_id = str(row[0])
        conn.execute(
            """
            UPDATE positions
            SET thesis_id = ?,
                strategy_type = COALESCE(?, strategy_type),
                strategy_cycle = COALESCE(?, strategy_cycle),
                stop_loss_price = COALESCE(?, stop_loss_price),
                take_profit_price = COALESCE(?, take_profit_price),
                next_review_date = COALESCE(?, next_review_date),
                updated_at = ?
            WHERE position_id = ?
            """,
            [
                thesis_id,
                strategy_type,
                strategy_cycle,
                stop_loss_price,
                take_profit_price,
                next_review_date,
                updated_at,
                position_id,
            ],
        )
        return self._fetch_position(conn, position_id)

    def _bind_thesis_to_watchlist(
        self,
        conn: Any,
        *,
        portfolio_id: str,
        ticker: str,
        thesis_id: str,
        strategy_type: str | None,
        strategy_cycle: str | None,
        next_review_date: date | None,
        updated_at: datetime,
    ) -> int:
        rows = conn.execute(
            """
            SELECT item_id
            FROM watchlist_items
            WHERE portfolio_id = ? AND ticker = ?
            """,
            [portfolio_id, ticker],
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                UPDATE watchlist_items
                SET thesis_id = ?,
                    strategy_type = COALESCE(?, strategy_type),
                    strategy_cycle = COALESCE(?, strategy_cycle),
                    next_review_date = COALESCE(?, next_review_date),
                    updated_at = ?
                WHERE item_id = ?
                """,
                [thesis_id, strategy_type, strategy_cycle, next_review_date, updated_at, row[0]],
            )
        return len(rows)

    def _fetch_thesis(self, conn: Any, thesis_id: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT thesis_id, portfolio_id, ticker, ticker_name, thesis_type,
                   strategy_type, strategy_cycle, thesis, buy_reason,
                   expected_catalysts, invalidation_conditions, stop_loss_price,
                   take_profit_price, max_position_pct, target_holding_days,
                   entry_conditions, exit_conditions, not_buy_conditions,
                   review_frequency_days, next_review_date, completeness_status,
                   entry_rules_json, exit_rules_json, evidence_json, status,
                   created_by, created_at, updated_at
            FROM investment_theses
            WHERE thesis_id = ?
            """,
            [thesis_id],
        ).fetchone()
        if row is None:
            raise AdvisorError("投资逻辑记录不存在")
        completeness_status, missing_fields, has_exit_condition = _thesis_completeness(
            buy_reason=row[8],
            entry_conditions=row[15],
            exit_conditions=row[16],
            not_buy_conditions=row[17],
            max_position_pct=row[13],
            target_holding_days=row[14],
            review_frequency_days=row[18],
            invalidation_conditions=row[10],
            stop_loss_price=row[11],
        )
        stored_status = row[20] or completeness_status
        return {
            "thesis_id": row[0],
            "portfolio_id": row[1],
            "ticker": row[2],
            "ticker_name": row[3],
            "thesis_type": row[4],
            "strategy_type": row[5],
            "strategy_type_label": STRATEGY_TYPE_LABELS.get(row[5], row[5]),
            "strategy_cycle": row[6],
            "thesis": row[7],
            "buy_reason": row[8],
            "expected_catalysts": row[9],
            "invalidation_conditions": row[10],
            "stop_loss_price": row[11],
            "take_profit_price": row[12],
            "max_position_pct": row[13],
            "target_holding_days": row[14],
            "entry_conditions": row[15],
            "exit_conditions": row[16],
            "not_buy_conditions": row[17],
            "review_frequency_days": row[18],
            "next_review_date": _date_or_none(row[19]),
            "completeness_status": stored_status,
            "missing_fields": missing_fields,
            "has_exit_condition": has_exit_condition,
            "can_enter_ready_to_buy": stored_status == "complete" and has_exit_condition,
            "entry_rules": _json_loads(row[21]),
            "exit_rules": _json_loads(row[22]),
            "evidence": _json_loads(row[23]),
            "status": row[24],
            "created_by": row[25],
            "created_at": _dt_or_none(row[26]),
            "updated_at": _dt_or_none(row[27]),
        }

    def _normalize_action(self, action: str) -> str:
        value = str(action or "").strip().lower()
        mapping = {
            "buy": "buy",
            "bought": "buy",
            "买": "buy",
            "买入": "buy",
            "sell": "sell",
            "sold": "sell",
            "卖": "sell",
            "卖出": "sell",
        }
        normalized = mapping.get(value, value)
        if normalized not in {"buy", "sell"}:
            raise AdvisorError("当前投资助手只记录买入或卖出事实，不连接券商下单")
        return normalized

    def _idempotent_replay(self, conn: Any, idempotency_key: str | None) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        row = conn.execute(
            """
            SELECT response_json
            FROM advisor_command_events
            WHERE idempotency_key = ? AND status = 'succeeded'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [idempotency_key],
        ).fetchone()
        if row is None:
            return None
        return _json_loads(row[0])

    def _ensure_portfolio(self, conn: Any, portfolio_id: str) -> None:
        row = conn.execute(
            "SELECT portfolio_id FROM portfolios WHERE portfolio_id = ?",
            [portfolio_id],
        ).fetchone()
        if row is not None:
            conn.execute(
                "UPDATE portfolios SET updated_at = ? WHERE portfolio_id = ?",
                [_utc_now(), portfolio_id],
            )
            return
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO portfolios (
              portfolio_id, portfolio_name, base_currency, initial_cash, cash_balance,
              research_only, live_trading, status, created_at, updated_at
            )
            VALUES (?, ?, 'CNY', 0.0, 0.0, true, false, 'active', ?, ?)
            """,
            [portfolio_id, "A股投资助手组合", now, now],
        )

    def _asset_name(self, conn: Any, ticker: str) -> str | None:
        row = conn.execute(
            "SELECT ticker_name FROM assets WHERE ticker = ? LIMIT 1",
            [ticker],
        ).fetchone()
        if row is None or not row[0]:
            return None
        return str(row[0])

    def _latest_price(self, conn: Any, ticker: str, as_of: date, fallback: float) -> float:
        row = conn.execute(
            """
            SELECT close
            FROM market_daily
            WHERE ticker = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            [ticker, as_of],
        ).fetchone()
        if row is None or row[0] is None:
            return fallback
        try:
            return float(row[0])
        except (TypeError, ValueError):
            return fallback

    def _ensure_thesis(
        self,
        conn: Any,
        *,
        portfolio_id: str,
        ticker: str,
        ticker_name: str,
        thesis: str | None,
        buy_reason: str | None,
        expected_catalysts: str | None,
        invalidation_conditions: str | None,
        strategy_type: str | None,
        strategy_cycle: str | None,
        stop_loss_price: float | None,
        take_profit_price: float | None,
        max_position_pct: float | None,
        target_holding_days: int | None,
        evidence: dict[str, Any] | None,
        created_by: str,
        created_at: datetime,
    ) -> str | None:
        has_thesis = any(
            value not in (None, "", {}, [])
            for value in (
                thesis,
                buy_reason,
                expected_catalysts,
                invalidation_conditions,
                strategy_type,
                strategy_cycle,
                evidence,
            )
        )
        if not has_thesis:
            return None
        thesis_id = _new_id("thesis", f"{portfolio_id}:{ticker}:{created_at.isoformat()}")
        conn.execute(
            """
            INSERT INTO investment_theses (
              thesis_id, portfolio_id, ticker, ticker_name, thesis_type, strategy_type,
              strategy_cycle, thesis, buy_reason, expected_catalysts,
              invalidation_conditions, stop_loss_price, take_profit_price,
              max_position_pct, target_holding_days, entry_rules_json, exit_rules_json,
              evidence_json, status, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'manual_position', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', '{}', ?, 'active', ?, ?, ?)
            """,
            [
                thesis_id,
                portfolio_id,
                ticker,
                ticker_name,
                strategy_type,
                strategy_cycle,
                thesis,
                buy_reason,
                expected_catalysts,
                invalidation_conditions,
                stop_loss_price,
                take_profit_price,
                max_position_pct,
                int(target_holding_days) if target_holding_days is not None else None,
                _json_dumps(evidence or {}),
                created_by,
                created_at,
                created_at,
            ],
        )
        return thesis_id

    def _apply_transaction(
        self,
        conn: Any,
        *,
        transaction_id: str,
        portfolio_id: str,
        ticker: str,
        ticker_name: str,
        action: str,
        price: float,
        quantity: float,
        trade_date: date,
        trade_time: datetime,
        fees: float,
        strategy_type: str | None,
        strategy_cycle: str | None,
        thesis_id: str | None,
        reason: str | None,
        source_command: str | None,
        idempotency_key: str | None,
        created_by: str,
        stop_loss_price: float | None,
        take_profit_price: float | None,
        max_position_pct: float | None,
        evidence: dict[str, Any] | None,
    ) -> dict[str, Any]:
        gross = round(price * quantity, 6)
        net = gross + fees if action == "buy" else gross - fees
        conn.execute(
            """
            INSERT INTO advisor_transactions (
              transaction_id, portfolio_id, ticker, ticker_name, trade_date, trade_time,
              action, price, quantity, gross_amount, fees, net_amount, strategy_type,
              strategy_cycle, thesis_id, reason, source_command, idempotency_key,
              created_by, research_only, live_trading, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, true, false, ?)
            """,
            [
                transaction_id,
                portfolio_id,
                ticker,
                ticker_name,
                trade_date,
                trade_time,
                action,
                price,
                quantity,
                gross,
                fees,
                net,
                strategy_type,
                strategy_cycle,
                thesis_id,
                reason,
                source_command,
                idempotency_key,
                created_by,
                trade_time,
            ],
        )
        if action == "buy":
            return self._apply_buy(
                conn,
                transaction_id=transaction_id,
                portfolio_id=portfolio_id,
                ticker=ticker,
                ticker_name=ticker_name,
                price=price,
                quantity=quantity,
                trade_date=trade_date,
                fees=fees,
                strategy_type=strategy_type,
                strategy_cycle=strategy_cycle,
                thesis_id=thesis_id,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                max_position_pct=max_position_pct,
                evidence=evidence,
                created_at=trade_time,
            )
        return self._apply_sell(
            conn,
            portfolio_id=portfolio_id,
            ticker=ticker,
            price=price,
            quantity=quantity,
            trade_date=trade_date,
            fees=fees,
            created_at=trade_time,
        )

    def _position_row(self, conn: Any, portfolio_id: str, ticker: str) -> tuple[Any, ...] | None:
        return conn.execute(
            """
            SELECT position_id, total_quantity, average_cost, invested_cost,
                   realized_pnl, first_buy_date, thesis_id, created_at, ticker_name,
                   strategy_type, strategy_cycle
            FROM positions
            WHERE portfolio_id = ? AND ticker = ?
            ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, updated_at DESC
            LIMIT 1
            """,
            [portfolio_id, ticker],
        ).fetchone()

    def _apply_buy(
        self,
        conn: Any,
        *,
        transaction_id: str,
        portfolio_id: str,
        ticker: str,
        ticker_name: str,
        price: float,
        quantity: float,
        trade_date: date,
        fees: float,
        strategy_type: str | None,
        strategy_cycle: str | None,
        thesis_id: str | None,
        stop_loss_price: float | None,
        take_profit_price: float | None,
        max_position_pct: float | None,
        evidence: dict[str, Any] | None,
        created_at: datetime,
    ) -> dict[str, Any]:
        position_id = _position_id(portfolio_id, ticker)
        old = self._position_row(conn, portfolio_id, ticker)
        old_qty = float(old[1]) if old else 0.0
        old_cost = float(old[3]) if old and old[3] is not None else 0.0
        old_realized = float(old[4]) if old and old[4] is not None else 0.0
        old_first_buy = old[5] if old else trade_date
        old_created_at = old[7] if old else created_at
        effective_thesis_id = thesis_id or (old[6] if old else None)
        effective_strategy_type = strategy_type or (old[9] if old else None)
        effective_strategy_cycle = strategy_cycle or (old[10] if old else None)
        buy_cost = price * quantity + fees
        total_quantity = old_qty + quantity
        invested_cost = old_cost + buy_cost
        average_cost = invested_cost / total_quantity
        last_price = self._latest_price(conn, ticker, trade_date, price)
        market_value = last_price * total_quantity
        unrealized_pnl = market_value - invested_cost
        lot_id = _new_id("lot", transaction_id)
        conn.execute(
            """
            INSERT INTO position_lots (
              lot_id, transaction_id, portfolio_id, position_id, ticker, ticker_name,
              buy_date, buy_price, initial_quantity, remaining_quantity, fees,
              cost_basis, status, thesis_id, stop_loss_price, take_profit_price,
              max_position_pct, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
            """,
            [
                lot_id,
                transaction_id,
                portfolio_id,
                position_id,
                ticker,
                ticker_name,
                trade_date,
                price,
                quantity,
                quantity,
                fees,
                buy_cost,
                effective_thesis_id,
                stop_loss_price,
                take_profit_price,
                max_position_pct,
                created_at,
                created_at,
            ],
        )
        self._replace_position(
            conn,
            position_id=position_id,
            portfolio_id=portfolio_id,
            ticker=ticker,
            ticker_name=ticker_name,
            strategy_type=effective_strategy_type,
            strategy_cycle=effective_strategy_cycle,
            total_quantity=total_quantity,
            average_cost=average_cost,
            invested_cost=invested_cost,
            realized_pnl=old_realized,
            last_price=last_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            status="open",
            first_buy_date=old_first_buy,
            last_trade_date=trade_date,
            thesis_id=effective_thesis_id,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            evidence=evidence,
            created_at=old_created_at,
            updated_at=created_at,
        )
        return self._fetch_position(conn, position_id)

    def _apply_sell(
        self,
        conn: Any,
        *,
        portfolio_id: str,
        ticker: str,
        price: float,
        quantity: float,
        trade_date: date,
        fees: float,
        created_at: datetime,
    ) -> dict[str, Any]:
        old = self._position_row(conn, portfolio_id, ticker)
        if old is None:
            raise AdvisorError(f"没有可卖出的持仓: {ticker}")
        position_id = str(old[0])
        old_qty = float(old[1] or 0.0)
        average_cost = float(old[2] or 0.0)
        old_realized = float(old[4] or 0.0)
        if quantity > old_qty + 1e-9:
            raise AdvisorError(f"卖出数量超过当前持仓: 当前 {old_qty:g} 股，尝试卖出 {quantity:g} 股")
        self._consume_lots_fifo(conn, portfolio_id=portfolio_id, ticker=ticker, quantity=quantity, updated_at=created_at)
        remaining_qty = max(0.0, old_qty - quantity)
        realized_pnl = old_realized + (price - average_cost) * quantity - fees
        invested_cost = average_cost * remaining_qty
        status = "closed" if remaining_qty <= 1e-9 else "open"
        last_price = self._latest_price(conn, ticker, trade_date, price) if status == "open" else price
        market_value = last_price * remaining_qty
        unrealized_pnl = market_value - invested_cost
        self._replace_position(
            conn,
            position_id=position_id,
            portfolio_id=portfolio_id,
            ticker=ticker,
            ticker_name=str(old[8] or ticker),
            strategy_type=old[9],
            strategy_cycle=old[10],
            total_quantity=remaining_qty,
            average_cost=average_cost if status == "open" else 0.0,
            invested_cost=invested_cost,
            realized_pnl=realized_pnl,
            last_price=last_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            status=status,
            first_buy_date=old[5],
            last_trade_date=trade_date,
            thesis_id=old[6],
            stop_loss_price=None,
            take_profit_price=None,
            evidence=None,
            created_at=old[7],
            updated_at=created_at,
        )
        return self._fetch_position(conn, position_id)

    def _consume_lots_fifo(
        self,
        conn: Any,
        *,
        portfolio_id: str,
        ticker: str,
        quantity: float,
        updated_at: datetime,
    ) -> None:
        remaining_to_close = quantity
        rows = conn.execute(
            """
            SELECT lot_id, remaining_quantity
            FROM position_lots
            WHERE portfolio_id = ? AND ticker = ? AND remaining_quantity > 0
            ORDER BY buy_date, created_at, lot_id
            """,
            [portfolio_id, ticker],
        ).fetchall()
        for lot_id, lot_remaining in rows:
            if remaining_to_close <= 1e-9:
                break
            current = float(lot_remaining or 0.0)
            close_qty = min(current, remaining_to_close)
            new_remaining = max(0.0, current - close_qty)
            new_status = "closed" if new_remaining <= 1e-9 else "open"
            conn.execute(
                """
                UPDATE position_lots
                SET remaining_quantity = ?, status = ?, updated_at = ?
                WHERE lot_id = ?
                """,
                [new_remaining, new_status, updated_at, lot_id],
            )
            remaining_to_close -= close_qty
        if remaining_to_close > 1e-6:
            raise AdvisorError("持仓批次数量不足，无法完成卖出记录")

    def _replace_position(
        self,
        conn: Any,
        *,
        position_id: str,
        portfolio_id: str,
        ticker: str,
        ticker_name: str,
        strategy_type: str | None,
        strategy_cycle: str | None,
        total_quantity: float,
        average_cost: float,
        invested_cost: float,
        realized_pnl: float,
        last_price: float,
        market_value: float,
        unrealized_pnl: float,
        status: str,
        first_buy_date: Any,
        last_trade_date: date,
        thesis_id: str | None,
        stop_loss_price: float | None,
        take_profit_price: float | None,
        evidence: dict[str, Any] | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        conn.execute("DELETE FROM positions WHERE position_id = ?", [position_id])
        conn.execute(
            """
            INSERT INTO positions (
              position_id, portfolio_id, ticker, ticker_name, sector_id, sector_name,
              strategy_type, strategy_cycle, total_quantity, available_quantity,
              average_cost, invested_cost, realized_pnl, last_price, market_value,
              unrealized_pnl, status, first_buy_date, last_trade_date, thesis_id,
              stop_loss_price, take_profit_price, next_review_date, evidence_json,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            [
                position_id,
                portfolio_id,
                ticker,
                ticker_name,
                strategy_type,
                strategy_cycle,
                total_quantity,
                total_quantity,
                average_cost,
                invested_cost,
                realized_pnl,
                last_price,
                market_value,
                unrealized_pnl,
                status,
                first_buy_date,
                last_trade_date,
                thesis_id,
                stop_loss_price,
                take_profit_price,
                _json_dumps(evidence or {}),
                created_at,
                updated_at,
            ],
        )

    def _fetch_position(self, conn: Any, position_id: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT position_id, portfolio_id, ticker, ticker_name, sector_id, sector_name,
                   strategy_type, strategy_cycle, total_quantity, available_quantity,
                   average_cost, invested_cost, realized_pnl, last_price, market_value,
                   unrealized_pnl, status, first_buy_date, last_trade_date, thesis_id,
                   stop_loss_price, take_profit_price, next_review_date, evidence_json,
                   created_at, updated_at
            FROM positions
            WHERE position_id = ?
            """,
            [position_id],
        ).fetchone()
        if row is None:
            raise AdvisorError("持仓记录写入失败")
        return self._position_tuple_to_dict(row)

    def _position_tuple_to_dict(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "position_id": row[0],
            "portfolio_id": row[1],
            "ticker": row[2],
            "ticker_name": row[3],
            "sector_id": row[4],
            "sector_name": row[5],
            "strategy_type": row[6],
            "strategy_cycle": row[7],
            "total_quantity": float(row[8] or 0.0),
            "available_quantity": float(row[9] or 0.0),
            "average_cost": round(float(row[10] or 0.0), 4),
            "invested_cost": round(float(row[11] or 0.0), 4),
            "realized_pnl": round(float(row[12] or 0.0), 4),
            "last_price": round(float(row[13] or 0.0), 4),
            "market_value": round(float(row[14] or 0.0), 4),
            "unrealized_pnl": round(float(row[15] or 0.0), 4),
            "status": row[16],
            "first_buy_date": _date_or_none(row[17]),
            "last_trade_date": _date_or_none(row[18]),
            "thesis_id": row[19],
            "stop_loss_price": row[20],
            "take_profit_price": row[21],
            "next_review_date": _date_or_none(row[22]),
            "evidence": _json_loads(row[23]),
            "created_at": _dt_or_none(row[24]),
            "updated_at": _dt_or_none(row[25]),
        }

    def _portfolio_summary(self, conn: Any, portfolio_id: str) -> dict[str, Any]:
        portfolio = conn.execute(
            """
            SELECT portfolio_id, portfolio_name, base_currency, initial_cash, cash_balance,
                   research_only, live_trading, status, created_at, updated_at
            FROM portfolios
            WHERE portfolio_id = ?
            """,
            [portfolio_id],
        ).fetchone()
        if portfolio is None:
            raise AdvisorError("组合记录不存在")
        rows = conn.execute(
            """
            SELECT ticker, ticker_name, total_quantity, average_cost, invested_cost,
                   market_value, unrealized_pnl, realized_pnl, status
            FROM positions
            WHERE portfolio_id = ? AND status <> 'closed'
            ORDER BY ticker
            """,
            [portfolio_id],
        ).fetchall()
        invested_cost = sum(float(row[4] or 0.0) for row in rows)
        market_value = sum(float(row[5] or 0.0) for row in rows)
        unrealized_pnl = sum(float(row[6] or 0.0) for row in rows)
        realized_row = conn.execute(
            "SELECT SUM(realized_pnl) FROM positions WHERE portfolio_id = ?",
            [portfolio_id],
        ).fetchone()
        realized_pnl = float(realized_row[0] or 0.0) if realized_row else 0.0
        return {
            "portfolio_id": portfolio[0],
            "portfolio_name": portfolio[1],
            "base_currency": portfolio[2],
            "initial_cash": float(portfolio[3] or 0.0),
            "cash_balance": float(portfolio[4] or 0.0),
            "position_count": len(rows),
            "invested_cost": round(invested_cost, 4),
            "market_value": round(market_value, 4),
            "unrealized_pnl": round(unrealized_pnl, 4),
            "realized_pnl": round(realized_pnl, 4),
            "total_pnl": round(unrealized_pnl + realized_pnl, 4),
            "positions": [
                {
                    "ticker": row[0],
                    "ticker_name": row[1],
                    "total_quantity": float(row[2] or 0.0),
                    "average_cost": round(float(row[3] or 0.0), 4),
                    "invested_cost": round(float(row[4] or 0.0), 4),
                    "market_value": round(float(row[5] or 0.0), 4),
                    "unrealized_pnl": round(float(row[6] or 0.0), 4),
                    "realized_pnl": round(float(row[7] or 0.0), 4),
                    "status": row[8],
                }
                for row in rows
            ],
            "research_only": bool(portfolio[5]),
            "live_trading": bool(portfolio[6]),
            "status": portfolio[7],
            "updated_at": _dt_or_none(portfolio[9]),
        }

    def _record_command_event(
        self,
        conn: Any,
        *,
        command_id: str,
        idempotency_key: str | None,
        command_type: str,
        source: str,
        portfolio_id: str,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any],
        error_message: str | None,
        created_by: str,
        created_at: datetime,
    ) -> None:
        conn.execute(
            """
            INSERT INTO advisor_command_events (
              command_id, idempotency_key, command_type, source, portfolio_id,
              status, request_json, response_json, error_message, created_by,
              research_only, live_trading, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, true, false, ?)
            """,
            [
                command_id,
                idempotency_key,
                command_type,
                source,
                portfolio_id,
                status,
                _json_dumps(request),
                _json_dumps(response),
                error_message,
                created_by,
                created_at,
            ],
        )
