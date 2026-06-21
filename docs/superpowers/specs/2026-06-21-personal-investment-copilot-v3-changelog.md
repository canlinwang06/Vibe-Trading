# Personal Investment Copilot V3 Changelog

## 3.1.0 - 2026-06-21

Change type: added

Summary:

- Added an executable PR-A0 to PR-A13 plan for the approved advisor action display.
- Clarified that the Web UI should show investor-facing action results instead of complex backend analysis steps.
- Added implementation scope for holdings, sell lines, buy triggers, do-not-buy filters, Codex command helpers, alerts, journals, and JoinQuant result writeback.
- Confirmed desktop-only first delivery for the advisor display page.

Impact:

- Documentation only.
- No runtime behavior change.
- Future implementation work for the simplified advisor page should reference `docs/pr-plans/2026-06-21-advisor-action-display-pr-plan.md`.

## 3.0.0 - 2026-06-21

Change type: added

Summary:

- Added V3 product baseline for evolving Vibe-Trading from an event strategy workbench into a personal AI investment copilot.
- Confirmed the product should not be rebuilt from scratch.
- Preserved existing data collection, event, sector, strategy, JoinQuant, and local API capabilities.
- Added new target modules: market memory, market regime, portfolio copilot, investment thesis, watchlist, alerts, trade plans, decision journal, daily report, simulation, and event study.
- Added PR-C0 to PR-C12 implementation plan.
- Reconfirmed research-only, no OpenAI API key, no stored JoinQuant password, and no automatic live trading boundaries.

Impact:

- Documentation only.
- No runtime behavior change.
- Future implementation PRs should reference `docs/superpowers/specs/2026-06-21-personal-investment-copilot-v3.md`.
