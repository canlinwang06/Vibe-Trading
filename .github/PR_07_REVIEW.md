# PR-07 Code Review

## Scope Check

- Status: CLEAN
- Intent: Map extracted A-share events to local themes, sectors, and representative stocks.
- Delivered: Added event-to-theme mapping service, seeded local theme map, sector and stock mapping tables, protected mapping APIs, tests, and acceptance docs.
- Out of scope avoided: no LLM API calls, no paid API key usage, no external data fetch, no candidate-pool scoring, no strategy generation, and no live trading actions.

## Pre-Landing Review

Pre-Landing Review: No unresolved issues found.

AUTO-FIXED:

- None.

## Review Evidence

- SQL and data safety: user-provided `theme`, `event_id`, `limit`, and `min_relevance` values are bounded or parameterized; dynamic SQL only joins fixed local filter fragments.
- Auth boundary: new `/api/event-radar/theme-map`, `/api/event-radar/map/run`, `/api/event-radar/mappings/sectors`, and `/api/event-radar/mappings/stocks` routes stay behind `require_local_or_auth`.
- Cost guardrail: PR-07 introduces no `OPENAI_API_KEY` usage, no OpenAI API calls, and no LLM dependency.
- Research boundary: mapping writes only local research tables and does not place trades, create brokerage orders, or call live-trading APIs.
- Idempotency: mapping reruns delete existing sector/stock mappings for the selected event before rewriting current matches.
- Test coverage: tests cover default theme seeding, sector/member seeding, event-to-sector mapping, event-to-stock mapping, API round trip, route mounting, and Chinese error handling.

## Verification

Latest local checks:

```text
bash scripts/acceptance-pr-07
10 tests passed; PR-07 acceptance passed.

bash scripts/acceptance-pr-06
6 tests passed; PR-06 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
213 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
