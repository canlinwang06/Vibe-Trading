"""Local advisor ledger for Codex-directed portfolio facts.

The service records research-only transactions and current holdings. It never
talks to a broker and never places live orders.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter
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


def _parse_optional_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


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

    def resolve_prices(
        self,
        *,
        tickers: list[str],
        as_of_date: str | date | datetime | None = None,
        stale_after_days: int = 5,
    ) -> dict[str, Any]:
        """Resolve latest available local prices and data-freshness status."""
        self.store.initialize()
        as_of = _parse_date(as_of_date)
        normalized = []
        for ticker in tickers:
            clean = _normalize_ticker(ticker)
            if clean not in normalized:
                normalized.append(clean)
        max_stale_days = max(int(stale_after_days), 1)
        with self.store.connect(read_only=True) as conn:
            prices = [
                self._resolve_price_row(conn, ticker=ticker, as_of=as_of, stale_after_days=max_stale_days)
                for ticker in normalized
            ]
        return {
            "as_of_date": as_of.isoformat(),
            "prices": prices,
            "price_count": len(prices),
            "research_only": True,
            "live_trading": False,
        }

    def resolve_portfolio_prices(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        as_of_date: str | date | datetime | None = None,
        include_watchlist: bool = True,
        stale_after_days: int = 5,
    ) -> dict[str, Any]:
        """Resolve local prices for current holdings and optional watchlist names."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT ticker
                FROM positions
                WHERE portfolio_id = ? AND status <> 'closed'
                ORDER BY ticker
                """,
                [clean_portfolio_id],
            ).fetchall()
            tickers = [str(row[0]) for row in rows]
            if include_watchlist:
                watch_rows = conn.execute(
                    """
                    SELECT ticker
                    FROM watchlist_items
                    WHERE portfolio_id = ?
                    ORDER BY ticker
                    """,
                    [clean_portfolio_id],
                ).fetchall()
                for row in watch_rows:
                    ticker = str(row[0])
                    if ticker not in tickers:
                        tickers.append(ticker)
        result = self.resolve_prices(
            tickers=tickers,
            as_of_date=as_of_date,
            stale_after_days=stale_after_days,
        )
        result["portfolio_id"] = clean_portfolio_id
        result["include_watchlist"] = include_watchlist
        return result

    def diagnose_holdings(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        as_of_date: str | date | datetime | None = None,
        stale_after_days: int = 5,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Generate research-only next-action diagnostics for open holdings."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        as_of = _parse_date(as_of_date)
        max_stale_days = max(int(stale_after_days), 1)
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT position_id, portfolio_id, ticker, ticker_name, sector_id, sector_name,
                       strategy_type, strategy_cycle, total_quantity, available_quantity,
                       average_cost, invested_cost, realized_pnl, last_price, market_value,
                       unrealized_pnl, status, first_buy_date, last_trade_date, thesis_id,
                       stop_loss_price, take_profit_price, next_review_date, evidence_json,
                       created_at, updated_at
                FROM positions
                WHERE portfolio_id = ? AND status <> 'closed'
                ORDER BY ticker
                """,
                [clean_portfolio_id],
            ).fetchall()
            diagnostics: list[dict[str, Any]] = []
            for row in rows:
                position = self._position_tuple_to_dict(row)
                thesis = self._thesis_for_position(conn, position)
                price = self._resolve_price_row(
                    conn,
                    ticker=position["ticker"],
                    as_of=as_of,
                    stale_after_days=max_stale_days,
                )
                diagnostic = self._diagnose_position(
                    position=position,
                    thesis=thesis,
                    price=price,
                    as_of=as_of,
                )
                if persist:
                    self._record_holding_recommendation(conn, clean_portfolio_id, diagnostic, as_of)
                diagnostics.append(diagnostic)
        action_counts = dict(sorted(Counter(row["action"] for row in diagnostics).items()))
        return {
            "status": "ok",
            "portfolio_id": clean_portfolio_id,
            "as_of_date": as_of.isoformat(),
            "diagnostics": diagnostics,
            "diagnostic_count": len(diagnostics),
            "action_counts": action_counts,
            "research_only": True,
            "live_trading": False,
        }

    def upsert_watchlist_item(
        self,
        *,
        ticker: str,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        ticker_name: str | None = None,
        theme: str | None = None,
        sector_id: str | None = None,
        sector_name: str | None = None,
        strategy_type: str | None = None,
        strategy_cycle: str | None = None,
        watch_status: str = "watching",
        target_buy_price: float | None = None,
        trigger_price: float | None = None,
        stop_loss_price: float | None = None,
        max_position_pct: float | None = None,
        not_buy_conditions: str | None = None,
        reason: str | None = None,
        evidence: dict[str, Any] | None = None,
        thesis_id: str | None = None,
        next_review_date: str | date | datetime | None = None,
        created_by: str = "codex",
    ) -> dict[str, Any]:
        """Create or update a research-only watchlist candidate."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        normalized_ticker = _normalize_ticker(ticker)
        normalized_strategy_type = _normalize_strategy_type(strategy_type)
        clean_target = _optional_float(target_buy_price, label="目标买入价")
        clean_trigger = _optional_float(trigger_price, label="买入触发价")
        clean_stop = _optional_float(stop_loss_price, label="卖出线")
        clean_max_pct = _optional_float(max_position_pct, label="最大仓位")
        review_date = _parse_optional_date(next_review_date)
        now = _utc_now()
        with self.store.connect() as conn:
            self._ensure_portfolio(conn, clean_portfolio_id)
            resolved_name = ticker_name or self._asset_name(conn, normalized_ticker) or normalized_ticker
            existing = conn.execute(
                """
                SELECT item_id, created_at
                FROM watchlist_items
                WHERE portfolio_id = ? AND ticker = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                [clean_portfolio_id, normalized_ticker],
            ).fetchone()
            item_id = str(existing[0]) if existing else _new_id("watch", f"{clean_portfolio_id}:{normalized_ticker}")
            created_at = existing[1] if existing else now
            clean_thesis_id = thesis_id or self._latest_thesis_id(conn, clean_portfolio_id, normalized_ticker)
            conn.execute("DELETE FROM watchlist_items WHERE item_id = ?", [item_id])
            conn.execute(
                """
                INSERT INTO watchlist_items (
                  item_id, portfolio_id, ticker, ticker_name, sector_id, sector_name,
                  theme, thesis_id, strategy_type, strategy_cycle, watch_status,
                  target_buy_price, trigger_price, stop_loss_price, max_position_pct,
                  not_buy_conditions, reason, evidence_json, next_review_date,
                  created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    item_id,
                    clean_portfolio_id,
                    normalized_ticker,
                    resolved_name,
                    sector_id,
                    sector_name,
                    theme,
                    clean_thesis_id,
                    normalized_strategy_type,
                    strategy_cycle,
                    watch_status,
                    clean_target,
                    clean_trigger,
                    clean_stop,
                    clean_max_pct,
                    not_buy_conditions,
                    reason,
                    _json_dumps(evidence or {}),
                    review_date,
                    created_by,
                    created_at,
                    now,
                ],
            )
            return self._fetch_watchlist_item(conn, item_id)

    def build_watchlist_candidates(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        as_of_date: str | date | datetime | None = None,
        limit: int = 50,
        stale_after_days: int = 5,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Build advisor-facing candidate states from watchlist and candidate pool."""
        self.store.initialize()
        clean_portfolio_id = (portfolio_id or DEFAULT_PORTFOLIO_ID).strip() or DEFAULT_PORTFOLIO_ID
        as_of = _parse_date(as_of_date)
        capped_limit = min(max(int(limit), 1), 200)
        with self.store.connect() as conn:
            rows = self._load_watchlist_sources(conn, clean_portfolio_id, as_of, capped_limit)
            held_tickers = {
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT ticker
                    FROM positions
                    WHERE portfolio_id = ? AND status <> 'closed'
                    """,
                    [clean_portfolio_id],
                ).fetchall()
            }
            candidates: list[dict[str, Any]] = []
            for row in rows:
                thesis = self._thesis_for_watchlist_source(conn, clean_portfolio_id, row)
                price = self._resolve_price_row(
                    conn,
                    ticker=row["ticker"],
                    as_of=as_of,
                    stale_after_days=max(int(stale_after_days), 1),
                )
                candidate = self._evaluate_watchlist_candidate(
                    source=row,
                    thesis=thesis,
                    price=price,
                    as_of=as_of,
                    held_tickers=held_tickers,
                )
                if persist:
                    self._record_watchlist_recommendation(conn, clean_portfolio_id, candidate, as_of)
                candidates.append(candidate)
        status_counts = dict(sorted(Counter(row["suggested_status"] for row in candidates).items()))
        return {
            "status": "ok",
            "portfolio_id": clean_portfolio_id,
            "as_of_date": as_of.isoformat(),
            "candidates": candidates,
            "candidate_count": len(candidates),
            "status_counts": status_counts,
            "research_only": True,
            "live_trading": False,
        }

    def build_risk_filters(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        as_of_date: str | date | datetime | None = None,
        limit: int = 50,
        stale_after_days: int = 5,
    ) -> dict[str, Any]:
        """Build a current-stage do-not-buy list from candidate risk rules."""
        candidates_result = self.build_watchlist_candidates(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            limit=limit,
            stale_after_days=stale_after_days,
            persist=False,
        )
        risk_items: list[dict[str, Any]] = []
        for candidate in candidates_result["candidates"]:
            for flag in self._risk_flags_for_candidate(candidate):
                risk_items.append(flag)
        rule_counts = dict(sorted(Counter(item["rule_id"] for item in risk_items).items()))
        return {
            "status": "ok",
            "portfolio_id": candidates_result["portfolio_id"],
            "as_of_date": candidates_result["as_of_date"],
            "do_not_buy_items": risk_items,
            "item_count": len(risk_items),
            "rule_counts": rule_counts,
            "scope": "current_stage_risk_only",
            "research_only": True,
            "live_trading": False,
        }

    def today_snapshot(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        as_of_date: str | date | datetime | None = None,
    ) -> dict[str, Any]:
        """Return display-ready data for the advisor today page."""
        as_of = _parse_date(as_of_date)
        summary = self.portfolio_summary(portfolio_id=portfolio_id)
        diagnostics = self.diagnose_holdings(portfolio_id=portfolio_id, as_of_date=as_of, persist=True)
        candidates = self.build_watchlist_candidates(portfolio_id=portfolio_id, as_of_date=as_of, persist=True)
        risks = self.build_risk_filters(portfolio_id=portfolio_id, as_of_date=as_of)
        headline = self._today_headline(diagnostics, candidates, risks)
        primary_actions = self._primary_actions(diagnostics, candidates, risks)
        snapshot = {
            "snapshot_type": "today",
            "title": "今日建议",
            "portfolio_id": portfolio_id,
            "as_of_date": as_of.isoformat(),
            "headline": headline,
            "summary_cards": [
                {"label": "持仓数量", "value": summary["position_count"]},
                {"label": "候选数量", "value": candidates["candidate_count"]},
                {"label": "暂不买风险", "value": risks["item_count"]},
                {"label": "总盈亏", "value": summary["total_pnl"]},
            ],
            "primary_actions": primary_actions,
            "holding_action_counts": diagnostics["action_counts"],
            "candidate_status_counts": candidates["status_counts"],
            "risk_rule_counts": risks["rule_counts"],
            "data_freshness": self._snapshot_data_freshness(diagnostics, candidates),
            "research_only": True,
            "live_trading": False,
        }
        self._record_snapshot(snapshot)
        return snapshot

    def holdings_snapshot(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        as_of_date: str | date | datetime | None = None,
    ) -> dict[str, Any]:
        """Return display-ready data for the holdings care page."""
        as_of = _parse_date(as_of_date)
        summary = self.portfolio_summary(portfolio_id=portfolio_id)
        diagnostics = self.diagnose_holdings(portfolio_id=portfolio_id, as_of_date=as_of, persist=True)
        prices = self.resolve_portfolio_prices(
            portfolio_id=portfolio_id,
            as_of_date=as_of,
            include_watchlist=False,
        )
        snapshot = {
            "snapshot_type": "holdings",
            "title": "我的持仓",
            "portfolio_id": portfolio_id,
            "as_of_date": as_of.isoformat(),
            "headline": "优先看护已买股票，明确持有、退出或补充逻辑。",
            "portfolio_summary": summary,
            "diagnostics": diagnostics["diagnostics"],
            "prices": prices["prices"],
            "action_counts": diagnostics["action_counts"],
            "research_only": True,
            "live_trading": False,
        }
        self._record_snapshot(snapshot)
        return snapshot

    def watchlist_snapshot(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        as_of_date: str | date | datetime | None = None,
    ) -> dict[str, Any]:
        """Return display-ready data for the watchlist page."""
        as_of = _parse_date(as_of_date)
        candidates = self.build_watchlist_candidates(portfolio_id=portfolio_id, as_of_date=as_of, persist=True)
        risks = self.build_risk_filters(portfolio_id=portfolio_id, as_of_date=as_of)
        snapshot = {
            "snapshot_type": "watchlist",
            "title": "观察清单",
            "portfolio_id": portfolio_id,
            "as_of_date": as_of.isoformat(),
            "headline": "候选只代表观察和条件等待，不代表直接买入。",
            "candidates": candidates["candidates"],
            "do_not_buy_items": risks["do_not_buy_items"],
            "status_counts": candidates["status_counts"],
            "risk_rule_counts": risks["rule_counts"],
            "research_only": True,
            "live_trading": False,
        }
        self._record_snapshot(snapshot)
        return snapshot

    def journal_snapshot(
        self,
        *,
        portfolio_id: str = DEFAULT_PORTFOLIO_ID,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return display-ready command, recommendation, and validation history."""
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 200)
        with self.store.connect(read_only=True) as conn:
            commands = self._list_command_events(conn, portfolio_id, capped_limit)
            recommendations = self._list_recommendations(conn, portfolio_id, capped_limit)
            validations = self._list_external_validations(conn, portfolio_id, capped_limit)
        snapshot = {
            "snapshot_type": "journal",
            "title": "复盘记录",
            "portfolio_id": portfolio_id,
            "headline": "记录 Codex 指令、系统建议和外部验证写回。",
            "commands": commands,
            "recommendations": recommendations,
            "external_validations": validations,
            "record_count": len(commands) + len(recommendations) + len(validations),
            "research_only": True,
            "live_trading": False,
        }
        self._record_snapshot(snapshot)
        return snapshot

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

    def _thesis_for_position(self, conn: Any, position: dict[str, Any]) -> dict[str, Any] | None:
        thesis_id = position.get("thesis_id") or self._latest_thesis_id(
            conn,
            str(position["portfolio_id"]),
            str(position["ticker"]),
        )
        if not thesis_id:
            return None
        try:
            return self._fetch_thesis(conn, str(thesis_id))
        except AdvisorError:
            return None

    def _diagnose_position(
        self,
        *,
        position: dict[str, Any],
        thesis: dict[str, Any] | None,
        price: dict[str, Any],
        as_of: date,
    ) -> dict[str, Any]:
        ticker = str(position["ticker"])
        ticker_name = str(position["ticker_name"])
        next_review = _parse_optional_date(thesis.get("next_review_date")) if thesis else None
        fallback_review = (as_of + timedelta(days=1)).isoformat()
        if not thesis or thesis.get("completeness_status") != "complete":
            missing = thesis.get("missing_fields", []) if thesis else ["投资逻辑"]
            return {
                "position_id": position["position_id"],
                "ticker": ticker,
                "ticker_name": ticker_name,
                "action": "complete_thesis",
                "action_label": "补充投资逻辑",
                "priority": 2,
                "current_price": price.get("close"),
                "price": price,
                "sell_line": None,
                "trigger_price_or_condition": "补齐买入原因、退出条件、最大仓位和复盘频率后再判断。",
                "reason": f"{ticker_name} 缺少完整投资逻辑（缺少：{'、'.join(missing)}），系统不编造具体卖出价。",
                "risk": "逻辑不完整时，无法判断下跌是正常波动还是买入假设失效。",
                "next_review_date": fallback_review,
                "research_only": True,
                "live_trading": False,
            }

        stop_price = thesis.get("stop_loss_price") or position.get("stop_loss_price")
        take_profit_price = thesis.get("take_profit_price") or position.get("take_profit_price")
        sell_line = {
            "hard_stop_price": stop_price,
            "take_profit_price": take_profit_price,
            "logic_exit_conditions": thesis.get("exit_conditions") or thesis.get("invalidation_conditions"),
            "invalidation_conditions": thesis.get("invalidation_conditions"),
            "review_date": thesis.get("next_review_date"),
        }
        strategy_label = thesis.get("strategy_type_label") or thesis.get("strategy_type") or "当前策略"
        current_price = price.get("close")
        if price.get("freshness_status") in {"missing", "stale"}:
            return {
                "position_id": position["position_id"],
                "ticker": ticker,
                "ticker_name": ticker_name,
                "action": "observe",
                "action_label": "谨慎观察",
                "priority": 3,
                "current_price": current_price,
                "price": price,
                "sell_line": sell_line,
                "trigger_price_or_condition": price.get("freshness_reason"),
                "reason": f"{ticker_name} 的行情数据不新，暂不依据价格触发{strategy_label}的卖出或减仓判断。",
                "risk": price.get("freshness_reason"),
                "next_review_date": (next_review or as_of + timedelta(days=1)).isoformat(),
                "research_only": True,
                "live_trading": False,
            }
        if price.get("suspended"):
            return {
                "position_id": position["position_id"],
                "ticker": ticker,
                "ticker_name": ticker_name,
                "action": "observe",
                "action_label": "停牌观察",
                "priority": 3,
                "current_price": current_price,
                "price": price,
                "sell_line": sell_line,
                "trigger_price_or_condition": "停牌期间不依据价格触发交易动作。",
                "reason": f"{ticker_name} 最新行情标记为停牌，先观察{strategy_label}的逻辑是否仍成立。",
                "risk": "停牌期间价格不可交易，需等待复牌后重新评估。",
                "next_review_date": (next_review or as_of + timedelta(days=1)).isoformat(),
                "research_only": True,
                "live_trading": False,
            }
        if current_price is not None and stop_price is not None and float(current_price) <= float(stop_price):
            return {
                "position_id": position["position_id"],
                "ticker": ticker,
                "ticker_name": ticker_name,
                "action": "exit",
                "action_label": "触发退出",
                "priority": 1,
                "current_price": current_price,
                "price": price,
                "sell_line": sell_line,
                "trigger_price_or_condition": f"当前价 {float(current_price):.2f} <= 硬止损价 {float(stop_price):.2f}",
                "reason": f"{ticker_name} 已触及{strategy_label}预设硬止损价，属于风险条件触发，不只是简单下跌。",
                "risk": thesis.get("invalidation_conditions") or "价格跌破硬止损线，原买入假设需要判定失效。",
                "next_review_date": as_of.isoformat(),
                "research_only": True,
                "live_trading": False,
            }
        if current_price is not None and take_profit_price is not None and float(current_price) >= float(take_profit_price):
            return {
                "position_id": position["position_id"],
                "ticker": ticker,
                "ticker_name": ticker_name,
                "action": "reduce",
                "action_label": "考虑减仓",
                "priority": 2,
                "current_price": current_price,
                "price": price,
                "sell_line": sell_line,
                "trigger_price_or_condition": f"当前价 {float(current_price):.2f} >= 阶段止盈线 {float(take_profit_price):.2f}",
                "reason": f"{ticker_name} 达到{strategy_label}阶段兑现线，可考虑降低波动暴露并保留观察。",
                "risk": "达到收益目标后继续持有，需要确认板块热度和原投资逻辑仍然有效。",
                "next_review_date": (next_review or as_of + timedelta(days=1)).isoformat(),
                "research_only": True,
                "live_trading": False,
            }
        if next_review is not None and next_review <= as_of:
            return {
                "position_id": position["position_id"],
                "ticker": ticker,
                "ticker_name": ticker_name,
                "action": "observe",
                "action_label": "到期复盘",
                "priority": 3,
                "current_price": current_price,
                "price": price,
                "sell_line": sell_line,
                "trigger_price_or_condition": f"复盘日期 {next_review.isoformat()} 已到，需要检查退出条件。",
                "reason": f"{ticker_name} 尚未触发价格卖出线，但{strategy_label}已到复盘窗口，应确认逻辑是否延续。",
                "risk": thesis.get("exit_conditions") or "持有周期到期后继续持有会增加策略漂移风险。",
                "next_review_date": next_review.isoformat(),
                "research_only": True,
                "live_trading": False,
            }
        return {
            "position_id": position["position_id"],
            "ticker": ticker,
            "ticker_name": ticker_name,
            "action": "hold",
            "action_label": "继续持有",
            "priority": 4,
            "current_price": current_price,
            "price": price,
            "sell_line": sell_line,
            "trigger_price_or_condition": thesis.get("exit_conditions") or thesis.get("invalidation_conditions"),
            "reason": f"{ticker_name} 未触发{strategy_label}的硬止损、减仓线或复盘退出条件，当前建议继续持有并观察。",
            "risk": thesis.get("not_buy_conditions") or "继续持有期间需要关注板块退潮和投资逻辑失效。",
            "next_review_date": (next_review or as_of + timedelta(days=3)).isoformat(),
            "research_only": True,
            "live_trading": False,
        }

    def _record_holding_recommendation(
        self,
        conn: Any,
        portfolio_id: str,
        diagnostic: dict[str, Any],
        as_of: date,
    ) -> None:
        recommendation_id = _new_id(
            "rec",
            f"{portfolio_id}:{diagnostic['ticker']}:{as_of.isoformat()}:holding_diagnosis",
        )
        conn.execute(
            "DELETE FROM advisor_action_recommendations WHERE recommendation_id = ?",
            [recommendation_id],
        )
        conn.execute(
            """
            INSERT INTO advisor_action_recommendations (
              recommendation_id, portfolio_id, as_of_date, action_type, action_label,
              ticker, ticker_name, priority, confidence, target_price, stop_loss_price,
              take_profit_price, max_position_pct, expected_holding_days, reason,
              evidence_json, data_as_of, data_freshness, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, 'active', ?)
            """,
            [
                recommendation_id,
                portfolio_id,
                as_of,
                diagnostic["action"],
                diagnostic["action_label"],
                diagnostic["ticker"],
                diagnostic["ticker_name"],
                diagnostic["priority"],
                0.72 if diagnostic["action"] in {"hold", "observe"} else 0.66,
                diagnostic["current_price"],
                (diagnostic.get("sell_line") or {}).get("hard_stop_price"),
                (diagnostic.get("sell_line") or {}).get("take_profit_price"),
                diagnostic["reason"],
                _json_dumps(
                    {
                        "price": diagnostic.get("price"),
                        "sell_line": diagnostic.get("sell_line"),
                        "risk": diagnostic.get("risk"),
                        "trigger": diagnostic.get("trigger_price_or_condition"),
                    }
                ),
                _parse_optional_date(diagnostic.get("price", {}).get("data_date")),
                diagnostic.get("price", {}).get("freshness_status"),
                _utc_now(),
            ],
        )

    def _fetch_watchlist_item(self, conn: Any, item_id: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT item_id, portfolio_id, ticker, ticker_name, sector_id, sector_name,
                   theme, thesis_id, strategy_type, strategy_cycle, watch_status,
                   target_buy_price, trigger_price, stop_loss_price, max_position_pct,
                   not_buy_conditions, reason, evidence_json, next_review_date,
                   created_by, created_at, updated_at
            FROM watchlist_items
            WHERE item_id = ?
            """,
            [item_id],
        ).fetchone()
        if row is None:
            raise AdvisorError("观察清单记录不存在")
        return {
            "item_id": row[0],
            "portfolio_id": row[1],
            "ticker": row[2],
            "ticker_name": row[3],
            "sector_id": row[4],
            "sector_name": row[5],
            "theme": row[6],
            "thesis_id": row[7],
            "strategy_type": row[8],
            "strategy_type_label": STRATEGY_TYPE_LABELS.get(row[8], row[8]),
            "strategy_cycle": row[9],
            "watch_status": row[10],
            "target_buy_price": row[11],
            "trigger_price": row[12],
            "stop_loss_price": row[13],
            "max_position_pct": row[14],
            "not_buy_conditions": row[15],
            "reason": row[16],
            "evidence": _json_loads(row[17]),
            "next_review_date": _date_or_none(row[18]),
            "created_by": row[19],
            "created_at": _dt_or_none(row[20]),
            "updated_at": _dt_or_none(row[21]),
        }

    def _load_watchlist_sources(
        self,
        conn: Any,
        portfolio_id: str,
        as_of: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT item_id, ticker, ticker_name, sector_id, sector_name, theme,
                   thesis_id, strategy_type, strategy_cycle, watch_status,
                   target_buy_price, trigger_price, stop_loss_price, max_position_pct,
                   not_buy_conditions, reason, evidence_json, next_review_date
            FROM watchlist_items
            WHERE portfolio_id = ?
            ORDER BY updated_at DESC, ticker
            LIMIT ?
            """,
            [portfolio_id, limit],
        ).fetchall()
        sources = [
            {
                "source": "watchlist",
                "item_id": row[0],
                "ticker": row[1],
                "ticker_name": row[2],
                "sector_id": row[3],
                "sector_name": row[4],
                "theme": row[5],
                "thesis_id": row[6],
                "strategy_type": row[7],
                "strategy_cycle": row[8],
                "watch_status": row[9],
                "target_buy_price": row[10],
                "trigger_price": row[11],
                "stop_loss_price": row[12],
                "max_position_pct": row[13],
                "not_buy_conditions": row[14],
                "reason": row[15],
                "evidence": _json_loads(row[16]),
                "next_review_date": _date_or_none(row[17]),
            }
            for row in rows
        ]
        seen = {row["ticker"] for row in sources}
        if len(sources) >= limit:
            return sources
        latest_candidate_date = conn.execute(
            "SELECT MAX(as_of_date) FROM candidate_pool WHERE as_of_date <= ?",
            [as_of],
        ).fetchone()
        if latest_candidate_date is None or latest_candidate_date[0] is None:
            return sources
        pool_rows = conn.execute(
            """
            SELECT ticker, ticker_name, sector_id, sector_name, theme, stock_score,
                   risk_flag, reason, source
            FROM candidate_pool
            WHERE as_of_date = ? AND included = true
            ORDER BY stock_score DESC, ticker
            LIMIT ?
            """,
            [latest_candidate_date[0], limit],
        ).fetchall()
        for row in pool_rows:
            if row[0] in seen:
                continue
            sources.append(
                {
                    "source": row[8] or "candidate_pool",
                    "item_id": None,
                    "ticker": row[0],
                    "ticker_name": row[1],
                    "sector_id": row[2],
                    "sector_name": row[3],
                    "theme": row[4],
                    "thesis_id": None,
                    "strategy_type": None,
                    "strategy_cycle": None,
                    "watch_status": "from_candidate_pool",
                    "target_buy_price": None,
                    "trigger_price": None,
                    "stop_loss_price": None,
                    "max_position_pct": None,
                    "not_buy_conditions": None,
                    "reason": row[7],
                    "evidence": {
                        "candidate_pool_date": _date_or_none(latest_candidate_date[0]),
                        "stock_score": row[5],
                        "risk_flag": row[6],
                    },
                    "next_review_date": None,
                }
            )
            seen.add(row[0])
            if len(sources) >= limit:
                break
        return sources

    def _thesis_for_watchlist_source(
        self,
        conn: Any,
        portfolio_id: str,
        source: dict[str, Any],
    ) -> dict[str, Any] | None:
        thesis_id = source.get("thesis_id") or self._latest_thesis_id(
            conn,
            portfolio_id,
            str(source["ticker"]),
        )
        if not thesis_id:
            return None
        try:
            return self._fetch_thesis(conn, str(thesis_id))
        except AdvisorError:
            return None

    def _evaluate_watchlist_candidate(
        self,
        *,
        source: dict[str, Any],
        thesis: dict[str, Any] | None,
        price: dict[str, Any],
        as_of: date,
        held_tickers: set[str],
    ) -> dict[str, Any]:
        trigger_price = source.get("trigger_price") or source.get("target_buy_price")
        buy_condition = (
            thesis.get("entry_conditions") if thesis else None
        ) or source.get("reason") or "未设置明确买入触发条件"
        not_buy_conditions = (
            source.get("not_buy_conditions")
            or (thesis.get("not_buy_conditions") if thesis else None)
            or "未设置不买条件，需补充风险边界"
        )
        max_position_pct = source.get("max_position_pct") or (thesis.get("max_position_pct") if thesis else None)
        target_holding_days = thesis.get("target_holding_days") if thesis else None
        has_exit = bool(thesis and thesis.get("has_exit_condition"))
        complete = bool(thesis and thesis.get("completeness_status") == "complete")
        close = price.get("close")
        if source["ticker"] in held_tickers:
            status = "risk_high"
            status_label = "持仓重叠"
            reason = f"{source['ticker_name']} 已在当前持仓中，不能重复展示为新增买入候选。"
        elif not complete or not has_exit:
            status = "needs_exit_condition"
            status_label = "补充退出条件"
            reason = f"{source['ticker_name']} 还没有完整退出条件，不能进入可小仓试探。"
        elif price.get("freshness_status") in {"missing", "stale"}:
            status = "observe"
            status_label = "先观察"
            reason = f"{source['ticker_name']} 行情数据不新，暂不触发买入判断。"
        elif trigger_price is None:
            status = "observe"
            status_label = "先观察"
            reason = f"{source['ticker_name']} 尚未设置买入触发价，只保留观察。"
        elif close is not None and float(close) >= float(trigger_price) * 1.08:
            status = "missed"
            status_label = "已错过"
            reason = f"{source['ticker_name']} 当前价明显高于触发价，追高风险增加。"
        elif close is not None and float(close) >= float(trigger_price):
            status = "ready_small_probe"
            status_label = "可小仓试探"
            reason = f"{source['ticker_name']} 价格达到触发线且退出条件完整，只能作为研究候选。"
        else:
            status = "waiting_trigger"
            status_label = "等待买点"
            reason = f"{source['ticker_name']} 尚未达到触发价，继续等待条件确认。"
        return {
            "ticker": source["ticker"],
            "ticker_name": source["ticker_name"],
            "source": source["source"],
            "theme": source.get("theme"),
            "sector_id": source.get("sector_id"),
            "sector_name": source.get("sector_name"),
            "suggested_status": status,
            "suggested_status_label": status_label,
            "buy_trigger_price": trigger_price,
            "buy_trigger_condition": buy_condition,
            "not_buy_conditions": not_buy_conditions,
            "max_position_pct": max_position_pct,
            "target_holding_days": target_holding_days,
            "reason": reason,
            "price": price,
            "evidence": {
                "source_evidence": source.get("evidence") or {},
                "thesis_id": thesis.get("thesis_id") if thesis else None,
                "has_exit_condition": has_exit,
                "as_of_date": as_of.isoformat(),
            },
            "research_only": True,
            "live_trading": False,
        }

    def _record_watchlist_recommendation(
        self,
        conn: Any,
        portfolio_id: str,
        candidate: dict[str, Any],
        as_of: date,
    ) -> None:
        recommendation_id = _new_id(
            "rec",
            f"{portfolio_id}:{candidate['ticker']}:{as_of.isoformat()}:watchlist_candidate",
        )
        conn.execute(
            "DELETE FROM advisor_action_recommendations WHERE recommendation_id = ?",
            [recommendation_id],
        )
        priority = {
            "ready_small_probe": 1,
            "waiting_trigger": 2,
            "observe": 3,
            "needs_exit_condition": 3,
            "risk_high": 3,
            "missed": 4,
        }.get(candidate["suggested_status"], 5)
        conn.execute(
            """
            INSERT INTO advisor_action_recommendations (
              recommendation_id, portfolio_id, as_of_date, action_type, action_label,
              ticker, ticker_name, priority, confidence, target_price, stop_loss_price,
              take_profit_price, max_position_pct, expected_holding_days, reason,
              evidence_json, data_as_of, data_freshness, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, 'active', ?)
            """,
            [
                recommendation_id,
                portfolio_id,
                as_of,
                candidate["suggested_status"],
                candidate["suggested_status_label"],
                candidate["ticker"],
                candidate["ticker_name"],
                priority,
                0.68,
                candidate.get("buy_trigger_price"),
                candidate.get("max_position_pct"),
                candidate.get("target_holding_days"),
                candidate["reason"],
                _json_dumps(candidate.get("evidence") or {}),
                _parse_optional_date(candidate.get("price", {}).get("data_date")),
                candidate.get("price", {}).get("freshness_status"),
                _utc_now(),
            ],
        )

    def _risk_flags_for_candidate(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        flags: list[dict[str, Any]] = []
        ticker = candidate["ticker"]
        ticker_name = candidate["ticker_name"]

        def add(rule_id: str, rule_label: str, reason: str, severity: str = "medium") -> None:
            flags.append(
                {
                    "ticker": ticker,
                    "ticker_name": ticker_name,
                    "rule_id": rule_id,
                    "rule_label": rule_label,
                    "severity": severity,
                    "reason": reason,
                    "candidate_status": candidate["suggested_status"],
                    "candidate_status_label": candidate["suggested_status_label"],
                    "evidence": candidate.get("evidence") or {},
                    "scope": "current_stage_risk_only",
                    "research_only": True,
                    "live_trading": False,
                }
            )

        status = candidate.get("suggested_status")
        price = candidate.get("price") or {}
        evidence = candidate.get("evidence") or {}
        source_evidence = evidence.get("source_evidence") or {}
        if status == "missed":
            add(
                "chase_risk",
                "追高风险",
                f"{ticker_name} 当前价明显高于买入触发价，当前阶段暂不追高。",
                "high",
            )
        if status == "needs_exit_condition" or not evidence.get("has_exit_condition"):
            add(
                "missing_exit_condition",
                "没有清晰卖出线",
                f"{ticker_name} 缺少退出条件或硬止损线，当前阶段暂不买。",
                "high",
            )
        if status == "risk_high":
            add(
                "holding_overlap",
                "与当前持仓重叠",
                f"{ticker_name} 已在持仓中，当前阶段不作为新增买入候选。",
                "medium",
            )
        if price.get("suspended"):
            add(
                "suspended",
                "停牌风险",
                f"{ticker_name} 最新行情标记为停牌，当前阶段暂不买。",
                "high",
            )
        if price.get("freshness_status") in {"missing", "stale"}:
            add(
                "stale_or_missing_price",
                "行情缺失或过期",
                f"{ticker_name} 行情数据缺失或过期，当前阶段暂不买。",
                "medium",
            )
        if not candidate.get("max_position_pct"):
            add(
                "missing_position_limit",
                "仓位边界缺失",
                f"{ticker_name} 没有设置最大仓位，当前阶段不进入买入清单。",
                "medium",
            )
        if "未设置不买条件" in str(candidate.get("not_buy_conditions") or ""):
            add(
                "missing_not_buy_condition",
                "不买条件缺失",
                f"{ticker_name} 没有明确不买条件，当前阶段暂不买。",
                "medium",
            )
        if not evidence.get("thesis_id") and not source_evidence.get("candidate_pool_date"):
            add(
                "insufficient_evidence",
                "证据不足",
                f"{ticker_name} 缺少投资逻辑或来源证据，当前阶段只观察不买入。",
                "medium",
            )
        return flags

    def _today_headline(
        self,
        diagnostics: dict[str, Any],
        candidates: dict[str, Any],
        risks: dict[str, Any],
    ) -> str:
        if diagnostics["action_counts"].get("exit"):
            return "有持仓触发退出条件，先处理风险。"
        if diagnostics["action_counts"].get("complete_thesis"):
            return "先补齐持仓投资逻辑，再判断买卖。"
        if candidates["status_counts"].get("ready_small_probe"):
            return "有候选达到试探条件，但仍需遵守仓位和不买条件。"
        if risks["item_count"]:
            return "今天以风控为先，部分候选暂不适合买入。"
        return "今天以持有和观察为主，等待更清晰的触发条件。"

    def _primary_actions(
        self,
        diagnostics: dict[str, Any],
        candidates: dict[str, Any],
        risks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for item in sorted(diagnostics["diagnostics"], key=lambda row: row["priority"]):
            if item["action"] in {"exit", "reduce", "complete_thesis", "observe"}:
                actions.append(
                    {
                        "type": "holding",
                        "ticker": item["ticker"],
                        "ticker_name": item["ticker_name"],
                        "action": item["action"],
                        "label": item["action_label"],
                        "reason": item["reason"],
                        "next_review_date": item["next_review_date"],
                    }
                )
        for item in candidates["candidates"]:
            if item["suggested_status"] in {"ready_small_probe", "waiting_trigger"}:
                actions.append(
                    {
                        "type": "watchlist",
                        "ticker": item["ticker"],
                        "ticker_name": item["ticker_name"],
                        "action": item["suggested_status"],
                        "label": item["suggested_status_label"],
                        "reason": item["reason"],
                        "trigger": item["buy_trigger_price"] or item["buy_trigger_condition"],
                    }
                )
        for item in risks["do_not_buy_items"][:5]:
            actions.append(
                {
                    "type": "risk",
                    "ticker": item["ticker"],
                    "ticker_name": item["ticker_name"],
                    "action": item["rule_id"],
                    "label": item["rule_label"],
                    "reason": item["reason"],
                }
            )
        return actions[:8]

    def _snapshot_data_freshness(self, diagnostics: dict[str, Any], candidates: dict[str, Any]) -> dict[str, int]:
        statuses: Counter[str] = Counter()
        for item in diagnostics["diagnostics"]:
            statuses[str(item.get("price", {}).get("freshness_status") or "unknown")] += 1
        for item in candidates["candidates"]:
            statuses[str(item.get("price", {}).get("freshness_status") or "unknown")] += 1
        return dict(sorted(statuses.items()))

    def _record_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.store.initialize()
        snapshot_id = _new_id(
            "snap",
            f"{snapshot.get('portfolio_id')}:{snapshot.get('snapshot_type')}:{snapshot.get('as_of_date') or _utc_now().date().isoformat()}",
        )
        created_at = _utc_now()
        with self.store.connect() as conn:
            conn.execute(
                "DELETE FROM advisor_action_snapshots WHERE snapshot_id = ?",
                [snapshot_id],
            )
            conn.execute(
                """
                INSERT INTO advisor_action_snapshots (
                  snapshot_id, portfolio_id, snapshot_date, snapshot_type, headline,
                  summary, market_state, action_summary_json, holdings_summary_json,
                  watchlist_summary_json, risk_summary_json, evidence_json,
                  data_as_of, data_freshness, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    snapshot_id,
                    snapshot.get("portfolio_id"),
                    _parse_optional_date(snapshot.get("as_of_date")) or created_at.date(),
                    snapshot.get("snapshot_type"),
                    snapshot.get("headline"),
                    snapshot.get("title"),
                    None,
                    _json_dumps(snapshot.get("primary_actions") or []),
                    _json_dumps(snapshot.get("diagnostics") or snapshot.get("portfolio_summary") or {}),
                    _json_dumps(snapshot.get("candidates") or {}),
                    _json_dumps(snapshot.get("do_not_buy_items") or snapshot.get("risk_rule_counts") or {}),
                    _json_dumps({"snapshot_type": snapshot.get("snapshot_type")}),
                    created_at,
                    _json_dumps(snapshot.get("data_freshness") or {}),
                    created_at,
                ],
            )

    def _list_command_events(self, conn: Any, portfolio_id: str, limit: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT command_id, idempotency_key, command_type, source, status,
                   request_json, response_json, error_message, created_by, created_at
            FROM advisor_command_events
            WHERE portfolio_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [portfolio_id, limit],
        ).fetchall()
        return [
            {
                "command_id": row[0],
                "idempotency_key": row[1],
                "command_type": row[2],
                "source": row[3],
                "status": row[4],
                "request": _json_loads(row[5]),
                "response": _json_loads(row[6]),
                "error_message": row[7],
                "created_by": row[8],
                "created_at": _dt_or_none(row[9]),
            }
            for row in rows
        ]

    def _list_recommendations(self, conn: Any, portfolio_id: str, limit: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT recommendation_id, as_of_date, action_type, action_label,
                   ticker, ticker_name, priority, reason, evidence_json,
                   data_freshness, status, created_at
            FROM advisor_action_recommendations
            WHERE portfolio_id = ?
            ORDER BY created_at DESC, priority
            LIMIT ?
            """,
            [portfolio_id, limit],
        ).fetchall()
        return [
            {
                "recommendation_id": row[0],
                "as_of_date": _date_or_none(row[1]),
                "action_type": row[2],
                "action_label": row[3],
                "ticker": row[4],
                "ticker_name": row[5],
                "priority": row[6],
                "reason": row[7],
                "evidence": _json_loads(row[8]),
                "data_freshness": row[9],
                "status": row[10],
                "created_at": _dt_or_none(row[11]),
            }
            for row in rows
        ]

    def _list_external_validations(self, conn: Any, portfolio_id: str, limit: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT validation_id, source, source_ref, subject_type, subject_id,
                   validation_date, status, metrics_json, summary, created_by, created_at
            FROM external_validation_results
            WHERE portfolio_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [portfolio_id, limit],
        ).fetchall()
        return [
            {
                "validation_id": row[0],
                "source": row[1],
                "source_ref": row[2],
                "subject_type": row[3],
                "subject_id": row[4],
                "validation_date": _date_or_none(row[5]),
                "status": row[6],
                "metrics": _json_loads(row[7]),
                "summary": row[8],
                "created_by": row[9],
                "created_at": _dt_or_none(row[10]),
            }
            for row in rows
        ]

    def _resolve_price_row(
        self,
        conn: Any,
        *,
        ticker: str,
        as_of: date,
        stale_after_days: int,
    ) -> dict[str, Any]:
        asset = conn.execute(
            "SELECT ticker_name FROM assets WHERE ticker = ? LIMIT 1",
            [ticker],
        ).fetchone()
        row = conn.execute(
            """
            SELECT trade_date, ticker, open, high, low, close, volume, amount,
                   turnover, limit_status, suspended, source, created_at
            FROM market_daily
            WHERE ticker = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            [ticker, as_of],
        ).fetchone()
        if row is None:
            return {
                "ticker": ticker,
                "ticker_name": asset[0] if asset else ticker,
                "as_of_date": as_of.isoformat(),
                "data_date": None,
                "close": None,
                "source": None,
                "is_latest": False,
                "freshness_status": "missing",
                "freshness_reason": "缺少可用行情数据，建议页面只能降级展示。",
                "suspended": False,
                "limit_status": None,
            }
        data_date = row[0]
        if isinstance(data_date, datetime):
            data_date = data_date.date()
        gap_days = (as_of - data_date).days
        is_latest = gap_days == 0
        suspended = bool(row[10])
        if suspended:
            status = "suspended"
            reason = "最新可用行情标记为停牌，价格只用于持仓展示，不应直接触发交易建议。"
        elif is_latest:
            status = "latest"
            reason = "交易日行情数据已更新到当前分析日期。"
        elif as_of.weekday() >= 5 and gap_days <= stale_after_days:
            status = "non_trading_day_recent"
            reason = "当前分析日期为周末或非交易日，使用最近交易日数据。"
        elif gap_days <= stale_after_days:
            status = "recent_previous_trade"
            reason = "当前分析日期没有同日行情，使用最近可用交易日数据。"
        else:
            status = "stale"
            reason = f"最近行情距离分析日期已有 {gap_days} 天，数据可能过期。"
        return {
            "ticker": row[1],
            "ticker_name": asset[0] if asset else row[1],
            "as_of_date": as_of.isoformat(),
            "data_date": data_date.isoformat(),
            "open": row[2],
            "high": row[3],
            "low": row[4],
            "close": row[5],
            "volume": row[6],
            "amount": row[7],
            "turnover": row[8],
            "limit_status": row[9],
            "suspended": suspended,
            "source": row[11],
            "created_at": _dt_or_none(row[12]),
            "is_latest": is_latest,
            "days_lag": gap_days,
            "freshness_status": status,
            "freshness_reason": reason,
        }

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
