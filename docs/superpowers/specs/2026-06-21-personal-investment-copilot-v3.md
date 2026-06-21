# Vibe-Trading Personal Investment Copilot V3

Date: 2026-06-21
Status: Product baseline for next-stage refactor
Related docs:

- `docs/superpowers/specs/2026-06-20-two-module-event-research-design.md`
- `docs/superpowers/specs/2026-06-21-codex-command-presentation-layer-design.md`
- `docs/pr-plans/2026-06-21-personal-investment-copilot-v3-pr-plan.md`

## 1. Product Positioning

Vibe-Trading should evolve from an A-share event and strategy workbench into a personal AI investment copilot.

The product is not an automatic trading system. It is a local research, decision, planning, alerting, and review cockpit. Codex remains the main orchestration layer. The Web UI is primarily a structured visualization and evidence presentation layer.

## 2. Core Decision

Do not rebuild the whole system.

Keep the existing data collection, source registry, event ingestion, market snapshots, sector records, strategy cards, JoinQuant task center, and local storage. Add a new investment-copilot core beside the current collection system.

The upgrade strategy is:

- Data layer: reuse and standardize existing capabilities.
- Analysis layer: add market regime, hotspot lifecycle, stock scoring, and evidence synthesis.
- Portfolio layer: add holdings, theses, risk, and decision tracking.
- Alert layer: add opportunity and risk reminders.
- Review layer: add trade plans, journals, simulation records, and daily reports.
- Backtest layer: keep JoinQuant as the main execution environment.
- Deep learning and automatic live trading: defer.

## 3. Target User

The primary user is an individual A-share investor who wants Codex to help organize research and decision discipline.

User characteristics:

- Uses Codex Pro as the main interaction entry.
- Wants fewer manual UI operations and more structured conclusions.
- Needs local historical memory for events, sectors, stocks, strategies, and decisions.
- Wants to avoid impulsive trading and overfitting backtests.
- Wants to start with roughly RMB 100,000 simulation or small-capital workflow.

## 4. Investment Workflow

The target workflow is:

1. The system collects daily market, event, sector, stock, policy, announcement, and media data.
2. Codex reads the collected data and asks the system for market state, hotspot lifecycle, and candidate opportunities.
3. The system generates observation pools and candidate strategies, not direct buy instructions.
4. The user reviews candidates with Codex.
5. Codex sends selected strategies to JoinQuant for backtest or simulation, using user-authorized browser/session flow.
6. Codex reads JoinQuant results and writes them back into the local system.
7. The system tracks strategy lifecycle, alerts, positions, decision journals, and follow-up reviews.

## 5. Existing Capabilities To Keep

Keep and continue improving:

- Hotspot and event collection.
- Raw document ingestion and source traceability.
- Official, exchange, market, media, and social source tiers.
- A-share stock and sector snapshots.
- Candidate stock and strategy-card generation.
- JoinQuant task creation and result import.
- Strategy lifecycle dashboard.
- Local API-first architecture for Codex orchestration.

These are useful assets. Rewriting them would slow down the product and create unnecessary migration risk.

## 6. New Core Modules

### 6.1 Market Memory

Purpose: make the system remember what happened, when it happened, and how the market reacted.

Inputs:

- Events, raw documents, sector snapshots, stock snapshots, anomalies, strategy cards, JoinQuant results, alerts, and journals.

Outputs:

- Time-series memory by day, week, month, quarter, year, topic, sector, stock, and strategy.
- Event impact windows such as T+1, T+3, T+5, T+10, T+20, and T+60.
- Reusable evidence records for future strategy generation.

Business rules:

- Store event publish time, crawl time, knowable time, and tradable time separately.
- Keep source URL or local document reference for every record.
- Distinguish official facts, mainstream media reports, research views, and social leads.
- Never promote unverified social leads into strategy evidence without source checks.

Priority: P0.

### 6.2 Market Regime Engine

Purpose: answer whether the current market is suitable for trading.

Inputs:

- Index trend, sector breadth, turnover, volatility, limit-up/limit-down structure, hotspot dispersion, and external risk events.

Outputs:

- Daily market state, such as strong trend, weak trend, range-bound, risk-off, or unclear.
- Short-term trading stance.
- Medium-term position stance.
- Suggested total exposure band.

Business rules:

- Market regime is a risk filter, not a buy signal.
- If data is missing or market is closed, show a readable reason.
- Every regime output must include evidence and uncertainty.

Priority: P0.

### 6.3 Portfolio Copilot

Purpose: make the system understand the user's current holdings and risk exposure.

Inputs:

- Portfolio, positions, buy date, buy price, quantity, cost, strategy type, investment thesis, stop-loss, target holding period, and current price.

Outputs:

- Position diagnosis.
- Position risk level.
- Exposure by sector, theme, strategy, and holding period.
- Action suggestions such as hold, observe, reduce risk, review thesis, or wait.

Business rules:

- The system must not place live trades.
- A position cannot be evaluated only by price movement; it must be compared with the original thesis.
- If no thesis exists, the position should be marked as incomplete.

Priority: P0.

### 6.4 Investment Thesis

Purpose: force every candidate or position to have a clear reason and invalidation rule.

Inputs:

- Stock, sector, strategy type, evidence, expected catalyst, entry logic, exit logic, invalidation condition, maximum position, risk, and expected holding period.

Outputs:

- Structured investment thesis.
- Thesis status: active, challenged, invalidated, completed, or archived.
- Daily thesis check result.

Business rules:

- No thesis, no buy-plan.
- Every thesis must include "what would prove this wrong".
- Thesis changes must be logged.

Priority: P0.

### 6.5 Watchlist

Purpose: separate "interesting stocks" from "tradeable plans".

Inputs:

- Candidate stocks from events, sector heat, historical impact, user additions, and Codex suggestions.

Outputs:

- Short-term hotspot watchlist.
- Medium-term quality trend watchlist.
- Status for each item: observing, waiting for entry, small test allowed, missed, risk too high, removed.

Business rules:

- Watchlist is not a buy list.
- Every item needs entry reason, removal reason, and latest review time.
- The system should avoid regenerating a completely new list every day without memory.

Priority: P1.

### 6.6 Alerts

Purpose: remind the user of risk, opportunity, and broken logic.

Inputs:

- Market regime changes, position levels, thesis status, price movement, sector heat, event lifecycle, and JoinQuant results.

Outputs:

- Alerts for stop-loss, hotspot fading, market regime weakening, overexposure, watchlist entry setup, thesis invalidation, and strategy deterioration.

Business rules:

- Alerts should explain why they fired.
- Alerts should have status: new, acknowledged, resolved, dismissed.
- Alerts should be research-only and must not trigger trades automatically.

Priority: P1.

### 6.7 Trade Plan

Purpose: turn a candidate strategy into a disciplined plan before any simulation or manual trading.

Inputs:

- Strategy card, watchlist item, thesis, risk budget, entry rule, exit rule, max loss, expected holding period, and JoinQuant backtest plan.

Outputs:

- Trade plan draft.
- JoinQuant backtest package.
- Simulation plan.

Business rules:

- A trade plan must include buy condition, do-not-buy condition, max position, stop-loss, take-profit/review condition, and review date.
- A plan can be sent to JoinQuant, but the system does not execute live trades.

Priority: P1.

### 6.8 Decision Journal

Purpose: record why a decision was made and review it later.

Inputs:

- User decision, Codex recommendation, selected evidence, rejected alternatives, market state, and emotional/risk notes.

Outputs:

- Decision journal entry.
- Review schedule.
- Lessons learned.

Business rules:

- Every simulated or manual trade plan should create a journal entry.
- A journal should separate facts, interpretation, decision, and later outcome.

Priority: P2.

### 6.9 Daily Report

Purpose: give the user one daily cockpit view instead of many parameter-heavy screens.

Inputs:

- Market regime, top events, sector heat, watchlist, portfolio diagnosis, alerts, strategy lifecycle, JoinQuant tasks, and journal review items.

Outputs:

- Daily investment assistant report with:
  - Market state.
  - Key events.
  - Hotspot lifecycle.
  - Current portfolio diagnosis.
  - Short-term watchlist.
  - Medium-term watchlist.
  - Risk alerts.
  - Today's suggested actions.

Business rules:

- Charts and conclusions first, details second.
- Missing data must be visible and understandable.
- The report must not present itself as guaranteed investment advice.

Priority: P2.

### 6.10 Simulation And Event Study

Purpose: learn which system-generated ideas are useful.

Inputs:

- Candidate strategies, watchlist entries, hypothetical signals, JoinQuant backtests, and manual outcomes.

Outputs:

- Simulation trades.
- Strategy quality review.
- Event impact statistics.
- Candidate strategy ranking for research only.

Business rules:

- Simulation records should include ideas that the user did not trade.
- Event studies should compare performance after 1, 3, 5, 10, 20, and 60 trading days when data is available.
- Ranking cannot be treated as a live-trading command.

Priority: P3.

## 7. Strategy Philosophy

The system should support a barbell workflow:

- Core sleeve: medium-term quality trend strategies.
- Satellite sleeve: short-term hotspot trend strategies.

For a RMB 100,000 starting assumption:

- Avoid high-frequency trading.
- Avoid over-diversification.
- Avoid heavy concentration in one theme.
- Avoid chasing after a hotspot is already clearly overheated.
- Prefer "candidate -> watchlist -> plan -> backtest/simulation -> review" over direct recommendation.

## 8. Data Model Additions

Proposed new tables:

- `portfolios`
- `positions`
- `investment_theses`
- `thesis_checks`
- `watchlist_items`
- `watchlist_reviews`
- `market_regime_daily`
- `hotspot_lifecycle_daily`
- `alerts`
- `trade_plans`
- `trade_journals`
- `daily_reports`
- `simulation_trades`
- `event_study_results`

Existing tables should be reused wherever possible:

- `raw_documents`
- `events`
- `event_mentions`
- `event_sector_mappings`
- `event_stock_mappings`
- `market_daily`
- `sector_daily`
- `stock_anomaly_snapshots`
- `strategy_ideas`
- `strategy_specs`
- `jq_orchestration_tasks`
- `backtest_runs`

## 9. UI Direction

The Web UI should become a decision cockpit, not a parameter console.

Main pages:

- Daily Copilot: one-screen daily report.
- Market Memory: historical event, sector, stock, and strategy memory.
- Portfolio Copilot: holdings, thesis health, exposure, and risk.
- Watchlists: short-term and medium-term observation pools.
- Alerts: risk and opportunity reminders.
- Trade Plans: candidate plans and JoinQuant packages.
- Decision Journal: decisions, reviews, and lessons.
- Strategy Lifecycle: keep current idea-to-simulation flow.
- JoinQuant Task Center: keep current orchestration center.

Design principles:

- Show conclusions and charts before tables.
- Keep filters light: date, topic, sector, strategy type, risk level.
- Do not put large JSON, code, or parameter blocks in the primary view.
- Use Codex instructions for complex operations.
- Every recommendation must show evidence, risk, and status.

## 10. Codex-Orchestrated Operations

Codex should be able to:

- Ask the system to collect daily information.
- Ask for today's market regime and daily report.
- Add or update holdings.
- Create or revise an investment thesis.
- Add stocks to a watchlist.
- Generate alerts and explain them.
- Draft trade plans.
- Send selected plans to JoinQuant for backtest or simulation.
- Import JoinQuant results.
- Write decision journal and review entries.

The system should expose structured local APIs for each operation.

## 11. Safety Boundaries

- Do not use or request `OPENAI_API_KEY`.
- Keep `LANGCHAIN_PROVIDER=openai-codex` and ChatGPT/Codex OAuth flow.
- Do not store brokerage credentials or JoinQuant passwords.
- Do not bypass login, captcha, or platform restrictions.
- Do not automatically place live trades.
- Treat all outputs as research, simulation, planning, and review.
- Show uncertainty, missing data, and source quality.

## 12. Non-Goals

These are explicitly out of scope for the next stage:

- Full system rewrite.
- Automatic live trading.
- High-frequency intraday trading.
- Deep learning model training.
- Paid data dependency as the default path.
- Saving secrets in source code, frontend files, screenshots, issues, or PRs.
- Treating backtest ranking as proof that a strategy is fit for live capital.

## 13. Acceptance Criteria

The V3 copilot upgrade is accepted when:

- Existing data collection and current pages still run.
- The user can view a daily investment assistant report.
- The system can store positions, theses, watchlists, alerts, trade plans, journals, and simulation records.
- Codex can drive the workflow through local APIs.
- The UI presents conclusions, charts, evidence, and status instead of dense parameter forms.
- JoinQuant remains the backtest and simulation environment.
- Every PR has code review, feature acceptance cases, whole-system regression cases, and automated tests.

## 14. Version Notes

V3 changes the system center from "discover stocks" to "manage decisions".

The right implementation path is gradual refactoring:

1. Preserve the working collection system.
2. Add decision memory.
3. Add position and thesis discipline.
4. Add watchlists and alerts.
5. Add trade plans and journals.
6. Add daily copilot report.
7. Expand simulation and event studies after enough data is accumulated.
