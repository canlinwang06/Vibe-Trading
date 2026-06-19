# PR-05 Code Review

## Scope Check

- Status: CLEAN
- Intent: Add the event radar ingestion foundation before PR-06 event extraction.
- Delivered: Added default event sources, manual collection, raw-document persistence, content-hash deduplication, protected API routes, tests, and acceptance docs.
- Out of scope avoided: no live web crawler, no LLM event extraction, no strategy generation, no JoinQuant export, and no live trading actions.

## Pre-Landing Review

Pre-Landing Review: No unresolved issues found.

AUTO-FIXED:

- `agent/src/event_radar/source_ingestion.py`: handled duplicate insert conflicts so concurrent submissions of the same document are reported as duplicates instead of surfacing a database error.

## Review Evidence

- SQL and data safety: user-provided source IDs, source types, document hashes, dates, and limits are bound as DuckDB parameters; dynamic SQL fragments only use fixed allowlisted filter clauses.
- Auth boundary: `/api/event-radar/*` routes are mounted with the existing `require_local_or_auth` dependency.
- Cost guardrail: PR-05 introduces no `OPENAI_API_KEY` usage and no LLM API calls.
- Compliance guardrail: PR-05 seeds source metadata and supports manual JSON ingestion only; it does not scrape pages, bypass login, or read arbitrary local paths through the API.
- Point-in-time fields: raw documents persist `publish_time`, `crawl_time`, and `content_hash` before later structured event extraction.
- Test coverage: tests cover default source seeding, raw-document write, deduplication, Chinese error handling, route mounting, and API round trip.

## Verification

Latest local checks:

```text
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
