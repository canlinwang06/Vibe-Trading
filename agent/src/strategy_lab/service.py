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
    strategy_family: str
    idea_category: str
    signal_source: str
    market_regimes: tuple[str, ...]
    cycle_stages: tuple[str, ...]
    description: str
    signal_rules: tuple[str, ...]
    risk_notes: tuple[str, ...]
    idea_prompt: str
    generator_enabled: bool
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
        strategy_family="板块轮动",
        idea_category="热点板块等权",
        signal_source="sector_heat",
        market_regimes=("neutral", "attack"),
        cycle_stages=("warming", "confirmed"),
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
        idea_prompt="当热点板块刚升温或确认时，生成一组分散的主题轮动回测假设。",
        generator_enabled=True,
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
        strategy_family="趋势确认",
        idea_category="热点板块相对强度",
        signal_source="sector_heat+relative_strength",
        market_regimes=("neutral", "attack"),
        cycle_stages=("confirmed", "accelerating"),
        description=(
            "只买热门板块中相对板块更强的股票，"
            "优先选择板块龙头和高 stock_score 标的。"
        ),
        signal_rules=("sector_heat_score 高于阈值", "个股 20 日相对强度为正", "stock_score 排名靠前"),
        risk_notes=("强势股可能短期拥挤", "需要避免追高后一致预期回落"),
        idea_prompt="当板块热度和个股强度同时确认时，生成强势股跟随回测假设。",
        generator_enabled=True,
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
        strategy_family="事件确认",
        idea_category="事件确认",
        signal_source="event_heat+volume_confirm",
        market_regimes=("neutral", "attack"),
        cycle_stages=("warming", "confirmed", "accelerating"),
        description="事件热度上升、板块和个股成交额确认后，次日进入观察组合。",
        signal_rules=("event_heat_score 上升", "板块成交额放大", "个股量价确认不低于阈值"),
        risk_notes=("成交额放大可能来自分歧加剧", "事件次日可能出现高开回落"),
        idea_prompt="当事件可信度较高且市场成交确认时，生成短周期事件驱动回测假设。",
        generator_enabled=True,
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
        strategy_family="回调交易",
        idea_category="回调买入",
        signal_source="sector_heat+pullback",
        market_regimes=("neutral", "attack"),
        cycle_stages=("confirmed", "accelerating"),
        description="在板块热度仍高时，等待趋势股回踩均线或缩量回调后纳入。",
        signal_rules=("sector_heat_score 保持高位", "个股趋势向上", "回调幅度不破风险阈值"),
        risk_notes=("回调可能转为退潮", "需要控制补跌和流动性风险"),
        idea_prompt="当热点仍在但短线涨幅较大时，生成等待回踩确认的回测假设。",
        generator_enabled=True,
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
        strategy_family="龙头进攻",
        idea_category="龙头突破",
        signal_source="leader_strength+breakout",
        market_regimes=("attack",),
        cycle_stages=("accelerating",),
        description="在热门板块中筛选创新高且成交额放大的龙头股票。",
        signal_rules=("热门板块内 stock_score 靠前", "个股创阶段新高", "成交额确认"),
        risk_notes=("突破失败会快速回撤", "连续涨停后成交可得性较差"),
        idea_prompt="当热点进入加速期时，生成龙头突破和短周期进攻回测假设。",
        generator_enabled=True,
        default_rebalance_freq="daily",
        default_holding_period=5,
        default_max_position=0.05,
        default_max_sector_exposure=0.25,
        default_max_total_exposure=0.40,
        default_stop_loss=0.06,
        default_take_profit=0.15,
    ),
    StrategyTemplate(
        strategy_type="catch_up_spread",
        template_name="S06 补涨扩散策略",
        strategy_family="扩散补涨",
        idea_category="补涨扩散",
        signal_source="sector_heat+laggard_score",
        market_regimes=("neutral", "attack"),
        cycle_stages=("confirmed", "accelerating"),
        description="在热点板块龙头已上涨后，寻找同板块内评分提升但涨幅相对滞后的股票。",
        signal_rules=("热点板块仍保持高分", "股票 stock_score 上升", "短期涨幅低于板块龙头"),
        risk_notes=("补涨可能变成跟跌", "需要避免低流动性后排股票"),
        idea_prompt="当热点从龙头向板块内部扩散时，生成补涨观察和分散回测假设。",
        generator_enabled=True,
        default_rebalance_freq="weekly",
        default_holding_period=5,
        default_max_position=0.06,
        default_max_sector_exposure=0.32,
        default_max_total_exposure=0.55,
        default_stop_loss=0.07,
        default_take_profit=0.16,
    ),
    StrategyTemplate(
        strategy_type="low_vol_core",
        template_name="S07 防守低波核心票策略",
        strategy_family="防守核心",
        idea_category="防守低波",
        signal_source="sector_heat+liquidity_risk",
        market_regimes=("defense", "neutral"),
        cycle_stages=("warming", "confirmed"),
        description="在热门板块中选择流动性好、波动较低、趋势稳定的核心股票。",
        signal_rules=("sector_heat_score 达标", "流动性评分达标", "风险标记为 normal"),
        risk_notes=("收益弹性可能低于高波动股票", "适合作为组合稳定器而非唯一进攻策略"),
        idea_prompt="当用户偏保守或市场信心一般时，生成低波动核心票回测假设。",
        generator_enabled=True,
        default_rebalance_freq="weekly",
        default_holding_period=15,
        default_max_position=0.10,
        default_max_sector_exposure=0.30,
        default_max_total_exposure=0.55,
        default_stop_loss=0.06,
        default_take_profit=0.14,
    ),
    StrategyTemplate(
        strategy_type="overheated_avoidance",
        template_name="S08 过热规避策略",
        strategy_family="风险控制",
        idea_category="过热规避",
        signal_source="crowding_risk+cycle_stage",
        market_regimes=("defense", "low_confidence"),
        cycle_stages=("climax", "fading"),
        description="板块拥挤风险上升或热度退潮时降低总仓位，避免追高进入过热主题。",
        signal_rules=(
            "crowding_risk 高时降低纳入比例",
            "crowding_risk 高时降低仓位",
            "fading 阶段不新增仓",
        ),
        risk_notes=("防守策略可能错过快速反弹", "需要和进攻模板组合使用"),
        idea_prompt="当热点过热或退潮时，生成降低暴露、只保留观察的防守回测假设。",
        generator_enabled=True,
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
        "strategy_family": template.strategy_family,
        "idea_category": template.idea_category,
        "signal_source": template.signal_source,
        "market_regimes": list(template.market_regimes),
        "cycle_stages": list(template.cycle_stages),
        "description": template.description,
        "signal_rules": list(template.signal_rules),
        "risk_notes": list(template.risk_notes),
        "idea_prompt": template.idea_prompt,
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
                "strategy_family": template.strategy_family,
                "idea_category": template.idea_category,
                "signal_source": template.signal_source,
                "market_regimes": list(template.market_regimes),
                "cycle_stages": list(template.cycle_stages),
                "description": template.description,
                "signal_rules": list(template.signal_rules),
                "risk_notes": list(template.risk_notes),
                "idea_prompt": template.idea_prompt,
                "generator_enabled": template.generator_enabled,
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

    def list_template_taxonomy(self) -> dict[str, Any]:
        templates = self.list_templates()
        families: dict[str, list[str]] = {}
        categories: dict[str, str] = {}
        signal_sources: dict[str, list[str]] = {}
        for template in templates:
            families.setdefault(template["strategy_family"], []).append(template["strategy_type"])
            categories[template["strategy_type"]] = template["idea_category"]
            signal_sources.setdefault(template["signal_source"], []).append(template["strategy_type"])
        return {
            "template_count": len(templates),
            "families": families,
            "categories": categories,
            "signal_sources": signal_sources,
            "generator_enabled_types": [
                template["strategy_type"] for template in templates if template["generator_enabled"]
            ],
            "research_only": True,
            "live_trading": False,
        }

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
        template = next(item for item in STRATEGY_TEMPLATES if item.strategy_type == strategy_type)
        payload.setdefault("strategy_family", template.strategy_family)
        payload.setdefault("idea_category", template.idea_category)
        payload.setdefault("signal_source", template.signal_source)
        payload.setdefault("market_regimes", list(template.market_regimes))
        payload.setdefault("cycle_stages", list(template.cycle_stages))
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
