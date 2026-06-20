# PR-08 Code Review

## Scope Check

- Status: CLEAN
- Intent: Convert mapped A-share events into ranked sector heat scores.
- Delivered: Added `sector_scores`, local sector scoring service, protected run/list APIs, tests, acceptance script, and acceptance docs.
- Out of scope avoided: no candidate-pool writes, no user-added stock management, no strategy generation, no external market-data fetch, no LLM API calls, and no live trading actions.

## Pre-Landing Review

Pre-Landing Review: No unresolved issues found.

AUTO-FIXED:

- None.

## Review Evidence

- SQL and data safety: API inputs are bounded by Pydantic/FastAPI; SQL values are parameterized; dynamic SQL is not used in the scoring service.
- Auth boundary: `/api/event-radar/sector-scores/run` and `/api/event-radar/sector-scores` stay behind `require_local_or_auth`.
- Cost guardrail: PR-08 introduces no `OPENAI_API_KEY` usage, no OpenAI API calls, and no LLM dependency.
- Research boundary: scoring writes only local research rows in `sector_scores`; it does not create candidate positions, orders, or execution signals.
- Scoring traceability: output keeps component scores for event heat, market confirmation, breadth, flow, persistence, crowding risk, final heat, and cycle stage.
- Test coverage: tests cover table creation, service scoring, market-data confirmation, API round trip, route mounting, Chinese error handling, and prior PR-07 mapping acceptance.

## Verification

Latest local checks:

```text
bash scripts/acceptance-pr-08
9 tests passed; PR-08 acceptance passed.

bash scripts/acceptance-pr-07
10 tests passed; PR-07 acceptance passed.

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
