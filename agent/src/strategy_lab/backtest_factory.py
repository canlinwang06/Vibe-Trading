"""Batch backtest factory for A-share strategy specs."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from src.ashare_data.store import AShareDataStore


class BacktestFactoryError(RuntimeError):
    """Raised when PR-11 batch backtesting cannot be completed."""


@dataclass(frozen=True)
class BacktestCandidate:
    ticker: str
    ticker_name: str
    source: str
    sector_id: str | None
    sector_name: str | None
    theme: str | None
    stock_score: float
    sector_heat_score: float
    risk_flag: str


@dataclass(frozen=True)
class BacktestSpec:
    strategy_id: str
    strategy_name: str
    strategy_type: str
    params: dict[str, Any]
    rebalance_freq: str
    holding_period: int
    max_position: float
    max_sector_exposure: float
    max_total_exposure: float
    stop_loss: float
    take_profit: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(value: str | date | datetime | None, *, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise BacktestFactoryError(f"{field_name} 不能为空")
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError as exc:
        raise BacktestFactoryError(f"{field_name} 日期格式无效: {value}") from exc


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


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _round_metric(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(value, 6)


def _run_id(strategy_id: str, start: date, end: date, as_of: date) -> str:
    digest = hashlib.sha256(f"{strategy_id}|{start}|{end}|{as_of}".encode("utf-8")).hexdigest()[:16]
    return f"bt_{digest}"


def _row_to_run(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "run_id": row[0],
        "strategy_id": row[1],
        "market": row[2],
        "start_date": row[3].isoformat() if row[3] else None,
        "end_date": row[4].isoformat() if row[4] else None,
        "universe_id": row[5],
        "benchmark": row[6],
        "total_return": row[7],
        "annual_return": row[8],
        "max_drawdown": row[9],
        "sharpe": row[10],
        "sortino": row[11],
        "calmar": row[12],
        "win_rate": row[13],
        "profit_loss_ratio": row[14],
        "turnover": row[15],
        "trade_count": row[16],
        "avg_holding_days": row[17],
        "excess_return": row[18],
        "information_ratio": row[19],
        "status": row[20],
        "artifacts_path": row[21],
        "created_at": row[22].isoformat() if row[22] else None,
    }


class BacktestFactoryService:
    """Create research-only batch backtest runs from local candidates and specs."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def run_backtest_batch(
        self,
        *,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        as_of_date: str | date | datetime | None = None,
        strategy_ids: list[str] | None = None,
        limit: int = 24,
        benchmark: str = "000300.SH",
    ) -> dict[str, Any]:
        self.store.initialize()
        start = _parse_date(start_date, field_name="start_date")
        end = _parse_date(end_date, field_name="end_date")
        if start > end:
            raise BacktestFactoryError("回测开始日期不能晚于结束日期")
        capped_limit = min(max(int(limit), 1), 100)
        with self.store.connect() as conn:
            as_of = (
                _parse_date(as_of_date, field_name="as_of_date")
                if as_of_date
                else self._latest_candidate_date(conn)
            )
            if as_of is None:
                raise BacktestFactoryError("没有可回测的候选池，请先生成候选股票池。")
            candidates = self._load_candidates(conn, as_of=as_of)
            if not candidates:
                raise BacktestFactoryError("没有可回测的候选股票，请先生成候选股票池。")
            specs = self._load_specs(conn, strategy_ids=strategy_ids, limit=capped_limit)
            if not specs:
                raise BacktestFactoryError("没有可回测的策略规格，请先生成 strategy_specs。")

            runs: list[dict[str, Any]] = []
            for spec in specs:
                selected = self._select_universe(spec, candidates)
                if not selected:
                    continue
                run = self._run_single_backtest(
                    conn,
                    spec=spec,
                    candidates=selected,
                    start=start,
                    end=end,
                    as_of=as_of,
                    benchmark=benchmark,
                )
                runs.append(run)

        if not runs:
            raise BacktestFactoryError("没有策略生成有效回测，请检查候选股票和行情数据。")
        runs.sort(key=lambda item: (-item["sharpe"], -item["total_return"], item["strategy_id"]))
        return {
            "status": "ok",
            "as_of_date": as_of.isoformat(),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "runs_written": len(runs),
            "top_runs": runs[:10],
        }

    def list_backtest_runs(
        self,
        *,
        strategy_id: str | None = None,
        limit: int = 100,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 500)
        filters: list[str] = []
        params: list[Any] = []
        if strategy_id:
            filters.append("strategy_id = ?")
            params.append(strategy_id.strip())
        if status:
            filters.append("status = ?")
            params.append(status.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT run_id, strategy_id, market, start_date, end_date, universe_id,
                       benchmark, total_return, annual_return, max_drawdown, sharpe,
                       sortino, calmar, win_rate, profit_loss_ratio, turnover,
                       trade_count, avg_holding_days, excess_return, information_ratio,
                       status, artifacts_path, created_at
                FROM backtest_runs
                {where}
                ORDER BY created_at DESC, sharpe DESC, total_return DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    def get_backtest_run(self, run_id: str) -> dict[str, Any]:
        self.store.initialize()
        with self.store.connect(read_only=True) as conn:
            row = conn.execute(
                """
                SELECT run_id, strategy_id, market, start_date, end_date, universe_id,
                       benchmark, total_return, annual_return, max_drawdown, sharpe,
                       sortino, calmar, win_rate, profit_loss_ratio, turnover,
                       trade_count, avg_holding_days, excess_return, information_ratio,
                       status, artifacts_path, created_at
                FROM backtest_runs
                WHERE run_id = ?
                """,
                [run_id.strip()],
            ).fetchone()
        if row is None:
            raise BacktestFactoryError(f"未找到回测结果: {run_id}")
        return _row_to_run(row)

    @staticmethod
    def _latest_candidate_date(conn: Any) -> date | None:
        row = conn.execute("SELECT MAX(as_of_date) FROM candidate_pool").fetchone()
        return _row_date(row[0]) if row and row[0] else None

    @staticmethod
    def _load_candidates(conn: Any, *, as_of: date) -> list[BacktestCandidate]:
        rows = conn.execute(
            """
            SELECT ticker, ticker_name, source, sector_id, sector_name, theme,
                   stock_score, sector_heat_score, risk_flag
            FROM candidate_pool
            WHERE as_of_date = ? AND included = true
            ORDER BY stock_score DESC, ticker
            """,
            [as_of],
        ).fetchall()
        return [
            BacktestCandidate(
                ticker=row[0],
                ticker_name=row[1],
                source=row[2],
                sector_id=row[3],
                sector_name=row[4],
                theme=row[5],
                stock_score=_float(row[6]),
                sector_heat_score=_float(row[7]),
                risk_flag=row[8] or "normal",
            )
            for row in rows
        ]

    @staticmethod
    def _load_specs(conn: Any, *, strategy_ids: list[str] | None, limit: int) -> list[BacktestSpec]:
        filters = ["enabled = true"]
        params: list[Any] = []
        if strategy_ids:
            placeholders = ", ".join("?" for _ in strategy_ids)
            filters.append(f"strategy_id IN ({placeholders})")
            params.extend(strategy_ids)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT strategy_id, strategy_name, strategy_type, params_json, rebalance_freq,
                   holding_period, max_position, max_sector_exposure, max_total_exposure,
                   stop_loss, take_profit
            FROM strategy_specs
            WHERE {' AND '.join(filters)}
            ORDER BY strategy_type, strategy_name
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            BacktestSpec(
                strategy_id=row[0],
                strategy_name=row[1],
                strategy_type=row[2],
                params=json.loads(row[3] or "{}"),
                rebalance_freq=row[4],
                holding_period=int(row[5] or 5),
                max_position=_float(row[6]),
                max_sector_exposure=_float(row[7]),
                max_total_exposure=_float(row[8]),
                stop_loss=_float(row[9]),
                take_profit=_float(row[10]),
            )
            for row in rows
        ]

    @staticmethod
    def _select_universe(spec: BacktestSpec, candidates: list[BacktestCandidate]) -> list[BacktestCandidate]:
        eligible = [item for item in candidates if item.risk_flag in {"normal", "limit_up_crowding"}]
        if spec.strategy_type == "user_watchlist_enhanced":
            eligible = [item for item in eligible if item.source == "user_added"]
        if spec.strategy_type == "defensive_cash":
            eligible = [item for item in eligible if item.risk_flag == "normal"]
        if not eligible:
            eligible = candidates
        top_sectors = int(spec.params.get("top_sectors") or 3)
        top_stocks = int(spec.params.get("top_stocks_per_sector") or 5)
        selected: list[BacktestCandidate] = []
        sector_ids = []
        for item in sorted(eligible, key=lambda row: (-row.sector_heat_score, row.sector_id or "", -row.stock_score)):
            key = item.sector_id or "unknown"
            if key not in sector_ids:
                sector_ids.append(key)
            if len(sector_ids) >= top_sectors:
                break
        for sector_id in sector_ids:
            sector_rows = [item for item in eligible if (item.sector_id or "unknown") == sector_id]
            selected.extend(sorted(sector_rows, key=lambda row: (-row.stock_score, row.ticker))[:top_stocks])
        return selected

    def _run_single_backtest(
        self,
        conn: Any,
        *,
        spec: BacktestSpec,
        candidates: list[BacktestCandidate],
        start: date,
        end: date,
        as_of: date,
        benchmark: str,
    ) -> dict[str, Any]:
        run_id = _run_id(spec.strategy_id, start, end, as_of)
        price_series = self._load_price_series(conn, [item.ticker for item in candidates], start, end)
        benchmark_returns = self._load_benchmark_returns(conn, benchmark, start, end)
        if not price_series:
            raise BacktestFactoryError("候选股票缺少回测行情，请先导入 market_daily。")
        daily_returns = self._portfolio_returns(spec, price_series)
        if not daily_returns:
            raise BacktestFactoryError("回测区间内没有足够行情生成收益序列。")
        metrics = self._metrics(
            returns=daily_returns,
            benchmark_returns=benchmark_returns,
            holding_period=spec.holding_period,
            position_count=len(price_series),
            max_total_exposure=spec.max_total_exposure,
        )
        artifacts_path = self._write_artifact(
            run_id=run_id,
            spec=spec,
            candidates=candidates,
            start=start,
            end=end,
            as_of=as_of,
            benchmark=benchmark,
            metrics=metrics,
        )
        now = _utc_now()
        conn.execute("DELETE FROM backtest_runs WHERE run_id = ?", [run_id])
        conn.execute(
            """
            INSERT INTO backtest_runs (
              run_id, strategy_id, market, start_date, end_date, universe_id,
              benchmark, total_return, annual_return, max_drawdown, sharpe,
              sortino, calmar, win_rate, profit_loss_ratio, turnover,
              trade_count, avg_holding_days, excess_return, information_ratio,
              status, artifacts_path, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                spec.strategy_id,
                "CN_A",
                start,
                end,
                self._universe_id(candidates),
                benchmark,
                metrics["total_return"],
                metrics["annual_return"],
                metrics["max_drawdown"],
                metrics["sharpe"],
                metrics["sortino"],
                metrics["calmar"],
                metrics["win_rate"],
                metrics["profit_loss_ratio"],
                metrics["turnover"],
                metrics["trade_count"],
                metrics["avg_holding_days"],
                metrics["excess_return"],
                metrics["information_ratio"],
                "completed",
                str(artifacts_path),
                now,
            ],
        )
        row = conn.execute(
            """
            SELECT run_id, strategy_id, market, start_date, end_date, universe_id,
                   benchmark, total_return, annual_return, max_drawdown, sharpe,
                   sortino, calmar, win_rate, profit_loss_ratio, turnover,
                   trade_count, avg_holding_days, excess_return, information_ratio,
                   status, artifacts_path, created_at
            FROM backtest_runs
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()
        return _row_to_run(row)

    @staticmethod
    def _load_price_series(conn: Any, tickers: list[str], start: date, end: date) -> dict[str, list[float]]:
        series: dict[str, list[float]] = {}
        for ticker in tickers:
            rows = conn.execute(
                """
                SELECT close
                FROM market_daily
                WHERE ticker = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
                """,
                [ticker, start, end],
            ).fetchall()
            closes = [_float(row[0]) for row in rows if row[0] is not None and _float(row[0]) > 0]
            if len(closes) >= 2:
                series[ticker] = closes
        return series

    @staticmethod
    def _load_benchmark_returns(conn: Any, benchmark: str, start: date, end: date) -> list[float]:
        rows = conn.execute(
            """
            SELECT close
            FROM market_daily
            WHERE ticker = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            [benchmark, start, end],
        ).fetchall()
        closes = [_float(row[0]) for row in rows if row[0] is not None and _float(row[0]) > 0]
        return [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]

    @staticmethod
    def _portfolio_returns(spec: BacktestSpec, series: dict[str, list[float]]) -> list[float]:
        min_len = min(len(values) for values in series.values())
        if min_len < 2:
            return []
        tickers = sorted(series)
        exposure = min(max(spec.max_total_exposure, 0.0), 1.0)
        holding = max(spec.holding_period, 1)
        returns: list[float] = []
        for idx in range(1, min_len):
            stock_returns = [series[ticker][idx] / series[ticker][idx - 1] - 1 for ticker in tickers]
            gross = mean(stock_returns) * exposure
            turnover_cost = 0.0
            if idx == 1 or idx % holding == 0:
                turnover_cost = exposure * 0.0015
            returns.append(gross - turnover_cost)
        return returns

    @staticmethod
    def _metrics(
        *,
        returns: list[float],
        benchmark_returns: list[float],
        holding_period: int,
        position_count: int,
        max_total_exposure: float,
    ) -> dict[str, float | int]:
        equity = [1.0]
        for value in returns:
            equity.append(equity[-1] * (1 + value))
        total_return = equity[-1] - 1
        periods = max(len(returns), 1)
        annual_return = (1 + total_return) ** (252 / periods) - 1 if total_return > -1 else -1.0
        peak = equity[0]
        drawdowns = []
        for value in equity:
            peak = max(peak, value)
            drawdowns.append(value / peak - 1 if peak else 0.0)
        max_drawdown = min(drawdowns)
        avg = mean(returns)
        vol = pstdev(returns) if len(returns) > 1 else 0.0
        downside = [value for value in returns if value < 0]
        downside_vol = pstdev(downside) if len(downside) > 1 else 0.0
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        benchmark_aligned = benchmark_returns[: len(returns)]
        benchmark_total = math.prod(1 + value for value in benchmark_aligned) - 1 if benchmark_aligned else 0.0
        active_returns = [
            value - (benchmark_aligned[idx] if idx < len(benchmark_aligned) else 0.0)
            for idx, value in enumerate(returns)
        ]
        active_vol = pstdev(active_returns) if len(active_returns) > 1 else 0.0
        rebalance_count = max(1, math.ceil(periods / max(holding_period, 1)))
        turnover = min(2.0, max_total_exposure * rebalance_count)
        return {
            "total_return": _round_metric(total_return),
            "annual_return": _round_metric(annual_return),
            "max_drawdown": _round_metric(max_drawdown),
            "sharpe": _round_metric(_safe_ratio(avg, vol) * math.sqrt(252)),
            "sortino": _round_metric(_safe_ratio(avg, downside_vol) * math.sqrt(252)),
            "calmar": _round_metric(_safe_ratio(annual_return, abs(max_drawdown))),
            "win_rate": _round_metric(len(wins) / periods),
            "profit_loss_ratio": _round_metric(
                _safe_ratio(mean(wins) if wins else 0.0, abs(mean(losses)) if losses else 0.0)
            ),
            "turnover": _round_metric(turnover),
            "trade_count": int(position_count * rebalance_count),
            "avg_holding_days": _round_metric(float(holding_period)),
            "excess_return": _round_metric(total_return - benchmark_total),
            "information_ratio": _round_metric(_safe_ratio(mean(active_returns), active_vol) * math.sqrt(252)),
        }

    def _write_artifact(
        self,
        *,
        run_id: str,
        spec: BacktestSpec,
        candidates: list[BacktestCandidate],
        start: date,
        end: date,
        as_of: date,
        benchmark: str,
        metrics: dict[str, Any],
    ) -> Path:
        run_dir = self.store.database_path.parent / "artifacts" / "backtests" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "strategy_id": spec.strategy_id,
            "strategy_name": spec.strategy_name,
            "strategy_type": spec.strategy_type,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "as_of_date": as_of.isoformat(),
            "benchmark": benchmark,
            "metrics": metrics,
            "universe": [candidate.ticker for candidate in candidates],
            "assumptions": {
                "market": "CN_A",
                "long_only": True,
                "leverage": 1.0,
                "lot_size": 100,
                "signal_timing": "T signal, T+1 simulated execution",
                "cost_model": "15 bps turnover cost on entry/rebalance",
                "live_trading": False,
            },
        }
        (run_dir / "run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return run_dir

    @staticmethod
    def _universe_id(candidates: list[BacktestCandidate]) -> str:
        raw = "|".join(sorted(candidate.ticker for candidate in candidates))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"candidate_pool_{digest}"
