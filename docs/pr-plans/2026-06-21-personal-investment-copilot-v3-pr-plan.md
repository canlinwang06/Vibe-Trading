# Personal Investment Copilot V3 PR Plan

Date: 2026-06-21
Spec: `docs/superpowers/specs/2026-06-21-personal-investment-copilot-v3.md`
Action-display refinement: `docs/pr-plans/2026-06-21-advisor-action-display-pr-plan.md`

## 2026-06-21 Refinement

The broad PR-C plan remains the product baseline. The approved "advisor action display" experience has been decomposed into PR-A0 to PR-A13 in `docs/pr-plans/2026-06-21-advisor-action-display-pr-plan.md`.

Use the PR-A plan when implementing the simplified investor-facing page that answers:

- What should I do with current holdings?
- What should I prepare to buy, and only under what conditions?
- What should I avoid buying now?
- What can I ask Codex to do next?

## Overall Build Strategy

This plan extends the current A-share event strategy workbench into a personal investment copilot.

Do not delete or rewrite the existing collection system. Build the copilot core beside it, expose local APIs for Codex, and keep the Web UI focused on structured presentation.

Every PR must include:

- Code review before acceptance.
- Acceptance cases for the current PR.
- Whole-system regression acceptance cases.
- Automated tests.
- Backend compile check when backend code changes.
- Frontend build when frontend code changes.
- Research-only and no-live-trading guardrails.

## PR-C0: Product Baseline And Migration Map

Goal: make V3 the product baseline without changing runtime behavior.

Scope:

- Add the V3 product spec and PR plan.
- Map existing pages, APIs, and tables to the future copilot modules.
- Mark reused, extended, and new components.

Acceptance:

- Documentation states that existing collection capabilities are retained.
- Documentation identifies new copilot modules and non-goals.
- No runtime code changes.

Tests:

- Documentation files exist.
- Git diff contains only docs.

## PR-C1: Market Memory Contract

Goal: standardize the memory layer that connects events, market snapshots, sectors, stocks, strategies, JoinQuant results, and journals.

Scope:

- Add or document service contracts for day/topic/sector/stock/strategy memory queries.
- Normalize event time fields, source references, and evidence metadata in API responses.
- Add missing local query endpoints only where needed.
- Preserve existing `raw_documents`, `events`, `market_daily`, `sector_daily`, and strategy tables.

Acceptance:

- Codex can query what happened on a given date.
- Each returned item has source quality, time fields, and evidence reference.
- Closed-market or missing-data days return readable status.

Tests:

- Backend memory API tests.
- Closed-market fixture test.
- `.venv/bin/python -m compileall -q agent`.

## PR-C2: Portfolio And Position Core

Goal: let the system understand what the user currently holds.

Scope:

- Add `portfolios` and `positions` tables.
- Add APIs to create, update, list, and archive portfolios and positions.
- Track buy date, cost, quantity, strategy type, thesis link, status, and risk notes.
- Add Codex-friendly endpoints for position summaries.

Acceptance:

- User can record a position without touching source code.
- A position can be linked to an investment thesis later.
- No live trading or broker action exists.

Tests:

- Position CRUD tests.
- Portfolio summary test.
- Safety guardrail test.

## PR-C3: Investment Thesis Core

Goal: require every candidate or position to have a clear logic and invalidation rule.

Scope:

- Add `investment_theses` and `thesis_checks`.
- Add APIs for creating, updating, checking, and archiving theses.
- Fields include thesis type, evidence, catalyst, entry logic, exit logic, invalidation condition, max position, holding period, and status.
- Add daily thesis check service that can be called by Codex.

Acceptance:

- A thesis can answer why the stock is watched or held.
- A thesis can be marked active, challenged, invalidated, completed, or archived.
- Thesis changes are logged.

Tests:

- Thesis status transition tests.
- Missing invalidation condition validation test.
- Position-thesis linkage test.

## PR-C4: Market Regime Engine

Goal: answer whether the current market is suitable for trading before discussing candidates.

Scope:

- Add `market_regime_daily`.
- Build rule-based regime scoring from available market, sector, anomaly, breadth, and risk inputs.
- Support closed-market and partial-data status.
- Expose daily market regime API.

Acceptance:

- Output includes market state, short-term stance, medium-term stance, exposure band, evidence, and uncertainty.
- Missing data is visible instead of failing silently.
- Regime is clearly labeled as risk filter, not buy signal.

Tests:

- Strong, weak, range-bound, and partial-data fixture tests.
- Closed-market day test.
- API response shape test.

## PR-C5: Watchlist Core

Goal: separate observation from trade planning.

Scope:

- Add `watchlist_items` and `watchlist_reviews`.
- Support short-term hotspot and medium-term quality trend watchlists.
- Track source, reason, status, entry condition, removal condition, latest review, and linked evidence.
- Allow Codex to add, update, rank, and remove items.

Acceptance:

- A candidate stock can be saved to a watchlist.
- Watchlist items have status and reason.
- Removed items keep history.

Tests:

- Watchlist CRUD tests.
- Status transition tests.
- Evidence link test.

## PR-C6: Alert Center

Goal: surface risk and opportunity reminders.

Scope:

- Add `alerts`.
- Generate alerts from regime change, thesis invalidation, position risk, watchlist entry setup, hotspot fading, and JoinQuant result deterioration.
- Add APIs to list, acknowledge, dismiss, and resolve alerts.

Acceptance:

- Alerts explain why they fired.
- Alerts do not trigger trades.
- Alerts can be filtered by risk level, topic, stock, and status.

Tests:

- Alert rule tests.
- Alert status transition tests.
- No-live-trading guardrail test.

## PR-C7: Trade Plan Core

Goal: turn a candidate strategy into a disciplined plan before JoinQuant backtest or simulation.

Scope:

- Add `trade_plans`.
- Support plan draft from strategy card, watchlist item, or thesis.
- Fields include entry condition, do-not-buy condition, max position, stop-loss, take-profit or review condition, expected holding period, risk level, and JoinQuant package link.
- Integrate with existing JoinQuant task center.

Acceptance:

- Codex can create a trade plan from a candidate strategy.
- A trade plan can create a JoinQuant task.
- The plan remains research-only.

Tests:

- Trade plan validation tests.
- JoinQuant task linkage tests.
- Plan-to-task regression test.

## PR-C8: Decision Journal

Goal: record decisions and enable later review.

Scope:

- Add `trade_journals`.
- Support journal entries for decisions, rejected alternatives, Codex rationale, user notes, market state, and review schedule.
- Add APIs for creating and reviewing journal entries.

Acceptance:

- Every accepted trade plan can create a journal entry.
- Journal separates facts, interpretation, decision, and later outcome.
- Review schedule can be queried by Codex.

Tests:

- Journal creation tests.
- Trade plan journal linkage test.
- Review due query test.

## PR-C9: Daily Copilot Report

Goal: provide one daily investment assistant view.

Scope:

- Add `daily_reports`.
- Combine market regime, key events, sector heat, watchlists, portfolio diagnosis, alerts, strategy lifecycle, JoinQuant tasks, and journal review items.
- Add daily report API.
- Add Web page focused on charts, conclusion cards, and evidence links.

Acceptance:

- User can open one page and understand today's market state and actions.
- Closed-market days are explained.
- Charts and summary cards appear before detail tables.

Tests:

- Daily report service tests.
- Frontend loading, empty, closed-market, and normal states.
- `npm --prefix frontend run build`.

## PR-C10: Portfolio Copilot Page

Goal: visualize holdings, thesis health, and exposure.

Scope:

- Add Portfolio Copilot page.
- Show holdings, sector/theme exposure, thesis status, risk flags, and upcoming reviews.
- Keep editing lightweight; complex operations are Codex-driven.

Acceptance:

- User can see current holdings and whether each thesis still holds.
- Page does not look like a trading terminal.
- No live trade button exists.

Tests:

- Frontend page tests.
- API integration smoke test.
- Build passes.

## PR-C11: Simulation And Event Study

Goal: learn from candidate ideas without requiring live trading.

Scope:

- Add `simulation_trades` and `event_study_results`.
- Track system-generated ideas that were traded, backtested, simulated, or ignored.
- Calculate event impact windows when data exists.
- Link simulation outcomes to strategy and thesis quality.

Acceptance:

- System can record a candidate idea even if the user did not trade it.
- Event studies report T+1, T+3, T+5, T+10, T+20, and T+60 when available.
- Results are labeled research-only.

Tests:

- Simulation record tests.
- Event impact window tests.
- Partial-data degradation test.

## PR-C12: End-To-End Copilot Acceptance

Goal: verify the full product flow locally.

Scope:

- Browser test from daily collection to daily report.
- Create portfolio, position, thesis, watchlist item, alert, trade plan, JoinQuant task, imported result, journal entry, and simulation record.
- Update user-facing documentation.

Acceptance:

- The full flow runs in local VS Code environment.
- Frontend build passes.
- Backend compile and test suite pass.
- The user can operate primarily through Codex commands.

Tests:

- Full smoke script.
- Browser real-flow test.
- Regression tests for existing event and JoinQuant pages.

## Sequencing

Recommended sequence:

1. PR-C0 to PR-C1 establish the foundation.
2. PR-C2 to PR-C4 build discipline: holdings, theses, and market regime.
3. PR-C5 to PR-C7 build opportunity handling: watchlists, alerts, and trade plans.
4. PR-C8 to PR-C10 build daily usage: journal, report, and portfolio page.
5. PR-C11 to PR-C12 add learning loop and full acceptance.

## Explicitly Deferred

- Full rewrite.
- Automatic live trading.
- Brokerage integration.
- Deep learning model training.
- Paid data as a hard dependency.
- Using `OPENAI_API_KEY`.
- Treating backtest ranking as live-trading permission.
