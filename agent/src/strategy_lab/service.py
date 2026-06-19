"""Auditable A-share strategy templates and strategy specs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.ashare_data.store import AShareDataStore


class StrategyLabError(RuntimeError):
    """Raised when PR-10 strategy-lab operations cannot be completed."""


@dataclass(frozen=True)
class StrategyTemplate:
    strategy_type: str
    template_name: str
    description: str
    signal_rules: tuple[str, ...]
    risk_notes: tuple[str, ...]
    default_rebalance_freq: str
    default_holding_period: int
    default_max_position: float
    default_max_sector_exposure: float
    default_max_total_exposure: float
    default_stop_loss: float
    default_take_profit: float


@dataclass(frozen=True)
class StrategyVariant:
    suffix: str
    label: str
    top_sectors: int
    top_stocks_per_sector: int
    rebalance_freq: str
    holding_period: int
    max_position: float
    max_sector_exposure: float
    max_total_exposure: float
    stop_loss: float
    take_profit: float
    confirmation_threshold: float
    risk_level: str


STRATEGY_TEMPLATES: tuple[StrategyTemplate, ...] = (
    StrategyTemplate(
        strategy_type="hot_sector_equal_weight",
        template_name="S01 热点板块等权策略",
        description=(
            "选择 sector_heat_score 排名前 N 的板块，"
            "每个板块选 stock_score 前 M 的股票，等权纳入。"
        ),
        signal_rules=(
            "sector_heat_score 排名前 N",
            "每个板块选择 stock_score 前 M",
            "候选股 included 必须为 true",
        ),
        risk_notes=("避免单板块过度集中", "板块热度退潮时降低纳入比例"),
        default_rebalance_freq="weekly",
        default_holding_period=5,
        default_max_position=0.08,
        default_max_sector_exposure=0.35,
        default_max_total_exposure=0.65,
        default_stop_loss=0.08,
        default_take_profit=0.18,
    ),
    StrategyTemplate(
        strategy_type="hot_sector_relative_strength",
        template_name="S02 热点板块 + 相对强度策略",
        description=(
            "只买热门板块中相对板块更强的股票，"
            "优先选择板块龙头和高 stock_score 标的。"
        ),
        signal_rules=("sector_heat_score 高于阈值", "个股 20 日相对强度为正", "stock_score 排名靠前"),
        risk_notes=("强势股可能短期拥挤", "需要避免追高后一致预期回落"),
        default_rebalance_freq="weekly",
        default_holding_period=10,
        default_max_position=0.07,
        default_max_sector_exposure=0.32,
        default_max_total_exposure=0.60,
        default_stop_loss=0.07,
        default_take_profit=0.20,
    ),
    StrategyTemplate(
        strategy_type="event_heat_volume_confirm",
        template_name="S03 事件热度 + 成交额确认策略",
        description="事件热度上升、板块和个股成交额确认后，次日进入观察组合。",
        signal_rules=("event_heat_score 上升", "板块成交额放大", "个股量价确认不低于阈值"),
        risk_notes=("成交额放大可能来自分歧加剧", "事件次日可能出现高开回落"),
        default_rebalance_freq="daily",
        default_holding_period=3,
        default_max_position=0.05,
        default_max_sector_exposure=0.25,
        default_max_total_exposure=0.45,
        default_stop_loss=0.06,
        default_take_profit=0.12,
    ),
    StrategyTemplate(
        strategy_type="hot_sector_pullback",
        template_name="S04 热点板块回调买入策略",
        description="在板块热度仍高时，等待趋势股回踩均线或缩量回调后纳入。",
        signal_rules=("sector_heat_score 保持高位", "个股趋势向上", "回调幅度不破风险阈值"),
        risk_notes=("回调可能转为退潮", "需要控制补跌和流动性风险"),
        default_rebalance_freq="weekly",
        default_holding_period=8,
        default_max_position=0.06,
        default_max_sector_exposure=0.30,
        default_max_total_exposure=0.55,
        default_stop_loss=0.07,
        default_take_profit=0.16,
    ),
    StrategyTemplate(
        strategy_type="leader_breakout",
        template_name="S05 龙头突破策略",
        description="在热门板块中筛选创新高且成交额放大的龙头股票。",
        signal_rules=("热门板块内 stock_score 靠前", "个股创阶段新高", "成交额确认"),
        risk_notes=("突破失败会快速回撤", "连续涨停后成交可得性较差"),
        default_rebalance_freq="daily",
        default_holding_period=5,
        default_max_position=0.05,
        default_max_sector_exposure=0.25,
        default_max_total_exposure=0.40,
        default_stop_loss=0.06,
        default_take_profit=0.15,
    ),
    StrategyTemplate(
        strategy_type="low_vol_core",
        template_name="S06 低波动核心票策略",
        description="在热门板块中选择流动性好、波动较低、趋势稳定的核心股票。",
        signal_rules=("sector_heat_score 达标", "流动性评分达标", "风险标记为 normal"),
        risk_notes=("收益弹性可能低于高波动股票", "适合作为组合稳定器而非唯一进攻策略"),
        default_rebalance_freq="weekly",
        default_holding_period=15,
        default_max_position=0.10,
        default_max_sector_exposure=0.30,
        default_max_total_exposure=0.55,
        default_stop_loss=0.06,
        default_take_profit=0.14,
    ),
    StrategyTemplate(
        strategy_type="user_watchlist_enhanced",
        template_name="S07 用户自选股增强策略",
        description=(
            "只从用户手动加入的股票中，"
            "选择同时满足热点板块、趋势确认和风险约束的标的。"
        ),
        signal_rules=("source 为 user_added", "included 为 true", "sector_heat_score 和 stock_score 达标"),
        risk_notes=("用户偏好可能带来主观集中", "需要保留系统风险过滤"),
        default_rebalance_freq="weekly",
        default_holding_period=10,
        default_max_position=0.08,
        default_max_sector_exposure=0.35,
        default_max_total_exposure=0.50,
        default_stop_loss=0.08,
        default_take_profit=0.18,
    ),
    StrategyTemplate(
        strategy_type="defensive_cash",
        template_name="S08 防守现金策略",
        description="市场环境弱或热点分数下降时降低总仓位，无强热点时保留现金。",
        signal_rules=(
            "无强热点时提高现金比例",
            "crowding_risk 高时降低仓位",
            "fading 阶段不新增仓",
        ),
        risk_notes=("防守策略可能错过快速反弹", "需要和进攻模板组合使用"),
        default_rebalance_freq="weekly",
        default_holding_period=5,
        default_max_position=0.04,
        default_max_sector_exposure=0.18,
        default_max_total_exposure=0.30,
        default_stop_loss=0.04,
        default_take_profit=0.08,
    ),
)


VARIANTS: tuple[StrategyVariant, ...] = (
    StrategyVariant("conservative", "保守参数", 2, 3, "weekly", 10, 0.05, 0.25, 0.45, 0.06, 0.12, 0.65, "low"),
    StrategyVariant("balanced", "均衡参数", 3, 5, "weekly", 5, 0.08, 0.35, 0.65, 0.08, 0.18, 0.55, "medium"),
    StrategyVariant("aggressive", "进攻参数", 5, 8, "daily", 3, 0.10, 0.45, 0.80, 0.10, 0.25, 0.45, "high"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _strategy_id(strategy_type: str, suffix: str) -> str:
    digest = hashlib.sha256(f"{strategy_type}|{suffix}".encode("utf-8")).hexdigest()[:10]
    return f"spec_{strategy_type}_{suffix}_{digest}"


def _params(template: StrategyTemplate, variant: StrategyVariant) -> dict[str, Any]:
    return {
        "template_name": template.template_name,
        "description": template.description,
        "signal_rules": list(template.signal_rules),
        "risk_notes": list(template.risk_notes),
        "top_sectors": variant.top_sectors,
        "top_stocks_per_sector": variant.top_stocks_per_sector,
        "confirmation_threshold": variant.confirmation_threshold,
        "risk_level": variant.risk_level,
        "data_inputs": ["candidate_pool", "sector_scores"],
        "execution_mode": "research_only",
    }


def _row_to_spec(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "strategy_id": row[0],
        "strategy_name": row[1],
        "market": row[2],
        "strategy_type": row[3],
        "params": json.loads(row[4] or "{}"),
        "rebalance_freq": row[5],
        "holding_period": row[6],
        "max_position": row[7],
        "max_sector_exposure": row[8],
        "max_total_exposure": row[9],
        "stop_loss": row[10],
        "take_profit": row[11],
        "enabled": bool(row[12]),
        "created_at": row[13].isoformat() if row[13] else None,
        "updated_at": row[14].isoformat() if row[14] else None,
    }


class StrategyLabService:
    """Seed and list auditable strategy specs for the A-share strategy lab."""

    def __init__(self, store: AShareDataStore | None = None) -> None:
        self.store = store or AShareDataStore()

    def list_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "strategy_type": template.strategy_type,
                "template_name": template.template_name,
                "description": template.description,
                "signal_rules": list(template.signal_rules),
                "risk_notes": list(template.risk_notes),
                "default_rebalance_freq": template.default_rebalance_freq,
                "default_holding_period": template.default_holding_period,
                "default_max_position": template.default_max_position,
                "default_max_sector_exposure": template.default_max_sector_exposure,
                "default_max_total_exposure": template.default_max_total_exposure,
                "default_stop_loss": template.default_stop_loss,
                "default_take_profit": template.default_take_profit,
            }
            for template in STRATEGY_TEMPLATES
        ]

    def seed_strategy_specs(self, *, replace: bool = False) -> dict[str, Any]:
        self.store.initialize()
        now = _utc_now()
        written = 0
        skipped = 0
        with self.store.connect() as conn:
            for template in STRATEGY_TEMPLATES:
                for variant in VARIANTS:
                    strategy_id = _strategy_id(template.strategy_type, variant.suffix)
                    existing = conn.execute(
                        "SELECT strategy_id FROM strategy_specs WHERE strategy_id = ?",
                        [strategy_id],
                    ).fetchone()
                    if existing and not replace:
                        skipped += 1
                        continue
                    if existing:
                        conn.execute("DELETE FROM strategy_specs WHERE strategy_id = ?", [strategy_id])
                    conn.execute(
                        """
                        INSERT INTO strategy_specs (
                          strategy_id, strategy_name, market, strategy_type, params_json,
                          rebalance_freq, holding_period, max_position, max_sector_exposure,
                          max_total_exposure, stop_loss, take_profit, enabled, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            strategy_id,
                            f"{template.template_name} - {variant.label}",
                            "CN_A",
                            template.strategy_type,
                            json.dumps(_params(template, variant), ensure_ascii=False, sort_keys=True),
                            variant.rebalance_freq,
                            variant.holding_period,
                            variant.max_position,
                            variant.max_sector_exposure,
                            variant.max_total_exposure,
                            variant.stop_loss,
                            variant.take_profit,
                            True,
                            now,
                            now,
                        ],
                    )
                    written += 1

        return {
            "status": "ok",
            "template_count": len(STRATEGY_TEMPLATES),
            "variant_count": len(VARIANTS),
            "strategy_specs_written": written,
            "strategy_specs_skipped": skipped,
            "total_expected_specs": len(STRATEGY_TEMPLATES) * len(VARIANTS),
        }

    def list_strategy_specs(
        self,
        *,
        strategy_type: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.store.initialize()
        capped_limit = min(max(int(limit), 1), 500)
        filters: list[str] = []
        params: list[Any] = []
        if strategy_type:
            filters.append("strategy_type = ?")
            params.append(strategy_type.strip())
        if enabled is not None:
            filters.append("enabled = ?")
            params.append(bool(enabled))
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(capped_limit)
        with self.store.connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT strategy_id, strategy_name, market, strategy_type, params_json,
                       rebalance_freq, holding_period, max_position, max_sector_exposure,
                       max_total_exposure, stop_loss, take_profit, enabled, created_at, updated_at
                FROM strategy_specs
                {where}
                ORDER BY strategy_type, strategy_name
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_spec(row) for row in rows]

    def create_strategy_spec(
        self,
        *,
        strategy_type: str,
        strategy_name: str,
        params: dict[str, Any],
        rebalance_freq: str,
        holding_period: int,
        max_position: float,
        max_sector_exposure: float,
        max_total_exposure: float,
        stop_loss: float,
        take_profit: float,
        enabled: bool = True,
    ) -> dict[str, Any]:
        self.store.initialize()
        if strategy_type not in {template.strategy_type for template in STRATEGY_TEMPLATES}:
            raise StrategyLabError(f"不支持的策略模板类型: {strategy_type}")
        holding = min(max(int(holding_period), 1), 60)
        risk_values = {
            "max_position": max_position,
            "max_sector_exposure": max_sector_exposure,
            "max_total_exposure": max_total_exposure,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        for key, value in risk_values.items():
            if not 0 <= float(value) <= 1:
                raise StrategyLabError(f"{key} 必须在 0 到 1 之间")
        strategy_id = _strategy_id(strategy_type, hashlib.sha256(strategy_name.encode("utf-8")).hexdigest()[:12])
        now = _utc_now()
        payload = dict(params)
        payload.setdefault("execution_mode", "research_only")
        payload.setdefault("data_inputs", ["candidate_pool", "sector_scores"])
        with self.store.connect() as conn:
            conn.execute("DELETE FROM strategy_specs WHERE strategy_id = ?", [strategy_id])
            conn.execute(
                """
                INSERT INTO strategy_specs (
                  strategy_id, strategy_name, market, strategy_type, params_json,
                  rebalance_freq, holding_period, max_position, max_sector_exposure,
                  max_total_exposure, stop_loss, take_profit, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    strategy_id,
                    strategy_name.strip(),
                    "CN_A",
                    strategy_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    rebalance_freq.strip(),
                    holding,
                    float(max_position),
                    float(max_sector_exposure),
                    float(max_total_exposure),
                    float(stop_loss),
                    float(take_profit),
                    bool(enabled),
                    now,
                    now,
                ],
            )
            row = conn.execute(
                """
                SELECT strategy_id, strategy_name, market, strategy_type, params_json,
                       rebalance_freq, holding_period, max_position, max_sector_exposure,
                       max_total_exposure, stop_loss, take_profit, enabled, created_at, updated_at
                FROM strategy_specs
                WHERE strategy_id = ?
                """,
                [strategy_id],
            ).fetchone()
        return _row_to_spec(row)
