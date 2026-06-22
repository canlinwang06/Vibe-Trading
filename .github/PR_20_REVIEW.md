# PR-20 Code Review

## Scope

- PR: PR-20
- Branch: `codex/pr-20-simulation-readiness-report`
- Base: `codex/pr-19-joinquant-report-ui`
- Files reviewed:
  - `agent/src/joinquant_adapter/service.py`
  - `agent/src/api/joinquant_routes.py`
  - `agent/tests/test_joinquant_adapter.py`
  - `scripts/acceptance-pr-20`
  - `.github/PR_20_ACCEPTANCE.md`

## Review Summary

```text
Decision: approve
```

## Blocker

- None

## Important

- None

## Follow-up

- Add a Chinese frontend panel for this readiness report after the backend JSON contract has been validated with real simulated JoinQuant exports.

## Required Checks

- [x] The PR stays inside the current local Git project.
- [x] The PR does not introduce `OPENAI_API_KEY`.
- [x] The PR does not add JoinQuant login, browser automation, remote submission, live trading, or broker actions.
- [x] The readiness report includes execution failures, missing reports, weight deviations, signal delays, limit/suspension issues, and backtest drawdown evidence.
- [x] Targeted acceptance tests passed.
- [x] Previous PR acceptance passed.
- [x] Backend compile check passed.
- [x] Frontend full test suite passed.
- [x] Frontend build passed.
- [x] Automated smoke test passed.

## Review Checklist

| Area | Result | Evidence |
| --- | --- | --- |
| Scope control | Pass | PR-20 adds one backend readiness report and route without changing import, export, or UI behavior |
| API-key guardrail | Pass | No `OPENAI_API_KEY`, paid LLM API client, or model-call path is introduced |
| Trading guardrail | Pass | Report remains research-only and does not log in to JoinQuant, submit orders, call brokers, or enable live trading |
| Readiness contract | Pass | Report returns status, recommendation, score, totals, rates, checks, findings, daily summaries, and research-only flags |
| Risk evidence | Pass | Tests cover clean simulation, insufficient observation, failed execution, weight deviation, limit-up issue, and high backtest drawdown |
| Automated acceptance | Pass | `scripts/acceptance-pr-20` covers tests, route registration, readiness implementation, and guardrails |

## Verification Evidence

```text
bash scripts/acceptance-pr-20
16 tests passed; PR-20 acceptance passed.

bash scripts/acceptance-pr-19
10 tests passed; PR-19 acceptance passed.

.venv/bin/python -m compileall -q agent
passed

npm --prefix frontend run test:run
25 test files passed; 223 tests passed.

npm --prefix frontend run build
passed

bash scripts/smoke
PR smoke test passed.

git diff --check
passed
```
