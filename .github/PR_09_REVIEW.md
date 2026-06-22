# PR-09 Code Review

## Scope Check

- Status: CLEAN
- Intent: Generate a local A-share candidate pool from sector radar outputs and support manual review controls.
- Delivered: Added candidate-pool service, protected list/build/user-add/include/exclude APIs, tests, acceptance script, and acceptance docs.
- Out of scope avoided: no strategy generation, no backtest execution, no execution signals, no broker calls, no LLM API calls, and no live trading actions.

## Pre-Landing Review

Pre-Landing Review: No unresolved issues found.

AUTO-FIXED:

- `agent/src/candidate_pool/service.py`: user-add now returns the exact inserted candidate by `as_of_date` and `ticker`, instead of relying on the first row from a broader user-added list.
- `agent/src/candidate_pool/service.py`: build now reports the missing sector-score prerequisite before checking stock mappings when a requested date has no scored sectors.

## Review Evidence

- SQL and data safety: user inputs are validated by Pydantic/FastAPI or normalized as A-share codes; SQL values are parameterized; dynamic candidate-list filters use fixed local fragments only.
- Auth boundary: `/api/candidate-pool`, `/api/candidate-pool/build`, `/api/candidate-pool/user-add`, `/api/candidate-pool/include`, and `/api/candidate-pool/exclude` stay behind `require_local_or_auth`.
- Cost guardrail: PR-09 introduces no `OPENAI_API_KEY` usage, no OpenAI API calls, and no LLM dependency.
- Research boundary: candidate operations write only `candidate_pool`; they do not create `execution_signals`, submit orders, or call broker/live-trading code.
- Review workflow: system candidates preserve source, theme, sector, event heat, sector heat, stock score, risk flag, inclusion state, and reason for manual inspection.
- Test coverage: tests cover candidate generation from mapped stocks and sector scores, manual add, include/exclude toggles, API round trip, route mounting, and Chinese prerequisite errors.

## Verification

Latest local checks:

```text
bash scripts/acceptance-pr-09
10 tests passed; PR-09 acceptance passed.

bash scripts/acceptance-pr-08
9 tests passed; PR-08 acceptance passed.

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
