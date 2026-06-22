# PR-06 Code Review

## Scope Check

- Status: CLEAN
- Intent: Convert PR-05 raw documents into structured event records and event clusters.
- Delivered: Added local rule-based extraction, point-in-time timestamps, A-share relevance scoring, event clustering, event query APIs, tests, and acceptance docs.
- Out of scope avoided: no LLM API calls, no external crawler, no sector mapping, no candidate-pool writes, no strategy generation, and no live trading actions.

## Pre-Landing Review

Pre-Landing Review: No unresolved issues found.

AUTO-FIXED:

- `agent/src/event_radar/event_extraction.py`: fixed weekend `tradable_time` calculation so Saturday/Sunday knowable events map to the next Monday 09:30.
- `agent/src/event_radar/event_extraction.py`: changed event, mention, and cluster writes to tolerate duplicate/concurrent extraction conflicts without surfacing a database error.

## Review Evidence

- SQL and data safety: user-provided filters are validated or parameterized; dynamic filter SQL is assembled only from fixed local fragments.
- Auth boundary: `/api/event-radar/*` extraction/query routes stay behind the existing `require_local_or_auth` dependency.
- Cost guardrail: PR-06 introduces no `OPENAI_API_KEY` usage and no LLM API calls.
- Point-in-time safety: extraction stores `publish_time`, `crawl_time`, `knowable_time`, and `tradable_time`; tests cover after-close and weekend timing.
- Event clustering: same topic/day/source-family documents aggregate into one `event_cluster` with mention count, source count, hot score, and cross-platform score.
- Test coverage: tests cover event extraction, cluster grouping, weekend tradable time, Chinese error handling, and API collect/extract/query round trip.

## Verification

Latest local checks:

```text
bash scripts/acceptance-pr-06
6 tests passed; PR-06 acceptance passed.

bash scripts/acceptance-pr-05
6 tests passed; PR-05 acceptance passed.

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
