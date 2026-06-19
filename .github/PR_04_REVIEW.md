# PR-04 Code Review

## Scope Check

- Status: CLEAN
- Intent: Add A-share asset master data, daily market-data persistence, and a manual update API.
- Delivered: Added core A-share/index assets, local/AKShare daily-bar ingestion, authenticated API routes, tests, and an acceptance script.
- Out of scope avoided: no news ingestion, no strategy backtest changes, no JQ export, no live trading actions.

## Pre-Landing Review

Pre-Landing Review: No unresolved issues found.

AUTO-FIXED:

- `agent/src/ashare_data/market_data.py`: removed an unused private helper discovered during review.

## Review Evidence

- SQL and data safety: `assets` and `market_daily` writes use parameterized DuckDB statements in `AShareMarketDataService.upsert_assets` and `AShareMarketDataService.upsert_market_daily`.
- Auth boundary: `/ashare/*` routes are mounted with the existing `require_local_or_auth` dependency.
- Source guardrails: update source is restricted to `auto`, `local`, or `akshare`; ticker validation keeps the PR-04 surface inside Shanghai/Shenzhen A-share codes.
- Error handling: invalid ticker, invalid date window, empty data, and loader failures surface readable Chinese errors.
- API key/cost guardrail: this PR does not introduce `OPENAI_API_KEY` usage and does not add any LLM API calls.

## Verification

Latest local checks:

```text
bash scripts/acceptance-pr-04
7 tests passed; PR-04 acceptance passed.

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
