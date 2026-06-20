# PR-11 Code Review

## Scope Check

- Status: CLEAN
- Intent: Add a local batch backtest factory for A-share strategy specs.
- Delivered: Added `strategy_lab/backtest_factory.py`, batch/list/detail backtest APIs, `backtest_runs` writes, run artifacts, tests, acceptance script, and acceptance docs.
- Out of scope avoided: no strategy allocation, no execution signals, no JoinQuant export, no broker calls, no LLM API calls, and no live trading actions.

## Pre-Landing Review

Pre-Landing Review: No unresolved issues found.

AUTO-FIXED:

- `agent/src/strategy_lab/backtest_factory.py`: wrapped long expressions to stay within the repository's 120-character style expectation.
- `agent/tests/test_backtest_factory.py`: wrapped long candidate fixture rows for readability and style consistency.

## Review Evidence

- SQL and data safety: API inputs are bounded by Pydantic/FastAPI; SQL values are parameterized; dynamic filters use generated placeholders only for strategy IDs.
- Auth boundary: `/api/strategy-lab/backtest-batch`, `/api/strategy-lab/backtest-runs`, and `/api/strategy-lab/backtest-runs/{run_id}` stay behind `require_local_or_auth`.
- Cost guardrail: PR-11 introduces no `OPENAI_API_KEY` usage, no OpenAI API calls, and no LLM dependency.
- Research boundary: backtests read local `candidate_pool`, `strategy_specs`, and `market_daily`; they write only `backtest_runs` and local artifacts.
- Trading guardrail: artifacts explicitly mark `live_trading=false`, long-only, no leverage, 100-share lot assumptions, and T+1 simulated execution.
- Test coverage: tests cover batch run writes, metrics, artifacts, run detail lookup, API round trip, route mounting, Chinese prerequisite errors, and prior PR-10 acceptance.

## Verification

Latest local checks:

```text
bash scripts/acceptance-pr-11
9 tests passed; PR-11 acceptance passed.

bash scripts/acceptance-pr-10
10 tests passed; PR-10 acceptance passed.

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
